"""Scanner 3D e biblioteca de hologramas.

Pedido dele (24/10): tirar foto de um objeto e o Jarvis virar aquilo num modelo 3D pra guardar e mostrar no holograma,
de graça. Este PC não aguenta gerar 3D (AMD integrada, 512 MB), então quem gera é a IA grátis do Hugging Face:
  1º TRELLIS (trellis-community/TRELLIS): foto → modelo COM cor, ~45 s, ~1 MB.
  2º Hunyuan3D-2 (tencent/Hunyuan3D-2), reserva: só a forma (sem cor), vem pesado → aqui enxuga pra ~60 mil faces.
Sem conta funciona (cota pequena por dia); com um token grátis do Hugging Face a cota sobe.
Várias fotos do mesmo objeto não dá: a API desses Spaces não deixa ligar o modo multi-imagem.

A biblioteca fica em dados/hologramas/ (fora do git: é dele). "Prontos" são os hologramas que o Jarvis já sabe montar
(PC ao vivo, Terra, coração…); "meus" são os escaneados.
"""
import json
import re
import shutil
import tempfile
import threading
import time
import unicodedata
import uuid
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).parent
PASTA = RAIZ / "dados" / "hologramas"
INDICE = PASTA / "biblioteca.json"
TOKEN = RAIZ / "huggingface.json"
MAX_FACES = 60000
_trava = threading.Lock()
TRABALHOS = {}  # id do trabalho → {"estado": "gerando|pronto|erro", "etapa", "erro", "item"}
ao_terminar = None  # o server pendura aqui o aviso falado ("holograma da caneca pronto")

PRONTOS = [
    {"id": "pc", "nome": "Este PC (ao vivo)", "tipo": "hardware", "alvo": "tudo"},
    {"id": "ram", "nome": "Memória RAM", "tipo": "hardware", "alvo": "ram"},
    {"id": "cpu", "nome": "Processador", "tipo": "hardware", "alvo": "cpu"},
    {"id": "gpu", "nome": "Placa de vídeo", "tipo": "hardware", "alvo": "gpu"},
    {"id": "disco", "nome": "Armazenamento", "tipo": "hardware", "alvo": "disco"},
    {"id": "iphone", "nome": "iPhone 15", "tipo": "celular"},
    {"id": "terra", "nome": "Camadas da Terra", "tipo": "apresentacao", "alvo": "camadas da terra"},
    {"id": "computador", "nome": "Peças de um computador", "tipo": "apresentacao", "alvo": "peças do computador"},
    {"id": "coracao", "nome": "Coração", "tipo": "apresentacao", "alvo": "coração"},
    {"id": "cerebro", "nome": "Cérebro humano", "tipo": "apresentacao", "alvo": "cérebro humano"},
    {"id": "cranio", "nome": "Crânio", "tipo": "apresentacao", "alvo": "crânio"},
    {"id": "esqueleto", "nome": "Esqueleto", "tipo": "apresentacao", "alvo": "esqueleto"},
    {"id": "musculos", "nome": "Músculos", "tipo": "apresentacao", "alvo": "músculos"},
    {"id": "nervoso", "nome": "Sistema nervoso", "tipo": "apresentacao", "alvo": "sistema nervoso"},
]


