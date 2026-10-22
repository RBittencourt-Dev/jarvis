"""Fica ouvindo o microfone e abre o Jarvis com duas palmas ou chamando "Jarvis".

Nada é gravado nem sai do PC enquanto ninguém chama: o volume de cada fatia de 20 ms vira
detector de palma, e o Vosk (reconhecimento offline) só procura a palavra "Jarvis".

Segundo plano: com a tela fechada, "Jarvis, abre o Spotify" é executado sem abrir nada.
Só o trecho depois do nome é mandado pro Whisper da Groq (cerebro.transcrever) e o
Jarvis responde pela caixa de som. "Jarvis" sozinho, ou duas palmas, abrem a tela.
Palma = pico curto e bem acima do barulho de fundo. Duas palmas no intervalo
certo abrem a janela (e ligam o servidor se ele estiver desligado).

    python palmas.py            fica ouvindo
    python palmas.py --medir    mostra o volume, para ajustar a sensibilidade
"""
import collections
import ctypes
import io
import json
import queue
import re
import tempfile
import wave
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import numpy as np
import sounddevice as sd
import vosk

import primeiro_uso  # noqa: F401
import cerebro
import falas

RAIZ = Path(__file__).parent
CONFIG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
AJUSTE = CONFIG["palmas"]
URL = f"http://127.0.0.1:{CONFIG['porta']}"  # "localhost" no Windows tenta IPv6 antes e perde 2 s
TAXA, BLOCO = 16000, 320  # 20 ms

MODELO_VOZ = RAIZ / "modelos" / "vosk-model-small-en-us-0.15"
audio_para_voz = queue.Queue(maxsize=400)

fundo = 0.01
ultima_palma = 0.0
ultima_abertura = 0.0
pico_anterior = 0.0


audio_da_espera = []


def tela_reagiu(status, antes):
    """A tela aberta ouviu mesmo o "Jarvis"? O bug antigo: o reconhecimento do Chrome morria calado depois de muito
    tempo parado, e daqui só se via "tela aberta" — ninguém atendia. Agora: ouvido morto ou nenhuma transcrição na
    tela em até 2,5 s depois do nome = tela surda → manda ela reanimar e o segundo plano atende (o áudio desse
    tempo de espera vai junto, pra não perder o pedido). Mutado de propósito (clique no 7) continua mudo."""
    if status.get("ouvido_da_tela") == "mudo":
        return True
    if status.get("tela_ouvindo", True):
        ouvido_em = time.time()
        extra = []
        while time.time() - ouvido_em < 2.5:
            try:
                extra.append(audio_para_voz.get(timeout=0.5))
            except queue.Empty:
                pass
            s = servidor_no_ar() or {}
            if s.get("tela_ouviu_ha", 999) < time.time() - ouvido_em + 1.5:
                return True  # a tela transcreveu algo agora: ela está atendendo
        audio_da_espera[:] = extra  # o pedido dito durante a espera vai junto pro segundo plano
    print("chamaram pelo nome: a tela está aberta mas surda — reanimando e atendendo no segundo plano")
    try:
        httpx.post(URL + "/api/reouvir", timeout=2)
    except Exception:
        pass
    return False


def servidor_no_ar():
    try:
        return httpx.get(URL + "/api/status", timeout=1).json()
    except Exception:
        return None


def ligar_servidor():
    pythonw = RAIZ / ".venv" / "Scripts" / "pythonw.exe"
    subprocess.Popen([str(pythonw), str(RAIZ / "server.py")], cwd=RAIZ, creationflags=subprocess.DETACHED_PROCESS)
    for _ in range(40):
        if servidor_no_ar():
            return True
        time.sleep(0.25)
    return False


def navegador():
    for p in [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe",
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),  # PC sem Chrome: o Edge serve igual
    ]:
        if p.exists():
            return p
    return None


def acordar(motivo):
    global ultima_abertura
    if time.time() - ultima_abertura < 5:
        return
    ultima_abertura = time.time()
    print(motivo)
    threading.Thread(target=abrir_jarvis, daemon=True).start()


