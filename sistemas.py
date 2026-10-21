"""Status dos sistemas dele e do PC.

Sistemas: confere se os sites respondem (a cada 5 min, em segundo plano; avisa quando um cai e quando volta) e,
quando ele pergunta do deploy, lê o último deploy de produção na Vercel CLI (demora ~15 s, por isso avisa antes).
PC: CPU, memória, disco e quem está pesando (psutil). A extensão mostra um mini-painel com /api/painel.
"""
import json
import re
import subprocess
import time
from pathlib import Path

import httpx
import psutil

RAIZ = Path(__file__).parent
CONFIG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
SITES = CONFIG.get("sites_monitorados") or {
    "Porthon (site)": "https://porthon.com.br",
    "Porthon (sistema)": "https://porthon-app-two.vercel.app",
    "Radar de Leads": "https://radar-7sevencode.vercel.app",
}
PASTA_PORTHON = Path.home() / "Desktop" / "Porthon-System" / "lobby"
DEMORA = True

STATUS = re.compile(r"\b(?:(?:t[aá]|est[aá])\s+(?:tudo\s+)?no\s+ar|fora\s+do\s+ar|caiu|ca[ií]ram|t[aá]\s+online|"
                    r"status\s+d[oa]s?\s+(?:sistemas?|sites?|servidores?)|como\s+(?:t[aá]o|est[aã]o)\s+(?:os\s+)?(?:meus\s+)?(?:sistemas|sites)|"
                    r"(?:meus\s+)?sistemas\s+(?:t[aã]o|est[aã]o)\s+(?:ok|bem|funcionando|no ar))\b", re.I)
DEPLOY = re.compile(r"\b(?:deploy|deploys|subiu|publicou|vers[aã]o\s+(?:no\s+ar|publicada))\b", re.I)
PC = re.compile(r"\b(?:(?:o\s+)?(?:pc|computador|m[aá]quina|note)\s+(?:t[aá]|est[aá])\s+(?:lento|travando|pesado|devagar|esquentando)|"
                r"(?:uso|consumo)\s+d[ae]\s+(?:cpu|mem[oó]ria|ram|processador|disco)|o\s+que\s+(?:t[aá]|est[aá])\s+(?:pesando|consumindo|travando)|"
                r"como\s+(?:t[aá]|est[aá])\s+o\s+(?:pc|computador)|status\s+do\s+(?:pc|computador)|quanto\s+de\s+(?:ram|mem[oó]ria))\b", re.I)

_ultimo = {}  # nome → {"ok": bool, "ms": int, "quando": ts}


def checar(nome, url):
    inicio = time.time()
    try:
        r = httpx.get(url, timeout=12, follow_redirects=True, headers={"User-Agent": "JarvisMonitor/1.0"})
        ok = r.status_code < 500
        codigo = r.status_code
    except Exception:
        ok, codigo = False, 0
    return {"ok": ok, "codigo": codigo, "ms": int((time.time() - inicio) * 1000), "quando": time.time()}


def vigiar():
    """[(fala, cartão)] quando algum site muda de estado (caiu / voltou). Chamado a cada 5 min pelo servidor."""
    avisos = []
    for nome, url in SITES.items():
        novo = checar(nome, url)
        antes = _ultimo.get(nome)
        _ultimo[nome] = novo
        if antes is None or antes["ok"] == novo["ok"]:
            continue
        if not novo["ok"]:
            avisos.append((f"Atenção, chefe: {nome} parece fora do ar.",
                           {"titulo": "Sistema fora do ar", "destaque": nome, "texto": url, "alerta": True}))
        else:
            avisos.append((f"{nome} voltou ao ar, chefe.", {"titulo": "Sistema", "destaque": f"{nome} no ar", "rapido": True}))
    return avisos