def _sa(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn").strip()


def _ler():
    try:
        return json.loads(INDICE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _gravar(itens):
    PASTA.mkdir(parents=True, exist_ok=True)
    INDICE.write_text(json.dumps(itens, ensure_ascii=False, indent=1), encoding="utf-8")


def _token():
    try:
        return json.loads(TOKEN.read_text(encoding="utf-8")).get("token") or None
    except Exception:
        return None


def guardar_token(token):
    token = (token or "").strip()
    if token and not re.fullmatch(r"hf_[A-Za-z0-9]{20,}", token):
        raise ValueError("token do Hugging Face começa com hf_")
    if token:
        TOKEN.write_text(json.dumps({"token": token}), encoding="utf-8")
    else:
        TOKEN.unlink(missing_ok=True)


def listar():
    with _trava:
        meus = _ler()
    ativos = [{"trabalho": k, **{c: v for c, v in t.items() if c != "item"}} for k, t in TRABALHOS.items() if t["estado"] == "gerando"]
    return {"meus": meus, "prontos": PRONTOS, "gerando": ativos, "tem_token": bool(_token())}


def achar(id_):
    with _trava:
        return next((i for i in _ler() if i["id"] == id_), None)


def cena(item):
    """O que o holograma.js recebe: um .glb com o estilo escolhido (cores reais ou azul holográfico)."""
    return {"titulo": item["nome"], "subtitulo": "BIBLIOTECA · ESCANEADO", "modelo": f"/api/hologramas/arquivo/{item['id']}.glb",
            "estilo": item.get("estilo", "real"), "intro": "", "zoom": 9}


def editar(id_, nome=None, estilo=None):
    with _trava:
        itens = _ler()
        item = next((i for i in itens if i["id"] == id_), None)
        if not item:
            raise KeyError(id_)
        if nome and nome.strip():
            item["nome"] = nome.strip()[:60]
        if estilo in ("real", "raiox"):
            item["estilo"] = estilo
        _gravar(itens)
        return item


def apagar(id_):
    with _trava:
        itens = _ler()
        _gravar([i for i in itens if i["id"] != id_])
    for ext in (".glb", ".png"):
        (PASTA / f"{id_}{ext}").unlink(missing_ok=True)


# ------------------------------------------------------------------ voz: "mostra a caneca", "abre o holograma do tênis"
VOZ = re.compile(r"^(?:jarvis[ ,]*)?(?:me\s+)?(?:mostra|mostrar|abre|abrir|projeta|projetar|exibe|quero\s+ver|deixa\s+eu\s+ver|cad[eê])\s+"
                 r"(?:pra\s+mim\s+)?(?:o\s+|a\s+)?(?:holograma\s+d[aoe]s?\s+|modelo\s+d[aoe]s?\s+)?(?:o\s+|a\s+|meu\s+|minha\s+)?(?P<nome>.+?)"
                 r"(?:\s+em\s+3\s*d|\s+em\s+holograma|\s+escaneada?o?)?[ .!?]*$")


def pelo_nome(texto):
    """Item escaneado cujo nome bate com o que ele falou (sem acento, sem artigo)."""
    alvo = _sa(texto)
    alvo = re.sub(r"^(?:o|a|os|as|meu|minha|um|uma)\s+", "", alvo)
    if not alvo:
        return None
    with _trava:
        itens = _ler()
    for i in itens:
        n = re.sub(r"^(?:o|a|os|as|meu|minha|um|uma)\s+", "", _sa(i["nome"]))
        if n and (alvo == n or alvo == n + "s" or n == alvo + "s"):
            return i
    return None


def pedido_de_voz(texto_sem_acento):
    m = VOZ.match(texto_sem_acento)
    return pelo_nome(m.group("nome")) if m else None


# ------------------------------------------------------------------ scanner: foto → 3D
def iniciar(foto: bytes, nome: str, estilo: str = "real"):
    nome = (nome or "").strip()[:60] or "Objeto"
    try:
        img = Image.open(__import__("io").BytesIO(foto))
        img.verify()
    except Exception:
        raise ValueError("isso não é uma foto que eu consiga abrir")
    tid = uuid.uuid4().hex[:10]
    TRABALHOS[tid] = {"estado": "gerando", "etapa": "Enviando a foto", "erro": None, "item": None, "nome": nome, "inicio": time.time()}
    threading.Thread(target=_gerar, args=(tid, foto, nome, estilo if estilo in ("real", "raiox") else "real"), daemon=True).start()
    return tid


def _trellis(foto, etapa, tok):
    from gradio_client import Client, handle_file
    c = Client("trellis-community/TRELLIS", token=tok, verbose=False)
    c.predict(api_name="/start_session")
    etapa("Recortando o objeto da foto")
    pre = c.predict(image=handle_file(str(foto)), api_name="/preprocess_image")
    etapa("Esculpindo em 3D (uns 45 s)")
    r = c.predict(image=handle_file(pre), multiimages=[], seed=0, ss_guidance_strength=7.5, ss_sampling_steps=12,
                  slat_guidance_strength=3.0, slat_sampling_steps=12, multiimage_algo="stochastic",
                  mesh_simplify=0.95, texture_size=1024, api_name="/generate_and_extract_glb")
    return r[1], pre, "TRELLIS"


def _hunyuan(foto, etapa, tok):
    from gradio_client import Client, handle_file
    etapa("A primeira IA não deu; tentando a reserva (só a forma, sem cor)")
    c = Client("tencent/Hunyuan3D-2", token=tok, verbose=False)
    r = c.predict(caption=None, image=handle_file(str(foto)), mv_image_front=None, mv_image_back=None, mv_image_left=None,
                  mv_image_right=None, steps=30, guidance_scale=5.0, seed=1234, octree_resolution=256, check_box_rembg=True,
                  num_chunks=8000, randomize_seed=True, api_name="/shape_generation")
    glb = r[0]["value"] if isinstance(r[0], dict) else r[0]
    return glb, None, "Hunyuan3D"


def _enxugar(origem, destino):
    """Modelo só-forma pesado (o Hunyuan duplica cada face) → tira as repetidas e simplifica. Com textura, não mexe."""
    import numpy as np
    import trimesh
    cena_ = trimesh.load(origem)
    malhas = list(cena_.geometry.values()) if isinstance(cena_, trimesh.Scene) else [cena_]
    if sum(len(m.faces) for m in malhas) <= MAX_FACES or any(getattr(m.visual, "kind", None) == "texture" for m in malhas):
        shutil.copyfile(origem, destino)
        return
    import fast_simplification as fs
    m = trimesh.util.concatenate([x for x in malhas if hasattr(x, "faces")])
    _, idx = np.unique(np.sort(m.faces, axis=1), axis=0, return_index=True)
    faces = m.faces[np.sort(idx)]
    v, f = m.vertices, faces
    if len(f) > MAX_FACES:
        v, f = fs.simplify(m.vertices, faces, target_reduction=1 - MAX_FACES / len(faces))
    trimesh.Trimesh(v, f, process=False).export(destino)


def _gerar(tid, foto, nome, estilo):
    t = TRABALHOS[tid]
    etapa = lambda txt: t.update(etapa=txt)  # noqa: E731
    tmp = Path(tempfile.mkdtemp(prefix="scan3d-"))
    try:
        entrada = tmp / "foto.png"
        img = Image.open(__import__("io").BytesIO(foto)).convert("RGB")
        img.thumbnail((1024, 1024))
        img.save(entrada)
        tok = _token()
        try:
            glb, recorte, motor = _trellis(entrada, etapa, tok)
        except Exception as e1:
            if "quota" in str(e1).lower() and not tok:
                etapa("Cota grátis do dia acabou nessa IA; tentando a reserva")
            try:
                glb, recorte, motor = _hunyuan(entrada, etapa, tok)
            except Exception as e2:
                raise RuntimeError(_explicar(e1, e2, tok)) from e2
        etapa("Deixando leve e guardando")
        PASTA.mkdir(parents=True, exist_ok=True)
        id_ = re.sub(r"[^a-z0-9]+", "-", _sa(nome)).strip("-")[:30] or "objeto"
        id_ = f"{id_}-{uuid.uuid4().hex[:4]}"
        _enxugar(glb, PASTA / f"{id_}.glb")
        miniatura = Image.open(recorte or entrada).convert("RGBA")
        miniatura.thumbnail((256, 256))
        miniatura.save(PASTA / f"{id_}.png")
        item = {"id": id_, "nome": nome, "estilo": estilo if motor == "TRELLIS" else "raiox", "motor": motor,
                "criado": time.strftime("%Y-%m-%d %H:%M"), "kb": round((PASTA / f"{id_}.glb").stat().st_size / 1024)}
        with _trava:
            itens = _ler()
            itens.insert(0, item)
            _gravar(itens)
        t.update(estado="pronto", etapa="Pronto", item=item)
        if ao_terminar:
            ao_terminar(item)
    except Exception as e:
        t.update(estado="erro", erro=str(e)[:300])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _explicar(e1, e2, tok):
    txt = f"{e1} {e2}".lower()
    if "quota" in txt or "gpu duration" in txt or "exceeded" in txt:
        return ("A cota grátis do dia acabou nas duas IAs. " + ("Tenta de novo amanhã." if tok else
                "Põe um token grátis do Hugging Face aqui na aba Scanner 3D que a cota sobe, ou tenta amanhã."))
    if "connect" in txt or "timed out" in txt or "getaddrinfo" in txt:
        return "Sem conexão com o Hugging Face agora. Confere a internet e tenta de novo."
    return f"As duas IAs falharam agora (TRELLIS: {str(e1)[:90]} · Hunyuan: {str(e2)[:90]}). Tenta de novo em alguns minutos."


def estado(tid):
    t = TRABALHOS.get(tid)
    if not t:
        return None
    return {"estado": t["estado"], "etapa": t["etapa"], "erro": t["erro"], "item": t["item"], "segundos": round(time.time() - t["inicio"])}
