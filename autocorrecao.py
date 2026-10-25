"""Autocorreção pelo SOM: o Jarvis acerta o que o reconhecimento de voz escreveu torto, SEM perguntar.

Pedido dele (25/10): "falei abre o vscode e ele entendeu cold… ele tem que entender essas coisas e se autocorrigir".
O Chrome em português escreve o inglês do jeito que soa: "VS Code" vira "vs cold", "Spotify" vira "spotifai",
"Chrome" vira "crome"/"crômi", "Steam" vira "stim", "Notion" vira "nóchon", "Excel" vira "écsel", "Word" vira "uórd".

Como funciona:
1. chave_sonora() reduz a palavra ao SOM, juntando o que soa igual pra um brasileiro
   (ph=f, th=t, w=u, y=i, ea/ee=i, c antes de e/i = s, l no fim da sílaba = u, "tion"="xon", vogal final some…).
   "vs cold" e "vs code" viram a mesma chave; "crômi" e "chrome" também.
2. melhor() compara a chave do que ele falou com a chave de cada nome conhecido (programas do PC, sites,
   apelidos) e devolve o mais parecido — só se for parecido DE VERDADE (nota alta e com folga pro 2º lugar).
   Nome comprido ("adobe photoshop 2026") também é comparado por pedaços ("photoshop").
3. Na dúvida, NÃO troca: aí segue o caminho de sempre (cérebro, "não achei").

Errou? Ele diz "errado" / "não era isso" e o server desfaz o que foi aprendido (ver server.ultima_autocorrecao).
Pra ensinar um som novo: acrescente em TROCAS e um caso no treino_ruido.py.
"""
import difflib
import re
import unicodedata

# palavras que não mudam o nome do programa: "adobe photoshop 2026" ≈ "photoshop"
RUIDO = {"o", "a", "os", "as", "do", "da", "de", "app", "aplicativo", "programa", "site", "adobe", "microsoft",
         "browser", "desktop", "the", "classic", "new", "atalho"}

# som em inglês (ou escrito à brasileira) → um jeito só. A ordem importa: as mais compridas primeiro.
TROCAS = [
    # x: em português "x" soa "ch" (fotoxop = photoshop); só o "xc"/"cs" do inglês ("excel" = "écsel") soa "ks"
    ("xc", "ks"), ("cs", "ks"), ("ex", "eks"), ("any", "eni"), ("tion", "xon"), ("sion", "xon"), ("chr", "kr"), ("sch", "sk"),
    ("ch", "x"), ("sh", "x"), ("ph", "f"),
    ("th", "t"), ("ck", "k"), ("qu", "k"), ("gh", "g"), ("ee", "i"), ("ea", "i"), ("ie", "i"), ("oo", "u"),
    ("ou", "o"), ("au", "o"), ("ow", "o"), ("ay", "ei"), ("ai", "ei"), ("ey", "ei"), ("w", "u"), ("y", "i"),
    ("z", "s"), ("ç", "s"), ("h", ""),
]


def sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


# siglas faladas letra por letra: "vê esse code" = "VS Code"
LETRAS = [(r"\bv[eê]\s*-?\s*[eé]ss?e\b", "vs"), (r"\bg[eê]\s*t[eê]\s*a\b", "gta"), (r"\bp[eê]\s*d[eê]\s*[eé]fe\b", "pdf"),
          # números em inglês do jeito que soam: "uan note" = OneNote, "tu" fica (é português demais)
          (r"\bu[aã]n\b", "one"),
          # "e" antes de s+consoante no começo é sotaque ("estim" = steam, "espotifai" = spotify)
          (r"\be(?=s[ptkcm])", "")]


