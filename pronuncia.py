"""Como as palavras SOAM na voz do Jarvis (edge-tts pt-BR lê inglês como se fosse português: "Ryzen" vira "rizen").

Só mexe no que vai pra voz; a legenda na tela continua com a grafia certa.
Pra ensinar uma palavra nova: ponha em FALAR (grafia → como soa) e rode `python pronuncia.py palavra`, que gera
o áudio, ouve de volta pelo Whisper e mostra o que saiu (dá pra ajustar a grafia até soar certo).
"""
import re

# grafia → como um brasileiro fala (a voz lê isso). Ordem: as mais compridas primeiro (o código ordena sozinho).
FALAR = {
    # processador / PC
    "Ryzen": "Ráizen", "Threadripper": "Trédripper", "threads": "trédis", "thread": "tréd", "Intel": "Íntel",
    "Core i3": "Côr ai três", "Core i5": "Côr ai cinco", "Core i7": "Côr ai sete", "Core i9": "Côr ai nove",
    "Radeon": "Radeôn", "NVIDIA": "Envídia", "Nvidia": "Envídia", "GeForce": "Djifórce", "RTX": "érre tê xis",
    "GTX": "gê tê xis", "AMD": "a eme dê", "CPU": "cê pê u", "GPU": "gê pê u", "APU": "a pê u", "SSD": "ésse ésse dê",
    "HDD": "agá dê dê", "NVMe": "ene vê eme é", "M.2": "eme dois", "SATA": "sáta", "DDR4": "dê dê érre quatro",
    "DDR5": "dê dê érre cinco", "XMP": "xis eme pê", "EXPO": "ékspo", "BIOS": "báios", "Kingston": "Kíngston",
    "Corsair": "Córsér", "HyperX": "Ráiper éks", "Samsung": "Sâmsung", "Western Digital": "Uéstern Dígital",
    "Gigabyte": "Gigabáite", "ASUS": "Ásus", "MSI": "eme ésse í", "ASRock": "Ás Róck", "cooler": "cúler",
    "clock": "clóc", "boost": "búst", "cache": "quéche", "overclock": "overclóc", "single channel": "síngou tchânel",
    "dual channel": "dual tchânel", "chipset": "tchipsét", "socket": "sóquet", "watts": "uóts", "benchmark": "bêntchmark",
    "GHz": "gigahertz", "MHz": "megahertz", "TB": "teras", "GB": "gigas", "MB": "megas", "KB": "kilobaites",
    "hardware": "rárduer", "software": "sóftuer", "firmware": "fírmuer", "driver": "dráiver", "drivers": "dráivers",
    "setup": "setáp", "gamer": "gueimer", "notebook": "nôtbuk", "desktop": "désktop",
    "Wi-Fi": "uái fái", "WiFi": "uái fái", "wifi": "uái fái", "Bluetooth": "Blutúf", "USB": "u ésse bê", "HDMI": "agá dê eme í",
    # programas, sites, empresas
    "Windows": "Uíndous", "Microsoft": "Máicrosoft", "Google": "Gúgou", "Chrome": "Crôume", "YouTube": "Iutúbi",
    "WhatsApp": "Uótsáp", "Spotify": "Spótifai", "Notion": "Nôuxon", "Vercel": "Vérsel", "Supabase": "Supabêis",
    "GitHub": "Guít Râb", "Git": "Guít", "Visual Studio Code": "Víjual Stúdio Côud", "VS Code": "vê ésse Côud",
    "Opera GX": "Ópera gê xis", "Edge": "Édj", "Firefox": "Fáierfóks", "Instagram": "Ínstagram", "Facebook": "Feicibúk",
    "LinkedIn": "Linkedín", "iPhone": "Aifôun", "A16 Bionic": "A dezesseis Baiônic", "Bionic": "Baiônic", "Dynamic Island": "Dainâmic Áilend", "OLED": "ó léd", "iOS": "ai ó és", "Apple": "Épou", "Street View": "Strít Viú", "Google Maps": "Gúgou Méps",
    "Maps": "Méps", "Claude": "Clôd", "Groq": "Grók", "Ollama": "Olama", "Gemini": "Djêmini", "OpenAI": "Ôupen ei ai",
    "ChatGPT": "Tchat gê pê tê", "Steam": "Stím", "Discord": "Díscord", "Telegram": "Telegrâm", "Canva": "Kânva",
    "Excel": "Écsel", "Word": "Uórd", "PowerPoint": "Páuer Póint", "PowerShell": "Páuer Xél", "Python": "Páiton",
    "JavaScript": "Javascrípt", "TypeScript": "Táipscrípt", "Next.js": "Nékst jêi ésse", "React": "Riéct",
    "Node": "Nôud", "Tailscale": "Têilsquêil", "Riot": "Ráiot", "Netflix": "Nétflics", "Amazon": "Ámazon",
    "Wikipédia": "Uikipédia", "Wikipedia": "Uikipédia", "LATAM": "Latâm",
    "JetSMART": "Djét Smárt", "Esri": "Ésri", "NASA": "Nása",
    # palavras do dia a dia dele
    "leads": "lídis", "lead": "líd", "deploy": "deplói", "commit": "comít", "commits": "comíts", "push": "púxi",
    "feedback": "fídbéc", "follow-up": "fálou áp", "landing page": "lêndin pêidj", "landing": "lêndin",
    "dashboard": "déxbórd", "login": "lóguin", "logout": "logáut", "online": "onláin", "offline": "ofláin",
    "download": "daunlôud", "upload": "aplôud", "email": "imêiu", "e-mail": "imêiu", "site": "sáite", "sites": "sáites",
    "app": "áp", "apps": "áps", "playlist": "pleilíst", "playlists": "pleilísts", "shuffle": "xâfou", "play": "plêi",
    "stand-by": "stêndbai", "pop-up": "pópáp", "pop-ups": "pópáps", "popup": "pópáp", "popups": "pópáps",
    "home office": "rôum ófis", "meeting": "mítin", "call": "cól", "briefing": "brífin", "pomodoro": "pomodoro",
    "Porthon": "Pórton", "Street": "Strít", "show": "xôu", "ok": "oquêi", "OK": "oquêi",
}
_ORDEM = sorted(FALAR, key=len, reverse=True)
_REGRA = re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(p) for p in _ORDEM) + r")(?![\w-])", re.I)
_EXATO = {p.lower(): FALAR[p] for p in _ORDEM}
_CASO = {p: FALAR[p] for p in _ORDEM}  # "OK" e "ok" iguais; "Git" ≠ "git"? igual também


