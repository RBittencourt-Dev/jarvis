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
NO = {"marketing": "no Marketing", "chromebook": "nos Chromebooks", "lab": "no Laboratório", "maker": "no Maker",
      "artes": "em Artes", "auditorio": "no Auditório"}
STATUS = {"pending": "pendente", "confirmed": "confirmado"}
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
_horarios = {"em": 0.0, "mapa": {}}


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


def _acesso():
    if _token["valor"] and time.time() < _token["ate"]:
        return _token["valor"]
    s = cofre.pegar("7planner")
    if not (isinstance(s, dict) and s.get("refresh")):
        raise LookupError("sem login")
    j = _auth({"refresh_token": s["refresh"]}, "refresh_token")
    s["refresh"] = j["refresh_token"]  # o Supabase troca o de renovação a cada uso
    cofre.guardar("7planner", s)
    _token.update(valor=j["access_token"], ate=time.time() + j.get("expires_in", 3600) - 60)
    return _token["valor"]


def _get(tabela, params, token=None):
    r = httpx.get(f"{URL}/rest/v1/{tabela}", params=params, timeout=20,
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
    horarios = _mapa_de_horarios()
    saida = []
    for chave in agendas or AGENDAS:
        tabela, nome = AGENDAS[chave]
        try:
            linhas = _get(tabela, {"select": "date,time_slot_id,time_slot_ids,description,status,user_id",
                                   "and": f"(date.gte.{inicio},date.lte.{fim})", "status": "neq.cancelled", "order": "date"})
        except httpx.HTTPStatusError:
            continue  # agenda que a conta dele não enxerga
        for a in linhas:
            ids = [i for i in (a.get("time_slot_ids") or [a.get("time_slot_id")]) if i in horarios]
            faixas = sorted(horarios[i] for i in ids)
            saida.append({"agenda": nome, "data": a["date"], "inicio": faixas[0][0] if faixas else "",
                          "fim": faixas[-1][1] if faixas else "", "descricao": (a.get("description") or "").strip(),
                          "status": STATUS.get(a.get("status"), a.get("status") or ""), "user_id": a.get("user_id")})
    pessoas = {x["user_id"] for x in saida if x["user_id"]}
    nomes = {}
    if pessoas:  # profiles à parte: user_id aponta pro auth.users, o banco não junta sozinho
        for p in _get("profiles", {"select": "id,full_name,sector", "id": "in.(" + ",".join(pessoas) + ")"}):
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


def entender(texto):
    t = texto.strip()
    if ABRIR.match(t):
        return {"acao": "abrir"}
    if CONECTAR.search(t):
        return {"acao": "conectar"}
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
    if not lista:
        return (f"Nada agendado {onde} {p['dito']}, chefe.",)
    n = len(lista)
    fala = f"{p['dito'].capitalize()}, {n} agendamento{'s' if n > 1 else ''} {onde}. "
    fala += ". ".join(_fala_de(x, varios) for x in lista[:6]) + "."
    if n > 6:
        fala += f" E mais {n - 6}, tão no cartão."
    linhas = [(f"{date.fromisoformat(x['data']):%d/%m} " if varios else "") + f"{x['inicio']}–{x['fim']} · {x['agenda']} · "
              f"{x['quem'] or '?'}" + (f" ({x['setor']})" if x["setor"] else "") + (f" — {x['descricao'][:80]}" if x["descricao"] else "")
              + (" · pendente" if x["status"] == "pendente" else "") for x in lista[:30]]
    return (fala, [{"titulo": f"7planner · {p['dito']}", "destaque": f"{n} agendamento{'s' if n > 1 else ''}", "linhas": linhas,
                    "links": [{"texto": "Abrir o 7planner", "url": SITE}]}])
