"""Sub-agentes especialistas do Jarvis: ele "chama" um expert e responde com a cabeça daquela área.

Pedido dele (23/10/2026): "cria vários agentes pra ele acionar pra cada coisa, pra ser especialista". Cada especialista
é uma persona forte no cérebro (Groq/Gemini). Pra tarefa PESADA de verdade (revisar segurança de um app, mexer no
código), ele lembra que pode mandar pro Claude Code (o claude_ponte já faz isso) — é lá que está a força de fato.

Dispara em pedido CLARO de especialista ("chama o especialista em X", "como um programador, ...", "modo segurança"),
pra não roubar a conversa comum nem o professor. SEGURANÇA é sempre DEFENSIVA: achar e corrigir falhas nos apps DELE,
nunca orientar ataque a terceiros.
"""
import asyncio
import re
import unicodedata

import cerebro
from pathlib import Path

RAIZ = Path(__file__).parent

DEMORA = True

# chave → (nome falado, persona, pede_claude_para)
EXPERTS = {
    "programacao": ("programação", "Você é um programador sênior, didático e direto. Explica com exemplos de código "
                    "curtos e comentados, aponta a melhor prática e os erros comuns. Português do Brasil.",
                    "escrever ou mexer no código de um projeto"),
    "seguranca": ("segurança", "Você é um especialista em segurança de aplicações (AppSec), DEFENSIVO. Ajuda o Rafael a "
                  "ACHAR e CORRIGIR vulnerabilidades nos aplicativos DELE e a se proteger. Explica o risco e a correção. "
                  "NUNCA oriente invadir, atacar ou burlar sistemas de terceiros. Português do Brasil.",
                  "auditar a segurança de um app inteiro dele"),
    "copy": ("copy e marketing", "Você é um redator publicitário e estrategista de marketing. Escreve textos que "
             "vendem, com clareza e gancho, sem clichê. Português do Brasil.", None),
    "dados": ("análise de dados", "Você é um analista de dados. Ajuda a entender números, métricas e tendências, e a "
              "tirar conclusões úteis. Explica simples. Português do Brasil.", None),
    "financeiro": ("finanças", "Você é um consultor de finanças que explica conceitos de forma simples. NÃO dá "
                   "recomendação personalizada de investimento (não é consultor habilitado); explica os conceitos pra "
                   "ele decidir. Português do Brasil.", None),
    "juridico": ("jurídico", "Você é um especialista jurídico que explica leis e contratos em português claro, voltado ao "
                 "dia a dia de condomínio, empresa e do Rafael (CDC, LGPD, Código Civil, locação, condomínio, trabalhista "
                 "básico). Explica o conceito e o caminho. NÃO é advogado habilitado e isto não é parecer jurídico: pra caso "
                 "concreto e sério, oriente procurar um advogado. Português do Brasil.", None),
    "contabil": ("contábil e financeiro", "Você é um especialista contábil e financeiro que explica em português simples: "
                 "impostos, notas, MEI/Simples, fluxo de caixa, precificação, custos. NÃO é contador habilitado e isto não "
                 "substitui um contador; pra fechar imposto e obrigação legal, oriente procurar um contador. Português do Brasil.", None),
    "design": ("design gráfico", "Você é um diretor de design gráfico sênior: faz qualquer coisa ficar TOP — posts, "
               "artes, logos, interface, layout, tipografia, cor e composição, com critério profissional (hierarquia, "
               "contraste, espaço em branco, grid). Sabe a identidade do Porthon (fundo escuro quase preto, verde "
               "esmeralda #34d399 como destaque, visual limpo e moderno) e usa ela de forma PROFISSIONAL e VARIADA — não "
               "engessado num só modelo, mas sempre coerente com a marca. Dá direções concretas e acionáveis "
               "(o Rafael monta a arte no Canva; você dá o passo a passo e as escolhas). Português do Brasil.", None),
    "suporte": ("suporte técnico de T.I", "Você é um técnico de suporte de T.I sênior de uma escola: PCs Windows, "
                "notebooks, Chromebooks e Google Admin, redes (cabo, Wi-Fi, roteador, DHCP, DNS), impressoras, projetores, "
                "Office e contas. Faz o diagnóstico em passos curtos e numerados, do mais simples pro mais complexo, com o "
                "comando exato quando houver, e diz quando é caso de trocar peça ou chamar a assistência. Português do Brasil.",
                None),
    "adventista": ("Educação Adventista e Igreja", "Você conhece a fundo a Igreja Adventista do Sétimo Dia (história, "
                   "organização, as 28 crenças fundamentais, Escola Sabatina, Desbravadores, projetos da DSA) e a Educação "
                   "Adventista (filosofia de educação integral, rotina espiritual da escola, material da rede). Responde com "
                   "respeito e fidelidade ao que a igreja ensina, sem inventar dados; se não tiver certeza de um número ou "
                   "nome, diz isso. Português do Brasil.", None),
}