def _troca(m):
    w = m.group(0)
    return _CASO.get(w) or _EXATO.get(w.lower(), w)


def falar(texto):
    """O texto do jeito que a voz deve ler."""
    t = re.sub(r"\b7\s*-?\s*(?:seven\s*code|sevencode|code)\b", "SevenCode", texto, flags=re.I)
    t = re.sub(r"\bseven\s*code\b", "SevenCode", t, flags=re.I)
    # "6 cores" = núcleos (em português "cores" é outra coisa); "5600GT" → "5600 GT" (letras soletradas)
    t = re.sub(r"\b(\d+)\s*(?:cores|core)\b", r"\1 núcleos", t, flags=re.I)
    t = re.sub(r"\b(\d{3,5})(G|GT|X|XT|X3D|K|KF|F|U|H|HX|S|Ti)\b", r"\1 \2", t)
    t = re.sub(r"\b(\d+(?:[.,]\d+)?)\s*(GHz|MHz|GB|TB|MB|KB)\b", lambda m: f"{m.group(1)} {m.group(2)}", t)
    t = re.sub(r"\b(GT|XT|X3D|HX|KF|Ti)\b", lambda m: " ".join({"G": "gê", "T": "tê", "X": "xis", "3": "três",
                                                                 "D": "dê", "H": "agá", "K": "cá", "F": "éfe",
                                                                 "i": "ai"}.get(c, c) for c in m.group(1)), t)
    t = re.sub(r"(\d)\.(\d)(?=\s*(?:GHz|MHz|GB|TB))", r"\1,\2", t)  # 3.6 GHz → 3,6 (a voz lê vírgula)
    t = _REGRA.sub(_troca, t)
    return re.sub(r"\b1 (giga|tera|mega)s\b", r"1 \1", t)  # "1 teras" → "1 tera"


if __name__ == "__main__":
    # python pronuncia.py "Ryzen 5 5600GT" → gera o áudio, transcreve pelo Whisper e mostra o que se ouve
    import asyncio, sys, json
    from pathlib import Path
    import edge_tts, httpx
    raiz = Path(__file__).parent
    cfg = json.loads((raiz / "config.json").read_text(encoding="utf-8"))
    chave = json.loads((raiz / "groq.json").read_text(encoding="utf-8"))["chave"]

    async def ouvir(frase):
        audio = b""
        async for parte in edge_tts.Communicate(falar(frase), cfg["voz"], rate=cfg["voz_velocidade"], pitch=cfg["voz_tom"]).stream():
            if parte["type"] == "audio":
                audio += parte["data"]
        r = httpx.post("https://api.groq.com/openai/v1/audio/transcriptions", headers={"Authorization": f"Bearer {chave}"},
                       files={"file": ("a.mp3", audio, "audio/mpeg")}, data={"model": "whisper-large-v3", "language": "pt"},
                       timeout=60)
        return r.json().get("text", r.text)

    for frase in sys.argv[1:]:
        print(f"{frase!r:40} voz lê: {falar(frase)!r:45} ouvido: {asyncio.run(ouvir(frase)).strip()!r}")
