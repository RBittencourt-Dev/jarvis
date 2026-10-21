"""Proatividade: quando o Jarvis pode falar sozinho, alertas do PC e sugestões de automação pela rotina dele.

- Nível (config "proatividade.nivel"):
    "alto"      — fala tudo: lembretes, sites caindo, PC apertado, sugestões de rotina;
    "baixo"     — só lembretes/pomodoro e problemas sérios (site fora do ar, disco quase cheio);
    "desligado" — só o que ELE marcou (lembrete, pomodoro). O resto vira só pop-up mudo.
- Não perturbe (manual ou nos horários "silencio_de"→"silencio_ate"): nada fala, tudo vira pop-up mudo
  (lembrete marcado por ele ainda aparece na tela).
- PC: disco C acima de 92% (1x por dia), memória acima de 92% ou CPU acima de 90% por 3 min seguidos.
- Rotina: o mesmo pedido curto, no mesmo horário (±1 h), em 3+ dias diferentes nas últimas 2 semanas
  → sugere uma automação (uma vez por pedido). "Cria a automação sugerida" cria.
"""
import json
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import psutil

import registro

RAIZ = Path(__file__).parent
SUGERIDAS = RAIZ / "dados" / "sugestoes.json"
PADRAO = {"nivel": "alto", "nao_perturbe": False, "silencio_de": "23:00", "silencio_ate": "07:00", "sugerir_proximo_passo": True}
_estado = {"cpu_alta": 0, "ram_alta": 0, "disco_avisado": "", "ultima_sugestao": None}


def config():
    try:
        c = json.loads((RAIZ / "config.json").read_text(encoding="utf-8")).get("proatividade") or {}
    except (OSError, ValueError):
        c = {}
    return {**PADRAO, **c}


def em_silencio(c=None):
    c = c or config()
    if c.get("nao_perturbe"):
        return True
    de, ate = c.get("silencio_de") or "", c.get("silencio_ate") or ""
    if not (re.fullmatch(r"\d\d:\d\d", de) and re.fullmatch(r"\d\d:\d\d", ate)) or de == ate:
        return False
    agora = datetime.now().strftime("%H:%M")
    return (de <= agora < ate) if de < ate else (agora >= de or agora < ate)


def pode_falar(importancia):
    """importancia: 'marcado' (lembrete/pomodoro dele), 'serio' (site caiu, disco cheio), 'info' (sugestão, CPU)."""
    c = config()
    if em_silencio(c):
        return False
    if c["nivel"] == "desligado":
        return importancia == "marcado"
    if c["nivel"] == "baixo":
        return importancia in ("marcado", "serio")
    return True


def vigiar_pc():
    """[(fala, cartão, importância)] — chamado a cada minuto."""
    avisos = []
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory().percent
    disco = psutil.disk_usage("C:\\").percent
    _estado["cpu_alta"] = _estado["cpu_alta"] + 1 if cpu > 90 else 0
    _estado["ram_alta"] = _estado["ram_alta"] + 1 if ram > 92 else 0
    if _estado["cpu_alta"] == 3:
        quem = _quem_pesa()
        avisos.append((f"Chefe, o processador tá no talo faz 3 minutos.{(' Quem tá pesando: ' + quem + '.') if quem else ''}",
                       {"titulo": "PC", "destaque": f"CPU {cpu:.0f}%", "texto": quem, "alerta": True}, "info"))
    if _estado["ram_alta"] == 3:
        quem = _quem_pesa("memoria")
        avisos.append((f"Chefe, a memória tá quase cheia.{(' O maior consumo: ' + quem + '.') if quem else ''}",
                       {"titulo": "PC", "destaque": f"RAM {ram:.0f}%", "texto": quem, "alerta": True}, "info"))
    hoje = datetime.now().strftime("%Y-%m-%d")
    if disco > 92 and _estado["disco_avisado"] != hoje:
        _estado["disco_avisado"] = hoje
        livre = psutil.disk_usage("C:\\").free / 2**30
        avisos.append((f"Atenção, chefe: o disco C tá com {disco:.0f}% ocupado, só {livre:.0f} giga livres.",
                       {"titulo": "Disco quase cheio", "destaque": f"{disco:.0f}%", "texto": f"{livre:.1f} GB livres no C:",
                        "alerta": True}, "serio"))
    return avisos


