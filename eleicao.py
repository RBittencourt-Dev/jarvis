"""Apuração da eleição AO VIVO, direto do TSE (25/10/2026, 2º turno de presidente).

Pedido dele: "faz um painel do segundo turno buscando pelo site do TSE, com a foto dos candidatos e a porcentagem,
e ele falar sempre que atualizar: quantos porcento pra cada um, a quantidade de votos e quem tá na frente. E tem que
ativar se eu falar pra ele mostrar os resultados das eleições ao vivo."

De onde vêm os números: a página resultados.tse.jus.br é só a "casca"; os números ficam num JSON público que o TSE
regrava a cada lote de urnas:
    https://resultados.tse.jus.br/oficial/ele2026/6258/dados/br/br-c0001-e006258-u.json
      6258  = código da eleição (Federal 2026, 2º turno)    c0001 = cargo Presidente    br = Brasil inteiro
    fotos:  https://resultados.tse.jus.br/oficial/ele2026/6258/fotos/br/<sqcand>.jpeg
(Esses códigos estão no índice do próprio TSE: /oficial/comum/config/ele-c.json.)

O popup usa o mesmo palco dos painéis ao vivo (paineis_vivos): HTML num iframe sandbox + números empurrados.
"""
import json
import re
import threading
import time
import uuid
from pathlib import Path

import httpx

import extensao
import paineis_vivos

BASE = "https://resultados.tse.jus.br/oficial/ele2026/6258"
DADOS = BASE + "/dados/br/br-c0001-e006258-u.json"
FOTO = BASE + "/fotos/br/{}.jpeg"
INTERVALO = 15          # segundos entre uma consulta e outra (o JSON é leve; o TSE atualiza em lotes)
FALA_MIN = 40           # segundos: atualização que chega colada na anterior espera a próxima pra não falar sem parar
DURACAO = 8 * 3600      # para sozinho depois de 8 h

falar = None            # o server.py liga aqui o avisar() dele (o Jarvis fala sozinho, mesmo sem ninguém perguntar)
_estado = {"id": None, "parar": None, "ordem": [], "pst": None, "falou_em": 0.0, "pendente": False,
           "mudo": False, "eleito_avisado": False, "ultimo": None}


# ------------------------------------------------------------------ ler o TSE

def _num(texto):
    """'57,66' → 57.66 ; '193574' → 193574"""
    try:
        return float(str(texto).replace(".", "").replace(",", "."))
    except ValueError:
        return 0.0


def _milhar(n):
    return f"{int(n):,}".replace(",", ".")


def _nome(c):
    nome = (c.get("nmu") or c.get("nm") or "").title()
    return re.sub(r"\b(Da|De|Do|Dos|Das|E)\b", lambda m: m.group(1).lower(), nome)


def ler():
    """Situação agora: {"apuradas": 12.3, "hora": "17:06:31", "candidatos": [{...}], ...}"""
    j = httpx.get(DADOS, headers=paineis_vivos.NAVEGADOR, timeout=15).json()
    candidatos = []
    for cargo in j.get("carg", []):
        for agr in cargo.get("agr", []):
            for par in agr.get("par", []):
                for c in par.get("cand", []):
                    candidatos.append({
                        "sq": c["sqcand"], "nome": _nome(c), "numero": c.get("n", ""), "partido": par.get("sg", ""),
                        "votos": int(_num(c.get("vap", 0))), "pct": _num(c.get("pvapn") or c.get("pvap", 0)),
                        "eleito": c.get("e") == "s" or "eleito" in (c.get("st") or "").lower(),
                        "foto": FOTO.format(c["sqcand"])})
    s = j.get("s", {})
    return {"apuradas": _num(s.get("pstn") or s.get("pst", 0)), "hora": j.get("hg", ""),
            "brancos": int(_num(j.get("v", {}).get("vb", 0))), "nulos": int(_num(j.get("v", {}).get("tvn", 0))),
            "candidatos": sorted(candidatos, key=lambda c: -c["votos"])}


# ------------------------------------------------------------------ o popup

