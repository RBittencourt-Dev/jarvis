"""Gerar credencial de morador no Porthon por voz — o Jarvis conta TUDO e só faz depois do "sim".

"gera a credencial do João, bloco 14, apto 203" → procura (pelo login do Rafael, as regras do
Porthon valem) → "Achei João da Silva, bloco 14, apto 203, Ventos do Sul. Vou gerar senha nova;
a atual deixa de funcionar. Confirma?" → gera a senha IGUAL ao botão do painel (lib/senha.ts) e
grava pela MESMA rota (PATCH /api/moradores/[id]: confere permissão, valida a senha, bloqueia
admin, obriga a troca no 1º acesso) → "Mando no WhatsApp ou salvo num arquivo?".

Não achou o nome? Pede para soletrar. Achou mais de um? Lista e pergunta qual.
"""
import json
import re
import secrets
import unicodedata
from datetime import datetime
from pathlib import Path

import httpx

import porthon_dados

RAIZ = Path(__file__).parent
PASTA = RAIZ / "credenciais"
SITE = "https://porthon.com.br"

PEDIDO = re.compile(r"^(?:gera|gerar|gere|cria|criar|faz|fazer|reseta|resetar|redefine|troca|nova)\s+(?:(?:uma?|a|o|as|os)\s+)?"
                    r"(?:nova\s+|novo\s+)?(?:credencial|credenciais|senha|acesso|login)(?:\s+nova|\s+novo)?"
                    r"(?:\s+(?:d[oa]s?|pr[oa]|para\s+(?:o\s+|a\s+)?)\s*(?P<resto>.*))?\s*[.!]*$", re.I)
CANCELAR = re.compile(r"^(cancela|cancelar|deixa|deixa pra l[aá]|esquece|para|n[aã]o)\b", re.I)

# alfabeto do Porthon (lib/senha.ts): sem 0/O, 1/l/I, porque a senha é lida em voz alta
LETRAS, MAIUSCULAS, NUMEROS = "abcdefghijkmnopqrstuvwxyz", "ABCDEFGHJKLMNPQRSTUVWXYZ", "23456789"


def gerar_senha():
    """Igual ao gerarSenhaAleatoria do Porthon: 10 caracteres, ao menos uma minúscula, maiúscula e número."""
    chars = [secrets.choice(LETRAS), secrets.choice(MAIUSCULAS), secrets.choice(NUMEROS)]
    chars += [secrets.choice(LETRAS + MAIUSCULAS + NUMEROS) for _ in range(7)]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def _sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def separar(resto):
    """"João bloco 14 apto 203" / "João, 14/203" → (nome, bloco, apto)."""
    bloco = apto = None
    m = re.search(r"\b(\w{1,4})\s*/\s*(\w{1,6})\b", resto)
    if m:
        bloco, apto = m.group(1), m.group(2)
        resto = resto.replace(m.group(0), " ")
    m = re.search(r"\bbloco\s+(\w+)", resto, re.I)
    if m:
        bloco = m.group(1)
        resto = resto.replace(m.group(0), " ")
    m = re.search(r"\b(?:apartamento|apto|ap\.?)\s*(\w+)", resto, re.I)  # o mais comprido primeiro
    if m:
        apto = m.group(1)
        resto = resto.replace(m.group(0), " ")
    nome = re.sub(r"\b(?:morador|moradora|porteiro|porteira|s[ií]ndico|s[ií]ndica|funcion[aá]rio|funcion[aá]ria|"
                  r"do|da|de|o|a|no|na)\b", " ", resto, flags=re.I)
    nome = re.sub(r"[,.;]+", " ", nome).strip()
    return (nome or None), bloco, apto