def ouvir_o_nome():
    """Roda numa thread: só reconhece "jarvis" (o resto vira [unk]), então é leve e erra pouco."""
    global modelo_vosk
    vosk.SetLogLevel(-1)
    modelo_vosk = vosk.Model(str(MODELO_VOZ))
    rec = vosk.KaldiRecognizer(modelo_vosk, TAXA, json.dumps(["jarvis", "[unk]"]))
    antes = collections.deque(maxlen=75)  # 1,5 s de áudio anterior: o "Jarvis" e o começo do pedido
    while True:
        bloco = audio_para_voz.get()
        antes.append(bloco)
        if rec.AcceptWaveform(bloco):
            texto = json.loads(rec.Result()).get("text", "")
        else:
            texto = json.loads(rec.PartialResult()).get("partial", "")
        if "jarvis" in texto:
            rec.Reset()
            status = servidor_no_ar()
            audio_da_espera.clear()
            if status and status.get("tela_aberta"):
                # pedido dele: com a interface aberta, o segundo plano NÃO atende (quem ouve é a tela). Se a tela
                # disser que o ouvido dela morreu, só manda ela se reanimar.
                if not status.get("tela_ouvindo", True):
                    try:
                        httpx.post(URL + "/api/reouvir", timeout=2)
                    except Exception:
                        pass
                print("chamaram pelo nome: a interface está aberta e ouvindo; o segundo plano fica quieto")
            elif not cerebro.chave("groq"):
                acordar("chamaram pelo nome: abrindo o Jarvis")  # sem Groq não há ouvido bom: abre a tela como antes
            else:
                try:
                    segundo_plano(list(antes) + audio_da_espera)
                except Exception as e:
                    print("segundo plano falhou:", e)
            antes.clear()
            esvaziar_fila()  # o que entrou enquanto ele falava é a voz dele mesmo


# ------------------------------------------------------------------ segundo plano: pedido sem abrir a tela

FALA_MINIMA = 0.02
SILENCIO_PARA_ACABAR = 70  # blocos de 20 ms (1,4 s): dá pra respirar no meio da frase sem ele cortar


def esvaziar_fila():
    while not audio_para_voz.empty():
        try:
            audio_para_voz.get_nowait()
        except queue.Empty:
            break


def gravar_pedido(inicio=(), espera_fala=4.0, maximo=20.0):
    """Junta o áudio até ele parar de falar. Devolve bytes PCM 16 bits, ou None se ele não falou nada."""
    blocos = list(inicio)
    falou = any(np.abs(np.frombuffer(b, np.int16)).max() / 32767 > FALA_MINIMA * 2 for b in blocos[-25:])
    silencio = 0
    limite_fala = time.time() + espera_fala
    fim = time.time() + maximo
    while time.time() < fim:
        try:
            bloco = audio_para_voz.get(timeout=1)
        except queue.Empty:
            continue
        blocos.append(bloco)
        alto = np.abs(np.frombuffer(bloco, np.int16)).max() / 32767 > max(FALA_MINIMA, fundo * 3)
        if alto:
            falou, silencio = True, 0
        else:
            silencio += 1
        if falou and silencio >= SILENCIO_PARA_ACABAR:
            break
        if not falou and time.time() > limite_fala:
            return None
    return b"".join(blocos) if falou else None


def gravar_depois_do_nome(inicio):
    """Logo depois do "Jarvis": espera o pedido até 2,2 s (uma pausinha depois do nome é normal).
    Devolve o áudio (nome + pedido) se ele falou algo depois do nome; None se ficou só no nome."""
    blocos = list(inicio)
    comeco = time.time()
    ate = comeco + 2.2
    falou_depois, silencio = False, 0
    fim = comeco + 20.0
    while time.time() < fim:
        try:
            bloco = audio_para_voz.get(timeout=0.5)
        except queue.Empty:
            if not falou_depois and time.time() > ate:
                return None
            continue
        blocos.append(bloco)
        alto = np.abs(np.frombuffer(bloco, np.int16)).max() / 32767 > max(FALA_MINIMA, fundo * 3)
        if time.time() - comeco < 0.35:
            continue  # ainda é o fim do "Jarvis"
        if alto:
            falou_depois, silencio = True, 0
        else:
            silencio += 1
        if falou_depois and silencio >= SILENCIO_PARA_ACABAR:
            break
        if not falou_depois and time.time() > ate:
            return None
    return b"".join(blocos) if falou_depois else None


