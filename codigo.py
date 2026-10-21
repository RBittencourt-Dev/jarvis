"""Programação: rodar código numa pasta isolada, git dos projetos dele e editar arquivo com aprovação.

- rodar_codigo: Python, JavaScript (Node) ou PowerShell numa pasta temporária própria (dados/sandbox/<id>),
  com tempo limite de 60 s. NÃO é uma máquina virtual: o código roda com o usuário dele. Por isso o servidor
  pede o "sim" quando o código mexe em arquivo fora da pasta, apaga, instala ou manda dado pra fora (PERIGOSO).
- git: status, diff, log, branch e show rodam direto (só leitura). commit/push/pull/checkout pedem o "sim".
- editar_arquivo: troca um trecho exato por outro. Sempre pede o "sim" mostrando o antes/depois.
Todo código e resultado aparece na tela num painel com realce de sintaxe (highlight.js, local).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import extensao
import registro

RAIZ = Path(__file__).parent
CONFIG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
SANDBOX = RAIZ / "dados" / "sandbox"
LINGUAGENS = {".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "typescript", ".jsx": "javascript",
              ".json": "json", ".html": "xml", ".css": "css", ".sql": "sql", ".ps1": "powershell", ".md": "markdown",
              ".bat": "dos", ".sh": "bash", ".yml": "yaml", ".yaml": "yaml"}

# código que sai da pasta isolada, apaga, instala ou manda dado pra fora: o servidor pede o "sim" antes
PERIGOSO = re.compile(
    r"\b(os\.remove|os\.unlink|os\.rmdir|shutil\.rmtree|shutil\.move|unlink\(|rmdir|rmSync|unlinkSync|fs\.rm|"
    r"remove-item|del\s|rm\s+-|format|shutdown|subprocess|os\.system|child_process|exec\(|eval\(|"
    r"pip\s+install|npm\s+i|npm\s+install|winget|choco|requests\.(?:post|put|delete)|httpx\.(?:post|put|delete)|"
    r"fetch\([^)]*method\s*:\s*['\"](?:POST|PUT|DELETE)|smtplib|Send-MailMessage|Invoke-(?:WebRequest|RestMethod)|"
    r"open\([^)]*['\"][wa]b?['\"]|writeFile|set-content|out-file|reg\s+(?:add|delete)|[A-Za-z]:\\\\)", re.I)


def precisa_autorizar(linguagem, codigo_fonte):
    return bool(PERIGOSO.search(codigo_fonte or ""))


def _mostrar(titulo, destaque, codigo_fonte, linguagem, saida=None, erro=False):
    cartao = {"titulo": titulo, "destaque": destaque, "codigo": codigo_fonte[:8000], "linguagem": linguagem, "rapido": False}
    if saida is not None:
        cartao["saida"] = saida[:6000]
        cartao["erro"] = erro
    try:
        extensao.publicar_cartao(cartao)
    except Exception:
        pass


def rodar_codigo(linguagem: str, codigo: str):
    """Roda o código e devolve a saída (stdout + stderr) e o código de saída."""
    lang = (linguagem or "python").lower()
    pasta = SANDBOX / uuid.uuid4().hex[:8]
    pasta.mkdir(parents=True, exist_ok=True)
    if lang.startswith("py"):
        arquivo, cmd, nome = pasta / "main.py", [sys.executable, "-I", "main.py"], "python"
    elif lang in ("js", "javascript", "node"):
        node = shutil.which("node")
        if not node:
            return "Node não está instalado nesse PC."
        arquivo, cmd, nome = pasta / "main.js", [node, "main.js"], "javascript"
    elif lang in ("powershell", "ps", "ps1"):
        arquivo, cmd, nome = pasta / "main.ps1", ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "main.ps1"], "powershell"
    else:
        return f"Linguagem {linguagem} ainda não: uso python, javascript ou powershell."
    arquivo.write_text(codigo, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not re.search(r"KEY|TOKEN|SECRET|SENHA|PASSWORD", k, re.I)}
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        r = subprocess.run(cmd, cwd=pasta, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=60, env=env)
        saida = (r.stdout + ("\n" + r.stderr if r.stderr else "")).strip() or "(sem saída)"
        codigo_saida = r.returncode
    except subprocess.TimeoutExpired:
        saida, codigo_saida = "Passou de 60 s: parei.", -1
    _mostrar("Código rodado", nome, codigo, nome, saida, codigo_saida != 0)
    registro.anotar(f"rodar {nome}", saida[:200], ["rodar_codigo"], tipo="acao")
    return f"{saida[:4000]}\n[código de saída {codigo_saida}] (pasta: {pasta})"


# ------------------------------------------------------------------ git

GIT_LEITURA = {"status", "diff", "log", "branch", "show", "remote", "blame", "shortlog", "rev-parse", "ls-files"}
GIT_ESCRITA = {"add", "commit", "push", "pull", "checkout", "switch", "merge", "rebase", "reset", "stash", "restore",
               "tag", "fetch", "init", "clone", "revert", "cherry-pick"}


def _repo(pasta):
    p = Path(os.path.expandvars(pasta or "")).expanduser()
    if not p.is_absolute():
        p = Path.home() / "Desktop" / p
    return p.resolve()


def git_precisa_autorizar(argumentos):
    sub = (argumentos or "").split()[:1]
    return not sub or sub[0] not in GIT_LEITURA


def git(pasta: str, argumentos: str):
    """Roda `git <argumentos>` no projeto. Leitura vai direto; o resto o servidor confirma antes."""
    repo = _repo(pasta)
    if not (repo / ".git").exists() and not argumentos.startswith(("init", "clone")):
        return f"{repo} não é um repositório git."
    sub = argumentos.split()[:1]
    if sub and sub[0] not in GIT_LEITURA | GIT_ESCRITA:
        return f"Comando git '{sub[0]}' não liberado."
    r = subprocess.run(f'git -C "{repo}" {argumentos}', capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120, shell=True)
    saida = (r.stdout + ("\n" + r.stderr if r.stderr else "")).strip() or "(sem saída)"
    if sub and sub[0] in ("diff", "show"):
        _mostrar("Git", f"{repo.name} · git {argumentos[:40]}", saida, "diff")
    if sub and sub[0] in GIT_ESCRITA:
        registro.anotar(f"git {argumentos} em {repo.name}", saida[:200], ["git"], tipo="acao")
    return saida[:6000]


# ------------------------------------------------------------------ editar arquivo (sempre com o "sim")

def editar_arquivo(caminho: str, trecho_antigo: str, trecho_novo: str):
    import controle_pc
    p = controle_pc._permitido(caminho)
    if not p.exists():
        return f"Não achei {p}."
    texto = p.read_text(encoding="utf-8")
    n = texto.count(trecho_antigo)
    if n == 0:
        return "O trecho antigo não está no arquivo (confira espaços e quebras de linha)."
    if n > 1:
        return f"O trecho aparece {n} vezes; mande um pedaço maior pra eu saber qual."
    backup = RAIZ / "dados" / "backups" / f"{p.name}.{uuid.uuid4().hex[:6]}.bak"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, backup)
    p.write_text(texto.replace(trecho_antigo, trecho_novo, 1), encoding="utf-8")
    registro.anotar(f"editar {p}", "feito", ["editar_arquivo"], desfazer={"tipo": "mover", "de": str(p), "para": str(backup)},
                    tipo="acao")
    _mostrar("Arquivo editado", p.name, trecho_novo, LINGUAGENS.get(p.suffix.lower(), "plaintext"))
    return f"Editei {p}. (Backup guardado; 'desfaz isso' volta.)"


def mostrar_codigo(titulo: str, codigo: str, linguagem: str = "plaintext"):
    """Mostra código ou texto técnico num painel com realce de sintaxe (sem rodar)."""
    _mostrar(titulo or "Código", linguagem, codigo, linguagem)
    return "Mostrei o código na tela."