# Conhecimento que vai junto no pedido (especialidades/*.md, viaja com o Jarvis pra todo PC).
BASE = {"suporte": "suporte-ti.md", "adventista": "educacao-adventista-e-igreja.md", "copy": "marketing-escolar.md"}

# Problema de T.I dito do jeito comum ("a impressora não imprime") já chama o suporte, sem dizer "especialista".
PROBLEMA_TI = re.compile(
    r"\b(?:impressora|imprim\w*|scanner|wi-?fi|internet|rede|roteador|cabo de rede|projetor|chromebooks?|tela azul|"
    r"windows|notebook|computador|pc|monitor|teclado|mouse|driver|spooler|outlook|office)\b.{0,40}\b(?:n[aã]o|parou|"
    r"travou|travando|trava|lent[oa]|sem|erro|problema|offline|caindo|cai|n[aã]o liga|desliga|atolad\w*|falhad\w*|"
    r"riscad\w*|consert\w*|resolv\w*|arrum\w*)\b"
    r"|\b(?:n[aã]o|parou de|sem)\b.{0,25}\b(?:imprime|imprimir|conecta|liga|pega a internet|tem internet|funciona a rede)\b",
    re.I)

# como ele chama cada um (palavras → chave)
AREA = [
    (r"suporte|t\.?\s?i\b|impressora|rede|wi-?fi|internet|roteador|projetor|chromebook|computador|notebook|tela azul", "suporte"),
    (r"adventista|igreja|iasd|educa[cç][aã]o adventista|desbravador\w*|escola sabatina|sabado|ellen white|biblia|crencas?", "adventista"),
    (r"program\w*|c[oó]digo|codar|dev|software|script|bug", "programacao"),
    (r"seguran[çc]\w*|hacker|pentest|vulnerab\w*|cibersegur\w*|invas\w*|appsec", "seguranca"),
    (r"copy\w*|redator|marketing|an[uú]ncio|texto que vende|vendas?", "copy"),
    (r"dados|an[aá]lise|m[eé]tricas?|estat[ií]stic\w*|n[uú]meros", "dados"),
    (r"finan[çc]\w*|dinheiro|investim\w*|or[çc]amento", "financeiro"),
    (r"design|ui\b|ux\b|interface|layout|usabilidade|arte|logo", "design"),
    (r"jur[ií]dic\w*|advog\w*|lei\b|leis\b|contrato|direito|lgpd|processo|clt|locacao|aluguel", "juridico"),
    (r"cont[aá]bil|cont\w*(?:ador)?|imposto|fiscal|nota\s+fiscal|mei|simples\s+nacional|tribut\w*", "contabil"),
]

CHAMAR = re.compile(r"\b(?:chama|chamar|aciona|acionar|quero|me\s+(?:d[aá]|passa)|usa|p[oõ]e)\b.{0,20}?"
                    r"(?:o\s+|a\s+|um\s+|uma\s+)?(?:especialista|expert|agente|sub-?agente)\b", re.I)
COMO = re.compile(r"\bcomo\s+(?:um\s+|uma\s+)?(?:especialista|expert|profissional)\s+(?:em|de|d[oa])\b", re.I)
MODO = re.compile(r"\bmodo\s+(?:especialista\s+)?(?:de\s+|em\s+)?(?P<area>program\w*|seguran[çc]\w*|cibersegur\w*|"
                  r"copy\w*|marketing|dados|an[aá]lise|finan[çc]\w*|design|suporte|adventista|igreja)\b", re.I)


