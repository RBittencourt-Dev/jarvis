"""7planner (fala-se "Seven Planner"): o app de agendas do colégio, lido pelo Jarvis.

Pedido dele (22/10, PC do colégio): "acessa o 7planner e me dá os dados da agenda".
Agendas (uma tabela cada no Supabase do 7planner): Marketing (appointments), Chromebooks, Laboratório, Maker, Artes
e Auditório. O Jarvis entra COMO ELE (o login dele no 7planner, digitado por ele na tela Configurações → 7planner):
troca email+senha por um token na hora e guarda só o token de renovação no cofre do PC (criptografado). A senha não
fica guardada. Vê o que a conta dele vê (as regras do banco valem igual ao site). Nada é alterado: só leitura.
Voz: "o que tem no 7planner amanhã", "agenda do auditório hoje", "quem agendou o laboratório segunda",
"agendamentos da semana no seven planner", "abre o 7planner".
"""
import re
import threading
import time
import unicodedata
from datetime import date, timedelta

import httpx

import cofre

DEMORA = True
URL = "https://ppanbgceqrepbhagzqre.supabase.co"
# chave pública do app (papel "anon", a mesma que vai no site pra qualquer um): sozinha não lê nada, precisa do login
ANON = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBwYW5iZ2NlcXJlcGJoYWd6cXJlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM3NzM0MTgsImV4cCI6MjA4OTM0OTQxOH0.OjCDR73NmPB0fdqrWk1wrgAK9cu72IpsitQgBDUE32o"
SITE = "https://7planner-system.vercel.app"
AGENDAS = {"marketing": ("appointments", "Marketing"), "chromebook": ("chromebook_appointments", "Chromebooks"),
           "lab": ("lab_appointments", "Laboratório"), "maker": ("maker_appointments", "Maker"),
           "artes": ("artes_appointments", "Artes"), "auditorio": ("auditorio_appointments", "Auditório")}
NO = {"marketing": "no Marketing", "chromebook": "na T.I (Chromebooks)", "lab": "no Laboratório", "maker": "no Maker",
      "artes": "em Artes", "auditorio": "no Auditório"}
STATUS = {"pending": "pendente", "confirmed": "confirmado"}
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
_horarios = {"em": 0.0, "mapa": {}}
falhas = []  # agendas que não responderam na última leitura
_vigia = {"espera": 0.0}  # até quando o vigiar fica quieto depois de um erro (evita martelar toda hora)


