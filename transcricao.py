"""Modo Reunião: o Jarvis ouve a reunião, transcreve LOCAL (faster-whisper — nada sai do PC, bom pra LGPD) e no fim
gera ATA (resumo + decisões + tarefas) com o cérebro. Grava o microfone; a transcrição roda numa thread em trechos.

Comandos de voz:
  - "modo reunião" / "começa a gravar a reunião" / "transcreve a reunião"  → começa
  - "como está a reunião"                                                   → status (duração, trechos, último)
  - "encerra a reunião" / "para a reunião" / "finaliza a reunião"           → fecha, monta a ata e salva

É DIFERENTE de reunioes.py (que AGENDA reunião no painel). Salva em conteudo/reunioes/AAAA-MM-DD-HHMM-ata.md
(+ -transcricao.txt). Nada é enviado pra nuvem na transcrição; só a ata passa pelo cérebro (texto, sem áudio)."""
import asyncio
import re
import threading
import time
from datetime import datetime
from pathlib import Path

import cerebro

RAIZ = Path(__file__).parent
PASTA = RAIZ / "conteudo" / "reunioes"
DEMORA = False  # o iniciar/status respondem na hora; o parar leva alguns segundos (gera a ata)
MODELO = "small"  # qualidade/velocidade boa pro PT; baixa uma vez (~0,5 GB) e fica em cache
SR = 16000

INICIAR = re.compile(r"\b(?:modo reuni[aã]o|(?:come[cç]a(?:r)?|inicia(?:r)?|grava(?:r)?|liga(?:r)?|ativa(?:r)?)\s+"
                     r"(?:a\s+|o\s+)?(?:grava[cç][aã]o\s+d[ae]\s+)?reuni[aã]o|transcrev[ae](?:r)?\s+(?:a\s+)?reuni[aã]o)\b", re.I)
PARAR = re.compile(r"\b(?:encerra(?:r)?|termina(?:r)?|para(?:r)?|finaliza(?:r)?|fecha(?:r)?)\s+"
                   r"(?:a\s+|o\s+)?(?:grava[cç][aã]o\s+d[ae]\s+)?reuni[aã]o\b", re.I)
STATUS = re.compile(r"\b(?:como\s+(?:t[aá]|est[aá]|vai)\s+(?:a\s+)?reuni[aã]o|status\s+d[ae]\s+reuni[aã]o)\b", re.I)

_estado = {"gravando": False, "inicio": 0.0, "trechos": [], "erro": None}
_parar_flag = False
_modelo_cache = {}


def _modelo():
    if "m" in _modelo_cache:
        return _modelo_cache["m"]
    try:
        from faster_whisper import WhisperModel
        _modelo_cache["m"] = WhisperModel(MODELO, device="cpu", compute_type="int8")
    except Exception as e:  # lib ausente ou falha ao baixar
        _estado["erro"] = f"motor de transcrição: {e}"
        _modelo_cache["m"] = None
    return _modelo_cache["m"]


def _transcrever(audio, modelo):
    try:
        segs, _ = modelo.transcribe(audio, language="pt", vad_filter=True)
        texto = " ".join(s.text.strip() for s in segs).strip()
        if texto:
            _estado["trechos"].append({"t": time.time(), "texto": texto})
    except Exception as e:
        _estado["erro"] = f"transcrição: {e}"


def _loop():
    """Roda em thread: carrega o modelo, abre o microfone e transcreve de 15 em 15 s."""
    global _parar_flag
    import numpy as np
    import sounddevice as sd
    modelo = _modelo()
    if modelo is None:
        _estado["gravando"] = False
        return
    buffer, por_trecho = [], 15
    try:
        with sd.InputStream(samplerate=SR, channels=1, dtype="float32") as stream:
            while not _parar_flag:
                bloco, _ = stream.read(SR)  # ~1 s
                buffer.append(bloco[:, 0].copy())
                if len(buffer) >= por_trecho:
                    _transcrever(np.concatenate(buffer), modelo)
                    buffer = []
            if buffer:
                _transcrever(np.concatenate(buffer), modelo)
    except Exception as e:
        _estado["erro"] = f"microfone: {e}"
    _estado["gravando"] = False


def iniciar():
    global _parar_flag
    if _estado["gravando"]:
        return "já"
    _estado.update({"gravando": True, "inicio": time.time(), "trechos": [], "erro": None})
    _parar_flag = False
    threading.Thread(target=_loop, daemon=True).start()
    return "ok"


