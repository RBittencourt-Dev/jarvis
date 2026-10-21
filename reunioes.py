"""Agendar reunião no painel da SevenCode por voz, igual ao Radar (MarcarReuniao.tsx + /api/reunioes).

"agenda uma reunião com a LG Síndicos amanhã às 15h" → confirma → grava em sv_radar_reunioes,
põe o evento "reunião marcada" na linha do tempo do lead e o passa para "Reunião marcada".
Faltou algo? Ele pergunta (com quem, que dia, que horas). "Quem você sugere?" lista os leads
que responderam ou estão interessados.
"""
import re
import unicodedata
from datetime import datetime, time, timedelta

import httpx

import painel

PEDIDO = re.compile(r"^(?:jarvis[ ,]*)?(?:agenda|agendar|agende|marca|marcar|marque|cria|criar|bota|coloca|faz|fazer)\s+"
                    r"(?:uma\s+|a\s+|um[a]?\s+nova\s+)?(?:reuni[aã]o|call|chamada|meet)\b(?P<resto>.*)$", re.I)
# "cancela a reunião com o João", "desmarca a de amanhã", "remarca a reunião da equipe pra sexta às 8 da noite"
GESTAO = re.compile(r"^(?:jarvis[ ,]*)?(?P<acao>cancela|cancelar|cancele|desmarca|desmarcar|desmarque|apaga|tira|"
                    r"remarca|remarcar|remarque|muda|mudar|passa|passar|adia|adiar|transfere|transferir|troca|trocar|reagenda|reagendar|"
                    r"antecipa|empurra)\s+(?:a\s+|aquela\s+|essa\s+|minha\s+|o\s+hor[aá]rio\s+da\s+)?"
                    r"(?:reuni[aã]o|call|chamada|meet|(?=d[aeo]\s|de\s|com\s))(?P<resto>.*)$", re.I)
EQUIPE = re.compile(r"\b(?:com\s+(?:a\s+|o\s+|toda\s+a\s+|todo\s+o\s+)?(?:equipe|time|pessoal|galera|gurizada|turma|todo mundo|todos|s[oó]cios)|"
                    r"d[ae]\s+(?:equipe|time|s[oó]cios)|geral|interna)\b", re.I)
NOME_DA_REUNIAO = re.compile(r"\b(?:chamada|com o nome(?: de)?|com nome(?: de)?|de nome|com o t[ií]tulo|t[ií]tulo|sobre|pra falar (?:de|sobre)|"
                             r"pra tratar (?:de|do|da))\s+(?P<nome>.+?)" + r"(?=\s+(?:amanh[aã]|hoje|depois de|segunda|ter[cç]a|quarta|"
                             r"quinta|sexta|s[aá]bado|domingo|dia\s+\d|[àa]s?\s+\S+|com\s|pra\s|para\s|no\s|na\s|\d{1,2}\s*h)|[,.]|$)", re.I)
CANCELAR = re.compile(r"^(cancela|cancelar|deixa|deixa pra l[aá]|esquece|para|n[aã]o marca)\b", re.I)
PEDE_SUGESTAO = re.compile(r"\b(sugere|sugest[aã]o|sugira|quem (?:voc[eê] )?(?:sugere|acha)|lista|quais|me mostra|"
                           r"quem (?:t[aá]|est[aá]) interessado|n[aã]o sei)\b", re.I)

