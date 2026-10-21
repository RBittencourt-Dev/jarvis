"""Mandar mensagem no WhatsApp por voz, sempre com confirmação.

Conversa em etapas: falta destinatário → "Pra quem?"; falta texto → "Qual a mensagem?";
número desconhecido → "Qual o número?" (e grava em contatos.json). No fim: "Vou mandar pro
João: … Confirma?". O envio usa o WhatsApp Desktop dele: abre a conversa com o texto pronto
e aperta Enter, mas só se a janela da frente for mesmo o WhatsApp.

Disparo em massa (pros leads) NÃO é feito aqui: o Radar já dispara com ritmo seguro, sem
arriscar o número ser banido.
"""
import ctypes
import json
import os
import re
import time
import unicodedata
from pathlib import Path
from urllib.parse import quote

RAIZ = Path(__file__).parent
ARQUIVO_CONTATOS = RAIZ / "contatos.json"
DDD_PADRAO = "51"

CANCELAR = re.compile(r"^(cancela|cancelar|deixa|deixa pra l[aá]|esquece|para|n[aã]o manda)\b", re.I)

# "manda pro João dizendo que tô chegando" / "manda uma mensagem pra Laura: oi" / "envia uma mensagem"
VERBO = re.compile(r"^(?:jarvis[ ,]*)?(manda|mande|envia|envie|escreve|escreva|fala|diz|avisa)\s*", re.I)
COISA = re.compile(r"^(?:uma?\s+)?(?:mensagem|msg|zap|zapzap|whats|whatsapp|recado)(?:\s+(?:no|pelo)\s+(?:whatsapp|zap))?\s*", re.I)
PARA = re.compile(r"^(?:pro|pra|para|ao|à)\s+(?:(?:o|a)\s+)?", re.I)
SEPARADOR = re.compile(r"\s*[,:]\s*|\s+(?:dizendo|falando|escrevendo|perguntando|avisando)\s+(?:que\s+)?|"
                       r"\s+(?:e\s+)?(?:escreve|escreva|diz|diga|fala|fale|manda|mande|pergunta|pergunte|avisa|avise)\s+(?:que\s+)?|"
                       r"\s+que\s+", re.I)
NO_WHATS = re.compile(r"\s+(?:no|pelo|pela|via)\s+(?:whats\s*app|whats|zap(?:zap)?)\b", re.I)
# "manda pra ele", "pro mesmo", "de novo pra ela": a pessoa da última mensagem
ELE = re.compile(r"^(?:ele|ela|o mesmo|a mesma|ele de novo|ela de novo|mesmo|mesma)$", re.I)
ultimo = {"quem": None}
EM_MASSA = re.compile(r"\b(dispar\w*|todos os leads|pros leads|para os leads|em massa|pra todo mundo)\b", re.I)


PARA_NO_MEIO = re.compile(r"\s+(?:pro|pra|para o|para a|para|ao|à)\s+", re.I)

# "minha mãe", "o meu sócio", "a Laura" → "mae", "socio", "laura": é a chave do contato
POSSESSIVOS = re.compile(r"^(?:(?:a|o|as|os)\s+)?(?:minha|meu|minhas|meus|nossa|nosso)?\s*", re.I)