def ultimo_deploy():
    """(estado, idade, url) do último deploy de produção do Porthon pela Vercel CLI, ou None."""
    try:
        r = subprocess.run("vercel ls --prod --yes", shell=True, cwd=PASTA_PORTHON, capture_output=True, text=True,
                           timeout=60, encoding="utf-8", errors="replace", creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        return None
    for linha in (r.stdout + r.stderr).splitlines():
        m = re.match(r"\s*(\d+\w+)\s+\S+\s+(https://\S+)\s+●\s+(\w+)", linha)
        if m:
            return m.group(3), m.group(1), m.group(2)
    return None


IDADE = {"s": "segundos", "m": "minutos", "h": "horas", "d": "dias"}


def entender(texto):
    if re.match(r"^\s*(?:jarvis[ ,]*)?(?:fala|manda|avisa|diz|escreve|responde)\s+(?:pr[oa]|pro|para|a[oa]?)\b", texto, re.I):
        return None  # "fala pro Jesus que subi o deploy" é mensagem, não pergunta
    if PC.search(texto):
        return {"o_que": "pc"}
    if DEPLOY.search(texto) and re.search(r"porthon|deploy|subiu|vercel|sistema|site", texto, re.I):
        return {"o_que": "deploy"}
    if STATUS.search(texto):
        return {"o_que": "sites"}
    return None


def executar(p):
    if p["o_que"] == "pc":
        return pc_agora()
    if p["o_que"] == "deploy":
        d = ultimo_deploy()
        if not d:
            return "Não consegui falar com a Vercel agora, chefe.", []
        estado, idade, url = d
        n, un = re.match(r"(\d+)(\w)", idade).groups()
        traduz = {"Ready": "no ar e funcionando", "Error": "com ERRO", "Building": "ainda subindo", "Queued": "na fila",
                  "Canceled": "cancelado"}
        fala = f"O último deploy do Porthon em produção foi há {n} {IDADE.get(un, un)}, e tá {traduz.get(estado, estado)}."
        return fala, [{"titulo": "Deploy · Porthon", "destaque": estado, "texto": f"há {n} {IDADE.get(un, un)}\n{url}",
                       "rapido": estado == "Ready"}]
    resultados = {nome: checar(nome, url) for nome, url in SITES.items()}
    _ultimo.update(resultados)
    fora = [n for n, r in resultados.items() if not r["ok"]]
    linhas = [f"{'●' if r['ok'] else '✕'} {n} · {r['ms']} ms" + ("" if r["ok"] else f" (erro {r['codigo'] or 'sem resposta'})")
              for n, r in resultados.items()]
    if fora:
        fala = f"Tem problema, chefe: {', '.join(fora)} não {'respondem' if len(fora) > 1 else 'responde'}. O resto tá no ar."
    else:
        fala = f"Tudo no ar, chefe. Os {len(resultados)} sistemas responderam, o mais lento em {max(r['ms'] for r in resultados.values())} milissegundos."
    return fala, [{"titulo": "Sistemas", "destaque": "Tudo no ar" if not fora else f"{len(fora)} fora", "linhas": linhas,
                   "rapido": not fora}]


def numeros_do_pc():
    mem = psutil.virtual_memory()
    disco = psutil.disk_usage("C:\\")
    return {"cpu": psutil.cpu_percent(interval=None), "ram": mem.percent, "ram_gb": round(mem.used / 2**30, 1),
            "ram_total": round(mem.total / 2**30, 1), "disco": disco.percent}


def pc_agora():
    psutil.cpu_percent(interval=None)
    for p in psutil.process_iter():
        try:
            p.cpu_percent(None)
        except (psutil.Error, OSError):
            pass
    time.sleep(1.0)  # mede 1 s de uso de verdade
    n = numeros_do_pc()
    nucleos = psutil.cpu_count() or 1
    procs = []
    for p in psutil.process_iter(["name", "memory_info"]):
        try:
            procs.append((p.info["name"], p.cpu_percent(None) / nucleos, p.info["memory_info"].rss / 2**30))
        except (psutil.Error, OSError, AttributeError):
            pass
    # junta processos com o mesmo nome (o Chrome abre dezenas)
    juntos = {}
    for nome, cpu, ram in procs:
        if not nome or nome.lower() in ("system idle process", "idle"):
            continue
        c, r = juntos.get(nome, (0, 0))
        juntos[nome] = (c + cpu, r + ram)
    por_cpu = sorted(juntos.items(), key=lambda x: -x[1][0])[:4]
    por_ram = sorted(juntos.items(), key=lambda x: -x[1][1])[:4]
    culpado_cpu, culpado_ram = por_cpu[0], por_ram[0]
    fala = f"Processador em {n['cpu']:.0f}% e memória em {n['ram']:.0f}%, {n['ram_gb']} de {n['ram_total']} giga. "
    if n["cpu"] > 70:
        fala += f"Quem mais pesa no processador é o {culpado_cpu[0].replace('.exe', '')}. "
    if n["ram"] > 80:
        fala += f"Na memória, o {culpado_ram[0].replace('.exe', '')} tá usando {culpado_ram[1][1]:.1f} giga. "
    if n["cpu"] <= 70 and n["ram"] <= 80:
        fala += "Tá tudo tranquilo, chefe."
    linhas = [f"CPU {n['cpu']:.0f}% · RAM {n['ram']:.0f}% · Disco {n['disco']:.0f}%"] + \
             [f"{nome.replace('.exe', '')}: {cpu:.0f}% CPU · {ram:.1f} GB" for nome, (cpu, ram) in por_ram]
    return fala, [{"titulo": "PC", "destaque": f"CPU {n['cpu']:.0f}% · RAM {n['ram']:.0f}%", "linhas": linhas}]
