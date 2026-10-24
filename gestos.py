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
    opc = vision.HandLandmarkerOptions(base_options=base, num_hands=1, running_mode=vision.RunningMode.VIDEO)
    return vision.HandLandmarker.create_from_options(opc)


def _classificar(lm):
    """lm = 21 landmarks normalizados (y cresce pra BAIXO). Devolve o gesto ou None."""
    def estende(tip, pip):  # dedo esticado: ponta acima da junta
        return lm[tip].y < lm[pip].y - 0.02
    dedos = sum(estende(t, p) for t, p in ((8, 6), (12, 10), (16, 14), (20, 18)))  # indicador, médio, anelar, mínimo
    pontas_y = [lm[i].y for i in (6, 10, 14, 18)]
    polegar_y = lm[4].y
    if dedos == 4:
        return "aberta"
    if dedos == 0:
        if polegar_y < min(pontas_y) - 0.06:      # polegar bem mais alto que a mão fechada
            return "sim"
        if polegar_y > max(pontas_y) + 0.06:       # polegar bem mais baixo
            return "nao"
        return "punho"
    return None


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

    anterior, estavel, ultimo_envio = None, 0, 0.0
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
            if gesto and estavel >= 4 and agora - ultimo_envio > 1.5:   # estável ~0,4s + espera 1,5s entre disparos
                ultimo_envio = agora; estavel = 0
                try:
                    extensao.publicar({"gesto": gesto}, "hud")
                except Exception:
                    pass
            time.sleep(0.06)  # ~15 fps
    finally:
        try:
            cam.release()
        except Exception:
            pass
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
    return ("Gestos ligados, chefe. Punho fechado me faz parar, joinha é sim, polegar pra baixo é não, "
            "e a mão aberta troca o modo. É só dizer 'desliga os gestos' pra eu soltar a câmera.")


def parar():
    global _parar
    if not _estado["ligado"]:
        return "Os gestos já estavam desligados, chefe."
    _parar = True
    _estado["ligado"] = False
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
