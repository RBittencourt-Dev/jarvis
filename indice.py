"""Índice dos documentos e projetos dele (RAG local): "o que tem no meu projeto X sobre Y?".

Por que SQLite FTS5 (busca por texto com ranking BM25) e não banco vetorial: sem GPU, gerar embeddings de
milhares de arquivos levaria horas no CPU e o modelo de embedding ocuparia RAM o tempo todo. O FTS5 indexa
tudo em minutos, responde em milissegundos e entende palavras sem acento. A busca por sentido fica com o
cérebro: ele reformula a pergunta em palavras-chave antes de procurar (está na descrição da ferramenta).

- Pastas: config "pastas_indexadas" (padrão: Documentos e Área de trabalho). Pula node_modules, .git, build,
  arquivos de senha (.env, chaves) e o que passar de 400 KB.
- Atualiza em segundo plano a cada 30 min, só o que mudou (data de modificação).
- Fica em dados/indice.db.
"""
import json
import os
import re
import sqlite3
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).parent
CONFIG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
BANCO = RAIZ / "dados" / "indice.db"
PASTAS = CONFIG.get("pastas_indexadas") or [str(Path.home() / "Documents"), str(Path.home() / "Desktop")]
EXTENSOES = {".md", ".txt", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".html", ".css", ".sql", ".csv", ".yml",
             ".yaml", ".toml", ".ini", ".ps1", ".bat", ".sh", ".java", ".c", ".cpp", ".cs", ".go", ".rs", ".php", ".rb",
             ".vue", ".svelte", ".xml", ".env.example", ".docx", ".pdf"}
PULAR_PASTAS = {"node_modules", ".git", ".next", ".venv", "venv", "__pycache__", "dist", "build", ".vercel", ".turbo",
                "coverage", ".cache", "voz-guardada", "dados", "modelos", "vendor", "_arquivo", "Jarvis-backup-2026-10-21"}
PROIBIDOS = [x.lower() for x in CONFIG.get("arquivos_proibidos", [])] + [
    "groq.json", "gemini.json", "spotify-token.json", "spotify.json", "login-painel.json", "login-porthon.json",
    "rosto.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "cofre.bin"]
TAMANHO_MAX = 400_000
PEDACO = 1400
_trava = threading.Lock()
_estado = {"indexando": False, "arquivos": 0, "ultima": 0.0}


def _conexao():
    BANCO.parent.mkdir(exist_ok=True)
    c = sqlite3.connect(BANCO, check_same_thread=False)
    c.execute("CREATE TABLE IF NOT EXISTS arquivos (caminho TEXT PRIMARY KEY, mtime REAL)")
    c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS pedacos USING fts5(caminho UNINDEXED, nome, texto, "
              "tokenize = 'unicode61 remove_diacritics 2')")
    return c


def _proibido(p: Path):
    nome = p.name.lower()
    return nome.startswith(".env") and not nome.endswith(".example") or any(nome == x or nome.endswith(x) for x in PROIBIDOS)


def _ler(p: Path):
    ext = p.suffix.lower()
    if ext == ".docx":
        import zipfile
        with zipfile.ZipFile(p) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xml.replace("</w:p>", "\n")))
    if ext == ".pdf":
        return ""  # sem leitor de PDF instalado; o nome do arquivo ainda entra no índice
    return p.read_text(encoding="utf-8", errors="replace")


def _pedacos(texto):
    linhas, atual = [], ""
    for linha in texto.splitlines():
        if len(atual) + len(linha) > PEDACO and atual:
            linhas.append(atual)
            atual = ""
        atual += linha + "\n"
    if atual.strip():
        linhas.append(atual)
    return linhas[:60]  # arquivo enorme: os primeiros 60 pedaços bastam


