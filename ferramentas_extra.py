"""Ferramentas que o cérebro usa sozinho: buscar na internet, ler um site e criar planilha.

Nada aqui pede autorização: são leituras, ou arquivos novos (nunca sobrescreve).
"""
import html
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import httpx

NAVEGADOR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/130.0 Safari/537.36", "Accept-Language": "pt-BR,pt;q=0.9"}
PASTA_PADRAO = Path.home() / "Documents" / "Jarvis"


def _texto_de(html_bruto):
    t = re.sub(r"(?is)<(script|style|noscript|svg|header|footer|nav)\b.*?</\1>", " ", html_bruto)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def buscar_na_web(consulta: str):
    """Os primeiros resultados do DuckDuckGo (título, endereço e resumo), para o cérebro responder com dado atual."""
    r = httpx.post("https://html.duckduckgo.com/html/", data={"q": consulta, "kl": "br-pt"}, headers=NAVEGADOR,
                   timeout=10, follow_redirects=True)
    saida = []
    for bloco in r.text.split('class="result__a"')[1:7]:
        link = re.search(r'href="([^"]+)"[^>]*>(.*?)</a>', bloco, re.S)
        if not link:
            continue
        href, titulo = link.groups()
        resumo = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', bloco, re.S)
        resumo = resumo.group(1) if resumo else ""
        if "uddg=" in href:
            href = unquote(parse_qs(urlparse(href).query).get("uddg", [href])[0])
        if "duckduckgo.com/y.js" in href:
            continue  # anúncio
        saida.append(f"- {_texto_de(titulo)} ({href}): {_texto_de(resumo or '')}")
    return "\n".join(saida) or "Nenhum resultado."


def ler_site(url: str):
    """Texto de uma página (até ~6 mil caracteres)."""
    if not re.match(r"^https?://", url):
        url = "https://" + url
    r = httpx.get(url, headers=NAVEGADOR, timeout=12, follow_redirects=True)
    if r.status_code in (403, 429) or "robot policy" in r.text[:300]:
        # alguns sites (Wikipédia) preferem um robô que se identifica a um que finge ser navegador
        r = httpx.get(url, headers={"User-Agent": "JarvisAssistente/1.0 (https://7sevencode.com.br; uso pessoal)"}, timeout=12, follow_redirects=True)
    texto = _texto_de(r.text)
    return texto[:6000] + (" …(cortado)" if len(texto) > 6000 else "")


def criar_planilha(nome: str, abas: dict, pasta: str = ""):
    """abas = {"Aba": [["Cabeçalho", ...], [linha], ...]}. Grava .xlsx novo (nunca sobrescreve) e devolve o caminho."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    destino = Path(pasta) if pasta else PASTA_PADRAO
    destino.mkdir(parents=True, exist_ok=True)
    base = re.sub(r'[<>:"/\\|?*]', "", nome).strip() or "Planilha"
    arquivo = destino / (base if base.lower().endswith(".xlsx") else base + ".xlsx")
    n = 2
    while arquivo.exists():
        arquivo = destino / f"{base} ({n}).xlsx"
        n += 1
    livro = Workbook()
    livro.remove(livro.active)
    for nome_aba, linhas in (abas or {"Planilha": [[]]}).items():
        aba = livro.create_sheet(str(nome_aba)[:31] or "Planilha")
        for linha in linhas or []:
            aba.append([_numero(v) for v in (linha if isinstance(linha, list) else [linha])])
        if aba.max_row >= 1:
            for celula in aba[1]:  # cabeçalho em negrito, fundo azul claro
                celula.font = Font(bold=True)
                celula.fill = PatternFill("solid", fgColor="DDEBF7")
            aba.freeze_panes = "A2"
        for i, coluna in enumerate(aba.columns, 1):
            largura = max((len(str(c.value)) for c in coluna if c.value is not None), default=8)
            aba.column_dimensions[get_column_letter(i)].width = min(60, largura + 3)
    livro.save(arquivo)
    try:  # já abre pra ele (antes o cérebro abria pelo PowerShell)
        import os
        os.startfile(arquivo)
        return f"{arquivo} (já aberta na tela)"
    except OSError:
        return str(arquivo)


def _numero(v):
    """"1.234,56" e "R$ 10" viram número de verdade na planilha (dá pra somar)."""
    if isinstance(v, str):
        s = v.strip().replace("R$", "").strip()
        if re.fullmatch(r"-?\d{1,3}(\.\d{3})*(,\d+)?|-?\d+(,\d+)?", s):
            return float(s.replace(".", "").replace(",", "."))
        if re.fullmatch(r"-?\d+(\.\d+)?", s):
            return float(s)
    return v


def calcular(expressao: str):
    """Conta exata (o modelo erra conta grande de cabeça). Aceita + - * / ** % ( ), vírgula decimal e
    sqrt, raiz, round, abs, min, max, log, sin, cos, pi."""
    import ast
    import math
    import operator as op
    ops = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv, ast.Pow: op.pow,
           ast.Mod: op.mod, ast.FloorDiv: op.floordiv, ast.USub: op.neg, ast.UAdd: op.pos}
    funcoes = {"sqrt": math.sqrt, "raiz": math.sqrt, "round": round, "abs": abs, "min": min, "max": max,
               "log": math.log, "log10": math.log10, "sin": math.sin, "cos": math.cos, "tan": math.tan}
    constantes = {"pi": math.pi, "e": math.e}
    texto = re.sub(r"(\d),(\d)", r"\1.\2", expressao.replace("x", "*").replace("×", "*").replace("÷", "/").replace("^", "**"))

    def val(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in ops:
            if isinstance(n.op, ast.Pow) and abs(val(n.right)) > 1000:
                raise ValueError("expoente grande demais")
            return ops[type(n.op)](val(n.left), val(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in ops:
            return ops[type(n.op)](val(n.operand))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in funcoes:
            return funcoes[n.func.id](*[val(a) for a in n.args])
        if isinstance(n, ast.Name) and n.id in constantes:
            return constantes[n.id]
        raise ValueError("expressão não suportada")

    resultado = val(ast.parse(texto, mode="eval").body)
    if isinstance(resultado, float) and resultado.is_integer():
        resultado = int(resultado)
    return f"{expressao} = {round(resultado, 6) if isinstance(resultado, float) else resultado}"
