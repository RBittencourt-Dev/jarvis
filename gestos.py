"""Controle por GESTOS (MediaPipe Tasks, roda local). A webcam só liga quando ele pede ("liga os gestos") e solta
quando pede pra desligar — nada é gravado, é só a forma da mão (não identifica ninguém). Empurra o gesto pro HUD
pelo SSE (canal 'hud'); quem age é o jarvis.js.

Gestos (v1):
  ✊ punho fechado   → "punho"  (o HUD interrompe a fala / para)
  👍 polegar pra cima → "sim"    (confirma uma autorização)
  👎 polegar pra baixo→ "nao"    (recusa)
  ✋ mão aberta       → "aberta" (alterna modo foco/completo)

Comandos de voz: "liga/ativa os gestos", "desliga/para os gestos", "os gestos estão ligados?"."""
import re
import threading
import time
from pathlib import Path

import extensao

RAIZ = Path(__file__).parent
MODELO = RAIZ / "modelos" / "hand_landmarker.task"
URL_MODELO = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
DEMORA = False

LIGAR = re.compile(r"\b(?:liga(?:r)?|ativa(?:r)?|habilita(?:r)?|come[cç]a(?:r)?)\s+(?:o\s+|os\s+)?(?:controle\s+(?:por\s+)?)?gestos?\b", re.I)
DESLIGAR = re.compile(r"\b(?:desliga(?:r)?|desativa(?:r)?|para(?:r)?|tira(?:r)?|fecha(?:r)?)\s+(?:o\s+|os\s+)?(?:controle\s+(?:por\s+)?)?gestos?\b", re.I)
STATUS = re.compile(r"\bgestos?\s+(?:est[aã]o?\s+)?(?:ligados?|ativos?|funcionando)\b|\bstatus\s+d[eo]s?\s+gestos?\b", re.I)

_estado = {"ligado": False, "erro": None}
_parar = False
_frame = {"jpg": None, "t": 0.0}   # última miniatura da câmera (com os pontos da mão) pro painel VISÃO
_opcoes = {"so_tracking": False}   # True = desenha só o esqueleto da mão no fundo preto (oculta a câmera)
_LIG = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10), (10, 11), (11, 12),
        (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (17, 18), (18, 19), (19, 20), (0, 17)]


def _desenhar_frame(frame, res):
    """Desenha os pontos/ligações da mão no quadro, espelha, encolhe e guarda um JPEG pequeno (leve)."""
    import cv2, numpy as np
    h, w = frame.shape[:2]
    base = np.zeros_like(frame) if _opcoes["so_tracking"] else frame   # fundo preto = só o tracking
    if res and res.hand_landmarks:
        cores = [(255, 229, 0), (0, 176, 255)]   # BGR: ciano (mão 0) e âmbar (mão 1) — bate com os cursores
        for i, mao in enumerate(res.hand_landmarks):   # desenha TODAS as mãos (até 2)
            cor = cores[i % 2]
            pts = [(int(p.x * w), int(p.y * h)) for p in mao]
            for a, b in _LIG:
                cv2.line(base, pts[a], pts[b], cor, 2)
            for (x, y) in pts:
                cv2.circle(base, (x, y), 4, (255, 245, 150), -1)
    small = cv2.flip(cv2.resize(base, (320, max(1, int(320 * h / w)))), 1)  # espelho (natural)
    ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 55])
    if ok:
        _frame["jpg"] = buf.tobytes(); _frame["t"] = time.time()


def frame_atual():
    """Bytes do último JPEG da câmera (só quando os gestos estão ligados)."""
    return _frame["jpg"] if _estado["ligado"] else None


def set_tracking_only(v):
    """True oculta a imagem da câmera e mostra só o esqueleto da mão (fundo preto)."""
    _opcoes["so_tracking"] = bool(v)
    return _opcoes["so_tracking"]


def _baixar_modelo():
    if MODELO.exists():
        return True
    try:
        import httpx
        MODELO.parent.mkdir(parents=True, exist_ok=True)
        MODELO.write_bytes(httpx.get(URL_MODELO, timeout=60).content)
        return True
    except Exception as e:
        _estado["erro"] = f"modelo: {e}"
        return False


def _criar_landmarker():
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    base = python.BaseOptions(model_asset_path=str(MODELO))
    opc = vision.HandLandmarkerOptions(base_options=base, num_hands=2, running_mode=vision.RunningMode.VIDEO,
                                       min_hand_detection_confidence=0.6, min_tracking_confidence=0.6)
    return vision.HandLandmarker.create_from_options(opc)


def _classificar(lm):
    """lm = 21 landmarks normalizados. Devolve o gesto ou None.
    Robusto a rotação: 'esticado' = ponta mais longe do PULSO que a junta (não depende do eixo Y),
    e só devolve gesto quando está CLARO (ambíguo → None, pra não disparar errado)."""
    import math
    def d(a, b):
        return math.hypot(lm[a].x - lm[b].x, lm[a].y - lm[b].y)
    PULSO = 0
    def estende(tip, pip):               # dedo esticado: ponta bem mais longe do pulso que a junta média
        return d(tip, PULSO) > d(pip, PULSO) * 1.05
    idx, mid, rng, pnk = estende(8, 6), estende(12, 10), estende(16, 14), estende(20, 18)
    dedos = sum((idx, mid, rng, pnk))
    pol = d(4, PULSO) > d(2, PULSO) * 1.1  # polegar esticado
    if dedos == 4 and pol:                 # mão toda aberta (os 5)
        return "aberta"
    if dedos == 0:                         # os 4 dedos dobrados = punho
        if pol:                            # com o polegar esticado = joinha pra cima/baixo
            if lm[4].y < lm[PULSO].y - 0.08:
                return "sim"
            if lm[4].y > lm[PULSO].y + 0.08:
                return "nao"
            return None                    # polegar de lado: não confia
        return "punho"
    return None                            # qualquer coisa no meio do caminho: ignora


