"""Leitura dos dados da 7 SevenCode (banco do painel). SÓ LEITURA: aqui só existe GET.

O Jarvis entra com o login do Rafael (e-mail e senha em login-painel.json, arquivo que
só existe no PC dele), igual ao painel no navegador: as permissões do banco continuam
valendo e ele nunca vê mais do que o Rafael vê. O modelo não recebe a senha nem o token,
só o texto pronto destas funções.
"""
import json
import re
import time as relogio
from collections import Counter
from datetime import datetime, time, timedelta
from pathlib import Path

import httpx

RAIZ = Path(__file__).parent
ARQUIVO_LOGIN = RAIZ / "login-painel.json"
ENV_DO_PAINEL = Path.home() / "Desktop" / "7 SevenCode" / "painel-7sevencode" / ".env.local"

STATUS = {"novo": "novos", "contatado": "contatados", "respondeu": "responderam", "reuniao": "em reunião",
          "proposta": "com proposta", "fechado": "fechados", "perdido": "perdidos"}

_sessao = {"token": None, "expira": 0}

# Endereço de produção do painel (pra abrir o documento criado no navegador/HUD).
BASE_PAINEL = "https://painel-7sevencode.vercel.app"

# O "papel do Word" que a folha em branco grava (lib/pagina-documento.ts → PAGINA_WORD): Calibri 11, margem Normal,
# entrelinha 1,08. É o que dá a formatação certa da 7code no documento novo.
PAGINA_WORD = {"margens": {"topo": 25, "baixo": 25, "esquerda": 30, "direita": 30},
               "fonte": "Calibri, Carlito, 'Segoe UI', Arial, sans-serif",
               "tamanho": 11, "entrelinha": 1.08, "depois": 8}


def configurado():
    return ARQUIVO_LOGIN.exists() and ENV_DO_PAINEL.exists()


def _publico():
    # endereço e chave pública (anon), as mesmas que vão para o navegador de qualquer visitante
    env = dict(re.findall(r"^([A-Z_]+)=(.*)$", ENV_DO_PAINEL.read_text(encoding="utf-8"), re.M))
    return env["NEXT_PUBLIC_SUPABASE_URL"].strip().strip('"'), env["NEXT_PUBLIC_SUPABASE_ANON_KEY"].strip().strip('"')


def _token():
    url, anon = _publico()
    if _sessao["token"] and relogio.time() < _sessao["expira"] - 60:
        return url, anon, _sessao["token"]
    login = json.loads(ARQUIVO_LOGIN.read_text(encoding="utf-8"))
    r = httpx.post(f"{url}/auth/v1/token?grant_type=password", headers={"apikey": anon},
                   json={"email": login["email"], "password": login["senha"]}, timeout=8)
    if r.status_code != 200:
        raise RuntimeError("Login do painel recusado: confira login-painel.json")
    dados = r.json()
    _sessao.update(token=dados["access_token"], expira=relogio.time() + dados.get("expires_in", 3600))
    return url, anon, _sessao["token"]


def _ler(tabela, consulta):
    url, anon, token = _token()
    r = httpx.get(f"{url}/rest/v1/{tabela}?{consulta}",
                  headers={"apikey": anon, "Authorization": f"Bearer {token}", "Range": "0-9999"}, timeout=8)
    r.raise_for_status()
    return r.json()


def criar_documento(titulo, corpo, tipo="livre", cliente_nome=None, cliente_documento=None, cliente_endereco=None):
    """Cria um documento no painel (tabela sv_documentos), como o Rafael, igual à 'folha em branco'.

    Escreve com o token DELE (login-painel.json): a RLS de sv_documentos exige estar em sv_usuarios, então nada aqui
    contorna a permissão — ele cria porque é da equipe. Nasce como rascunho (default da tabela); o número é dado pelo
    gatilho do banco. Grava a 'pagina' do Word (PAGINA_WORD) pra sair com a formatação certa; se a coluna não existir
    nesse banco, grava sem ela. Devolve {id, numero, ano, url} ou levanta exceção.
    """
    url, anon, token = _token()
    login = json.loads(ARQUIVO_LOGIN.read_text(encoding="utf-8"))
    cab = {"apikey": anon, "Authorization": f"Bearer {token}", "Content-Type": "application/json",
           "Prefer": "return=representation"}
    linha = {"tipo": tipo, "titulo": titulo, "corpo": corpo,
             "cliente_nome": (cliente_nome or None), "cliente_documento": (cliente_documento or None),
             "cliente_endereco": (cliente_endereco or None), "criado_por": login.get("email"),
             "pagina": PAGINA_WORD}
    r = httpx.post(f"{url}/rest/v1/sv_documentos", headers=cab, json=linha, timeout=15)
    if r.status_code >= 400 and "pagina" in (r.text or ""):
        linha.pop("pagina", None)  # banco sem a coluna 'pagina' (SQL de 02/10 não rodou): grava sem ela
        r = httpx.post(f"{url}/rest/v1/sv_documentos", headers=cab, json=linha, timeout=15)
    if r.status_code >= 300:
        raise RuntimeError(f"painel recusou ({r.status_code}): {(r.text or '')[:160]}")
    dados = r.json()
    criado = dados[0] if isinstance(dados, list) else dados
    doc_id = criado.get("id")
    return {"id": doc_id, "numero": criado.get("numero"), "ano": criado.get("ano"),
            "url": f"{BASE_PAINEL}/painel/documentos/{doc_id}"}