def parar():
    global _parar_flag
    if not _estado["gravando"] and not _estado["trechos"]:
        return {"vazio": True}
    _parar_flag = True
    for _ in range(40):  # espera o loop fechar e transcrever o resto (até ~4 s)
        if not _estado["gravando"]:
            break
        time.sleep(0.1)
    transcricao = "\n".join(t["texto"] for t in _estado["trechos"]).strip()
    if not transcricao:
        return {"vazio": True, "erro": _estado["erro"]}
    ata = _gerar_ata(transcricao)
    arquivo = _salvar(transcricao, ata)
    return {"transcricao": transcricao, "ata": ata, "arquivo": str(arquivo)}


def _gerar_ata(transcricao):
    sistema = ("Você é um secretário executivo. Recebe a transcrição crua de uma reunião (pode ter erros de fala) e "
               "devolve em português do Brasil, em markdown, com exatamente estes títulos: '## Resumo' (até 5 linhas), "
               "'## Decisões' (bullets) e '## Tarefas' (lista acionável: quem, o quê e quando, quando aparecer). "
               "Seja fiel à transcrição: NÃO invente nada que não foi dito. Se algo não ficou claro, escreva '(não ficou claro)'.")
    try:
        return asyncio.run(cerebro.completar(
            [{"role": "system", "content": sistema}, {"role": "user", "content": transcricao[:12000]}],
            temperatura=0.3, max_tokens=900, dificil=True)).strip()
    except Exception as e:
        return f"(Não consegui gerar a ata agora: {e}. A transcrição está salva em texto.)"


def _salvar(transcricao, ata):
    PASTA.mkdir(parents=True, exist_ok=True)
    nome = datetime.now().strftime("%Y-%m-%d-%H%M")
    (PASTA / f"{nome}-transcricao.txt").write_text(transcricao, encoding="utf-8")
    arq = PASTA / f"{nome}-ata.md"
    arq.write_text(f"# Ata da reunião — {datetime.now():%d/%m/%Y %H:%M}\n\n{ata}\n", encoding="utf-8")
    return arq


def _status():
    if not _estado["gravando"]:
        return "Não estou gravando reunião agora, chefe."
    dur = int(time.time() - _estado["inicio"])
    n = len(_estado["trechos"])
    ult = _estado["trechos"][-1]["texto"] if _estado["trechos"] else "(ainda capturando…)"
    return f"Gravando há {dur // 60}min{dur % 60:02d}, chefe. {n} trecho{'s' if n != 1 else ''} até agora. Último: {ult[:140]}"


def entender(texto):
    t = texto.strip()
    m = PARAR.search(t)
    # "para" no meio da frase é preposição ("muda a Clínica Sorriso PARA reunião marcada"), não o verbo parar:
    # só vale como "parar" se vier no começo do pedido (com ou sem "jarvis"). Os outros verbos valem em qualquer lugar.
    if m and (not re.match(r"para\b", m.group(0), re.I) or re.match(r"^(?:jarvis[ ,]*)?$", t[:m.start()], re.I)):
        return {"acao": "parar"}
    if STATUS.search(t):
        return {"acao": "status"}
    if INICIAR.search(t):
        return {"acao": "iniciar"}
    return None


def executar(p):
    if p["acao"] == "iniciar":
        r = iniciar()
        if r == "já":
            return "Já estou gravando a reunião, chefe.", []
        return ("Modo reunião ligado, chefe. Tô gravando e transcrevendo aqui no PC. No fim é só dizer "
                "'encerra a reunião' que eu monto a ata.",
                [{"titulo": "Modo Reunião", "destaque": "🔴 Gravando", "rapido": True,
                  "texto": "Transcrição local — nada sai do PC. Diga “encerra a reunião” pra fechar e gerar a ata."}])
    if p["acao"] == "status":
        return _status(), []
    if p["acao"] == "parar":
        r = parar()
        if r.get("vazio"):
            base = "Não tinha reunião gravando, chefe." if not _estado["trechos"] else "A reunião não teve fala transcrita, chefe."
            return (base + (f" (erro: {r['erro']})" if r.get("erro") else "")), []
        return ("Reunião encerrada, chefe. Montei a ata com resumo, decisões e tarefas — tá salva e aqui na tela.",
                [{"titulo": "Ata da reunião", "destaque": "Pronta", "texto": r["ata"][:1600]}])
    return None