SOLETRADO = {"a": "a", "be": "b", "bê": "b", "ce": "c", "cê": "c", "de": "d", "dê": "d", "e": "e", "efe": "f", "ge": "g", "gê": "g",
             "aga": "h", "agá": "h", "i": "i", "jota": "j", "ka": "k", "cá": "k", "ele": "l", "eme": "m", "ene": "n", "o": "o",
             "pe": "p", "pê": "p", "que": "q", "quê": "q", "erre": "r", "esse": "s", "te": "t", "tê": "t", "u": "u", "ve": "v",
             "vê": "v", "dablio": "w", "dáblio": "w", "xis": "x", "ipsilon": "y", "ípsilon": "y", "ze": "z", "zê": "z"}


def de_soletrado(fala):
    """"jota o a o" / "J-O-A-O" / "j o ã o" → "joao"; se não parecer soletrado, devolve a fala limpa."""
    partes = re.split(r"[\s,.\-]+", fala.strip().lower())
    sem_acento = {_sem_acento(k): v for k, v in SOLETRADO.items()}
    letras = [SOLETRADO.get(p) or sem_acento.get(_sem_acento(p)) or (_sem_acento(p) if len(p) == 1 else None)
              for p in partes if p]
    if letras and all(letras) and len(letras) >= 2:
        return "".join(letras)
    return fala.strip()


def procurar(d):
    """Moradores que batem com nome/bloco/apto (só os campos que a confirmação precisa)."""
    filtros = ["select=id,name,bloco,apartamento,role,email,contato,condominio_id"]
    if d.get("bloco"):
        filtros.append(f"bloco=eq.{d['bloco']}")
    if d.get("apto"):
        filtros.append(f"apartamento=eq.{d['apto']}")
    if d.get("nome"):
        # o banco não ignora acento: troca vogal por "_" (qualquer letra) no 1º nome — "joao" acha "João"
        primeiro = _sem_acento(d["nome"].split()[0])
        filtros.append("name=ilike.*" + re.sub(r"[aeiouc]", "_", primeiro) + "*")
    if len(filtros) == 1:
        return []
    achados = porthon_dados._ler("profiles", "&".join(filtros) + "&limit=20")
    if d.get("nome"):
        alvo = _sem_acento(d["nome"])
        achados = [a for a in achados if all(p in _sem_acento(a["name"] or "") for p in alvo.split())] or achados
    return achados


def _condominio(cid):
    return {c["id"]: c["nome"] for c in porthon_dados._ler("condominios", "select=id,nome")}.get(cid, "")


def _descrever(m):
    onde = f"bloco {m['bloco']}, apto {m['apartamento']}" if m.get("bloco") else "sem unidade"
    return f"{m['name']}, {onde}, do {_condominio(m['condominio_id'])}"


def entender(texto):
    m = PEDIDO.match(texto.strip())
    if not m:
        return None
    nome, bloco, apto = separar(m.group("resto") or "")
    return {"tipo": "credencial", "nome": nome, "bloco": bloco, "apto": apto}


def proximo_passo(d):
    if not (d.get("nome") or d.get("apto")):
        d["etapa"] = "nome"
        return "De quem é a credencial, chefe? Me diz o nome, e se souber, o bloco e o apartamento."
    achados = procurar(d)
    if not achados:
        d["etapa"] = "soletrar"
        return (f"Não achei {d.get('nome') or 'ninguém'}" + (f" no bloco {d['bloco']}" if d.get("bloco") else "")
                + (f", apto {d['apto']}" if d.get("apto") else "") + ". Soletra o nome pra mim?")
    if len(achados) > 1:
        d["etapa"] = "qual"
        d["opcoes"] = achados[:4]
        lista = "; ".join(f"{i + 1}, {_descrever(a)}" for i, a in enumerate(achados[:4]))
        return f"Achei {len(achados)}: {lista}. Qual deles?"
    alvo = achados[0]
    if alvo.get("role") == "admin":
        d["etapa"] = "cancelado"
        return f"{alvo['name']} é administrador: a senha de admin não pode ser trocada por aqui. É regra do Pórton."
    d.update(alvo=alvo, etapa="confirmar")
    return (f"Achei {_descrever(alvo)}. Vou gerar uma senha nova; a senha atual deixa de funcionar e "
            f"no primeiro acesso a pessoa troca. Confirma?")


