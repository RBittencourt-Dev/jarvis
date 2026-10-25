"""Painéis AO VIVO (25/10): o Jarvis monta um popup bonito que se atualiza sozinho com dados de um site.

Pedido dele: "monitora as eleições no site do TSE e cria um popup com os números ao vivo, bonito, com a foto dos dois
— isso foi um exemplo, dá esse poder a ele". Então é genérico: qualquer fonte, qualquer número.

Como funciona:
  1. O cérebro acha a FONTE (de preferência uma API que devolve JSON; senão a página) e diz os CAMPOS:
       {"lula_pct": "cand[0].pvap", "bolso_pct": "cand[1].pvap", "apurado": "pst"}   ← caminho no JSON
       {"preco": "preço atual do bitcoin em dólar"}                                  ← descrição (página comum)
     Caminho no JSON é lido direto (rápido, de graça). Descrição: o cérebro lê a página e tira o número (mais lento,
     por isso o intervalo mínimo é maior).
  2. O cérebro desenha o HTML do popup (pode usar fotos e as classes prontas de CSS abaixo). Onde vai um número:
       <span data-campo="lula_pct"></span>    texto trocado a cada atualização
       <div class="vivo-barra"><i data-largura="lula_pct"></i></div>   barra com a largura = o número (%)
       <img data-img="foto_campo">            foto que vem de um campo (ou <img src="..."> fixo)
  3. Uma thread busca de novo a cada N segundos e empurra os números pro popup (sem piscar).

Segurança: o HTML do cérebro roda num iframe SANDBOX (sem acesso ao Jarvis, às chaves ou ao PC). Só https.
Para sozinho depois de `minutos` (padrão 3 h) pra não ficar consultando o site pra sempre. "Para o painel ao vivo" para.
"""
import json
import re
import threading
import time
import uuid

import httpx

import extensao

INTERVALO_MIN_JSON = 10    # segundos (API JSON: barato)
INTERVALO_MIN_PAGINA = 60  # segundos (página comum: o cérebro lê a página, gasta o limite da nuvem)
NAVEGADOR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}

_paineis = {}  # id -> {"titulo", "fonte", "campos", "html", "intervalo", "ate", "parar": Event, "dados", "erro"}


# ------------------------------------------------------------------ ler os números

def _caminho(dado, caminho):
    """'cand[0].pvap' ou 'cand.0.pvap' dentro do JSON. None se não existir."""
    for parte in re.findall(r"[^.\[\]]+", caminho):
        if isinstance(dado, list):
            if not parte.lstrip("-").isdigit() or not -len(dado) <= int(parte) < len(dado):
                return None
            dado = dado[int(parte)]
        elif isinstance(dado, dict):
            if parte not in dado:
                return None
            dado = dado[parte]
        else:
            return None
    return dado


def _e_caminho(texto):
    return bool(re.fullmatch(r"[\w\-]+(?:\[\d+\]|\.[\w\-]+)*", texto.strip()))


def _baixar(fonte):
    r = httpx.get(fonte, headers=NAVEGADOR, timeout=20, follow_redirects=True)
    r.raise_for_status()
    try:
        return r.json(), r.text
    except ValueError:
        return None, r.text


def _texto_da_pagina(html):
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def _pelo_cerebro(campos, texto):
    """Página comum: o cérebro lê o texto e devolve só os números pedidos (JSON)."""
    import asyncio
    import cerebro
    pedido = ("Extraia da página abaixo SÓ estes valores e responda em JSON {campo: valor} (valor curto, como aparece; "
              "null se não achar):\n" + json.dumps(campos, ensure_ascii=False) + "\n\nPÁGINA:\n" + texto[:7000])
    resposta = asyncio.run(cerebro.completar([{"role": "user", "content": pedido}], json_mode=True, temperatura=0,
                                             max_tokens=300))
    return json.loads(resposta[resposta.index("{"):resposta.rindex("}") + 1])


def ler(painel):
    """{campo: valor} agora. Levanta erro com uma dica se a fonte ou os campos não servirem."""
    dado, bruto = _baixar(painel["fonte"])
    campos = painel["campos"]
    caminhos = {k: v for k, v in campos.items() if dado is not None and _e_caminho(v)}
    valores = {k: _caminho(dado, v) for k, v in caminhos.items()}
    resto = {k: v for k, v in campos.items() if k not in caminhos}
    if resto:
        valores.update(_pelo_cerebro(resto, _texto_da_pagina(bruto) if dado is None else bruto))
    return {k: ("" if v is None else v if isinstance(v, (int, float)) else str(v)) for k, v in valores.items()}


def _amostra(fonte):
    """Pra ajudar o cérebro a acertar o caminho: o começo do JSON (ou do texto) da fonte."""
    try:
        dado, bruto = _baixar(fonte)
    except Exception as e:
        return f"(nem consegui abrir a fonte: {e})"
    return (json.dumps(dado, ensure_ascii=False)[:1500] if dado is not None else _texto_da_pagina(bruto)[:1500])


# ------------------------------------------------------------------ o popup

_canal_de = {}  # id do painel -> a tela onde ele está (pedido dele 25/10: UMA tela só, não as duas)


def _publicar(evento):
    """O painel nasce numa tela só: a principal (palco do HUD) se estiver aberta, senão a lateral.
    As atualizações e o "remover" vão pra mesma tela onde ele nasceu."""
    pid = (evento.get("vivo") or evento.get("vivo_dados") or {}).get("id") or (evento.get("remover") or [None])[0]
    if "vivo" in evento:
        _canal_de[pid] = "palco" if extensao.tem_palco() else "extensao"
    canal = _canal_de.get(pid, "palco" if extensao.tem_palco() else "extensao")
    if "remover" in evento:
        _canal_de.pop(pid, None)
    extensao.publicar(evento, canal)


