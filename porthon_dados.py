"""Números do Porthon (produção), lidos com o login do Rafael. SÓ LEITURA e SÓ CONTAGENS.

Nenhum nome, apartamento, telefone ou foto de morador sai daqui: o Jarvis fala "3 encomendas
pendentes no Ventos do Sul", nunca de quem são. É dado real de condomínio (LGPD).
"""
import json
import re
import time as relogio
from collections import Counter
from datetime import datetime
from pathlib import Path

import httpx

RAIZ = Path(__file__).parent
ARQUIVO_LOGIN = RAIZ / "login-porthon.json"
ENV = Path.home() / "Desktop" / "Porthon-System" / "lobby" / ".env.local"
_sessao = {"token": None, "expira": 0}

ASSUNTO = re.compile(r"\b(?:encomendas?|pacotes?|ocorr[eê]ncias?|tarefas?|ordens? de servi[cç]o|reservas?|sal[aã]o de festas)\b", re.I)
QUANTIDADE = re.compile(r"\b(?:quant[oa]s?|tem|t[eê]m|h[aá]|alguma?|pendentes?|abert[oa]s?|hoje|aguardando|parad[oa]s?)\b", re.I)
GERAL = re.compile(r"\b(?:como (?:t[aá]|est[aá]) o (?:ventos do sul|condom[ií]nio|pr[eé]dio)|resumo do p[oó]rth?on|"
                   r"n[uú]meros do p[oó]rth?on|movimento (?:do|no) (?:condom[ií]nio|p[oó]rth?on))\b", re.I)


class _Pergunta:
    """"Quantas encomendas pendentes?" é número; "como funciona a retirada de encomenda?" é conhecimento."""

    @staticmethod
    def search(texto):
        if re.search(r"\bcomo funciona|o que [eé]|explica|pra que serve|por que\b", texto, re.I):
            return None
        return GERAL.search(texto) or (ASSUNTO.search(texto) and QUANTIDADE.search(texto))


PERGUNTA = _Pergunta()


def configurado():
    return ARQUIVO_LOGIN.exists()


def _publico():
    env = dict(re.findall(r"^([A-Z_]+)=(.*)$", ENV.read_text(encoding="utf-8"), re.M))
    return env["NEXT_PUBLIC_SUPABASE_URL"].strip().strip('"'), env["NEXT_PUBLIC_SUPABASE_ANON_KEY"].strip().strip('"')


def _token():
    url, anon = _publico()
    if _sessao["token"] and relogio.time() < _sessao["expira"] - 60:
        return url, anon, _sessao["token"]
    login = json.loads(ARQUIVO_LOGIN.read_text(encoding="utf-8"))
    r = httpx.post(f"{url}/auth/v1/token?grant_type=password", headers={"apikey": anon},
                   json={"email": login["email"], "password": login["senha"]}, timeout=8)
    if r.status_code != 200:
        raise RuntimeError("Login do Porthon recusado: confira login-porthon.json")
    dados = r.json()
    _sessao.update(token=dados["access_token"], expira=relogio.time() + dados.get("expires_in", 3600))
    return url, anon, _sessao["token"]


def _ler(tabela, consulta):
    url, anon, token = _token()
    r = httpx.get(f"{url}/rest/v1/{tabela}?{consulta}",
                  headers={"apikey": anon, "Authorization": f"Bearer {token}", "Range": "0-9999"}, timeout=10)
    r.raise_for_status()
    return r.json()


def _contar(tabela, filtro):
    """Contagem por condomínio. Só pede condominio_id: nenhuma outra coluna sai do banco."""
    linhas = _ler(tabela, f"select=condominio_id&{filtro}")
    return Counter(l["condominio_id"] for l in linhas)


def resumo():
    condominios = {c["id"]: c["nome"] for c in _ler("condominios", "select=id,nome&demonstracao=is.false&ativo=is.true")}
    hoje = datetime.now().strftime("%Y-%m-%d")
    contagens = {
        "encomendas aguardando retirada": _contar("encomendas", "status=in.(pendente,interceptada)"),
        "ocorrências abertas": _contar("ocorrencias", "status=in.(aberta,em_andamento)"),
        "tarefas abertas": _contar("tarefas", "status=in.(pendente,em_andamento)"),
        "reservas hoje": _contar("reservas", f"data=eq.{hoje}"),
    }
    linhas, falas = [], []
    for cid, nome in condominios.items():
        partes = [f"{n[cid]} {rotulo}" for rotulo, n in contagens.items() if n.get(cid)]
        linhas.append(f"{nome}: " + (", ".join(partes) if partes else "tudo em dia"))
        if partes:
            falas.append(f"no {nome}, " + ", ".join(partes))
    fala = ("No Porthon, " + "; ".join(falas) + ".") if falas else "No Porthon está tudo em dia, chefe."
    return fala, [{"titulo": "Porthon · agora", "destaque": f"{len(condominios)} condomínio" + ("s" if len(condominios) != 1 else ""),
                   "linhas": linhas}]