def em_wav(pcm):
    saida = io.BytesIO()
    with wave.open(saida, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes(pcm)
    return saida.getvalue()


# o que vem depois do "Jarvis" quando ele só quer que pare de falar
PARAR = re.compile(r"(?:j[aá] )?(?:deu|chega|para|pare|parar|pode parar|para de falar|cala(?: a)?(?: boca)?|"
                   r"fica quiet[oa]|quiet[oa]|sil[eê]ncio|xiu|shh+|stop|espera|pera|t[aá] bom|ok|beleza)"
                   r"(?: a[ií]| j[aá]| chefe| por favor)?", re.I)
INTERFACE = re.compile(r"(?:abre|abra|abrir|aparece|aparecer|mostra|acorda|liga)(?: a| o| tua| sua| a tua| a sua)?"
                       r"(?: (?:tela|janela|interface|hud|cara|jarvis))?(?: (?:do|da) jarvis)?(?: a[ií]| pra mim)?", re.I)
NOME = re.compile(r"^.*?\b(?:jarvis|j[aá]rvis|jarves|jarbas|djarvis|jarviz|chavis)\b[\s,.!?]*", re.I)


def tocar(arquivo_ou_bytes, esperar=True):
    """Toca mp3/wav pela caixa de som com o próprio Windows (MCI), sem programa extra."""
    if isinstance(arquivo_ou_bytes, bytes):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tmp.write(arquivo_ou_bytes)
        tmp.close()
        arquivo_ou_bytes = tmp.name
    mci = ctypes.windll.winmm.mciSendStringW
    alias = f"jv{int(time.time() * 1000) % 1000000}"
    tipo = "waveaudio" if str(arquivo_ou_bytes).lower().endswith(".wav") else "mpegvideo"
    mci(f'open "{arquivo_ou_bytes}" type {tipo} alias {alias}', None, 0, None)
    mci(f"play {alias}" + (" wait" if esperar else ""), None, 0, None)
    if esperar:
        mci(f"close {alias}", None, 0, None)


modelo_vosk = None
ultima_cauda = []  # áudio do fim da última fala (a resposta "sim" pode vir colada)
ultimas_falas = collections.deque(maxlen=4)  # o que ele disse por último: o microfone ouve a caixa de som


def palavras(t):
    return set(re.findall(r"\w{3,}", (t or "").lower()))


def eco(ouvido, *falas):
    """O que o microfone pegou é a voz do próprio Jarvis (60% das palavras iguais a algo que ele falou)?"""
    dele = palavras(NOME.sub("", ouvido or ""))
    if not dele:
        return False
    return any(len(dele & palavras(f)) / len(dele) >= 0.6 for f in (*falas, *ultimas_falas) if f)


def falar(texto):
    """Fala pela caixa de som. Se ele disser "Jarvis" no meio, cala na hora e devolve o áudio desde ali
    (o pedido novo, ou o "para"); senão devolve None."""
    if not texto:
        return None
    ultimas_falas.append(texto)
    try:
        r = httpx.get(URL + "/api/voz", params={"texto": texto}, timeout=40)
    except Exception as e:
        print("não consegui falar:", e)
        return None
    if r.status_code != 200:
        return None
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp.write(r.content)
    tmp.close()
    mci = ctypes.windll.winmm.mciSendStringW
    alias = f"fala{int(time.time() * 1000) % 1000000}"
    mci(f'open "{tmp.name}" type mpegvideo alias {alias}', None, 0, None)
    mci(f"play {alias}", None, 0, None)
    esvaziar_fila()
    rec = vosk.KaldiRecognizer(modelo_vosk, TAXA, json.dumps(["jarvis", "[unk]"])) if modelo_vosk else None
    antes = collections.deque(maxlen=75)
    estado = ctypes.create_unicode_buffer(32)
    interrompido = None
    while True:
        mci(f"status {alias} mode", estado, 32, None)
        if estado.value != "playing":
            break
        try:
            bloco = audio_para_voz.get(timeout=0.05)
        except queue.Empty:
            continue
        antes.append(bloco)
        if not rec:
            continue
        ouvido = json.loads(rec.Result()).get("text", "") if rec.AcceptWaveform(bloco) else \
            json.loads(rec.PartialResult()).get("partial", "")
        if "jarvis" in ouvido:
            # o ouvido simples confunde a voz dele mesmo com o nome: confere com o transcritor bom antes de parar
            conferido = cerebro.transcrever(em_wav(b"".join(list(antes)[-60:])), dica="") or ""
            rec.Reset()
            if NOME.search(conferido) and not eco(conferido, texto):
                mci(f"stop {alias}", None, 0, None)
                interrompido = list(antes)
                print(f"interrompido pelo nome ({conferido!r})")
                break
            print(f"falso alarme enquanto falava: {conferido!r}")
    mci(f"close {alias}", None, 0, None)
    # os últimos ~1,5 s ficam guardados: se era pergunta, a resposta dele pode ter começado antes do fim
    ultima_cauda[:] = list(antes)[-75:] if interrompido is None else []
    return interrompido


def bip():
    """Sinal curtinho de "tô ouvindo" (gerado uma vez e guardado)."""
    arquivo = RAIZ / "voz-guardada" / "bip-ouvindo.wav"
    if not arquivo.exists():
        arquivo.parent.mkdir(exist_ok=True)
        t = np.linspace(0, 0.12, int(TAXA * 0.12), False)
        onda = (np.sin(2 * np.pi * 1320 * t) * np.exp(-t * 30) * 0.35 * 32767).astype(np.int16)
        arquivo.write_bytes(em_wav(onda.tobytes()))
    tocar(str(arquivo), esperar=False)


_vocabulario = {"quando": 0, "lista": []}


def palavras_do_vocabulario():
    """Nomes que ele fala e o Whisper precisa conhecer: as playlists dele (do Spotify) e os contatos. Guarda 1 h."""
    if time.time() - _vocabulario["quando"] < 3600:
        return _vocabulario["lista"]
    extras = []
    try:
        import spotify
        if spotify.configurado():
            for p in spotify._minhas_playlists():
                nome = re.sub(r"[^\w\s&'-]", "", p.get("name") or "").strip()
                if 2 < len(nome) < 30:
                    extras.append(nome)
    except Exception:
        pass
    try:
        contatos = json.loads((RAIZ / "contatos.json").read_text(encoding="utf-8"))
        extras += [k for k in contatos if 2 < len(k) < 25][:15]
    except (OSError, ValueError, TypeError):
        pass
    _vocabulario.update(quando=time.time(), lista=extras[:30])
    return _vocabulario["lista"]


def bip_de_saida():
    """Tom que desce: "voltei pro stand-by"."""
    arquivo = RAIZ / "voz-guardada" / "bip-standby.wav"
    if not arquivo.exists():
        arquivo.parent.mkdir(exist_ok=True)
        t = np.linspace(0, 0.22, int(TAXA * 0.22), False)
        freq = 990 - 1800 * t  # 990 Hz → ~600 Hz
        onda = (np.sin(2 * np.pi * np.cumsum(freq) / TAXA) * np.exp(-t * 12) * 0.25 * 32767).astype(np.int16)
        arquivo.write_bytes(em_wav(onda.tobytes()))
    tocar(str(arquivo), esperar=False)


def segundo_plano(inicio):
    if not servidor_no_ar() and not ligar_servidor():
        print("O servidor não subiu.")
        return
    bip()
    pcm = gravar_depois_do_nome(inicio)
    if not pcm:
        # só chamou e ficou quieto: aí sim se apresenta e espera; se continuar quieto, volta pro stand-by
        interrompido = falar(falas.escolher(falas.CHAMADO))
        esvaziar_fila()
        pcm = gravar_pedido(inicio=interrompido or (), espera_fala=15.0)
        if not pcm:
            print("chamaram e não pediram nada: voltando pro stand-by")
            bip_de_saida()
            return
    precisa_do_nome = True  # a primeira frase tem que ter "Jarvis" (música e TV também acordam o ouvido simples)
    for _ in range(5):  # conversa curta: enquanto ele perguntar algo ("Confirma?"), escuta a resposta sem o nome
        texto = cerebro.transcrever(em_wav(pcm), extras=palavras_do_vocabulario()) or ""
        pedido = NOME.sub("", texto, count=1).strip(" ,.!?") if NOME.search(texto) else texto.strip(" ,.!?")
        print(f"segundo plano: ouvi {texto!r} -> pedido {pedido!r}")
        if not precisa_do_nome and ultimas_falas:
            fim_da_pergunta = palavras(ultimas_falas[-1])
            sobra = texto.split()
            while sobra and (re.sub(r"\W", "", sobra[0].lower()) in fim_da_pergunta):
                sobra.pop(0)
            texto = " ".join(sobra) or texto
            pedido = NOME.sub("", texto, count=1).strip(" ,.!?") if NOME.search(texto) else texto.strip(" ,.!?")
        if precisa_do_nome and not NOME.search(texto):
            print("  sem o nome: não era com ele")
            return
        precisa_do_nome = False
        if eco(pedido):
            print("  é a voz dele mesmo: ignorado")
            return
        if PARAR.fullmatch(pedido):
            return  # "Jarvis, para" / "cala a boca": já calou, não faz mais nada
        if len(pedido) < 2:
            if not NOME.search(texto):
                return  # barulho, ou nem era com ele
            interrompido = falar(falas.escolher(falas.CHAMADO))  # disse só "Jarvis": responde e escuta o pedido
            esvaziar_fila()
            pcm = gravar_pedido(inicio=interrompido or (), espera_fala=15.0)
            if not pcm:
                bip_de_saida()
                return
            continue
        if INTERFACE.fullmatch(pedido):
            acordar("pediram a tela: abrindo o Jarvis")
            return
        try:
            r = httpx.post(URL + "/api/fundo", json={"texto": pedido}, timeout=120).json()
        except Exception as e:
            print("o servidor não respondeu:", e)
            falar("Desculpe, chefe, tive um problema pra fazer isso.")
            return
        interrompido = falar(r.get("fala"))
        esvaziar_fila()
        if interrompido is not None:
            # chamou "Jarvis" enquanto ele falava: o que vem depois é a ordem nova (ou só "para")
            pcm = gravar_pedido(inicio=interrompido, espera_fala=3.0)
            if not pcm:
                return
            continue
        if not r.get("aguardando"):
            return
        bip()
        pcm = gravar_pedido(inicio=ultima_cauda, espera_fala=6.0)  # o "sim" dito em cima do fim da pergunta conta
        if not pcm:
            bip_de_saida()  # perguntou e ele não respondeu: volta pro stand-by
            return


def falar_avisos():
    """Thread: lembrete/pomodoro/site caiu com a tela fechada (ou minimizada) → bip e o Jarvis fala pela caixa de som."""
    while True:
        time.sleep(3)
        status = servidor_no_ar()
        if not status or status.get("tela_aberta"):
            continue  # a tela aberta fala sozinha
        try:
            blocos = httpx.get(URL + "/api/novidades", timeout=5).json().get("blocos", [])
        except Exception:
            continue
        for b in blocos:
            if b.get("fala"):
                bip()
                time.sleep(0.25)
                try:
                    r = httpx.get(URL + "/api/voz", params={"texto": b["fala"]}, timeout=40)
                    if r.status_code == 200:
                        tocar(r.content)
                except Exception as e:
                    print("aviso não falado:", e)


def janela_do_jarvis():
    """Procura a janela pelo título da página (J.A.R.V.I.S.)."""
    achadas = []
    usuario = ctypes.windll.user32

    def olhar(hwnd, _):
        tamanho = usuario.GetWindowTextLengthW(hwnd)
        if tamanho and usuario.IsWindowVisible(hwnd):
            titulo = ctypes.create_unicode_buffer(tamanho + 1)
            usuario.GetWindowTextW(hwnd, titulo, tamanho + 1)
            if titulo.value == "J.A.R.V.I.S.":  # a extensão ("J.A.R.V.I.S. · Extensão") é outra janela
                achadas.append(hwnd)
        return True

    usuario.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(olhar), 0)
    return achadas[0] if achadas else None


