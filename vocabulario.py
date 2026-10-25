"""Conserta o que o reconhecimento de voz entende errado e aprende com as correções do Rafael.

Três níveis:
1. FIXOS: erros conhecidos dos termos dele ("seven code" → SevenCode); corrige sempre, sem perguntar.
2. APRENDIDOS: palavras que ele já confirmou ("lídia" → leads); corrige sempre, sem perguntar.
3. PARECIDOS: palavra que soa como um termo dele mas não é certeza; o Jarvis pergunta
   "você quis dizer…?". O "sim" vira aprendido; o "não" entra na lista de não corrigir.
"""
import difflib
import json
import re
import unicodedata
from pathlib import Path

ARQUIVO = Path(__file__).parent / "vocabulario-aprendido.json"

# palavras que existem de verdade (nomes de apps do PC, termos em inglês comuns): nunca são "erro"
PALAVRAS_CONHECIDAS = {"code", "codes", "cloud", "lead", "leads", "clock", "photos", "notes", "studio", "visual",
                       # português comum que soa parecido com os termos dele
                       "porto", "porta", "portas", "portão", "portao", "porteiro", "porton", "lidas", "lindas", "lido",
                       "claudia", "claudio", "jarra", "radio", "rádio", "comida", "comitê", "comite", "lendas", "lados",
                       # 21/10: "depois" virava "deploy" e o Jarvis perguntava "Você quis dizer…?" no meio da frase
                       "depois", "deposito", "depoimento", "depor", "comigo", "comer", "cometa", "comete", "cometi",
                       "lindo", "linda", "lista", "listas", "leite", "claro", "clara", "radar", "radial", "porte",
                       "portal", "postar", "poste", "comprar", "compras", "cores", "carro", "carros", "cloro", "claudio"}

FIXOS = [
    (r"\b(?:ryan|rian|raian|rayan|riam|rhyan|ryhan|rihan|rihãn|riã|rião)\b", "Rihan"),  # sócio/equipe: no WhatsApp é "Rihan"
    (r"\b(?:extens[aã]o|exten[cç][aã]o|estens[aã]o|estenç[aã]o|extenss[aã]o)\b", "extensão"),
    (r"\b(?:p[oó]\s*-?\s*pups?|p[oó]\s*-?\s*papis|popapis|pop\s+papis|p[oó]pis|pop\s+ups?|pop\s*-\s*ups?|popups?)\b", "popups"),
    (r"\b(?:seven|sete|7)\s*-?\s*(?:code|codes|cold|coat|c[oó]di?|cood)\b", "SevenCode"),
    (r"\b(?:l[ií]d[sz]|l[ií]des|lidis|lead's|leeds|lides|lidz)\b", "leads"),
    (r"\bpagode\s+restaur(?:ar|ação|acao|ante|ou)\b", "Pagode Restaura"),  # o grupo de pagode gospel que ele curte
    # "Pórton" (como ele fala): o reconhecimento escreve pórton/pôrton/porton/portom/porthon/port on… — tudo é o sistema
    (r"\b(?:p[oóô]rt[oóô]n[ns]?|p[oóô]rt[oóô]m|p[oóô]rthom|p[oóô]rth?on|port\s+h?on|portho|p[oó]rton\b)", "Porthon"),
    # "porto" sozinho só vira Porthon quando a frase é do sistema (Porto Alegre, porto seguro… ficam como estão)
    (r"\b(abre|abrir|no|do|pro|o)\s+porto\b(?!\s+(?:alegre|seguro|velho|rico|belo|de|do|da|das|dos)\b)"
     r"(?=.*\b(?:encomend|morador|ocorr|commit|deploy|condom|portaria|pacote|sistema|reserva|tarefa|s[ií]ndic|porteir|atualiza)"
     r"|\s*[.!?]?$)", r"\1 Porthon"),
    # o Chrome ouve "Porthon" como "portão"; o Jarvis não mexe em portão nenhum, então é o sistema —
    # menos quando é portão de verdade ("portão da garagem", "portão eletrônico")
    (r"\bport[aã]o\b(?!\s+(?:d[aeo]s?|eletr[oô]nico|autom[aá]tico|social|principal|da frente|lateral)\b)", "Porthon"),
    (r"\b(pro|para o|pra o|ao)\s+(?:cloud|cl[oó]vis|clode|cl[aá]udio|claudi|clóude)\b", r"\1 Claude"),
    (r"\b(?:jarves|jervis|j[aá]rvis|jarvi|jarvys|jarbis)\b", "Jarvis"),
    (r"\b(?:what'?s ?app|uats ?app|uatizap|zapzap)\b", "WhatsApp"),
    (r"\b(?:insta ?gram|instagran)\b", "Instagram"),
    (r"\b(?:vs|v s|vê esse|ve esse)\s*code\b", "VS Code"),
    (r"\b(?:deploi|diploi|deployar)\b", "deploy"),
    (r"\b(?:comitar|comit|commitá)\b", "commit"),
    # 22/10: peças do PC do jeito que o Chrome escreve o que ele fala
    (r"\b(?:r[aá]izen|raisen|raizem|rizen|risen|r[aá]isen)\b", "Ryzen"),
    (r"\b(?:tr[eé]ds|tr[eé]dis|tredes|treads)\b", "threads"),
    (r"\b(?:gi\s*force|dji\s*force|ji\s*force|geforce)\b", "GeForce"),
    (r"\b(?:radeom|radion|rad[eê]on)\b", "Radeon"),
    (r"\b(?:king\s*ston|kingstom)\b", "Kingston"),
    (r"\b(?:envidia|en\s*vidia|nvídia)\b", "NVIDIA"),
]

