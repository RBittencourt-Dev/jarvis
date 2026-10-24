"""Jarvis AGE no PC: entende pedidos em linguagem natural sobre arquivos/pastas/programas e faz, sabendo ONDE.

Pedido do Rafael (24/10/2026): "ensina o Jarvis a criar arquivos em tal pasta, fazer coisas, entender onde é".
Decisões dele: o Jarvis faz as operações SIMPLES direto (criar/mover/renomear/abrir/escrever), CONFIRMANDO antes;
código/mudança em projeto vai pro Claude. Pode agir no PC INTEIRO (caminho absoluto vale), mas apagar vai pra LIXEIRA
(reversível, via send2trash), nunca apaga de vez.

Fluxo no server: `entender(texto)` -> dict do pedido (ou None). Operações de leitura (abrir/listar) o server faz direto;
as que mexem (criar/escrever/mover/renomear/copiar/apagar) ele confirma (pendente "arquivo") e no "sim" chama
`executar(pedido)`. `descrever(pedido)` dá a frase da confirmação.
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

import claude_ponte

LAR = Path(os.path.expanduser("~"))

# pastas conhecidas por nome falado
PASTAS = {
    "desktop": LAR / "Desktop", "area de trabalho": LAR / "Desktop", "área de trabalho": LAR / "Desktop",
    "documentos": LAR / "Documents", "documents": LAR / "Documents",
    "downloads": LAR / "Downloads", "baixados": LAR / "Downloads",
    "imagens": LAR / "Pictures", "fotos": LAR / "Pictures", "pictures": LAR / "Pictures",
    "musicas": LAR / "Music", "músicas": LAR / "Music", "music": LAR / "Music",
    "videos": LAR / "Videos", "vídeos": LAR / "Videos",
}
PADRAO = LAR / "Desktop"  # quando ele não diz onde

# "cria/crie/criar/faz/faça/monta ... (um)? arquivo|pasta|documento ..."
_CRIAR = re.compile(r"\b(?:cri[ae]\w*|faz\w*|fa[çc]\w*|monta\w*|gera\w*)\b", re.I)
_PASTA = re.compile(r"\b(?:pasta|diret[óo]rio)\b", re.I)
_ARQUIVO = re.compile(r"\b(?:arquivo|documento|bloco de notas|txt|arquivo de texto|nota)\b", re.I)
_ABRIR = re.compile(r"\b(?:abr[ei]\w*|abrir)\b", re.I)
_LISTAR = re.compile(r"\b(?:lista\w*|mostra\w*|o que tem|o que h[áa]|conte[úu]do)\b.{0,20}\bpasta\b", re.I)
_APAGAR = re.compile(r"\b(?:apaga\w*|apague|exclu[ai]\w*|delet[ae]\w*|remov[ae]\w*|joga\w*\s+fora|manda\w*\s+pra\s+lixeira)\b", re.I)
_MOVER = re.compile(r"\b(?:move\w*|mova|mud[ae]\w*\s+(?:pra|para)|transfere\w*)\b", re.I)
_RENOMEAR = re.compile(r"\b(?:renomei\w*|renomear|muda\w*\s+o\s+nome|troca\w*\s+o\s+nome)\b", re.I)
_COPIAR = re.compile(r"\b(?:copi[ae]\w*|copiar|duplica\w*)\b", re.I)

# "chamado/chamada X", "de nome X", nome.ext solto
_NOME = re.compile(r"\b(?:chamad[oa]|de nome|com o nome|nomeado)\s+['\"]?([^'\"]+?)['\"]?(?=\s+(?:na|no|em|dentro|com|pra|para|$))", re.I)
_NOME_EXT = re.compile(r"(?<![\w.])([\w\-]+\.[A-Za-z0-9]{1,5})\b")  # nome.ext solto (sem espaços; com espaço use 'chamado')
# "com o texto/conteúdo/escrito ..."
_CONTEUDO = re.compile(r"\b(?:com (?:o )?(?:texto|conte[úu]do|escrito)|escrev\w*(?:\s+nele)?|contendo|que diga)\s+[:,]?\s*(.+)$", re.I)
# caminho absoluto do Windows: C:\...  ou  "C:\..."
_ABS = re.compile(r"[A-Za-z]:[\\/][^\"'<>|]+")


def _achar_pasta_estrito(texto):
    """Pasta citada no texto (caminho absoluto, pasta conhecida ou projeto), ou None se nada bater."""
    m = _ABS.search(texto)
    if m:
        return Path(m.group(0).strip().rstrip(".,"))
    t = texto.lower()
    for chave, (nome, pasta) in claude_ponte.PROJETOS.items():  # porthon, painel, radar, site, planner, jarvis
        if re.search(rf"\b{chave}\b", t):
            return pasta
    for nome, caminho in PASTAS.items():
        if re.search(rf"\b{re.escape(nome)}\b", t):
            return caminho
    return None


def _achar_pasta(texto):
    """Como o estrito, mas cai no Desktop quando ele não diz onde."""
    return _achar_pasta_estrito(texto) or PADRAO


def _destino(dir_, base):
    """Pasta de destino de um mover/copiar: conhecida/absoluta, ou 'pra pasta X' = subpasta da origem."""
    d = _achar_pasta_estrito(dir_)
    if d is not None:
        return d
    sub = re.search(r"\bpasta\s+(?:chamad[oa]\s+)?['\"]?([\wÀ-ÿ][\wÀ-ÿ \-]*?)['\"]?\s*$", dir_.strip(), re.I)
    return (base / sub.group(1).strip()) if sub else None


def _split_pra(t):
    """Separa 'origem ... pra destino' em (esquerda, direita)."""
    partes = re.split(r"\s+(?:pra|para|->|at[ée]\s+(?:a|o)?)\s+", t, maxsplit=1, flags=re.I)
    return (partes[0], partes[1]) if len(partes) == 2 else (t, "")


def _origem(t):
    """Caminho completo do arquivo/pasta citado (absoluto, ou nome.ext/‘chamado X’ dentro da pasta resolvida)."""
    m = _ABS.search(t)
    if m:
        return m.group(0).strip().rstrip(".,")
    nome = _NOME.search(t) or _NOME_EXT.search(t)
    if nome:
        return str(_achar_pasta(t) / nome.group(1).strip())
    return None


def entender(texto):
    t = (texto or "").strip()
    if not t:
        return None
    # RENOMEAR: "renomeia X pra Y" (Y = nome novo)
    if _RENOMEAR.search(t):
        esq, dir_ = _split_pra(t)
        alvo = _origem(esq)
        novo = re.sub(r"['\"]", "", dir_).strip().rstrip(".,")
        if alvo and novo:
            return {"op": "renomear", "alvo": alvo, "novo": novo}
    # MOVER / COPIAR: "move|copia X pra <pasta>"
    if _MOVER.search(t) or _COPIAR.search(t):
        esq, dir_ = _split_pra(t)
        alvo = _origem(esq)
        destino = _destino(dir_, Path(alvo).parent) if (alvo and dir_) else None
        if alvo and destino:
            return {"op": "copiar" if _COPIAR.search(t) and not _MOVER.search(t) else "mover",
                    "alvo": alvo, "destino": str(destino)}
    # LISTAR
    if _LISTAR.search(t):
        return {"op": "listar", "pasta": str(_achar_pasta(t))}
    # ABRIR (pasta/arquivo/programa)
    if _ABRIR.search(t) and not _CRIAR.search(t):
        alvo = _ABS.search(t)
        if alvo:
            return {"op": "abrir", "alvo": alvo.group(0).strip().rstrip(".,")}
        if _PASTA.search(t):
            return {"op": "abrir", "alvo": str(_achar_pasta(t))}
        # "abre o <programa/arquivo>" — pega o resto depois de 'abre o/a'
        mp = re.search(r"\babr[ei]\w*\s+(?:o|a|os|as)?\s*(.+)$", t, re.I)
        if mp:
            return {"op": "abrir", "alvo": mp.group(1).strip().rstrip(".,"), "programa": True}
    # APAGAR (vai pra lixeira)
    if _APAGAR.search(t):
        alvo = _ABS.search(t)
        nome = (_NOME.search(t) or _NOME_EXT.search(t))
        if alvo or nome:
            base = _achar_pasta(t)
            caminho = alvo.group(0).strip() if alvo else str(base / (nome.group(1).strip()))
            return {"op": "apagar", "alvo": caminho}
    # CRIAR pasta
    if _CRIAR.search(t) and _PASTA.search(t):
        nome = _NOME.search(t)
        nome = nome.group(1).strip() if nome else _depois_de_pasta(t)
        if nome:
            return {"op": "criar_pasta", "pasta": str(_achar_pasta(t)), "nome": nome}
    # CRIAR arquivo
    if _CRIAR.search(t) and _ARQUIVO.search(t):
        m = _NOME.search(t) or _NOME_EXT.search(t)
        nome = (m.group(1).strip() if m else "novo arquivo")
        if "." not in Path(nome).name:
            nome += ".txt"
        conteudo = _CONTEUDO.search(t)
        return {"op": "criar_arquivo", "pasta": str(_achar_pasta(t)), "nome": nome,
                "conteudo": conteudo.group(1).strip() if conteudo else ""}
    return None


def _depois_de_pasta(t):
    m = re.search(r"\bpasta\s+(?:chamad[oa]\s+)?['\"]?([A-Za-zÀ-ÿ0-9 _\-]+?)['\"]?(?=\s+(?:na|no|em|dentro|$))", t, re.I)
    return m.group(1).strip() if m else ""


def descrever(p):
    op = p["op"]
    if op == "criar_pasta":
        return f"Vou criar a pasta \"{p['nome']}\" em {p['pasta']}."
    if op == "criar_arquivo":
        extra = " com o texto que você ditou" if p.get("conteudo") else ""
        return f"Vou criar o arquivo \"{p['nome']}\" em {p['pasta']}{extra}."
    if op == "apagar":
        return f"Vou mandar pra LIXEIRA (dá pra recuperar): {p['alvo']}."
    if op == "renomear":
        return f"Vou renomear {Path(p['alvo']).name} para \"{p['novo']}\"."
    if op == "mover":
        return f"Vou mover {Path(p['alvo']).name} para {p['destino']}."
    if op == "copiar":
        return f"Vou copiar {Path(p['alvo']).name} para {p['destino']}."
    return "Vou mexer nos arquivos."


def nome_curto(p):
    return {"criar_pasta": "criar uma pasta", "criar_arquivo": "criar um arquivo",
            "apagar": "mandar pra lixeira", "abrir": "abrir", "listar": "listar a pasta",
            "renomear": "renomear", "mover": "mover", "copiar": "copiar"}.get(p["op"], "mexer em arquivos")


def executar(p):
    try:
        op = p["op"]
        if op == "listar":
            d = Path(p["pasta"])
            if not d.exists():
                return f"A pasta {d} não existe, chefe."
            itens = sorted(os.listdir(d))[:40]
            if not itens:
                return f"A pasta {d.name} está vazia, chefe."
            return f"Em {d.name} tem {len(itens)} itens: " + ", ".join(itens[:15]) + ("…" if len(itens) > 15 else "") + "."
        if op == "abrir":
            os.startfile(p["alvo"]) if os.path.exists(p["alvo"]) else subprocess.Popen(["cmd", "/c", "start", "", p["alvo"]])
            return f"Abrindo {Path(p['alvo']).name or p['alvo']}, chefe."
        if op == "criar_pasta":
            alvo = Path(p["pasta"]) / p["nome"]
            alvo.mkdir(parents=True, exist_ok=True)
            return f"Pronto, criei a pasta \"{p['nome']}\" em {p['pasta']}, chefe."
        if op == "criar_arquivo":
            Path(p["pasta"]).mkdir(parents=True, exist_ok=True)
            alvo = Path(p["pasta"]) / p["nome"]
            alvo.write_text(p.get("conteudo", ""), encoding="utf-8")
            return f"Pronto, criei \"{p['nome']}\" em {p['pasta']}, chefe." + (" Já escrevi o texto nele." if p.get("conteudo") else "")
        if op == "apagar":
            from send2trash import send2trash
            if not os.path.exists(p["alvo"]):
                return f"Não achei {p['alvo']} pra apagar, chefe."
            send2trash(p["alvo"].replace("/", "\\"))
            return f"Mandei pra lixeira, chefe (dá pra recuperar): {Path(p['alvo']).name}."
        if op == "renomear":
            src = Path(p["alvo"])
            if not src.exists():
                return f"Não achei {src.name} pra renomear, chefe."
            novo = p["novo"] if ("." in p["novo"] or src.is_dir()) else p["novo"] + src.suffix
            src.rename(src.with_name(novo))
            return f"Pronto, renomeei para \"{novo}\", chefe."
        if op in ("mover", "copiar"):
            src = Path(p["alvo"])
            if not src.exists():
                return f"Não achei {src.name}, chefe."
            Path(p["destino"]).mkdir(parents=True, exist_ok=True)
            destino = Path(p["destino"]) / src.name
            if op == "mover":
                shutil.move(str(src), str(destino))
                return f"Pronto, movi {src.name} pra {p['destino']}, chefe."
            shutil.copytree(src, destino) if src.is_dir() else shutil.copy2(src, destino)
            return f"Pronto, copiei {src.name} pra {p['destino']}, chefe."
        return "Não entendi o que era pra fazer com o arquivo, chefe."
    except Exception as e:
        return f"Não consegui, chefe: {str(e)[:150]}"