def janelas_da_extensao():
    achadas = []
    usuario = ctypes.windll.user32

    def olhar(hwnd, _):
        tamanho = usuario.GetWindowTextLengthW(hwnd)
        if tamanho:
            titulo = ctypes.create_unicode_buffer(tamanho + 1)
            usuario.GetWindowTextW(hwnd, titulo, tamanho + 1)
            if titulo.value.startswith("J.A.R.V.I.S. · Extensão"):
                achadas.append(hwnd)
        return True

    usuario.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(olhar), 0)
    return achadas


def trazer_para_frente(espera=10):
    """O Windows não deixa programa em segundo plano roubar o foco; apertar e soltar o Alt libera."""
    usuario = ctypes.windll.user32
    fim = time.time() + espera
    while time.time() < fim:
        hwnd = janela_do_jarvis()
        if hwnd:
            if usuario.IsIconic(hwnd):
                usuario.ShowWindow(hwnd, 9)  # SW_RESTORE
            usuario.keybd_event(0x12, 0, 0, 0)  # Alt apertado
            usuario.keybd_event(0x12, 0, 2, 0)  # Alt solto
            usuario.SetForegroundWindow(hwnd)
            usuario.BringWindowToTop(hwnd)
            return True
        time.sleep(0.25)
    return False