def _quem_pesa(tipo="cpu"):
    procs = []
    for p in psutil.process_iter(["name", "cpu_percent", "memory_info"]):
        try:
            procs.append((p.info["cpu_percent"] or 0, (p.info["memory_info"].rss if p.info["memory_info"] else 0), p.info["name"]))
        except Exception:
            pass
    procs.sort(key=lambda x: x[0] if tipo == "cpu" else x[1], reverse=True)
    return ", ".join(n.removesuffix(".exe") for _, _, n in procs[:2] if n and n != "System Idle Process")


# ------------------------------------------------------------------ rotina → sugestão de automação

COMANDO = re.compile(r"^(?:abre|abrir|toca|tocar|liga|ativa|mostra|modo|bora|entra|inicia|come[cç]a|pesquisa|quanto|tenho|"
                     r"not[ií]cias|dados de hoje|resumo)\b", re.I)


def _sugeridas():
    try:
        return json.loads(SUGERIDAS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def procurar_rotina():
    """Um pedido que se repete no mesmo horário em 3+ dias. Devolve (fala, cartão, 'info') ou None."""
    import automacoes
    agora = time.time()
    vezes = defaultdict(list)  # pedido → [(dia, hora)]
    for r in registro.todas():
        if agora - r["quando"] > 14 * 86400 or r.get("tipo") != "pedido":
            continue
        pedido = re.sub(r"\s+", " ", r["pedido"].lower().strip(" .!?"))
        if not COMANDO.match(pedido) or len(pedido.split()) > 7:
            continue
        quando = datetime.fromtimestamp(r["quando"])
        vezes[pedido].append((quando.date(), quando.hour + quando.minute / 60))
    ja = _sugeridas()
    existentes = " ".join(" ".join(a.get("acoes", [])).lower() for a in automacoes.todas())
    for pedido, lista in vezes.items():
        if pedido in ja or pedido in existentes:
            continue
        dias = {}
        for dia, hora in lista:
            dias.setdefault(dia, hora)
        if len(dias) < 3:
            continue
        horas = sorted(dias.values())
        meio = horas[len(horas) // 2]
        perto = [h for h in horas if abs(h - meio) <= 1]
        if len({d for d, h in dias.items() if abs(h - meio) <= 1}) < 3:
            continue
        media = sum(perto) / len(perto)
        hora = f"{int(media):02d}:{int((media % 1) * 60) // 5 * 5:02d}"
        ja[pedido] = {"hora": hora, "quando": agora}
        SUGERIDAS.parent.mkdir(exist_ok=True)
        SUGERIDAS.write_text(json.dumps(ja, ensure_ascii=False), encoding="utf-8")
        _estado["ultima_sugestao"] = {"pedido": pedido, "hora": hora}
        return (f"Chefe, reparei que quase todo dia, por volta das {hora.replace(':', ' e ')}, você me pede: {pedido}. "
                "Quer que eu faça sozinho nesse horário? É só dizer: cria a automação sugerida.",
                {"titulo": "Sugestão de automação", "destaque": pedido, "texto": f"Todo dia às {hora}. Diga \"cria a automação sugerida\"."},
                "info")
    return None


CRIAR_SUGERIDA = re.compile(r"^(?:jarvis[ ,]*)?(?:cria|criar|faz|fa[cç]a|pode criar|aceito|bora)\s+(?:a\s+|essa\s+)?"
                            r"automa[cç][aã]o(?:\s+sugerida|\s+que voc[eê] sugeriu)?[.!]*$", re.I)


def criar_sugerida():
    import automacoes
    s = _estado.get("ultima_sugestao")
    if not s:
        return "Não tenho sugestão de automação pendente, chefe."
    automacoes.salvar({"nome": s["pedido"].capitalize(), "tipo": "horario", "hora": s["hora"], "dias": list(range(7)),
                       "acoes": [s["pedido"]]})
    _estado["ultima_sugestao"] = None
    return f"Feito, chefe. Todo dia às {s['hora']} eu faço: {s['pedido']}. Dá pra mudar no painel de automações."