def atualizar():
    """Varre as pastas e indexa o que é novo ou mudou. Pode demorar alguns minutos na primeira vez."""
    if _estado["indexando"]:
        return
    _estado["indexando"] = True
    try:
        c = _conexao()
        conhecidos = dict(c.execute("SELECT caminho, mtime FROM arquivos"))
        vistos = set()
        for pasta in PASTAS:
            for raiz, dirs, arquivos in os.walk(pasta):
                dirs[:] = [d for d in dirs if d not in PULAR_PASTAS and not d.startswith(".")]
                for nome in arquivos:
                    p = Path(raiz) / nome
                    if p.suffix.lower() not in EXTENSOES or _proibido(p):
                        continue
                    try:
                        st = p.stat()
                    except OSError:
                        continue
                    if st.st_size > TAMANHO_MAX:
                        continue
                    chave = str(p)
                    vistos.add(chave)
                    if conhecidos.get(chave) == st.st_mtime:
                        continue
                    try:
                        texto = _ler(p)
                    except Exception:
                        continue
                    with _trava:
                        c.execute("DELETE FROM pedacos WHERE caminho = ?", (chave,))
                        c.executemany("INSERT INTO pedacos (caminho, nome, texto) VALUES (?, ?, ?)",
                                      [(chave, f"{p.parent.name}/{p.name}", t) for t in (_pedacos(texto) or [""])])
                        c.execute("INSERT OR REPLACE INTO arquivos VALUES (?, ?)", (chave, st.st_mtime))
                    if len(vistos) % 200 == 0:
                        c.commit()
        with _trava:
            for chave in set(conhecidos) - vistos:  # apagados ou movidos
                c.execute("DELETE FROM pedacos WHERE caminho = ?", (chave,))
                c.execute("DELETE FROM arquivos WHERE caminho = ?", (chave,))
            c.commit()
        _estado["arquivos"] = len(vistos)
        _estado["ultima"] = time.time()
        c.close()
    finally:
        _estado["indexando"] = False


def manter_em_dia():
    def laco():
        time.sleep(40)  # deixa o Jarvis ligar primeiro
        while True:
            try:
                atualizar()
            except Exception as e:
                print("índice falhou:", e)
            time.sleep(1800)
    threading.Thread(target=laco, daemon=True).start()


def _consulta_fts(texto):
    palavras = [p for p in re.findall(r"\w+", texto.lower()) if len(p) > 2]
    if not palavras:
        return None
    return " OR ".join(f'"{p}"*' for p in palavras[:12])


def procurar(consulta: str, limite: int = 6):
    q = _consulta_fts(consulta)
    if not q or not BANCO.exists():
        return []
    c = _conexao()
    try:
        linhas = c.execute(
            "SELECT caminho, nome, snippet(pedacos, 2, '«', '»', ' … ', 40), bm25(pedacos, 0, 4.0, 1.0) AS r "
            "FROM pedacos WHERE pedacos MATCH ? ORDER BY r LIMIT ?", (q, limite * 3)).fetchall()
    finally:
        c.close()
    vistos, saida = set(), []
    for caminho, nome, trecho, _ in linhas:
        if caminho in vistos:
            continue
        vistos.add(caminho)
        saida.append({"caminho": caminho, "nome": nome, "trecho": trecho})
        if len(saida) >= limite:
            break
    return saida


def procurar_nos_meus_arquivos(consulta: str):
    """Ferramenta do cérebro."""
    achados = procurar(consulta)
    if not achados:
        estado = " (ainda indexando, tenta de novo daqui a pouco)" if _estado["indexando"] else ""
        return f"Nada nos arquivos dele sobre isso{estado}."
    return "\n\n".join(f"[{a['caminho']}]\n{a['trecho']}" for a in achados) + \
        "\n\n(Pra ler um arquivo inteiro, use ler_arquivo com o caminho.)"


def situacao():
    n = 0
    if BANCO.exists():
        c = _conexao()
        n = c.execute("SELECT count(*) FROM arquivos").fetchone()[0]
        c.close()
    return {"arquivos": n, "indexando": _estado["indexando"], "ultima": _estado["ultima"], "pastas": PASTAS}