def abrir_jarvis():
    status = servidor_no_ar()
    if janela_do_jarvis() or (status and status["tela_aberta"]):
        trazer_para_frente(espera=1)  # já está aberto (ou minimizado): só volta pra frente
        for hwnd in janelas_da_extensao():
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # a extensão volta junto
        return
    if not status and not ligar_servidor():
        print("O servidor não subiu. Rode iniciar-jarvis.bat para ver o erro.")
        return
    exe = navegador()
    x, y, w, h = tela_horizontal()
    # perfil próprio: a permissão do microfone fica salva e o som toca sem precisar clicar
    perfil = RAIZ / ".perfil-navegador"
    subprocess.Popen([str(exe), f"--app={URL}", f"--user-data-dir={perfil}",
                      "--autoplay-policy=no-user-gesture-required",
                      # coberta por outra janela ela continua viva e ouvindo (só minimizada é que "dorme")
                      "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding", "--disable-background-timer-throttling",
                      "--remote-debugging-port=9230",  # só local: o Jarvis usa a extensão do Radar por aqui
                      f"--window-position={x},{y}", f"--window-size={w},{h}", "--start-fullscreen"])
    trazer_para_frente()
    try:
        if (servidor_no_ar() or {}).get("usar_extensao"):
            httpx.post(URL + "/api/extensao", json={"abrir": True}, timeout=5)  # já abre com as duas telas
            time.sleep(2.5)
            trazer_para_frente(espera=2)  # o foco volta pro HUD (é nele que o microfone escuta)
    except Exception:
        pass


