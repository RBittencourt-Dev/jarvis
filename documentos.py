"""Documentos da 7 SevenCode por voz: o Jarvis monta contrato e proposta de software — no Word de verdade — e deixa
pronto pra revisar, com a cabeça jurídica e contábil certa.

Pedido dele (24/10/2026): "acesso total ao Office + ensinar a montar documento, com conhecimento jurídico e contábil,
foco em contrato/proposta de SOFTWARE. Eu pedir 'olha os docs da 7SevenCode' e o Jarvis saber o que pode / o que não
pode e como montar."

Como funciona (sempre com a chave de IA que ele já tem — Groq/Gemini):
  1. Ele fala "monta um contrato de software pro condomínio X" / "faz uma proposta do Porthon pra administradora Y" /
     "o que pode num contrato de software?".
  2. O cérebro escreve o documento NO PADRÃO (ver a base especialidades/documentos-juridico-contabil.md + o que ele
     sabe da 7 SevenCode em conhecimento/7sevencode.md): as cláusulas/seções certas, sem prometer o que não pode, com
     LGPD quando trata dado pessoal, e deixando [campos pra preencher] no que não sabe (CPF, valor fechado) em vez de
     inventar.
  3. Salva em Documentos/7 SevenCode/AAAA-MM-DD-<assunto>.docx, ABRE no Word (Office de verdade, pra ele editar e
     assinar), copia o texto pra área de transferência e mostra o resumo no HUD.

"o que pode / o que não pode / me explica os docs" → responde com a cabeça da base, sem gerar arquivo.

NÃO é parecer jurídico nem contábil: é documento BASE pra revisar. Enquanto a 7 SevenCode recebe como PF, o Jarvis não
promete nota fiscal — avisa que nota é o gatilho pra abrir o CNPJ.
"""
import asyncio
import json
import os
import re
import unicodedata
from datetime import date
from pathlib import Path

import cerebro

DEMORA = True
RAIZ = Path(__file__).parent
# Vai pra pasta Documentos do Windows, dentro de "7 SevenCode" (onde ele guarda as coisas da empresa).
PASTA = Path(os.path.expanduser("~")) / "Documents" / "7 SevenCode"

PALETA = {"fundo": "#17191f", "azul": "#0479da", "texto": "#1a1a1a", "apoio": "#555"}
PREVIA_DIR = RAIZ / "web" / "docs-preview"  # prévias servidas em /web/docs-preview/<id>.html (mesma origem do HUD)

_logo_cache = {"uri": None}


def _logo_data_uri():
    """O logo da 7code embutido (base64), pra prévia e .docx não dependerem de caminho externo."""
    if _logo_cache["uri"] is None:
        try:
            import base64
            dados = (RAIZ / "web" / "marca" / "sevencode.png").read_bytes()
            _logo_cache["uri"] = "data:image/png;base64," + base64.b64encode(dados).decode()
        except OSError:
            _logo_cache["uri"] = ""
    return _logo_cache["uri"]


def _porta():
    try:
        return json.loads((RAIZ / "config.json").read_text(encoding="utf-8")).get("porta", 8765)
    except (OSError, ValueError):
        return 8765