def _html(cands):
    """Os candidatos em colunas (foto, nome, % grande, votos, barra). Os números entram por data-campo."""
    colunas = "".join(f"""
  <div class="col">
    <div class="foto"><img src="{c['foto']}" alt=""><span class="lider" data-campo="c{i}_lider"></span></div>
    <div class="nome">{c['nome']}</div>
    <div class="partido">{c['numero']} · {c['partido']}</div>
    <div class="pct"><span data-campo="c{i}_pct"></span><small>%</small></div>
    <div class="barra"><i data-largura="c{i}_pctn"></i></div>
    <div class="votos"><span data-campo="c{i}_votos"></span> votos</div>
  </div>""" for i, c in enumerate(cands))
    return f"""<style>
  body {{ font-family: Segoe UI, sans-serif; color: #dff6ff; margin: 0; padding: 4px 2px 8px; }}
  .topo {{ display: flex; justify-content: space-between; align-items: baseline; font-size: 12px; letter-spacing: .08em;
          color: #7fd4ff; text-transform: uppercase; }}
  .topo b {{ font-size: 20px; color: #fff; letter-spacing: 0; }}
  .apur {{ height: 4px; background: #0b2a3d; border-radius: 2px; margin: 6px 0 12px; overflow: hidden; }}
  .apur i {{ display: block; height: 100%; background: linear-gradient(90deg, #1fa3ff, #7fe7ff); transition: width 1s; }}
  .grade {{ display: grid; grid-template-columns: repeat({len(cands)}, 1fr); gap: 12px; }}
  .col {{ background: rgba(20, 70, 110, .25); border: 1px solid rgba(90, 190, 255, .25); border-radius: 10px;
         padding: 12px; text-align: center; animation: entra .6s both; }}
  .col:nth-child(2) {{ animation-delay: .15s; }}
  .foto {{ position: relative; width: 110px; height: 110px; margin: 0 auto 8px; }}
  .foto img {{ width: 100%; height: 100%; object-fit: cover; border-radius: 50%; border: 3px solid #39b6ff;
              box-shadow: 0 0 18px rgba(57, 182, 255, .5); }}
  .lider {{ position: absolute; left: 50%; bottom: -6px; transform: translateX(-50%); background: #ffd23f; color: #1a1300;
           font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 8px; letter-spacing: .1em; white-space: nowrap; }}
  .lider:empty {{ display: none; }}
  .nome {{ font-size: 17px; font-weight: 600; margin-top: 6px; }}
  .partido {{ font-size: 11px; color: #8fb8cc; margin-bottom: 4px; }}
  .pct {{ font-size: 44px; font-weight: 700; color: #fff; line-height: 1.1; text-shadow: 0 0 14px rgba(80, 200, 255, .6); }}
  .pct small {{ font-size: 20px; margin-left: 2px; }}
  .barra {{ height: 8px; background: #0b2a3d; border-radius: 4px; overflow: hidden; margin: 6px 0; }}
  .barra i {{ display: block; height: 100%; background: linear-gradient(90deg, #1fa3ff, #7fe7ff); transition: width 1.2s; }}
  .votos {{ font-size: 13px; color: #bfe6ff; }}
  .rodape {{ margin-top: 10px; font-size: 13px; text-align: center; color: #ffd23f; }}
  .mudou {{ animation: pisca .9s; }}
  @keyframes pisca {{ 30% {{ color: #ffd23f; }} }}
  @keyframes entra {{ from {{ opacity: 0; transform: translateY(14px); }} }}
</style>
<div class="topo"><span>Urnas apuradas</span><b><span data-campo="apuradas"></span>%</b></div>
<div class="apur"><i data-largura="apuradas_n"></i></div>
<div class="grade">{colunas}
</div>
<div class="rodape" data-campo="frente"></div>"""