DIAS = {"segunda": 0, "terca": 1, "terça": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5, "sábado": 5, "domingo": 6}
NOMES_DOS_DIAS = ["seg.", "ter.", "qua.", "qui.", "sex.", "sáb.", "dom."]
NUMEROS = {"uma": 1, "um": 1, "duas": 2, "dois": 2, "tres": 3, "três": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7,
           "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12, "meio-dia": 12, "meio dia": 12}

FIM_DO_NOME = (r"(?=\s+(?:amanh[aã]|hoje|depois de amanh[aã]|segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo|"
               r"dia\s+\d|[àa]s?\s+\d|[àa]s?\s+(?:uma|duas|tr[eê]s|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|meio)|"
               r"(?:no|na|pelo|pela|por|de)\s+(?:meet|google|zoom|liga|telefone|escrit|presencial|\d)|"
               r"(?:durante|em)\s+\d|\d{1,2}\s*h|(?:pra|para|pro)\s+|\d{1,2}\s+da\s)|[,.]|$)")


def _sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def _dia(texto, hoje):
    t = _sem_acento(texto)
    if "depois de amanha" in t:
        return hoje + timedelta(days=2)
    if "amanha" in t:
        return hoje + timedelta(days=1)
    if re.search(r"\bhoje\b", t):
        return hoje
    m = re.search(r"\b(segunda|terca|quarta|quinta|sexta|sabado|domingo)\b", t)
    if m:
        alvo = DIAS[m.group(1)]
        dias = (alvo - hoje.weekday()) % 7 or 7  # "sexta" = a próxima sexta (nunca hoje)
        return hoje + timedelta(days=dias)
    m = re.search(r"\b(?:dia\s+)?(\d{1,2})/(\d{1,2})\b", t) or re.search(r"\bdia\s+(\d{1,2})\b", t)
    if m:
        dia = int(m.group(1))
        mes = int(m.group(2)) if m.lastindex and m.lastindex >= 2 else hoje.month
        ano = hoje.year
        try:
            d = hoje.replace(year=ano, month=mes, day=dia)
        except ValueError:
            return None
        if d < hoje:  # "dia 5" já passou neste mês: é o do mês que vem
            d = (d.replace(day=1) + timedelta(days=32)).replace(day=dia) if m.lastindex == 1 else d.replace(year=ano + 1)
        return d
    return None


HORAS_POR_EXTENSO = [  # os compostos primeiro ("vinte e uma" antes de "uma")
    ("vinte e tres", 23), ("vinte e duas", 22), ("vinte e dois", 22), ("vinte e uma", 21), ("vinte e um", 21), ("vinte", 20),
    ("dezenove", 19), ("dezoito", 18), ("dezessete", 17), ("dezesseis", 16), ("quinze", 15), ("quatorze", 14), ("catorze", 14),
    ("treze", 13), ("doze", 12), ("onze", 11), ("dez", 10), ("nove", 9), ("oito", 8), ("sete", 7), ("seis", 6), ("cinco", 5),
    ("quatro", 4), ("tres", 3), ("duas", 2), ("dois", 2), ("uma", 1), ("um", 1)]
MINUTOS_POR_EXTENSO = {"quarenta e cinco": 45, "meia": 30, "trinta": 30, "vinte": 20, "quinze": 15, "dez": 10, "cinco": 5}
_UMA_HORA = "|".join(p for p, _ in HORAS_POR_EXTENSO)


def _hora(texto):
    """Do jeito que ele fala: "8 da noite" = 20h, "oito e meia da manhã" = 8h30, "às 3" (sem dizer) = 15h,
    "20 horas", "20h30", "meio-dia", "meia-noite"."""
    t = _sem_acento(texto)
    if re.search(r"\bmeia[ -]noite\b", t):
        return time(0, 30 if re.search(r"meia[ -]noite e meia", t) else 0)
    if re.search(r"\bmeio[ -]dia\b", t):
        return time(12, 30 if re.search(r"meio[ -]dia e meia", t) else 0)
    # minutos por extenso logo depois da hora: "oito e meia", "8 e quinze" → "oito:30", "8:15"
    for palavra, n in MINUTOS_POR_EXTENSO.items():
        t = re.sub(rf"\b(\d{{1,2}}|{_UMA_HORA})\s+e\s+{palavra}\b", rf"\1:{n:02d}", t)
    t = re.sub(r"\b(\d{1,2})\s+e\s+([0-5]\d)(?:\s+minutos?)?\b", r"\1:\2", t)  # "às 8 e 40"
    # hora por extenso só onde é hora: "às oito", "oito horas", "oito da noite", "oito:30"
    for palavra, n in HORAS_POR_EXTENSO:
        t = re.sub(rf"(?<=\bas ){palavra}\b|(?<=\bdas ){palavra}\b|\b{palavra}(?=:\d\d|\s+horas?\b|\s+da (?:manha|tarde|noite|madrugada)\b)", str(n), t)
    padroes = [r"\b(\d{1,2})(?::|h)(\d{2})\b",                                      # 20:30, 20h30
               r"\b(\d{1,2})\s*(?:horas?\s+)?(?=da (?:manha|tarde|noite|madrugada))",  # 8 da noite, 8 horas da noite
               r"\b(?:[aà]s?|das)\s+(\d{1,2})\b(?!/)",                               # às 8, "a das 10"
               r"\b(\d{1,2})\s*(?:h|horas?)\b(?!\s+de (?:reuni|dura))"]               # 20h, 20 horas
    m = next((x for x in (re.search(p, t) for p in padroes) if x), None)
    if not m:
        return None
    h = int(m.group(1))
    minuto = int(m.group(2)) if m.lastindex and m.lastindex >= 2 else 0
    depois = t[m.end():m.end() + 30]
    if re.match(r"\s*(?:horas?\s+)?da (?:tarde|noite)", depois) and h < 12:
        h += 12
    elif re.match(r"\s*(?:horas?\s+)?da noite", depois) and h == 12:
        h = 0
    elif h < 7 and not re.match(r"\s*(?:horas?\s+)?da (?:manha|madrugada)", depois):
        h += 12  # "às 3" pra reunião de trabalho é 15h
    if not (0 <= h <= 23 and 0 <= minuto <= 59):
        return None
    return time(h, minuto)


def _duracao(texto):
    t = _sem_acento(texto)
    if "meia hora" in t:
        return 30
    m = re.search(r"\b(\d{1,3})\s*min", t)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(uma|1|duas|2)\s+horas?\b", t)
    if m and not re.search(r"\bas\s+(uma|duas)\b", t):
        return 60 if m.group(1) in ("uma", "1") else 120
    return None


def _onde(texto):
    t = _sem_acento(texto)
    if "zoom" in t:
        return "Zoom"
    if re.search(r"liga[cç]ao|telefone|por telefone", t):
        return "Ligação"
    if re.search(r"presencial|escritorio|pessoalmente", t):
        return "Presencial"
    if "meet" in t or "google" in t:
        return "Google Meet"
    return None


def _quem(resto):
    m = re.search(r"\bcom\s+(?:o\s+|a\s+|os\s+|as\s+)?(?:lead\s+)?(?P<quem>.+?)" + FIM_DO_NOME, resto, re.I)
    return m.group("quem").strip() if m else None


def _nome_da_reuniao(resto):
    m = NOME_DA_REUNIAO.search(resto)
    if not m:
        return None
    nome = re.sub(r"^(?:o|a|os|as|um|uma)\s+", "", m.group("nome").strip(" .,!?"), flags=re.I)
    return nome[:1].upper() + nome[1:]


def entender(texto):
    """Diálogo inicial: marcar, cancelar ou remarcar. None se não for pedido de reunião."""
    t = texto.strip()
    hoje = datetime.now().date()
    g = GESTAO.match(t)
    if g:
        acao = "cancelar" if re.match(r"cancel|desmarc|apaga|tira", g.group("acao"), re.I) else "remarcar"
        resto = g.group("resto")
        # "remarca a reunião com o João (de amanhã) pra sexta às 20h": antes do "pra" é QUAL, depois é o NOVO horário
        partes = re.split(r"\s+(?:pra|para|pro)\s+(?=(?:o\s+|a\s+)?(?:amanh|hoje|depois|segunda|ter|quarta|quinta|sexta|s[aá]bado|"
                          r"domingo|dia\s|semana|[àa]s?\s|\d|meio|meia|outro|outra|mais tarde|mais cedo))", resto, maxsplit=1, flags=re.I)
        qual, novo = (partes[0], partes[1]) if len(partes) == 2 else (resto, resto if acao == "remarcar" else "")
        equipe = bool(EQUIPE.search(qual))
        d = {"tipo": "reuniao", "acao": acao, "equipe": equipe,
             "quem": None if equipe else _quem(qual) or _quem(" " + qual.strip()),
             "filtro_dia": _dia(qual, hoje) if len(partes) == 2 or acao == "cancelar" else None,
             "dia": _dia(novo, hoje) if novo else None, "hora": _hora(novo) if novo else None}
        if not d["quem"] and not equipe:
            m = re.match(r"^\s*(?:d[aeo]s?|com)\s+(?:o\s+|a\s+)?(?P<n>.+?)" + FIM_DO_NOME, qual, re.I)
            if m and not _dia(m.group("n"), hoje):
                d["quem"] = m.group("n").strip()
        return d
    m = PEDIDO.match(t)
    if not m:
        return None
    resto = m.group("resto")
    equipe = bool(EQUIPE.search(resto) or re.search(r"\breuni[aã]o\s+(?:de|da)\s+(?:equipe|time|s[oó]cios)\b", t, re.I))
    return {"tipo": "reuniao", "acao": "marcar", "equipe": equipe, "titulo": _nome_da_reuniao(resto),
            "quem": None if equipe else _quem(resto), "dia": _dia(resto, hoje), "hora": _hora(resto),
            "duracao": _duracao(resto) or (60 if equipe else 30), "duracao_dita": bool(_duracao(resto)),
            "onde": _onde(resto) or "Google Meet"}


def _quando(d):
    inicio = datetime.combine(d["dia"], d["hora"])
    hoje = datetime.now().date()
    dia = ("hoje" if d["dia"] == hoje else "amanhã" if d["dia"] == hoje + timedelta(days=1)
           else f"{NOMES_DOS_DIAS[d['dia'].weekday()]}, {d['dia']:%d/%m}")
    return f"{dia} às {_hora_falada(inicio)}"


def _hora_falada(i):
    return f"{i:%H}h" if i.minute == 0 else f"{i:%H:%M}"


def _inicio_local(r):
    return datetime.fromisoformat(r["inicio"]).astimezone()


def _descrever(r):
    i = _inicio_local(r)
    hoje = datetime.now().date()
    dia = "hoje" if i.date() == hoje else "amanhã" if i.date() == hoje + timedelta(days=1) else \
        f"{NOMES_DOS_DIAS[i.weekday()]} {i:%d/%m}"
    return f"{r['lead_nome']}, {dia} às {_hora_falada(i)}"


def sugestoes():
    """Leads que responderam ou estão interessados, os mais recentes primeiro (sem reunião marcada ainda)."""
    todos = painel._ler("sv_leads", "select=id,nome,status,atualizado_em&status=in.(interessado,respondeu)&order=atualizado_em.desc&limit=6")
    return todos


def reunioes_marcadas():
    """As que ainda vão acontecer (ou começaram há pouco), na ordem."""
    desde = (datetime.now().astimezone() - timedelta(hours=2)).isoformat().replace("+", "%2B")
    return painel._ler("sv_radar_reunioes", f"select=id,lead_nome,inicio,duracao_min,participantes,status&status=eq.marcada"
                                            f"&inicio=gte.{desde}&order=inicio")


def _candidatas(d):
    lista = reunioes_marcadas()
    if d.get("equipe"):
        lista = [r for r in lista if len(r.get("participantes") or []) > 1 or _sem_acento(r["lead_nome"]).startswith("equipe")]
    elif d.get("quem"):
        alvo = _sem_acento(d["quem"])
        lista = [r for r in lista if all(p in _sem_acento(r["lead_nome"]) for p in alvo.split())]
    if d.get("filtro_dia"):
        lista = [r for r in lista if _inicio_local(r).date() == d["filtro_dia"]]
    return lista


def _passo_da_gestao(d):
    if not d.get("reuniao"):
        achadas = _candidatas(d)
        if not achadas:
            sobre = f" com {d['quem']}" if d.get("quem") else " da equipe" if d.get("equipe") else ""
            return "", f"Não achei nenhuma reunião marcada{sobre}, chefe."
        if len(achadas) > 1:
            d["etapa"], d["opcoes"] = "qual", achadas[:5]
            nomes = "; ".join(f"a {ORDEM_FALADA[i]}, {_descrever(r)}" for i, r in enumerate(achadas[:4]))
            return "pergunta", f"Tem {len(achadas)} marcadas: {nomes}. Qual delas?"
        d["reuniao"] = achadas[0]
    r = d["reuniao"]
    if d["acao"] == "cancelar":
        d["etapa"] = "confirmar"
        return "confirmar", f"Vou cancelar a reunião {_descrever(r)}. Quem estava nela vai deixar de ser avisado. Confirma?"
    atual = _inicio_local(r)
    if not d.get("dia") and not d.get("hora"):
        d["etapa"] = "novo"
        return "pergunta", f"A reunião {_descrever(r)}. Pra quando eu passo?"
    d["dia"] = d.get("dia") or atual.date()      # disse só a hora: mesmo dia
    d["hora"] = d.get("hora") or atual.time().replace(tzinfo=None)  # disse só o dia: mesma hora
    d["etapa"] = "confirmar"
    return "confirmar", f"Vou passar a reunião {_descrever(r)} para {_quando(d)}. Todo mundo é avisado no horário novo. Confirma?"


ORDEM_FALADA = ["primeira", "segunda", "terceira", "quarta", "quinta"]
ESCOLHA = {"primeira": 0, "primeiro": 0, "1": 0, "segunda": 1, "segundo": 1, "2": 1, "terceira": 2, "terceiro": 2, "3": 2,
           "quarta": 3, "quarto": 3, "4": 3, "ultima": -1, "ultimo": -1}


def proximo_passo(d):
    """Pergunta o que falta; com tudo, pede a confirmação."""
    if d.get("acao") in ("cancelar", "remarcar"):
        tipo, fala = _passo_da_gestao(d)
        if not tipo:
            d["etapa"] = "cancelado"
        return fala
    if d.get("equipe"):
        if not d.get("titulo"):
            d["etapa"] = "titulo"
            return "Reunião com a equipe toda. Qual o nome da reunião, chefe?"
        d.update(quem=f"Equipe · {d['titulo']}", interna=True, lead=None, lead_resolvido=True)
    if not d.get("quem"):
        d["etapa"] = "quem"
        return "Com quem é a reunião, chefe? Se for com todo mundo, diz com a equipe. Se quiser, eu sugiro os leads interessados."
    if not d.get("lead_resolvido"):
        achados = painel.achar_leads(d["quem"])
        equipe = [u for u in equipe_do_radar() if _sem_acento(d["quem"]) in _sem_acento(u["nome"])]
        if len(achados) == 1:
            d.update(lead=achados[0], quem=painel.nome_curto(achados[0]["nome"]), lead_resolvido=True)
        elif len(achados) > 1:
            d["etapa"] = "quem"
            nomes = ", ".join(painel.nome_curto(l["nome"]) for l in achados[:4])
            return f"Achei mais de um: {nomes}. Qual deles?"
        elif equipe:
            d.update(lead=None, interna=True, quem=equipe[0]["nome"], colega=equipe[0]["id"], lead_resolvido=True)
        else:
            d.update(lead=None, lead_resolvido=True)  # reunião avulsa: alguém que não está no Radar
    if not d.get("dia"):
        d["etapa"] = "dia"
        return f"Pra que dia é a reunião{' ' + d['titulo'] if d.get('titulo') else ' com ' + d['quem']}?"
    if not d.get("hora"):
        d["etapa"] = "hora"
        return "E que horas?"
    d["etapa"] = "confirmar"
    if d.get("equipe"):
        nomes = [painel.nome_curto(u["nome"]) for u in equipe_do_radar()]
        return (f"Vou marcar {d['titulo']}, {_quando(d)}, {d['duracao']} minutos, {d['onde']}, com a equipe toda: "
                f"{', '.join(nomes)}. Todos recebem o aviso. Confirma?")
    avulsa = "" if d.get("lead") or d.get("interna") else " Não achei no Radar, então fica como reunião avulsa."
    return f"Vou marcar reunião com {d['quem']}, {_quando(d)}, {d['duracao']} minutos, {d['onde']}.{avulsa} Confirma?"


def confirmacao(d):
    """(nome do botão de autorizar, detalhes) da confirmação na tela."""
    if d.get("acao") == "cancelar":
        return "cancelar reunião", {"reunião": _descrever(d["reuniao"])}
    if d.get("acao") == "remarcar":
        return "remarcar reunião", {"de": _descrever(d["reuniao"]), "para": _quando(d)}
    args = {"quando": _quando(d), "duração": f"{d['duracao']} min", "onde": d["onde"]}
    if d.get("equipe"):
        args["participantes"] = ", ".join(painel.nome_curto(u["nome"]) for u in equipe_do_radar())
    return f"marcar reunião {d['quem']}" if d.get("equipe") else f"marcar reunião com {d['quem']}", args


def responder(d, fala):
    if CANCELAR.match(fala.strip()) and d.get("etapa") != "qual":
        d["etapa"] = "cancelado"
        return "Tudo bem, chefe. Deixei a agenda como estava."
    etapa = d.get("etapa")
    hoje = datetime.now().date()
    if etapa == "qual":
        escolha = _sem_acento(re.sub(r"^(?:a|o)\s+", "", fala.strip(" .!?")))
        i = next((v for k, v in ESCOLHA.items() if re.search(rf"\b{k}\b", escolha)), None)
        if i is None:  # "a das 8", "a de sexta", "a do João"
            dia, hora = _dia(fala, hoje), _hora(fala)
            certas = [r for r in d["opcoes"] if (not dia or _inicio_local(r).date() == dia)
                      and (not hora or _inicio_local(r).time().replace(tzinfo=None, second=0) == hora)
                      and (dia or hora or any(p in _sem_acento(r["lead_nome"]) for p in escolha.split() if len(p) > 2))]
            if len(certas) == 1:
                d["reuniao"] = certas[0]
            else:
                return "Não peguei qual, chefe. Diz a primeira, a segunda, ou o horário."
        else:
            d["reuniao"] = d["opcoes"][i]
        if d["acao"] == "remarcar" and not (d.get("dia") or d.get("hora")):
            d["dia"], d["hora"] = _dia(fala, hoje) if i is not None else None, _hora(fala) if i is not None else None
        return proximo_passo(d)
    if etapa == "novo":
        d["dia"], d["hora"] = _dia(fala, hoje), _hora(fala)
        if not d["dia"] and not d["hora"]:
            return "Não entendi o novo horário. Fala tipo: sexta às 8 da noite, ou amanhã às 15h."
        return proximo_passo(d)
    if etapa == "titulo":
        d["titulo"] = re.sub(r"^(?:o nome [eé]|[eé]|vai ser|bota|coloca|chama|se chama)\s+", "", fala.strip(" .!?"), flags=re.I)
        d["titulo"] = d["titulo"][:1].upper() + d["titulo"][1:]
        d["dia"] = d.get("dia") or _dia(fala, hoje)
        d["hora"] = d.get("hora") or _hora(fala)
    elif etapa == "quem":
        if EQUIPE.search(" " + fala) or re.match(r"^(?:a\s+)?(?:equipe|time|pessoal|todo mundo|todos)\b", fala.strip(), re.I):
            d["equipe"] = True
            if not d.get("duracao_dita"):
                d["duracao"] = 60  # reunião de equipe: uma hora, a menos que ele diga outra coisa
            return proximo_passo(d)
        if PEDE_SUGESTAO.search(fala):
            lista = sugestoes()
            if not lista:
                return "Não tem nenhum lead interessado ou que respondeu agora. Me diz o nome de quem é."
            d["sugeridos"] = lista
            nomes = ", ".join(painel.nome_curto(l["nome"]) for l in lista[:4])
            return f"Os mais quentes agora: {nomes}. Com qual deles?"
        escolhido = re.sub(r"^(?:com\s+)?(?:o|a)?\s*(?:lead\s+)?", "", fala.strip(" .!"), flags=re.I)
        ordem = {"primeiro": 0, "primeira": 0, "segundo": 1, "segunda": 1, "terceiro": 2, "terceira": 2, "quarto": 3}
        if d.get("sugeridos") and _sem_acento(escolhido) in ordem and ordem[_sem_acento(escolhido)] < len(d["sugeridos"]):
            escolhido = d["sugeridos"][ordem[_sem_acento(escolhido)]]["nome"]
        d.update(quem=escolhido, lead_resolvido=False)
        # ele pode já ter dito o dia/hora junto ("com a LG amanhã às 3")
        d["dia"] = d.get("dia") or _dia(fala, hoje)
        d["hora"] = d.get("hora") or _hora(fala)
    elif etapa == "dia":
        d["dia"] = _dia(fala, hoje)
        d["hora"] = d.get("hora") or _hora(fala)
        if not d["dia"]:
            return "Não entendi o dia, chefe. Pode ser hoje, amanhã, sexta, dia 25…"
    elif etapa == "hora":
        d["hora"] = _hora(fala)
        if not d["hora"]:
            return "Não entendi a hora. Fala tipo: às 15h, ou às 8 da noite."
    return proximo_passo(d)


# ------------------------------------------------------------- gravar (igual ao Radar)

_equipe = {"em": 0, "lista": []}


def equipe_do_radar():
    """Quem pode estar numa reunião, como no Radar: ativo, e dono ou com a caixinha do Radar."""
    import time as relogio
    if relogio.time() - _equipe["em"] > 600:
        try:
            _equipe["lista"] = painel._ler("sv_usuarios", "select=id,nome,email,ativo,papel,features")
        except Exception:
            _equipe["lista"] = []
        _equipe["em"] = relogio.time()
    return [u for u in _equipe["lista"] if u.get("ativo", True)
            and (u.get("papel") == "dono" or "radar" in (u.get("features") or []))]


def _cabecalho():
    url, anon, token = painel._token()
    return url, {"apikey": anon, "Authorization": f"Bearer {token}", "Prefer": "return=minimal"}


def _email():
    import json
    return json.loads(painel.ARQUIVO_LOGIN.read_text(encoding="utf-8"))["email"]


def _mudar(reuniao_id, campos):
    """PATCH igual ao do Radar (/api/reunioes): grava quem mexeu e quando."""
    url, cab = _cabecalho()
    campos = {**campos, "atualizado_em": datetime.now().astimezone().isoformat(), "atualizado_por": _email()}
    r = httpx.patch(f"{url}/rest/v1/sv_radar_reunioes?id=eq.{reuniao_id}", headers=cab, json=campos, timeout=10)
    if r.status_code >= 400 and "avisado_5_em" in r.text:  # SQL do aviso de 5 min não rodado
        campos.pop("avisado_5_em", None)
        r = httpx.patch(f"{url}/rest/v1/sv_radar_reunioes?id=eq.{reuniao_id}", headers=cab, json=campos, timeout=10)
    r.raise_for_status()


def marcar(d):
    """Grava (ou cancela, ou remarca) em sv_radar_reunioes, como o Radar."""
    if d.get("acao") == "cancelar":
        _mudar(d["reuniao"]["id"], {"status": "cancelada"})
        return f"Pronto, cancelei a reunião {_descrever(d['reuniao'])}."
    if d.get("acao") == "remarcar":
        inicio = datetime.combine(d["dia"], d["hora"]).astimezone()
        # horário novo = os dois avisos (30 e 5 minutos antes) saem de novo, como no Radar
        _mudar(d["reuniao"]["id"], {"inicio": inicio.isoformat(), "status": "marcada", "avisado_em": None, "avisado_5_em": None})
        return f"Pronto, a reunião {d['reuniao']['lead_nome']} passou para {_quando(d)}."
    email = _email()
    equipe = equipe_do_radar()
    eu = next((u for u in equipe if u["email"].lower() == email.lower()), None)
    if d.get("equipe"):
        participantes = [u["id"] for u in equipe]  # todo mundo recebe o aviso
    else:
        participantes = [x for x in ((eu or {}).get("id"), d.get("colega")) if x]
    inicio = datetime.combine(d["dia"], d["hora"]).astimezone()
    lead = d.get("lead")
    corpo = {
        "lead_id": lead["id"] if lead else None,
        "lead_nome": d["quem"][:200],
        "whatsapp": "" if d.get("interna") else (lead.get("whatsapp") or "") if lead else "",
        "inicio": inicio.isoformat(),
        "duracao_min": d["duracao"],
        "onde": d["onde"],
        "pauta": d.get("titulo") or "",
        "participantes": list(dict.fromkeys(participantes)),
        "status": "marcada",
        "criado_por": email,
        "criado_por_nome": (eu or {}).get("nome", ""),
        "atualizado_por": email,
    }
    url, cab = _cabecalho()
    r = httpx.post(f"{url}/rest/v1/sv_radar_reunioes", headers=cab, json=corpo, timeout=10)
    r.raise_for_status()
    if lead:
        quando = f"{NOMES_DOS_DIAS[d['dia'].weekday()]}, {d['dia']:%d/%m} às {inicio:%H:%M}"
        andar = lead["status"] in ("novo", "contatado", "respondeu", "interessado")
        painel.registrar_reuniao_no_lead(lead["id"], quando, andar)
    if d.get("equipe"):
        return f"Pronto, {d['titulo']} marcada pra {_quando(d)} com a equipe toda. Todos vão ser avisados antes."
    return f"Pronto, reunião com {d['quem']} marcada pra {_quando(d)}. Já está na agenda do Radar."
