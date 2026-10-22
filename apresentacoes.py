"""Apresentações holográficas: o assunto vira um objeto 3D em peças + o roteiro que o Jarvis fala, peça por peça.

A tela (web/holograma.js, three.js) desenha as peças com cara de holograma; cada frase falada acende a(s) peça(s)
daquele trecho e, quando o roteiro pede, o objeto "explode" (as peças se separam pra mostrar por dentro).
Dois modelos feitos à mão (camadas da Terra e peças do computador); o resto o cérebro monta com formas simples.
"""
import json
import math
import re
import unicodedata

import cerebro


def _sa(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


PI = math.pi
# virar o corte da esfera (o quarto que falta) pra frente da câmera
CORTE_PRA_FRENTE = [0, 3 * PI / 4, 0]

TERRA = {
    "titulo": "As camadas da Terra",
    "zoom": 10.5,
    "intro": "A Terra tem quatro camadas principais: crosta, manto, núcleo externo e núcleo interno. Vou abrir ela pra você ver.",
    "partes": [
        {"nome": "Crosta", "forma": "esfera_cortada", "tam": [2.0], "cor": "#4fe3ff", "pos": [0, 0, 0], "rot": CORTE_PRA_FRENTE,
         "explode": [0, 1.5, 0], "ancora": [0, 0.88, 1.74]},
        {"nome": "Manto", "forma": "esfera_cortada", "tam": [1.9], "cor": "#ff7a2f", "pos": [0, 0, 0], "rot": CORTE_PRA_FRENTE,
         "explode": [0, 0.5, 0], "ancora": [0, 0.68, 1.34]},
        {"nome": "Núcleo externo", "forma": "esfera_cortada", "tam": [1.1], "cor": "#ffc23d", "pos": [0, 0, 0], "rot": CORTE_PRA_FRENTE,
         "explode": [0, -0.45, 0], "ancora": [0, 0.35, 0.72]},
        {"nome": "Núcleo interno", "forma": "esfera", "tam": [0.45], "cor": "#fff6b0", "pos": [0, 0, 0],
         "explode": [0, -1.2, 0], "ancora": [0, 0.1, 0.25]},
    ],
    "passos": [
        {"fala": "Por fora, a crosta: a casca fininha onde a gente vive. Tem de 5 a 70 quilômetros de espessura, menos de um por cento do planeta.",
         "destaque": ["Crosta"]},
        {"fala": "Embaixo dela, o manto: rocha quente e pastosa, quase 2.900 quilômetros de espessura. É o movimento dele que arrasta as placas tectônicas.",
         "destaque": ["Manto"]},
        {"fala": "Depois vem o núcleo externo, de ferro e níquel líquidos. Esse metal girando é o que cria o campo magnético da Terra.",
         "destaque": ["Núcleo externo"], "explodir": True},
        {"fala": "E bem no centro, o núcleo interno: uma bola sólida de ferro a uns 5.400 graus, quente como a superfície do Sol, sólida por causa da pressão.",
         "destaque": ["Núcleo interno"], "explodir": True},
        {"fala": "Juntando tudo: crosta, manto, núcleo externo e núcleo interno. Pode girar o modelo com o mouse.",
         "destaque": ["Crosta", "Manto", "Núcleo externo", "Núcleo interno"]},
    ],
}

COMPUTADOR = {
    "titulo": "As peças de um computador",
    "intro": "Vou desmontar um computador pra você: são sete peças principais dentro do gabinete.",
    "partes": [
        {"nome": "Gabinete", "forma": "caixa", "tam": [3.2, 3.6, 1.7], "cor": "#4fe3ff", "pos": [0, 0, 0], "explode": [0, 0, -0.4], "fantasma": True},
        {"nome": "Placa-mãe", "forma": "placa", "tam": [2.4, 2.9, 0.06], "cor": "#2ee88a", "pos": [0.1, 0.15, -0.72], "explode": [0, 0, -1.0]},
        {"nome": "Processador", "forma": "caixa", "tam": [0.45, 0.45, 0.08], "cor": "#ffd23d", "pos": [-0.25, 0.75, -0.62], "explode": [0, 0.5, 1.0]},
        {"nome": "Cooler", "forma": "cilindro", "tam": [0.36, 0.3], "cor": "#9ad8ff", "pos": [-0.25, 0.75, -0.38], "rot": [PI / 2, 0, 0], "explode": [0, 0.9, 1.9]},
        {"nome": "Memória RAM", "forma": "caixa", "tam": [0.28, 1.05, 0.26], "cor": "#c77dff", "pos": [0.45, 0.75, -0.55], "explode": [1.1, 0.8, 1.0]},
        {"nome": "Placa de vídeo", "forma": "caixa", "tam": [2.0, 0.26, 0.75], "cor": "#ff5d8f", "pos": [-0.1, -0.45, -0.3], "explode": [0, -0.3, 1.6]},
        {"nome": "SSD", "forma": "placa", "tam": [0.7, 0.22, 0.05], "cor": "#7cff6b", "pos": [0.65, -0.05, -0.66], "explode": [1.4, -0.2, 0.9]},
        {"nome": "Fonte", "forma": "caixa", "tam": [1.4, 0.8, 1.2], "cor": "#ff9b3d", "pos": [-0.75, -1.35, 0.05], "explode": [-1.0, -0.9, 0.9]},
    ],
    "passos": [
        {"fala": "A placa-mãe é a base de tudo: é nela que todas as outras peças se encaixam e conversam.", "destaque": ["Placa-mãe"], "explodir": True},
        {"fala": "O processador é o cérebro: faz as contas. Em cima dele vai o cooler, que tira o calor pra ele não fritar.",
         "destaque": ["Processador", "Cooler"], "explodir": True},
        {"fala": "A memória RAM guarda o que está aberto agora. É rápida, mas esquece tudo quando desliga.", "destaque": ["Memória RAM"], "explodir": True},
        {"fala": "O SSD é onde ficam seus arquivos e o Windows, guardados mesmo desligado.", "destaque": ["SSD"], "explodir": True},
        {"fala": "A placa de vídeo desenha a imagem na tela; pra jogo e 3D é ela que faz o trabalho pesado.", "destaque": ["Placa de vídeo"], "explodir": True},
        {"fala": "E a fonte transforma a energia da tomada na que as peças usam. Fechando o gabinete, tá montado.",
         "destaque": ["Fonte", "Gabinete"]},
    ],
}

MODELOS = [
    (re.compile(r"camadas?\s+(?:d[ae]|n[ae])\s+(?:terra|planeta)|(?:terra|planeta)\s+por\s+dentro|dentro\s+d[ae]\s+(?:terra|planeta)|"
                r"(?:interior|estrutura|nucleo)\s+d[ae]\s+(?:terra|planeta)"), TERRA),
    (re.compile(r"(?:pecas|partes|componentes|hardware)\s+d[eo]\s+(?:um\s+)?(?:computador|pc)|(?:computador|pc)\s+por\s+dentro|"
                r"dentro\s+d[eo]\s+(?:um\s+)?(?:computador|pc)|montar\s+um\s+(?:computador|pc)"), COMPUTADOR),
]

FORMAS = {"esfera", "esfera_cortada", "caixa", "placa", "cilindro", "cone", "toro"}
CORES = ["#4fe3ff", "#ff7a2f", "#ffd23d", "#2ee88a", "#c77dff", "#ff5d8f", "#7cff6b", "#9ad8ff", "#ff9b3d", "#fff6b0"]


def _num(v, padrao, minimo, maximo):
    try:
        return max(minimo, min(maximo, float(v)))
    except (TypeError, ValueError):
        return padrao


def _vet(v, padrao=(0, 0, 0), lim=3.5):
    v = v if isinstance(v, (list, tuple)) else []
    return [_num(v[i] if i < len(v) else padrao[i], padrao[i], -lim, lim) for i in range(3)]


def validar(cena, assunto):
    partes = []
    for i, p in enumerate((cena.get("partes") or [])[:10]):
        if not isinstance(p, dict) or not str(p.get("nome", "")).strip():
            continue
        forma = p.get("forma") if p.get("forma") in FORMAS else "caixa"
        cor = p.get("cor") if re.fullmatch(r"#[0-9a-fA-F]{6}", str(p.get("cor", ""))) else CORES[i % len(CORES)]
        tam = [_num(x, 0.8, 0.04, 3.5) for x in (p.get("tam") or [0.8, 0.8, 0.8])[:3]] or [0.8]
        pos = _vet(p.get("pos"))
        explode = _vet(p.get("explode"), tuple(x * 0.9 for x in pos) if any(pos) else (0, 0.8, 0.6))
        partes.append({"nome": str(p["nome"]).strip()[:40], "forma": forma, "tam": tam, "cor": cor, "pos": pos,
                       "rot": _vet(p.get("rot"), lim=7), "explode": explode, "texto": str(p.get("texto", ""))[:200]})
    if not partes:
        raise ValueError("o modelo não montou peça nenhuma")
    nomes = {p["nome"] for p in partes}
    passos = []
    for s in (cena.get("passos") or [])[:8]:
        if isinstance(s, dict) and str(s.get("fala", "")).strip():
            passos.append({"fala": str(s["fala"]).strip()[:320], "destaque": [n for n in s.get("destaque") or [] if n in nomes],
                           "explodir": bool(s.get("explodir"))})
    if not passos:
        passos = [{"fala": f"{p['nome']}: {p['texto']}" if p["texto"] else p["nome"], "destaque": [p["nome"]], "explodir": True}
                  for p in partes]
    return {"titulo": str(cena.get("titulo") or assunto)[:80], "intro": str(cena.get("intro") or "")[:300],
            "partes": partes, "passos": passos}


PEDIDO = """Você monta apresentações holográficas 3D do J.A.R.V.I.S. (fala com o Rafael, chama ele de chefe, tom leve).
Assunto: "{assunto}".
Monte o objeto com 4 a 9 peças de formas simples e um roteiro de 4 a 7 passos. Responda SÓ este JSON:
{{"titulo": "...", "intro": "1 frase apresentando",
 "partes": [{{"nome": "nome curto em português", "forma": "esfera|esfera_cortada|caixa|placa|cilindro|cone|toro",
   "tam": [..], "pos": [x,y,z], "rot": [rx,ry,rz], "cor": "#rrggbb", "explode": [x,y,z], "texto": "1 frase sobre a peça"}}],
 "passos": [{{"fala": "1 ou 2 frases curtas, faladas", "destaque": ["nome de peça"], "explodir": true|false}}]}}
Regras: tam de esfera = [raio]; caixa/placa = [largura, altura, profundidade]; cilindro/cone = [raio, altura]; toro = [raio, espessura].
Coordenadas entre -2.5 e 2.5, centro em 0,0,0, Y pra cima. Encaixe as peças como no objeto real (uma dentro/em cima da outra).
"explode" = pra onde a peça se afasta quando o objeto se abre (deslocamento, ~1 a 1.8). Cores vivas e diferentes por peça.
Pra coisas com camadas (planeta, célula, olho, átomo) use esfera_cortada uma dentro da outra. Fatos corretos, nada inventado."""


async def montar(assunto):
    t = _sa(assunto)
    for rx, modelo in MODELOS:
        if rx.search(t):
            return json.loads(json.dumps(modelo))
    bruto = await cerebro.completar([{"role": "user", "content": PEDIDO.format(assunto=assunto)}],
                                    json_mode=True, temperatura=0.4, max_tokens=2000)
    return validar(json.loads(bruto[bruto.index("{"):bruto.rindex("}") + 1]), assunto)