def _dados(sit, ordem):
    """Os valores que o popup troca (por posição fixa: as fotos não trocam de lado quando a liderança vira)."""
    por_sq = {c["sq"]: c for c in sit["candidatos"]}
    lider = sit["candidatos"][0] if sit["candidatos"] else None
    d = {"apuradas": f"{sit['apuradas']:.2f}".replace(".", ","), "apuradas_n": f"{sit['apuradas']:.2f}".replace(".", ","),  # com vírgula: a barra lê no formato BR
         "frente": _frase_frente(sit)}
    for i, sq in enumerate(ordem):
        c = por_sq.get(sq)
        if not c:
            continue
        d[f"c{i}_pct"] = f"{c['pct']:.2f}".replace(".", ",")
        d[f"c{i}_pctn"] = d[f"c{i}_pct"]
        d[f"c{i}_votos"] = _milhar(c["votos"])
        d[f"c{i}_lider"] = ("ELEITO" if c["eleito"] else "NA FRENTE") if (c["eleito"] or (lider and lider["sq"] == sq and c["votos"] > 0)) else ""
    return d


def _frase_frente(sit):
    cs = sit["candidatos"]
    if len(cs) < 2 or not cs[0]["votos"]:
        return "Aguardando os primeiros votos…"
    if cs[0]["eleito"]:
        return f"{cs[0]['nome']} está eleito presidente"
    return f"{cs[0]['nome']} na frente por {_milhar(cs[0]['votos'] - cs[1]['votos'])} votos"


# ------------------------------------------------------------------ a fala