# termos dele que o Chrome em português costuma estragar (só palavras de 5+ letras: as curtas
# batem com palavras comuns do português e o Jarvis ficaria perguntando à toa)
TERMOS = ["leads", "Porthon", "SevenCode", "Claude", "Jarvis", "WhatsApp", "Instagram", "Supabase", "Vercel",
          "deploy", "commit", "landing", "dashboard", "feedback", "follow-up", "Notion", "CapCut"]


def _sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def som(palavra):
    """Chave aproximada do som (inglês falado por brasileiro): leads → lids, claude → clod."""
    t = _sem_acento(palavra)
    for de, para in [("ea", "i"), ("ee", "i"), ("au", "o"), ("ou", "o"), ("th", "t"), ("ph", "f"), ("w", "u"),
                     ("y", "i"), ("k", "c"), ("qu", "c"), ("z", "s"), ("ç", "s"), ("h", ""), ("-", "")]:
        t = t.replace(de, para)
    t = re.sub(r"(.)\1+", r"\1", t)  # letra dobrada soa como uma
    return re.sub(r"e$", "", t)


def _carregar():
    if ARQUIVO.exists():
        try:
            return json.loads(ARQUIVO.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return {"corrigir": {}, "nao_corrigir": []}


DADOS = _carregar()


def _salvar():
    ARQUIVO.write_text(json.dumps(DADOS, ensure_ascii=False, indent=1), encoding="utf-8")


def corrigir(texto):
    """Aplica as correções certas (fixas e aprendidas). Devolve o texto consertado."""
    for regra, troca in FIXOS:
        texto = re.sub(regra, troca, texto, flags=re.I)
    for errado, certo in DADOS["corrigir"].items():
        texto = re.sub(rf"\b{_sem_ligar_pra_acento(errado)}\b", certo, texto, flags=re.I)
    return texto


VARIANTES = {"a": "aáàâã", "e": "eéê", "i": "ií", "o": "oóôõ", "u": "uúü", "c": "cç"}


def _sem_ligar_pra_acento(palavra):
    """"lidios" vira um padrão que também acha "lídios" (o aprendido é gravado sem acento)."""
    return "".join(f"[{VARIANTES[c]}]" if c in VARIANTES else re.escape(c) for c in palavra)


def suspeitas(texto, com_nota=False):
    """Palavras que soam como um termo dele mas não estão escritas assim: [(palavra, termo)] ou, com_nota,
    [(palavra, termo, nota)] — o server troca sozinho as de nota alta (sem perguntar)."""
    achadas = []
    for palavra in re.findall(r"[\wÀ-ú'-]{4,}", texto):
        chave = _sem_acento(palavra)
        if (chave in DADOS["nao_corrigir"] or chave in PALAVRAS_CONHECIDAS
                or any(chave == _sem_acento(t) for t in TERMOS)):
            continue
        melhor, nota = None, 0.0
        for termo in TERMOS:
            r = difflib.SequenceMatcher(None, som(palavra), som(termo)).ratio()
            if r > nota:
                melhor, nota = termo, r
        if nota >= 0.8:
            achadas.append((palavra, melhor, nota) if com_nota else (palavra, melhor))
    return achadas


def com_sugestao(texto):
    """Texto com as suspeitas trocadas, ou None se não houver o que perguntar."""
    trocas = suspeitas(texto)
    if not trocas:
        return None, []
    novo = texto
    for palavra, termo in trocas:
        novo = re.sub(rf"\b{re.escape(palavra)}\b", termo, novo)
    return novo, trocas


def confirmar(trocas, certo):
    """O Rafael respondeu à pergunta "você quis dizer…?": aprende para a próxima vez."""
    for palavra, termo in trocas:
        chave = _sem_acento(palavra)
        if certo:
            DADOS["corrigir"][chave] = termo
        elif chave not in DADOS["nao_corrigir"]:
            DADOS["nao_corrigir"].append(chave)
    _salvar()


ENSINO = re.compile(r"^(?:jarvis[ ,]*)?quando eu (?:falar|disser|digo|falo)\s+[\"']?(.+?)[\"']?,?\s+"
                    r"(?:é|e|quero dizer|significa|entenda)\s+[\"']?(.+?)[\"']?[.!]*$", re.I)


def ensino(texto):
    """"Quando eu falar lídia, é leads": aprende direto. Devolve a fala de resposta, ou None."""
    m = ENSINO.match(texto.strip())
    if not m:
        return None
    errado, certo = _sem_acento(m.group(1).strip()), m.group(2).strip()
    DADOS["corrigir"][errado] = certo
    if errado in DADOS["nao_corrigir"]:
        DADOS["nao_corrigir"].remove(errado)
    _salvar()
    return f"Anotado, chefe. Quando eu ouvir {m.group(1).strip()}, vou entender {certo}."


# Enfeites de fala (gaúcha ou não) que não mudam o pedido: saem do começo e do fim antes de entender.
# "bah, abre o zap aí, tchê" → "abre o zap". No meio da frase ficam (lá podem ter sentido).
ENFEITES_NO_COMECO = re.compile(
    r"^(?:"
    # sempre enfeite
    r"(?:bah|b[aá]|tch[eê]|ô|oi|ei|opa|jarvis|por favor|faz um favor|faz o favor|me faz um favor|"
    r"d[aá] pra|tem como|ser[aá] que (?:tu|voc[eê]) (?:pode|consegue))[\s,!.]+"
    # só é enfeite com vírgula depois ("o porteiro chegou" fica como está; "olha, abre o zap" perde o "olha")
    r"|(?:o|olha|escuta|seguinte|ent[aã]o|tipo|cara|meu|v[eé]i|guri)\s*[,!]\s*"
    r")+", re.I)
ENFEITES_NO_FIM = re.compile(
    r"(?:[\s,]+(?:a[ií]|pra mim|para mim|por favor|tch[eê]|bah|meu|v[eé]i|guri|rapidinho|ligeiro|"
    r"por gentileza|valeu|obrigad[oa]|faz favor|fazendo favor))+[\s.!?]*$", re.I)


# "jarvis" no fim é ele chamando ("abre o zap, jarvis"), menos quando é o nome de algo ("a pasta do jarvis")
JARVIS_NO_FIM = re.compile(r"(?<!\bdo)(?<!\bda)(?<!\bno)(?<!\bna)(?<!\bo)(?<!\bpro)[\s,]+jarvis[\s.!?]*$", re.I)


def limpar(texto):
    texto = ENFEITES_NO_COMECO.sub("", texto.strip())
    for _ in range(2):  # "abre o zap aí, jarvis, tchê"
        texto = JARVIS_NO_FIM.sub("", ENFEITES_NO_FIM.sub("", texto))
    return texto.strip(" ,.!") or texto


# Glossário gaúcho para o cérebro (entra no prompt): ele entende o sentido, não só as palavras.
GAUCHES = ("bah/tchê = interjeições; tri = muito (tri legal = muito legal); capaz = de jeito nenhum (às vezes 'imagina'); "
           "bergamota = tangerina; cacetinho = pão francês; sinaleira = semáforo; pila = real (dinheiro); guri/guria = menino/menina; "
           "barbaridade = nossa!; afudê = ótimo; loco de = muito; a la pucha = nossa!; tu = você (o Rafael fala 'tu vai', 'tu pode'); "
           "lagartear = ficar ao sol; bagual = forte, bom; chinelagem = coisa malfeita; borracho = bêbado; "
           "piá = guri; trovar = conversar; pechar = esbarrar; chimarrão/mate = bebida; churras = churrasco")


def melhor_alternativa(alternativas, entende):
    """O Chrome devolve até 5 versões do que ouviu; fica com a primeira que vira comando conhecido."""
    corrigidas = [limpar(corrigir(a)) for a in alternativas if a and a.strip()]
    return next((a for a in corrigidas if entende(a)), corrigidas[0] if corrigidas else "")