def reais(v):
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def caixa():
    lanc = _ler("sv_lancamentos", "select=data,tipo,valor")
    mes = datetime.now().strftime("%Y-%m")
    saldo = entrou = saiu = 0.0
    for l in lanc:
        v = float(l["valor"])
        do_mes = str(l["data"]).startswith(mes)
        if l["tipo"] == "entrada":
            saldo += v
            entrou += v if do_mes else 0
        else:
            saldo -= v
            saiu += v if do_mes else 0
    return {
        "fala": f"O caixa da SevenCode está em {reais(saldo)}. Neste mês entraram {reais(entrou)} e saíram {reais(saiu)}.",
        "cartao": {"titulo": "Caixa 7 SevenCode", "destaque": reais(saldo),
                   "linhas": [f"Entrou no mês: {reais(entrou)}", f"Saiu no mês: {reais(saiu)}"]},
    }


def leads():
    todos = _ler("sv_leads", "select=nome,status,proximo_em,proximo_passo")
    por_status = Counter(l["status"] for l in todos)
    fim_de_hoje = datetime.combine(datetime.now().date(), time.max).astimezone()
    retornos = [l for l in todos if l.get("proximo_em") and datetime.fromisoformat(l["proximo_em"]) <= fim_de_hoje]
    linhas = [f"{n} {STATUS.get(s, str(s).replace('_', ' ').replace('whatsapp', 'WhatsApp'))}"
              for s, n in por_status.most_common(4)]
    linhas += [f"Retornar: {l['nome']}" + (f" · {l['proximo_passo']}" if l.get("proximo_passo") else "") for l in retornos[:3]]
    fala = f"No radar há {len(todos)} leads, {por_status.get('novo', 0)} ainda novos."
    if retornos:
        fala += f" {len(retornos)} pedem retorno até hoje."
    return {"fala": fala, "cartao": {"titulo": "Radar de Leads", "destaque": f"{len(todos)} leads", "linhas": linhas}}


def reunioes_de_hoje():
    inicio = datetime.combine(datetime.now().date(), time.min).astimezone()
    fim = inicio + timedelta(days=1)
    consulta = (f"select=lead_nome,inicio,onde&status=eq.marcada"
                f"&inicio=gte.{inicio.isoformat()}&inicio=lt.{fim.isoformat()}&order=inicio").replace("+", "%2B")
    lista = _ler("sv_radar_reunioes", consulta)
    if not lista:
        return {"fala": "Nenhuma reunião marcada para hoje.",
                "cartao": {"titulo": "Reuniões de hoje", "destaque": "Agenda livre", "linhas": []}}
    hora = lambda r: datetime.fromisoformat(r["inicio"]).astimezone().strftime("%H:%M")
    p = lista[0]
    fala = (f"Hoje há {len(lista)} reuniões; a primeira é às {hora(p)}, com {p['lead_nome']}."
            if len(lista) > 1 else f"Hoje há uma reunião, às {hora(p)}, com {p['lead_nome']}.")
    return {"fala": fala, "cartao": {
        "titulo": "Reuniões de hoje", "destaque": f"{len(lista)} marcada" + ("s" if len(lista) > 1 else ""),
        "linhas": [f"{hora(r)} · {r['lead_nome']}" + (f" · {r['onde']}" if r.get("onde") else "") for r in lista]}}


# ------------------------------------------------------------- CRM do Radar

ETAPAS = {  # como ele fala → status do Radar
    "respondeu": "respondeu", "interessado": "interessado", "interessada": "interessado",
    "reuniao": "reuniao", "reunião": "reuniao", "reuniao marcada": "reuniao", "reunião marcada": "reuniao",
    "fechado": "fechado", "fechou": "fechado", "cliente": "fechado", "perdido": "perdido", "perdeu": "perdido",
    "nao perturbe": "nao_perturbe", "não perturbe": "nao_perturbe",
}
NOME_DA_ETAPA = {"respondeu": "respondeu", "interessado": "interessado", "reuniao": "reunião marcada",
                 "fechado": "fechado", "perdido": "perdido", "nao_perturbe": "não perturbe"}
ARQUIVO_AVISADOS = RAIZ / "leads-ja-avisados.json"


