"""Perguntas de informação sobre o painel da SevenCode (só leitura): lead, reuniões da semana, leads por etapa."""
import re
from datetime import datetime, time, timedelta

import painel

SOBRE_LEAD = re.compile(
    r"^(?:me\s+)?(?:fala|conta|diz)\s+(?:mais\s+)?(?:d[oa]|sobre\s+(?:o|a)?)\s*(?:lead\s+)?(?P<nome>.+?)[?.!]*$|"
    r"^(?:como\s+(?:t[aá]|est[aá])|qual\s+(?:[eé]\s+)?a\s+situa[cç][aã]o\s+d[oa])\s+(?:o\s+|a\s+)?lead\s+(?P<nome2>.+?)[?.!]*$", re.I)
REUNIOES_DA_SEMANA = re.compile(r"\b(?:reuni[oõ]es da semana|pr[oó]ximas reuni[oõ]es|minhas reuni[oõ]es|agenda da semana|"
                                r"reuni[oõ]es (?:de )?amanh[aã]|o que tenho (?:essa|esta) semana)\b", re.I)
LEADS_DA_ETAPA = re.compile(r"\b(?:quais|quem s[aã]o|lista|me mostra)\s+(?:os\s+)?leads?\s+(?:que\s+)?(?:est[aã]o\s+|t[aã]o\s+)?"
                            r"(?P<etapa>responderam|respondeu|interessados?|novos?|contatados?|fechados?|perdidos?|em reuni[aã]o)\b", re.I)
ETAPA_DO_PEDIDO = {"responderam": "respondeu", "respondeu": "respondeu", "interessado": "interessado",
                   "interessados": "interessado", "novo": "novo", "novos": "novo", "contatado": "contatado",
                   "contatados": "contatado", "fechado": "fechado", "fechados": "fechado", "perdido": "perdido",
                   "perdidos": "perdido", "em reunião": "reuniao", "em reuniao": "reuniao"}
NOMES_DOS_DIAS = ["seg.", "ter.", "qua.", "qui.", "sex.", "sáb.", "dom."]


def entender(texto):
    """Qual consulta é ("lead", nome) / ("semana", None) / ("etapa", status); None se não for."""
    t = texto.strip()
    if REUNIOES_DA_SEMANA.search(t):
        return "semana", None
    m = LEADS_DA_ETAPA.search(t)
    if m:
        return "etapa", ETAPA_DO_PEDIDO[m.group("etapa").lower()]
    m = SOBRE_LEAD.match(t)
    if m and not re.search(r"\b(porthon|sevencode|caixa|reuni)", t, re.I):
        return "lead", (m.group("nome") or m.group("nome2")).strip()
    return None


def responder(consulta):
    tipo, valor = consulta
    if tipo == "semana":
        return reunioes_da_semana()
    if tipo == "etapa":
        return leads_da_etapa(valor)
    return sobre_lead(valor)


def sobre_lead(nome):
    achados = painel.achar_leads(nome)
    if not achados:
        return f"Não achei nenhum lead chamado {nome}, chefe.", []
    if len(achados) > 1:
        nomes = ", ".join(painel.nome_curto(l["nome"]) for l in achados[:4])
        return f"Tem mais de um: {nomes}. Qual deles?", []
    lead = painel._ler("sv_leads", f"select=nome,status,cidade,categoria,proximo_passo,proximo_em,historico&id=eq.{achados[0]['id']}")[0]
    nome = painel.nome_curto(lead["nome"])
    etapa = painel.NOME_DA_ETAPA.get(lead["status"], lead["status"].replace("_", " "))
    fala = f"{nome} está como {etapa}."
    if lead.get("proximo_passo"):
        fala += f" Próximo passo: {lead['proximo_passo']}."
    eventos = [e for e in (lead.get("historico") or []) if e.get("acao")][-3:]
    linhas = [f"Etapa: {etapa}"] + ([f"{lead['categoria']} · {lead['cidade']}"] if lead.get("cidade") else [])
    linhas += [f"{e['em'][8:10]}/{e['em'][5:7]} · {e['acao']}" + (f": {e['detalhe']}" if e.get("detalhe") else "") for e in eventos]
    return fala, [{"titulo": "Lead", "destaque": nome, "linhas": linhas}]


def reunioes_da_semana():
    inicio = datetime.combine(datetime.now().date(), time.min).astimezone()
    fim = inicio + timedelta(days=7)
    consulta = (f"select=lead_nome,inicio,onde&status=eq.marcada&inicio=gte.{inicio.isoformat()}"
                f"&inicio=lt.{fim.isoformat()}&order=inicio").replace("+", "%2B")
    lista = painel._ler("sv_radar_reunioes", consulta)
    if not lista:
        return "Nenhuma reunião marcada nos próximos 7 dias, chefe.", []
    quando = lambda r: datetime.fromisoformat(r["inicio"]).astimezone()
    linhas = [f"{NOMES_DOS_DIAS[quando(r).weekday()]} {quando(r):%d/%m %H:%M} · {painel.nome_curto(r['lead_nome'])}" for r in lista]
    p = lista[0]
    fala = (f"São {len(lista)} reuniões nos próximos 7 dias. A primeira: {linhas[0].split(' · ')[0]}, com {painel.nome_curto(p['lead_nome'])}."
            if len(lista) > 1 else f"Uma reunião nos próximos 7 dias: {linhas[0].replace(' · ', ', com ')}.")
    return fala, [{"titulo": "Reuniões · 7 dias", "destaque": f"{len(lista)} marcada" + ("s" if len(lista) > 1 else ""), "linhas": linhas}]


def leads_da_etapa(status):
    lista = painel._ler("sv_leads", f"select=nome&status=eq.{status}&order=atualizado_em.desc&limit=8")
    etapa = painel.NOME_DA_ETAPA.get(status, status)
    if not lista:
        return f"Nenhum lead como {etapa} agora, chefe.", []
    nomes = [painel.nome_curto(l["nome"]) for l in lista]
    fala = f"{len(lista)} como {etapa}: " + ", ".join(nomes[:4]) + ("." if len(nomes) <= 4 else ", e outros.")
    return fala, [{"titulo": f"Leads · {etapa}", "destaque": str(len(lista)), "linhas": nomes}]
