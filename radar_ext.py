"""O Jarvis usando a extensão do Radar de Leads (7code-radar-leads/extensao), sem mexer no projeto do Radar.

Como: o Chrome das janelas do Jarvis (perfil .perfil-navegador) abre com depuração LOCAL (porta 9230, só
127.0.0.1). Com a extensão instalada nesse perfil (uma vez: "Carregar sem compactação"), o Jarvis abre a página do
painel da extensão numa aba e, por ela, faz o mesmo que os botões fazem: iniciar/parar a varredura do Google Maps e
ler o progresso e os leads (chrome.storage). A aba do Maps trabalhando aparece na tela; o progresso vai pro HUD.

Por que não "--load-extension": o Chrome 137+ ignora essa opção (testado no 155). Por isso a instalação é manual, uma
vez, e o Jarvis guia (abre chrome://extensions e copia o caminho da pasta).
"""
import json
import re
import time
import unicodedata
from pathlib import Path

import httpx

RAIZ = Path(__file__).parent
PORTA = 9230
PASTA_EXT = Path.home() / "Desktop" / "7code-radar-leads" / "extensao"
ARQUIVO = RAIZ / "dados" / "radar.json"
PERFIL = RAIZ / ".perfil-navegador"


def _sa(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def disponivel():
    return PASTA_EXT.exists()


def _alvos():
    try:
        return httpx.get(f"http://127.0.0.1:{PORTA}/json/list", timeout=3).json()
    except Exception:
        return None


def _id_da_extensao():
    """Acha o id da extensão do Radar instalada no perfil do Jarvis (pelas preferências do perfil)."""
    try:
        guardado = json.loads(ARQUIVO.read_text(encoding="utf-8")).get("id")
    except (OSError, ValueError):
        guardado = None
    pasta = str(PASTA_EXT.resolve()).lower()
    for arquivo in ("Secure Preferences", "Preferences"):
        try:
            prefs = json.loads((PERFIL / "Default" / arquivo).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for eid, dados in ((prefs.get("extensions") or {}).get("settings") or {}).items():
            if str(dados.get("path", "")).lower() == pasta:
                ARQUIVO.parent.mkdir(exist_ok=True)
                ARQUIVO.write_text(json.dumps({"id": eid}), encoding="utf-8")
                return eid
    return guardado


def situacao():
    """'sem_extensao' (pasta não existe neste PC) | 'sem_depuracao' (Jarvis aberto sem a porta) | 'nao_instalada' | 'ok'."""
    if not disponivel():
        return "sem_extensao"
    if _alvos() is None:
        return "sem_depuracao"
    return "ok" if _id_da_extensao() else "nao_instalada"


def guiar_instalacao():
    """Abre chrome://extensions no navegador do Jarvis e copia o caminho da pasta pra ele colar."""
    import subprocess
    subprocess.run(["powershell", "-NoProfile", "-Command", "$input | Set-Clipboard"], input=str(PASTA_EXT), text=True,
                   encoding="utf-8", timeout=10)
    try:
        httpx.put(f"http://127.0.0.1:{PORTA}/json/new?chrome://extensions/", timeout=5)
    except Exception:
        pass
    return (f"Pra eu usar o Radar, instala ele uma vez no meu navegador: abri a página de extensões. Liga o Modo do "
            f"desenvolvedor, clica em Carregar sem compactação e cola o caminho que já deixei copiado.")


# ------------------------------------------------------------------ conversa com a página do painel da extensão

def _pagina():
    """O alvo (aba) com o painel da extensão aberto; abre se não tiver."""
    eid = _id_da_extensao()
    if not eid:
        return None
    url = f"chrome-extension://{eid}/painel-lateral.html"
    for a in _alvos() or []:
        if a.get("url", "").startswith(url) and a.get("webSocketDebuggerUrl"):
            return a
    try:
        novo = httpx.put(f"http://127.0.0.1:{PORTA}/json/new?{url}", timeout=5).json()
        time.sleep(1.2)
        return novo
    except Exception:
        return None


def _avaliar(expressao, timeout=20):
    from websockets.sync.client import connect
    alvo = _pagina()
    if not alvo:
        raise RuntimeError("extensão do Radar não instalada no navegador do Jarvis")
    with connect(alvo["webSocketDebuggerUrl"], max_size=2**24, open_timeout=5) as ws:
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
            "expression": expressao, "awaitPromise": True, "returnByValue": True}}))
        fim = time.time() + timeout
        while time.time() < fim:
            m = json.loads(ws.recv(timeout=timeout))
            if m.get("id") == 1:
                r = m.get("result", {})
                if r.get("exceptionDetails"):
                    raise RuntimeError(r["exceptionDetails"].get("text", "erro na extensão"))
                return r.get("result", {}).get("value")
    raise TimeoutError("a extensão não respondeu")


def _catalogo():
    return json.loads((PASTA_EXT / "dados" / "nichos.json").read_text(encoding="utf-8"))