def _sa(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


# ------------------------------------------------------------------ login (token no cofre, nunca a senha)
def conectado():
    s = cofre.pegar("7planner")
    return isinstance(s, dict) and bool(s.get("refresh"))


def quem():
    s = cofre.pegar("7planner") or {}
    return {"conectado": conectado(), "email": s.get("email"), "nome": s.get("nome")}


def _auth(corpo, tipo):
    r = httpx.post(f"{URL}/auth/v1/token?grant_type={tipo}", json=corpo, timeout=15,
                   headers={"apikey": ANON, "Content-Type": "application/json"})
    if r.status_code >= 400:
        msg = (r.json() if r.headers.get("content-type", "").startswith("application/json") else {}).get("error_description") or r.text[:120]
        raise PermissionError("Email ou senha não conferem." if "invalid" in msg.lower() else msg)
    return r.json()


def entrar(email, senha):
    j = _auth({"email": email.strip(), "password": senha}, "password")
    s = {"refresh": j["refresh_token"], "email": email.strip(), "nome": None}
    try:
        p = _get("profiles", {"select": "full_name,role", "id": f"eq.{j['user']['id']}"}, j["access_token"])
        if p:
            s["nome"], s["papel"] = p[0].get("full_name"), p[0].get("role")
    except Exception:
        pass
    cofre.guardar("7planner", s)
    _token.update(valor=j["access_token"], ate=time.time() + j.get("expires_in", 3600) - 60)
    return quem()


def sair():
    cofre.apagar("7planner")
    _token.update(valor=None, ate=0)


_token = {"valor": None, "ate": 0.0}


_trava_token = threading.Lock()


def _acesso():
    with _trava_token:  # o aviso de 1 em 1 min e uma pergunta ao mesmo tempo: renova uma vez só
        return _acesso_sem_trava()


def _acesso_sem_trava():
    if _token["valor"] and time.time() < _token["ate"]:
        return _token["valor"]
    s = cofre.pegar("7planner")
    if not (isinstance(s, dict) and s.get("refresh")):
        raise LookupError("sem login")
    try:
        j = _auth({"refresh_token": s["refresh"]}, "refresh_token")
    except PermissionError:
        # refresh inválido/vencido (ou corrompido por corrida antiga): desconecta de vez pra pedir reconexão,
        # em vez de tentar o mesmo token podre toda leitura e todo minuto no vigiar.
        cofre.apagar("7planner")
        _token.update(valor=None, ate=0)
        raise PermissionError("O acesso ao 7planner venceu; reconecta na aba 7planner.")
    s["refresh"] = j["refresh_token"]  # o Supabase troca o de renovação a cada uso
    cofre.guardar("7planner", s)
    _token.update(valor=j["access_token"], ate=time.time() + j.get("expires_in", 3600) - 60)
    return _token["valor"]


def _get(tabela, params, token=None):
    r = httpx.get(f"{URL}/rest/v1/{tabela}", params=params, timeout=httpx.Timeout(10, connect=5),
                  headers={"apikey": ANON, "Authorization": f"Bearer {token or _acesso()}"})
    r.raise_for_status()
    return r.json()


# ------------------------------------------------------------------ leitura
def _mapa_de_horarios():
    if time.time() - _horarios["em"] > 6 * 3600 or not _horarios["mapa"]:
        _horarios["mapa"] = {h["id"]: (h["start_time"][:5], h["end_time"][:5])
                             for h in _get("time_slots", {"select": "id,start_time,end_time"})}
        _horarios["em"] = time.time()
    return _horarios["mapa"]


def agendamentos(inicio, fim, agendas=None):
    """[{agenda, data, inicio, fim, quem, setor, descricao, status}] de inicio a fim (datas), sem os cancelados."""
    from concurrent.futures import ThreadPoolExecutor
    token = _acesso()  # um token só pra todas: renovar em paralelo queimaria o refresh (o Supabase troca a cada uso)
    horarios = _mapa_de_horarios()
    saida = []
    falhas.clear()

    def ler(chave):
        try:
            return chave, _get(AGENDAS[chave][0], {"select": "date,time_slot_id,time_slot_ids,description,status,user_id",
                                                   "and": f"(date.gte.{inicio},date.lte.{fim})", "status": "neq.cancelled",
                                                   "order": "date"}, token)
        except httpx.HTTPStatusError:
            return chave, []  # agenda que a conta dele não enxerga
        except httpx.HTTPError:
            falhas.append(AGENDAS[chave][1])  # demorou/caiu: segue com as outras e avisa
            return chave, []

    with ThreadPoolExecutor(6) as pool:  # as 6 agendas juntas: 1 espera em vez de 6
        lidas = list(pool.map(ler, agendas or AGENDAS))
    for chave, linhas in lidas:
        nome = AGENDAS[chave][1]
        for a in linhas:
            ids = [i for i in (a.get("time_slot_ids") or [a.get("time_slot_id")]) if i in horarios]
            faixas = sorted(horarios[i] for i in ids)
            saida.append({"agenda": nome, "data": a["date"], "inicio": faixas[0][0] if faixas else "",
                          "fim": faixas[-1][1] if faixas else "", "descricao": (a.get("description") or "").strip(),
                          "status": STATUS.get(a.get("status"), a.get("status") or ""), "user_id": a.get("user_id")})
    pessoas = {x["user_id"] for x in saida if x["user_id"]}
    nomes = {}
    if pessoas:  # profiles à parte: user_id aponta pro auth.users, o banco não junta sozinho
        for p in _get("profiles", {"select": "id,full_name,sector", "id": "in.(" + ",".join(pessoas) + ")"}, token):
            nomes[p["id"]] = (p.get("full_name") or "", p.get("sector") or "")
    for x in saida:
        x["quem"], x["setor"] = nomes.get(x.pop("user_id"), ("", ""))
    return sorted(saida, key=lambda x: (x["data"], x["inicio"], x["agenda"]))


# ------------------------------------------------------------------ por voz
SETE = r"(?:7|sete|seven|sevem|seve)\s*-?\s*plann?er"
SALAS = {"auditorio": r"audit[oó]rio", "lab": r"laborat[oó]rio|\blab\b", "maker": r"\bmaker\b|sala\s+maker",
         "artes": r"\bartes?\b|sala\s+de\s+artes", "chromebook": r"chrome\s*books?|cromebuc?k?s?", "marketing": r"\bmarketing\b"}
AGENDA_DE_SALA = re.compile(r"\b(?:agenda|agendamentos?|agendad[oa]s?|reservas?|reservad[oa]|marcad[oa]|ocupad[oa]|livre|quem\s+(?:vai\s+usar|usa|agendou|reservou|pegou))\b", re.I)
ABRIR = re.compile(r"^(?:jarvis[ ,]*)?(?:abre|abrir|entra\s+n[oa]|acessa|vai\s+n[oa])\s+(?:o\s+)?(?:site\s+d[oa]\s+)?" + SETE + r"[.!?]*$", re.I)
CONECTAR = re.compile(r"\b(?:conecta|conectar|liga|ligar|configura|configurar|loga|logar|entra)\b.*\b" + SETE, re.I)


def _datas(t):
    """(inicio, fim, como dizer) do que ele falou; sem data = hoje."""
    hoje = date.today()
    t = _sa(t)
    fim_do_mes = lambda d: (d.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    if re.search(r"\bmes\s+que\s+vem|proximo\s+mes", t):
        ini = fim_do_mes(hoje) + timedelta(days=1)
        return ini, fim_do_mes(ini), "no mês que vem"
    if re.search(r"\bmes\b", t):
        return hoje, fim_do_mes(hoje), "nesse mês"
    if re.search(r"semana\s+que\s+vem|proxima\s+semana", t):
        ini = hoje + timedelta(days=7 - hoje.weekday())
        return ini, ini + timedelta(days=4), "na semana que vem"
    if re.search(r"\b(?:essa|esta|nessa|nesta|da|a)\s+semana\b|\bsemana\b", t):
        return hoje, hoje + timedelta(days=(4 - hoje.weekday()) if hoje.weekday() < 5 else 6), "nessa semana"
    if "depois de amanha" in t:
        d = hoje + timedelta(days=2)
        return d, d, "depois de amanhã"
    if "amanha" in t:
        d = hoje + timedelta(days=1)
        return d, d, "amanhã"
    if "ontem" in t:
        d = hoje - timedelta(days=1)
        return d, d, "ontem"
    m = re.search(r"\bdia\s+(\d{1,2})(?:\s*(?:/|de)\s*(\d{1,2}))?\b", t)
    if m:
        dia, mes = int(m.group(1)), int(m.group(2) or hoje.month)
        try:
            d = date(hoje.year, mes, dia)
            if not m.group(2) and d < hoje:
                d = date(hoje.year + (mes == 12), mes % 12 + 1, dia)
            return d, d, f"no dia {d:%d/%m}"
        except ValueError:
            pass
    for i, nome in enumerate(_sa(x) for x in DIAS):
        if re.search(r"\b" + nome[:5], t):
            d = hoje + timedelta(days=(i - hoje.weekday()) % 7)
            return d, d, ("hoje" if d == hoje else f"na {DIAS[i]}" if i < 5 else f"no {DIAS[i]}")
    return hoje, hoje, "hoje"


# PC do colégio (pedido de 24/10): lá "agenda"/"agendamento" é sempre o 7planner, sem precisar dizer o nome.
# Vale quando o 7planner tá conectado e o painel da SevenCode (agenda de reuniões do Radar) não existe neste PC.
AGENDA_SOLTA = re.compile(r"\b(?:agenda|agendamentos?|agendad[oa]s?|reservas?|reservad[oa]s?)\b", re.I)
CRIAR = re.compile(r"^(?:jarvis[ ,]*)?(?:agenda|agendar|agende|marca|marcar|marque|cria|criar|reserva|reservar)\s+(?:um|uma|pra|para|o|a)\b", re.I)


def agenda_padrao():
    import painel
    return conectado() and not painel.configurado()


def entender(texto):
    t = texto.strip()
    if ABRIR.match(t):
        return {"acao": "abrir"}
    if CONECTAR.search(t):
        return {"acao": "conectar"}
    if AGENDA_SOLTA.search(t) and not CRIAR.match(t) and agenda_padrao():
        salas = [k for k, rx in SALAS.items() if re.search(rx, t, re.I)]
        if re.search(r"\bt\.?\s?i\b", t, re.I) and "chromebook" not in salas:
            salas.append("chromebook")
        ini, fim, dito = _datas(t)
        return {"acao": "agenda", "inicio": ini.isoformat(), "fim": fim.isoformat(), "dito": dito, "salas": salas or None}
    do_sete = re.search(r"\b" + SETE + r"\b", t, re.I)
    salas = [k for k, rx in SALAS.items() if re.search(rx, t, re.I)]
    if do_sete or (salas and AGENDA_DE_SALA.search(t)):
        if salas == ["marketing"] and not do_sete and not re.search(r"\bagenda\b", t, re.I):
            return None
        ini, fim, dito = _datas(t)
        return {"acao": "agenda", "inicio": ini.isoformat(), "fim": fim.isoformat(), "dito": dito, "salas": salas or None}
    return None


def _fala_de(x, varios_dias):
    h, _, m = (x["inicio"] or ":").partition(":")
    hora = f"{int(h)}h{'' if m == '00' else m}" if h.isdigit() else ""
    quando = (f"{DIAS[date.fromisoformat(x['data']).weekday()]}, " if varios_dias else "") + hora
    o_que = f", {x['descricao'][:60]}" if x["descricao"] else ""
    return f"{x['agenda']}, {quando}, {x['quem'].split(' ')[0] if x['quem'] else 'alguém'}{o_que}"


def executar(p):
    if p["acao"] == "abrir":
        import navegadores
        navegadores.abrir(SITE)
        return ("Abrindo o 7planner, chefe.",)
    if p["acao"] == "conectar" or not conectado():
        return ("Pra eu ler o 7planner neste PC, abre as Configurações, aba 7planner, e entra com teu email e senha "
                "de lá. Eu guardo só uma chave de acesso, criptografada, a senha não fica salva."
                if not conectado() else f"O 7planner já tá conectado com {quem()['email']}, chefe.",)
    try:
        lista = agendamentos(p["inicio"], p["fim"], p.get("salas"))
    except LookupError:
        return ("O 7planner não tá conectado neste PC. Configurações, aba 7planner.",)
    except PermissionError:
        return ("O acesso ao 7planner venceu. Entra de novo em Configurações, aba 7planner.",)
    except httpx.HTTPError as e:
        return (f"Não consegui falar com o 7planner agora: {str(e)[:80]}",)
    onde = " e ".join(NO[s] for s in p["salas"]) if p.get("salas") else "no 7planner"
    varios = p["inicio"] != p["fim"]
    aviso = f" Não consegui ler {', '.join(falhas)} agora, a internet tá lenta." if falhas else ""
    if not lista:
        return (f"Nada agendado {onde} {p['dito']}, chefe.{aviso}",)
    n = len(lista)
    fala = f"{p['dito'].capitalize()}, {n} agendamento{'s' if n > 1 else ''} {onde}. "
    fala += ". ".join(_fala_de(x, varios) for x in lista[:6]) + "."
    if n > 6:
        fala += f" E mais {n - 6}, tão no cartão."
    fala += aviso
    linhas = [(f"{date.fromisoformat(x['data']):%d/%m} " if varios else "") + f"{x['inicio']}–{x['fim']} · {x['agenda']} · "
              f"{x['quem'] or '?'}" + (f" ({x['setor']})" if x["setor"] else "") + (f" — {x['descricao'][:80]}" if x["descricao"] else "")
              + (" · pendente" if x["status"] == "pendente" else "") for x in lista[:30]]
    return (fala, [{"titulo": f"7planner · {p['dito']}", "destaque": f"{n} agendamento{'s' if n > 1 else ''}", "linhas": linhas,
                    "links": [{"texto": "Abrir o 7planner", "url": SITE}]}])


# ------------------------------------------------------------------ avisos sozinho (pedido de 24/10, PC do colégio)
# 1) Todo dia, a partir das 7h (ou na hora de "planner_avisos.resumo"), fala a agenda do dia — uma vez só; se a
#    abertura do PC já falou, não repete (marcar_resumo_de_hoje).
# 2) Marketing e T.I (a agenda de Chromebooks, que o 7planner chama de "Agenda de Chromebooks — T.I"): avisa 10 min
#    antes de cada agendamento. Agendas e minutos mudam em config.json → "planner_avisos".
import json
from datetime import datetime
from pathlib import Path

ESTADO = Path(__file__).parent / "dados" / "planner-avisados.json"
_cache = {"em": 0.0, "dia": "", "lista": []}
ONDE_AVISO = {"chromebook": "na T.I, dos Chromebooks"}


def _config():
    try:
        c = json.loads((Path(__file__).parent / "config.json").read_text(encoding="utf-8")).get("planner_avisos") or {}
    except (OSError, ValueError):
        c = {}
    return {"agendas": c.get("agendas") or ["marketing", "chromebook"], "minutos": int(c.get("minutos", 10)),
            "resumo": c.get("resumo", "07:00"), "ligado": c.get("ligado", True)}


def _estado():
    try:
        e = json.loads(ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        e = {}
    hoje = date.today().isoformat()
    if e.get("dia") != hoje:
        e = {"dia": hoje, "resumo": False, "avisados": []}
    return e


def _gravar(e):
    ESTADO.parent.mkdir(exist_ok=True)
    ESTADO.write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")


def marcar_resumo_de_hoje():
    e = _estado()
    e["resumo"] = True
    _gravar(e)


def _de_hoje(agendas):
    hoje = date.today().isoformat()
    if time.time() - _cache["em"] > 300 or _cache["dia"] != hoje:  # 5 min: pega agendamento marcado em cima da hora
        _cache.update(em=time.time(), dia=hoje, lista=agendamentos(hoje, hoje, agendas))
    return _cache["lista"]


def vigiar(agora=None):
    """[(fala, cartão)] do que avisar agora. Chamado a cada minuto pelo servidor; nunca estoura o laço."""
    cfg = _config()
    if not cfg["ligado"] or not conectado() or time.time() < _vigia["espera"]:
        return []
    try:
        return _vigiar(cfg, agora or datetime.now())
    except PermissionError:
        return []  # desconectou (token vencido): fica quieto até ele reconectar
    except Exception as e:
        _vigia["espera"] = time.time() + 300  # deu ruim (internet?): não insiste todo minuto
        print("7planner vigiar falhou:", str(e)[:120])
        return []


def _vigiar(cfg, agora):
    e, saida = _estado(), []
    if not e["resumo"] and agora.strftime("%H:%M") >= cfg["resumo"]:
        e["resumo"] = True
        _gravar(e)
        r = executar(entender("agenda do 7planner hoje"))
        if agora.weekday() < 5 or len(r) > 1:  # fim de semana vazio: fica quieto
            saida.append((r[0], r[1][0] if len(r) > 1 else None))
    for x in _de_hoje(cfg["agendas"]):
        if not x["inicio"]:
            continue
        comeca = datetime.combine(agora.date(), datetime.strptime(x["inicio"], "%H:%M").time())
        falta = (comeca - agora).total_seconds() / 60
        chave = f"{x['agenda']}|{x['inicio']}|{x['quem']}|{x['descricao'][:30]}"
        if 0 < falta <= cfg["minutos"] and chave not in e["avisados"]:
            e["avisados"].append(chave)
            _gravar(e)
            n = round(falta)
            quem_ = x["quem"].split(" ")[0] if x["quem"] else "alguém"
            o_que = f": {x['descricao'][:70]}" if x["descricao"] else ""
            fala = (f"Chefe, daqui a {n} minuto{'s' if n != 1 else ''} tem agendamento {ONDE_AVISO.get(_chave_da(x['agenda'])) or NO.get(_chave_da(x['agenda']), x['agenda'])}"
                    f", das {x['inicio']} às {x['fim']}, com {quem_}{o_que}.")
            saida.append((fala, {"titulo": f"7planner · em {n} min", "destaque": x["agenda"],
                                 "linhas": [f"{x['inicio']}–{x['fim']} · {x['quem'] or '?'}" + (f" ({x['setor']})" if x["setor"] else ""),
                                            *([x["descricao"][:120]] if x["descricao"] else [])],
                                 "links": [{"texto": "Abrir o 7planner", "url": SITE}]}))
    return saida


def _chave_da(nome):
    return next((k for k, (_, n) in AGENDAS.items() if n == nome), "")


def resgatar_login_trocado():
    """PC do colégio (24/10): ele colou o email e a senha do 7planner no login-painel.json. Se o 7planner ainda não
    tá conectado e esse login entra no 7planner, conecta por ele (guarda só o token, no cofre) e apaga o arquivo,
    pra senha não ficar em texto puro. Só mexe se o login NÃO for do painel de verdade (o painel não existe neste PC)."""
    import painel
    arq = painel.ARQUIVO_LOGIN
    if conectado() or not arq.exists() or painel.ENV_DO_PAINEL.exists():
        return None
    try:
        l = json.loads(arq.read_text(encoding="utf-8"))
        email, senha = l.get("email", ""), l.get("senha", "")
        if not email or not senha or "exemplo" in email:
            return None
        entrar(email, senha)
    except Exception as e:
        return f"login-painel.json não entrou no 7planner: {str(e)[:80]}"
    arq.unlink()
    return f"7planner conectado com {email} (estava no login-painel.json)"
