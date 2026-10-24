"""Gerar imagem por voz, de graça: "cria uma imagem de um dragão", "desenha um gato astronauta", "faz uma foto de...".

Pedido dele (23/10/2026): pegar modelos de IA grátis e gerar imagem. Começo pelo Pollinations (grátis, SEM chave, sem
limite prático): um GET numa URL já devolve o JPEG. Estrutura preparada pra rodar outros provedores em sequência quando
um estourar o limite (igual o cerebro.py faz com texto). O Jarvis mostra a imagem no cartão (o HUD carrega a URL) e
baixa uma cópia em conteudo/imagens/ pra ele guardar. NÃO colide com o marketing do Porthon: aqui é "imagem/foto/
ilustração/desenho/figura...", lá é "post/arte/legenda".
"""
import random
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import quote

DEMORA = True
RAIZ = Path(__file__).parent
PASTA = RAIZ / "conteudo" / "imagens"

# substantivos que deixam claro que é IMAGEM (de propósito sem "arte", que é do marketing do Porthon)
NOUN = r"(?:imagem|imagens|foto|fotografia|ilustra[cç][aã]o|desenho|figura|cena|wallpaper|papel\s+de\s+parede|pintura|logotipo|logo)"
CRIA = re.compile(r"\b(?:cria|crie|criar|gera|gere|gerar|faz|fa[cç]a|fazer|monta|montar|quero|me\s+faz|me\s+gera|me\s+cria)\b"
                  r".{0,20}?\b" + NOUN + r"\b", re.I)
DESENHA = re.compile(r"\b(?:desenha|desenhe|desenhar|ilustra|ilustre|pinta|pinte|imagina)\b", re.I)
# de onde tirar o que desenhar
ASSUNTO = re.compile(r"\b(?:de|do|da|das|dos|com|sobre|que\s+mostra|mostrando|retratando)\s+(?P<q>.+)$", re.I)
APOS_VERBO = re.compile(r"\b(?:desenha|desenhe|desenhar|ilustra|ilustre|pinta|pinte|imagina)\s+"
                        r"(?:pra\s+mim\s+)?(?:uma?\s+|o\s+|a\s+)?(?P<q>.+)$", re.I)


def _sa(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def _slug(t):
    return (re.sub(r"[^a-z0-9]+", "-", _sa(t)).strip("-") or "imagem")[:40]


def _assunto(texto):
    m = ASSUNTO.search(texto)
    if m:
        return m.group("q").strip(" .!?")
    m = APOS_VERBO.search(texto)
    if m:
        return m.group("q").strip(" .!?")
    return ""


def entender(texto):
    t = texto or ""
    if CRIA.search(t) or DESENHA.search(t):
        return {"prompt": _assunto(t)}
    return None


# ---------------------------------------------------------------- provedores grátis (em ordem; cai pro próximo se falhar)
def _pollinations(prompt, seed):
    p = quote(prompt)[:500]
    return (f"https://image.pollinations.ai/prompt/{p}?width=1024&height=1024&nologo=true&seed={seed}&model=flux")


PROVEDORES = [("Pollinations", _pollinations)]  # dá pra somar Gemini/Cloudflare aqui depois, com rotação por limite


def _melhorar_prompt(prompt):
    """O Flux entende muito melhor inglês detalhado do que "um gato no sofá": a IA rápida (Groq) reescreve o pedido
    como diretor de arte (assunto, estilo, luz, enquadramento). Sem IA, vai o pedido como veio."""
    import asyncio
    import cerebro
    try:
        texto = asyncio.run(cerebro.completar([{"role": "user", "content": (
            "Rewrite this image request as ONE detailed English prompt for the FLUX image model (max 60 words): "
            "subject, style (photo-realistic unless the request says otherwise), lighting, composition, quality "
            "keywords. Keep every detail the user asked for; any text that must appear in the image stays in its "
            "original language, in quotes. Reply with the prompt only. Request: " + prompt)}],
            temperatura=0.4, max_tokens=150))
        texto = texto.strip().strip('"')
        return texto if 10 < len(texto) < 700 else prompt
    except Exception:
        return prompt


def _baixar(url):
    try:
        import httpx
        r = httpx.get(url, timeout=90, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
            return r.content
    except Exception:
        pass
    return None


def executar(p):
    prompt = (p.get("prompt") or "").strip()
    if not prompt:
        return "Imagem de quê, chefe? Me diz o que você quer que eu desenhe.", []
    seed = random.randint(1, 10_000_000)
    url, provedor, dados = None, None, None
    descricao = _melhorar_prompt(prompt)
    for nome, fn in PROVEDORES:  # tenta cada provedor até um devolver imagem (rotação por limite)
        u = fn(descricao, seed)
        d = _baixar(u)
        if d:
            url, provedor, dados = u, nome, d
            break
    if not url:
        return "Não consegui gerar a imagem agora, chefe. O serviço deve estar fora do ar — tenta de novo?", []
    # guarda uma cópia pra ele
    arquivo = None
    try:
        PASTA.mkdir(parents=True, exist_ok=True)
        arquivo = PASTA / f"{date.today().isoformat()}-{_slug(prompt)}.jpg"
        arquivo.write_bytes(dados)
    except Exception:
        arquivo = None
    fala = f"Prontinho, chefe. Gerei a imagem de {prompt}." + (" Já guardei uma cópia pra você." if arquivo else "")
    cartao = {"titulo": "Imagem gerada", "destaque": prompt, "imagens": [url],
              "creditos": [f"Gerada por IA ({provedor})"],
              "linhas": [f"Salva em {arquivo.name}"] if arquivo else []}
    return fala, [cartao]