def responder(d, fala):
    if CANCELAR.match(fala.strip()) and d.get("etapa") != "entregar":
        d["etapa"] = "cancelado"
        return "Cancelado, chefe. Não mexi em nada."
    etapa = d.get("etapa")
    if etapa == "nome":
        d["nome"], b, a = separar(fala)
        d["bloco"], d["apto"] = d.get("bloco") or b, d.get("apto") or a
    elif etapa == "soletrar":
        d["nome"] = de_soletrado(fala)
    elif etapa == "qual":
        ordem = {"1": 0, "um": 0, "primeiro": 0, "primeira": 0, "2": 1, "dois": 1, "segundo": 1, "segunda": 1,
                 "3": 2, "três": 2, "tres": 2, "terceiro": 2, "terceira": 2, "4": 3, "quatro": 3, "quarto": 3}
        chave = next((p for p in re.findall(r"\w+", fala.lower()) if p in ordem), None)
        if chave is not None and ordem[chave] < len(d["opcoes"]):
            escolhido = d["opcoes"][ordem[chave]]
            d.update(nome=escolhido["name"], bloco=escolhido["bloco"], apto=escolhido["apartamento"])
        else:
            nome, b, a = separar(fala)
            d.update(nome=nome or d["nome"], bloco=b or d.get("bloco"), apto=a or d.get("apto"))
    return proximo_passo(d)


def gerar(d):
    """Grava a senha nova pela rota do Porthon (as mesmas travas do botão do painel)."""
    senha = gerar_senha()
    alvo = d["alvo"]
    # a regra do Porthon: a senha não pode conter o primeiro nome (aleatória de 10 quase nunca tem, mas confere)
    while _sem_acento(alvo["name"].split()[0]) in senha.lower():
        senha = gerar_senha()
    _, _, token = porthon_dados._token()
    r = httpx.patch(f"{SITE}/api/moradores/{alvo['id']}", headers={"Authorization": f"Bearer {token}"},
                    json={"password": senha}, timeout=20)
    if r.status_code >= 300:
        raise RuntimeError(r.json().get("error", r.text[:120]) if r.headers.get("content-type", "").startswith("application/json") else r.text[:120])
    usuario = (alvo.get("email") or "").removesuffix("@porthon.local")
    d.update(usuario=usuario, senha=senha, etapa="entregar")
    return (f"Pronto, credencial gerada pra {alvo['name']}. Está na tela. "
            "Quer que eu mande no WhatsApp pra alguém, salve num arquivo, ou os dois?")


def texto_da_credencial(d):
    a = d["alvo"]
    return (f"Olá, {a['name'].split()[0]}! Seu acesso ao Porthon:\n"
            f"Usuário: {d['usuario']}\nSenha: {d['senha']}\n"
            f"Entre em {SITE}. É uma senha temporária: no primeiro acesso o sistema pede para você criar a sua.")


def salvar(d):
    PASTA.mkdir(exist_ok=True)
    a = d["alvo"]
    nome = re.sub(r"[^\w]+", "-", _sem_acento(a["name"])).strip("-")
    arquivo = PASTA / f"{datetime.now():%Y-%m-%d_%H%M}_{nome}_{a.get('bloco') or ''}-{a.get('apartamento') or ''}.txt"
    arquivo.write_text(texto_da_credencial(d) + f"\n\nGerada pelo Jarvis em {datetime.now():%d/%m/%Y %H:%M}.\n", encoding="utf-8")
    return arquivo


def cartao(d):
    a = d["alvo"]
    return {"titulo": "Porthon · credencial", "destaque": a["name"],
            "linhas": [f"Bloco {a.get('bloco')} · apto {a.get('apartamento')}", f"Usuário: {d['usuario']}", f"Senha: {d['senha']}"]}
