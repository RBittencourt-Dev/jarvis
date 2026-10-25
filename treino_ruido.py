"""Treino RIGOROSO de autocorreção (25/10): o Jarvis tem que acertar mesmo quando a voz chega torta.

O treino.py confere frases escritas certinhas. Este GERA centenas de variações do jeito que o reconhecimento
de voz estraga a fala do Rafael e confere se o caminho continua certo:
  - o nome do programa escrito como soa ("vs cold", "crômi", "spotifai", "stim", "nóchon", "écsel")
  - jeitos de pedir em português e em inglês ("abre", "abra", "tu pode abrir", "open", "can you open")
  - enfeites gaúchos e o "jarvis" no começo/fim ("bah, abre o X aí", "abre o X, jarvis")
  - comandos de música/volume/hora em inglês e português
E também confere o contrário: frase que NÃO pode virar outra coisa (conversa normal não abre programa).

    python treino_ruido.py        mostra só o que falhou e a nota final
    python treino_ruido.py -v     mostra tudo

Falhou algo? Conserte em autocorrecao.py (som), bilingue.py (inglês) ou sinonimos.py (jeito de pedir) e rode de novo.
"""
import itertools
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# programa → (jeitos que a voz escreve, o que tem que aparecer na rota)
PROGRAMAS = [
    (["vs code", "vs cold", "vscold", "vs coud", "vê esse code", "vê esse cold", "bs code", "visual studio cold",
      "vs côde", "vscode"], "visual studio code"),
    (["chrome", "crome", "crômi", "crôme", "crôume", "google crome", "gugou crome"], "google chrome"),
    (["spotify", "spotifai", "spotfai", "spotifái", "spótifai", "espotifai"], "spotify"),
    (["steam", "stim", "stíme", "estim"], "steam"),
    (["notion", "nóchon", "nouchon", "nôuxon", "noxon"], "notion"),
    (["excel", "écsel", "ecsel", "éksel", "exel"], "excel"),
    (["capcut", "capicut", "capcat", "kepcut", "cap cut"], "capcut"),
    (["photoshop", "fotoshop", "fotochop", "fotoxop"], "photoshop"),
    (["whatsapp", "uatsap", "uatsapp", "zap", "zapzap", "whats"], "whatsapp"),
    (["opera", "ópera", "opera gx"], "opera"),
    (["powerpoint", "pauerpoint", "pauer point", "power point"], "powerpoint"),
    (["onenote", "uan note", "one note"], "onenote"),
    (["anydesk", "ani desk", "enidesk"], "anydesk"),
    (["teamviewer", "tim viewer", "time viewer", "timviuer"], "teamviewer"),
    (["calculadora", "calculator"], "calcula"),
    (["explorador de arquivos", "file explorer", "explorador"], "file explorer"),
]

PEDIR = [  # {x} = o nome do programa como a voz escreveu
    "abre o {x}", "abre {x}", "abra o {x}", "abrir o {x}", "jarvis, abre o {x}", "bah, abre o {x} aí",
    "tu pode abrir o {x}", "abre o {x} pra mim", "abre o {x}, jarvis", "open {x}", "jarvis, can you open {x} please",
]

# comandos que não são "abrir": (frase, o que tem que aparecer na rota)
COMANDOS = [
    ("next song", "midia próxima"), ("play next song", "midia próxima"), ("skip", "midia próxima"),
    ("skip this song", "midia próxima"), ("passa a música", "midia próxima"), ("próxima música", "midia próxima"),
    ("pause the music", "midia paus"), ("pause", "midia paus"), ("pausa a música", "midia paus"),
    ("previous song", "midia voltando"), ("música anterior", "midia voltando"),
    ("resume the music", "midia continuando"), ("continua a música", "midia continuando"),
    ("turn up the volume", "volume aumentado"), ("volume up", "volume aumentado"), ("aumenta o volume", "volume aumentado"),
    ("turn down the volume", "volume diminu"), ("abaixa o volume", "volume diminu"),
    ("what time is it", "hora"), ("what's the time", "hora"), ("que horas são", "hora"),
    ("search for bmw x1", "pesquisa bmw x1"), ("search bmw x1 on opera", "pesquisa bmw x1 no opera"),
    ("pesquisa bmw x1", "pesquisa bmw x1"), ("look up cadeira gamer", "pesquisa cadeira gamer"),
    ("show me the news", "noticias"), ("me mostra as notícias", "noticias"),
    ("close spotify", "fechar spotify"), ("fecha o spotify", "fechar spotify"),
    ("minimize spotify", "minimiz"), ("lock the screen", "bloque"), ("bloqueia a tela", "bloque"),
    ("play legião urbana", "tocar legião urbana"), ("toca legião urbana", "tocar legião urbana"),
    ("jarvis, what time is it", "hora"), ("thank you jarvis", "de nada"), ("thanks", "de nada"),
]

# frases que NÃO podem virar abrir/pesquisar (conversa ou pergunta vai pro cérebro)
NAO_PODE = [
    ("how are you jarvis", "abrir|pesquisa"), ("o que tu acha da landing do porthon", "abrir"),
    ("show de bola", "abrir|mostra"), ("me explica o que é uma vlan", "abrir"),
    ("abre o portão da garagem", "abrir porthon"), ("tô pensando em abrir uma empresa", "abrir"),
    ("what is the best programming language", "abrir"), ("can you explain javascript promises", "abrir"),
]


def rodar(verboso=False):
    import server
    casos, erros = 0, []
    for (falas, esperado), modelo in itertools.product(PROGRAMAS, PEDIR):
        for x in falas:
            frase = modelo.format(x=x)
            rota = server.rota_de(frase)
            casos += 1
            ok = rota.lower().startswith("abrir") and esperado in rota.lower()
            if not ok:
                erros.append((frase, rota, esperado))
            elif verboso:
                print(f"ok    {frase:45} → {rota}")
    for frase, esperado in COMANDOS:
        rota = server.rota_de(frase)
        casos += 1
        ok = any(e in rota.lower() for e in esperado.split("|"))
        if not ok:
            erros.append((frase, rota, esperado))
        elif verboso:
            print(f"ok    {frase:45} → {rota}")
    for frase, proibido in NAO_PODE:
        rota = server.rota_de(frase)
        casos += 1
        ok = not any(rota.lower().startswith(p) for p in proibido.split("|"))
        if not ok:
            erros.append((frase, rota, f"NÃO {proibido}"))
        elif verboso:
            print(f"ok    {frase:45} → {rota}")
    for frase, rota, esperado in erros:
        print(f"ERRO  {frase:45} → {rota}   (esperado: {esperado})")
    print(f"\n{casos - len(erros)}/{casos} certas ({(casos - len(erros)) / casos:.1%})")
    return len(erros)


if __name__ == "__main__":
    sys.exit(1 if rodar("-v" in sys.argv) else 0)
