"""De onde o Jarvis aprende: a memória do Claude Code e os documentos dos projetos, lidos AO VIVO.

Nada é copiado: quando o Claude anota algo novo na memória ou um documento muda, o Jarvis
relê sozinho (o servidor recarrega de tempos em tempos). Arquivos de senha nunca entram.
"""
import re
import time
from pathlib import Path

CASA = Path.home()
DESKTOP = CASA / "Desktop"
RAIZ = Path(__file__).parent
# memória do Claude Code do projeto Porthon (a pasta tem o caminho do projeto no nome; em outro PC, outro nome)
MEMORIA = CASA / ".claude" / "projects" / str(DESKTOP / "Porthon-System").replace(":", "-").replace("\\", "-").replace(" ", "-") / "memory"

DOCUMENTOS = [  # (nome que aparece para o modelo, arquivo)
    ("porthon-guia", DESKTOP / "Porthon-System" / "lobby" / "docs" / "porthon-para-ia.md"),
    ("porthon-estado", DESKTOP / "Porthon-System" / "lobby" / "docs" / "ESTADO-DO-PROJETO.md"),
    ("porthon-multicondominio", DESKTOP / "Porthon-System" / "lobby" / "docs" / "multicondominio.md"),
    ("porthon-sindico-profissional", DESKTOP / "Porthon-System" / "lobby" / "docs" / "sindico-profissional.md"),
    ("porthon-regras-de-codigo", DESKTOP / "Porthon-System" / "lobby" / "AGENTS.md"),
    ("painel-regras-de-codigo", DESKTOP / "7 SevenCode" / "painel-7sevencode" / "AGENTS.md"),
    ("radar-guia", DESKTOP / "7code-radar-leads" / "GUIA.md"),
]
NUNCA = re.compile(r"\.env|senha|password|secret|demo-acessos", re.I)


def _sem_cabecalho(texto):
    """Tira o bloco --- name/description --- do começo das anotações de memória."""
    m = re.match(r"^---\n(.*?)\n---\n", texto, re.S)
    if not m:
        return None, texto
    descricao = re.search(r"^description:\s*\"?(.*?)\"?\s*$", m.group(1), re.M)
    return (descricao.group(1) if descricao else None), texto[m.end():]


def ler_fontes():
    """[(nome, texto, idade em dias)] de tudo que o Jarvis deve saber.

    A idade pesa na busca: anotação antiga ("onde paramos" de agosto) perde para a atual,
    senão o Jarvis responde com uma decisão que já mudou.
    """
    agora = time.time()
    idade = lambda arquivo: (agora - arquivo.stat().st_mtime) / 86400
    fontes = [(a.stem, a.read_text(encoding="utf-8"), 0) for a in sorted((RAIZ / "conhecimento").glob("*.md"))]
    # especialidades/: conhecimento que vai junto com o Jarvis pra todo PC (suporte de T.I, Educação Adventista, marketing)
    fontes += [(a.stem, a.read_text(encoding="utf-8"), 0) for a in sorted((RAIZ / "especialidades").glob("*.md"))]
    for nome, arquivo in DOCUMENTOS:
        if arquivo.exists():
            fontes.append((nome, arquivo.read_text(encoding="utf-8", errors="replace"), idade(arquivo)))
    if MEMORIA.exists():
        for arquivo in sorted(MEMORIA.glob("*.md")):
            if arquivo.name == "MEMORY.md" or NUNCA.search(arquivo.name):
                continue
            descricao, corpo = _sem_cabecalho(arquivo.read_text(encoding="utf-8", errors="replace"))
            if descricao and re.match(r"\s*SUPERAD[OA]", descricao):
                continue  # anotação que o próprio Claude marcou como ultrapassada: só confundiria
            # a descrição vira o título, junto com o nome do arquivo ("papel-manutencao" → papel manutencao)
            titulo = f"{arquivo.stem.replace('-', ' ')}: {descricao or ''}"
            fontes.append((f"memoria-{arquivo.stem}", f"# {titulo}\n\n{corpo}", idade(arquivo)))
    return fontes


# ------------------------------------------------------------- andamento do Porthon (da memória)

PALAVRAS_DE_PENDENCIA = re.compile(r"falta|pendente|pend[eê]ncia|confirmar|n[aã]o confirmad|N[ÃA]O commit|em aberto", re.I)


def desenvolvimento_porthon():
    """O que está no pacote de atualização e o que ficou pendente, como o Claude anotou."""
    pacote, sqls, pendencias = [], [], []
    indice = MEMORIA / "MEMORY.md"
    linhas_do_indice = indice.read_text(encoding="utf-8").splitlines() if indice.exists() else []
    # título curto de cada anotação, pelo nome do arquivo: "inquilino-responsavel" → "Inquilino responsável + ordem no apto"
    titulos = {m.group(2): m.group(1) for m in (re.match(r"- \[(.+?)\]\((.+?)\.md\)", l) for l in linhas_do_indice) if m}
    arquivo = MEMORIA / "proxima-atualizacao-porthon.md"
    if arquivo.exists():
        texto = arquivo.read_text(encoding="utf-8")
        itens = re.search(r"## Itens do pacote\n(.*?)(?:\n## |\Z)", texto, re.S)
        for linha in (itens.group(1) if itens else "").splitlines():
            m = re.match(r"\d+\.\s*(?:\[\[([^\]]+)\]\]:?\s*)?(.+)", linha.strip())
            if m:
                pacote.append(titulos.get(m.group(1)) or re.split(r"[.:;]", m.group(2))[0].strip())
        sql = re.search(r"## SQL do pacote.*?\n(.*?)(?:\n## |\n\n[A-Z]|\Z)", texto, re.S)
        sqls = [l.strip("- ").strip() for l in (sql.group(1) if sql else "").splitlines()
                if l.strip().startswith("-") and re.search(r"n[aã]o confirmad|\?", l)]
    for linha in linhas_do_indice[:20]:  # o topo do índice é o mais recente
        m = re.match(r"- \[(.+?)\]\(.+?\)\s*[—-]\s*(.+)", linha)
        if m and PALAVRAS_DE_PENDENCIA.search(m.group(2)) and not re.search(r"jarvis|7planner|radar", linha, re.I):
            # do resumo, só o pedaço que diz o que falta
            pedaco = next((p.strip() for p in re.split(r"[;—]", m.group(2)) if PALAVRAS_DE_PENDENCIA.search(p)), m.group(2))
            pendencias.append(f"{m.group(1)}: {pedaco}")
    return {"pacote": pacote, "sqls": sqls, "pendencias": pendencias[:5]}