def fechar(pid):
    """Ele fechou o painel no X da tela: para de consultar o site também."""
    p = _paineis.get(pid)
    if p:
        p["parar"].set()
    _canal_de.pop(pid, None)


def _rodar(pid):
    p = _paineis[pid]
    while not p["parar"].wait(p["intervalo"]):
        if time.time() > p["ate"]:
            _publicar({"vivo_dados": {"id": pid, "status": "encerrado (tempo limite)"}})
            break
        try:
            p["dados"], p["erro"] = ler(p), None
            _publicar({"vivo_dados": {"id": pid, "dados": p["dados"], "hora": time.strftime("%H:%M:%S")}})
        except Exception as e:  # site fora do ar um minuto não derruba o painel: mostra e tenta de novo
            p["erro"] = str(e)[:120]
            _publicar({"vivo_dados": {"id": pid, "status": "sem conexão com a fonte, tentando de novo…"}})
    _paineis.pop(pid, None)


def criar_painel_ao_vivo(titulo: str, fonte: str, campos: str, html: str = "", intervalo: str = "30", minutos: str = "180"):
    """Ferramenta do cérebro. campos = JSON {"nome": "caminho.no[0].json" ou "descrição do valor"}."""
    if not re.match(r"^https://", fonte or ""):
        return "A fonte precisa ser um link https."
    try:
        campos_ = json.loads(campos) if isinstance(campos, str) else dict(campos)
        assert campos_ and isinstance(campos_, dict)
    except Exception:
        return 'campos tem que ser um JSON tipo {"lula_pct": "cand[0].pvap"}.'
    so_json = all(_e_caminho(v) for v in campos_.values())
    try:
        segundos = max(int(float(intervalo or 30)), INTERVALO_MIN_JSON if so_json else INTERVALO_MIN_PAGINA)
    except ValueError:
        segundos = 30
    pid = "vivo-" + uuid.uuid4().hex[:8]
    painel = {"titulo": titulo, "fonte": fonte, "campos": campos_, "html": html or "", "intervalo": segundos,
              "ate": time.time() + max(5, min(int(float(minutos or 180)), 24 * 60)) * 60,
              "parar": threading.Event(), "dados": {}, "erro": None}
    try:
        painel["dados"] = ler(painel)
    except Exception as e:
        return f"Não consegui ler a fonte ({e}). Começo do que ela devolve:\n{_amostra(fonte)}"
    vazios = [k for k, v in painel["dados"].items() if v in ("", None)]
    if len(vazios) == len(campos_):
        return ("Abri a fonte mas nenhum campo veio (caminhos errados?). Valores: " + json.dumps(painel["dados"], ensure_ascii=False)
                + f"\nComeço do que ela devolve:\n{_amostra(fonte)}\nAjuste os campos e chame de novo.")
    _paineis[pid] = painel
    if not extensao.aberta() and not extensao.tem_palco():
        # porta lida do config.json: "from server import" carregaria uma 2ª cópia do servidor (ele roda como __main__)
        from pathlib import Path
        extensao.abrir(json.loads((Path(__file__).parent / "config.json").read_text(encoding="utf-8")).get("porta", 8765))
    _publicar({"vivo": {"id": pid, "titulo": titulo, "html": painel["html"], "campos": list(campos_),
                        "dados": painel["dados"], "intervalo": segundos, "hora": time.strftime("%H:%M:%S")}})
    threading.Thread(target=_rodar, args=(pid,), daemon=True).start()
    aviso = f" Campos vazios (confira o caminho): {', '.join(vazios)}." if vazios else ""
    return (f"Painel ao vivo '{titulo}' na tela, atualizando a cada {segundos}s. Valores agora: "
            f"{json.dumps(painel['dados'], ensure_ascii=False)[:600]}.{aviso}")


def parar_painel_ao_vivo(titulo: str = ""):
    alvo = (titulo or "").lower().strip()
    parados = []
    for pid, p in list(_paineis.items()):
        if not alvo or alvo in ("todos", "tudo") or alvo in p["titulo"].lower() or p["titulo"].lower() in alvo:
            p["parar"].set()
            _publicar({"remover": [pid]})
            parados.append(p["titulo"])
    return ("Parei: " + ", ".join(parados)) if parados else "Não tem painel ao vivo rodando."


def listar():
    return [{"id": k, "titulo": p["titulo"], "intervalo": p["intervalo"], "erro": p["erro"]} for k, p in _paineis.items()]


# ------------------------------------------------------------------ voz: parar/listar sem passar pelo cérebro

DEMORA = False
PARAR = re.compile(r"^(?:jarvis[ ,]*)?(?:para|parar|pare|desliga|fecha|encerra|tira)\s+(?:de\s+monitorar|o\s+monitoramento|"
                   r"(?:o|os)\s+(?:painel|pain[eé]is|popup|pop-up)s?\s+(?:ao\s+vivo|de\s+monitoramento))(?:\s+d[aeo]s?\s+(?P<t>.+?))?[.!?]*$", re.I)


def entender(texto):
    m = PARAR.match((texto or "").strip())
    return {"acao": "parar", "titulo": (m.group("t") or "") if m else ""} if m else None


def executar(p):
    return parar_painel_ao_vivo(p["titulo"]) + ", chefe.", []