def chave_sonora(texto):
    """"vs cold" → "vskod"; "chrome" → "krom"; "spotifai" → "spotifei" ≈ "spotify" → "spotifi"."""
    texto = texto or ""
    for regra, troca in LETRAS:
        texto = re.sub(regra, troca, texto, flags=re.I)
    palavras = [p for p in re.findall(r"[a-z0-9]+", sem_acento(texto)) if p not in RUIDO and not p.isdigit()]
    saida = []
    for p in palavras:
        for de, para in TROCAS:
            p = p.replace(de, para)
        p = re.sub(r"c(?=[ei])", "s", p)        # "excel" → "eksel" (c antes de e/i soa s)
        p = p.replace("c", "k")                  # o resto do c soa k ("code" = "kode")
        p = re.sub(r"l(?=[^aeiou]|$)", "u", p)   # "cold" soa "coud" (gaúcho/brasileiro fala o l como u)
        p = p.replace("ou", "o").replace("b", "v") if len(p) > 3 else p.replace("ou", "o")  # "bs code" ≈ "vs code"
        p = re.sub(r"(.)\1+", r"\1", p)          # letra dobrada soa como uma
        p = re.sub(r"(?<=[a-z]{3})ei$", "i", p)  # "-fy"/"-fai" no fim: "spotifai" = "spotify"
        if len(p) > 3:
            p = re.sub(r"[aeiou]$", "", p)       # vogal final quase não soa: "crômi" = "chrome" = "krom"
        saida.append(p)
    return "".join(saida)


def nota(dito, nome):
    """0 a 1: o quanto 'dito' SOA como 'nome' (também comparando com pedaços do nome)."""
    a = chave_sonora(dito)
    if len(a) < 3:
        return 0.0
    palavras = [p for p in re.findall(r"[a-z0-9]+", sem_acento(nome)) if p not in RUIDO and not p.isdigit()]
    pedacos = {" ".join(palavras)}
    for i in range(len(palavras)):  # "visual studio code" → também "studio code", "code"…
        for j in range(i + 1, len(palavras) + 1):
            pedacos.add(" ".join(palavras[i:j]))
    melhor = 0.0
    for pedaco in pedacos:
        b = chave_sonora(pedaco)
        if len(b) < 3:
            continue
        r = difflib.SequenceMatcher(None, a, b).ratio()
        if pedaco != " ".join(palavras):
            r -= 0.04  # bater só num pedaço do nome vale um pouco menos que o nome inteiro
        melhor = max(melhor, r)
    return melhor


def melhor(dito, nomes, minimo=0.8, folga=0.06):
    """O nome conhecido que soa como o que ele disse, ou None se não tiver certeza.

    Certeza = nota ≥ mínimo E o 2º colocado (de OUTRO alvo) bem atrás — senão é chute e o Jarvis não troca."""
    if not dito or len(chave_sonora(dito)) < 3:
        return None
    notas = sorted(((nota(dito, n), n) for n in set(nomes) if n), reverse=True)
    if not notas or notas[0][0] < minimo:
        return None
    primeiro = notas[0]

    def _palavras(n):
        return set(re.findall(r"[a-z0-9]+", sem_acento(n))) - RUIDO

    def _mesmo_alvo(n):  # "spotify web" e "uninstall anydesk" são o mesmo nome com sobra: não são concorrentes
        a, b = _palavras(primeiro[1]), _palavras(n)
        return chave_sonora(n) == chave_sonora(primeiro[1]) or a <= b or b <= a

    segundo = next((n for n in notas[1:] if not _mesmo_alvo(n[1])), (0.0, ""))
    if primeiro[0] < 0.92 and primeiro[0] - segundo[0] < folga:
        return None  # dois nomes quase iguais: melhor não adivinhar
    return primeiro[1]


if __name__ == "__main__":
    # python autocorrecao.py "vs cold" "crômi"  → mostra a chave e o melhor nome entre alguns de exemplo
    import sys
    exemplos = ["visual studio code", "vs code", "google chrome", "spotify", "steam", "notion", "excel", "word",
                "adobe photoshop 2026", "canva", "whatsapp", "capcut", "opera gx browser", "discord", "paint"]
    for frase in sys.argv[1:]:
        print(f"{frase!r:25} chave={chave_sonora(frase)!r:15} → {melhor(frase, exemplos)}")
