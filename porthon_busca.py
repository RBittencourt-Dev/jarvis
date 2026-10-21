"""Pesquisa DENTRO do Porthon: morador pelo nome, carro pela placa ou pelo modelo. SÓ LEITURA.

Só entra quando ele fala do Porthon ("no porthon", "morador", "placa ABC1D23"): "pesquisa BMW X1"
sozinho é internet. Usa o login dele (login-porthon.json), então vale o RLS: ele só vê o que já vê
no sistema. O resultado aparece na tela e é falado; nada disso é gravado em disco nem aprendido.
Telefone não sai daqui (nem pedido ao banco).
"""
import re
import unicodedata

import pesquisa
import porthon_dados

PORTHON = re.compile(r"\b(?:no|do|pelo|dentro do|l[aá] no)?\s*p[oó]rth?on\b|\bno sistema\b|\bno condom[ií]nio\b", re.I)
PLACA = re.compile(r"\bplaca\s+(?:d[oa]\s+)?(?P<p>[a-z]{3}[\s-]*\d[\s-]*[a-z0-9][\s-]*\d[\s-]*\d)\b", re.I)
VERBO = r"(?:pesquis[ae]r?|procur[ae]r?|busc[ae]r?|acha|ach[ae]r|v[eê]|olha|consulta|me (?:fala|mostra|diz))"
MORADOR = re.compile(rf"(?:{VERBO}|tem|existe|h[aá])\s+(?:(?:o|a|um|uma|algum|alguma|tal|tem|existe|do|da|pelo|pela)\s+)*morador(?:a|es|as)?\s+"
                     r"(?:(?:chamad[oa]|de nome|com (?:o )?nome(?: de)?|que se chama)\s+)?(?P<nome>.+)$", re.I)
CARRO = re.compile(rf"(?:{VERBO}|tem|existe|h[aá]|quem tem)\s+(?:(?:o|a|um|uma|algum|alguma|tal|tem|existe|do|da|pelo|pela)\s+)*"
                   r"(?:carros?|ve[ií]culos?|motos?|autom[oó]vel)\s+(?:(?:modelo|da marca|marca|que [eé] (?:uma?|o|a))\s+)?(?P<modelo>.+)$", re.I)
MARCAS = ("bmw", "honda", "toyota", "fiat", "chevrolet", "volkswagen", "vw", "ford", "hyundai", "renault", "nissan", "jeep",
          "peugeot", "citroen", "citroën", "kia", "mitsubishi", "audi", "mercedes", "volvo", "byd", "chery", "caoa", "yamaha")
SOBRA = re.compile(r"\b(?:no|do|pelo|dentro do|l[aá] no)\s+(?:p[oó]rth?on|sistema|condom[ií]nio)\b|\bp[oó]rth?on\b|[?.!,]+|"
                   r"\b(?:a[ií]|pra mim|por favor|jarvis|cadastrad[oa]s?|registrad[oa]s?)\b", re.I)
VAZIO = {"tal", "morador", "moradora", "carro", "placa", "algum", "alguma", "um", "uma", "o", "a", "fulano", "ciclano"}


def _sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def _limpar(s):
    s = re.sub(r"\s{2,}", " ", SOBRA.sub(" ", s)).strip()
    return re.sub(r"^(?:o|a|os|as|um|uma|tal)\s+", "", s, flags=re.I).strip()


def entender(texto):
    """("placa", "ABC1D23") | ("morador", "joão") | ("carro", "bmw x1") | ("vago", tipo) | None."""
    t = texto.strip()
    if pesquisa.ONDE_SITE.search(t) or pesquisa.ONDE_NAV.search(t):
        return None  # "pesquisa o site do porthon no google" é internet
    m = PLACA.search(t)
    if m:  # placa no formato de placa já é coisa do Porthon, mesmo sem dizer "no porthon"
        return "placa", re.sub(r"[\s-]", "", m.group("p")).upper()
    falou_porthon = bool(PORTHON.search(t))
    if re.match(r"^(?:jarvis[ ,]*)?(?:quant[oa]s|como|o que|por ?que|pra que)\b", t, re.I):
        return None  # pergunta de contagem ou de "como funciona": não é procurar alguém
    m = MORADOR.search(t)
    if m:
        nome = _limpar(m.group("nome"))
        return ("morador", nome) if nome and _sem_acento(nome) not in VAZIO else ("vago", "morador")
    m = CARRO.search(t)
    if m and falou_porthon:
        modelo = _limpar(m.group("modelo"))
        return ("carro", modelo) if modelo and _sem_acento(modelo) not in VAZIO else ("vago", "carro")
    if not falou_porthon:
        return None
    m = re.match(rf"^(?:jarvis[ ,]*)?{VERBO}\s+(?P<o_que>.+)$", t, re.I)
    if not m:
        return None
    o_que = _limpar(m.group("o_que"))
    if not o_que or re.search(r"\b(?:encomenda|ocorr|tarefa|reserva|pend|commit|falta|andamento)", o_que, re.I):
        return None  # contagens e andamento já têm caminho próprio
    if re.match(r"^placa\b", o_que, re.I):
        return "vago", "placa"
    if any(_sem_acento(o_que).startswith(marca) for marca in MARCAS):
        return "carro", o_que
    return "morador", o_que  # "pesquisa o João Silva no Porthon"