def _chave(nome):
    t = unicodedata.normalize("NFD", POSSESSIVOS.sub("", nome.strip()).lower().strip())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _contatos():
    if ARQUIVO_CONTATOS.exists():
        try:
            return json.loads(ARQUIVO_CONTATOS.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return {}


def guardar_contato(como_ele_chama, telefone=None, salvo_como=None, verificado=None):
    """"mãe" → telefone e/ou nome salvo no WhatsApp ("Coroa"). Guarda o jeito como ELE chama a pessoa."""
    contatos = _contatos()
    chave = _chave(como_ele_chama)
    atual = contatos.get(chave, {"nome": POSSESSIVOS.sub("", como_ele_chama.strip()) or como_ele_chama.strip()})
    if telefone:
        atual["telefone"] = telefone
    if salvo_como:
        atual["salvo_como"] = salvo_como
        atual.setdefault("verificado", False)
    if verificado is not None:
        atual["verificado"] = verificado
    contatos[chave] = atual
    ARQUIVO_CONTATOS.write_text(json.dumps(contatos, ensure_ascii=False, indent=1), encoding="utf-8")
    return atual


DIGITOS_FALADOS = {"zero": "0", "um": "1", "uma": "1", "dois": "2", "duas": "2", "tres": "3", "três": "3", "quatro": "4",
                   "cinco": "5", "seis": "6", "meia": "6", "sete": "7", "oito": "8", "nove": "9"}


def numero_do_texto(texto):
    """"51 99876-5432" ou "cinco um nove nove…" → "5551998765432"; None se não parecer telefone."""
    falado = " ".join(DIGITOS_FALADOS.get(p, p) for p in texto.lower().split())
    digitos = re.sub(r"\D", "", falado)
    if len(digitos) in (8, 9):
        digitos = DDD_PADRAO + digitos
    if len(digitos) in (10, 11):
        digitos = "55" + digitos
    return digitos if len(digitos) in (12, 13) else None


SALVO_COMO = re.compile(
    r"(?:t[aá]|est[aá]|fica|ficou)?\s*salv[oa]\s+como\s+(.+)|(?:no whats(?:app)?\s+)?(?:[eé]|chama|se chama|aparece como)\s+(?:a\s+|o\s+)?(.+)",
    re.I)


def salvo_como_do_texto(texto):
    """"tá salva como Coroa" / "é a Coroa" / "Coroa" → "Coroa"."""
    m = SALVO_COMO.search(texto.strip())
    nome = (m.group(1) or m.group(2)) if m else texto
    return nome.strip(" .!\"'") or None


def achar_contato(nome, leads=None):
    """Procura em contatos.json (pelo jeito que ele chama a pessoa) e depois nos leads do Radar."""
    chave = _chave(nome)
    contatos = _contatos()
    if chave in contatos:
        return contatos[chave]
    parecido = [c for k, c in contatos.items() if chave in k or k in chave]
    if len(parecido) == 1:
        return parecido[0]
    for lead in leads() if leads else []:
        if chave and chave in _chave(lead.get("nome", "")):
            numero = numero_do_texto(lead.get("whatsapp") or lead.get("telefone") or "")
            if numero:
                return {"nome": lead["nome"], "telefone": numero, "verificado": True}
    return None


def entender(texto):
    """Se é pedido de mensagem, devolve o diálogo inicial {quem, texto}; senão None."""
    if EM_MASSA.search(texto) and re.search(r"\b(mensag|zap|whats|dispar)", texto, re.I):
        return {"em_massa": True}
    v = VERBO.match(texto.strip())
    if not v:
        return None
    resto = NO_WHATS.sub("", texto.strip()[v.end():])  # "no WhatsApp" não faz parte do nome nem da mensagem
    coisa = COISA.match(resto)
    resto = resto[coisa.end():] if coisa else resto
    para = PARA.match(resto)
    if not para and v.group(1).lower() in ("avisa", "fala", "diz") and re.match(r"^(?:o|a|com o|com a)\s+\S", resto, re.I):
        para = re.match(r"^(?:com\s+)?(?:o|a)\s+", resto, re.I)  # "avisa o Jesus que…" também é mensagem
    quem = mensagem = None
    if para:
        resto = resto[para.end():]
        sep = SEPARADOR.search(resto)
        quem, mensagem = (resto[:sep.start()], resto[sep.end():]) if sep else (resto, None)
    elif coisa:
        mensagem = (SEPARADOR.sub("", resto, count=1) if SEPARADOR.match(resto) else resto) or None
    else:
        # "manda um oi pra minha mãe": mensagem curta ANTES do "pra"
        meio = PARA_NO_MEIO.search(resto)
        if not meio or len(resto[:meio.start()].split()) > 6 or v.group(1).lower() in ("fala", "diz", "avisa"):
            return None  # "manda ver", "fala com o cliente": não é mensagem
        mensagem = re.sub(r"^(?:um|uma)\s+", "", resto[:meio.start()], flags=re.I)
        quem = resto[meio.end():]
        sep = SEPARADOR.search(quem)
        if sep:  # "manda outra pra ele dizendo valeu": a mensagem é o que vem depois do "dizendo"
            quem, depois = quem[:sep.start()], quem[sep.end():]
            if re.fullmatch(r"(?:outra|mais uma)(?:\s+mensagem)?|mensagem|recado|msg", mensagem.strip(), re.I):
                mensagem = depois
            else:
                mensagem = f"{mensagem} {depois}".strip()
        elif re.fullmatch(r"(?:outra|mais uma)(?:\s+mensagem)?", mensagem.strip(), re.I):
            mensagem = ""  # "manda outra pra ele": pergunta o texto
    if v.group(1).lower() in ("fala", "diz", "avisa") and not (quem and mensagem):
        return None  # "fala pro Jesus" sozinho é conversa; "fala pro Jesus que…" é mensagem
    quem = (quem or "").strip(" ,.") or None
    if quem and ELE.match(quem) and ultimo["quem"]:
        quem = ultimo["quem"]  # "manda outra pra ele"
    return {"quem": quem, "texto": (mensagem or "").strip() or None}


def _como_chamar(d):
    """"sua mãe" quando ele disse "minha mãe"; senão o nome."""
    dito = d.get("como_disse") or d["quem"]
    return re.sub(r"^(?:a\s+|o\s+)?(minha|meu)\s+", lambda m: "sua " if m.group(1).lower() == "minha" else "seu ", dito, flags=re.I)


def proximo_passo(d, leads=None):
    """Olha o que falta no diálogo e devolve o que o Jarvis fala (e a etapa em que fica)."""
    if not d.get("quem"):
        d["etapa"] = "quem"
        return "Pra quem, chefe?"
    if not (d.get("telefone") or d.get("salvo_como")):
        contato = achar_contato(d["quem"], leads)
        if contato:
            d.setdefault("como_disse", d["quem"])
            d["quem"] = contato.get("salvo_como") or contato["nome"]
            d["telefone"] = contato.get("telefone")
            d["salvo_como"] = contato.get("salvo_como")
            d["verificado"] = contato.get("verificado", True)
        else:
            d["etapa"] = "quem_e"
            d["como_disse"] = d["quem"]
            return f"Não sei quem é {_como_chamar(d)}. Como está salvo no WhatsApp, ou qual o número?"
    if not d.get("texto"):
        d["etapa"] = "texto"
        return f"E qual a mensagem pro {d['quem']}?"
    d["etapa"] = "confirmar"
    return f"Vou mandar pro {d['quem']}: {d['texto']}. Confirma?"


def responder(d, fala_dele, leads=None):
    """Recebe a resposta do Rafael na etapa atual e devolve a próxima fala."""
    if CANCELAR.match(fala_dele.strip()):
        d["etapa"] = "cancelado"
        return "Cancelado, chefe. Não mandei nada."
    if d["etapa"] == "quem":
        d["quem"] = re.sub(r"^(pro|pra|para)\s+", "", fala_dele.strip(), flags=re.I)
    elif d["etapa"] == "quem_e":
        # ou um número, ou o nome com que a pessoa está salva no WhatsApp ("tá salva como Coroa")
        numero = numero_do_texto(fala_dele)
        if numero:
            contato = guardar_contato(d["como_disse"], telefone=numero)
            d.update(telefone=numero, verificado=True)
        elif VERBO.match(fala_dele.strip()) or len(fala_dele.split()) > 4:
            # repetiu o pedido ("manda uma mensagem pro Rian no WhatsApp") em vez do nome salvo: não grava lixo
            novo = entender(fala_dele) or {}
            if novo.get("quem") and _chave(novo["quem"]) != _chave(d["como_disse"]):
                d.update(quem=novo["quem"], como_disse=novo["quem"], texto=d.get("texto") or novo.get("texto"))
                d.pop("telefone", None)
                d.pop("salvo_como", None)
                return proximo_passo(d, leads)
            return "Só o nome como está salvo no WhatsApp, chefe, ou o número com DDD."
        else:
            salvo = salvo_como_do_texto(fala_dele)
            if not salvo:
                return "Não entendi, chefe. Me diz o nome como está no WhatsApp, ou o número com DDD."
            contato = guardar_contato(d["como_disse"], salvo_como=salvo)
            d.update(salvo_como=salvo, quem=salvo, verificado=contato.get("verificado", False))
    elif d["etapa"] == "texto":
        d["texto"] = fala_dele.strip()
    elif d["etapa"] == "conferir":
        # depois do 1º envio pelo nome: ele olhou a tela e diz se a conversa era a certa
        if re.match(r"^(sim|isso|certo|foi|era|pode|manda|confirm|claro)", fala_dele.strip(), re.I):
            guardar_contato(d["como_disse"], verificado=True)
            apertar_enter()
            d["etapa"] = "fim"
            return f"Enviado. Agora eu sei: {_como_chamar(d)} é {d['salvo_como']} no WhatsApp. Da próxima vez mando direto."
        d["etapa"] = "quem_e"
        return "Então não mandei. Me passa o número, com DDD, que eu gravo certinho."
    return proximo_passo(d, leads)


def _janela_da_frente():
    u = ctypes.windll.user32
    hwnd = u.GetForegroundWindow()
    tamanho = u.GetWindowTextLengthW(hwnd)
    titulo = ctypes.create_unicode_buffer(tamanho + 1)
    u.GetWindowTextW(hwnd, titulo, tamanho + 1)
    return titulo.value


def _esperar_whatsapp(segundos=6):
    for _ in range(int(segundos * 4)):
        time.sleep(0.25)
        if "whatsapp" in _janela_da_frente().lower():
            return True
    return False


def _tecla(*teclas):
    u = ctypes.windll.user32
    for t in teclas:
        u.keybd_event(t, 0, 0, 0)
    for t in reversed(teclas):
        u.keybd_event(t, 0, 2, 0)


def apertar_enter():
    if "whatsapp" not in _janela_da_frente().lower():
        os.startfile("whatsapp:")
        _esperar_whatsapp(4)
    time.sleep(0.3)
    _tecla(0x0D)


def _colar(texto):
    """Escreve pela área de transferência: acento e emoji passam certinho."""
    import subprocess
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "[Console]::InputEncoding=[Text.Encoding]::UTF8; Set-Clipboard -Value ([Console]::In.ReadToEnd())"],
                   input=texto, encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
    time.sleep(0.2)
    _tecla(0x11, 0x56)  # Ctrl+V