def _loop():
    global _parar
    try:
        import cv2
        import mediapipe as mp
    except Exception as e:
        _estado["erro"] = f"bibliotecas: {e}"; _estado["ligado"] = False; return
    if not _baixar_modelo():
        _estado["ligado"] = False; return
    try:
        marcador = _criar_landmarker()
    except Exception as e:
        _estado["erro"] = f"modelo: {e}"; _estado["ligado"] = False; return
    cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cam.isOpened():
        cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        _estado["erro"] = "não abri a webcam"; _estado["ligado"] = False; return

    import math
    anterior, estavel, ultimo_envio = None, 0, 0.0
    tinha_mao = False
    pinca_slot = [False, False]       # pinça (com histerese) de cada slot
    slots = [None, None]              # última posição (x,y) de cada slot, pra manter a identidade
    try:
        while not _parar:
            ok, frame = cam.read()
            if not ok:
                time.sleep(0.05); continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            imagem = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            res = marcador.detect_for_video(imagem, int(time.time() * 1000))
            gesto = _classificar(res.hand_landmarks[0]) if res.hand_landmarks else None
            if gesto and gesto == anterior:
                estavel += 1
            else:
                anterior, estavel = gesto, 1 if gesto else 0
            agora = time.time()
            if agora - _frame["t"] > 0.11:   # ~8 fps de preview pro painel VISÃO
                try:
                    _desenhar_frame(frame, res)
                except Exception:
                    pass
            # controle de mão (1 ou 2 mãos): cursor + pinça, com identidade ESTÁVEL por proximidade (slots 0/1)
            try:
                det = []
                for lm in (res.hand_landmarks or []):
                    d48 = math.hypot(lm[4].x - lm[8].x, lm[4].y - lm[8].y)
                    escala = math.hypot(lm[0].x - lm[9].x, lm[0].y - lm[9].y) or 1e-3
                    rp = d48 / escala
                    det.append({"x": 1.0 - lm[8].x, "y": lm[8].y,          # espelho (bate com o preview)
                                "junto": rp < 0.50 or d48 < 0.06, "solto": rp > 0.70 and d48 > 0.08})
                # casa cada mão com o slot mais próximo do quadro anterior (raio 0.18); o resto pega slot livre
                atrib, usados = {}, set()
                for di, d in enumerate(det):
                    melhor, dist0 = None, 0.18
                    for s in (0, 1):
                        if s in usados or slots[s] is None:
                            continue
                        dd = math.hypot(d["x"] - slots[s][0], d["y"] - slots[s][1])
                        if dd < dist0:
                            dist0, melhor = dd, s
                    if melhor is not None:
                        atrib[di] = melhor; usados.add(melhor)
                for di in range(len(det)):
                    if di in atrib:
                        continue
                    for s in (0, 1):
                        if s not in usados:
                            atrib[di] = s; usados.add(s); break
                novo = [None, None]; maos = []
                for di, d in enumerate(det):
                    s = atrib.get(di)
                    if s is None:
                        continue
                    novo[s] = (d["x"], d["y"])
                    pin = d["junto"] or (pinca_slot[s] and not d["solto"])   # histerese por slot
                    pinca_slot[s] = pin
                    maos.append({"id": s, "x": round(d["x"], 4), "y": round(d["y"], 4), "pinca": pin})
                for s in (0, 1):
                    if novo[s] is None:
                        pinca_slot[s] = False
                slots[0], slots[1] = novo[0], novo[1]
                if maos:
                    for canal in ("hud", "palco"):   # tela principal + o centro embutido (onde abre a BMW etc.)
                        extensao.publicar({"maos": maos}, canal)
                    tinha_mao = True
                elif tinha_mao:
                    for canal in ("hud", "palco"):
                        extensao.publicar({"maos": []}, canal)
                    tinha_mao = False
            except Exception:
                pass
            if gesto and estavel >= 5 and agora - ultimo_envio > 1.5:   # estável ~0,5s + espera 1,5s (precisão)
                ultimo_envio = agora; estavel = 0
                try:
                    extensao.publicar({"gesto": gesto}, "hud")
                except Exception:
                    pass
            time.sleep(0.06)  # ~15 fps (estável)
    finally:
        try:
            cam.release()
        except Exception:
            pass
        _frame["jpg"] = None
    _estado["ligado"] = False


def iniciar():
    global _parar
    if _estado["ligado"]:
        return "Os gestos já estão ligados, chefe."
    _estado.update({"ligado": True, "erro": None})
    _parar = False
    threading.Thread(target=_loop, daemon=True).start()
    time.sleep(0.3)
    if _estado["erro"]:
        _estado["ligado"] = False
        return f"Não consegui ligar os gestos, chefe: {_estado['erro']}."
    return "Gestos ligados, chefe."


def parar():
    global _parar
    if not _estado["ligado"]:
        return "Os gestos já estavam desligados, chefe."
    _parar = True
    _estado["ligado"] = False
    _frame["jpg"] = None
    return "Gestos desligados, chefe. Soltei a câmera."


def entender(texto):
    t = texto.strip()
    if DESLIGAR.search(t):
        return {"acao": "desligar"}
    if LIGAR.search(t):
        return {"acao": "ligar"}
    if STATUS.search(t):
        return {"acao": "status"}
    return None


def executar(p):
    if p["acao"] == "ligar":
        return iniciar(), []
    if p["acao"] == "desligar":
        return parar(), []
    estado = "ligados" if _estado["ligado"] else "desligados"
    return f"Os gestos estão {estado}, chefe.", []