def _sa(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def _area(texto):
    sa = _sa(texto)
    for rx, chave in AREA:
        if re.search(rx, sa):
            return chave
    return None


def _pergunta(texto):
    """Tira o 'chama o especialista em X' e deixa o que ele realmente quer."""
    t = re.sub(r"^.*?(?:especialista|expert|agente|profissional)\s+(?:em|de|d[oa])\s+\S+[\s,:-]*", "", texto, flags=re.I)
    t = re.sub(r"^(?:modo\s+\S+[\s,:-]*)", "", t, flags=re.I)
    return t.strip(" ,.:-")


def entender(texto):
    t = texto or ""
    gatilho = CHAMAR.search(t) or COMO.search(t) or MODO.search(t)
    if not gatilho:
        import sistemas  # "o pc tá lento" é ESTE PC: quem responde é o sistemas (mede CPU/RAM na hora)
        if PROBLEMA_TI.search(t) and not sistemas.entender(t) and not re.match(r"^(?:jarvis[ ,]*)?(?:abre|abrir|liga|desliga|reinicia|fecha)\b", t, re.I):
            return {"area": "suporte", "pergunta": t.strip()}
        return None
    area = _area(t)
    if not area:
        return None
    return {"area": area, "pergunta": _pergunta(t)}


def executar(p):
    area = p["area"]
    nome, persona, pede_claude = EXPERTS[area]
    pergunta = (p.get("pergunta") or "").strip()
    if not pergunta:  # só chamou o especialista, sem a dúvida ainda
        dica = f" Pra {pede_claude}, dá pra eu mandar pro Claude." if pede_claude else ""
        return f"Especialista em {nome} na linha, chefe. Pode mandar sua dúvida.{dica}", []
    if area in BASE:
        try:
            persona += "\n\nBase de conhecimento (use quando servir):\n" + (RAIZ / "especialidades" / BASE[area]).read_text(encoding="utf-8")[:9000]
        except OSError:
            pass
    try:
        resposta = asyncio.run(cerebro.completar(
            [{"role": "system", "content": persona}, {"role": "user", "content": pergunta}],
            temperatura=0.4, max_tokens=700, dificil=True)).strip()
    except Exception:
        resposta = ""
    if not resposta:
        return f"Não consegui responder como especialista em {nome} agora, chefe. Tenta de novo?", []
    fala = f"Como especialista em {nome}, chefe:"
    limpo = re.sub(r"[*`#]+", "", resposta)
    cartao = {"titulo": f"Especialista · {nome}", "linhas": [l.strip() for l in limpo.split("\n") if l.strip()][:16],
              "copiar": resposta}
    if area in NO_CLAUDE and _mandar_pro_claude(area, pergunta):
        cartao["linhas"].append("— Mandei também pro Claude (só lendo, sem mexer em nada). Ele responde em instantes.")
        return fala + " " + (resposta.split("\n")[0][:200]) + " E já pedi a análise completa pro Claude.", [cartao]
    if pede_claude:
        cartao["linhas"].append(f"— Pra {pede_claude}, posso mandar pro Claude.")
    return fala + " " + (resposta.split("\n")[0][:200]), [cartao]


# Pedido de 23/10: programação e segurança têm a resposta rápida do Gemini/Groq E a análise completa do Claude Code,
# que é mais preciso. Vai em modo plan (só lê e explica, não muda nada), em segundo plano, e o Jarvis fala quando
# chegar (claude_ponte.novidades). Mexer no código continua sendo "pede pro Claude…", com o sim dele.
NO_CLAUDE = {"programacao", "seguranca"}


def _mandar_pro_claude(area, pergunta):
    import shutil
    import claude_ponte
    if not shutil.which("claude"):
        return False  # PC sem o Claude Code (ex.: o do colégio): fica só a resposta rápida
    sa = _sa(pergunta)
    projeto = next((k for k in claude_ponte.PROJETOS if re.search(rf"\b{k}\b", sa)), claude_ponte.ultimo_projeto["chave"])
    if not claude_ponte.PROJETOS[projeto][1].exists():
        return False
    papel = ("Atue como especialista em segurança de aplicações, DEFENSIVO: ache e explique como corrigir falhas no "
             "projeto dele. " if area == "seguranca" else "Atue como programador sênior. ")
    claude_ponte.executar({"modo": "perguntar", "projeto": projeto, "nome": claude_ponte.PROJETOS[projeto][0],
                           "pedido": papel + pergunta})
    return True