def montar_config(o_que, onde, meta=50):
    """"pizzaria", "Porto Alegre" → config igual à do botão Iniciar do painel lateral."""
    cat = _catalogo()
    t = _sa(o_que)
    locais = [l.strip() for l in re.split(r",| e ", onde) if l.strip()]
    if re.search(r"condom|administradora|s[ií]ndic", t):
        alvos = [a for a in cat["porthon"]["alvos"] if a["id"] in t or (a["id"] == "condominio" and "condom" in t)
                 or (a["id"] == "administradora" and "administr" in t)] or cat["porthon"]["alvos"][:1]
        nichos = [{"frente": "porthon", "alvo": a["id"], "nicho": a["id"], "termos": a["termos"],
                   "categorias": a["categorias"], "rotulo": a["rotulo"].lower()} for a in alvos]
        frente, situacoes = "porthon", []
    else:
        nichos = []
        for g in cat["sevencode"]["grupos"]:
            for n in g["nichos"]:
                nomes = [_sa(n["id"]), _sa(n["rotulo"])] + [_sa(x) for x in n["termos"]]
                if any(x and (x in t or t in x) for x in nomes):
                    nichos.append({"frente": "sevencode", "alvo": g["id"], "nicho": n["id"], "termos": n["termos"],
                                   "categorias": n["categorias"], "rotulo": n["rotulo"].lower()})
        if not nichos:  # nicho que o catálogo não conhece: vai como termo livre
            nichos = [{"frente": "sevencode", "alvo": "outros", "nicho": o_que, "termos": [o_que], "categorias": [], "rotulo": o_que}]
        frente, situacoes = "sevencode", ["sem_site", "rede_social", "site_gratuito"]
    return {"frente": frente, "nichos": nichos[:4], "locais": locais or ["Porto Alegre"], "meta": int(meta),
            "ignorarHistorico": True, "filtros": {"situacoes": situacoes, "notaMinima": 0, "avaliacoesMinimas": 0,
                                                  "somenteCelular": False, "conferirCategoria": True, "fichaCompleta": False}}


def iniciar(o_que, onde, meta=50):
    config = montar_config(o_que, onde, meta)
    r = _avaliar(f"chrome.runtime.sendMessage({{tipo: 'iniciarVarredura', config: {json.dumps(config, ensure_ascii=False)}}})")
    return r or {"ok": False, "erro": "sem resposta"}, config


def parar():
    return _avaliar("chrome.runtime.sendMessage({tipo: 'pararVarredura'})")


def estado():
    """Progresso da varredura e os últimos leads (o que a tela do Jarvis mostra)."""
    v = _avaliar("chrome.storage.local.get(['varredura', 'leads']).then(d => ({varredura: d.varredura || null, "
                 "leads: Object.values(d.leads || {}).sort((a, b) => String(b.coletado_em || '').localeCompare(String(a.coletado_em || ''))).slice(0, 12), "
                 "total: Object.keys(d.leads || {}).length}))")
    var = v.get("varredura") or {}
    fila, i = var.get("fila") or [], var.get("indice") or 0
    atual = fila[i] if i < len(fila) else {}
    return {"status": var.get("status"), "mensagem": var.get("mensagem"), "encontrados": var.get("encontrados", 0),
            "coletados": var.get("coletados", 0), "meta": (var.get("config") or {}).get("meta"),
            "busca": f"{atual.get('termo', '')} em {atual.get('local', '')}" if atual else "",
            "progresso": f"{min(i + 1, len(fila))}/{len(fila)}" if fila else "", "total": v.get("total", 0),
            "leads": [{"id": l.get("id"), "nome": l.get("nome"), "telefone": l.get("telefone"), "cidade": l.get("cidade") or l.get("bairro"),
                       "site": l.get("situacao_site"), "nota": l.get("nota"), "score": l.get("score"), **_coordenadas(l.get("maps_url"))}
                      for l in v.get("leads", [])]}


def _coordenadas(url):
    """O link do Maps tem a posição: ".../@-30.03,-51.22,17z" ou "!3d-30.03!4d-51.22"."""
    m = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", url or "") or re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", url or "")
    return {"lat": float(m.group(1)), "lng": float(m.group(2))} if m else {}


PAINEL_RADAR = "https://painel-7sevencode.vercel.app/radar"


def abrir_painel():
    """Abre o painel do Radar no navegador do Jarvis: com ele aberto junto da extensão, cada lead novo já vai pro
    painel sozinho (a sincronia é do próprio painel). Devolve False se ele cair na tela de login."""
    alvos = _alvos() or []
    aba = next((a for a in alvos if a.get("url", "").startswith(PAINEL_RADAR)), None)
    if not aba:
        try:
            aba = httpx.put(f"http://127.0.0.1:{PORTA}/json/new?{PAINEL_RADAR}", timeout=5).json()
        except Exception:
            return None
        time.sleep(6)
        aba = next((a for a in (_alvos() or []) if a.get("id") == aba.get("id")), aba)
    return "login" not in aba.get("url", "") and "entrar" not in aba.get("title", "").lower()
