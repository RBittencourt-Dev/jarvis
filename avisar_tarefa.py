"""Hook do Claude Code (evento Stop): quando o Claude termina de responder, faz o Jarvis avisar em voz alta.

O Rafael pediu (23/10/2026): "faz o Jarvis avisar sempre que você completar uma tarefa — tipo 'tarefa tal concluída'".

Como liga: um hook Stop no settings.json do Claude Code roda `python avisar_tarefa.py`. O Claude Code manda, pelo stdin,
um JSON com `transcript_path` (o .jsonl da conversa). Este script lê a ÚLTIMA fala do Claude, resume em poucas palavras
e faz POST em http://127.0.0.1:8765/api/aviso. O Jarvis fala (respeitando o Não perturbe). Se o Jarvis estiver desligado,
o POST falha em silêncio — nunca atrapalha o Claude Code.
"""
import json
import re
import sys
import urllib.request

PORTA = 8765
LIMITE_PALAVRAS = 14


def _ultima_fala_do_claude(caminho):
    """Lê o transcript (.jsonl) e devolve o texto da última mensagem do assistente."""
    texto = ""
    try:
        with open(caminho, encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    evento = json.loads(linha)
                except ValueError:
                    continue
                if evento.get("type") != "assistant":
                    continue
                conteudo = (evento.get("message") or {}).get("content")
                if isinstance(conteudo, str):
                    bloco = conteudo
                elif isinstance(conteudo, list):
                    bloco = " ".join(c.get("text", "") for c in conteudo
                                     if isinstance(c, dict) and c.get("type") == "text")
                else:
                    bloco = ""
                if bloco.strip():
                    texto = bloco.strip()  # fica com a última não-vazia
    except OSError:
        return ""
    return texto


# Saudações/fillers que o Claude costuma pôr no começo — pular pra chegar no que importa.
FILLER = re.compile(r"^(?:prontinho|pronto|feito|beleza|certo|ok|okay|isso|a[ií]|ent[aã]o|olha|bom|"
                    r"perfeito|show|t[aá]|tudo certo|conclu[ií]do|chefe|senhor)\b[\s,!.]*", re.I)


def _resumir(texto):
    """A primeira frase com conteúdo (sem saudação), sem markdown, curta — é o que vai ser falado."""
    if not texto:
        return ""
    t = re.sub(r"```.*?```", " ", texto, flags=re.S)     # tira blocos de código
    t = re.sub(r"https?://\S+", " ", t)                   # tira links
    t = re.sub(r"[`*_#>]+", " ", t)                        # tira marcação
    frases = [f.strip() for f in re.split(r"(?<=[.!?\n])\s", t) if f.strip()]
    escolhida = ""
    for f in frases:
        limpa = f
        while True:  # descasca saudações repetidas ("Pronto, chefe. ")
            nova = FILLER.sub("", limpa).strip(" ,.-:")
            if nova == limpa:
                break
            limpa = nova
        if len(limpa.split()) >= 3:  # primeira frase que realmente diz algo
            escolhida = limpa
            break
    if not escolhida:
        escolhida = FILLER.sub("", frases[0]).strip(" ,.-:") if frases else ""
    palavras = escolhida.split()
    if len(palavras) > LIMITE_PALAVRAS:
        escolhida = " ".join(palavras[:LIMITE_PALAVRAS]) + "…"
    return escolhida.strip(" .:-")


def main():
    try:
        entrada = json.load(sys.stdin)
    except (ValueError, OSError):
        entrada = {}
    caminho = entrada.get("transcript_path")
    resumo = _resumir(_ultima_fala_do_claude(caminho)) if caminho else ""
    fala = f"Tarefa concluída, chefe. {resumo}" if resumo else "Tarefa concluída, chefe."
    dados = json.dumps({"texto": fala}).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{PORTA}/api/aviso", data=dados,
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=3).read()
    except Exception:
        pass  # Jarvis desligado ou ocupado: não é problema do Claude Code
    sys.exit(0)


if __name__ == "__main__":
    main()