def rota(pedido):
    return f"porthon busca {pedido[0]} {pedido[1]}"


def _onde(condominios, cid):
    return condominios.get(cid, "")


def _casa(busca, alvo):
    """Todas as palavras da busca aparecem no alvo, sem ligar pra acento ou maiúscula."""
    alvo = _sem_acento(alvo or "")
    return all(p in alvo for p in _sem_acento(busca).split())


def _apto(p):
    if not p:
        return ""
    partes = [f"bloco {p['bloco']}" if p.get("bloco") else "", f"apto {p['apartamento']}" if p.get("apartamento") else ""]
    return " ".join(x for x in partes if x)


def responder(pedido):
    tipo, valor = pedido
    if tipo == "vago":
        perguntas = {"morador": "Qual o nome do morador, chefe?", "carro": "Qual o modelo do carro, chefe?",
                     "placa": "Qual a placa, chefe? Pode soletrar."}
        return perguntas[valor], []
    if not porthon_dados.configurado():
        return ("Pra pesquisar no Pórton eu preciso do seu login, chefe. Preenche o login-porthon.json na minha pasta "
                "e eu já consigo."), []
    condominios = {c["id"]: c["nome"] for c in porthon_dados._ler("condominios", "select=id,nome")}
    if tipo == "morador":
        pessoas = porthon_dados._ler("profiles", "select=name,bloco,apartamento,condominio_id&role=in.(morador,sindico,admin)")
        achados = [p for p in pessoas if _casa(valor, p.get("name"))][:8]
        if not achados:
            return f"Não achei nenhum morador com {valor} no Pórton, chefe.", []
        linhas = [f"{p['name']} · {_apto(p) or 'sem apto'} · {_onde(condominios, p['condominio_id'])}" for p in achados]
        if len(achados) == 1:
            p = achados[0]
            fala = f"Achei: {p['name']}, {_apto(p) or 'sem apartamento cadastrado'}, no {_onde(condominios, p['condominio_id'])}."
        else:
            fala = f"Achei {len(achados)} moradores com {valor}. Estão na tela, chefe."
        return fala, [{"titulo": "Porthon · moradores", "destaque": valor, "linhas": linhas}]
    veiculos = porthon_dados._ler("veiculos", "select=placa,marca,modelo,cor,condominio_id,"
                                              "morador:profiles!morador_id(name,bloco,apartamento)")
    if tipo == "placa":
        achados = [v for v in veiculos if re.sub(r"[\s-]", "", (v.get("placa") or "")).upper() == valor]
    else:
        achados = [v for v in veiculos if _casa(valor, f"{v.get('marca') or ''} {v.get('modelo') or ''}")]
    achados = achados[:8]
    if not achados:
        o_que = f"a placa {valor}" if tipo == "placa" else f"nenhum {valor}"
        return f"Não achei {o_que} no Pórton, chefe.", []

    def dono(v):
        m = v.get("morador") or {}
        m = m[0] if isinstance(m, list) and m else m
        return m if isinstance(m, dict) else {}

    linhas = []
    for v in achados:
        carro = " ".join(x for x in (v.get("marca"), v.get("modelo"), v.get("cor")) if x) or "carro"
        d = dono(v)
        linhas.append(f"{v.get('placa') or 'sem placa'} · {carro} · {d.get('name') or 'sem dono'} {_apto(d)}".strip())
    if len(achados) == 1:
        v, d = achados[0], dono(achados[0])
        carro = " ".join(x for x in (v.get("modelo") or v.get("marca"), v.get("cor")) if x) or "um carro"
        fala = (f"A placa {v.get('placa')} é {carro}" if tipo == "placa" else f"Achei um {carro}, placa {v.get('placa')}")
        fala += (f", do {d['name']}, {_apto(d)}." if d.get("name") else ", sem morador ligado.")
    else:
        fala = f"Achei {len(achados)} {valor} no Pórton. Estão na tela, chefe."
    return fala, [{"titulo": "Porthon · veículos", "destaque": valor, "linhas": linhas}]