def nome_curto(nome):
    """Igual ao Radar (lib/mensagens.ts nomeCurto): "JORGE WAIT - Síndico Profissional" → "Jorge Wait".
    O nome do Maps vem cheio de palavra-chave; falado em voz alta fica estranho."""
    n = re.split(r"\s[|–—]\s|\s-\s|\s\|\s?|\s·\s", nome)[0].strip()
    n = re.sub(r"(\s+[A-ZÀ-Ú]{3,}){2,}$", "", n).strip() if not n.isupper() else n
    if len(n) > 48:
        n = re.sub(r"\s+\S*$", "", n[:48])
    if n.isupper():  # tudo em maiúscula soletra mal na voz
        n = " ".join(p if len(p) <= 3 else p.capitalize() for p in n.split())
    return n or nome


def achar_leads(nome):
    """Leads cujo nome contém o que ele disse (sem ligar pra maiúscula)."""
    todos = _ler("sv_leads", "select=id,nome,status,whatsapp,categoria,nicho,cidade,proximo_passo,responsavel")
    alvo = nome.lower().strip()
    exatos = [l for l in todos if l["nome"].lower() == alvo]
    return exatos or [l for l in todos if alvo in l["nome"].lower()]


def mudar_etapa(lead_id, status, detalhe=None):
    """Igual ao Radar (lib/banco.ts mudarStatus): troca o status e põe o evento na linha do tempo."""
    url, anon, token = _token()
    cab = {"apikey": anon, "Authorization": f"Bearer {token}"}
    atual = httpx.get(f"{url}/rest/v1/sv_leads?select=historico&id=eq.{lead_id}", headers=cab, timeout=8).json()
    if not atual:
        raise RuntimeError("Lead não encontrado.")
    login = json.loads(ARQUIVO_LOGIN.read_text(encoding="utf-8"))
    evento = {"em": datetime.now().astimezone().isoformat(), "acao": "status", "detalhe": status, "por": login["email"]}
    if detalhe:
        evento = {**evento, "detalhe": f"{status}: {detalhe}"}
    historico = ((atual[0].get("historico") or []) + [{**evento, "via": "Jarvis"}])[-200:]
    r = httpx.patch(f"{url}/rest/v1/sv_leads?id=eq.{lead_id}", headers={**cab, "Prefer": "return=minimal"},
                    json={"status": status, "historico": historico, "atualizado_em": datetime.now().astimezone().isoformat()},
                    timeout=8)
    r.raise_for_status()


def registrar_reuniao_no_lead(lead_id, quando, andar):
    """Igual ao MarcarReuniao do Radar: evento "reunião marcada" e, se ainda não passou disso, status reunião."""
    url, anon, token = _token()
    cab = {"apikey": anon, "Authorization": f"Bearer {token}"}
    atual = httpx.get(f"{url}/rest/v1/sv_leads?select=historico&id=eq.{lead_id}", headers=cab, timeout=8).json()
    if not atual:
        return
    email = json.loads(ARQUIVO_LOGIN.read_text(encoding="utf-8"))["email"]
    agora = datetime.now().astimezone().isoformat()
    eventos = [{"em": agora, "acao": "reunião marcada", "detalhe": quando, "por": email, "via": "Jarvis"}]
    campos = {"atualizado_em": agora}
    if andar:
        eventos.append({"em": agora, "acao": "status", "detalhe": "reuniao", "por": email, "via": "Jarvis"})
        campos["status"] = "reuniao"
    campos["historico"] = ((atual[0].get("historico") or []) + eventos)[-200:]
    httpx.patch(f"{url}/rest/v1/sv_leads?id=eq.{lead_id}", headers={**cab, "Prefer": "return=minimal"},
                json=campos, timeout=8).raise_for_status()


def respostas_novas():
    """Leads que passaram a "respondeu" desde a última olhada (a extensão do Radar é quem marca)."""
    responderam = _ler("sv_leads", "select=id,nome,categoria,cidade&status=eq.respondeu")
    ids = {l["id"] for l in responderam}
    if not ARQUIVO_AVISADOS.exists():
        # primeira vez: o que já estava respondido não é novidade
        ARQUIVO_AVISADOS.write_text(json.dumps(sorted(ids)), encoding="utf-8")
        return []
    avisados = set(json.loads(ARQUIVO_AVISADOS.read_text(encoding="utf-8")))
    novos = [l for l in responderam if l["id"] not in avisados]
    if novos:
        ARQUIVO_AVISADOS.write_text(json.dumps(sorted(avisados | ids)), encoding="utf-8")
    return novos


def tentar(funcao, titulo):
    """Se o banco falhar, o Jarvis avisa no cartão em vez de travar a abertura."""
    if not configurado():
        return {"fala": "", "cartao": {"titulo": titulo, "destaque": "Falta o seu login", "aguardando": True,
                                       "linhas": ["Preencha login-painel.json na minha pasta."]}}
    try:
        return funcao()
    except Exception as e:
        return {"fala": "", "cartao": {"titulo": titulo, "destaque": "Não consegui ler", "aguardando": True,
                                       "linhas": [str(e)[:140]]}}