def _votos_falados(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".replace(".", ",").replace(",0", "") + " milhões de votos"
    return f"{_milhar(n)} votos"


def _pct_falado(p):
    return f"{p:.2f}".replace(".", ",") + "%"


def resumo_falado(sit, abertura="Atualização da apuração"):
    cs = sit["candidatos"]
    if not cs or not cs[0]["votos"]:
        return "A apuração ainda não tem votos contados, chefe. Te aviso quando começar."
    partes = [f"{abertura}: {_pct_falado(sit['apuradas'])} das urnas."]
    partes += [f"{c['nome']} tem {_pct_falado(c['pct'])}, com {_votos_falados(c['votos'])}." for c in cs[:2]]
    if cs[0]["eleito"]:
        partes.append(f"{cs[0]['nome']} está eleito presidente do Brasil.")
    elif len(cs) > 1:
        partes.append(f"{cs[0]['nome']} na frente, por {_votos_falados(cs[0]['votos'] - cs[1]['votos'])}.")
    return " ".join(partes)


def _falar(texto):
    if falar and not _estado["mudo"]:
        falar(texto)


# ------------------------------------------------------------------ o vigia

def _abrir_tela():
    if not extensao.aberta() and not extensao.tem_palco():
        porta = json.loads((Path(__file__).parent / "config.json").read_text(encoding="utf-8")).get("porta", 8765)
        extensao.abrir(porta)


def _rodar(pid, parar, ate):
    while not parar.wait(INTERVALO):
        if time.time() > ate:
            paineis_vivos._publicar({"vivo_dados": {"id": pid, "status": "encerrado (tempo limite)"}})
            break
        try:
            sit = ler()
        except Exception:
            paineis_vivos._publicar({"vivo_dados": {"id": pid, "status": "TSE não respondeu, tentando de novo…"}})
            continue
        _estado["ultimo"] = sit
        paineis_vivos._publicar({"vivo_dados": {"id": pid, "dados": _dados(sit, _estado["ordem"]),
                                                "hora": f"TSE {sit['hora']}"}})
        if sit["apuradas"] != _estado["pst"]:  # chegou lote novo de urnas
            _estado["pst"], _estado["pendente"] = sit["apuradas"], True
        if _estado["pendente"] and time.time() - _estado["falou_em"] >= FALA_MIN:
            _estado["pendente"], _estado["falou_em"] = False, time.time()
            eleito = sit["candidatos"] and sit["candidatos"][0]["eleito"]
            if eleito and not _estado["eleito_avisado"]:
                _estado["eleito_avisado"] = True
                _falar(resumo_falado(sit, "Chefe, temos resultado"))
            elif not eleito or sit["apuradas"] >= 100:
                _falar(resumo_falado(sit))
        if sit["apuradas"] >= 100:
            paineis_vivos._publicar({"vivo_dados": {"id": pid, "status": f"apuração encerrada · TSE {sit['hora']}"}})
            break
    if _estado["id"] == pid:
        _estado["id"] = None


def mostrar():
    """Liga (ou religa) o painel e devolve a fala com a situação de agora."""
    sit = ler()
    if _estado["id"]:  # já estava rodando: só traz de volta pra tela, com os números de agora
        parar(silencioso=True)
    pid = "vivo-eleicao-" + uuid.uuid4().hex[:6]
    ordem = [c["sq"] for c in sit["candidatos"][:2]]
    ev = threading.Event()
    _estado.update(id=pid, parar=ev, ordem=ordem, pst=sit["apuradas"], falou_em=time.time(), pendente=False,
                   mudo=False, ultimo=sit, eleito_avisado=bool(sit["candidatos"] and sit["candidatos"][0]["eleito"]))
    _abrir_tela()
    paineis_vivos._publicar({"vivo": {"id": pid, "titulo": "Eleição 2026 · 2º turno · Presidente",
                                      "html": _html([c for c in sit["candidatos"] if c["sq"] in ordem]),
                                      "campos": [], "dados": _dados(sit, ordem), "intervalo": INTERVALO,
                                      "hora": f"TSE {sit['hora']}"}})
    threading.Thread(target=_rodar, args=(pid, ev, time.time() + DURACAO), daemon=True).start()
    return resumo_falado(sit, "Apuração na tela, chefe") + " Te falo a cada atualização."


def parar(silencioso=False):
    if not _estado["id"]:
        return "O painel da eleição não tá ligado, chefe."
    _estado["parar"].set()
    paineis_vivos._publicar({"remover": [_estado["id"]]})
    _estado["id"] = None
    return "" if silencioso else "Desliguei o painel da eleição, chefe."


# ------------------------------------------------------------------ voz (sem passar pelo cérebro)

DEMORA = True
_ASSUNTO = r"(?:elei[cç](?:[aã]o|[oõ]es)|apura[cç][aã]o|segundo turno|2[ºo°]? turno|urnas|resultados? (?:pra|para|de) presidente)"
_FORA = re.compile(r"condom|s[ií]ndic|chapa|gr[eê]mio|\b(?:19\d\d|20[01]\d|202[0-5])\b|sindicato|reuni", re.I)
MUDO = re.compile(r"\b(?:para|pare|parar) de (?:falar|avisar)\b.*" + _ASSUNTO, re.I)
FALAR = re.compile(r"\b(?:volta|pode voltar) a (?:falar|avisar)\b.*" + _ASSUNTO, re.I)
PARAR = re.compile(r"\b(?:para|pare|parar|desliga|fecha|tira|encerra|some com)\b(?:\s+\w+){0,4}\s+" + _ASSUNTO, re.I)
MOSTRAR = re.compile(r"\b(?:mostr\w*|abr\w*|lig\w*|ativ\w*|acompanh\w*|monitor\w*|bot\w*|coloc\w*|p[oõ]e|quero ver|"
                     r"deixa eu ver|ao vivo|como (?:t[aá]|est[aá]|anda)|quem (?:t[aá]|est[aá]) (?:ganhando|na frente|vencendo)|"
                     r"quem ganhou|resultados?|placar|painel|parcial)\b", re.I)


def entender(texto):
    t = (texto or "").strip()
    if not re.search(r"\b" + _ASSUNTO, t, re.I) or _FORA.search(t):
        return None
    if MUDO.search(t):
        return {"acao": "mudo"}
    if FALAR.search(t):
        return {"acao": "falar"}
    if PARAR.search(t):
        return {"acao": "parar"}
    if MOSTRAR.search(t):
        return {"acao": "mostrar"}
    return None


def executar(p):
    if p["acao"] == "parar":
        return parar(), []
    if p["acao"] == "mudo":
        _estado["mudo"] = True
        return "Beleza, sigo atualizando o painel mas fico quieto.", []
    if p["acao"] == "falar":
        _estado["mudo"] = False
        return "Voltei a te avisar a cada atualização da apuração.", []
    try:
        return mostrar(), []
    except Exception as e:
        return f"O site do TSE não respondeu agora ({str(e)[:60]}). Tenta de novo daqui a pouco, chefe.", []