def enviar(d):
    """Pelo número: abre a conversa certa e envia. Pelo nome salvo: busca no WhatsApp; na 1ª vez só deixa
    digitado e pergunta se é a conversa certa (ele não tem como ver isso sozinho)."""
    ultimo["quem"] = d.get("como_disse") or d.get("quem")
    if d.get("telefone"):
        os.startfile(f"whatsapp://send?phone={d['telefone']}&text={quote(d['texto'])}")
        if _esperar_whatsapp():
            time.sleep(1.2)  # o texto entra na caixa um instante depois da janela aparecer
            _tecla(0x0D)
            return f"Mensagem enviada pro {d['quem']}, chefe."
        return f"Deixei a mensagem pronta no WhatsApp pro {d['quem']}, mas não consegui confirmar a janela. É só apertar Enter."
    os.startfile("whatsapp:")
    if not _esperar_whatsapp():
        return "Não consegui abrir o WhatsApp, chefe. Ele está instalado?"
    time.sleep(0.8)
    _tecla(0x11, 0x4E)  # Ctrl+N: nova conversa, com a busca de contatos
    time.sleep(0.8)
    _colar(d["salvo_como"])
    time.sleep(1.5)  # a lista filtra enquanto digita
    _tecla(0x0D)  # abre o primeiro resultado
    time.sleep(1.0)
    _colar(d["texto"])
    if d.get("verificado"):
        time.sleep(0.3)
        _tecla(0x0D)
        return f"Mensagem enviada pro {d['quem']}, chefe."
    d["etapa"] = "conferir"
    return f"Deixei a mensagem digitada na conversa {d['salvo_como']}, sem enviar. Foi a conversa certa?"