def tela_horizontal():
    """Área útil do monitor deitado (o vertical fica de fora); com dois deitados, o principal."""
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Screen]::AllScreens | "
                        "ForEach-Object { '{0} {1} {2} {3} {4}' -f $_.WorkingArea.X, $_.WorkingArea.Y, "
                        "$_.WorkingArea.Width, $_.WorkingArea.Height, [int]$_.Primary }"],
                       capture_output=True, text=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
    telas = [tuple(map(int, linha.split())) for linha in r.stdout.splitlines() if linha.strip()]
    deitadas = sorted((t for t in telas if t[2] > t[3]), key=lambda t: (-t[4], -t[2]))
    return (deitadas or telas or [(0, 0, 1280, 800, 1)])[0][:4]


def ouvir(indata, frames, tempo, status):
    global fundo, ultima_palma, ultima_abertura, pico_anterior
    try:
        audio_para_voz.put_nowait((indata[:, 0] * 32767).astype(np.int16).tobytes())
    except queue.Full:
        pass  # o reconhecimento ficou para trás: perder um pedaço é melhor que travar o áudio
    pico = float(np.abs(indata).max())
    agora = time.time()
    if "--medir" in sys.argv:
        print(f"volume {pico:.2f}  fundo {fundo:.3f}  " + "#" * int(pico * 60))
    palma = pico > AJUSTE["sensibilidade"] and pico > fundo * 6 and pico_anterior < pico * 0.6
    pico_anterior = pico
    if not palma:
        fundo = fundo * 0.98 + pico * 0.02  # só o que não é palma conta como fundo
        return
    intervalo = (agora - ultima_palma) * 1000
    if AJUSTE["intervalo_min_ms"] < intervalo < AJUSTE["intervalo_max_ms"]:
        ultima_palma = 0.0
        acordar("duas palmas: abrindo o Jarvis")
    elif intervalo > AJUSTE["intervalo_min_ms"]:
        ultima_palma = agora


if __name__ == "__main__":
    if sys.stdout is None:  # rodando escondido
        sys.stdout = sys.stderr = open(RAIZ / "palmas.log", "a", encoding="utf-8", buffering=1)
    print("Ouvindo palmas e o nome Jarvis… (Ctrl+C para sair)")
    threading.Thread(target=ouvir_o_nome, daemon=True).start()
    threading.Thread(target=falar_avisos, daemon=True).start()
    with sd.InputStream(channels=1, samplerate=TAXA, blocksize=BLOCO, callback=ouvir):
        while True:
            time.sleep(1)