def _sa(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def _slug(t):
    s = re.sub(r"[^a-z0-9]+", "-", _sa(t)).strip("-")
    return (s or "documento")[:40]


# ---------------------------------------------------------------- entender o pedido
# gerar um documento: "monta um contrato", "faz uma proposta de software", "elabora um termo"
GERAR = re.compile(
    r"\b(?:cria?r?|faz(?:er)?|monta?r?|gera?r?|escreve[r]?|prepara?r?|elabora?r?|redig[ei]r?|bola?r?|refaz(?:er)?|"
    r"atualiza?r?|revisa?r?)\b.{0,40}?"
    r"\b(contrato|proposta(?:\s+comercial)?|documento|termo(?:\s+de\s+uso)?|minuta|acordo|recibo|or[çc]amento\s+formal)\b",
    re.I)
# explicar / mostrar: "o que pode num contrato", "me explica os docs da 7sevencode", "quais documentos a gente tem"
EXPLICAR = re.compile(
    r"\b(?:o que (?:pode|n[aã]o pode|deve|precisa|tem que)|o que vai|como (?:monta|faz|escrev|é)|me explica|"
    r"explica|quais|que)\b.{0,40}?\b(contrato|proposta|documento|termo|cl[aá]usul\w*|minuta)\b"
    r"|\b(?:olha|v[eê]|mostra|quais s[aã]o)\b.{0,25}?\bdoc(?:umento)?s?\b.{0,20}?\b(?:da\s+)?(?:7\s*seven\s*code|sevencode|7code|empresa)\b",
    re.I)

TIPOS = [
    (re.compile(r"\bproposta|or[çc]amento\s+formal\b", re.I), "proposta"),
    (re.compile(r"\bcontrato|minuta|acordo|termo\b", re.I), "contrato"),
    (re.compile(r"\brecibo\b", re.I), "recibo"),
]


def _tipo(t):
    for rx, nome in TIPOS:
        if rx.search(t):
            return nome
    return "documento"


def _assunto(texto):
    """Pra quem / sobre o quê: pega o resto depois de 'pro/pra/para/do/de ...' pra dar contexto ao cérebro."""
    t = re.sub(r"\b(?:contrato|proposta(?:\s+comercial)?|documento|termo(?:\s+de\s+uso)?|minuta|acordo|recibo|"
               r"or[çc]amento\s+formal|de\s+software|de\s+presta[çc][aã]o\s+de\s+servi[çc]o)\b", " ", texto, flags=re.I)
    t = re.sub(r"\b(?:cria?r?|faz(?:er)?|monta?r?|gera?r?|escreve[r]?|prepara?r?|elabora?r?|redig[ei]r?|bola?r?|"
               r"refaz(?:er)?|atualiza?r?|revisa?r?|jarvis|um|uma|o|a|me|pra mim)\b", " ", t, flags=re.I)
    m = re.search(r"\b(?:pr[oa]|para|do|da|de|ao|a|com)\s+(?P<q>.+?)[.!?]*$", t, re.I)
    q = (m.group("q").strip() if m else t.strip())
    q = re.sub(r"\s+", " ", q).strip(" ,.:-")
    return q


def entender(texto):
    t = (texto or "").strip()
    if GERAR.search(t):
        return {"modo": "gerar", "tipo": _tipo(t), "assunto": _assunto(t)}
    if EXPLICAR.search(t):
        return {"modo": "explicar", "pergunta": t}
    return None


# ---------------------------------------------------------------- base de conhecimento
def _conhecimento():
    partes = []
    for caminho in (RAIZ / "especialidades" / "documentos-juridico-contabil.md",
                    RAIZ / "conhecimento" / "7sevencode.md"):
        try:
            partes.append(caminho.read_text(encoding="utf-8"))
        except OSError:
            pass
    return "\n\n".join(partes)[:16000]


PERSONA = (
    "Você é o assessor de documentos da 7 SevenCode (software house do Rafael Bittencourt). Monta e revisa PROPOSTA "
    "comercial e CONTRATO de software (desenvolvimento sob medida e/ou licença de uso SaaS), com cabeça jurídica e "
    "contábil brasileira (Código Civil, CDC, LGPD, Lei do Software 9.609/98). Profissional, claro e direto, português "
    "do Brasil, com as cláusulas/seções certas e sem juridiquês inútil. Regras duras: NÃO prometa resultado que não se "
    "controla (posição no Google, aumento de vendas, zero bug); NÃO prometa nota fiscal (a empresa recebe como PF — "
    "nota é o gatilho pra abrir CNPJ); em SaaS é LICENÇA de uso, o código é da 7 SevenCode; inclua cláusula de LGPD "
    "sempre que o sistema tratar dado pessoal (o Porthon trata); nada de cláusula abusiva (CDC art. 51). O que você não "
    "souber (CPF/CNPJ do cliente, valor fechado, prazo), deixe um campo visível entre colchetes tipo "
    "[preencher: CPF do cliente] em vez de inventar.")


def _esquema():
    return ('{ "titulo": "título do documento", "subtitulo": "uma linha (partes/assunto/data)", '
            '"secoes": [ { "titulo": "NOME DA SEÇÃO OU CLÁUSULA", "paragrafos": ["...", "..."], '
            '"itens": ["ponto a", "ponto b"] } ], "campos": ["campos que ficaram pra preencher"], '
            '"observacao": "aviso curto de que é documento base pra revisar" }')


async def _gerar_doc(tipo, assunto):
    alvo = {"proposta": "uma PROPOSTA COMERCIAL de software",
            "contrato": "um CONTRATO de prestação de serviço / licença de uso de software",
            "recibo": "um RECIBO de pagamento",
            "documento": "o documento pedido (proposta ou contrato de software, o que fizer mais sentido)"}[tipo]
    pedido = (f"Monte {alvo} da 7 SevenCode" + (f", para: {assunto}." if assunto else ".")
              + " Use TUDO que souber da 7 SevenCode e do padrão. Preencha o que dá; o resto, [campos pra preencher]. "
              "Responda SÓ o JSON no esquema: " + _esquema())
    bruto = await cerebro.completar(
        [{"role": "system", "content": PERSONA + "\n\nBASE (padrão + dados reais da empresa):\n" + _conhecimento()},
         {"role": "user", "content": pedido}],
        json_mode=True, temperatura=0.3, max_tokens=2200, dificil=True)
    try:
        d = json.loads(bruto[bruto.index("{"):bruto.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return None
    d["secoes"] = [s for s in (d.get("secoes") or []) if isinstance(s, dict)]
    return d if d.get("titulo") and d["secoes"] else None


# ---------------------------------------------------------------- render + salvar no Word
def _esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _html(doc):
    hoje = date.today().strftime("%d/%m/%Y")
    secoes = []
    for i, s in enumerate(doc["secoes"], 1):
        corpo = "".join(f"<p>{_esc(p)}</p>" for p in (s.get("paragrafos") or []) if str(p).strip())
        itens = [str(x) for x in (s.get("itens") or []) if str(x).strip()]
        if itens:
            corpo += "<ul>" + "".join(f"<li>{_esc(x)}</li>" for x in itens) + "</ul>"
        titulo = _esc(s.get("titulo") or f"Seção {i}")
        secoes.append(f'<h2>{titulo}</h2>{corpo}')
    campos = [str(c) for c in (doc.get("campos") or []) if str(c).strip()]
    bloco_campos = ("<div class='campos'><strong>A preencher antes de enviar:</strong><ul>"
                    + "".join(f"<li>{_esc(c)}</li>" for c in campos) + "</ul></div>") if campos else ""
    obs = _esc(doc.get("observacao") or
               "Documento base gerado pela 7 SevenCode — revise antes de enviar. Não substitui advogado/contador.")
    assinaturas = (
        "<div class='assin'><div class='linha'>7 SevenCode — Rafael Bittencourt</div>"
        "<div class='linha'>Contratante</div></div>")
    return f"""<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; color: {PALETA['texto']}; max-width: 720px; margin: 40px auto;
          line-height: 1.55; font-size: 11pt; }}
  .topo {{ border-bottom: 3px solid {PALETA['azul']}; padding-bottom: 10px; margin-bottom: 18px;
           display: flex; align-items: center; gap: 12px; }}
  .logo {{ height: 34px; width: auto; }}
  .marca {{ color: {PALETA['azul']}; font-size: 20pt; font-weight: 700; letter-spacing: .5px; }}
  .marca small {{ color: {PALETA['apoio']}; font-weight: 400; font-size: 10pt; }}
  h1 {{ font-size: 16pt; margin: 6px 0 2px; }}
  .sub {{ color: {PALETA['apoio']}; margin: 0 0 4px; }}
  .data {{ color: {PALETA['apoio']}; font-size: 9pt; }}
  h2 {{ color: {PALETA['azul']}; font-size: 12pt; margin: 20px 0 6px; }}
  p {{ margin: 6px 0; text-align: justify; }}
  ul {{ margin: 6px 0; }}
  .campos {{ background: #eef5fd; border-left: 4px solid {PALETA['azul']}; padding: 8px 14px; margin: 18px 0; font-size: 10pt; }}
  .assin {{ display: flex; gap: 40px; margin-top: 50px; }}
  .assin .linha {{ flex: 1; border-top: 1px solid #333; padding-top: 6px; text-align: center; font-size: 9pt; }}
  .obs {{ color: {PALETA['apoio']}; font-size: 8.5pt; margin-top: 26px; border-top: 1px solid #ddd; padding-top: 8px; }}
</style></head><body>
<div class="topo">{('<img class="logo" src="' + _logo_data_uri() + '" alt="7 SevenCode">') if _logo_data_uri() else ''}<div class="marca">7 SevenCode <small>· software sob medida</small></div></div>
<h1>{_esc(doc['titulo'])}</h1>
<p class="sub">{_esc(doc.get('subtitulo') or '')}</p>
<p class="data">Documento gerado em {hoje} — 7sevencode.com.br</p>
{''.join(secoes)}
{bloco_campos}
{assinaturas}
<p class="obs">{obs}</p>
</body></html>"""


def _texto(doc):
    linhas = [doc["titulo"], doc.get("subtitulo") or "", ""]
    for s in doc["secoes"]:
        linhas.append((s.get("titulo") or "").upper())
        for p in (s.get("paragrafos") or []):
            if str(p).strip():
                linhas.append(str(p))
        for x in (s.get("itens") or []):
            if str(x).strip():
                linhas.append("• " + str(x))
        linhas.append("")
    campos = [str(c) for c in (doc.get("campos") or []) if str(c).strip()]
    if campos:
        linhas.append("A PREENCHER: " + "; ".join(campos))
    return "\n".join(l for l in linhas).strip()


def _salvar_e_abrir(doc):
    """Escreve o .docx e abre no Word (Office de verdade). Fallback: .doc (HTML) que o Word também abre."""
    PASTA.mkdir(parents=True, exist_ok=True)
    base = PASTA / f"{date.today():%Y-%m-%d}-{_slug(doc['titulo'])}"
    html = _html(doc)
    # 1) Word de verdade via COM: abre o HTML e salva como .docx editável.
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        tmp = base.with_suffix(".html")
        tmp.write_text(html, encoding="utf-8")
        destino = base.with_suffix(".docx")
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = True
        d = word.Documents.Open(str(tmp))
        d.SaveAs(str(destino), FileFormat=16)  # 16 = .docx (wdFormatDocumentDefault)
        try:
            tmp.unlink()
        except OSError:
            pass
        return destino, "word"
    except Exception:
        pass
    # 2) Sem Word automatizável: grava .doc com o HTML — o Word (ou WordPad/navegador) abre.
    destino = base.with_suffix(".doc")
    try:
        destino.write_text(html, encoding="utf-8")
        os.startfile(str(destino))
        return destino, "doc"
    except Exception:
        try:
            alt = base.with_suffix(".html")
            alt.write_text(html, encoding="utf-8")
            os.startfile(str(alt))
            return alt, "html"
        except Exception:
            return None, "erro"


def _copiar(texto):
    try:
        import controle_pc
        controle_pc.area_de_transferencia("copiar", texto)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- salvar no painel (folha em branco) + HUD
_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
          "novembro", "dezembro"]
# títulos de seção que NÃO viram cláusula própria: o fecho/assinatura é montado no padrão da casa (RODAPE_ASSINATURAS)
_SECAO_ASSINATURA = re.compile(r"\bassinatur|\bfecho\b|\bencerr", re.I)


def _data_extenso():
    h = date.today()
    return f"{_EMPRESA['cidade']}, {h.day} de {_MESES[h.month - 1]} de {h.year}"


def _rodape_assinaturas(cliente):
    """O mesmo padrão dos modelos do painel (RODAPE_ASSINATURAS em lib/documentos.ts): fecho, local/data, duas
    assinaturas lado a lado (CONTRATADA/CONTRATANTE) e as testemunhas."""
    cli = _esc(cliente or "[preencher: nome do contratante]")
    return (
        '<p class="fecho">E, por estarem assim justas e contratadas, as partes firmam o presente instrumento em duas '
        'vias de igual teor e forma, na presença das testemunhas abaixo.</p>\n'
        f'<p class="local-data">{_esc(_data_extenso())}.</p>\n'
        '<p class="assinaturas">\n'
        '  <span><span class="linha-assinatura"></span><br><strong>Rafael Bittencourt</strong><br>CONTRATADA</span>\n'
        f'  <span><span class="linha-assinatura"></span><br><strong>{cli}</strong><br>CONTRATANTE</span>\n'
        '</p>\n'
        '<p class="testemunhas">Testemunhas:</p>\n'
        '<p class="assinaturas">\n'
        '  <span><span class="linha-assinatura"></span><br>Nome:<br>CPF:</span>\n'
        '  <span><span class="linha-assinatura"></span><br>Nome:<br>CPF:</span>\n'
        '</p>')


def _corpo_painel(doc, tipo="contrato", cliente=None):
    """Monta o corpo em HTML com as tags que o painel aceita (p, h2, strong, ul/li) + o rodapé de assinatura no padrão
    da casa. O painel aplica o timbre e o logo da 7code por cima; aqui vai só o conteúdo."""
    partes = []
    for i, s in enumerate(doc["secoes"]):
        t = (s.get("titulo") or "").strip()
        if _SECAO_ASSINATURA.search(t):
            continue  # assinatura/fecho vêm do rodapé-padrão, não como cláusula do modelo
        # O painel numera o h2 sozinho ("CLÁUSULA N — …", em maiúsculas via CSS). Tiro número/‘cláusula’ do título
        # pra não duplicar, e deixo só o texto.
        t = re.sub(r"^\s*(?:cl[aá]usula\s+)?\d+\s*[\.\)\-–—:]*\s*", "", t, flags=re.I).strip()
        # a 1ª seção costuma ser a qualificação das partes: vai como parágrafo de abertura (sem virar cláusula)
        classe = ' class="partes"' if i == 0 and re.search(r"\bparte", _sa(t)) else ""
        if t and not classe:
            partes.append(f"<h2>{_esc(t)}</h2>")
        for p in (s.get("paragrafos") or []):
            if str(p).strip():
                partes.append(f"<p{classe}>{_esc(p)}</p>")
                classe = ""
        itens = [x for x in (s.get("itens") or []) if str(x).strip()]
        if itens:
            partes.append("<ul>" + "".join(f"<li>{_esc(x)}</li>" for x in itens) + "</ul>")
    campos = [c for c in (doc.get("campos") or []) if str(c).strip()]
    if campos:
        partes.append('<p class="nota"><strong>A preencher antes de enviar:</strong> ' + _esc("; ".join(campos)) + "</p>")
    if tipo == "proposta":
        # proposta não se assina (é oferta); fecha com a validade, como os modelos do painel.
        partes.append('<p class="validade">Proposta válida por 15 dias a partir da data acima. '
                      'O aceite formaliza a contratação.</p>')
    else:
        partes.append(_rodape_assinaturas(cliente))
    return "\n".join(partes)


def _cliente_do_assunto(assunto):
    """Tira um nome de cliente razoável do assunto ('pro condomínio Ventos do Sul' → 'Condomínio Ventos do Sul')."""
    a = re.sub(r"\b(?:licen[çc]a|do\s+porthon|de\s+software|pra|para|pro)\b", " ", assunto or "", flags=re.I)
    a = re.sub(r"\s+", " ", a).strip(" ,.:-")
    return a[:120].title() if a else None


# Prévia IDÊNTICA ao painel: mesma folha.css, mesma faixa (logo + dados da empresa) e o MESMO corpo que foi pro banco.
# Dados da empresa espelhados de lib/documentos.ts → EMPRESA (sem CNPJ enquanto é PF).
_EMPRESA = {"marca": "7SevenCode", "razao": "Rafael Bittencourt", "cidade": "Porto Alegre", "uf": "RS",
            "tel": "(51) 98012-8983", "email": "r.bittencourt.dev@gmail.com"}


def _previa_painel_html(doc, corpo):
    hoje = date.today().strftime("%d/%m/%Y")
    e = _EMPRESA
    # mesma estrutura do EditorTexto (cabecalho-editor) e mesmas CSS vars do PAGINA_WORD (Calibri 11, margem Normal)
    return f"""<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<link rel="stylesheet" href="/web/doc-folha.css">
<style>
  html,body {{ margin:0; background:#2b2f36; }}
  .palco-doc {{ padding:22px 12px; display:flex; justify-content:center; }}
</style></head><body>
<div class="palco-doc"><div class="editor-documento" style="--folha-fonte:Calibri, Carlito, 'Segoe UI', Arial, sans-serif;
  --folha-tamanho:11pt; --folha-entrelinha:1.08; --folha-depois:8pt;
  --folha-margem-topo:25mm; --folha-margem-esquerda:30mm; --folha-margem-direita:30mm;">
  <div class="folha folha-editor numerado">
    <div class="cabecalho-editor">
      <div class="faixa"><img class="faixa-logo" src="/web/marca/logo-nav.webp" alt="{_esc(e['marca'])}" width="600" height="111">
        <div class="faixa-lado"><span class="faixa-data">{hoje}</span></div></div>
      <p class="emissor"><strong>{_esc(e['razao'])}</strong><br>{_esc(e['cidade'])}/{_esc(e['uf'])} · {_esc(e['tel'])} · {_esc(e['email'])}</p>
      <h1>{_esc(doc['titulo'])}</h1>
    </div>
    {corpo}
  </div>
</div></body></html>"""


def _escrever_previa(doc_id, doc, corpo):
    """Grava a prévia (idêntica ao painel) em web/docs-preview/<id>.html e devolve a URL servida (mesma origem do HUD)."""
    PREVIA_DIR.mkdir(parents=True, exist_ok=True)
    (PREVIA_DIR / f"{doc_id}.html").write_text(_previa_painel_html(doc, corpo), encoding="utf-8")
    return f"http://127.0.0.1:{_porta()}/web/docs-preview/{doc_id}.html"


def _mostrar_no_hud(titulo, previa_url):
    try:
        import uuid
        import extensao
        extensao.publicar_tela({"pagina": {"id": "doc" + uuid.uuid4().hex[:6], "url": previa_url,
                                           "titulo": titulo[:80], "fonte": "7 SevenCode"}})
        return True
    except Exception:
        return False


def _abrir_no_painel(url):
    try:
        import navegadores
        navegadores.abrir(url)
        return True
    except Exception:
        return False


def _salvar_no_painel(doc, cliente, corpo):
    """Cria o documento na folha em branco do painel. Devolve o resultado ou None (cai pro .docx local)."""
    try:
        import painel
        if not painel.configurado():
            return None
        return painel.criar_documento(doc["titulo"], corpo, tipo="livre", cliente_nome=cliente)
    except Exception:
        return None


# ---------------------------------------------------------------- executar
def _explicar(pergunta):
    persona = (PERSONA + "\n\nResponda à dúvida do Rafael sobre documentos da 7 SevenCode de forma direta e prática, em "
               "tópicos curtos quando couber. Use a BASE.\n\nBASE:\n" + _conhecimento())
    try:
        resp = asyncio.run(cerebro.completar(
            [{"role": "system", "content": persona}, {"role": "user", "content": pergunta}],
            temperatura=0.35, max_tokens=800, dificil=True)).strip()
    except Exception:
        resp = ""
    if not resp:
        return "Não consegui montar a explicação agora, chefe. Tenta de novo?", []
    limpo = re.sub(r"[*`#]+", "", resp)
    cartao = {"titulo": "Documentos · 7 SevenCode", "destaque": "O que pode e como montar",
              "linhas": [l.strip() for l in limpo.split("\n") if l.strip()][:20], "copiar": resp}
    return "Sobre os documentos da 7 SevenCode, chefe: " + limpo.split("\n")[0][:200], [cartao]


NOMES = {"proposta": "proposta", "contrato": "contrato", "recibo": "recibo", "documento": "documento"}


def executar(p):
    if p.get("modo") == "explicar":
        return _explicar(p.get("pergunta") or "")

    tipo = p.get("tipo", "documento")
    assunto = p.get("assunto") or ""
    try:
        doc = asyncio.run(_gerar_doc(tipo, assunto))
    except Exception:
        doc = None
    if not doc:
        return (f"Não consegui montar o {NOMES[tipo]} agora, chefe. Tenta de novo, ou me diz pra quem e sobre o quê?", [])

    texto = _texto(doc)
    copiou = _copiar(texto)
    campos = [str(c) for c in (doc.get("campos") or []) if str(c).strip()]
    nota = ""
    if assunto and re.search(r"\bnota\s+fiscal|\bnota\b|\bnf\b", _sa(assunto)):
        nota = (" Lembrando: enquanto a empresa recebe como PF não tem nota fiscal — se o cliente exige nota, "
                "é o gatilho pra abrir o CNPJ.")

    # 1) Caminho principal: salvar na FOLHA EM BRANCO do painel (formatação da 7code, assinável, fica na lista de docs).
    cliente = _cliente_do_assunto(assunto)
    corpo = _corpo_painel(doc, tipo, cliente)
    res = _salvar_no_painel(doc, cliente, corpo)
    if res and res.get("id"):
        previa = _escrever_previa(res["id"], doc, corpo)
        _mostrar_no_hud(doc["titulo"], previa)
        _abrir_no_painel(res["url"])
        numero = f"{res['ano']}/{str(res['numero']).zfill(3)}" if res.get("numero") else ""
        linhas = [s.get("titulo", "") for s in doc["secoes"] if s.get("titulo")]
        if campos:
            linhas += ["", "A preencher: " + "; ".join(campos[:6])]
        linhas.append("Tá no painel em Documentos — é só revisar, preencher e assinar por lá.")
        cartao = {"titulo": doc["titulo"],
                  "destaque": (f"Documento {numero} · no painel" if numero else "Salvo no painel"),
                  "linhas": linhas, "copiar": texto}
        fala = (f"Prontinho, chefe. Montei o {NOMES[tipo]} \"{doc['titulo']}\" e salvei direto na folha em branco do "
                f"painel da 7code" + (f", documento {numero}" if numero else "") + " — já com a formatação da empresa. "
                "Tá aí na tela, e abri no painel pra você revisar e assinar."
                + (f" Deixei {len(campos)} campo{'s' if len(campos) != 1 else ''} pra preencher." if campos else "")
                + nota)
        return fala, [cartao]

    # 2) Reserva: painel indisponível/não configurado (ex.: PC sem o painel) → gera o .docx local e abre no Word.
    caminho, como = _salvar_e_abrir(doc)
    linhas = [s.get("titulo", "") for s in doc["secoes"] if s.get("titulo")]
    if campos:
        linhas += ["", "A preencher: " + "; ".join(campos[:6])]
    linhas.append("Pra mudar: \"tira a cláusula de…\", \"deixa o prazo em 30 dias\", \"inclui a parte de LGPD\".")
    cartao = {"titulo": doc["titulo"], "destaque": doc.get("subtitulo") or NOMES[tipo].capitalize(),
              "linhas": linhas, "copiar": texto}
    onde = {"word": "e abri no Word pra você revisar e assinar",
            "doc": "e abri o arquivo pra você revisar",
            "html": "e abri a prévia pra você",
            "erro": "mas não consegui abrir o arquivo automaticamente"}[como]
    fala = (f"Prontinho, chefe. Montei o {NOMES[tipo]} \"{doc['titulo']}\" {onde} (não consegui falar com o painel "
            "agora, então deixei em arquivo)" + (", e o texto já tá copiado." if copiou else ".")
            + (f" Deixei {len(campos)} campo{'s' if len(campos) != 1 else ''} pra preencher." if campos else "")
            + " É um documento base: revisa antes de enviar." + nota)
    return fala, [cartao]
