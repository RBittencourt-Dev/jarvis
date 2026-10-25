"""Jarvis: cérebro (Ollama), conhecimento local, ferramentas e voz.

Roda em http://localhost:8765. A interface fica em web/index.html.
"""
import asyncio
import hashlib
import json
import math
import os
import random
import re
import subprocess
import threading
import time
import unicodedata
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

import edge_tts
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import primeiro_uso  # noqa: F401  (cria o config.json deste PC antes de qualquer módulo ler)
import anotacoes
import transcricao
import gestos
import aprendizado
import autocorrecao
import bilingue
import skills
import paineis_vivos
import apresentar as slides  # "apresentar" já é uma função daqui (apresentação 3D): o módulo vai como slides
import lembretes
import noticias
import pomodoro
import timer
import sistemas
import automacoes
import cerebro
import avisos_diarios
import celular
import planner7
import rede
import claude_ponte
import claude_conversa
import hud_paineis
import hologramas3d
import ferramentas_extra
import extensao
import fontes
import lugares
import navegadores
import consultas
import microfone
import olhos_e_maos
import contexto
import interpretador
import painel
import pesquisa
import porthon_busca
import porthon_dados
import reunioes
import sistema
import spotify
import vocabulario
import sinonimos
import falas_programadas
import instagram
import marketing
import vendas
import documentos
import imagens
import professor
import seguranca
import especialistas
import voz_efeito
import habilidades
import pronuncia as pronuncia_
import telas
import web
import whatsapp
import windows_nomes
import memoria_conversa
import falas
import codigo
import controle_pc
import conectores
import indice
import pesquisa_painel
import internos
import olho
import proatividade
import noticias_painel
import pois
import radar_ext
import apresentacoes
import hardware
import cofre
import diagnostico
import instalacao
import registro

RAIZ = Path(__file__).parent
CONFIG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
PASTAS_PERMITIDAS = [Path(os.path.expandvars(p)).expanduser().resolve() for p in CONFIG["pastas_permitidas"]]

app = FastAPI()
ultimo_sinal_da_tela = 0.0  # a interface avisa que está aberta; as palmas consultam


@app.middleware("http")
async def sem_cache_na_tela(request, chamar_proximo):
    """A tela sempre pega o HTML/JS/CSS mais novo: o Chrome guardava a versão velha e o rosto voltava a ser pedido."""
    resposta = await chamar_proximo(request)
    if request.url.path in ("/", "/extensao") or request.url.path.endswith((".js", ".css", ".html")):
        resposta.headers["Cache-Control"] = "no-cache, must-revalidate"
    return resposta


# ---------------------------------------------------------------- conhecimento

def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def palavras_de(texto):
    # "precos" e "preco" contam como a mesma palavra
    return {w[:-1] if w.endswith("s") and len(w) > 4 else w for w in re.findall(r"\w{3,}", normalizar(texto))}


def carregar_trechos():
    """Tudo que ele sabe: conhecimento/ + documentos dos projetos + memória do Claude (fontes.py)."""
    trechos = []
    for nome, texto, idade in fontes.ler_fontes():
        partes = re.split(r"(?m)^(?=#{1,3} )", texto)
        for parte in partes:
            parte = parte.strip()
            if len(parte) < 40:
                continue
            titulo = parte.splitlines()[0]
            # trecho grande demais estoura o contexto de um modelo de 3B
            for i in range(0, len(parte), 900):
                pedaco = parte[i:i + 900]
                trechos.append({"doc": nome, "texto": pedaco, "idade": idade,
                                "palavras": palavras_de(pedaco), "titulo": palavras_de(titulo)})
    return trechos


def contar_frequencias(trechos):
    # palavra que aparece em quase todo trecho ("porthon") não ajuda a escolher
    frequencia = {}
    for t in trechos:
        for w in t["palavras"]:
            frequencia[w] = frequencia.get(w, 0) + 1
    return frequencia


def recarregar_conhecimento():
    global TRECHOS, FREQUENCIA
    novos = carregar_trechos()
    TRECHOS, FREQUENCIA = novos, contar_frequencias(novos)


def manter_conhecimento_em_dia():
    """A memória do Claude e os documentos mudam: relê a cada 10 minutos."""
    while True:
        time.sleep(10 * 60)
        try:
            recarregar_conhecimento()
        except Exception:
            pass


TRECHOS = carregar_trechos()
FREQUENCIA = contar_frequencias(TRECHOS)
threading.Thread(target=manter_conhecimento_em_dia, daemon=True).start()
PALAVRAS_VAZIAS = palavras_de(
    "que para com uma por como mais dos das nos nas sobre isso esse essa voce qual quais tem ter sao ser foi esta "
    "tudo bem oi ola jarvis obrigado valeu bom dia boa tarde noite pode fazer faz favor quero queria agora hoje aqui ainda")


FICHAS = ("fatos-essenciais", "perguntas-e-respostas")


def resposta_da_ficha(pergunta):
    """Se a pergunta é (quase) uma das perguntas das fichas, a resposta é a de lá: (fala, cartões) ou None."""
    termos = palavras_de(pergunta) - PALAVRAS_VAZIAS
    if len(termos) < 2:
        return None
    melhor, nota = None, 0.0
    for t in TRECHOS:
        if t["doc"] not in FICHAS or not t["texto"].startswith("## "):
            continue
        titulo = t["titulo"] - PALAVRAS_VAZIAS
        comuns = termos & titulo
        if len(comuns) < 2:
            continue
        nota_t = min(len(comuns) / len(termos), len(comuns) / max(1, len(titulo)))
        if nota_t > nota:
            melhor, nota = t, nota_t
    if not melhor or nota < 0.5:
        return None
    corpo = melhor["texto"].split("\n", 1)[1].strip() if "\n" in melhor["texto"] else ""
    frases = re.split(r"(?<=[.!?])\s+", corpo.replace("\n", " "))
    fala = " ".join(frases[:2])
    return fala, [{"titulo": "Da memória", "destaque": melhor["texto"].split("\n", 1)[0].lstrip("# ").strip(),
                   "texto": corpo[:600], "linhas": []}]


def buscar_conhecimento(pergunta: str, limite: int = 2):
    termos = palavras_de(pergunta) - PALAVRAS_VAZIAS
    pontuados = []
    for t in TRECHOS:
        pontos = sum(math.log(len(TRECHOS) / FREQUENCIA.get(w, 1)) * (2 if w in t["titulo"] else 1)
                     for w in termos & t["palavras"])
        # anotação recente vale mais: de 1,0 (hoje) até 0,4 (três meses ou mais)
        pontos *= max(0.4, 1 - t.get("idade", 0) / 150)
        if t["doc"].startswith("memoria-onde-paramos"):
            pontos *= 0.6  # diário de sessão: retrato do dia, não o estado atual do assunto
        elif t["doc"].startswith("memoria-") and palavras_de(t["doc"][8:].replace("-", " ")) <= termos | {"porthon"}:
            pontos *= 2  # a anotação É sobre isso ("papel-manutencao" para "papel manutenção")
        if t["doc"] in ("7sevencode", "perguntas-e-respostas", "fatos-essenciais", "memoria") or t["doc"].startswith("memoria-"):
            pontos *= 1.3  # resumo escrito para o Jarvis: mais direto que o documento técnico
        if pontos >= 2.5:
            pontuados.append((pontos, t))
    pontuados.sort(key=lambda x: -x[0])
    return [t for _, t in pontuados[:limite]]


# ---------------------------------------------------------------- ferramentas

def caminho_permitido(caminho: str) -> Path:
    p = Path(os.path.expandvars(caminho)).expanduser().resolve()
    if not any(p == base or base in p.parents for base in PASTAS_PERMITIDAS):
        raise PermissionError(f"Fora das pastas liberadas: {p}")
    nome = p.name.lower()
    if any(nome == x or nome.endswith(x) for x in CONFIG["arquivos_proibidos"]):
        raise PermissionError("Esse arquivo guarda senha ou chave; não leio.")
    return p


# ------------------------------------------------------------- índice de programas (fica em disco)
#
# Varrer os atalhos do PC leva ~3,5 s e perguntar ao Windows a lista de apps ~1,3 s. Por isso
# o índice é salvo em apps-conhecidos.json e atualizado em segundo plano; e cada pedido que deu
# certo ("zap" → WhatsApp) é lembrado, para a próxima vez ir direto.

ARQUIVO_APPS = RAIZ / "apps-conhecidos.json"


def _ler_apps():
    if ARQUIVO_APPS.exists():
        try:
            return json.loads(ARQUIVO_APPS.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return {"indice": {}, "aprendidos": {}, "atualizado_em": 0}


APPS = _ler_apps()


def _salvar_apps():
    ARQUIVO_APPS.write_text(json.dumps(APPS, ensure_ascii=False, indent=1), encoding="utf-8")


def atalhos_de_programas():
    lugares = [
        Path.home() / "Desktop",
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
    ]
    atalhos = {}
    for lugar in lugares:
        if lugar.exists():
            for lnk in lugar.rglob("*.lnk"):
                atalhos.setdefault(normalizar(lnk.stem), lnk)
    return atalhos


def apps_do_iniciar():
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
                        "Get-StartApps | ForEach-Object { $_.AppID + [char]9 + $_.Name }"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    return dict(linha.split("\t", 1) for linha in r.stdout.splitlines() if "\t" in linha)


def atualizar_indice_de_apps():
    """Monta o índice do zero (atalhos .lnk + apps do Iniciar, como WhatsApp da Store)."""
    indice = {k: {"tipo": "lnk", "alvo": str(v), "rotulo": v.stem} for k, v in atalhos_de_programas().items()}
    for app_id, rotulo in apps_do_iniciar().items():
        indice.setdefault(normalizar(rotulo), {"tipo": "app", "alvo": app_id, "rotulo": rotulo})
    APPS["indice"] = indice
    APPS["atualizado_em"] = time.time()
    _salvar_apps()


def manter_indice_em_dia():
    while True:
        try:
            atualizar_indice_de_apps()
        except Exception:
            pass
        time.sleep(30 * 60)


threading.Thread(target=manter_indice_em_dia, daemon=True).start()


def procurar_app(alvo):
    indice = APPS["indice"]
    return indice.get(alvo) or next((v for k, v in indice.items() if alvo in k), None)


def lancar(app):
    if app["tipo"] == "cmd":
        subprocess.Popen(app["alvo"])
    elif app["tipo"] == "pasta":
        os.startfile(app["alvo"])
    elif app["tipo"] == "site":
        navegadores.abrir(app["alvo"])
    elif app["tipo"] == "lnk":
        os.startfile(app["alvo"])
    else:
        subprocess.Popen(["explorer.exe", "shell:AppsFolder\\" + app["alvo"]])


def abrir_site(url: str, navegador=None, tela=None):
    if not re.match(r"^https?://", url):
        url = "https://" + url
    navegadores.abrir(url, navegador, tela=tela or "padrao")
    return f"Abri {url}"


def pesquisar_google(consulta: str):
    navegadores.abrir("https://www.google.com/search?q=" + quote_plus(consulta))
    return f"Pesquisei no Google: {consulta}"


def resolver_programa(nome: str, pode_atualizar=True):
    """Acha o que abrir, sem abrir: aprendido → índice → tradução (PC em inglês) → embutido do Windows → pasta."""
    alvo = normalizar(nome).strip()
    if alvo in APPS["aprendidos"]:
        return APPS["aprendidos"][alvo]
    candidatos = windows_nomes.candidatos(alvo)
    for tentativa in candidatos:  # 1º: nome exato (o dito ou a tradução)
        if tentativa in APPS["indice"]:
            return APPS["indice"][tentativa]
    for tentativa in candidatos:
        if tentativa in windows_nomes.EMBUTIDOS:
            return {"tipo": "cmd", "alvo": windows_nomes.EMBUTIDOS[tentativa], "rotulo": tentativa.title()}
    for tentativa in candidatos:  # 2º: um programa que contém o nome
        app = procurar_app(tentativa)
        if app:
            return app
    for tentativa in windows_nomes.candidatos(alvo):
        if tentativa in windows_nomes.EMBUTIDOS:
            return {"tipo": "cmd", "alvo": windows_nomes.EMBUTIDOS[tentativa], "rotulo": tentativa.title()}
    caminho = windows_nomes.pasta(alvo)
    if caminho:
        return {"tipo": "pasta", "alvo": str(caminho), "rotulo": f"a pasta {caminho.name}"}
    if pode_atualizar:
        atualizar_indice_de_apps()  # pode ser um programa instalado agora há pouco
        return resolver_programa(nome, pode_atualizar=False)
    return None


def abrir_programa(nome: str):
    alvo = normalizar(nome).strip()
    app = resolver_programa(nome)
    if not app:
        return f"Não achei nenhum programa chamado '{nome}'."
    try:
        lancar(app)
    except OSError:
        # o caminho gravado sumiu (programa desinstalado ou movido): esquece e procura de novo
        APPS["aprendidos"].pop(alvo, None)
        atualizar_indice_de_apps()
        app = resolver_programa(nome, pode_atualizar=False)
        if not app:
            return f"Não achei nenhum programa chamado '{nome}'."
        lancar(app)
    if APPS["aprendidos"].get(alvo) != app:  # "explorador de arquivos" passa a ir direto para o File Explorer
        APPS["aprendidos"][alvo] = app
        _salvar_apps()
    return f"Abri {app['rotulo']}"


def _abrir_programa_frente(nome: str):
    """Como abrir_programa, mas traz a janela aberta PRA FRENTE (o HUD do Jarvis fica atrás). Usado pelo modelo."""
    return telas.abrir_em(None, lambda: abrir_programa(nome))


def listar_pasta(caminho: str):
    p = caminho_permitido(caminho)
    itens = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))[:80]
    return "\n".join(("[pasta] " if i.is_dir() else "") + i.name for i in itens) or "(vazia)"


def ler_arquivo(caminho: str):
    p = caminho_permitido(caminho)
    texto = p.read_text(encoding="utf-8", errors="replace")
    return texto[:6000] + ("\n...(cortado)" if len(texto) > 6000 else "")


def executar_comando(comando: str):
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", comando],
        capture_output=True, text=True, timeout=90, cwd=str(Path.home() / "Desktop"),
        encoding="utf-8", errors="replace",
    )
    saida = (r.stdout + ("\n" + r.stderr if r.stderr else "")).strip()
    return (saida[:4000] or "(sem saída)") + f"\n[código de saída {r.returncode}]"


def criar_arquivo(caminho: str, conteudo: str):
    p = caminho_permitido(caminho)
    if p.exists():
        return "Esse arquivo já existe; não sobrescrevo."
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(conteudo, encoding="utf-8")
    registro.anotar(f"criar arquivo {p}", "feito", ["criar_arquivo"], desfazer={"tipo": "apagar", "caminho": str(p)}, tipo="acao")
    if p.suffix.lower() in codigo.LINGUAGENS:
        extensao.publicar_cartao({"titulo": "Arquivo criado", "destaque": p.name, "codigo": conteudo[:6000],
                                  "linguagem": codigo.LINGUAGENS[p.suffix.lower()], "caminho": str(p)})
    return f"Criei {p}"


ARQUIVO_MEMORIA = RAIZ / "conhecimento" / "memoria.md"


def lembrancas(ultimas=20):
    if not ARQUIVO_MEMORIA.exists():
        return ""
    linhas = [l for l in ARQUIVO_MEMORIA.read_text(encoding="utf-8").splitlines() if l.startswith("- ")]
    return "\n".join(linhas[-ultimas:])


def lembrar(fato: str):
    fato = " ".join(fato.split())[:300]
    if not ARQUIVO_MEMORIA.exists():
        ARQUIVO_MEMORIA.write_text("# O que o Jarvis aprendeu\n\n", encoding="utf-8")
    with ARQUIVO_MEMORIA.open("a", encoding="utf-8") as f:
        f.write(f"- {fato} ({datetime.now():%d/%m/%Y})\n")
    recarregar_conhecimento()
    return "Guardado na memória."


def parametro(nome, descricao):
    return {nome: {"type": "string", "description": descricao}}


FERRAMENTAS = {
    "abrir_site": (abrir_site, False, "Abre um site no navegador.", parametro("url", "endereço do site")),
    "pesquisar_google": (pesquisar_google, False, "Abre uma pesquisa no Google pra ele ver.", parametro("consulta", "o que pesquisar")),
    "abrir_programa": (_abrir_programa_frente, False, "Abre um programa do PC (ex.: Visual Studio Code, Porthon, Painel 7SevenCode, WhatsApp).", parametro("nome", "nome do programa")),
    "listar_pasta": (listar_pasta, False, "Lista uma pasta.", parametro("caminho", "caminho completo da pasta")),
    "ler_arquivo": (ler_arquivo, False, "Lê um arquivo de texto.", parametro("caminho", "caminho completo do arquivo")),
    "lembrar": (lembrar, False, "Guarda pra sempre um fato sobre ele, a empresa ou o Porthon.", parametro("fato", "o fato, numa frase")),
    "mostrar_holograma": (lambda assunto: mostrar_holograma(assunto), False,
                          "Mostra um HOLOGRAMA 3D animado na tela do Jarvis: peças do PC dele com dados ao vivo (ram, processador, "
                          "placa de vídeo, disco, ou 'hardware' pra todas) ou qualquer assunto que dê pra ver em 3D (órgão, planeta, "
                          "máquina, átomo…). Use sempre que ele pedir pra ver/mostrar/explicar algo físico.",
                          parametro("assunto", "o que mostrar, ex.: 'memória ram', 'hardware', 'o coração humano'")),
    "executar_comando": (executar_comando, True, "Roda um comando do PowerShell no PC e devolve a saída. Use à vontade "
                         "para fazer o que ele pedir no computador; só o que apaga, formata ou desliga pede autorização.",
                         parametro("comando", "comando PowerShell")),
    "criar_arquivo": (criar_arquivo, False, "Cria um arquivo de texto novo (não sobrescreve).",
                      {**parametro("caminho", "caminho completo do arquivo"), **parametro("conteudo", "texto do arquivo")}),
    "buscar_na_web": (ferramentas_extra.buscar_na_web, False, "Busca na internet e devolve os primeiros resultados com "
                      "resumo. Use para qualquer pergunta de fato atual (preço, notícia, placar, horário, lançamento).",
                      parametro("consulta", "o que buscar")),
    "calcular": (ferramentas_extra.calcular, False, "Faz qualquer conta com resultado exato. Use SEMPRE que houver "
                 "conta (porcentagem: 15% de 200 = 0.15*200).", parametro("expressao", "a conta, ex.: (1500*12)*0.85")),
    "ver_tela": (olhos_e_maos.ver_tela, False, "Tira print das telas dele AGORA e responde sobre o que está aparecendo "
                 "(ler erro, ver o que está aberto, achar algo na tela). tela: 'todas', 'esta' (principal) ou 'outra' (vertical).",
                 {**parametro("pergunta", "o que ele quer saber da tela"), **parametro("tela", "todas | esta | outra")}),
    "digitar": (olhos_e_maos.digitar, False, "Escreve um texto na janela que ele está usando (campo de texto, documento, "
                "chat). Use \\n para nova linha.", parametro("texto", "o texto a escrever")),
    "apertar_teclas": (olhos_e_maos.apertar_teclas, False, "Aperta um atalho de teclado na janela dele: 'ctrl+s', 'enter', "
                       "'alt+tab', 'ctrl+shift+t', 'win+d', 'ctrl+c'.", parametro("atalho", "teclas separadas por +")),
    "aprender_habilidade": (aprendizado.aprender_habilidade, False, "Grava uma habilidade nova que ele te ensinou "
                            "(\"aprende que…\", \"quando eu pedir X, faz Y\", \"daqui pra frente…\") ou um jeito que você "
                            "descobriu e ele aprovou. Fica valendo pra sempre.",
                            {**parametro("nome", "nome curto"), **parametro("quando_usar", "quando vale (o pedido dele)"),
                             **parametro("como_fazer", "o passo a passo: ferramentas e comandos exatos")}),
    "esquecer_habilidade": (aprendizado.esquecer_habilidade, False, "Apaga uma habilidade aprendida (\"esquece a habilidade X\").",
                            parametro("nome", "nome da habilidade")),
    # skills (25/10): jeitos de PENSAR por assunto, um .md cada em skills/ (ver skills.py)
    "usar_skill": (skills.usar_skill, False, "Abre uma skill instalada (do índice SKILLS SOB DEMANDA) pra seguir o "
                   "jeito de pensar dela neste pedido.", parametro("nome", "nome da skill")),
    "instalar_skill": (skills.instalar_skill, True, "Instala (ou atualiza) uma skill nova em você quando ele PEDIR "
                       "(\"instala uma skill de X\"). Pede o sim dele.",
                       {**parametro("nome", "curto, minúsculo-com-hífen"), **parametro("descricao", "uma linha"),
                        **parametro("quando", "'sempre' ou palavras-gatilho sem acento separadas por |"),
                        **parametro("conteudo", "3 a 8 frases de orientação prática")}),
    "instalar_skill_do_link": (skills.instalar_skill_do_link, True, "Baixa e instala uma skill de um link https "
                               "(ex.: SKILL.md no GitHub). Pede o sim dele.", parametro("url", "o link")),
    "remover_skill": (skills.remover_skill, True, "Remove uma skill (vai pra skills/_removidas). Pede o sim dele.",
                      parametro("nome", "nome da skill")),
    # painéis ao vivo (25/10): popup bonito que se atualiza sozinho com dados de um site (ver paineis_vivos.py)
    "criar_painel_ao_vivo": (paineis_vivos.criar_painel_ao_vivo, False,
                             "Cria um POPUP AO VIVO que se atualiza sozinho com números de um site (eleição, placar, cotação, "
                             "status...). fonte = link https (prefira API que devolve JSON); campos = JSON {nome: caminho no "
                             "JSON tipo 'cand[0].pvap'} ou {nome: 'descrição do valor'} pra página comum. html = o visual "
                             "(fotos com <img src>, números em <span data-campo=\"nome\">, barra <div class=\"vivo-barra\"><i "
                             "data-largura=\"nome\"></i></div>; classes prontas: vivo-grade, vivo-item, vivo-foto, vivo-nome, "
                             "vivo-num, vivo-rotulo, vivo-barra, vivo-vs). Devolve os primeiros valores: CONFIRA e corrija.",
                             {**parametro("titulo", "título do painel"), **parametro("fonte", "link https da fonte"),
                              **parametro("campos", "JSON {nome: caminho ou descrição}"),
                              **parametro("html", "HTML do visual (opcional: sem ele faz um layout automático)"),
                              **parametro("intervalo", "segundos entre atualizações (padrão 30)"),
                              **parametro("minutos", "por quanto tempo monitorar (padrão 180)")}),
    "apresentar": (slides.apresentar, False,
                   "APRESENTA a resposta na tela com fotos e animações, como num slide (use em TODA resposta que passa "
                   "informação: explicação, comparação, resumo, dados, notícia, produto, lugar, pessoa). blocos = lista JSON: "
                   "{tipo:'capa', titulo, subtitulo, imagem:'busca da foto'}, {tipo:'numeros', itens:[{valor:'204', "
                   "sufixo:'cv', rotulo:'potência'}]}, {tipo:'pontos', titulo, itens:[...]}, {tipo:'etapas', itens:[...]}, "
                   "{tipo:'imagens', busca:'...', quantas:3}, {tipo:'comparacao', colunas:[{titulo, imagem:'busca', "
                   "itens:[...]}]}, {tipo:'texto', texto}. Fotos: escreva a BUSCA em INGLÊS, 2 a 4 palavras concretas "
                   "('gasoline car engine', não 'combustão') — eu acho a foto. Comece com uma capa.",
                   {**parametro("titulo", "título curto"), **parametro("blocos", "lista JSON de blocos")}),
    "parar_painel_ao_vivo": (paineis_vivos.parar_painel_ao_vivo, False, "Para (e fecha) um painel ao vivo pelo título, "
                             "ou 'todos'.", parametro("titulo", "título ou 'todos'")),
    "criar_automacao": (lambda nome, frase, acoes: "Criei a automação " + automacoes.salvar({
                            "nome": nome, "tipo": "frase", "frase": frase, "acoes": re.split(r"\s*[;\n]\s*", acoes)})["nome"],
                        False, "Cria um atalho de voz: quando ele disser a frase, roda as ações em ordem "
                        "(\"quando eu falar bora codar, abre o VS Code e toca Development\").",
                        {**parametro("nome", "nome da rotina"), **parametro("frase", "a frase que dispara"),
                         **parametro("acoes", "ações faladas, separadas por ; (ex.: abre o VS Code; toca Development)")}),
    "mostrar_na_tela": (extensao.mostrar, False, "Mostra um pop-up na tela vertical (extensão do Jarvis): lista, "
                        "comparação, passo a passo, resumo, texto que ele vai querer LER em vez de ouvir. Fale só o resumo.",
                        {**parametro("titulo", "título curto"), **parametro("texto", "o conteúdo (pode ser longo)"),
                         **parametro("itens", "itens de lista separados por ; (opcional, pode ser vazio)")}),
    "ler_site": (ferramentas_extra.ler_site, False, "Lê o texto de uma página da internet.", parametro("url", "endereço")),
    "criar_planilha": (ferramentas_extra.criar_planilha, False, "Cria uma planilha Excel (.xlsx) em Documentos\\Jarvis "
                       "e abre ela pronta pra ele.",
                       {**parametro("nome", "nome do arquivo"), "abas": {"type": "object", "description":
                        'abas da planilha: {"Nome da aba": [["Cabeçalho1", "Cabeçalho2"], ["valor", "valor"], ...]}'}}),
    "comando_jarvis": (None, False, "Executa uma habilidade pronta do Jarvis, escrita como comando curto: "
                       "Spotify, WhatsApp, Instagram (perfil, story, direct, reels), falas programadas ('todo dia às 18h fala X'), "
                       "painel/caixa/leads/CRM/reuniões, Porthon, janelas e telas, volume, modo caverna, "
                       "fechar/minimizar as janelas que você abriu ('minimiza os popups'), fechar aba ('fecha a aba do youtube no opera'). "
                       "Ex.: 'toca Development', 'manda pro Jesus: já tô indo', 'quanto tem no caixa', "
                       "'passa o spotify pra outra tela'.", parametro("comando", "o comando, em português")),
}


def _pesquisar_e_mostrar(assunto, foco=""):
    """Ferramenta do cérebro: pesquisa e mostra o painel (roda numa thread, por isso um laço próprio)."""
    fala, painel_ = asyncio.run(pesquisa_painel.pesquisar(assunto, foco or ""))
    pesquisa_painel.publicar(painel_, ler_topicos=False)
    topicos = "\n".join("- " + t for t in painel_["topicos"])
    fontes = "\n".join(f"[{i}] {f['titulo']} ({f['url']})" for i, f in enumerate(painel_["fontes"], 1))
    return f"Painel mostrado na tela. Resumo: {fala}\nTópicos:\n{topicos}\nFontes:\n{fontes}"


def _planejar(passos, objetivo=""):
    """Mostra o plano na tela (linha do tempo); os passos vão acendendo conforme as ferramentas rodam."""
    lista = [p.strip(" -•") for p in re.split(r"\s*(?:;|\n)\s*", passos or "") if p.strip(" -•")][:10]
    plano_atual.update({"id": "pl" + uuid.uuid4().hex[:6], "objetivo": objetivo, "passos": lista, "feito": 0})
    extensao.publicar_tela({"plano": dict(plano_atual)})
    return "Plano na tela. Agora execute os passos, um por vez, e confira cada resultado."


plano_atual = {}

FERRAMENTAS.update({
    "ver_registro": (registro.ver_registro, False, "Lê o diário do que ele pediu e do que você fez num dia (hoje, ontem, "
                     "segunda, 20/10). Use para 'faz aquilo de ontem', 'repete o que você fez', 'o que eu te pedi hoje'.",
                     {**parametro("dia", "hoje | ontem | anteontem | dia da semana | dd/mm"),
                      **parametro("busca", "palavra pra filtrar (opcional, pode ser vazio)")}),
    "desfazer": (lambda: registro.desfazer_ultimo(), False, "Desfaz a última ação de arquivo que você fez "
                 "(arquivo criado/copiado vai pra lixeira; movido/renomeado/editado volta como era).", {}),
    "planejar": (_planejar, False, "Para tarefa com 3 passos ou mais: mostra o plano na tela ANTES de executar. "
                 "Depois execute passo a passo, confira cada resultado e corrija se falhar (até 3 tentativas).",
                 {**parametro("objetivo", "o que ele quer, numa frase"),
                  **parametro("passos", "os passos, separados por ;")}),
    "procurar_nos_meus_arquivos": (indice.procurar_nos_meus_arquivos, False, "Procura nos documentos e projetos DELE "
                                   "(Desktop e Documentos: código, anotações, textos). Use para perguntas sobre as coisas "
                                   "dele ('onde eu falei de X', 'o que tem no projeto Y sobre Z'). Mande palavras-chave, "
                                   "não a frase inteira (ex.: 'reserva salão festa').",
                                   parametro("consulta", "palavras-chave")),
    "pesquisar_e_mostrar": (_pesquisar_e_mostrar, False, "Pesquisa um assunto na internet e mostra DENTRO do Jarvis um "
                            "painel com resumo em tópicos, fotos e fontes. Use quando ele pedir pra pesquisar, falar "
                            "sobre, explicar algo atual, ou quando você não tiver certeza. Depois fale só o resumo.",
                            {**parametro("assunto", "o assunto"), **parametro("foco", "o que interessa (opcional)")}),
    # arquivos
    "procurar_arquivo": (controle_pc.procurar_arquivo, False, "Acha arquivos/pastas pelo nome nas pastas dele.",
                         {**parametro("nome", "parte do nome"), **parametro("pasta", "pasta onde procurar (opcional)")}),
    "mover_arquivo": (controle_pc.mover_arquivo, False, "Move um arquivo ou pasta (dá pra desfazer).",
                      {**parametro("origem", "caminho completo"), **parametro("destino", "pasta ou caminho novo")}),
    "renomear_arquivo": (controle_pc.renomear_arquivo, False, "Renomeia um arquivo ou pasta (dá pra desfazer).",
                         {**parametro("caminho", "caminho completo"), **parametro("novo_nome", "nome novo com extensão")}),
    "copiar_arquivo": (controle_pc.copiar_arquivo, False, "Copia um arquivo ou pasta.",
                       {**parametro("origem", "caminho completo"), **parametro("destino", "pasta ou caminho novo")}),
    "criar_pasta": (controle_pc.criar_pasta, False, "Cria uma pasta.", parametro("caminho", "caminho completo")),
    "apagar_arquivo": (controle_pc.apagar_arquivo, True, "Manda um arquivo ou pasta pra lixeira (pede o sim dele).",
                       parametro("caminho", "caminho completo")),
    # tela, teclado e sistema
    "area_de_transferencia": (controle_pc.area_de_transferencia, False, "Lê o que ele copiou (acao 'ler') ou copia um "
                              "texto pra ele colar (acao 'escrever').",
                              {**parametro("acao", "ler | escrever"), **parametro("texto", "o texto (só pra escrever)")}),
    "print_da_tela": (controle_pc.print_da_tela, False, "Salva um print em Imagens\\Jarvis.",
                      parametro("tela", "todas | esta | outra")),
    "brilho": (controle_pc.brilho, False, "Muda o brilho do monitor: '70', '+10', '-20' (vazio = diz o atual).",
               parametro("nivel", "0-100, +N ou -N")),
    "listar_janelas": (controle_pc.listar_janelas, False, "Lista as janelas abertas no PC.", {}),
    "clicar_em": (controle_pc.clicar_em, False, "Clica num botão, link, aba ou item pelo NOME que aparece nele, na janela "
                  "da frente (ou na janela cujo título contém 'janela'). Ex.: clicar_em('Salvar').",
                  {**parametro("nome", "texto do botão/item"), **parametro("janela", "parte do título da janela (opcional)")}),
    # programação
    "rodar_codigo": (codigo.rodar_codigo, False, "Roda código (python, javascript ou powershell) numa pasta isolada e "
                     "devolve a saída. Use pra calcular, testar ideia, converter dados, depurar.",
                     {**parametro("linguagem", "python | javascript | powershell"), **parametro("codigo", "o código")}),
    "git": (codigo.git, False, "Git num projeto dele. status/diff/log/branch/show rodam direto; commit, push, pull, "
            "checkout etc. pedem o sim dele.", {**parametro("pasta", "pasta do projeto (ex.: Porthon-System\\lobby)"),
                                                **parametro("argumentos", "ex.: status, log --oneline -5, diff")}),
    "editar_arquivo": (codigo.editar_arquivo, True, "Troca um trecho EXATO de um arquivo por outro (pede o sim dele "
                       "mostrando o antes e o depois; guarda backup).",
                       {**parametro("caminho", "caminho completo"), **parametro("trecho_antigo", "texto exato que existe"),
                        **parametro("trecho_novo", "texto novo")}),
    "mostrar_codigo": (codigo.mostrar_codigo, False, "Mostra código ou saída técnica num painel com realce de sintaxe.",
                       {**parametro("titulo", "título"), **parametro("codigo", "o código"),
                        **parametro("linguagem", "python, javascript, typescript, json, bash…")}),
    "carregar_ferramentas": (None, False, "Carrega mais ferramentas quando precisar. Grupos: " + "; ".join(
                                 f"'{g}' = {d}" for g, d in (
                                     ("arquivos", "listar, ler, criar, procurar, mover, renomear, copiar, apagar, planilha, desfazer"),
                                     ("tela", "ver a tela, digitar, apertar teclas, clicar por nome, janelas, print, "
                                              "área de transferência, brilho"),
                                     ("programacao", "rodar código, git, editar arquivo, mostrar código"),
                                     ("aprender", "aprender/esquecer habilidade, criar automação, instalar/remover skill"),
                                     ("aovivo", "popup ao vivo que se atualiza sozinho com números de um site, e parar ele"),
                                 )) + "; e cada conector ligado nas Configurações pelo nome dele.",
                             parametro("grupos", "nomes dos grupos, separados por vírgula")),
})

# Com modelo pequeno (e no limite grátis por minuto da nuvem), mandar 40 ferramentas em toda pergunta pesa.
# A base vai sempre; o resto o cérebro carrega pelo SENTIDO (carregar_ferramentas). Como atalho, frases que
# claramente pedem um grupo já chegam com ele carregado.
GRUPOS = {
    "base": ["comando_jarvis", "buscar_na_web", "ler_site", "pesquisar_e_mostrar", "mostrar_na_tela",
             "lembrar", "mostrar_holograma", "calcular", "ver_registro", "planejar", "procurar_nos_meus_arquivos", "abrir_programa", "abrir_site",
             "carregar_ferramentas", "pesquisar_google", "usar_skill", "apresentar"],
    "arquivos": ["listar_pasta", "ler_arquivo", "criar_arquivo", "criar_planilha", "procurar_arquivo", "mover_arquivo",
                 "renomear_arquivo", "copiar_arquivo", "criar_pasta", "apagar_arquivo", "desfazer"],
    "tela": ["ver_tela", "digitar", "apertar_teclas", "clicar_em", "listar_janelas", "print_da_tela",
             "area_de_transferencia", "brilho"],
    "programacao": ["rodar_codigo", "git", "editar_arquivo", "mostrar_codigo", "ler_arquivo", "listar_pasta", "criar_arquivo"],
    "aprender": ["aprender_habilidade", "esquecer_habilidade", "criar_automacao", "instalar_skill", "instalar_skill_do_link",
                 "remover_skill"],
    "powershell": ["executar_comando"],
    "aovivo": ["criar_painel_ao_vivo", "parar_painel_ao_vivo", "rodar_codigo"],  # rodar_codigo: espiar o JSON da fonte
}
# 22/10: ele pedia "me mostra meu PC" e o cérebro saía rodando PowerShell. O PowerShell só vem quando o pedido é
# coisa técnica do Windows; pro resto existe habilidade pronta (comando_jarvis) e ferramenta própria.
PEDIDO_TECNICO = re.compile(
    r"power\s*shell|terminal|\bcmd\b|prompt de comando|linha de comando|\bcomando\b|script|processo|servi[cç]o|driver|"
    r"\bip\b|ipconfig|\bdns\b|\bping\b|\bporta\s+\d|instal|desinstal|winget|vari[aá]vel de ambiente|regedit|registro do windows|"
    r"atualiza(?:r|[cç][aã]o)? (?:o|do) windows|tarefa agendada|inicializa[cç][aã]o|bateria|drivers?|\bbios\b|"
    r"espa[cç]o (?:livre|em disco)|limpa(?:r)? (?:a )?(?:lixeira|tempor[aá]rios|cache)|desfragment|vers[aã]o do (?:windows|python|node)", re.I)
ATALHO_DE_GRUPO = [
    ("powershell", PEDIDO_TECNICO),
    ("arquivos", re.compile(r"arquivo|pasta|planilha|documento|renome|mov[ae]|copi[ae]|apag|lixeira|desfa[zç]|\.(?:txt|md|py|js|pdf|docx|xlsx)\b", re.I)),
    ("tela", re.compile(r"\btela\b|print|digit|escrev[ea] (?:a[ií]|isso|no|na)|clica|clique|aperta|janela|copiad|cola\b|"
                        r"[aá]rea de transfer|brilho", re.I)),
    ("programacao", re.compile(r"c[oó]digo|script|program|python|javascript|node|\bgit\b|commit|branch|bug|erro no|"
                               r"depura|debug|fun[cç][aã]o|repo", re.I)),
    ("aovivo", re.compile(r"ao vivo|tempo real|monitor|acompanh|atualizando|placar|apura[cç][aã]o|live\b", re.I)),
    ("aprender", re.compile(r"aprend|ensin|automa[cç]|daqui pra frente|sempre que|quando eu (?:falar|pedir|disser)|esquece a habilidade|"
                            r"\bskills?\b|especialista em", re.I)),
]


def _definicao(nome):
    _, _, desc, props = FERRAMENTAS[nome]
    return {"type": "function", "function": {
        "name": nome, "description": desc,
        "parameters": {"type": "object", "properties": props,
                       "required": [k for k in props if k not in ("itens", "foco", "busca", "pasta", "janela", "texto",
                                                                   "objetivo", "nivel", "tela", "html", "intervalo",
                                                                   "minutos")]}}}


def grupos_para(texto, sessao):
    g = set(sessao.get("grupos") or ())
    for nome, regra in ATALHO_DE_GRUPO:
        if regra.search(texto or ""):
            g.add(nome)
    try:
        g |= conectores.grupos_citados(texto)  # "cria um post no Canva" já chega com as ferramentas do Canva
    except Exception:
        pass
    return g


def definicoes_para(sessao):
    nomes = list(GRUPOS["base"])
    for g in sessao.get("grupos") or ():
        nomes += GRUPOS.get(g, [])
    defs = [_definicao(n) for n in dict.fromkeys(nomes) if n in FERRAMENTAS]
    try:
        defs += conectores.definicoes(sessao.get("grupos") or ())
    except Exception as e:
        print("conectores:", e)
    return defs


# comando de PowerShell que apaga, formata, desliga ou mexe no sistema: esse espera o "sim" dele
COMANDO_PERIGOSO = re.compile(
    r"\b(remove-item|rm|rmdir|rd|del|erase|format(-volume)?|clear-(content|disk|recyclebin)|stop-computer|"
    r"restart-computer|shutdown|diskpart|reg\s+delete|remove-itemproperty|set-executionpolicy|bcdedit|cipher\s+/w|"
    r"uninstall|remove-appxpackage|stop-process|taskkill|netsh|disable-\w+|new-itemproperty|set-itemproperty|"
    r"move-item|rename-item|set-content|out-file|winget|choco|install-package|install-module|send-mailmessage)\b|"
    r"\bpip\s+install\b|\bnpm\s+(?:i|install)\s+-g\b|invoke-(?:webrequest|restmethod)[^|]*-method\s+(?:post|put|delete)|"
    r"\s-recurse\b|>\s*\S", re.I)


def precisa_autorizar(nome, args):
    if nome.startswith("con__"):  # conector: o que envia, publica, apaga ou gasta pede o sim (as Configurações decidem)
        return conectores.precisa_autorizar(nome, args)
    if nome == "rodar_codigo":
        return confirmar() and codigo.precisa_autorizar(args.get("linguagem"), str(args.get("codigo", "")))
    if nome == "git":
        return confirmar() and codigo.git_precisa_autorizar(str(args.get("argumentos", "")))
    if nome in ("apagar_arquivo", "editar_arquivo"):
        return True  # apagar e mexer em código dele: sempre com o sim, mesmo com a confirmação desligada
    if nome == "executar_comando":
        return confirmar() and bool(COMANDO_PERIGOSO.search(str(args.get("comando", ""))))
    return bool(confirmar() and nome in FERRAMENTAS and FERRAMENTAS[nome][1])

DEFINICOES = [
    {"type": "function", "function": {
        "name": nome, "description": desc,
        "parameters": {"type": "object", "properties": props, "required": [k for k in props if k not in ("itens",)]},
    }}
    for nome, (_, _, desc, props) in FERRAMENTAS.items()
]


def rodar_ferramenta(nome, argumentos):
    if nome not in FERRAMENTAS:
        return f"Ferramenta desconhecida: {nome}"
    try:
        return str(FERRAMENTAS[nome][0](**argumentos))[:8000]
    except Exception as e:  # o modelo precisa ver o erro para se corrigir
        return f"Erro: {e}"


# ---------------------------------------------------------------- cérebro

def perfil_do_pc():
    """Cada PC tem o seu papel (Configurações → Geral): "PC do colégio: revisar o 7planner"."""
    perfil = CONFIG.get("perfil") or {}
    if not perfil.get("contexto"):
        return ""
    return f"ESTE PC ({perfil.get('nome') or 'sem nome'}): {perfil['contexto']}\n"


COMO_CHAMAR = {"chefe": 'Chame ele de "chefe".', "senhor": 'Chame ele de "senhor".', "nome": "Chame ele pelo nome ({}).",
               "misto": 'Chame de "chefe" ou "senhor" (varie, e nem toda frase precisa).'}


PERSONALIDADE = RAIZ / "personalidade.md"


def personalidade():
    """O jeito de ser do Jarvis, lido de personalidade.md (ele edita o arquivo e vale na próxima conversa).

    Linhas que começam com "#" são comentário pra quem edita e não vão pro cérebro. Os {campos} são trocados aqui."""
    usuario = CONFIG.get("nome_do_usuario") or "chefe"
    campos = {
        "usuario": usuario,
        "hoje": datetime.now().strftime("%d/%m/%Y"),
        "como_chamar": COMO_CHAMAR.get(CONFIG.get("como_chamar", "misto"), COMO_CHAMAR["misto"]).format(usuario),
        "girias": vocabulario.GAUCHES,
        "desktop": str(Path.home() / "Desktop"),
    }
    try:
        texto = PERSONALIDADE.read_text(encoding="utf-8")
    except OSError:
        texto = "Você é o J.A.R.V.I.S., assistente pessoal do {usuario}. Fale português do Brasil, curto e direto."
    texto = "\n".join(linha for linha in texto.splitlines() if not linha.startswith("#")).strip()
    for chave, valor in campos.items():
        texto = texto.replace("{" + chave + "}", valor)
    return texto


def prompt_do_sistema():
    # fixo durante a conversa: assim o Ollama reaproveita o que já processou (no CPU isso é metade do tempo)
    return f"""{personalidade()}
{perfil_do_pc()}{habilidades.para_prompt()}{skills.para_prompt()}
Habilidades que ele te ensinou (siga sempre):
{aprendizado.ensinadas_para_prompt()}
O que você sabe dele:
{lembrancas() or "(nada ainda)"}"""


ASSUNTOS = [  # (assunto, palavras que o denunciam): a primeira que bater vale
    ("música", r"m[uú]sica|spotify|playlist|[aá]lbum|banda|cantor|tocar|tocando|toca\b|ouvir|som\b|faixa"),
    ("WhatsApp", r"whats|zap|mensagem|contato|manda pr[ao]"),
    ("CRM e leads", r"\blead|radar|crm|cliente em potencial|prospec"),
    ("o computador", r"\bpc\b|computador|windows|volume|tela|wi-?fi|bluetooth|configura"),
    ("o Porthon", r"porthon|p[oó]rton|condom[ií]nio|portaria|morador|encomenda|s[ií]ndico|porteiro"),
    ("a SevenCode", r"seven ?code|empresa|caixa|faturamento|s[oó]cio|painel"),
]
ASSUNTOS_SEM_CONHECIMENTO = ("música", "o computador")  # aqui as anotações do Porthon só atrapalham


def assunto_de(texto):
    for assunto, regra in ASSUNTOS:
        if re.search(regra, texto, re.I):
            return assunto
    return None


def mensagem_do_usuario(texto, assunto=None):
    """A pergunta, com o assunto da conversa e as anotações que COMBINAM com ele."""
    contexto = f"\n\n[Assunto da conversa: {assunto}. Responda dentro dele.]" if assunto else ""
    contexto += skills.para_pedido(texto)  # as skills do assunto ("me explica…" → professor, "deu erro" → depurador)
    if bilingue.parece_ingles(texto):  # a regra da skill sozinha o modelo às vezes ignora: aqui vai junto da frase
        contexto += "\n\n[Ele falou em INGLÊS (está aprendendo): responda EM INGLÊS simples e natural.]"
    if selecao_do_globo and time.time() - selecao_do_globo.get("quando", 0) < 1800:
        contexto += f"\n[Selecionado no globo agora: {selecao_do_globo['nome']} ({selecao_do_globo.get('tipo', 'lugar')}). " \
                    "\"Aqui/esse lugar/esse país\" = isso.]"
    trechos = [] if assunto in ASSUNTOS_SEM_CONHECIMENTO else buscar_conhecimento(texto)
    if not (assunto or assunto_de(texto)):
        # pergunta solta (carro, receita, curiosidade): anotação do Porthon e da empresa só puxa a conversa pra lá
        trechos = [t for t in trechos if t["doc"] == "memoria"]
    if not trechos:
        return texto + contexto
    anotacoes = "\n---\n".join(f"({t['doc']}) {t['texto']}" for t in trechos)
    return f"{texto}{contexto}\n\n[Anotações]\n{anotacoes}\n[Hora atual: {datetime.now():%H:%M}]"


sessoes = {}  # id -> {"mensagens": [...], "pendente": {...}}


def aprender_site(sessao, url):
    """Se o pedido era "abre o X" e o modelo achou o endereço, da próxima vez "abre o X" vai direto."""
    pedido = next((m["content"].split("\n\n[Anotações]")[0] for m in reversed(sessao["mensagens"]) if m["role"] == "user"), "")
    m = PEDIDO_DE_ABRIR.match(pedido.strip())
    if m:
        APPS["aprendidos"][normalizar(m.group(1)).strip()] = {"tipo": "site", "alvo": url, "rotulo": m.group(1)}
        _salvar_apps()


VISUAIS = {"apresentar", "mostrar_na_tela", "criar_painel_ao_vivo", "pesquisar_e_mostrar", "mostrar_codigo",
           "mostrar_holograma"}
_ESTRUTURA = re.compile(r"(?:^|\n)\s*(?:\||#{1,4}\s|```|[-*•]\s|\d+[.)]\s)")


def ponto_de_corte(texto):
    """Até onde a VOZ fala: antes da primeira tabela/lista/título/código, ou no fim da frase depois de ~300 letras.
    None = pode falar tudo. (Pedido dele: informação é apresentada na tela; falar só o resumo.)"""
    m = _ESTRUTURA.search(texto)
    pos = m.start() if m else None
    quebra = texto.rfind("\n")
    if pos is None and quebra >= 0 and len(texto) - quebra < 4:
        pos = quebra  # linha nova que ainda não deu pra saber se é lista ("-" sozinho): espera o resto chegar
    if len(texto) > 200 and texto.count("\n") >= 2:  # várias linhas de informação = é pra ver, não pra ouvir
        pos = min(pos, texto.index("\n")) if pos is not None else texto.index("\n")
    if len(texto) > 300:
        fim = re.search(r"[.!?](?:\s|$)", texto[220:])
        if fim:
            pos = min(pos, 220 + fim.end()) if pos is not None else 220 + fim.end()
    return pos


async def apresentar_texto(texto):
    """Resposta comprida do modelo → apresentação (capa, pontos, números, fotos). Falhou? Vai como pop-up de texto."""
    pedido = ("Transforme a resposta abaixo numa apresentação de slide. Responda SÓ JSON {\"titulo\": \"...\", \"blocos\": [...]} "
              "com blocos destes tipos: {\"tipo\":\"capa\",\"titulo\",\"subtitulo\",\"imagem\":\"busca da foto\"},{\"tipo\":\"numeros\",\"itens\":[{\"valor\",\"sufixo\",\"rotulo\"}]}, {\"tipo\":\"pontos\","
              "\"titulo\",\"itens\":[...]}, {\"tipo\":\"etapas\",\"itens\":[...]}, {\"tipo\":\"comparacao\",\"colunas\":[{\"titulo\","
              "\"imagem\",\"itens\":[...]}]}, {\"tipo\":\"imagens\",\"busca\",\"quantas\":2}, {\"tipo\":\"texto\",\"texto\"}. "
              "Comece com capa; frases curtas; no máximo 6 blocos; código vira texto curto. Busca de foto: 2 a 4 palavras "
              "EM INGLÊS, concretas e visuais (ex.: 'gasoline car engine', 'electric car charging', 'BMW X1 2024'), "
              "nunca palavra abstrata.\n\nRESPOSTA:\n" + texto[:6000])
    try:
        bruto = await cerebro.completar([{"role": "user", "content": pedido}], json_mode=True, temperatura=0.2, max_tokens=1500)
        j = json.loads(bruto[bruto.index("{"):bruto.rindex("}") + 1])
        await asyncio.to_thread(slides.apresentar, str(j.get("titulo") or "Resumo"), json.dumps(j["blocos"]))
    except Exception as e:
        print(f"apresentar_texto falhou: {type(e).__name__}: {e}", flush=True)
        await asyncio.to_thread(extensao.mostrar, "Resposta", texto)


async def pensar(sessao):
    """Ciclo modelo → ferramenta → modelo. Solta o texto aos pedaços, para a voz começar antes do fim."""
    sid = next((k for k, v in sessoes.items() if v is sessao), None)
    passos, deu_erro = [], False  # o caminho deste pedido: se der certo, vira aprendizado
    falhas = {}  # ferramenta → quantas vezes falhou neste pedido (3 = para de insistir nela)
    plano_atual.clear()
    comecou = time.time()
    mostrou = False  # já pôs algo na tela neste pedido (apresentação, popup, painel ao vivo…)?
    for _ in range(10):
        texto, chamadas, falado = "", [], 0
        try:
            async for tipo, valor in cerebro.conversar(sessao["mensagens"], definicoes_para(sessao), 0.5):
                if tipo == "texto":
                    texto += valor
                    # 25/10: a voz fala só o resumo; tabela/lista/título/código ou texto comprido vai pra TELA
                    corte = ponto_de_corte(texto)
                    ate = len(texto) if corte is None else corte
                    if ate > falado:
                        yield {"trecho": texto[falado:ate]}
                        falado = ate
                else:
                    chamadas = valor
        except Exception as e:
            yield {"erro": f"cérebro fora do ar: {str(e)[:120]}"}
            return
        sessao["mensagens"].append({"role": "assistant", "content": texto, **({"tool_calls": chamadas} if chamadas else {})})
        if not chamadas and falado < len(texto.rstrip()):
            # o modelo escreveu um "documento" em vez de apresentar: eu mesmo transformo em apresentação
            if not mostrou:
                await apresentar_texto(texto)
            yield {"trecho": " " + random.choice(["Botei o resto na tela, chefe.", "O detalhe tá na tela.",
                                                   "Deixei tudo apresentado aí na tela."])}
        if any(c["function"]["name"] in VISUAIS for c in chamadas):
            mostrou = True
        if not chamadas:
            if passos and not deu_erro and sessao.get("pedido"):
                aprendizado.gravar_caminho(sessao["pedido"], passos)
                if len(passos) == 1 and passos[0]["ferramenta"] == "comando_jarvis":
                    # resolveu com uma habilidade pronta: a mesma frase vai direto pra ela, sem IA
                    interpretador.aprender(sessao["pedido"], passos[0]["args"].get("comando", ""))
                ultimo_caminho["pedido"], ultimo_caminho["quando"] = sessao["pedido"], time.time()
            yield {"fim": True}
            return
        if texto and not texto.endswith((" ", "\n")):
            yield {"trecho": " "}
        for chamada in chamadas:
            if parar_agora["em"] > comecou:  # ele mandou parar: não executa mais nada deste pedido
                yield {"trecho": "Parei, chefe."}
                yield {"fim": True}
                return
            nome = chamada["function"]["name"]
            args = chamada["function"].get("arguments") or {}
            if nome == "executar_comando" and not PEDIDO_TECNICO.search(sessao.get("pedido") or ""):
                # pediu pra mostrar/abrir/tocar e o cérebro foi pro PowerShell: não roda, manda ele usar a habilidade certa
                sessao["mensagens"].append({"role": "tool", "tool_call_id": chamada.get("id"), "content":
                    "NÃO executado: ele não pediu nada de PowerShell. Use comando_jarvis com a frase dele "
                    f"(\"{(sessao.get('pedido') or '')[:120]}\"), mostrar_holograma, pesquisar_e_mostrar ou abrir_programa."})
                passos.append({"ferramenta": nome, "args": args})
                deu_erro = True
                continue
            if precisa_autorizar(nome, args):
                sessao["pendente"] = {"nome": nome, "args": args, "tool_call_id": chamada.get("id")}
                yield {"pendente": {"nome": nome, "args": args}}
                return
            yield {"ferramenta": nome}  # resposta que usou ferramenta depende do momento: não é aprendida
            passo = {"id": chamada.get("id") or uuid.uuid4().hex[:6], "nome": nome, "resumo": resumo_do_passo(nome, args),
                     "estado": "rodando", "plano": plano_atual.get("id")}
            yield {"passo": passo}
            extensao.publicar_tela({"passo": passo})
            if nome == "carregar_ferramentas":
                pedidos = {g.strip().lower() for g in re.split(r"[,;\s]+", str(args.get("grupos", ""))) if g.strip()}
                validos = {g for g in pedidos if g in GRUPOS or g in conectores.nomes_ligados()}
                sessao["grupos"] = set(sessao.get("grupos") or ()) | validos
                sessao["carregados"] = validos  # a próxima pergunta (continuação) já vem com eles
                resultado = (f"Carregado: {', '.join(sorted(validos))}. As ferramentas novas já estão disponíveis."
                             if validos else f"Grupo desconhecido. Existem: {', '.join([*GRUPOS, *conectores.nomes_ligados()])}.")
            elif nome.startswith("con__"):
                resultado = await conectores.chamar(nome, args)
            elif nome == "comando_jarvis":
                resultado = ""
                async for e in habilidade(sid, sessao, str(args.get("comando", ""))):
                    if "cartao" in e or "modo" in e or "microfone" in e:
                        yield e
                    if "pendente" in e:  # a habilidade quer um "sim" (mensagem, reunião…): a tela pergunta
                        yield e
                        return
                    resultado += e.get("trecho", "")
                resultado = resultado.strip() or "Feito."
            else:
                resultado = await asyncio.to_thread(rodar_ferramenta, nome, args)
            if nome == "abrir_site" and resultado.startswith("Abri"):
                aprender_site(sessao, resultado[5:])
            falhou = resultado.startswith(("Erro", "Não ", "Ferramenta desconhecida")) or "[código de saída 0]" not in resultado and nome == "executar_comando"
            deu_erro = deu_erro or falhou
            if falhou:
                falhas[nome] = falhas.get(nome, 0) + 1
                if falhas[nome] >= 3:  # 3 tentativas na mesma ferramenta: para de insistir e explica
                    resultado += "\n[3 tentativas falharam com essa ferramenta: NÃO tente de novo; explique o problema ao Rafael ou use outro caminho.]"
            passo = {**passo, "estado": "erro" if falhou else "ok", "detalhe": resultado[:160]}
            yield {"passo": passo}
            extensao.publicar_tela({"passo": passo})
            passos.append({"ferramenta": nome, "args": args})
            sessao["mensagens"].append({"role": "tool", "tool_call_id": chamada.get("id"), "content": resultado})
    yield {"trecho": "Me enrolei com as ferramentas, senhor. Pode repetir de outro jeito?"}
    yield {"fim": True}


NOMES_DOS_PASSOS = {
    "comando_jarvis": "Executando", "buscar_na_web": "Buscando na web", "ler_site": "Lendo página",
    "pesquisar_e_mostrar": "Pesquisando", "executar_comando": "Rodando no PowerShell", "mostrar_na_tela": "Mostrando",
    "lembrar": "Guardando na memória", "mostrar_holograma": "Montando o holograma", "calcular": "Calculando", "ver_registro": "Lendo o diário", "planejar": "Planejando",
    "procurar_nos_meus_arquivos": "Procurando nos seus arquivos", "abrir_programa": "Abrindo", "abrir_site": "Abrindo site",
    "carregar_ferramentas": "Carregando ferramentas", "ver_tela": "Olhando a tela", "digitar": "Digitando",
    "apertar_teclas": "Apertando teclas", "clicar_em": "Clicando", "rodar_codigo": "Rodando código", "git": "Git",
    "editar_arquivo": "Editando arquivo", "criar_arquivo": "Criando arquivo", "ler_arquivo": "Lendo arquivo",
}


def resumo_do_passo(nome, args):
    rotulo = NOMES_DOS_PASSOS.get(nome) or (conectores.rotulo(nome) if nome.startswith("con__") else nome.replace("_", " ").capitalize())
    principal = next((str(v) for v in (args or {}).values() if isinstance(v, (str, int, float)) and str(v).strip()), "")
    principal = principal.replace("\n", " ")
    return f"{rotulo}: {principal[:70]}" if principal else rotulo


async def habilidade(sid, sessao, comando):
    """O cérebro pediu uma habilidade pronta: passa pelo roteador (sem interpretar de novo) e repassa os eventos."""
    resposta = await _rotear(sid, sessao, comando, interpretar=False)
    async for linha in resposta.body_iterator:
        for parte in (linha if isinstance(linha, str) else linha.decode()).splitlines():
            if parte.strip():
                yield json.loads(parte)


ABRIR_INTERFACE = re.compile(r"(?:jarvis[ ,]*)?(?:abre|abra|abrir|aparece|mostra|acorda)(?: a| o| tua| sua| a tua| a sua)?"
                             r" (?:tela|janela|interface|hud|cara)(?: (?:do|da) jarvis)?(?: a[ií]| pra mim)?", re.I)


def abrir_interface():
    if time.time() - ultimo_sinal_da_tela < 6:
        return "Já tô na tela, chefe."
    pythonw = RAIZ / ".venv" / "Scripts" / "pythonw.exe"
    subprocess.Popen([str(pythonw), "-c", "import palmas; palmas.abrir_jarvis()"], cwd=RAIZ,
                     creationflags=subprocess.DETACHED_PROCESS)
    return "Abrindo a interface, chefe."


RECURSOS = (skills, paineis_vivos, avisos_diarios, planner7, celular, falas_programadas, instagram, marketing, vendas, documentos, imagens, professor, rede, seguranca, especialistas, timer, lembretes, pomodoro, anotacoes, transcricao, gestos, noticias, sistemas)
CLIMA_EM = re.compile(r"\b(?:em|no|na|pra|para|de)\s+(?P<cidade>(?!hoje|amanh|agora|semana)[^\d?!.]{3,40}?)\s*(?:hoje|amanh[aã]|agora|essa semana)?[?.!]*$", re.I)


SESSAO_ATUAL = {"sid": None}
ultimo_lugar = {}   # o último lugar/endereço mostrado no globo ("mostra o Street View" sem dizer de onde)
street_aberto = {}  # o Street View aberto na extensão: lat, lng, direção


def abrir_street_view(lugar, direcao=0):
    """Abre a visão da rua num pop-up grande da extensão."""
    marcar_globo()
    globo_ocupado["ate"] = time.time() + 600  # enquanto estiver vendo a rua, "beleza" fecha
    street_aberto.update(lat=lugar["lat"], lng=lugar["lng"], direcao=direcao, nome=lugar.get("nome", ""))
    extensao.publicar({"streetview": {"url": lugares.street_view_embutido(lugar["lat"], lugar["lng"], direcao),
                                      "nome": lugar.get("completo") or lugar.get("nome", ""),
                                      "id": extensao.com_id({"titulo": "Street View", "destaque": "street view rua",
                                                             "assunto": lugar.get("nome", "")})["id"]}})
    return "Abrindo a visão da rua aqui na tela, chefe. Diz 'vira pra direita' pra girar, ou 'fecha o Street View'."
globo_ocupado = {"ate": 0.0}  # até quando "beleza"/"volta ao normal" é sobre o globo (e não conversa)
VOLTAR_GLOBO = re.compile(
    r"^(?:jarvis[ ,]*)?(?:beleza|blz|t[aá]\s+bom|t[aá]\s+[oó]timo|ok|okay|valeu|show|perfeito|massa|top|fechou|entendi|"
    r"j[aá]\s+vi|pode\s+(?:voltar|tirar|fechar|sair)|volta(?:r)?\s+(?:ao|pro|para\s+o)\s+normal|volta\s+(?:o\s+globo|a\s+girar)|"
    r"normal|pode\s+deixar|tira\s+isso|fecha\s+isso|some\s+com\s+isso)"
    r"(?:[ ,]+(?:jarvis|chefe|obrigad[oa]|valeu|pode\s+voltar))*[.!]*$", re.I)


def marcar_globo():
    globo_ocupado["ate"] = time.time() + 45  # o globo volta sozinho em 30 s; um pouco de folga pro "beleza"


def tempo_no_globo(cidade=None):
    """Previsão do tempo; o globo da extensão vai até a cidade e a previsão abre em cima."""
    lugar = (lugares.estado(cidade) or lugares.procurar(cidade)) if cidade else None
    lugar = lugar or lugares.casa()
    fala, cartoes = web.tempo(lugar["nome"], lugar["lat"], lugar["lng"])
    cartao = cartoes[0] if cartoes else {}
    if extensao.aberta():
        marcar_globo()
        extensao.publicar({"globo": {**lugar, "id": extensao.com_id({"titulo": "Tempo", "destaque": lugar["nome"]})["id"],
                                     "texto": " · ".join([cartao.get("destaque", ""), *cartao.get("linhas", [])])}})
        return fala, []  # a previsão já aparece em cima do globo
    return fala, [{**cartao, "rapido": True}]


def avisar(fala, cartao=None, importancia="info"):
    """Aviso que chega sozinho (lembrete, pomodoro, site caiu): a tela fala; com a tela fechada, o segundo plano fala.
    Não perturbe / nível de proatividade (Configurações): o que não pode falar agora vira só pop-up, mudo."""
    cartao = extensao.com_id(cartao) if cartao else None
    if proatividade.pode_falar(importancia):
        novidades_de_leads.append({"fala": fala, "cartao": cartao})
    elif not cartao:
        cartao = extensao.com_id({"titulo": "Aviso (silencioso)", "texto": fala})
    if cartao:
        extensao.publicar_cartao(cartao)
    registro.anotar("aviso", fala, tipo="aviso")


vigia_pc = {"em": 0.0, "rotina": time.time() - 3000}  # rotina: 10 min depois de ligar


async def relogio_dos_avisos():
    """A cada 2 s: lembretes e pomodoro que venceram. A cada 5 min: os sites dele."""
    ultima_vigia = 0.0
    while True:
        for recurso in (lembretes, pomodoro):
            try:
                for fala, cartao in await asyncio.to_thread(recurso.vencidos):
                    avisar(fala, cartao, "marcado")
            except Exception as e:
                print("aviso falhou:", recurso.__name__, e)
        try:  # timer: avisa no aparelho que pediu (o do celular toca no celular, não no PC)
            for fala, cartao, origem_ in await asyncio.to_thread(timer.vencidos):
                if origem_ == "celular":
                    marca = extensao.origem.set("celular")
                    extensao.publicar({"aviso": {"fala": fala, "cartao": cartao}})
                    extensao.origem.reset(marca)
                else:
                    avisar(fala, cartao, "marcado")
        except Exception as e:
            print("aviso falhou: timer", e)
        if time.time() - ultima_vigia > 300:
            ultima_vigia = time.time()
            try:
                for fala, cartao in await asyncio.to_thread(sistemas.vigiar):
                    avisar(fala, cartao, "serio")
            except Exception as e:
                print("vigia dos sites falhou:", e)
        if time.time() - vigia_pc["em"] > 60:  # PC apertado (CPU, memória, disco)
            vigia_pc["em"] = time.time()
            try:
                for fala, cartao, imp in await asyncio.to_thread(proatividade.vigiar_pc):
                    avisar(fala, cartao, imp)
            except Exception as e:
                print("vigia do PC falhou:", e)
        if time.time() - vigia_pc.get("planner", 0) > 60:  # 7planner: agenda do dia e "daqui a 10 min" (Marketing/T.I)
            vigia_pc["planner"] = time.time()
            try:
                for fala, cartao in await asyncio.to_thread(planner7.vigiar):
                    avisar(fala, cartao, "marcado")
            except Exception as e:
                print("vigia do 7planner falhou:", e)
        if time.time() - vigia_pc["rotina"] > 3600:  # rotina dele → sugestão de automação
            vigia_pc["rotina"] = time.time()
            try:
                achou = await asyncio.to_thread(proatividade.procurar_rotina)
                if achou:
                    avisar(*achou)
            except Exception as e:
                print("rotina falhou:", e)
        await asyncio.sleep(2)


@app.on_event("startup")
async def ligar_relogio_dos_avisos():
    tarefas_de_fundo.add(asyncio.create_task(relogio_dos_avisos()))


@app.on_event("startup")
async def arrumar_login_do_7planner():
    msg = await asyncio.to_thread(planner7.resgatar_login_trocado)
    if msg:
        print(msg)


@app.on_event("startup")
async def ligar_freellmapi():
    await asyncio.to_thread(cerebro.ligar_freellmapi)


@app.get("/api/painel")
def painel_da_extensao():
    """Mini-painel da extensão: números do PC e o pomodoro."""
    return {"pc": sistemas.numeros_do_pc(), "pomodoro": pomodoro.situacao(), "agora": time.time(),
            "autenticado": rosto_ja_conferido() or not ARQUIVO_ROSTO.exists()}


@app.get("/api/hud")
async def hud_dados():
    """Dados ao vivo dos painéis fixos do HUD (sistema, rede, clima, notícias). Ver hud_paineis.py e web/hud-paineis.js."""
    return await asyncio.to_thread(hud_paineis.tudo)


@app.get("/api/visao/camera")
def api_visao_camera():
    """Último quadro da webcam (com os pontos da mão) pro painel VISÃO. Só quando os gestos estão ligados."""
    import gestos
    jpg = gestos.frame_atual()
    if not jpg:
        return Response(status_code=204)
    return Response(content=jpg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.post("/api/visao/modo")
def api_visao_modo(req: dict):
    """Liga/desliga o 'só tracking' (oculta a câmera, mostra só o esqueleto da mão)."""
    import gestos
    return {"so_tracking": gestos.set_tracking_only(req.get("so_tracking", False))}


musica_tocando = {"agora": False}


def vigiar_musica():
    """Pergunta ao Spotify a cada 8 s se tem som tocando (antes era a cada pedido, e custava 0,6 s em todos)."""
    while True:
        try:
            musica_tocando["agora"] = bool(spotify.configurado() and spotify.tocando())
        except Exception:
            musica_tocando["agora"] = False
        time.sleep(8)


threading.Thread(target=vigiar_musica, daemon=True).start()
ultimo_caminho = {}  # o que o cérebro aprendeu por último ("errado" logo depois desfaz)


def em_linhas(sid, eventos, primeiro=None):
    async def gerar():
        yield json.dumps({"sessao": sid, **(primeiro or {})}, ensure_ascii=False) + "\n"
        async for e in eventos:
            if e.get("cartao"):
                # "na outra tela"/"aqui" que ele pediu; sem dizer: curto na tela principal, grande na vertical
                cartao = extensao.com_id(e["cartao"])
                onde = (sessoes.get(sid) or {}).get("onde") or cartao.get("onde") or extensao.tela_do_cartao(cartao)
                if onde == "aqui" and not extensao.e_pequeno(cartao) and extensao.tem_palco():
                    onde = "palco"  # "me mostra aqui X" grande: no centro da principal
                e = {**e, "cartao": {**cartao, "onde": onde}}
                if onde != "aqui":
                    extensao.publicar({"cartao": e["cartao"]}, extensao.canal_de(onde))  # pop-up em tempo real
                extensao.lembrar_mostrado("cartao", e["cartao"], extensao.canal_de(onde))
            if e.get("modo"):
                extensao.publicar({"modo": e["modo"]})
            yield json.dumps(e, ensure_ascii=False) + "\n"

    return StreamingResponse(gerar(), media_type="application/x-ndjson")


def confirmar():
    return CONFIG.get("confirmar_acoes_perigosas", True)


COMENTARIOS_DE_MUSICA = falas.MUSICA
COMENTARIOS_DO_PAINEL = falas.PAINEL
ESPERAS = falas.ESPERAS


async def comentando(comentarios, tarefa):
    """Fala um comentário curto JÁ e faz o trabalho enquanto isso: nada de silêncio esperando o Spotify ou o painel."""
    import random
    yield {"trecho": falas.escolher(comentarios) + " ", "falar_ja": True}
    try:
        resultado = await asyncio.wait_for(tarefa, 45)  # nunca fica preso no "Um instante"
    except asyncio.TimeoutError:
        resultado = ("Demorou demais pra responder, chefe. Pede de novo daqui a pouco.", [])
    except Exception as e:  # antes o erro matava a resposta e ele ficava mudo depois do "Deixa eu ver"
        import traceback
        traceback.print_exc()
        resultado = (f"Deu um erro aqui, chefe: {type(e).__name__}: {str(e)[:150]}", [])
    fala, cartoes = resultado if isinstance(resultado, tuple) else (resultado, [])
    for c in cartoes:
        yield {"cartao": c}
    yield {"trecho": fala}
    yield {"fim": True}


DIAS_DA_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]
PERGUNTA_HORA = re.compile(r"\b(?:que horas|que hora [eé]|horas s[aã]o|me diz a hora)\b", re.I)
PERGUNTA_DATA = re.compile(r"\b(?:que dia [eé] hoje|qual [eé] a data|que data [eé] hoje|hoje [eé] que dia|dia da semana)\b", re.I)
PERGUNTA_TEMPO = re.compile(r"\b(?:previs[aã]o do tempo|vai chover|como (?:t[aá]|est[aá]) o tempo|clima de hoje|temperatura)\b", re.I)
# acknowledgements/expressões: quando NÃO há nada pendente, viram um "de nada" natural — nunca um comando errado.
# (se houver pergunta pendente, o sim/não é checado ANTES, então "beleza/ok" ali vale como "sim".)
AGRADECIMENTO = re.compile(
    r"^(?:jarvis[ ,]*)?(?:obrigad[oa]|brigad[oa]|muito\s+obrigad[oa]|valeu(?:\s+mesmo)?|vlw|vlws|tmj|tamo\s+junto|"
    r"show(?:\s+de\s+bola)?|perfeito|[oó]timo|massa|tri|maneiro|bacana|demais|top|"
    r"beleza|bele?za|blz|ok|okay|okey|tranquil[oa]|de\s+boa|dboa|suave|firmeza|fechou|fechado|combinado|"
    r"isso(?:\s+a[íi])?|exato|exatamente|entendi|saquei|joia|j[óo]ia|bah,?\s+valeu|"
    r"t[aá]\s+(?:bom|certo|[oó]timo|joia|tranquilo))\b[\wçãõáéíóúâêôà\s,!.]{0,15}$", re.I)
RESPOSTAS_DE_NADA = falas.DE_NADA
PERGUNTA_HABILIDADES = re.compile(
    r"\b(?:"
    r"o que (?:voc[eê]|tu) (?:sabe|consegue|pode|sabes|consegues) fazer|"
    r"o que (?:voc[eê]|tu) faz(?:es)?|"
    r"(?:me\s+)?(?:mostra|lista|diz|fala)\s+(?:tudo\s+)?(?:(?:o\s+)?que\s+)?(?:voc[eê]|tu)\s+(?:sabe|faz|consegue)(?:\s+fazer)?|"
    r"(?:me\s+)?(?:mostra|lista)\s+(?:todas\s+as\s+|as\s+)?(?:tuas\s+|suas\s+)?(?:habilidades|fun[cç][oõ]es|capacidades)|"
    r"quais (?:s[aã]o )?(?:as )?(?:tuas |suas )?(?:fun[cç][oõ]es|habilidades|capacidades)|"
    r"do que (?:voc[eê]|tu) (?:[eé]|és) capaz|me ajuda com o qu[eê]"
    r")\b", re.I)
PERGUNTA_QUEM_E = re.compile(r"^(?:jarvis[ ,]*)?(?:quem (?:[eé]|és) (?:voc[eê]|tu)|qual (?:[eé] )?o seu nome)\??$", re.I)
# contexto: continuar a leitura (ex.: leu 3 de 10 notícias, "lê o resto")
CONTINUAR_LENDO = re.compile(r"^(?:jarvis[ ,]*)?(?:continua(?:r)?\s+(?:lendo|a leitura|a ler|as not[ií]cias|de ler)|"
                             r"l[eê] o resto|l[eê] mais|me l[eê] o resto|l[eê] as outras|mais not[ií]cias|e o resto das not[ií]cias|"
                             r"continua as not[ií]cias)\b[\s\w]{0,12}$", re.I)
def resposta_rapida(texto):
    """Perguntas simples que não precisam do cérebro (e que ele poderia errar, como a hora)."""
    import random
    agora = datetime.now()
    if PERGUNTA_HORA.search(texto):
        return f"São {agora:%H:%M}, chefe."
    if PERGUNTA_DATA.search(texto):
        return f"Hoje é {DIAS_DA_SEMANA[agora.weekday()]}, {agora.day} de {MESES[agora.month - 1]}."
    if AGRADECIMENTO.match(texto.strip()):
        return falas.escolher(RESPOSTAS_DE_NADA)
    if PERGUNTA_QUEM_E.match(texto.strip()):
        return "Sou o Jarvis, o assistente da SevenCode. Estou aqui pra trabalhar pra você, chefe."
    return None


def responder_da_internet(pedido):
    """Responde num cartão; se a internet não trouxer nada, abre a pesquisa no navegador."""
    tipo, termo = pedido
    try:
        resposta = web.responder(pedido)
    except Exception:
        resposta = None
    if resposta:
        return resposta
    if tipo == "imagem":  # Commons não achou: Openverse/NASA, ainda dentro do Jarvis
        fotos = pesquisa_painel.fotos(termo, 6)
        if fotos:
            return f"Aqui, chefe: {termo}.", [{"titulo": "Imagens", "destaque": termo, "imagens": [f["url"] for f in fotos],
                                               "creditos": [f["credito"] for f in fotos], "linhas": []}]
        return f"Não achei fotos livres de {termo}, chefe. Quer que eu abra no Google Imagens?", []
    return f"Não achei um resumo de {termo}, chefe. Quer que eu pesquise a fundo?", []


# ------------------------------------------------------------- modo caverna

ARQUIVO_MODO = RAIZ / "modo.json"
ENTRAR_CAVERNA = re.compile(r"\b(?:modo caverna|entra(?:r)? (?:no|em) modo caverna|bora (?:trabalhar|programar|codar)|"
                            r"hora de (?:trabalhar|programar)|vamos (?:trabalhar|programar))\b", re.I)
SAIR_CAVERNA = re.compile(r"\b(?:sa(?:i|ir|ia) do modo caverna|volta(?:r)? ao (?:modo )?normal|modo normal|"
                          r"desliga o modo caverna|chega de caverna)\b", re.I)


def modo_atual():
    try:
        return json.loads(ARQUIVO_MODO.read_text(encoding="utf-8")).get("modo", "normal")
    except (OSError, ValueError):
        return "normal"


def mudar_modo(modo):
    ARQUIVO_MODO.write_text(json.dumps({"modo": modo}), encoding="utf-8")


def entrar_na_caverna():
    """Ambienta o trabalho: VS Code aberto e a playlist Development tocando. Devolve o que conseguiu fazer."""
    mudar_modo("caverna")
    feito = []
    if abrir_programa("vs code").startswith("Abri"):
        feito.append("VS Code aberto")
    if spotify.configurado():
        try:
            achado = spotify._playlist_ou_curtidas("minha playlist development")
            if isinstance(achado, tuple):
                spotify._dar_play(*achado, "playlist development", "caverna")
                feito.append("playlist Development tocando")
        except Exception:
            pass
    return feito


async def caverna(entrar, sessao=None):
    """Muda o modo (a tela troca de cor e a voz fica mais grave) e fala por cima."""
    if entrar:
        yield {"modo": "caverna"}
        yield {"trecho": "Entrando em modo caverna. ", "falar_ja": True}
        feito = await asyncio.to_thread(entrar_na_caverna)
        yield {"cartao": {"titulo": "Modo caverna", "destaque": "Foco total", "linhas": feito or ["Pronto pra trabalhar"], "rapido": True}}
        yield {"trecho": "Foco total, chefe. Sem distração. " + ("; ".join(feito) + "." if feito else "")}
        if sessao is not None and not pomodoro.ativo():
            sessao["pendente"] = {"pomodoro": pomodoro.FOCO, "nome": "iniciar um pomodoro", "args": {"foco": f"{pomodoro.FOCO} minutos"},
                                  "fala": f"Quer que eu inicie um pomodoro de {pomodoro.FOCO} minutos?"}
            yield {"pendente": {k: sessao["pendente"][k] for k in ("nome", "args", "fala")}}
            return
    else:
        mudar_modo("normal")
        yield {"modo": "normal"}
        yield {"trecho": "Saindo do modo caverna. Bom trabalho, chefe."}
    yield {"fim": True}


def pedido_de_microfone(texto):
    tipo = microfone.entender(texto)
    if tipo == "desmutar" and len(texto.split()) > 5:
        return None  # "escuta, pesquisa tal coisa" é um pedido, não "desmuta"
    return tipo


async def mexer_no_microfone(tipo):
    if tipo == "mutar":
        yield {"microfone": "surdo"}
        yield {"trecho": "Microfone mutado, chefe. Quando quiser, é só dizer desmuta."}
    elif tipo == "mutar_windows":
        yield {"trecho": "Mutando o microfone do computador. Pra voltar, clica no sete da tela.", "falar_ja": True}
        try:
            await asyncio.to_thread(microfone.mutar_windows, True)
            yield {"microfone": "windows"}
        except Exception as e:
            yield {"trecho": f" Não consegui mutar no Windows: {e}"}
    else:
        try:
            if await asyncio.to_thread(microfone.mudo_no_windows):
                await asyncio.to_thread(microfone.mutar_windows, False)
        except Exception:
            pass
        yield {"microfone": "ligado"}
        yield {"trecho": "Tô te ouvindo, chefe."}
    yield {"fim": True}


async def responder_ja(texto, cartoes=()):
    for c in cartoes:
        yield {"cartao": c}
    yield {"trecho": falas.variar(texto)}  # "Pronto, chefe." de sempre vira uma das variações
    yield {"fim": True}


# ------------------------------------------------------------- aprendizado: respostas que se repetem

ARQUIVO_RESPOSTAS = RAIZ / "respostas-aprendidas.json"
respostas = json.loads(ARQUIVO_RESPOSTAS.read_text(encoding="utf-8")) if ARQUIVO_RESPOSTAS.exists() else {}
NAO_GUARDAR = re.compile(r"\b(hora|hoje|agora|amanh|ontem|caixa|saldo|lead|reuni|abre|abrir|cria|apaga|roda|lembr|guarda|meu|minha|eu)\b", re.I)


def chave_da_pergunta(texto):
    return " ".join(sorted(palavras_de(texto) - PALAVRAS_VAZIAS))


def resposta_aprendida(texto):
    """Pergunta que ele já fez (mesmas palavras, qualquer ordem) volta na hora."""
    chave = chave_da_pergunta(texto)
    return respostas.get(chave) if chave and not NAO_GUARDAR.search(texto) else None


ESQUECER = re.compile(r"^(?:jarvis[ ,]*)?(?:t[aá] errado|est[aá] errado|errado|resposta errada|esquece(?: isso)?|n[aã]o é isso|"
                      r"n[aã]o (?:era|foi) isso|entendeu errado|wrong|that'?s wrong)\b", re.I)
ultima_aprendida = {"chave": None}
ultima_interpretacao = {}  # frase que o interpretador traduziu por último ("errado" desfaz)


def esquecer_a_ultima():
    chave = ultima_aprendida["chave"]
    if not chave or chave not in respostas:
        return "Não tenho nenhuma resposta recente guardada para esquecer, chefe."
    del respostas[chave]
    ARQUIVO_RESPOSTAS.write_text(json.dumps(respostas, ensure_ascii=False, indent=1), encoding="utf-8")
    ultima_aprendida["chave"] = None
    return "Entendido, esqueci essa resposta. Me diga o certo que eu guardo."


RESPOSTA_RUIM = re.compile(r"n[aã]o sei|n[aã]o consigo|n[aã]o posso|n[aã]o sou capaz|n[aã]o entendi|n[aã]o tenho (?:acesso|como)|"
                           r"voc[eê] (?:quer|precisa|gostaria)|pode me dizer|parece|talvez|\?", re.I)


def aprender(texto, resposta):
    chave = chave_da_pergunta(texto)
    if not chave or NAO_GUARDAR.search(texto) or len(resposta) < 8 or RESPOSTA_RUIM.search(resposta):
        return  # resposta de dúvida ou recusa não vira regra: da próxima vez ele tenta de novo
    respostas[chave] = resposta
    ultima_aprendida["chave"] = chave
    ARQUIVO_RESPOSTAS.write_text(json.dumps(respostas, ensure_ascii=False, indent=1), encoding="utf-8")


PEDIDO_DE_ABRIR = re.compile(
    r"^(?:jarvis[ ,]*)?"
    r"(?:(?:tu|voc[eê]|vc)\s+)?(?:(?:pode|podes|poderia|consegue|consegues|quero que (?:tu|voc[eê]) )\s*)?"
    r"(?:(?:me\s+)?(?:abr[ae]|abrir|abra|abri|acess[ae]|acessar|entr[ae]|entrar|mostr[ae]|liga|inicia|bota|chama|executa)"
    r"(?:\s+(?:n[oa]s?|em))?)\s+(?:(?:o|a|os|as|meu|minha|um|uma)\s+)?(.+?)[.!?]*$", re.I)


def destino_do_apelido(alvo):
    """Apelidos do config.json: "painel da 7code", "o painel", "painel" caem todos no mesmo atalho."""
    if normalizar(alvo).strip() in windows_nomes.TRADUCOES:
        return None  # nome de programa do Windows ("painel de controle") vem antes do apelido
    palavras = set(normalizar(alvo).split())
    for apelido, destino in CONFIG.get("apelidos", {}).items():
        if set(normalizar(apelido).split()) <= palavras:
            return destino
    return None


# ------------------------------------------------------------- autocorreção (25/10): acerta sozinho, sem perguntar
ultima_autocorrecao = {}  # {"de": "vs cold", "para": "vs code", "quando": t} — "errado" logo depois desfaz
ultima_abertura = {}  # o último "abre X" (como a voz escreveu) — "não, eu falei Y" ensina X → Y


def _alvo_conhecido(alvo):
    """O alvo já abre do jeito que foi dito (apelido, site, programa, pasta)? Sem varrer o PC de novo."""
    return bool(destino_do_apelido(alvo) or navegadores.site_conhecido(alvo) or resolver_programa(alvo, pode_atualizar=False))


def _nomes_que_abrem():
    """Tudo que o 'abre X' conhece: programas do PC, apelidos, sites, nomes em português do Windows, pastas."""
    return (list(APPS["indice"]) + list(APPS["aprendidos"]) + list(CONFIG.get("apelidos", {}))
            + list(navegadores.SITES) + list(windows_nomes.TRADUCOES) + list(windows_nomes.PASTAS))


def autocorrigir(texto, anotar=True):
    """"abre o vs cold" → "abre o vs code": o alvo que não existe vira o nome conhecido que SOA igual.

    Também troca, sem perguntar, palavra que soa como um termo dele com nota alta ("lídis" → leads).
    Na dúvida não troca nada. Devolve o texto (corrigido ou igual)."""
    m = PEDIDO_DE_ABRIR.match(texto.strip())
    if m:
        pedido, _tela = telas.separar(m.group(1))
        pedido, _nav = navegadores.separar(pedido)
        alvo = re.sub(r"^(?:site|programa|app|aplicativo|sistema)\s+(?:do|da|de)\s+", "", pedido).strip()
        aprendida = vocabulario.DADOS["corrigir"].get(vocabulario._sem_acento(alvo))
        if aprendida:  # ele já ensinou ("quando eu falar X é Y") — vale antes do som
            return texto.replace(alvo, aprendida, 1)
        if (alvo and len(alvo.split()) <= 4 and vocabulario._sem_acento(alvo) not in vocabulario.DADOS["nao_corrigir"]
                and not sistema.entender(texto) and not _alvo_conhecido(alvo)):
            certo = autocorrecao.melhor(alvo, _nomes_que_abrem())
            # "configurações de wifi" não vira só "configurações": se o nome achado já está DENTRO do que ele disse,
            # o resto é detalhe que importa (outro caminho cuida), não erro de som
            if certo and set(normalizar(certo).split()) < set(normalizar(alvo).split()):
                certo = None
            if anotar and alvo:
                ultima_abertura.update({"alvo": alvo, "quando": time.time()})
            if certo and certo != normalizar(alvo):
                if anotar:
                    ultima_autocorrecao.update({"de": alvo, "para": certo, "quando": time.time()})
                return texto.replace(alvo, certo, 1)
        elif anotar and alvo:
            ultima_abertura.update({"alvo": alvo, "quando": time.time()})
        return texto  # pedido de abrir: o resto da frase não é palavra pra corrigir por som
    trocas = [(p, t) for p, t, n in vocabulario.suspeitas(texto, com_nota=True) if n >= 0.88]
    for palavra, termo in trocas:
        texto = re.sub(rf"\b{re.escape(palavra)}\b", termo, texto)
        if anotar:
            ultima_autocorrecao.update({"de": palavra, "para": termo, "quando": time.time()})
    return texto


# "não, eu falei VS Code" / "eu disse notion" / "era o excel" logo depois de um "abre X" que deu errado:
# ele APRENDE (o que a voz escreveu → o que ele quis) e já abre o certo. Da próxima vez vai direto.
# (precisa do "não" ou do "quis dizer": "eu falei com o Rihan" é conversa, não correção)
EU_FALEI = re.compile(r"^(?:jarvis[ ,]*)?(?:n[aã]o[ ,]+(?:eu\s+)?(?:falei|disse|pedi|quis\s+dizer|era)|(?:eu\s+)?quis\s+dizer|"
                      r"no[ ,]+i\s+said)\s+(?:o\s+|a\s+)?(?P<certo>[\w .+-]{2,40}?)[.!]*$", re.I)


def aprender_eu_falei(texto):
    """Devolve o nome certo (e já aprendeu a troca), ou None se não for uma correção de um 'abre X' recente."""
    m = EU_FALEI.match(texto.strip())
    if not m or not ultima_abertura or time.time() - ultima_abertura.get("quando", 0) > 120:
        return None
    errado, certo = ultima_abertura["alvo"], m.group("certo").strip()
    if normalizar(errado) == normalizar(certo):
        return None
    chave = vocabulario._sem_acento(errado)
    vocabulario.DADOS["corrigir"][chave] = certo
    if chave in vocabulario.DADOS["nao_corrigir"]:
        vocabulario.DADOS["nao_corrigir"].remove(chave)
    vocabulario._salvar()
    if APPS["aprendidos"].pop(normalizar(errado), None):
        _salvar_apps()
    ultima_abertura.clear()
    ultima_autocorrecao.clear()
    return certo


def desfazer_autocorrecao():
    """Ele disse "errado" logo depois de uma autocorreção: aquela troca nunca mais acontece sozinha."""
    if not ultima_autocorrecao or time.time() - ultima_autocorrecao.get("quando", 0) > 120:
        return None
    de, para = ultima_autocorrecao["de"], ultima_autocorrecao["para"]
    vocabulario.confirmar([(de, para)], False)  # vai pra lista de "não corrigir"
    chave = normalizar(de)
    if APPS["aprendidos"].pop(chave, None):
        _salvar_apps()
    ultima_autocorrecao.clear()
    return f"Foi mal, chefe. Eu tinha entendido '{para}' no lugar de '{de}'; não troco mais. Me fala de novo do seu jeito?"


PERGUNTAS_DO_PAINEL = [
    (re.compile(r"\b(caixa|saldo|dinheiro|faturamento|financeiro|quanto (temos|tem|entrou|saiu))\b", re.I), painel.caixa, "Caixa 7 SevenCode"),
    (re.compile(r"\b(reuni[aã]o|reuni[oõ]es|agenda|compromisso)", re.I), painel.reunioes_de_hoje, "Reuniões de hoje"),
    (re.compile(r"\b(leads?|radar|prospec|retorno)", re.I), painel.leads, "Radar de Leads"),
]


def dados_do_painel(texto):
    """Pergunta sobre caixa, reunião ou leads: lê o painel e responde sem passar pelo modelo."""
    if PEDIDO_DE_ABRIR.match(texto.strip()):
        return None  # "abre o radar" é abrir, não perguntar
    achados = [painel.tentar(f, titulo) for regra, f, titulo in PERGUNTAS_DO_PAINEL if regra.search(texto)]
    if not achados:
        return None
    fala = " ".join(a["fala"] for a in achados if a["fala"])
    if not fala:
        fala = ("Ainda não tenho o seu login do painel, chefe. Preencha o arquivo login-painel.json na minha pasta."
                if not painel.configurado() else "Não consegui ler o painel agora, chefe. O motivo está na tela.")
    return fala, [a["cartao"] for a in achados]


def atalho(texto):
    """Pedido de abrir algo não precisa do modelo: responde na hora."""
    m = PEDIDO_DE_ABRIR.match(texto.strip())
    if not m:
        return None
    pedido, tela = telas.separar(m.group(1))  # "… na outra tela"
    pedido, navegador = navegadores.separar(pedido)
    alvo = re.sub(r"^(?:site|programa|app|aplicativo|sistema)\s+(?:do|da|de)\s+", "", pedido)
    no_nav = (f" no {navegador.title()}" if navegador else "") + \
             (" na outra tela" if tela == "outra" else " nessa tela" if tela == "esta" else "")
    destino = destino_do_apelido(pedido)
    site = destino if destino and destino.startswith("http") else navegadores.site_conhecido(alvo)
    if navegador and (site or "." in alvo):
        # pediu um navegador: é site, mesmo que exista um app com esse nome
        abrir_site(site or alvo.replace(" ", ""), navegador, tela)
        return f"Abrindo {alvo}{no_nav}, chefe."
    if destino and destino.startswith("http"):
        abrir_site(destino, tela=tela)
        return f"Abrindo {alvo}{no_nav}, chefe."
    resultado = telas.abrir_em(tela, lambda: abrir_programa(destino or alvo))
    if resultado.startswith("Abri"):
        return f"Abrindo {resultado[5:]}{no_nav}, senhor."
    if site or "." in alvo:
        abrir_site(site or alvo.replace(" ", ""), navegador, tela)
        return f"Abrindo {alvo}{no_nav}, senhor."
    if len(alvo.split()) <= 4 and not re.match(r"^(?:pra|pro|para|com)\b", alvo, re.I):  # "liga pra Laura" não é app
        return f"Não achei {alvo} instalado no computador, chefe. Quer que eu pesquise na internet?"
    return None  # frase longa: deixa o modelo tentar entender


class Pergunta(BaseModel):
    sessao: str | None = None
    texto: str
    alternativas: list[str] = []  # outras versões do que o Chrome ouviu
    celular: bool = False  # veio da tela do celular: o que mostrar vai só pra ela


class Decisao(BaseModel):
    sessao: str
    autorizado: bool


# Coisas que ele conta de si no meio da conversa: o Jarvis anota sozinho, sem precisar de "guarda aí".
FATO_PESSOAL = re.compile(
    r"^(?:(?:o|a)\s+)?(?:meu|minha|meus|minhas)\s+\w+.{0,60}?\b(?:[eé]|s[aã]o|se chama|chama|fica|mora|tem|gosta|faz anivers[aá]rio)\b"
    r"|^eu\s+(?:gosto|prefiro|moro|trabalho|tenho|sou|adoro|odeio|nasci|uso|tor[cç]o|curto|n[aã]o gosto|sempre|nunca)\b", re.I)
PERGUNTA_OU_PEDIDO = re.compile(r"\?\s*$|^(?:qual|quais|quem|quanto|quantos|como|onde|o que|quando|por que|ser[aá] que)\b", re.I)


def anotar_se_for_fato(texto):
    """"meu carro é uma BMW X1", "eu torço pro Grêmio" → vai pra memória (conhecimento/memoria.md)."""
    texto = texto.strip()
    if FATO_PESSOAL.search(texto) and not PERGUNTA_OU_PEDIDO.search(texto) and 3 <= len(texto.split()) <= 30:
        lembrar(f"O Rafael contou: {texto}")
        return True
    return False


def vira_comando(texto):
    """Sem efeito colateral: diz se o texto cai num caminho conhecido (abrir, painel, PC, Claude…)."""
    return bool(pesquisa.entender(texto) or porthon_busca.entender(texto) or claude_ponte.entender(texto) or whatsapp.entender(texto) or sistema.despedida(texto) or sistema.entender(texto)
                or PEDIDO_DE_ABRIR.match(texto.strip()) or any(r.search(texto) for r, _, _ in PERGUNTAS_DO_PAINEL))


def rota_de(texto, alternativas=(), assunto=None, foco=None):
    """Que caminho o pedido tomaria, SEM executar nada. É o que o treino.py confere."""
    texto, alternativas = sinonimos.normalizar(texto), [sinonimos.normalizar(a) for a in alternativas]
    texto = vocabulario.melhor_alternativa([texto, *alternativas], vira_comando)
    texto = contexto.resolver(texto, foco) or texto
    if extensao.ABRIR.match(vocabulario.corrigir(texto)) or extensao.FECHAR.match(vocabulario.corrigir(texto)):
        texto = vocabulario.corrigir(texto)  # igual ao conversar: "extenção" já chega consertado
    if pedido_de_microfone(texto):
        return "microfone " + pedido_de_microfone(texto)
    interno = internos.entender(texto)
    if interno and interno[0] in ("mover", "fechar_mostrado", "filtro") and not extensao.tem_mostrado() and not pois.ultima:
        interno = None  # igual ao conversar: sem nada na tela, essas frases seguem o caminho antigo
    if interno:
        if interno[0] == "lugar":
            return "globo " + interno[1].lower()
        return f"interno {interno[0]}" + (f" {interno[1]}" if interno[1] is not None else "")
    musical = assunto == "música" or re.match(r"^(?:toca|bota|coloca|p[oõ]e)\s+outra\b", texto, re.I)
    if musical and not spotify.pedido(texto) and spotify.continuacao(texto):
        tipo, valor = spotify.continuacao(texto)
        return "midia " + valor[1] if tipo == "tecla" else "tocar " + valor
    if vocabulario.ENSINO.match(texto.strip()):
        return "ensino"
    texto = autocorrigir(texto, anotar=False)  # igual ao conversar: corrige pelo som, sem perguntar (sem anotar: é só consulta)
    claude = claude_ponte.entender(texto)
    if claude:
        return f"claude {claude['modo']} {claude['projeto']}"
    if MINIMIZAR_JARVIS.match(texto):
        return "minimizar jarvis"
    for recurso in RECURSOS:
        pedido_ = recurso.entender(texto)
        if pedido_:
            return f"{recurso.__name__} " + " ".join(str(v) for k, v in pedido_.items() if k not in ("quando",))
    if lugares.SELECIONAR.match(texto) and lugares.estado(lugares.SELECIONAR.match(texto).group("lugar")):
        return "selecionar " + lugares.estado(lugares.SELECIONAR.match(texto).group("lugar"))["sigla"]
    if lugares.LIMPAR.match(texto):
        return "limpar globo"
    if lugares.STREET.match(texto):
        return "street view"
    if lugares.FECHAR_STREET.match(texto):
        return "fechar street view"
    if lugares.endereco(texto):
        return "endereco " + lugares.endereco(texto)
    if lugares.PERTO.match(texto):
        return "perto " + lugares.entender(texto)
    if lugares.EXPLICITO.match(texto) and lugares.entender(texto):
        return "globo " + lugares.entender(texto)
    if extensao.FECHAR_POPUP.match(texto):
        return "fechar popup " + extensao.FECHAR_POPUP.match(texto).group("assunto")
    if extensao.ABRIR.match(texto):
        return "extensao abrir"
    if extensao.FECHAR.match(texto):
        return "extensao fechar"
    mover_aba = telas.pedido_de_mover_aba(texto)
    if mover_aba:
        return f"mover aba {mover_aba[0] or '-'} {mover_aba[1] or '-'} → {mover_aba[2]}"
    aba = telas.pedido_de_aba(texto)
    if aba:
        return f"aba {aba[0] or '-'} {aba[1] or '-'}" + (" todas" if aba[2] else "")
    if olhos_e_maos.VER_TELA.search(texto):
        return "ver tela " + olhos_e_maos.qual_tela(texto)
    popup = telas.pedido_de_popup(texto)
    if popup:
        return f"popup {popup[0]} {popup[1]}"
    janela = telas.pedido_de_janela(texto)
    if janela:
        return f"janela {janela[0]} {janela[1]}"
    mover = telas.pedido_de_mover(texto)
    if mover:
        return f"mover {mover[0]} → {mover[1]}"
    reuniao = reunioes.entender(texto)
    if reuniao:
        quem = "equipe" if reuniao.get("equipe") else reuniao["quem"] or "?"
        partes = [quem, str(reuniao["dia"] or "?"), str(reuniao["hora"] or "?")[:5]]
        if reuniao.get("titulo"):
            partes.insert(1, reuniao["titulo"])
        if reuniao.get("filtro_dia"):
            partes.insert(1, f"de {reuniao['filtro_dia']}")
        return f"reuniao {reuniao['acao']} " + " · ".join(partes)
    etapa = PEDIDO_DE_ETAPA.match(texto)
    if etapa:
        return f"crm {etapa.group('nome')} → {etapa.group('etapa')}"
    sugestao = PEDIDO_DE_SUGESTAO.match(texto)
    if sugestao:
        return f"sugerir {sugestao.group('nome')}"
    zap = whatsapp.entender(vocabulario.corrigir(texto))
    if zap:
        return "whatsapp em massa" if zap.get("em_massa") else f"whatsapp quem={zap['quem']} texto={zap['texto']}"
    if SAIR_CAVERNA.search(texto):
        return "caverna sair"
    if ENTRAR_CAVERNA.search(texto):
        return "caverna entrar"
    if spotify.QUE_MUSICA.search(texto):
        return "que musica"
    if spotify.ESSA_NAO.match(texto.strip()):
        return "musica errada"
    if spotify.tecla_de_midia(texto):
        return "midia " + spotify.tecla_de_midia(texto)[1]
    if spotify.pedido(texto):
        return "tocar " + spotify.pedido(texto)
    if sistema.despedida(texto):
        return "dormir"
    trancar = BLOQUEAR.search(texto)
    if trancar and trancar.group("alvo").lower() == "jarvis":
        return "trancar jarvis"
    comando = sistema.entender(texto)
    if comando:
        return ("pc!: " if comando[0] else "pc: ") + comando[2]
    if PERGUNTA_HORA.search(texto) or PERGUNTA_DATA.search(texto):
        return "hora/data"
    busca = porthon_busca.entender(texto)
    if busca:
        return porthon_busca.rota(busca)
    pedido_web = web.entender(texto)
    if pedido_web and not resposta_da_ficha(texto):
        return f"web {pedido_web[0]}" + (f" {pedido_web[1]}" if pedido_web[0] in ("imagem", "saber") else "")
    if AGRADECIMENTO.match(texto.strip()):
        return "de nada"
    if PERGUNTA_HABILIDADES.search(texto) or PERGUNTA_QUEM_E.match(texto.strip()):
        return "sobre mim"
    if PERGUNTA_COMMIT.search(texto):
        return "commit"
    if PERGUNTA_ANDAMENTO.search(texto) and re.search(r"porthon|pacote|projeto|paramos|parei|pend", texto, re.I):
        return "andamento"
    procura = pesquisa.entender(texto)
    if procura:
        return pesquisa.rota(procura)
    m = PEDIDO_DE_ABRIR.match(texto.strip())
    if m:
        pedido, tela = telas.separar(m.group(1))
        if tela:
            return f"abrir {pedido} [tela {tela}]"
        pedido, navegador = navegadores.separar(pedido)
        destino = destino_do_apelido(pedido)
        alvo = re.sub(r"^(?:site|programa|app|aplicativo|sistema)\s+(?:do|da|de)\s+", "", pedido)
        site = destino if destino and destino.startswith("http") else navegadores.site_conhecido(alvo)
        if navegador and site:
            return f"abrir {site} no {navegador}"
        if destino and destino.startswith("http"):
            return f"abrir {destino}"
        app = resolver_programa(destino or alvo, pode_atualizar=False)
        if app:
            return f"abrir {app['rotulo']}"
        if site:
            return f"abrir {site} no {navegador or 'chrome'}"
        if len(alvo.split()) <= 4 and not re.match(r"^(?:pra|pro|para|com)\b", alvo, re.I):
            return "não instalado " + alvo
    consulta = consultas.entender(texto)
    if consulta:
        return f"consulta {consulta[0]} {consulta[1] or ''}".strip()
    if porthon_dados.PERGUNTA.search(texto) and not m:
        return "porthon numeros"
    painel_ = [t for r, _, t in PERGUNTAS_DO_PAINEL if r.search(texto)]
    if painel_ and not m:
        return "painel " + "+".join(painel_)
    if ESQUECER.match(texto.strip()):
        return "esquecer"
    if resposta_da_ficha(texto):
        return "ficha"
    return "modelo [" + str(assunto_de(texto) or assunto) + "]"


def leads_do_radar():
    """Leads com WhatsApp, para achar o número quando o contato não está em contatos.json."""
    try:
        return painel._ler("sv_leads", "select=nome,whatsapp,telefone") if painel.configurado() else []
    except Exception:
        return []


async def conversa_de_reuniao(sid, sessao, d, fala):
    """Pergunta o que falta pra marcar a reunião (com quem, dia, hora) e no fim pede a confirmação."""
    if d.get("etapa") == "confirmar":
        sessao["dialogo"] = None
        nome, args = reunioes.confirmacao(d)
        sessao["pendente"] = {"reuniao": d, "nome": nome, "args": args, "fala": fala}
        return em_linhas(sid, pedir_confirmacao(sessao["pendente"]))
    sessao["dialogo"] = None if d.get("etapa") == "cancelado" else d
    cartoes = []
    if d.get("sugeridos") and d.get("etapa") == "quem":
        cartoes = [{"titulo": "Radar · sugestões", "destaque": "Leads quentes",
                    "linhas": [f"{l['nome']} · {painel.NOME_DA_ETAPA.get(l['status'], l['status'])}" for l in d["sugeridos"]]}]
    return em_linhas(sid, responder_ja(fala, cartoes))


async def conversa_de_whatsapp(sid, sessao, d, fala):
    """Continua o diálogo da mensagem: pergunta o que falta ou pede a confirmação final."""
    if d.get("etapa") == "confirmar":
        sessao["dialogo"] = None
        sessao["pendente"] = {"whatsapp": d, "nome": f"mandar no WhatsApp pro {d['quem']}",
                              "args": {"mensagem": d["texto"]}, "fala": fala}
        return em_linhas(sid, pedir_confirmacao(sessao["pendente"]))
    sessao["dialogo"] = None if d.get("etapa") == "cancelado" else d
    if d.get("etapa") == "escolher" and d.get("opcoes"):  # os contatos achados no WhatsApp, numerados na tela
        return em_linhas(sid, responder_ja(fala, [{"titulo": "WhatsApp · qual deles?", "destaque": d.get("como_disse") or "",
                                                   "linhas": [f"{i}. {o['nome']}" + (" (contato)" if o["tipo"] == "contato" else "")
                                                              for i, o in enumerate(d["opcoes"], 1)]}]))
    return em_linhas(sid, responder_ja(fala))


# ------------------------------------------------------------- CRM do Radar por voz

PEDIDO_DE_ETAPA = re.compile(
    r"^(?:marca|marque|muda|mude|coloca|bota|passa|move)\s+(?:o\s+|a\s+)?(?:lead\s+)?(?:d[oa]\s+)?(?P<nome>.+?)\s+"
    r"(?:como|pra|para|em)\s+(?P<etapa>respondeu|interessad[oa]|reuni[aã]o(?: marcada)?|fechado|fechou|cliente|perdido|n[aã]o perturbe)"
    r"(?:\s*[,:]?\s*(?:porque|motivo)\s+(?P<motivo>.+))?[.!]*$", re.I)
PEDIDO_DE_SUGESTAO = re.compile(
    r"^(?:sugere|sugira|me sugere|escreve|monta|faz)\s+(?:uma\s+)?(?:resposta|mensagem|msg|follow[- ]?up)\s+"
    r"(?:pro|pra|para o|para a|para|ao)\s+(?:lead\s+)?(?P<nome>.+?)[.!?]*$", re.I)

novidades_de_leads = []  # avisos prontos que a tela fala quando estiver livre


def vigiar_respostas():
    """De minuto e meio em minuto e meio: algum lead respondeu? (quem marca é a extensão do Radar)"""
    while True:
        time.sleep(90)
        if not painel.configurado():
            continue
        try:
            for l in painel.respostas_novas():
                novidades_de_leads.append({
                    "fala": f"Chefe, o lead {l['nome']} respondeu no WhatsApp.",
                    "cartao": {"titulo": "Radar · resposta", "destaque": l["nome"],
                               "linhas": [x for x in (l.get("categoria"), l.get("cidade")) if x]
                               + ["Diga: sugere uma resposta pro " + l["nome"].split()[0]]}})
        except Exception:
            pass


threading.Thread(target=vigiar_respostas, daemon=True).start()


def um_lead(nome):
    """Acha o lead pelo nome; devolve (lead, None) ou (None, fala explicando o problema)."""
    achados = painel.achar_leads(nome)
    if not achados:
        return None, f"Não achei nenhum lead chamado {nome} no Radar, chefe."
    if len(achados) > 1:
        nomes = ", ".join(l["nome"] for l in achados[:3])
        return None, f"Achei {len(achados)} leads com esse nome: {nomes}. Qual deles?"
    return achados[0], None


async def texto_do_modelo(instrucao):
    return (await cerebro.completar([{"role": "user", "content": instrucao}], temperatura=0.6)).strip('"')


async def sugerir_resposta(lead):
    etapa = painel.NOME_DA_ETAPA.get(lead["status"], lead["status"])
    tipo = lead.get("categoria") or lead.get("nicho") or "empresa"
    cidade = f", de {lead['cidade']}" if lead.get("cidade") else ""
    passo = f"Próximo passo anotado: {lead['proximo_passo']}. " if lead.get("proximo_passo") else ""
    return await texto_do_modelo(
        "Escreva UMA mensagem curta de WhatsApp (no máximo 3 frases, sem emojis em excesso, tom cordial e direto) "
        "do Rafael, da SevenCode (software house que faz sites e sistemas, e o Porthon para condomínios), "
        f"para o lead {lead['nome']} ({tipo}{cidade}). Etapa no CRM: {etapa}. {passo}"
        "O objetivo é avançar a conversa para uma reunião rápida. Responda só com o texto da mensagem.")


PEDACO = re.compile(r"^(?:e\s+)?(?:(?:d[oa]s?|de|no|na|nos|nas|pro|pra|para|em|com|pelo|pela)\s+\S.{0,40}|"
                    r"tamb[eé]m\s+(?:d[oa]s?|no|na)\s+\S.{0,30}|aqui|na outra tela|todas?|tudo)[.!?]*$", re.I)


def juntar_com_o_anterior(sessao, texto):
    """"do youtube" logo depois de "fecha as abas" vira "fecha as abas do youtube" — se a frase junta for um comando.
    "e do instagram" troca o alvo; "no chrome" acrescenta. Devolve o texto juntado, ou None."""
    anterior, quando = sessao.get("ultimo_pedido") or ("", 0)
    t = vocabulario.limpar(vocabulario.corrigir(texto.strip())).strip(" .!?")
    if not anterior or time.time() - quando > 20 or not PEDACO.match(t):
        return None
    base = anterior
    m = re.match(r"^e\s+(d[oa]s?|de)\s+(.+)$", t, re.I)
    if m:  # "e do instagram": o mesmo pedido, outro alvo (o navegador, se tinha, continua no fim)
        nav = re.search(r"\s+(?:no|na)\s+(?:google chrome|chrome|opera(?: gx)?|edge|firefox)$", base, re.I)
        nucleo = base[:nav.start()] if nav else base
        sem_alvo = re.sub(r"\s+(?:d[oa]s?|de)\s+.+$", "", nucleo, flags=re.I)
        candidatos = [f"{sem_alvo} {m.group(1)} {m.group(2)}{nav.group(0) if nav else ''}", f"{base} {m.group(1)} {m.group(2)}"]
    else:
        candidatos = [f"{base} {re.sub(r'^e\s+', '', t, flags=re.I)}"]
    for junto in candidatos:
        if not rota_de(junto).startswith(("modelo", "ensino", "pergunta")):
            return junto
    return None


MOSTRAR_ONDE = re.compile(
    r"^(?P<pedido>(?:jarvis[ ,]*)?(?:me\s+)?(?:mostr\w*|exib\w*|p[oõ]e|bota|coloca|joga)\b.+?)\s+"
    r"(?:(?P<outra>(?:na|pra|para|pra a|para a|l[aá] na)\s+(?:outra|segunda)\s+tela|na\s+tela\s+vertical|na\s+tua\s+extens[aã]o|"
    r"na\s+extens[aã]o)|(?P<aqui>aqui(?:\s+mesmo)?|nessa\s+tela|na\s+tela\s+principal|na\s+minha\s+frente))[.!]*$", re.I)


@app.post("/api/conversar")
async def conversar(p: Pergunta):
    sid = p.sessao if p.sessao in sessoes else str(uuid.uuid4())
    sessao = sessoes.setdefault(sid, {"mensagens": [], "pendente": None})
    if p.celular:
        sessao["celular"] = True
    extensao.origem.set("celular" if sessao.get("celular") else "pc")
    if sessao.get("celular") and (internos.LIMPAR_CELULAR.match(p.texto.strip())
                                  or internos.LIMPAR_CELULAR.match(vocabulario.limpar(p.texto.strip()))):
        # no celular "fecha tudo"/"limpa a tela" é o que ELE abriu lá; no PC "fecha tudo" fecha os pop-ups do Windows
        extensao.publicar({"limpar_palco": True})
        return em_linhas(sid, responder_ja("Limpei a tela, chefe."))
    _limpo = vocabulario.limpar(p.texto.strip())
    if internos.REINICIAR_JARVIS.match(p.texto.strip()) or internos.REINICIAR_JARVIS.match(_limpo):
        instalacao.reiniciar(atraso=6)  # reiniciar.ps1: mata e sobe server+palmas e reabre a janela; o atraso deixa a fala sair
        return em_linhas(sid, responder_ja("Reiniciando, chefe. Já volto num instante."))
    if internos.LIMPAR_DISPLAY.match(p.texto.strip()) or internos.LIMPAR_DISPLAY.match(_limpo):
        # pedido dele (23/10): no PC também — volta ao estado inicial (holograma, notícias, popups, tudo some).
        extensao.publicar({"limpar_palco": True})
        extensao.publicar({"limpar_palco": True}, canal="hud")
        return em_linhas(sid, responder_ja("Limpei a tela, chefe. Tudo no lugar de novo."))
    if CONTINUAR_LENDO.match(p.texto.strip()) and noticias.ultimo.get("itens") and noticias.ultimo["lida"] < len(noticias.ultimo["itens"]):
        return em_linhas(sid, responder_ja(*noticias.resto()))
    # modo "falar direto com o Claude": o Jarvis passa o microfone. Tudo que ele falar vai pro PRÓPRIO Claude
    # (resposta real, com memória), menos os escapes acima (reiniciar/limpar). "volta pro Jarvis" sai do modo.
    if claude_conversa.ativo(sid):
        fala_c, cartao_c, _segue = await asyncio.to_thread(claude_conversa.falar, sid, p.texto)
        return em_linhas(sid, responder_ja(fala_c, [cartao_c] if cartao_c else ()))
    chave_claude = claude_conversa.entrar_pedido(p.texto)
    if chave_claude:
        nome_c = claude_conversa.entrar(sid, chave_claude)
        return em_linhas(sid, responder_ja(
            f"Prontinho, chefe. Agora você fala direto com o Claude no {nome_c} — quem te responde é ele. Começo só "
            "lendo, sem mexer em nada; diga 'pode editar' quando quiser que ele altere o código, e 'volta pro Jarvis' "
            "pra me chamar de volta. Pode mandar."))
    # "deixa eu ver X", "tu pode me mostrar X", "abra X"… → um jeito só (no meio de um diálogo a fala vai como foi dita:
    # pode ser o texto de uma mensagem)
    if not sessao.get("dialogo"):
        p = Pergunta(sessao=p.sessao, texto=sinonimos.normalizar(vocabulario.corrigir(p.texto)),
                     alternativas=[sinonimos.normalizar(vocabulario.corrigir(a)) for a in p.alternativas], celular=p.celular)
    # "não, eu falei VS Code" logo depois de um "abre X" errado: aprende a troca e já abre o certo
    certo = aprender_eu_falei(p.texto)
    if certo:
        return await rotear(sid, sessao, f"abre {certo}")
    # falou em pedaços ("fecha as abas" … "do YouTube" … "no Chrome"): junta com o pedido anterior
    juntado = juntar_com_o_anterior(sessao, p.texto)
    if juntado:
        p = Pergunta(sessao=p.sessao, texto=juntado, alternativas=[])
    sessao["ultimo_pedido"] = (p.texto.strip(), time.time())
    onde = MOSTRAR_ONDE.match(p.texto.strip())
    sessao["onde"] = None
    if onde:
        sessao["onde"] = "outra" if onde.group("outra") else "aqui"
        p = Pergunta(sessao=p.sessao, texto=onde.group("pedido"), alternativas=[])
        if sessao["onde"] == "outra" and not extensao.aberta() and not sessao.get("celular"):
            extensao.abrir(CONFIG["porta"])  # abre já: os pop-ups desta resposta esperam ela conectar
    d = sessao.get("dialogo")
    if d and d.get("tipo") == "lugar":
        sessao["dialogo"] = None
        escolhido = await asyncio.to_thread(lugares.escolher, d["nome"], p.texto, d["opcoes"])
        if escolhido:
            return em_linhas(sid, mostrar_no_globo(sessao, escolhido))
        return em_linhas(sid, oferecer_google(sessao, f"{d['nome']} {p.texto}"))
    if d and d.get("tipo") == "radar":
        if re.match(r"^(?:deixa|cancela|esquece|n[aã]o|nada)\b", p.texto.strip(), re.I):
            sessao["dialogo"] = None
            return em_linhas(sid, responder_ja("Beleza, deixei o Radar quieto."))
        return em_linhas(sid, pedido_de_leads(sessao, p.texto, d.get("dados")))
    if d and d.get("tipo") == "reuniao":
        fala = await asyncio.to_thread(reunioes.responder, d, vocabulario.limpar(vocabulario.corrigir(p.texto)))
        return await conversa_de_reuniao(sid, sessao, d, fala)
    if d:
        # no meio de uma mensagem de WhatsApp: a fala é a resposta à pergunta dele (texto da mensagem vai como foi dito)
        resposta = p.texto.strip() if d.get("etapa") == "texto" else vocabulario.limpar(vocabulario.corrigir(p.texto))
        return await conversa_de_whatsapp(sid, sessao, d, await asyncio.to_thread(whatsapp.responder, d, resposta, leads_do_radar))
    if street_aberto and lugares.FECHAR_STREET.match(p.texto.strip()):
        street_aberto.clear()
        extensao.publicar({"fechar_street": True})
        return em_linhas(sid, responder_ja("Fechei a visão da rua, chefe."))
    girar = lugares.GIRAR.match(p.texto.strip()) if street_aberto else None
    if girar:
        lado = vocabulario._sem_acento(girar.group("lado"))
        street_aberto["direcao"] = (street_aberto["direcao"] + {"direita": 90, "esquerda": -90}.get(lado, 180 if lado != "frente" else 0)) % 360
        extensao.publicar({"streetview": {"url": lugares.street_view_embutido(street_aberto["lat"], street_aberto["lng"],
                                                                               street_aberto["direcao"]), "girar": True}})
        return em_linhas(sid, responder_ja("Virando."))
    if street_aberto and re.search(r"\b(?:abre|abrir)\b.*\b(?:navegador|google|chrome|maps)\b", p.texto, re.I):
        navegadores.abrir(lugares.street_view(street_aberto), tela="esta")
        return em_linhas(sid, responder_ja("Abri a visão da rua no navegador, chefe."))
    street = lugares.STREET.match(p.texto.strip())
    if street:
        onde = street.group("onde") or street.group("onde2")
        lugar_ = None
        if onde:
            end = lugares.endereco("acha " + onde) if re.search(r"\d", onde) else None
            lugar_ = await asyncio.to_thread(lugares.achar_endereco, end) if end else \
                (await asyncio.to_thread(lugares.resolver, "onde fica " + onde) or (None, None))[1]
            lugar_ = lugar_ if isinstance(lugar_, dict) and "lat" in lugar_ else None
        lugar_ = lugar_ or (ultimo_lugar if ultimo_lugar else None)
        if not lugar_:
            return em_linhas(sid, responder_ja("De qual endereço, chefe? Me diz a rua e o número."))
        if not extensao.aberta():
            await asyncio.to_thread(extensao.abrir, CONFIG["porta"])
        sessao["pendente"] = None
        return em_linhas(sid, responder_ja(abrir_street_view(lugar_)))
    if time.time() < globo_ocupado["ate"] and VOLTAR_GLOBO.match(p.texto.strip()):
        globo_ocupado["ate"] = 0.0
        street_aberto.clear()
        extensao.publicar({"fechar_street": True})
        extensao.publicar({"selecionar": None})  # tira foto/silhueta/opções e volta a girar
        if sessao.get("pendente") and "maps" in sessao["pendente"]:
            sessao["pendente"] = None
        sessao["dialogo"] = None if (sessao.get("dialogo") or {}).get("tipo") == "lugar" else sessao.get("dialogo")
        return em_linhas(sid, responder_ja("Pronto, chefe."))
    # globo, painéis, notícias, telas: o entendedor interno vem antes das regras antigas de janela/pop-up
    # ("passa isso pra outra tela" caía no "mover janela" e respondia "não achei isso aberto")
    interno = internos.no_contexto_hw(p.texto, holo_atual.get("tipo")) or internos.entender(p.texto)
    # hologramas, câmeras e Radar são sempre dele mesmo: não podem cair no "fechar janela"/"abrir programa" antigos
    SEMPRE_INTERNO = ("fechar_holo", "apresentacao", "hardware", "hardware_info", "neural", "neural_adicionar", "neural_buscar",
                      "radar_pedido", "radar_buscar", "radar_estado", "radar_parar")
    if interno and (interno[0] in SEMPRE_INTERNO or
                    interno[0] in ("mover", "fechar_mostrado") and extensao.tem_mostrado(300 if interno[0] == "fechar_mostrado" else 1800)):
        sessao["ultimo_pedido"] = (p.texto.strip(), time.time())
        return em_linhas(sid, await pedido_interno(sid, sessao, *interno))
    rotina = automacoes.pela_frase(vocabulario.corrigir(p.texto))
    if rotina:
        return em_linhas(sid, rodar_automacao(sid, sessao, rotina))
    limpo = vocabulario.limpar(vocabulario.corrigir(p.texto))
    if extensao.ABRIR.match(limpo):
        return em_linhas(sid, responder_ja(await asyncio.to_thread(extensao.abrir, CONFIG["porta"])))
    if extensao.FECHAR.match(limpo):
        return em_linhas(sid, responder_ja(await asyncio.to_thread(extensao.fechar)))
    mover_aba = telas.pedido_de_mover_aba(limpo)
    if mover_aba:
        return em_linhas(sid, responder_ja(await asyncio.to_thread(telas.mover_aba, *mover_aba)))
    aba = telas.pedido_de_aba(vocabulario.limpar(vocabulario.corrigir(p.texto)))
    if aba:
        alvo_, nav_, todas_ = aba
        if todas_ and not alvo_:
            return em_linhas(sid, responder_ja(f"De qual site, chefe?{' No ' + nav_.title() + '.' if nav_ else ''}"))
        return em_linhas(sid, responder_ja(await asyncio.to_thread(telas.fechar_aba, *aba)))
    minimizar = MINIMIZAR_JARVIS.match(limpo)
    if minimizar:
        return em_linhas(sid, minimizar_jarvis())
    fechar_um = extensao.FECHAR_POPUP.match(limpo)
    if fechar_um:
        return em_linhas(sid, responder_ja(await asyncio.to_thread(extensao.fechar_popup, fechar_um.group("assunto"))))
    popup = telas.pedido_de_popup(limpo)
    if popup:
        fala = await asyncio.to_thread(telas.controlar_popups, *popup)
        if popup == ("fechar", "todas"):  # "fecha todos os popups": cartões e janelas que ele abriu
            cartoes = extensao.fechar_popup("tudo")
            fala = "Fechei todos os pop-ups, chefe." if "Fechei" in fala or "Fechei" in cartoes else fala
        return em_linhas(sid, responder_ja(fala))
    janela = telas.pedido_de_janela(vocabulario.limpar(vocabulario.corrigir(p.texto)))
    if janela:
        return em_linhas(sid, responder_ja(await asyncio.to_thread(telas.controlar_janela, *janela)))
    mover = telas.pedido_de_mover(vocabulario.limpar(vocabulario.corrigir(p.texto)))
    if mover:
        return em_linhas(sid, responder_ja(await asyncio.to_thread(telas.mover_app, *mover)))
    reuniao = reunioes.entender(vocabulario.limpar(vocabulario.corrigir(p.texto)))
    if reuniao and painel.configurado():
        sessao["assunto"] = "CRM e leads"
        return await conversa_de_reuniao(sid, sessao, reuniao, await asyncio.to_thread(reunioes.proximo_passo, reuniao))
    etapa = PEDIDO_DE_ETAPA.match(vocabulario.limpar(vocabulario.corrigir(p.texto)))
    if etapa and painel.configurado():
        lead, problema = await asyncio.to_thread(um_lead, etapa.group("nome"))
        if problema:
            return em_linhas(sid, responder_ja(problema))
        chave = vocabulario._sem_acento(etapa.group("etapa"))
        status = painel.ETAPAS.get(chave) or painel.ETAPAS[chave.split()[0]]
        nome_etapa = painel.NOME_DA_ETAPA[status]
        sessao["pendente"] = {"crm": {"id": lead["id"], "status": status, "motivo": etapa.group("motivo")},
                              "nome": f"mudar no CRM: {lead['nome']} → {nome_etapa}",
                              "args": {"lead": lead["nome"], "de": painel.NOME_DA_ETAPA.get(lead["status"], lead["status"]),
                                       "para": nome_etapa},
                              "fala": f"Vou marcar o lead {lead['nome']} como {nome_etapa} no CRM. Confirma?"}
        return em_linhas(sid, pedir_confirmacao(sessao["pendente"]))
    sugestao = PEDIDO_DE_SUGESTAO.match(vocabulario.limpar(vocabulario.corrigir(p.texto)))
    if sugestao and painel.configurado():
        lead, problema = await asyncio.to_thread(um_lead, sugestao.group("nome"))
        if problema:
            return em_linhas(sid, responder_ja(problema))
        texto_sugerido = await sugerir_resposta(lead)
        telefone = whatsapp.numero_do_texto(lead.get("whatsapp") or "")
        if not telefone:
            return em_linhas(sid, responder_ja(f"Sugestão pro {lead['nome']}: {texto_sugerido} Esse lead não tem WhatsApp no Radar."))
        conversa = {"quem": lead["nome"], "telefone": telefone, "texto": texto_sugerido, "etapa": "confirmar"}
        sessao["pendente"] = {"whatsapp": conversa, "nome": f"mandar no WhatsApp pro {lead['nome']}",
                              "args": {"mensagem": texto_sugerido},
                              "fala": f"Sugestão pro {lead['nome']}: {texto_sugerido} Quer que eu mande?"}
        return em_linhas(sid, pedir_confirmacao(sessao["pendente"]))
    zap = whatsapp.entender(vocabulario.corrigir(p.texto.strip()))
    if zap:
        if zap.get("em_massa"):
            abrir_site("https://radar-7sevencode.vercel.app")
            return em_linhas(sid, responder_ja("Disparo pros leads é com o Radar, chefe: ele manda com ritmo seguro "
                                               "pra não banirem o seu número. Abri ele pra você."))
        fala = await asyncio.to_thread(whatsapp.proximo_passo, zap, leads_do_radar)
        return await conversa_de_whatsapp(sid, sessao, zap, fala)
    texto = vocabulario.melhor_alternativa([p.texto, *p.alternativas], vira_comando)
    texto = interpretador.ja_aprendida(texto) or texto
    ensinado = vocabulario.ensino(texto)
    if ensinado:
        return em_linhas(sid, responder_ja(ensinado))
    # 25/10: não pergunta mais "você quis dizer…?" — corrige sozinho pelo som ("vs cold" → VS Code);
    # se errar, ele diz "errado" e a troca é desfeita e esquecida (desfazer_autocorrecao)
    texto = autocorrigir(texto)
    await asyncio.to_thread(anotar_se_for_fato, texto)  # e segue: o cérebro responde normalmente
    return await rotear(sid, sessao, texto)


NAO_PERTURBE = re.compile(r"^(?:jarvis[ ,]*)?(?:(?P<desliga>desliga|desativa|tira|sai\s+do)|liga|ativa|entra\s+n[oa]|modo|bota\s+n[oa])?\s*"
                          r"(?:o\s+)?(?:modo\s+)?n[aã]o\s+perturbe[.!]*$", re.I)


def mudar_config(novos):
    """Grava no config.json e já vale no servidor (o resto dos módulos lê o arquivo quando precisa)."""
    atual = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
    atual.update(novos)
    (RAIZ / "config.json").write_text(json.dumps(atual, ensure_ascii=False, indent=2), encoding="utf-8")
    CONFIG.update(novos)
    cerebro.CONFIG.update(novos)
    return atual


async def pesquisar_no_painel(sessao, termo, foco="", usar_cache=True):
    """Pesquisa que aparece DENTRO do Jarvis: painel com tópicos, fotos e fontes; a voz lê com o tópico aceso."""
    import random
    contexto.guardar(sessao, termo)
    if not extensao.aberta() and extensao.preferida():
        await asyncio.to_thread(extensao.abrir, CONFIG["porta"])
    extensao.publicar_tela({"atividade": {"tipo": "pesquisando", "texto": f"Pesquisando {termo}"}})
    yield {"trecho": random.choice([f"Pesquisando {termo}, chefe.", f"Deixa eu levantar tudo sobre {termo}.",
                                    f"Varrendo a internet atrás de {termo}.", f"Um instante, buscando {termo}."]) + " ",
           "falar_ja": True}
    try:
        fala, painel_ = await pesquisa_painel.pesquisar(termo, foco, usar_cache)
    except Exception as e:
        extensao.publicar_tela({"atividade": {"tipo": "erro", "texto": "Pesquisa falhou"}})
        yield {"trecho": f"A pesquisa falhou agora, chefe: {str(e)[:80]}"}
        yield {"fim": True}
        return
    frases = pesquisa_painel.publicar(painel_)
    extensao.publicar_tela({"atividade": {"tipo": "concluido", "texto": painel_["titulo"]}})
    # a voz lê o resumo e os tópicos; cada frase acende o seu tópico no painel (o -1 é o resumo)
    yield {"leitura": {"id": painel_["id"], "frases": [fala, *frases[:4]], "indices": [-1, *range(min(4, len(frases)))]}}
    yield {"fim": True}


def area_falada(onde):
    """"Brasil", "RS", "perto de mim", "o centro" (dentro da área anterior) → {nome, lat, lng, caixa}."""
    o = re.sub(r"^(?:o|a|os|as|do|da|no|na)\s+", "", onde.strip(), flags=re.I)
    if re.fullmatch(r"(?:perto\s+de\s+mim|aqui(?:\s+perto)?|minha\s+casa|perto\s+de\s+casa|meu\s+bairro)", o, re.I):
        c = lugares.CASA
        return {"nome": "perto de você", "lat": c["lat"], "lng": c["lng"], "caixa": pois._caixa_perto(c["lat"], c["lng"])}
    uf = lugares.estado(o)
    if uf:
        o = uf["nome"] + ", Brasil"
    anterior = (pois.ultima or {}).get("area") or {}
    if anterior.get("nome") and anterior["nome"] not in ("no Brasil", "perto de você") and len(o.split()) <= 3:
        dentro = olho.area(f"{o}, {anterior['nome']}")  # "só no centro" depois de "em Porto Alegre"
        if dentro:
            return dentro
    achado = olho.area(o)
    if not achado or (achado["caixa"][1] - achado["caixa"][0]) < 0.02:  # caixa minúscula: provavelmente uma rua homônima
        no_brasil = olho.area(f"{o}, Brasil")
        if no_brasil and (not achado or (no_brasil["caixa"][1] - no_brasil["caixa"][0]) > (achado["caixa"][1] - achado["caixa"][0])):
            achado = no_brasil
    return achado


async def mostrar_pois(sessao, termo, onde="", filtrando=False):
    """Estabelecimentos no globo: todos os pontos marcados, a lista na tela, e o filtro falado depois."""
    yield {"trecho": falas.escolher([f"Procurando {termo}{(' em ' + onde) if onde else ''}.", "Varrendo o mapa, chefe.",
                                     f"Deixa eu achar {termo}."]) + " ", "falar_ja": True}
    if not extensao.aberta():
        await asyncio.to_thread(extensao.abrir, CONFIG["porta"])
    area = None
    if onde:
        area = await asyncio.to_thread(area_falada, onde)
        if not area:
            yield {"trecho": f"Não achei onde fica {onde}, chefe."}
            yield {"fim": True}
            return
    elif selecao_do_globo.get("caixa") and time.time() - selecao_do_globo.get("quando", 0) < 1800:
        area = {"nome": selecao_do_globo["nome"], "caixa": selecao_do_globo["caixa"]}  # o que ele clicou no globo

    def chegaram_mais(itens):  # o Overpass / a varredura por estado acharam mais
        extensao.publicar({"pois": {"termo": termo, "area": pois.ultima.get("area"), "itens": itens[:400], "mais": True}})

    itens, area = await asyncio.to_thread(pois.buscar, termo, area, chegaram_mais)
    marcar_globo()
    globo_ocupado["ate"] = time.time() + 600
    extensao.publicar({"pois": {"termo": termo, "area": area, "itens": itens[:400]}})
    if not itens:
        yield {"trecho": f"Não achei {termo} {area['nome'] if area['nome'].startswith(('no ', 'na ', 'perto')) else 'em ' + area['nome']}, chefe."}
    else:
        onde_txt = area["nome"] if area["nome"].startswith(("no ", "na ", "perto")) else "em " + area["nome"]
        mais = " Vou marcando os outros estados conforme acho." if area["caixa"] == pois.BRASIL else ""
        dica = "" if filtrando or area["caixa"] != pois.BRASIL else " Se quiser, diz a cidade que eu filtro."
        yield {"trecho": f"Achei {len(itens)} {onde_txt}, tão marcados no globo.{mais}{dica}"}
    yield {"fim": True}


async def contar_noticias(sessao, tema):
    """Notícias com foto: painel na tela vertical, foto da matéria da vez na principal, e ele vai contando."""
    yield {"trecho": falas.escolher(["Deixa eu ver as manchetes, chefe.", "Puxando as notícias.", "Um instante, vendo o que tá rolando."]) + " ",
           "falar_ja": True}
    if not extensao.aberta() and extensao.preferida():
        await asyncio.to_thread(extensao.abrir, CONFIG["porta"])
    try:
        intro, painel_, frases = await noticias_painel.contar(tema)
    except Exception as e:
        yield {"trecho": f"Não consegui puxar as notícias agora, chefe: {str(e)[:80]}"}
        yield {"fim": True}
        return
    if not painel_:
        yield {"trecho": intro}
        yield {"fim": True}
        return
    canal = "hud" if sessao.get("onde") == "aqui" or not extensao.aberta() else "extensao"
    extensao.publicar_tela({"noticias": painel_}, canal)
    # na tela principal, a foto da notícia da vez (as duas telas trabalham juntas)
    cartoes = [None] + ([{"id": "nf-" + painel_["id"], "onde": "aqui", "titulo": i["fonte"], "destaque": i["titulo"],
                          "imagens": [i["imagem"]] if i.get("imagem") else [], "rapido": False, "substitui": True}
                         for i in painel_["itens"]] if canal == "extensao" else [None] * len(frases))
    yield {"leitura": {"id": painel_["id"], "frases": [intro, *frases], "indices": [-1, *range(len(frases))], "cartoes": cartoes}}
    yield {"trecho": " Quer que eu abra alguma? É só dizer: abre a notícia 2."}
    yield {"fim": True}


async def abrir_noticia(sessao, n=None, no_navegador=False):
    """A página da matéria DENTRO do Jarvis (se o site deixar) ou o modo leitura com as fotos; e ele conta."""
    item = noticias_painel.da_vez(n)
    if not item:
        yield {"trecho": "Não tenho notícia aberta agora, chefe. Quer que eu puxe as de hoje?"}
        yield {"fim": True}
        return
    if no_navegador:
        abrir_site(item["url"])
        yield {"trecho": "Abrindo no navegador, chefe."}
        yield {"fim": True}
        return
    yield {"trecho": f"Abrindo a matéria do {item['fonte']}. ", "falar_ja": True}
    if not extensao.aberta():
        await asyncio.to_thread(extensao.abrir, CONFIG["porta"])
    pode_embutir, leitura = await asyncio.gather(asyncio.to_thread(noticias_painel.embutivel, item["url"]),
                                                 asyncio.to_thread(pesquisa_painel.leitura, item["url"]))
    if pode_embutir:
        extensao.publicar_tela({"pagina": {"id": "pg" + uuid.uuid4().hex[:6], "url": item["url"], "titulo": item["titulo"],
                                           "fonte": item["fonte"]}})
    else:
        extensao.publicar_tela({"leitura_pagina": {**leitura, "imagem": item.get("imagem")}})
    texto = " ".join(p for p in leitura.get("paragrafos", []) if not p.startswith("## "))[:4000]
    resumo = ""
    if texto:
        try:
            resumo = await cerebro.completar([{"role": "user", "content": (
                "Conte essa notícia pro Rafael em voz alta, em 3 a 5 frases curtas, tom de conversa, só com o que está "
                f"no texto (é do {item['fonte']}):\n\n{texto}")}], temperatura=0.3, max_tokens=350)
        except Exception:
            resumo = ""
    yield {"trecho": resumo or item.get("fala") or item["titulo"]}
    yield {"fim": True}


async def falar_dos_avioes(sessao, tipo, onde=""):
    """"Que avião é esse?" (o mais perto de você / do que está selecionado) ou "especifica os aviões" (os 5 mais perto)."""
    yield {"trecho": falas.escolher(["Deixa eu identificar, chefe.", "Puxando os dados do transponder.", "Um instante, consultando o radar."]) + " ",
           "falar_ja": True}
    centro = None
    if onde:
        area = await asyncio.to_thread(area_falada, onde)
        if area:
            centro = (area["lat"], area["lng"])
    if not centro and selecao_do_globo.get("lat") is not None and time.time() - selecao_do_globo.get("quando", 0) < 1800:
        centro = (selecao_do_globo["lat"], selecao_do_globo["lng"])
    centro = centro or (lugares.CASA["lat"], lugares.CASA["lng"])
    lista = olho._ultimos["lista"]
    if not lista or onde:
        lista = await asyncio.to_thread(olho.avioes, *centro)
    if not lista:
        yield {"trecho": "Não tem avião no radar por aqui agora, chefe."}
        yield {"fim": True}
        return
    import math
    perto = sorted(lista, key=lambda a: (a["lat"] - centro[0]) ** 2 + ((a["lng"] - centro[1]) * math.cos(math.radians(centro[0]))) ** 2)
    escolhidos = perto[:1] if tipo == "aviao_info" else perto[:5]
    detalhes = await asyncio.gather(*[asyncio.to_thread(olho.detalhes_aviao, a["id"], a["voo"], "", a["modelo"]) for a in escolhidos])
    if not extensao.aberta():
        await asyncio.to_thread(extensao.abrir, CONFIG["porta"])
    if tipo == "aviao_info":
        a, d = escolhidos[0], detalhes[0]
        extensao.publicar({"aviao": {**a, **d, "frase": olho.frase_do_aviao(a, d)}})
        yield {"trecho": olho.frase_do_aviao(a, d)}
    else:
        extensao.publicar_cartao({"titulo": "Aviões perto", "destaque": f"{len(lista)} no radar",
                                  "imagens": [d["foto"] for d in detalhes if d.get("foto")][:4],
                                  "linhas": [olho.frase_do_aviao(a, d).removeprefix("É o ") for a, d in zip(escolhidos, detalhes)],
                                  "rapido": False}, "outra")
        resumo = "; ".join(f"{a['voo'] or 'sem número'}{(' da ' + d['companhia']) if d.get('companhia') else ''}"
                           f"{(' pra ' + d['destino']) if d.get('destino') else ''}" for a, d in zip(escolhidos[:3], detalhes[:3]))
        yield {"trecho": f"Tem {len(lista)} no radar. Os mais perto: {resumo}. Os detalhes tão na tela."}
    yield {"fim": True}


radar_vigia = {"tarefa": None}
holo_atual = {}  # o holograma aberto agora: id, tipo (pra atualizar os dados ao vivo)


def _novo_id():
    return f"holo{int(time.time() * 1000)}"


async def apresentar(assunto):
    """"Me mostra as camadas da Terra" / "as peças de um computador" / "o sistema solar em 3D"."""
    id_ = _novo_id()
    holo_atual.clear()
    extensao.publicar_tela({"apresentacao": {"id": id_, "titulo": assunto, "carregando": True}})
    yield {"trecho": falas.escolher(["Montando o holograma, chefe.", "Projetando aí.", "Deixa eu montar isso em 3D."]) + " ", "falar_ja": True}
    try:
        cena = await apresentacoes.montar(assunto)
    except Exception as e:
        extensao.publicar_tela({"fechar_holo": True})
        yield {"trecho": f"Não consegui montar esse holograma agora: {str(e)[:100]}"}
        yield {"fim": True}
        return
    cena["id"] = id_
    extensao.publicar_tela({"apresentacao": cena})
    frases = [cena.get("intro") or cena["titulo"] + "."] + [p["fala"] for p in cena["passos"]]
    yield {"leitura": {"id": id_, "frases": frases, "indices": [-1, *range(len(cena["passos"]))]}}
    yield {"fim": True}


async def atualizar_holo(id_, tipo):
    """Enquanto o holograma do hardware estiver aberto, os números do lado mudam ao vivo."""
    while holo_atual.get("id") == id_:
        await asyncio.sleep(2)
        if holo_atual.get("id") != id_:
            return
        if time.time() - holo_atual.get("pausa_dados", 0) < 15:
            continue  # ele pediu temperatura/velocidade: deixa esse painel um tempo na tela
        try:
            d = await asyncio.to_thread(hardware.DADOS[tipo])
        except Exception:
            continue
        extensao.publicar_tela({"holo_dados": {"id": id_, "dados": d}})


async def holo_hardware(tipo):
    id_ = _novo_id()
    holo_atual.clear()
    holo_atual.update(id=id_, tipo=tipo)
    extensao.publicar_tela({"apresentacao": {"id": id_, "titulo": {"ram": "Memória RAM", "cpu": "Processador", "gpu": "Vídeo",
                                                                    "disco": "Armazenamento", "tudo": "Este PC"}[tipo], "carregando": True}})
    cena, fala = await asyncio.to_thread(hardware.CENAS[tipo])
    cena["id"] = id_
    extensao.publicar_tela({"apresentacao": cena})
    if tipo in hardware.DADOS:
        tarefas_de_fundo.add(asyncio.create_task(atualizar_holo(id_, tipo)))
    if len(cena.get("passos") or []) > 1:
        yield {"leitura": {"id": id_, "frases": [fala, *[p["fala"] for p in cena["passos"]]], "indices": [-1, *range(len(cena["passos"]))]}}
    else:
        yield {"leitura": {"id": id_, "frases": [fala], "indices": [0]}}
    yield {"fim": True}


async def info_hardware(qual):
    """"E a temperatura?" / "a velocidade" com uma peça na tela: o dado aparece do lado do holograma aberto."""
    tipo = holo_atual.get("tipo") or "tudo"
    if qual == "temperatura":
        t = await asyncio.to_thread(hardware.temperaturas)
        if not t:
            yield {"trecho": "O Windows não me deixa ler temperatura sozinho, chefe. Com o LibreHardwareMonitor aberto (é grátis), "
                             "com o servidor web dele ligado, eu leio processador, placa e disco e mostro aqui ao vivo."}
            yield {"fim": True}
            return
        linhas = t
        fala = "Temperaturas: " + ", ".join(f"{n} {v}" for n, v in t[:4]) + "."
    else:
        linhas = await asyncio.to_thread(hardware.velocidades, tipo)
        fala = "Velocidades: " + ", ".join(f"{n} {v}" for n, v in linhas[:4]) + "."
    if holo_atual.get("id"):
        extensao.publicar_tela({"holo_dados": {"id": holo_atual["id"], "dados": {"titulo": qual.upper(), "linhas": linhas}}})
        holo_atual["pausa_dados"] = time.time()  # não sobrescreve por uns segundos
    yield {"trecho": fala}
    yield {"fim": True}


def mostrar_holograma(assunto: str):
    """Ferramenta do cérebro: qualquer coisa que dê pra ver em 3D (peça do PC com dados ao vivo, ou um assunto)."""
    t = interpretador._sem_acento(assunto.lower()) if hasattr(interpretador, "_sem_acento") else assunto.lower()
    tipo = ("tudo" if re.search(r"hardware|pecas do meu|meu pc|meu computador|configurac|spec", t) else
            "ram" if re.search(r"\bram\b|memoria ram|pente", t) else "cpu" if re.search(r"processador|cpu", t) else
            "gpu" if re.search(r"placa de video|gpu|video", t) else "disco" if re.search(r"disco|ssd|\bhd\b|armazenamento", t) else None)
    id_ = _novo_id()
    holo_atual.clear()
    if tipo:
        cena, fala = hardware.CENAS[tipo]()
        holo_atual.update(id=id_, tipo=tipo)
        if tipo in hardware.DADOS and LACO.get("loop"):
            asyncio.run_coroutine_threadsafe(atualizar_holo(id_, tipo), LACO["loop"])
    else:
        cena = asyncio.run(apresentacoes.montar(assunto))
        fala = cena.get("intro") or ""
    cena.update(id=id_, auto=True)  # sem a voz sincronizada: a tela vai passando as partes sozinha
    extensao.publicar_tela({"apresentacao": cena})
    return ("Holograma na tela. Roteiro (fale isto, curto): " + " ".join([fala, *[p["fala"] for p in cena.get("passos", [])]]))[:1500]


LACO = {}


@app.on_event("startup")
async def guardar_laco():
    LACO["loop"] = asyncio.get_running_loop()


def _rede_neural(novo=None, achados=None):
    """A memória do Jarvis em grupos: o que ele sabe do chefe, habilidades, frases aprendidas, conhecimento, caminhos."""
    fatos = [l[2:] for l in (ARQUIVO_MEMORIA.read_text(encoding="utf-8").splitlines() if ARQUIVO_MEMORIA.exists() else []) if l.startswith("- ")]
    habil = aprendizado.listar() if hasattr(aprendizado, "listar") else []
    habil = [h.get("nome", str(h)) if isinstance(h, dict) else str(h) for h in (habil.values() if isinstance(habil, dict) else habil)]
    frases = [f"{k} → {v}" for k, v in interpretador._aprendidas().items()]
    docs = [a.stem for a in (RAIZ / "conhecimento").glob("*.md") if a.stem != "memoria"]
    grupos = [("Sobre você", fatos), ("Habilidades", habil), ("Frases aprendidas", frases), ("Conhecimento", docs)]
    try:
        ens, cam = aprendizado.resumo()
        grupos.append(("Caminhos aprendidos", [f"caminho {i + 1}" for i in range(min(cam, 40))]))
    except Exception:
        pass
    achados = [a.lower() for a in (achados or [])]
    rede = {"grupos": [{"nome": n, "itens": [{"texto": t, "novo": t == novo or t.lower() in achados} for t in itens[-60:]]}
                       for n, itens in grupos if itens]}
    linhas = [(n, str(len(i))) for n, i in grupos]
    return rede, linhas, fatos + habil + frases + docs


async def nucleo_neural(tipo, valor):
    novo, achados, fala = None, None, ""
    if tipo == "neural_adicionar":
        lembrar(valor)
        novo = next((l[2:] for l in reversed(ARQUIVO_MEMORIA.read_text(encoding="utf-8").splitlines()) if l.startswith("- ")), None)
        fala = falas.escolher(["Gravado no núcleo, chefe.", "Novo neurônio no ar.", "Aprendido e guardado."]) + f" {valor}."
    elif tipo == "neural_buscar":
        _, _, tudo = _rede_neural()
        for doc in (RAIZ / "conhecimento").glob("*.md"):  # e o que está escrito nos arquivos de conhecimento
            tudo += [l.strip("-# ").strip() for l in doc.read_text(encoding="utf-8", errors="replace").splitlines() if len(l.strip()) > 12]
        palavras = [w for w in re.findall(r"\w{3,}", valor.lower()) if w not in ("que", "sobre", "dos", "das", "com", "pra", "para")]
        achados = list(dict.fromkeys(t for t in tudo if any(w in t.lower() for w in palavras)))[:8]
        fala = (f"Achei {len(achados)} coisa{'s' if len(achados) != 1 else ''} sobre {valor}: " + "; ".join(achados[:3]) + "."
                if achados else f"Não tenho nada sobre {valor} no núcleo ainda. Quer que eu grave alguma coisa?")
    rede, linhas, _ = _rede_neural(novo, achados)
    total = sum(int(x) for _, x in linhas)
    if not fala:
        fala = (f"Núcleo neural aberto: {total} memórias. " + ", ".join(f"{v} em {n.lower()}" for n, v in linhas if v != "0") +
                ". Pode pedir pra eu acessar, procurar ou gravar coisa nova.")
    id_ = holo_atual.get("id") if holo_atual.get("tipo") == "neural" else _novo_id()
    holo_atual.clear()
    holo_atual.update(id=id_, tipo="neural")
    painel = {"titulo": "NÚCLEO NEURAL", "linhas": [("Memórias", str(total)), *linhas]}
    if achados:
        painel = {"titulo": f"ACESSO · {valor.upper()}", "linhas": [(str(i + 1), a[:60]) for i, a in enumerate(achados)]}
    extensao.publicar_tela({"apresentacao": {"id": id_, "titulo": "Núcleo neural", "subtitulo": f"{total} MEMÓRIAS · {len(rede['grupos'])} LOBOS",
                                             "rede": rede, "dados": painel, "intro": fala}})
    yield {"leitura": {"id": id_, "frases": [fala], "indices": [-1]}}
    yield {"fim": True}


async def extrair_pedido_de_leads(frase, ja=None):
    """O cérebro entende o pedido do jeito que ele falar: quantidade, nicho e cidade (o que não disse fica null)."""
    ja = dict(ja or {})
    pedido = ("Extraia de uma frase do Rafael pedindo leads (empresas pra prospectar no Google Maps): "
              '{"quantidade": número ou null, "nicho": "tipo de negócio no singular" ou null, "cidade": "cidade/bairro" ou null}. '
              'Ex.: "busque 10 barbearias" → {"quantidade": 10, "nicho": "barbearia", "cidade": null}; '
              '"quero uns 20 leads de dentista em Canoas" → {"quantidade": 20, "nicho": "dentista", "cidade": "Canoas"}; '
              '"garimpa pizzarias em Porto Alegre e Gravataí" → {"quantidade": null, "nicho": "pizzaria", "cidade": "Porto Alegre, Gravataí"}; '
              '"condomínios no Moinhos de Vento" → {"quantidade": null, "nicho": "condomínio", "cidade": "Moinhos de Vento, Porto Alegre"}.'
              + (f" Já se sabe: {json.dumps(ja, ensure_ascii=False)} — a frase é a resposta pro que faltava." if ja else "")
              + f'\nFrase: "{frase}"\nResponda só o JSON.')
    try:
        bruto = await cerebro.completar([{"role": "user", "content": pedido}], json_mode=True, temperatura=0, max_tokens=120)
        novo = json.loads(bruto[bruto.index("{"):bruto.rindex("}") + 1])
    except Exception:
        novo = {}
    for k in ("quantidade", "nicho", "cidade"):
        if novo.get(k) not in (None, "", 0):
            ja[k] = novo[k]
    return ja


async def pedido_de_leads(sessao, frase, ja=None):
    """"Busca 10 leads de barbearia" → se faltar algo pergunta; com tudo, liga o Radar."""
    dados = await extrair_pedido_de_leads(frase, ja)
    if not dados.get("nicho"):
        sessao["dialogo"] = {"tipo": "radar", "dados": dados}
        yield {"trecho": "Leads de quê, chefe? Me diz o nicho (barbearia, dentista, condomínio…)."}
        yield {"fim": True}
        return
    if not dados.get("cidade"):
        sessao["dialogo"] = {"tipo": "radar", "dados": dados}
        yield {"trecho": f"{dados['nicho'].capitalize()} em que cidade, chefe?"}
        yield {"fim": True}
        return
    sessao["dialogo"] = None
    meta = int(dados.get("quantidade") or 50)
    async for e in usar_radar("radar_buscar", (dados["nicho"], dados["cidade"], meta)):
        yield e


async def vigiar_radar():
    """Enquanto a varredura roda: atualiza o painel a cada 3 s, põe cada lead no globo e vai contando em voz alta
    (primeiro lead, metade da meta, terminou)."""
    ultimo_status = None
    falados = set()
    pinos = {}
    for _ in range(1200):  # no máximo 1 h
        try:
            e = await asyncio.to_thread(radar_ext.estado)
        except Exception as erro:
            print("radar:", erro)
            await asyncio.sleep(5)
            continue
        extensao.publicar_tela({"radar": {"id": "radar", **e}})
        novos = [l for l in e["leads"] if l.get("lat") is not None and l.get("id") not in pinos]
        for l in novos:
            pinos[l["id"]] = {"nome": l["nome"], "lat": l["lat"], "lng": l["lng"], "endereco": l.get("cidade") or "", "id": l["id"]}
        if novos:
            extensao.publicar({"pois": {"termo": "leads", "area": {"nome": "Radar"}, "itens": list(pinos.values()), "mais": len(pinos) > len(novos)}})
        meta = e.get("meta") or 0
        achados = e.get("encontrados") or 0
        if achados >= 1 and "primeiro" not in falados and e["leads"]:
            falados.add("primeiro")
            avisar(f"Primeiro lead: {e['leads'][0]['nome']}.", None, "marcado")
        if meta and achados >= meta / 2 and "metade" not in falados and achados < meta:
            falados.add("metade")
            avisar(f"Metade da meta, chefe: {achados} de {meta}.", None, "marcado")
        if e["status"] != "rodando":
            if ultimo_status == "rodando":
                avisar(f"Chefe, o Radar terminou: {e['encontrados']} leads novos, {e['total']} na lista. "
                       "Abre o Radar no painel pra importar e disparar.", None, "marcado")
            return
        ultimo_status = e["status"]
        await asyncio.sleep(3)


async def usar_radar(tipo, valor):
    situ = await asyncio.to_thread(radar_ext.situacao)
    if situ == "sem_extensao":
        yield {"trecho": "Não achei a extensão do Radar neste PC, chefe (a pasta 7code-radar-leads)."}
        yield {"fim": True}
        return
    if situ == "sem_depuracao":
        yield {"trecho": "Preciso reabrir minhas janelas pra ligar a ponte com o Radar. Fala \"reinicia o Jarvis\" e tenta de novo."}
        yield {"fim": True}
        return
    if situ == "nao_instalada":
        yield {"trecho": await asyncio.to_thread(radar_ext.guiar_instalacao)}
        yield {"fim": True}
        return
    if tipo == "radar_parar":
        await asyncio.to_thread(radar_ext.parar)
        yield {"trecho": "Parei a varredura do Radar, chefe. O que já achou ficou guardado."}
        yield {"fim": True}
        return
    if tipo == "radar_estado":
        e = await asyncio.to_thread(radar_ext.estado)
        extensao.publicar_tela({"radar": {"id": "radar", **e}})
        if e["status"] == "rodando":
            yield {"trecho": f"Tá rodando: {e['busca']}, {e['encontrados']} leads novos até agora. Tá na tela."}
        else:
            yield {"trecho": f"Sem varredura rodando. Tem {e['total']} leads guardados na extensão."}
        yield {"fim": True}
        return
    o_que, onde, meta = (*valor, 50)[:3]
    yield {"trecho": f"Ligando o Radar: {meta} leads de {o_que} em {onde}. ", "falar_ja": True}
    extensao.publicar_tela({"radar": {"id": "radar", "status": "rodando", "mensagem": "Abrindo o Google Maps…", "encontrados": 0,
                                      "meta": meta, "busca": f"{o_que} em {onde}", "leads": []}})
    try:
        r, config = await asyncio.to_thread(radar_ext.iniciar, o_que, onde, meta)
    except Exception as erro:
        yield {"trecho": f"O Radar não respondeu: {str(erro)[:120]}"}
        yield {"fim": True}
        return
    if not r.get("ok"):
        yield {"trecho": f"O Radar recusou: {r.get('erro', 'sem motivo')}"}
        yield {"fim": True}
        return
    if radar_vigia["tarefa"] is None or radar_vigia["tarefa"].done():
        radar_vigia["tarefa"] = asyncio.create_task(vigiar_radar())
    painel_ok = await asyncio.to_thread(radar_ext.abrir_painel)
    nichos = ", ".join(n["rotulo"] for n in config["nichos"])
    extra = (" O painel do Radar tá aberto: cada lead já vai direto pra lá." if painel_ok
             else " Abri o painel do Radar, mas ele pediu login: entra uma vez nele que os leads vão sozinhos.")
    yield {"trecho": f"Varredura começou: {nichos} em {', '.join(config['locais'])}, meta de {config['meta']} leads.{extra} "
                     "Vou te contando."}
    yield {"fim": True}


async def pedido_interno(sid, sessao, tipo, valor):
    """Globo, mapa, painéis e Olho de Deus: tudo dentro dele, na hora."""
    if tipo in ("abrir_globo", "olho", "camada", "lugar") and not extensao.aberta():
        await asyncio.to_thread(extensao.abrir, CONFIG["porta"])
    if tipo == "abrir_globo":
        extensao.publicar({"selecionar": None})
        extensao.publicar({"mostrar_globo": True})  # no palco (um monitor só) o globo aparece no centro
        return responder_ja(falas.escolher(["Globo na tela, chefe.", "Aqui o nosso planeta, chefe.", "Globo no ar.",
                                            "Mundo inteiro à sua disposição, chefe."]))
    if tipo == "lugar":
        achado = await asyncio.to_thread(lugares.resolver, "onde fica " + valor)
        if not achado and re.search(r"\d", valor):
            end = lugares.endereco("acha " + valor)
            lugar_ = await asyncio.to_thread(lugares.achar_endereco, end) if end else None
            if isinstance(lugar_, dict) and "lat" in lugar_:
                return mostrar_no_globo(sessao, lugar_)
        if achado:
            tipo_, coisa = achado
            if tipo_ == "lugar":
                return mostrar_no_globo(sessao, coisa)
            if tipo_ == "perguntar":
                return perguntar_qual_lugar(sessao, coisa)
            if tipo_ == "perto":
                SESSAO_ATUAL["sid"] = sid
                return mostrar_perto(coisa)
        return oferecer_google(sessao, valor)
    if tipo == "globo_normal":
        globo_ocupado["ate"] = 0.0
        street_aberto.clear()
        extensao.publicar({"globo_normal": True})
        return responder_ja(falas.escolher(["Globo de volta ao normal, chefe.", "Pronto, zoom tirado e o planeta girando de novo.",
                                            "Voltei o globo pro normal."]))
    if tipo == "atualizacao":
        r = await asyncio.to_thread(instalacao.verificar_atualizacao)
        if not r["ok"] or not r.get("novas"):
            return responder_ja(r["texto"].replace("O Jarvis já está", "Já tô") if r["ok"] else r["texto"])
        lista = "; ".join(r["novidades"][:3])
        if valor == "verificar":
            return responder_ja(f"Tem {r['novas']} atualização{'ões' if r['novas'] > 1 else ''}, chefe: {lista}. Quer que eu atualize?")
        sessao["pendente"] = {"atualizacao": True, "nome": "atualizar o Jarvis", "args": {"novidades": lista},
                              "fala": f"Tem {r['novas']} novidade{'s' if r['novas'] > 1 else ''}: {lista}. Atualizo agora? Eu reinicio sozinho."}
        return pedir_confirmacao(sessao["pendente"])
    if tipo in ("aviao_info", "avioes_lista"):
        return falar_dos_avioes(sessao, tipo, valor)
    if tipo == "apresentacao":
        return apresentar(valor)
    if tipo == "hardware":
        return holo_hardware(valor)
    if tipo == "holo_biblioteca":
        item = hologramas3d.achar(valor)
        if item:
            mostrar_da_biblioteca(item)
            return responder_ja(falas.escolher([f"Aqui, chefe: {item['nome']}.", f"Projetando {item['nome']}.", "Na tela, chefe."]))
    if tipo == "hardware_info":
        return info_hardware(valor)
    if tipo in ("neural", "neural_adicionar", "neural_buscar"):
        return nucleo_neural(tipo, valor)
    if tipo == "fechar_holo":
        holo_atual.clear()
        for canal in ("extensao", "hud", "palco"):
            extensao.publicar({"fechar_holo": True}, canal)
        return responder_ja(falas.escolher(["Fechado, chefe.", "Holograma desligado.", "Pronto, sumiu."]))
    if tipo == "radar_pedido":
        return pedido_de_leads(sessao, valor)
    if tipo in ("radar_buscar", "radar_estado", "radar_parar"):
        return usar_radar(tipo, valor)
    if tipo == "modo_globo":
        extensao.publicar({"modo_globo": valor})
        return responder_ja({"satelite": "Terra de verdade no globo, chefe, sem nuvens, dá pra chegar até a rua. Gira e dá zoom com o mouse.",
                             "nuvens": "Nuvens de verdade no globo: a foto de ontem da NASA. Pra tirar, é só dizer: tira as nuvens.",
                             "holograma": "Voltei pro holograma, chefe."}[valor])
    if tipo == "noticias":
        return contar_noticias(sessao, valor)
    if tipo == "abrir_noticia":
        return abrir_noticia(sessao, *valor)
    if tipo == "mover":
        return responder_ja(await asyncio.to_thread(extensao.mover, valor, CONFIG["porta"]) or "Não tenho nada na tela pra passar, chefe.")
    if tipo == "fechar_mostrado":
        return responder_ja(extensao.fechar_mostrado())
    if tipo == "pois":
        termo, onde = valor
        return mostrar_pois(sessao, termo, onde)
    if tipo == "filtro":
        return mostrar_pois(sessao, pois.ultima["termo"], valor, filtrando=True)
    if tipo == "olho":
        ligar = valor == "ligar"
        extensao.publicar({"olho": {"ligado": ligar, "camadas": list(olho.CAMADAS) if ligar else []}})
        extensao.publicar({"modo_globo": "satelite" if ligar else "holograma"})  # Olho de Deus = Terra real
        if ligar:
            marcar_globo()
        return responder_ja(falas.escolher([
            "Olho de Deus ativado, chefe. Aviões, satélites, terremotos e clima ao vivo.",
            "Ativando o Olho de Deus. Nada escapa agora, chefe.",
            "Olho de Deus online. Tô vendo tudo: céu, órbita e chão."]) if ligar else
            falas.escolher(["Olho de Deus desligado.", "Fechei o Olho de Deus, chefe.", "Camadas desligadas."]))
    if tipo == "camada":
        camada, ligar, onde, somar = (*valor, "", False)[:4]
        area = None
        if onde and ligar:  # "aviões sobrevoando o Brasil": a câmera vai pra lá e a busca cobre a região
            area = await asyncio.to_thread(area_falada, onde)
            if not area:
                return responder_ja(f"Não achei onde fica {onde}, chefe.")
        # pediu UMA coisa ("me mostra os satélites"): mostra só ela; "também"/"e os" soma às que já estão
        extensao.publicar({"olho_camada": {"camada": camada, "ligado": ligar, "area": area, "exclusivo": ligar and not somar}})
        nome = olho.CAMADAS[camada]
        if area:
            marcar_globo()
            extra = " Vão aparecendo conforme o radar varre a região." if camada == "avioes" else ""
            return responder_ja(f"Mostrando os {nome} sobre {area['nome']}, chefe.{extra}")
        if not ligar:
            return responder_ja(f"Tirei os {nome} do globo." if camada != "clima" else "Tirei o clima do globo.")
        extra = {"avioes": " Voando ao vivo, perto de você.", "satelites": " A ISS tá marcada.",
                 "terremotos": " Últimas 24 horas."}.get(camada, "")
        return responder_ja(f"Mostrando {('o ' if camada == 'clima' else 'os ') + nome} no globo, chefe.{extra}")
    if tipo == "mais_fotos":
        fala = await pesquisa_painel.mais_fotos()
        return responder_ja(fala or "Não tenho pesquisa aberta pra buscar mais fotos, chefe. Me diz o assunto.")
    if tipo == "aprofundar":
        termo = (pesquisa_painel._ultimo or {}).get("termo") or contexto.foco_atual(sessao)
        if not termo:
            return responder_ja("Aprofundar o quê, chefe? Me diz o assunto.")
        return pesquisar_no_painel(sessao, termo, foco="mais detalhes, aprofundado, explicação completa", usar_cache=False)
    if tipo == "fonte":
        n, no_navegador = valor
        fonte = pesquisa_painel.fonte_do_ultimo(n)
        if not fonte:
            return responder_ja("Não tenho essa fonte na tela, chefe.")
        if no_navegador:
            abrir_site(fonte["url"])
            return responder_ja("Abrindo no navegador, chefe.")
        leitura = await asyncio.to_thread(pesquisa_painel.leitura, fonte["url"])
        extensao.publicar_tela({"leitura_pagina": leitura})
        return responder_ja(f"Abri a fonte {n} em modo leitura, chefe: {leitura['titulo'][:80]}.")
    if tipo == "ampliar":
        extensao.publicar_tela({"ampliar": {"n": valor}})
        return responder_ja("Ampliando.")
    if tipo == "fechar_painel":
        extensao.publicar_tela({"fechar_painel": valor})
        extensao.publicar({"fechar_painel": valor}, "hud")
        return responder_ja("Fechado.")
    if tipo == "fixar":
        extensao.publicar_tela({"fixar": True})
        return responder_ja("Painel fixado, chefe. Ele fica até você mandar fechar.")
    if tipo == "desfazer":
        return responder_ja(await asyncio.to_thread(registro.desfazer_ultimo))
    return responder_ja("Não entendi o que fazer na tela, chefe.")


selecao_do_globo = {}  # o que ele clicou no globo: {tipo, nome, lat, lng, caixa, quando}
ESSE_LUGAR = re.compile(r"\b(?:ness[ea]|dess[ea]|est[ea]|ess[ea]|nest[ea]|dest[ea]|nesse\s+lugar|desse\s+lugar|no\s+selecionado|"
                        r"o\s+selecionado|a\s+sele[cç][aã]o)\s*(?P<tipo>pa[ií]s|estado|cidade|lugar|regi[aã]o|bairro|munic[ií]pio|local)?\b", re.I)


def com_a_selecao(texto):
    """"Me fala mais sobre esse país" com o Brasil clicado no globo → "me fala mais sobre o Brasil"."""
    sel = selecao_do_globo
    if not sel or time.time() - sel.get("quando", 0) > 1800:
        return texto
    m = ESSE_LUGAR.search(texto)
    if not m or not (m.group("tipo") or re.search(r"\b(?:lugar|sele[cç])", m.group(0), re.I)):
        return texto
    prep = m.group(0).split()[0].lower()
    troca = {"nesse": "em", "nessa": "em", "neste": "em", "nesta": "em", "desse": "de", "dessa": "de", "deste": "de",
             "desta": "de"}.get(prep, "")
    return (texto[:m.start()] + (troca + " " if troca else "") + sel["nome"] + texto[m.end():]).strip()


_VERBOS_COMANDO = (r"(?:liga|desliga|ativa|desativa|abre|fecha|minimiza|maximiza|mostra|me mostra|pesquisa|procura|"
                   r"toca|pausa|continua|manda|envia|aumenta|abaixa|bloqueia|passa|tira|traz|pergunta|pede|marca|"
                   r"agenda|sugere|coloca|p[oõ]e|bota|gira|amplia|diminui|roda|grava|encerra|anota|fala)")
_SEP_FORTE = re.compile(r"\s*(?:;|,?\s*(?:e\s+)?depois\b|,?\s*ent[aã]o\b|,?\s*e\s+a[ií]\b)\s*", re.I)
_SEP_VERBO = re.compile(r"\s*(?:,|\be)\s+(?=" + _VERBOS_COMANDO + r"\b)", re.I)


def separar_comandos(texto):
    """Quebra uma fala com vários pedidos em tarefas, em ordem. Só separa em 'depois/então/;' ou quando
    depois de 'e'/vírgula vem um VERBO de comando — assim 'mostra o preço e a ficha' NÃO é quebrado."""
    t = re.sub(r"^\s*jarvis[ ,]*", "", texto.strip(), flags=re.I)
    t = _SEP_FORTE.sub(" | ", t)
    t = _SEP_VERBO.sub(" | ", t)
    partes = [p.strip(" ,.") for p in t.split("|")]
    partes = [p for p in partes if p]
    return partes if len(partes) > 1 else [texto]


def _varios(sid, sessao, partes):
    """Roda cada tarefa em ordem, encadeando os streams; segura 'fim'/'dormir' até a última."""
    async def fluxo():
        for i, parte in enumerate(partes):
            ultimo = i == len(partes) - 1
            resp = await rotear(sid, sessao, parte, interpretar=True)   # cada parte é 1 comando (não re-quebra)
            async for linha in resp.body_iterator:
                s = linha if isinstance(linha, str) else linha.decode()
                for ln in s.splitlines():
                    try:
                        e = json.loads(ln)
                    except ValueError:
                        continue
                    if (e.get("fim") or e.get("dormir")) and not ultimo:
                        continue   # não finaliza entre uma tarefa e outra
                    yield json.dumps(e, ensure_ascii=False) + "\n"
    return StreamingResponse(fluxo(), media_type="application/x-ndjson")


async def rotear(sid, sessao, texto, interpretar=True):
    """Decide o caminho do pedido já entendido; o primeiro evento mostra na tela o que foi entendido."""
    if interpretar:
        partes = separar_comandos(texto)
        if len(partes) > 1:
            return _varios(sid, sessao, partes)   # vários pedidos numa fala: um de cada vez, em ordem
    # "me mostra fotos" logo depois de "pesquisa BMW X1" = fotos da BMW X1
    texto = contexto.resolver(texto, contexto.foco_atual(sessao)) or texto
    texto = com_a_selecao(texto)  # "esse país" = o que ele clicou no globo
    resposta = await _rotear(sid, sessao, texto, interpretar)
    original = resposta.body_iterator

    async def com_entendido():
        primeiro = True
        falado, usadas = "", []
        try:
            async for linha in original:
                yield linha
                if primeiro:
                    primeiro = False
                    yield json.dumps({"entendido": texto}, ensure_ascii=False) + "\n"
                for parte in (linha if isinstance(linha, str) else linha.decode()).splitlines():
                    try:
                        e = json.loads(parte)
                    except ValueError:
                        continue
                    falado += e.get("trecho", "")
                    if e.get("ferramenta"):
                        usadas.append(e["ferramenta"])
        finally:
            # diário: "faz aquilo de ontem" e o log das Configurações leem daqui
            try:
                registro.anotar(texto, re.sub(r"\s+", " ", falado).strip(), usadas)
            except Exception as erro:
                print("registro falhou:", erro)
    return StreamingResponse(com_entendido(), media_type="application/x-ndjson")


async def _rotear(sid, sessao, texto, interpretar=True):
    p = Pergunta(sessao=sid, texto=texto)
    _to = p.texto.strip()
    if re.search(r"\b(?:fecha\w*|sai\w*|encerra\w*)\s+(?:a\s+|da\s+)?(?:oficina|bancada)\b", _to, re.I):
        extensao.publicar({"oficina_fechar": True}, "hud")   # bancada de montagem por gestos (web/oficina.js)
        return em_linhas(sid, responder_ja("Fechando a oficina, chefe."))
    _of = re.search(r"\bmont(?:a|ar)\s+(?:um\s+|meu\s+)?(?P<q>pc|computador|carro|quebra[- ]?cabe\w+)\b|\babr\w*\s+a\s+oficina\b|\bbancada\s+d[eo]\s+(?P<q2>pc|carro)\b|\boficina\s+holog\w+\b|\babr\w*\s+a\s+bancada\b|\bquebra[- ]?cabe\w+\b", _to, re.I)
    if _of:
        _q = ((_of.group("q") or _of.group("q2") or "").lower())
        _g = ""   # ao entrar na oficina, liga os gestos se ainda não estiverem (ele monta com a mão)
        try:
            if not gestos._estado["ligado"]:
                gestos.iniciar(); _g = " Liguei a câmera pros gestos."
        except Exception:
            pass
        if "quebra" in _q or re.search(r"\bquebra[- ]?cabe", _to, re.I):
            extensao.publicar({"oficina": "quebra"}, "hud"); _fala = "Quebra-cabeça do JARVIS na mesa, chefe. Pince as peças e encaixe." + _g
        elif "carro" in _q:
            extensao.publicar({"oficina": "carro"}, "hud"); _fala = "Bancada do carro, chefe. Monte e depois dê a partida." + _g
        elif _q:
            extensao.publicar({"oficina": "pc"}, "hud"); _fala = "Bancada do PC, chefe. Pince as peças e encaixe." + _g
        else:
            extensao.publicar({"oficina": "escolher"}, "hud"); _fala = "Oficina aberta. Vamos montar o quê, chefe: PC, carro ou quebra-cabeça?" + _g
        return em_linhas(sid, responder_ja(_fala))
    para_o_claude = claude_ponte.entender(p.texto)
    if para_o_claude:
        # sempre confirma: a transcrição pode ter vindo errada
        acao = "perguntar ao Claude" if para_o_claude["modo"] == "perguntar" else "pedir ao Claude"
        sessao["pendente"] = {"claude": para_o_claude, "nome": f"{acao} no {para_o_claude['nome']}",
                              "args": {"pedido": para_o_claude["pedido"]},
                              "fala": f"Vou {acao}, no {para_o_claude['nome']}: {para_o_claude['pedido']}. Confirma?"}
        return em_linhas(sid, pedir_confirmacao(sessao["pendente"]))
    if proatividade.CRIAR_SUGERIDA.match(p.texto.strip()):
        return em_linhas(sid, responder_ja(await asyncio.to_thread(proatividade.criar_sugerida)))
    perturbe = NAO_PERTURBE.match(p.texto.strip())
    if perturbe:
        ligar = not perturbe.group("desliga")
        mudar_config({"proatividade": {**proatividade.config(), "nao_perturbe": ligar}})
        return em_linhas(sid, responder_ja("Não perturbe ligado, chefe. Avisos só na tela, sem voz." if ligar
                                           else "Não perturbe desligado. Volto a te avisar falando."))
    interno = internos.no_contexto_hw(p.texto, holo_atual.get("tipo")) or internos.entender(p.texto)  # contexto do holograma primeiro
    if interno and interno[0] in ("mover", "fechar_mostrado") and not extensao.tem_mostrado(300 if interno[0] == "fechar_mostrado" else 1800):
        interno = None  # nada na tela: "pode fechar" volta a ser despedida, "passa pra outra tela" abre a extensão
    if interno and interno[0] == "filtro" and not (pois.ultima and time.time() - pois.ultima.get("quando", 0) < 600):
        interno = None
    if interno:  # globo, mapa, painéis, Olho de Deus: é dentro dele, na hora (nunca "app chamado globo")
        return em_linhas(sid, await pedido_interno(sid, sessao, *interno))
    mic = pedido_de_microfone(p.texto)
    if mic:
        return em_linhas(sid, mexer_no_microfone(mic))
    for recurso in RECURSOS:  # lembretes, pomodoro, anotações, notícias, sistemas/PC
        pedido_ = recurso.entender(p.texto)
        if pedido_:
            tarefa = asyncio.to_thread(recurso.executar, pedido_)
            if recurso.DEMORA:  # notícias, Vercel, PC: fala já e trabalha enquanto isso
                return em_linhas(sid, comentando(["Deixa eu ver, chefe.", "Um instante.", "Já vejo isso."], tarefa))
            return em_linhas(sid, responder_ja(*await tarefa))
    clima = CLIMA_EM.search(p.texto) if web.TEMPO.search(p.texto) else None
    if web.TEMPO.search(p.texto) and not re.search(r"\b(?:quanto tempo|tempo falta|faz tempo|ao mesmo tempo)\b", p.texto, re.I):
        return em_linhas(sid, comentando(["Deixa eu ver o céu, chefe.", "Um instante."],
                                         asyncio.to_thread(tempo_no_globo, clima.group("cidade") if clima else None)))
    if spotify.QUE_MUSICA.search(p.texto):
        return em_linhas(sid, responder_ja(await asyncio.to_thread(spotify.que_musica)))
    if SAIR_CAVERNA.search(p.texto):
        return em_linhas(sid, caverna(False))
    if ENTRAR_CAVERNA.search(p.texto):
        return em_linhas(sid, caverna(True, sessao))
    if spotify.ESSA_NAO.match(p.texto.strip()):
        return em_linhas(sid, responder_ja(spotify.esquecer_ultima()))
    tecla = spotify.tecla_de_midia(p.texto)
    if tecla:
        sessao["assunto"] = "música"
        spotify.apertar(tecla[0])
        return em_linhas(sid, responder_ja(tecla[1]))
    musica = spotify.pedido(p.texto)
    if musica:
        sessao["assunto"] = "música"
        return em_linhas(sid, comentando(COMENTARIOS_DE_MUSICA, asyncio.to_thread(spotify.tocar, musica)))
    # música tocando (lido em segundo plano) vale só pras frases curtas de controle ("outra", "mais alto");
    # não vira o assunto da conversa toda, senão o cérebro só fala de música
    if sessao.get("assunto") == "música" or musica_tocando["agora"] or \
            re.match(r"^(?:toca|bota|coloca|p[oõ]e)\s+outra\b", p.texto, re.I):
        seguinte = spotify.continuacao(p.texto)
        if seguinte:
            tipo, valor = seguinte
            if tipo == "tecla":
                spotify.apertar(valor[0])
                return em_linhas(sid, responder_ja(valor[1]))
            return em_linhas(sid, comentando(COMENTARIOS_DE_MUSICA, asyncio.to_thread(spotify.tocar, valor)))
    fala_de_saida = sistema.despedida(p.texto)
    if fala_de_saida:
        return em_linhas(sid, dormir(fala_de_saida))
    trancar = BLOQUEAR.search(p.texto)
    if trancar:
        esquecer_rosto()
        if trancar.group("alvo").lower() == "jarvis":
            return em_linhas(sid, dormir("Trancado, chefe. Na próxima vez, só com o seu rosto."))
    comando = sistema.entender(p.texto)
    if comando:
        perigoso, acao, fala = comando
        if perigoso and confirmar():
            sessao["pendente"] = {"acao": acao, "fala": fala, "nome": "mexer no computador", "args": {"pedido": p.texto}}
            return em_linhas(sid, pedir_confirmacao(sessao["pendente"]))
        await asyncio.to_thread(acao)
        return em_linhas(sid, responder_ja(fala))
    if ABRIR_INTERFACE.fullmatch(p.texto.strip(" .!?")):
        return em_linhas(sid, responder_ja(await asyncio.to_thread(abrir_interface)))
    if olhos_e_maos.VER_TELA.search(p.texto):
        return em_linhas(sid, comentando(["Deixa eu ver.", "Olhando, chefe."], asyncio.to_thread(
            olhos_e_maos.ver_tela, p.texto, olhos_e_maos.qual_tela(p.texto))))
    if RESUMO_DO_DIA.search(p.texto):
        return em_linhas(sid, falar_resumo_do_dia())
    if PERGUNTA_HABILIDADES.search(p.texto):  # abre o popup com tudo que ele sabe fazer
        # se ele pediu pra LER/FALAR (não só mostrar), lê a lista inteira em voz alta
        ler = re.search(r"\b(?:l[eê]|leia|me\s+(?:l[eê]|fala|diz)|fala|diz|conta)\b", p.texto, re.I)
        return em_linhas(sid, responder_ja(habilidades.falar_tudo() if ler else habilidades.fala(), [habilidades.cartao()]))
    rapida = resposta_rapida(p.texto)
    if rapida:
        return em_linhas(sid, responder_ja(rapida))
    if PERGUNTA_COMMIT.search(p.texto):
        resposta = await asyncio.to_thread(ultimo_commit)
        if resposta:
            return em_linhas(sid, responder_ja(*resposta))
    if PERGUNTA_ANDAMENTO.search(p.texto) and re.search(r"porthon|pacote|projeto|paramos|parei|pend", p.texto, re.I):
        return em_linhas(sid, responder_ja(*andamento_porthon()))
    busca = porthon_busca.entender(p.texto)
    if busca:  # só quando ele falou do Porthon, de morador ou de placa
        return em_linhas(sid, comentando(["Deixa eu olhar no Pórton.", "Um instante, chefe."],
                                         asyncio.to_thread(porthon_busca.responder, busca)))
    if lugares.LIMPAR.match(p.texto.strip()):
        extensao.publicar({"selecionar": None})
        return em_linhas(sid, responder_ja("Limpei o globo, chefe."))
    selecao = await asyncio.to_thread(lugares.selecionar, p.texto)
    if selecao:
        if not extensao.aberta():
            await asyncio.to_thread(extensao.abrir, CONFIG["porta"])
        marcar_globo()
        extensao.publicar({"selecionar": selecao})
        return em_linhas(sid, responder_ja(f"Selecionado: {selecao['nome']}, chefe."))
    no_mapa = await asyncio.to_thread(lugares.resolver, p.texto)
    if no_mapa:
        tipo, coisa = no_mapa
        if tipo == "lugar":
            return em_linhas(sid, mostrar_no_globo(sessao, coisa))
        if tipo == "perguntar":
            return em_linhas(sid, perguntar_qual_lugar(sessao, coisa))
        if tipo == "perto":
            SESSAO_ATUAL["sid"] = sid
            return em_linhas(sid, mostrar_perto(coisa))
        if tipo == "busca":
            return em_linhas(sid, oferecer_google(sessao, coisa))
    pedido_web = web.entender(p.texto)
    if pedido_web and not resposta_da_ficha(p.texto):  # o que as fichas sabem (clientes, equipe) ganha da Wikipédia
        if pedido_web[0] in ("imagem", "saber"):
            contexto.guardar(sessao, pedido_web[1])
        if pedido_web[0] == "saber":  # "me fala sobre X" / "o que é X": painel completo dentro dele, lido em voz alta
            return em_linhas(sid, pesquisar_no_painel(sessao, pedido_web[1]))
        return em_linhas(sid, comentando(["Deixa eu ver, chefe.", "Um instante.", "Já vejo isso."],
                                         asyncio.to_thread(responder_da_internet, pedido_web)))
    procura = pesquisa.entender(p.texto)
    if procura:
        contexto.guardar(sessao, procura["termo"])
        if not procura["nav"] and not procura["site"]:
            # "pesquisa X": o resultado aparece DENTRO do Jarvis; navegador só se ele disser "no Google/no Chrome…"
            return em_linhas(sid, pesquisar_no_painel(sessao, procura["termo"]))
        return em_linhas(sid, responder_ja(pesquisa.executar(procura)))
    rapido = atalho(p.texto)
    if rapido:
        return em_linhas(sid, responder_ja(rapido))
    consulta = consultas.entender(p.texto)
    if consulta and painel.configurado():
        return em_linhas(sid, comentando(COMENTARIOS_DO_PAINEL, asyncio.to_thread(consultas.responder, consulta)))
    if porthon_dados.PERGUNTA.search(p.texto) and not PEDIDO_DE_ABRIR.match(p.texto.strip()):
        if not porthon_dados.configurado():
            return em_linhas(sid, responder_ja("Ainda não tenho o seu login do Porthon, chefe. Preencha o login-porthon.json na minha pasta."))
        return em_linhas(sid, comentando(["Deixa eu olhar o Pórton.", "Um instante, vou conferir."],
                                         asyncio.to_thread(porthon_dados.resumo)))
    if not PEDIDO_DE_ABRIR.match(p.texto.strip()) and any(r.search(p.texto) for r, _, _ in PERGUNTAS_DO_PAINEL):
        return em_linhas(sid, comentando(COMENTARIOS_DO_PAINEL, asyncio.to_thread(dados_do_painel, p.texto)))
    if ESQUECER.match(p.texto.strip()):
        desfeita = desfazer_autocorrecao()  # o mais recente primeiro: a troca de palavra que ele acabou de ver
        if desfeita:
            return em_linhas(sid, responder_ja(desfeita))
        if ultimo_caminho.get("pedido") and time.time() - ultimo_caminho.get("quando", 0) < 300:
            ultimo_caminho.clear()
            aprendizado.esquecer_ultimo_caminho()
            return em_linhas(sid, responder_ja("Entendido, chefe. Apaguei o jeito que eu tinha feito. Me explica como era pra ser."))
        if ultima_interpretacao.get("texto"):
            interpretador.esquecer(ultima_interpretacao.pop("texto"))
            return em_linhas(sid, responder_ja("Entendido, chefe. Esqueci o que eu tinha entendido. Me diz de novo do seu jeito."))
        return em_linhas(sid, responder_ja(esquecer_a_ultima()))
    ficha = resposta_da_ficha(p.texto)
    if ficha:
        return em_linhas(sid, responder_ja(*ficha))
    papo = re.match(r"^(?:jarvis[ ,]*)?(?:e a[ií]|oi|ol[aá]|opa|bom dia|boa tarde|boa noite|tudo (?:bem|certo|tranquilo|bom|joia)|"
                    r"beleza|como (?:vai|voc[eê] est[aá]|tu t[aá])|bah|tri)\b", p.texto.strip(), re.I)
    # Com o cérebro da nuvem, a frase vai DIRETO pra ele (que entende pela intenção e chama comando_jarvis
    # quando é uma habilidade pronta): uma ida ao modelo em vez de duas. O tradutor (interpretador) fica
    # pro cérebro local, que sozinho erra mais.
    if interpretar and not papo and not cerebro.nuvem():  # cumprimento e papo não são pedido: não gasta tempo interpretando
        comando, confianca = await interpretador.interpretar(p.texto)
        if not interpretador.plausivel(p.texto, comando):
            comando = "conversa"  # ex.: letra de música ouvida pelo microfone virando "toca …"
        if comando.lower() != "conversa" and not rota_de(comando).startswith("modelo"):
            ultima_interpretacao["texto"] = p.texto
            if confianca >= 0.75:
                interpretador.aprender(p.texto, comando)  # da próxima vez, direto
                return await rotear(sid, sessao, comando, interpretar=False)
            sessao["pendente"] = {"correcao": [], "interpretacao": True, "original": p.texto, "corrigido": comando,
                                  "nome": "confirmar o que você pediu", "args": {"entendi": comando},
                                  "fala": f"Você quer que eu faça isto: {comando}?"}
            return em_linhas(sid, pedir_confirmacao(sessao["pendente"]))
    ja_sei = None if cerebro.nuvem() else resposta_aprendida(p.texto)  # cérebro rápido: improvisa, não repete decorado
    if ja_sei:
        ultima_aprendida["chave"] = chave_da_pergunta(p.texto)
        return em_linhas(sid, responder_ja(ja_sei))
    if not sessao["mensagens"]:
        sessao["mensagens"], sessao["resumo"] = memoria_conversa.comeco_da_sessao(prompt_do_sistema())
    # passou do limite: a parte velha vira resumo (em segundo plano), em vez de simplesmente sumir
    msgs = memoria_conversa.cortar(sessao)
    # assunto: o desta frase, ou o da conversa ("e qual o nome dela?" depois de falar de música)
    assunto = assunto_de(p.texto) or sessao.get("assunto")
    sessao["assunto"] = assunto
    sessao["pedido"] = p.texto
    # ferramentas deste pedido: a base + os grupos que a frase pede + os que ele carregou no pedido anterior
    sessao["grupos"] = grupos_para(p.texto, {"grupos": sessao.pop("carregados", None) or ()})
    sessao["mensagens"] = [*msgs, {"role": "user", "content": mensagem_do_usuario(p.texto, assunto) + aprendizado.dica_do_caminho(p.texto)}]
    return em_linhas(sid, aprendendo(p.texto, pensar(sessao)))


async def dormir(fala):
    yield {"trecho": fala}
    yield {"dormir": True}  # a tela fala a despedida e depois chama /api/dormir
    yield {"fim": True}


async def pedir_confirmacao(pendente):
    yield {"pendente": {"nome": pendente["nome"], "args": pendente["args"], "fala": pendente.get("fala")}}


@app.get("/api/novidades")
def novidades():
    """Respostas do Claude que chegaram enquanto o Rafael fazia outra coisa.

    Varredura de segurança que ACHOU falhas vem com uma 'oferta': armo o pendente (claude, modo FAZER) na sessão
    aberta e deixo o HUD mostrar o sim/não. No "sim", /api/decidir roda claude_ponte.executar e abre o Claude pra
    corrigir (aprovando cada passo). Só a pasta local, nunca produção."""
    blocos = claude_ponte.novidades() + seguranca.novidades() + novidades_de_leads[:]
    novidades_de_leads.clear()
    sid = SESSAO_ATUAL.get("sid")
    sessao = sessoes.get(sid) if sid else None
    for b in blocos:
        oferta = b.pop("oferta", None)  # nunca vaza a oferta crua pro HUD
        if not oferta:
            continue
        # só arma se tem uma sessão aberta e nada mais esperando "sim" (um pedido de cada vez)
        if sessao is not None and not sessao.get("pendente"):
            sessao["pendente"] = oferta
            b["pendente"] = {"nome": oferta["nome"], "args": oferta["args"], "fala": oferta["fala"]}
    return {"blocos": blocos}


class Aviso(BaseModel):
    texto: str
    importancia: str = "marcado"  # "marcado" fala mesmo em proatividade média (ele PEDIU o aviso)


@app.post("/api/aviso")
def api_aviso(a: Aviso):
    """Fala um aviso curto que veio de fora (ex.: o Claude Code terminou uma tarefa). Respeita o Não perturbe."""
    fala = (a.texto or "").strip()[:300]
    if not fala:
        return {"ok": False}
    avisar(fala, importancia=a.importancia)
    return {"ok": True}


class Holo(BaseModel):
    assunto: str


@app.post("/api/holograma/mostrar")
async def api_holograma(h: Holo):
    """A janelinha de anatomia clicou um sistema (esqueleto, músculos...): monta e mostra o holograma na tela."""
    assunto = (h.assunto or "").strip()[:60]
    if not assunto:
        return {"ok": False}
    try:
        cena = await apresentacoes.montar(assunto)
    except Exception as e:
        return {"ok": False, "erro": str(e)[:100]}
    cena["id"] = _novo_id()
    holo_atual.clear()
    extensao.publicar_tela({"apresentacao": cena})
    return {"ok": True, "titulo": cena.get("titulo")}


# ------------------------------------------------------------- Scanner 3D + biblioteca de hologramas (Configurações)
def mostrar_da_biblioteca(item):
    holo_atual.clear()
    extensao.publicar_tela({"apresentacao": {**hologramas3d.cena(item), "id": _novo_id()}})


def _scanner_terminou(item):
    avisar(f"Holograma {item['nome']} pronto, chefe. Tá na biblioteca.")
    mostrar_da_biblioteca(item)


hologramas3d.ao_terminar = _scanner_terminou


class Scanner(BaseModel):
    foto_base64: str
    nome: str = ""
    estilo: str = "real"


class EditarHolo(BaseModel):
    nome: str | None = None
    estilo: str | None = None


class TokenHF(BaseModel):
    token: str = ""


@app.get("/api/hologramas")
def api_hologramas():
    return hologramas3d.listar()


@app.post("/api/hologramas/scanner")
def api_scanner(s: Scanner):
    import base64
    try:
        foto = base64.b64decode(s.foto_base64.split(",")[-1], validate=False)
        if len(foto) > 15 * 1024 * 1024:
            raise ValueError("foto grande demais (máx. 15 MB)")
        return {"trabalho": hologramas3d.iniciar(foto, s.nome, s.estilo)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/hologramas/scanner/{tid}")
def api_scanner_estado(tid: str):
    e = hologramas3d.estado(tid)
    if not e:
        raise HTTPException(404, "trabalho não existe (o Jarvis reiniciou?)")
    return e


@app.post("/api/hologramas/token")
def api_hologramas_token(t: TokenHF):
    try:
        hologramas3d.guardar_token(t.token)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.get("/api/hologramas/arquivo/{nome}")
def api_holograma_arquivo(nome: str):
    if not re.fullmatch(r"[a-z0-9-]+\.(?:glb|png)", nome):
        raise HTTPException(404)
    caminho = hologramas3d.PASTA / nome
    if not caminho.is_file():
        raise HTTPException(404)
    return FileResponse(caminho, media_type="model/gltf-binary" if nome.endswith(".glb") else "image/png")


@app.post("/api/hologramas/{id_}/mostrar")
async def api_holograma_biblioteca(id_: str):
    pronto = next((p for p in hologramas3d.PRONTOS if p["id"] == id_), None)
    if pronto:
        if pronto["tipo"] == "hardware":
            cena, _ = await asyncio.to_thread(hardware.CENAS[pronto["alvo"]])
        elif pronto["tipo"] == "celular":
            cena, _ = await asyncio.to_thread(celular.cena)
        else:
            cena = await apresentacoes.montar(pronto["alvo"])
        cena.update(id=_novo_id(), auto=True)
        holo_atual.clear()
        if pronto["tipo"] == "hardware":
            holo_atual.update(id=cena["id"], tipo=pronto["alvo"])
            if pronto["alvo"] in hardware.DADOS:
                tarefas_de_fundo.add(asyncio.create_task(atualizar_holo(cena["id"], pronto["alvo"])))
        extensao.publicar_tela({"apresentacao": cena})
        return {"ok": True}
    item = hologramas3d.achar(id_)
    if not item:
        raise HTTPException(404, "não achei esse holograma")
    mostrar_da_biblioteca(item)
    return {"ok": True}


@app.post("/api/hologramas/{id_}")
def api_holograma_editar(id_: str, e: EditarHolo):
    try:
        return hologramas3d.editar(id_, e.nome, e.estilo)
    except KeyError:
        raise HTTPException(404, "não achei esse holograma")


@app.delete("/api/hologramas/{id_}")
def api_holograma_apagar(id_: str):
    hologramas3d.apagar(id_)
    return {"ok": True}


class Microfone(BaseModel):
    mudo: bool


# ------------------------------------------------------------- automações (botão ⚙ da tela)

async def perguntar_qual_lugar(sessao, achado):
    """Mais de um com esse nome: marca todos no globo e pergunta qual."""
    marcar_globo()
    if not extensao.aberta():
        await asyncio.to_thread(extensao.abrir, CONFIG["porta"])
    opcoes = achado["opcoes"][:6]
    extensao.publicar({"globo_opcoes": [{"lat": o["lat"], "lng": o["lng"],
                                         "nome": o.get("bairro") or o.get("cidade") or o["nome"]} for o in opcoes]})
    sessao["dialogo"] = {"tipo": "lugar", "nome": achado["nome"], "opcoes": opcoes}
    if achado["tipo"] == "varios_perto":
        onde = ", ".join(dict.fromkeys(f"no {o['bairro']}" for o in opcoes if o.get("bairro")).keys()) or "aqui na volta"
        fala = f"Achei {len(opcoes)} {achado['nome']} por aqui, chefe: {onde}. Qual deles? Ou quer o mais perto?"
    else:
        cidades = ", ".join(dict.fromkeys(o.get("cidade") or o["completo"] for o in opcoes).keys())
        fala = f"Tem {achado['nome']} em mais de um lugar, chefe: {cidades}. De qual cidade?"
        if achado.get("endereco"):
            fala = f"Tem essa rua em mais de uma cidade aqui na região, chefe: {cidades}. Qual delas?"
    yield {"trecho": fala}
    yield {"fim": True}


async def oferecer_google(sessao, termo, perto=False):
    """Lugar que o mapa do Jarvis não resolve: o navegador só abre se ele disser "sim"."""
    sessao = sessao if sessao is not None else sessoes.get(SESSAO_ATUAL.get("sid")) or {}
    sessao["pendente"] = {"maps": lugares.maps_busca(termo, perto=perto), "nome": "procurar no Google Maps",
                          "args": {"busca": termo + (" perto de você" if perto else "")},
                          "fala": (f"Quer que eu abra {termo} perto de você no Google Maps?" if perto
                                   else f"Não achei {termo} no meu mapa, chefe. Quer que eu procure no Google Maps?")}
    yield {"pendente": {k: sessao["pendente"][k] for k in ("nome", "args", "fala")}}


async def mostrar_perto(termo):
    """"restaurantes japoneses aqui perto": o globo aponta a cidade dele e o Google Maps procura."""
    marcar_globo()
    if not extensao.aberta():
        await asyncio.to_thread(extensao.abrir, CONFIG["porta"])
    casa = lugares.casa()
    extensao.publicar({"globo": {**casa, "id": extensao.com_id({"titulo": "Por perto", "destaque": termo})["id"],
                                 "texto": f"Procurando {termo} perto de você no Google Maps."}})
    yield {"trecho": f"Tô te mostrando aqui na sua região, chefe. "}
    async for e in oferecer_google(None, termo, perto=True):
        yield e


async def mostrar_no_globo(sessao, lugar):
    """O globo da extensão gira até o lugar, abre a foto em cima e o Jarvis oferece o Google Maps."""
    marcar_globo()
    if not extensao.aberta():
        await asyncio.to_thread(extensao.abrir, CONFIG["porta"])
    yield {"trecho": f"Localizando {lugar['nome']}. ", "falar_ja": True}
    if lugar.get("tipo") == "endereco":
        foto = {"imagem": lugares.satelite(lugar), "satelite": True,
                "texto": lugar["completo"] + ("" if lugar.get("numero_exato") else " · número aproximado (o mapa só tem a rua)")}
    else:
        foto = await asyncio.to_thread(lugares.foto, lugar) or {}
    cid = extensao.com_id({"titulo": "Localizado", "destaque": lugar["completo"], "assunto": lugar["nome"]})["id"]
    texto = foto.get("texto") or (lugar["completo"] + (f" · {lugar['bairro']}" if lugar.get("bairro") else ""))
    extensao.publicar({"globo": {**lugar, "id": cid, "foto": foto.get("imagem"), "texto": texto, "maps": True,
                                 "satelite": foto.get("satelite", False)}})
    contexto.guardar(sessao, lugar["nome"])  # "me mostra fotos" / "e o tempo lá?" depois falam desse lugar
    ultimo_lugar.update(lugar)
    if lugar.get("tipo") == "endereco":
        sessao["pendente"] = {"maps": lugares.street_view(lugar), "streetview": lugar, "nome": "abrir a visão da rua (Street View)",
                              "args": {"endereço": lugar["completo"]},
                              "fala": f"Achei, chefe: {lugar['nome']}, {lugar.get('bairro') or lugar.get('cidade') or ''}. "
                                      "Essa é a vista de cima. Quer ver na rua, pelo Street View?"}
    else:
        sessao["pendente"] = {"maps": lugares.maps(lugar), "nome": "abrir no Google Maps", "args": {"lugar": lugar["completo"]},
                              "fala": f"Aqui, chefe: {lugar['completo']}. Quer ver no Google Maps?"}
    yield {"pendente": {"nome": sessao["pendente"]["nome"], "args": sessao["pendente"]["args"], "fala": sessao["pendente"]["fala"]}}


async def rodar_automacao(sid, sessao, rotina):
    """Executa as ações da rotina em ordem, como se ele tivesse falado cada uma."""
    yield {"trecho": f"Rodando {rotina['nome']}, chefe. ", "falar_ja": True}
    for acao in rotina["acoes"]:
        async for e in habilidade(sid, sessao, acao):
            if "pendente" in e:  # ação perigosa no meio da rotina: pergunta e para aqui
                yield e
                return
            if "trecho" in e or "cartao" in e or "modo" in e:
                yield {k: v for k, v in e.items() if k != "falar_ja"}
        yield {"trecho": " "}
    yield {"fim": True}


async def automacao_sozinha(rotina):
    """Rotina de horário ou de quando o PC liga: roda sem ninguém pedir; o que ela diria vira aviso da tela."""
    sid = "automacao"
    sessao = sessoes.setdefault(sid, {"mensagens": [], "pendente": None})
    fala = ""
    async for e in rodar_automacao(sid, sessao, rotina):
        fala += e.get("trecho", "")
    sessao["pendente"] = None  # ninguém para dizer "sim": o que era perigoso não roda
    novidades_de_leads.append({"fala": re.sub(r"\s+", " ", fala).strip(), "cartao": {
        "titulo": "Automação", "destaque": rotina["nome"], "linhas": rotina["acoes"][:5]}})


async def relogio_das_automacoes():
    """A cada 20 s confere se alguma rotina de horário bate com o minuto; a de ligar o PC roda uma vez por ligada."""
    feitas = set()
    await asyncio.sleep(25)  # dá tempo do Windows terminar de abrir
    ligada = ligada_do_pc()
    marca = RAIZ / "automacoes-ligada.json"
    try:
        ja_rodou = json.loads(marca.read_text(encoding="utf-8")).get("ligada") == ligada
    except (OSError, ValueError):
        ja_rodou = False
    if not ja_rodou:
        marca.write_text(json.dumps({"ligada": ligada}), encoding="utf-8")
        for rotina in automacoes.ao_ligar():
            await automacao_sozinha(rotina)
    while True:
        agora = datetime.now()
        for fala in falas_programadas.do_minuto(agora):  # fala sozinho no horário (tela fechada: o segundo plano fala)
            chave = ("fala", fala["id"], f"{agora:%Y-%m-%d %H:%M}")
            if chave not in feitas:
                feitas.add(chave)
                texto = falas_programadas.preencher(fala["texto"], agora)
                novidades_de_leads.append({"fala": texto, "cartao": extensao.com_id(
                    {"titulo": "Fala programada", "destaque": fala["hora"], "texto": texto})})
                registro.anotar("fala programada", texto, tipo="aviso")
        for rotina in automacoes.do_minuto(agora):
            chave = (rotina["id"], f"{agora:%Y-%m-%d %H:%M}")
            if chave not in feitas:
                feitas.add(chave)
                try:
                    await automacao_sozinha(rotina)
                except Exception as e:
                    print("automação falhou:", rotina["nome"], e)
        await asyncio.sleep(20)


@app.on_event("startup")
async def ligar_relogio_das_automacoes():
    tarefas_de_fundo.add(asyncio.create_task(relogio_das_automacoes()))


class Login7(BaseModel):
    email: str
    senha: str


@app.get("/api/7planner")
def api_7planner():
    return planner7.quem()


@app.post("/api/7planner")
async def api_7planner_entrar(l: Login7):
    """Ele digita o login do 7planner aqui; vira um token no cofre e a senha é descartada."""
    try:
        return await asyncio.to_thread(planner7.entrar, l.email, l.senha)
    except PermissionError as e:
        raise HTTPException(401, str(e))
    except Exception as e:
        raise HTTPException(502, f"Não consegui falar com o 7planner: {str(e)[:120]}")


@app.get("/api/timers")
def timers_na_tela(origem: str = "pc"):
    """A contagem que aparece na tela (web/timers.js), só a deste aparelho."""
    return timer.situacao("celular" if origem == "celular" else "pc")


@app.delete("/api/timers/{id_}")
def cancelar_timer(id_: str):
    return {"ok": timer.cancelar_por_id(id_)}


@app.delete("/api/7planner")
def api_7planner_sair():
    planner7.sair()
    return {"ok": True}


@app.get("/api/falas-programadas")
def listar_falas_programadas():
    return {"falas": falas_programadas.todas()}


@app.post("/api/falas-programadas")
def salvar_fala_programada(f: dict):
    try:
        return falas_programadas.salvar(f)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.delete("/api/falas-programadas/{id_}")
def apagar_fala_programada(id_: str):
    falas_programadas.apagar(id_)
    return {"ok": True}


@app.post("/api/falas-programadas/testar")
def testar_fala_programada(f: dict):
    """Botão "ouvir agora" da tela: fala a frase já (do jeito que vai sair no horário)."""
    novidades_de_leads.append({"fala": falas_programadas.preencher(str(f.get("texto") or "")), "cartao": None})
    return {"ok": True}


@app.get("/api/marketing/plano")
def ver_plano_marketing():
    return {"plano": marketing.plano_atual()}


@app.post("/api/marketing/plano")
def salvar_plano_marketing(d: dict):
    """Configurações → Marketing: ele edita o plano à mão (dia, horário, tema…) e os lembretes acompanham."""
    return {"plano": marketing.salvar_plano(d.get("plano") or [])}


@app.delete("/api/marketing/plano")
def apagar_plano_marketing():
    return {"lembretes_apagados": marketing.apagar_plano()}


@app.get("/api/automacoes")
def listar_automacoes():
    return {"automacoes": automacoes.todas()}


@app.post("/api/automacoes")
def salvar_automacao(a: dict):
    try:
        return automacoes.salvar(a)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.delete("/api/automacoes/{id_}")
def apagar_automacao(id_: str):
    automacoes.apagar(id_)
    return {"ok": True}


@app.post("/api/automacoes/{id_}/rodar")
async def testar_automacao(id_: str, sessao: str | None = None):
    rotina = next((a for a in automacoes.todas() if a["id"] == id_), None)
    if not rotina:
        raise HTTPException(404, "Automação não encontrada.")
    sid = sessao if sessao in sessoes else str(uuid.uuid4())
    s_ = sessoes.setdefault(sid, {"mensagens": [], "pendente": None})
    return em_linhas(sid, rodar_automacao(sid, s_, rotina))


class Fundo(BaseModel):
    texto: str


SIM_FALADO = re.compile(r"^(sim|pode|pode sim|pode ser|autoriz\w*|confirm\w*|manda(?: ver)?|pode ir|vai|claro|isso(?: a[íi])?|"
                        r"positivo|bora|beleza|blz|ok|okay|okey|tranquil[oa]|fechou|fechado|combinado|de boa|dboa|exato|"
                        r"t[aá] (?:bom|certo|[oó]timo))\b", re.I)
NAO_FALADO = re.compile(r"^(n[aã]o|cancela|negativo|deixa|para|esquece)\b", re.I)


@app.post("/api/fundo")
async def em_segundo_plano(f: Fundo):
    """Pedido falado com a tela fechada ("Jarvis, abre o Spotify"): faz e devolve só o que falar.

    A sessão "fundo" guarda a conversa; se o pedido anterior esperava um "sim", esta fala é a resposta.
    """
    sid = "fundo"
    sessao = sessoes.setdefault(sid, {"mensagens": [], "pendente": None})
    texto = f.texto.strip()
    if sessao["pendente"] and SIM_FALADO.match(texto):
        resposta = await decidir(Decisao(sessao=sid, autorizado=True))
    elif sessao["pendente"] and NAO_FALADO.match(texto):
        resposta = await decidir(Decisao(sessao=sid, autorizado=False))
    else:
        sessao["pendente"] = None  # falou outra coisa: o pedido antigo caiu
        resposta = await conversar(Pergunta(sessao=sid, texto=texto))
    fala, aguardando = "", False
    async for linha in resposta.body_iterator:
        for parte in (linha if isinstance(linha, str) else linha.decode()).splitlines():
            if not parte.strip():
                continue
            e = json.loads(parte)
            fala += e.get("trecho", "")
            if e.get("pendente"):
                aguardando = True
                fala += " " + (e["pendente"].get("fala") or "Confirma, chefe?")
            if e.get("erro"):
                fala += " Tive um problema: " + e["erro"]
            if e.get("dormir"):  # "tchau"/"se desliga" com a tela escondida: fecha a tela e a extensão do mesmo jeito
                threading.Timer(2.5, sistema.fechar_janela).start()
            if e.get("minimizar"):
                threading.Timer(1.5, esconder_janelas_do_jarvis).start()
    aguardando = aguardando or bool(sessao.get("dialogo")) or fala.strip().endswith("?")
    return {"fala": re.sub(r"\s+", " ", fala).strip(), "aguardando": aguardando}


@app.post("/api/microfone")
def api_microfone(m: Microfone):
    """O clique no 7 desmuta também o microfone do Windows (quando foi mutado por "muta o microfone do PC")."""
    microfone.mutar_windows(m.mudo)
    return {"ok": True}


@app.post("/api/dormir")
def ir_dormir():
    sistema.fechar_janela()
    return {"ok": True}


async def aprendendo(pergunta, eventos):
    """Repassa a resposta do modelo e, se ela veio inteira sem usar ferramenta, guarda para a próxima vez."""
    texto, limpo = "", True
    async for e in eventos:
        texto += e.get("trecho", "")
        limpo = limpo and not ({"pendente", "erro", "ferramenta"} & e.keys())
        yield e
    if limpo:
        aprender(pergunta, texto.strip())


@app.post("/api/decidir")
async def decidir(d: Decisao):
    sessao = sessoes.get(d.sessao)
    if not sessao or not sessao["pendente"]:
        raise HTTPException(404, "Nada esperando autorização.")
    pend, sessao["pendente"] = sessao["pendente"], None
    extensao.origem.set("celular" if sessao.get("celular") else "pc")
    if "correcao" in pend:
        # "sim" ensina a correção; "não" ensina a não insistir. Depois segue com o pedido.
        vocabulario.confirmar(pend["correcao"], d.autorizado)
        if pend.get("interpretacao") and d.autorizado:
            interpretador.aprender(pend["original"], pend["corrigido"])
        return await rotear(d.sessao, sessao, pend["corrigido"] if d.autorizado else pend["original"],
                            interpretar=not pend.get("interpretacao"))
    if "reuniao" in pend:
        if not d.autorizado:
            return em_linhas(d.sessao, responder_ja("Tudo bem, chefe. Deixei a agenda como estava."))
        try:
            fala = await asyncio.to_thread(reunioes.marcar, pend["reuniao"])
        except Exception as e:
            fala = f"O painel recusou a reunião, chefe: {str(e)[:120]}"
        return em_linhas(d.sessao, responder_ja(fala))
    if "crm" in pend:
        if not d.autorizado:
            return em_linhas(d.sessao, responder_ja("Cancelado, chefe. O CRM ficou como estava."))
        c = pend["crm"]
        try:
            await asyncio.to_thread(painel.mudar_etapa, c["id"], c["status"], c.get("motivo"))
            fala = f"Pronto, {pend['args']['lead']} agora está como {pend['args']['para']} no CRM."
        except Exception as e:
            fala = f"O CRM recusou a mudança, chefe: {str(e)[:120]}"
        return em_linhas(d.sessao, responder_ja(fala))
    if "whatsapp" in pend:
        conversa = pend["whatsapp"]
        fala = await asyncio.to_thread(whatsapp.enviar, conversa) if d.autorizado else "Cancelado, chefe. Não mandei nada."
        if conversa.get("etapa") == "conferir":
            sessao["dialogo"] = conversa  # a próxima fala dele responde "foi a conversa certa?"
        return em_linhas(d.sessao, responder_ja(fala))
    if "pomodoro" in pend:
        if not d.autorizado:
            return em_linhas(d.sessao, responder_ja("Beleza, sem pomodoro. É só pedir se mudar de ideia."))
        return em_linhas(d.sessao, responder_ja(*pomodoro.executar({"acao": "iniciar", "min": pend["pomodoro"]})))
    if "maps" in pend:
        if not d.autorizado:
            extensao.publicar({"selecionar": None})  # "não" pro Maps: o globo volta ao normal
            return em_linhas(d.sessao, responder_ja("Beleza, chefe."))
        if pend.get("streetview") and extensao.aberta():
            return em_linhas(d.sessao, responder_ja(abrir_street_view(pend["streetview"])))
        navegadores.abrir(pend["maps"], tela="esta")  # a outra tela é da extensão
        return em_linhas(d.sessao, responder_ja("Abrindo no Google Maps, chefe."))
    if "atualizacao" in pend:
        if not d.autorizado:
            return em_linhas(d.sessao, responder_ja("Beleza, fica pra depois."))
        r = await asyncio.to_thread(instalacao.atualizar)
        if not r["ok"]:
            return em_linhas(d.sessao, responder_ja(r["texto"]))
        instalacao.reiniciar(atraso=6)  # dá tempo da frase ser falada
        return em_linhas(d.sessao, responder_ja("Chefe, tudo pronto, subindo atualização!"))
    if "claude" in pend:
        fala = claude_ponte.executar(pend["claude"]) if d.autorizado else "Cancelado, chefe. Não mandei nada."
        return em_linhas(d.sessao, responder_ja(fala))
    if "acao" in pend:  # comando do Windows (desligar, reiniciar…): responde direto, sem modelo
        if d.autorizado:
            await asyncio.to_thread(pend["acao"])
        return em_linhas(d.sessao, responder_ja(pend["fala"] if d.autorizado else "Cancelado, chefe."))
    resultado = rodar_ferramenta(pend["nome"], pend["args"]) if d.autorizado else "O Rafael NÃO autorizou. Não faça."
    sessao["mensagens"].append({"role": "tool", "tool_call_id": pend.get("tool_call_id"), "content": resultado})
    return em_linhas(d.sessao, pensar(sessao), {"saida": resultado} if d.autorizado else None)


PASTA_PORTHON = Path.home() / "Desktop" / "Porthon-System" / "lobby"


def git(*args):
    r = subprocess.run(["git", "-C", str(PASTA_PORTHON), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=15)
    return r.stdout.strip()


DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]


def bloco_porthon():
    """Andamento do desenvolvimento, como o Claude anotou na memória: pacote e pendências."""
    d = fontes.desenvolvimento_porthon()
    if not (d["pacote"] or d["pendencias"]):
        return None
    partes = []
    if d["pacote"]:
        n = len(d["pacote"])
        partes.append(f"No Porthon, o pacote de atualização tem {n} {'item' if n == 1 else 'itens'} esperando o seu "
                      f"lançar atualização: {d['pacote'][0]}" + ("." if n == 1 else f", e mais {n - 1}."))
    if d["sqls"]:
        partes.append(f"{len(d['sqls'])} SQL do pacote ainda sem confirmação de que rodou.")
    if d["pendencias"]:
        partes.append(f"E há {len(d['pendencias'])} pendências anotadas; estão na tela.")
    linhas = [f"Pacote: {p}" for p in d["pacote"]] + [f"SQL: {s}" for s in d["sqls"]]
    linhas += d["pendencias"]
    return {"fala": " ".join(partes), "cartao": {
        "titulo": "Porthon · desenvolvimento",
        "destaque": f"{len(d['pacote'])} no pacote · {len(d['pendencias'])} pendências", "linhas": linhas}}


def ultimo_commit():
    """Só quando ele pergunta: o que foi publicado por último."""
    commits = [l.split("|", 1) for l in git("log", "-3", "--format=%cd|%s", "--date=format:%d/%m").splitlines() if "|" in l]
    if not commits:
        return None
    alterados = len([l for l in git("status", "--porcelain").splitlines() if l.strip()])
    data, assunto = commits[0]
    fala = f"O último commit do Porthon foi em {data}: {assunto.rstrip('.')}."
    if alterados:
        fala += f" Há {alterados} arquivos alterados ainda não commitados."
    return fala, [{"titulo": "Porthon · commits", "destaque": data, "linhas": [f"{d} · {a}" for d, a in commits]}]


def andamento_porthon():
    bloco = bloco_porthon()
    if not bloco:
        return "Não tenho nada pendente anotado do Porthon, chefe.", []
    return bloco["fala"].replace("E há", "Há"), [bloco["cartao"]]


PERGUNTA_COMMIT = re.compile(r"\b(?:[uú]ltim[oa]s?\s+commits?|commit mais recente|[uú]ltima publica[cç][aã]o)\b", re.I)
PERGUNTA_ANDAMENTO = re.compile(
    r"\b(?:o que (?:falta|tem pendente|est[aá] pendente)|pend[eê]ncias?|onde (?:a gente )?(?:paramos|parou)|onde parei|"
    r"andamento|como (?:t[aá]|est[aá]) o (?:porthon|desenvolvimento|pacote)|pacote de atualiza[cç][aã]o)\b", re.I)
def bloco_porthon_numeros():
    if not porthon_dados.configurado():
        return None
    try:
        fala, cartoes = porthon_dados.resumo()
        return {"fala": fala, "cartao": cartoes[0]}
    except Exception as e:
        return {"fala": "", "cartao": {"titulo": "Porthon · agora", "destaque": "Não consegui ler", "aguardando": True,
                                       "linhas": [str(e)[:120]]}}


def blocos_do_painel():
    """Caixa, reuniões e leads da 7 SevenCode, lidos com o login do Rafael (só leitura)."""
    return [painel.tentar(painel.caixa, "Caixa 7 SevenCode"),
            painel.tentar(painel.reunioes_de_hoje, "Reuniões de hoje"),
            painel.tentar(painel.leads, "Radar de Leads")]


async def aquecer(mensagens):
    """Faz o Ollama processar as instruções enquanto o Jarvis fala a abertura (na nuvem não precisa)."""
    if cerebro.nuvem():
        return
    try:
        async with httpx.AsyncClient(timeout=180) as cliente:
            await cliente.post(f"{CONFIG['ollama_url']}/api/chat", json={
                "model": CONFIG["modelo"], "messages": mensagens, "tools": definicoes_para({}), "stream": False,
                "keep_alive": "2h", "options": {"num_ctx": 4096, "num_predict": 1},
            })
    except Exception:
        pass


@app.get("/api/abertura")
async def abertura(curta: bool = False):
    """Primeira abertura depois de ligar o PC: o resumo do dia. Nas outras, só "Pois não?"."""
    sid = str(uuid.uuid4())
    mensagens, resumo = memoria_conversa.comeco_da_sessao(prompt_do_sistema())
    sessoes[sid] = {"mensagens": mensagens, "pendente": None, "resumo": resumo}
    asyncio.create_task(aquecer(sessoes[sid]["mensagens"]))
    marca = RAIZ / "resumo-falado.json"
    try:
        ja_falou = json.loads(marca.read_text(encoding="utf-8")).get("ligada") == ligada_do_pc()
    except (OSError, ValueError):
        ja_falou = False
    if curta or ja_falou:
        # rosto pedido de novo depois de bloquear: confere, mas não repete o resumo do dia
        return {"sessao": sid, "blocos": [{"fala": falas.escolher(falas.CHAMADO), "cartao": None}]}
    marca.write_text(json.dumps({"ligada": ligada_do_pc()}), encoding="utf-8")
    return {"sessao": sid, "blocos": await blocos_do_dia()}


def config_da_abertura():
    """O que entra no resumo do dia DESTE PC (Configurações → Abertura). No colégio: 7planner + avisos; em casa: tudo."""
    a = (json.loads((RAIZ / "config.json").read_text(encoding="utf-8")).get("abertura") or {})  # avisos por voz gravam direto no arquivo
    return {"porthon": a.get("porthon", True), "painel": a.get("painel", True), "planner": a.get("planner", True),
            "estado": a.get("estado", True), "noticias": a.get("noticias", True),
            "avisos": [x for x in a.get("avisos") or [] if isinstance(x, dict) and str(x.get("texto", "")).strip()]}


def bloco_estado():
    """O Jarvis se reconhece: cérebro em uso e conectores ligados (igual o 'todos os sistemas online' do filme)."""
    try:
        cerebro_nome = cerebro.nome_do_cerebro()
    except Exception:
        cerebro_nome = "local"
    try:
        import conectores
        conns = conectores.nomes_ligados()
    except Exception:
        conns = []
    linhas = [f"Cérebro: {cerebro_nome}", f"Conectores: {len(conns)} ligado" + ("s" if len(conns) != 1 else "")
              + (f" ({', '.join(conns)})" if conns else "")]
    fala = (f"Todos os sistemas online, chefe. Estou rodando com o cérebro {cerebro_nome.split(' · ')[0]}"
            + (f", {len(conns)} conector{'es' if len(conns) != 1 else ''} ligado{'s' if len(conns) != 1 else ''}." if conns else "."))
    return {"fala": fala, "cartao": {"titulo": "Estado do J.A.R.V.I.S.", "destaque": "Online", "linhas": linhas}}


def bloco_noticias_tech():
    """As principais notícias de tecnologia e IA do dia, pra ele começar por dentro."""
    try:
        fala, carts = noticias.executar({"tema": "tecnologia e inteligência artificial"})
    except Exception:
        return None
    if not carts:
        return None
    return {"fala": fala, "cartao": carts[0]}


def bloco_7planner():
    if not planner7.conectado():
        return None
    try:
        r = planner7.executar(planner7.entender("agenda do 7planner hoje"))
        planner7.marcar_resumo_de_hoje()  # já falou na abertura: o aviso das 7h não repete
    except Exception as e:
        return {"fala": "", "cartao": {"titulo": "7planner", "destaque": "Não consegui ler", "aguardando": True, "linhas": [str(e)[:140]]}}
    return {"fala": r[0].replace(", chefe.", "."), "cartao": r[1][0] if len(r) > 1 else None}


def bloco_dos_avisos(avisos):
    hoje = datetime.now().weekday()
    do_dia = [x["texto"].strip().rstrip(".") for x in avisos if hoje in (x.get("dias") or range(7)) and x.get("ativo", True)]
    if not do_dia:
        return None
    return {"fala": ("Aviso do dia: " if len(do_dia) == 1 else "Avisos do dia: ") + ". ".join(do_dia) + ".",
            "cartao": {"titulo": "Avisos do dia", "destaque": f"{len(do_dia)} aviso{'s' if len(do_dia) > 1 else ''}", "linhas": do_dia}}


async def blocos_do_dia(fecho="O que vamos fazer hoje?"):
    agora = datetime.now()
    saudacao = "Bom dia" if agora.hour < 12 else "Boa tarde" if agora.hour < 18 else "Boa noite"
    cfg = config_da_abertura()
    noticias_bloco = await asyncio.to_thread(bloco_noticias_tech) if cfg["noticias"] else None
    blocos = [
        {"fala": f"{saudacao}, chefe.", "cartao": None},
        *([bloco_estado()] if cfg["estado"] else []),
        {"fala": f"Hoje é {DIAS[agora.weekday()]}, e são {agora:%H:%M}.", "cartao": {
            "titulo": "Agora", "destaque": f"{agora:%H:%M}", "linhas": [f"{DIAS[agora.weekday()]}, {agora:%d/%m/%Y}"]}},
        *[b for b in (bloco_dos_avisos(cfg["avisos"]),
                      await asyncio.to_thread(bloco_7planner) if cfg["planner"] else None,
                      bloco_porthon() if cfg["porthon"] else None,
                      await asyncio.to_thread(bloco_porthon_numeros) if cfg["porthon"] else None,
                      # painel sem login neste PC (o do colégio): nem aparece, em vez do cartão "falta o login"
                      *(await asyncio.to_thread(blocos_do_painel) if cfg["painel"] and painel.configurado() else [])) if b],
        *([noticias_bloco] if noticias_bloco else []),
        *([{"fala": fecho, "cartao": None}] if fecho else []),
    ]
    return blocos


RESUMO_DO_DIA = re.compile(r"\b(?:dados|resumo|n[uú]meros|novidades|panorama|relat[oó]rio)\s+(?:de hoje|do dia)\b|"
                           r"\bcomo (?:t[aá]|est[aá]) o (?:dia|meu dia)\b|\bme (?:d[aá]|passa|fala) (?:o|um) resumo\b|"
                           r"\bo que (?:tem|temos) (?:pra|para) hoje\b|\bbriefing\b", re.I)


async def falar_resumo_do_dia():
    for b in await blocos_do_dia(fecho=None):
        if b.get("cartao"):
            yield {"cartao": b["cartao"]}
        yield {"trecho": b["fala"] + " "}
    yield {"fim": True}


def arquivo_de_voz(texto, tom=None, ritmo=None):
    tom = tom or CONFIG["voz_tom"]
    ritmo = ritmo or CONFIG["voz_velocidade"]
    filtro = CONFIG.get("voz_filtro") or ""  # filtrada e normal têm cache separado
    chave = f"{CONFIG['voz']}|{tom}|{filtro}|{texto}" + (f"|{ritmo}" if ritmo != "+0%" else "")  # mudou o ritmo: grava de novo
    return PASTA_DE_VOZ / (hashlib.sha1(chave.encode()).hexdigest() + ".mp3")


FRASES_FIXAS = [
    "Verificando identidade.", "Identidade confirmada. Bem-vindo de volta, chefe.",
    "Identidade confirmada. Bem-vindo de volta, senhor.", "Acesso negado. Não reconheço você.",
    "Primeiro acesso. Vou registrar o seu rosto.", "Bom dia. Todos os sistemas online.",
    "Boa tarde. Todos os sistemas online.", "Boa noite. Todos os sistemas online.", "O que vamos fazer hoje?",
    "Confirma, chefe? É só dizer sim ou não.", "Cancelado, chefe.", "Cancelado, chefe. Não mandei nada.",
    "Boa noite, chefe. Descanse. Estarei aqui quando precisar.", "Bom intervalo, chefe. É só me chamar.",
    "Desligando. Até logo, chefe.", "Até mais, chefe. Fico de ouvido aqui.",
    *COMENTARIOS_DE_MUSICA, *COMENTARIOS_DO_PAINEL, *ESPERAS, *RESPOSTAS_DE_NADA, "Deixa eu olhar o Pórton.", "Pois não, chefe?",
    *falas.todas_fixas(),
]


@app.get("/api/frases")
def frases_da_tela():
    """As variações que a tela usa sozinha (esperas, "Pois não?", demorando): o áudio delas já está pronto."""
    return {"esperas": falas.ESPERAS, "chamado": falas.CHAMADO, "demorando": falas.DEMORANDO}


@app.get("/api/espera")
def espera_do_pedido(texto: str = ""):
    """A frase de espera que combina com o que ele falou ("me mostra meu PC" → "Montando as peças do seu PC")."""
    return {"frase": falas.espera_para(sinonimos.normalizar(vocabulario.corrigir(texto)))}


@app.on_event("startup")
async def preparar_frases_fixas():
    """Gera de antemão o áudio das frases que ele sempre fala: a primeira vez também sai na hora."""
    async def gerar():
        PASTA_DE_VOZ.mkdir(exist_ok=True)
        for frase in FRASES_FIXAS:
            frase = pronuncia(frase)  # igual ao /api/voz: o arquivo guardado é o da frase já com a pronúncia certa
            destino = arquivo_de_voz(frase)
            if destino.exists():
                continue
            try:
                audio = b""
                async for parte in edge_tts.Communicate(frase, CONFIG["voz"], rate=CONFIG["voz_velocidade"],
                                                        pitch=CONFIG["voz_tom"]).stream():
                    if parte["type"] == "audio":
                        audio += parte["data"]
                destino.write_bytes(audio)
                if CONFIG.get("voz_filtro") == "ia":  # já deixa as frases fixas com o filtro
                    await asyncio.to_thread(voz_efeito.processar_mp3, destino)
            except Exception:
                continue  # sem internet agora: essa frase sai na hora em que for falada
    # a tarefa precisa ficar guardada: sem referência, o Python pode descartá-la no meio
    tarefas_de_fundo.add(asyncio.create_task(gerar()))


tarefas_de_fundo = set()


def pronuncia(texto):
    """Como as palavras soam: "SevenCode" (nunca "sete SevenCode"), "Pórton", "Ráizen", "trédis"… (tabela em pronuncia.py)."""
    return pronuncia_.falar(texto)


@app.get("/api/voz")
async def voz(texto: str):
    # frase que ele já falou uma vez (saudação, "Abrindo o WhatsApp", resposta aprendida) sai do disco, na hora
    texto = pronuncia(texto.strip()[:1500])
    tom, ritmo = ("-9Hz", "+14%") if modo_atual() == "caverna" else (CONFIG["voz_tom"], CONFIG["voz_velocidade"])
    guardado = arquivo_de_voz(texto, tom, ritmo)
    if guardado.exists():
        return FileResponse(guardado, media_type="audio/mpeg")
    if CONFIG.get("voz_filtro") == "ia":  # filtro "de IA": precisa do áudio inteiro, então gera tudo, filtra e entrega
        PASTA_DE_VOZ.mkdir(exist_ok=True)
        await edge_tts.Communicate(texto, CONFIG["voz"], rate=ritmo, pitch=tom).save(str(guardado))
        await asyncio.to_thread(voz_efeito.processar_mp3, guardado)
        return FileResponse(guardado, media_type="audio/mpeg")
    # senão entrega o áudio aos pedaços: o navegador começa a tocar antes da frase inteira ficar pronta
    falar = edge_tts.Communicate(texto, CONFIG["voz"], rate=ritmo, pitch=tom)

    async def pedacos():
        audio = b""
        async for parte in falar.stream():
            if parte["type"] == "audio":
                audio += parte["data"]
                yield parte["data"]
        if len(texto) <= 300 and not re.search(r"\d", texto):  # números mudam (hora, caixa): não vale guardar
            PASTA_DE_VOZ.mkdir(exist_ok=True)
            guardado.write_bytes(audio)

    return StreamingResponse(pedacos(), media_type="audio/mpeg")


PASTA_DE_VOZ = RAIZ / "voz-guardada"
ARQUIVO_ROSTO = RAIZ / "rosto.json"  # só números do rosto, nenhuma foto; nunca sai do PC


class Rosto(BaseModel):
    descritores: list[list[float]]


ARQUIVO_BOOT = RAIZ / "rosto-confirmado.json"  # em qual ligada do PC o rosto já foi conferido


def ligada_do_pc():
    """Hora em que o Windows ligou (arredondada no minuto): muda a cada boot, igual o dia todo."""
    import ctypes
    no_ar = ctypes.windll.kernel32.GetTickCount64() / 1000
    return int((time.time() - no_ar) // 60)


def rosto_ja_conferido():
    try:
        salvo = json.loads(ARQUIVO_BOOT.read_text(encoding="utf-8"))["ligada"]
    except (OSError, ValueError, KeyError):
        return False
    return abs(salvo - ligada_do_pc()) <= 1


BLOQUEAR = re.compile(r"\b(?:bloque\w*|tranc\w*|trava\w*)\b.*\b(?P<alvo>pc|computador|tela|m[aá]quina|jarvis|tudo)\b", re.I)


def esquecer_rosto():
    """Depois de bloquear, a próxima abertura pede o rosto de novo (o resumo do dia não se repete)."""
    ARQUIVO_BOOT.unlink(missing_ok=True)
    extensao.publicar({"autenticacao": "bloqueado"})  # a extensão trava na hora


@app.get("/api/rosto")
def rosto():
    if not CONFIG.get("usar_rosto", True):
        return {"descritores": [], "ja_conferido": True}  # este PC não usa reconhecimento facial
    if not ARQUIVO_ROSTO.exists():
        return {"descritores": [], "ja_conferido": False}
    # só a primeira abertura depois de ligar o PC pede o rosto; as outras entram direto
    return {**json.loads(ARQUIVO_ROSTO.read_text(encoding="utf-8")), "ja_conferido": rosto_ja_conferido()}


@app.post("/api/rosto/conferido")
def rosto_conferido():
    ARQUIVO_BOOT.write_text(json.dumps({"ligada": ligada_do_pc()}), encoding="utf-8")
    extensao.publicar({"autenticacao": "ok"})  # a extensão destrava e o globo aparece
    return {"ok": True}


class Autenticacao(BaseModel):
    estado: str  # "verificando" | "negado"


@app.post("/api/autenticacao")
def api_autenticacao(a: Autenticacao):
    """O portão do rosto (tela principal) avisa a extensão: enquanto não confirma, ela mostra só "Autenticando"."""
    if a.estado in ("verificando", "negado", "cadastrando"):
        extensao.publicar({"autenticacao": a.estado})
    return {"ok": True}


@app.post("/api/rosto")
def cadastrar_rosto(r: Rosto):
    if ARQUIVO_ROSTO.exists():
        raise HTTPException(409, "Já existe um rosto cadastrado. Apague rosto.json para refazer.")
    ARQUIVO_ROSTO.write_text(json.dumps({"descritores": r.descritores}), encoding="utf-8")
    return {"ok": True}


MINIMIZAR_JARVIS = re.compile(r"^(?:jarvis[ ,]*)?(?:se\s+)?(?:minimiza|minimizar|minimize|esconde|abaixa)"
                              r"(?:\s+(?:o\s+jarvis|a\s+tua\s+tela|tua\s+tela|a\s+sua\s+tela|voc[eê]|tu|a[ií]))?(?:\s+a[ií])?[.!]*$", re.I)
tela_visivel = {"visivel": True}


async def minimizar_jarvis():
    yield {"trecho": "Fico aqui embaixo, chefe. É só me chamar."}
    yield {"minimizar": True}  # a tela fala e depois some
    yield {"fim": True}


def esconder_janelas_do_jarvis():
    for hwnd in telas._janelas_em_ordem():
        if telas._titulo(hwnd).startswith("J.A.R.V.I.S."):
            telas.u.ShowWindow(hwnd, 6)  # SW_MINIMIZE


@app.post("/api/minimizar")
def api_minimizar():
    esconder_janelas_do_jarvis()
    return {"ok": True}


class PedidoExtensao(BaseModel):
    abrir: bool


@app.post("/api/extensao")
def api_extensao(p: PedidoExtensao):
    return {"fala": extensao.abrir(CONFIG["porta"]) if p.abrir else extensao.fechar()}


@app.post("/api/extensao/sinal")
def extensao_sinal():
    extensao.sinal()
    return {"ok": True}


@app.get("/api/extensao/eventos")
async def extensao_eventos(canal: str = "extensao"):
    canal = canal if canal in ("extensao", "hud", "palco", "celular") else "extensao"
    return StreamingResponse(extensao.eventos(canal), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/extensao")
def pagina_da_extensao():
    return FileResponse(RAIZ / "web" / "extensao.html")


@app.on_event("startup")
async def ligar_extensao():
    extensao.guardar_loop(asyncio.get_running_loop())


class Sinal(BaseModel):
    visivel: bool = True
    ouvido: str = "ok"  # ok | mudo (mutado de propósito) | morto (reconhecimento do Chrome parou)


ouvido_da_tela = {"estado": "ok", "ouviu_em": 0.0}
extensao.tela_principal_visivel["f"] = lambda: time.time() - ultimo_sinal_da_tela < 6


@app.post("/api/ouvi")
def tela_ouviu():
    """A tela transcreveu alguma coisa agora (o segundo plano usa pra saber se ela está mesmo escutando)."""
    ouvido_da_tela["ouviu_em"] = time.time()
    return {"ok": True}


@app.post("/api/sinal")
def sinal(s: Sinal | None = None):
    """A tela avisa que está aberta. Minimizada não conta: aí o ouvido de segundo plano atende o "Jarvis"."""
    global ultimo_sinal_da_tela
    vida_das_telas["hud"] = time.time()  # viva, mesmo minimizada
    if s is None or s.visivel:
        ultimo_sinal_da_tela = time.time()
        ouvido_da_tela["estado"] = s.ouvido if s else "ok"
    return {"ok": True}


vida_das_telas = {"hud": 0.0}


async def telas_andam_juntas():
    """Fechou uma das duas janelas na mão: a outra fecha junto. (Fechar a lateral por voz — "volta pra tela
    principal" — não conta: aí ela fecha sozinha de propósito.) Reinício/atualização matam as duas de uma vez."""
    # Olha os PROCESSOS das janelas (cada uma tem o perfil dela), não o sinal da página: o sinal some por uns
    # segundos enquanto o globo carrega e isso já fechou tudo por engano. Só age se sumiu em duas olhadas seguidas.
    import psutil

    def processos(perfil):
        achados = []
        for pr in psutil.process_iter(["name", "cmdline"]):
            try:
                if pr.info["name"] in ("chrome.exe", "msedge.exe") and any(perfil in a for a in pr.info["cmdline"] or []):
                    achados.append(pr)
            except (psutil.Error, TypeError):
                pass
        return achados

    antes = {"hud": False, "ext": False}
    sumiu = {"hud": 0, "ext": 0}
    while True:
        await asyncio.sleep(2)
        try:
            hud_p = await asyncio.to_thread(processos, ".perfil-navegador")
            ext_p = await asyncio.to_thread(processos, ".perfil-extensao")
            agora = {"hud": bool(hud_p), "ext": bool(ext_p)}
            for k in agora:
                sumiu[k] = sumiu[k] + 1 if antes[k] and not agora[k] else 0
            if sumiu["hud"] >= 2 and agora["ext"]:
                for pr in ext_p:
                    pr.kill()
                agora["ext"] = False
            elif sumiu["ext"] >= 2 and agora["hud"] and extensao.preferida():
                for pr in hud_p:
                    pr.kill()
                agora["hud"] = False
            for k in agora:  # "antes" só esquece a janela depois de confirmar que sumiu
                if agora[k] or sumiu[k] >= 2 or not antes[k]:
                    antes[k] = agora[k]
        except Exception as e:
            print("telas juntas:", e)


@app.on_event("startup")
async def ligar_telas_juntas():
    tarefas_de_fundo.add(asyncio.create_task(telas_andam_juntas()))


@app.post("/api/reouvir")
def reouvir():
    """O segundo plano ouviu "Jarvis" e a tela não reagiu: manda a tela reiniciar o reconhecimento."""
    extensao.publicar({"reouvir": True}, "hud")
    return {"ok": True}


@app.get("/api/status")
def status():
    return {"tela_aberta": time.time() - ultimo_sinal_da_tela < 6, "tela_viva": time.time() - vida_das_telas["hud"] < 10,
            "tela_ouvindo": ouvido_da_tela["estado"] != "morto",
            "ouvido_da_tela": ouvido_da_tela["estado"], "tela_ouviu_ha": time.time() - ouvido_da_tela["ouviu_em"],
            "modelo": cerebro.nome_do_cerebro(), "modo": modo_atual(),
            "musica": musica_tocando["agora"], "autenticado": rosto_ja_conferido() or not ARQUIVO_ROSTO.exists() or not CONFIG.get("usar_rosto", True), "casa": {k: lugares.CASA[k] for k in ("lat", "lng")}, "extensao": extensao.aberta(), "usar_extensao": extensao.preferida(),
            "trechos_de_conhecimento": len(TRECHOS)}


@app.get("/spotify/conectar")
def spotify_conectar():
    if not spotify.ARQUIVO_APP.exists():
        return Response("Falta o spotify.json com o client_id (veja o LEIA-ME).", media_type="text/plain; charset=utf-8")
    return RedirectResponse(spotify.endereco_de_login())


@app.get("/spotify/retorno")
def spotify_retorno(code: str = "", error: str = ""):
    if error or not code:
        return Response(f"O Spotify não autorizou: {error}", media_type="text/plain; charset=utf-8")
    spotify.concluir_login(code)
    return Response("Spotify conectado! Pode fechar esta aba e pedir uma música pro Jarvis.",
                    media_type="text/plain; charset=utf-8")


@app.get("/favicon.ico")
def favicon():
    return FileResponse(RAIZ / "web" / "marca" / "jarvis.ico")


CELULAR = re.compile(r"iPhone|iPad|iPod|Android.*Mobile", re.I)


@app.get("/")
def inicio(request: Request):
    # pelo Tailscale, do celular: a tela leve (botão de falar; o iPhone não deixa o microfone ouvindo direto
    # nem som tocar sem toque). /?pc força a tela do PC.
    if CELULAR.search(request.headers.get("user-agent", "")) and "pc" not in request.query_params:
        return FileResponse(RAIZ / "web" / "celular.html")
    return FileResponse(RAIZ / "web" / "index.html")


@app.get("/celular")
def pagina_do_celular():  # (não pode chamar "celular": é o nome do módulo)
    return FileResponse(RAIZ / "web" / "celular.html")


@app.post("/api/celular/estado")
async def celular_estado(request: Request):
    """Localização (tela do celular, a cada pouco) e bateria (Atalho da Siri). Vale como o "aqui" das buscas."""
    try:
        d = await request.json()
    except ValueError:
        d = {}
    return celular.receber(d if isinstance(d, dict) else {})


SIM_SIRI = re.compile(r"^(?:sim|pode|pode sim|pode ser|confirmo|manda|claro|isso(?: a[íi])?|vai|beleza|blz|ok|okay|okey|"
                      r"tranquil[oa]|fechou|fechado|combinado|de boa|dboa|exato|t[aá] (?:bom|certo|[oó]timo))\b", re.I)
NAO_SIRI = re.compile(r"^(?:n[aã]o|cancela|deixa|esquece)\b", re.I)


@app.post("/api/celular/atalho")
async def celular_atalho(request: Request):
    """Pela Siri ("E aí, Jarvis"): o Atalho do iPhone dita o pedido, manda pra cá e a Siri fala o texto que voltar.
    Corpo: {"texto": "...", "bateria": 80, "carregando": false} (ou só o texto puro). Conta como pedido do celular."""
    bruto = (await request.body()).decode("utf-8", "ignore").strip()
    try:
        d = json.loads(bruto) if bruto.startswith("{") else {"texto": bruto}
    except ValueError:
        d = {"texto": bruto}
    if d.get("bateria") not in (None, ""):
        celular.receber({"bateria": d["bateria"], "carregando": str(d.get("carregando")).lower() in ("1", "true", "sim", "yes")})
    texto = str(d.get("texto") or "").strip()
    if not texto:
        return Response("Fala comigo, chefe.", media_type="text/plain; charset=utf-8")
    sid = "siri"
    sessao = sessoes.setdefault(sid, {"mensagens": [], "pendente": None, "celular": True})
    if sessao.get("pendente") and (SIM_SIRI.match(texto) or NAO_SIRI.match(texto)):
        resposta = await decidir(Decisao(sessao=sid, autorizado=bool(SIM_SIRI.match(texto))))
    else:
        resposta = await conversar(Pergunta(sessao=sid, texto=texto, celular=True))
    partes = []
    if isinstance(resposta, StreamingResponse):
        async for pedaco in resposta.body_iterator:
            for linha in (pedaco.decode() if isinstance(pedaco, bytes) else pedaco).splitlines():
                try:
                    e = json.loads(linha)
                except ValueError:
                    continue
                if e.get("trecho"):
                    partes.append(e["trecho"])
                if e.get("leitura"):
                    partes.extend(e["leitura"].get("frases") or [])
                if e.get("pendente"):
                    partes.append((e["pendente"].get("fala") or "Confirma?") + " Me chama de novo e diz sim ou não.")
                if e.get("erro"):
                    partes.append("Deu um erro: " + str(e["erro"])[:120])
    fala = re.sub(r"\s+", " ", " ".join(partes)).strip() or "Feito, chefe."
    return Response(fala[:1500], media_type="text/plain; charset=utf-8")


@app.post("/api/celular/log")
async def celular_log(request: Request):
    """Diagnóstico da tela do celular (erro do microfone etc.): vai pra celular-log.txt pra eu ler daqui."""
    try:
        d = await request.json()
    except ValueError:
        d = {}
    with open(RAIZ / "celular-log.txt", "a", encoding="utf-8") as f:
        f.write(time.strftime("%d/%m %H:%M:%S ") + json.dumps(d, ensure_ascii=False)[:2000] + "\n")
    return {"ok": True}


@app.post("/api/celular/ouvir")
async def celular_ouvir(request: Request):
    """O áudio gravado no celular (m4a no iPhone, webm no Android) → texto, pelo mesmo Whisper do segundo plano."""
    audio = await request.body()
    if len(audio) < 1500:
        return {"texto": ""}
    tipo = request.headers.get("content-type", "audio/mp4").split(";")[0]
    nome = "fala." + {"audio/webm": "webm", "audio/ogg": "ogg", "audio/wav": "wav", "audio/mpeg": "mp3"}.get(tipo, "m4a")
    texto = await asyncio.to_thread(cerebro.transcrever, audio, None, (), (nome, tipo))
    if texto is None:
        raise HTTPException(503, "Não consegui transcrever (sem chave da Groq ou sem internet).")
    return {"texto": texto}


# ================================================================ API das telas novas
# (Olho de Deus, painéis, Configurações, Conectores). Tudo local, em 127.0.0.1.

@app.on_event("startup")
async def ligar_indice():
    indice.manter_em_dia()  # índice dos arquivos dele, em segundo plano (30 min)


class Selecao(BaseModel):
    tipo: str = "lugar"
    nome: str = ""
    lat: float | None = None
    lng: float | None = None
    caixa: list[float] | None = None


@app.post("/api/selecao")
def api_selecao(sel: Selecao):
    """Ele clicou num país/estado/cidade no globo: o Jarvis passa a saber o que está selecionado."""
    selecao_do_globo.clear()
    if sel.nome:
        selecao_do_globo.update(sel.model_dump(), quando=time.time())
    return {"ok": True}


@app.get("/api/onde")
async def api_onde(lat: float, lng: float):
    """Clique no globo bem de perto: que cidade/bairro é esse (Nominatim ao contrário)."""
    def buscar():
        try:
            j = httpx.get("https://nominatim.openstreetmap.org/reverse", headers={"User-Agent": "JarvisAssistente/1.0"}, timeout=8,
                          params={"lat": lat, "lon": lng, "format": "json", "zoom": 10, "accept-language": "pt-BR"}).json()
        except Exception:
            return {}
        end = j.get("address") or {}
        cidade = end.get("city") or end.get("town") or end.get("village") or end.get("municipality") or ""
        caixa = [float(x) for x in j.get("boundingbox", [])] or None
        return {"cidade": cidade, "estado": end.get("state", ""), "pais": end.get("country", ""), "caixa": caixa}
    return await asyncio.to_thread(buscar)


@app.get("/api/vista")
async def api_vista(lat: float, lng: float, z: int = 18):
    """Foto de satélite da quadra: 3×3 ladrilhos da Esri juntados num JPG (guardado em dados/vistas)."""
    import io
    import math
    from PIL import Image
    z = max(3, min(19, z))
    destino = RAIZ / "dados" / "vistas" / f"{lat:.5f}_{lng:.5f}_{z}.jpg"
    if not destino.exists():
        n = 2 ** z
        fx = (lng + 180) / 360 * n
        fy = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
        x0, y0 = int(fx) - 1, int(fy) - 1

        def montar():
            img = Image.new("RGB", (768, 768))
            with httpx.Client(timeout=10, headers={"User-Agent": "JarvisAssistente/1.0"}) as cli:
                for dx in range(3):
                    for dy in range(3):
                        try:
                            r = cli.get(f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y0 + dy}/{x0 + dx}")
                            img.paste(Image.open(io.BytesIO(r.content)).convert("RGB"), (dx * 256, dy * 256))
                        except Exception:
                            pass
            # recorta centrado no ponto exato
            cx, cy = (fx - x0) * 256, (fy - y0) * 256
            corte = img.crop((int(cx - 300), int(cy - 200), int(cx + 300), int(cy + 200)))
            destino.parent.mkdir(parents=True, exist_ok=True)
            corte.save(destino, "JPEG", quality=85)
        await asyncio.to_thread(montar)
    return FileResponse(destino, media_type="image/jpeg")


# ---------------------------------------------------------------- instalação (outro PC), assistente e atualizações

@app.get("/api/instalacao/precisa")
def api_instalacao_precisa():
    return {"precisa": instalacao.precisa_assistente()}


@app.get("/api/instalacao")
async def api_instalacao():
    return {"concluida": instalacao.concluida(), "precisa": await asyncio.to_thread(instalacao.precisa_assistente),
            "itens": await asyncio.to_thread(instalacao.itens), "modelos": [m[0] for m in instalacao.MODELOS],
            "config": {k: CONFIG.get(k) for k in ("nome_do_usuario", "como_chamar", "perfil", "usar_rosto", "casa", "modelo")}}


@app.get("/api/instalacao/hardware")
async def api_instalacao_hardware():
    hw = await asyncio.to_thread(instalacao.hardware)
    return {"hardware": hw, "recomendado": instalacao.recomendado(hw)}


class ItemInstalacao(BaseModel):
    id: str


@app.post("/api/instalacao/instalar")
def api_instalacao_instalar(i: ItemInstalacao):
    instalacao.instalar(i.id)
    return {"ok": True}


class ChaveInstalacao(BaseModel):
    provedor: str = "groq"
    valor: str


@app.post("/api/instalacao/chave")
async def api_instalacao_chave(c: ChaveInstalacao):
    """Cola a chave, testa de verdade e só então guarda no cofre."""
    valor = c.valor.strip()
    prefixo = cerebro.PROVEDORES.get(c.provedor, {}).get("prefixo", "")
    if not valor.startswith(prefixo):
        mostra = " ou ".join(prefixo) if isinstance(prefixo, tuple) else prefixo
        return {"ok": False, "texto": f"Essa não parece uma chave do {c.provedor.capitalize()} (começa com {mostra})."}
    try:
        r = await asyncio.to_thread(lambda: httpx.get(cerebro.PROVEDORES[c.provedor]["url"] + "/models",
                                                      headers={"Authorization": f"Bearer {valor}"}, timeout=10))
        if r.status_code != 200:
            return {"ok": False, "texto": f"O {c.provedor.capitalize()} recusou essa chave ({r.status_code}). Confere se copiou inteira."}
    except Exception:
        return {"ok": False, "texto": "Sem internet pra testar agora; tenta de novo quando conectar."}
    cofre.guardar(f"chave:{c.provedor}", valor)
    cerebro._listas.pop(c.provedor, None)
    return {"ok": True, "texto": "Chave testada e guardada no cofre."}


@app.post("/api/instalacao/perfil")
async def api_instalacao_perfil(dados: dict):
    novos = {k: v for k, v in dados.items() if k in ("nome_do_usuario", "como_chamar", "perfil", "usar_rosto", "modelo")}
    cidade = (dados.get("cidade") or "").strip()
    if cidade:
        area = await asyncio.to_thread(olho.area, cidade)
        if area:
            novos["casa"] = {"endereco": "", "bairro": "", "cidade": cidade, "lat": area["lat"], "lng": area["lng"]}
            lugares.CASA.update(novos["casa"])
    mudar_config(novos)
    if "autoinicio" in dados:
        await asyncio.to_thread(instalacao.autoinicio, bool(dados["autoinicio"]))
    return {"ok": True}


@app.post("/api/instalacao/concluir")
def api_instalacao_concluir():
    instalacao.marcar_concluida()
    for s_ in sessoes.values():  # nome, perfil e cidade novos já valem
        if s_.get("mensagens"):
            s_["mensagens"][0] = {"role": "system", "content": prompt_do_sistema()}
    return {"ok": True}


@app.get("/api/instalacao/autoinicio")
def api_autoinicio():
    return {"ligado": instalacao.autoinicio()}


class Liga(BaseModel):
    ligado: bool


@app.post("/api/instalacao/autoinicio")
def api_autoinicio_mudar(l_: Liga):
    return {"ligado": instalacao.autoinicio(l_.ligado)}


@app.get("/api/atualizacao")
async def api_verificar_atualizacao():
    return await asyncio.to_thread(instalacao.verificar_atualizacao)


@app.post("/api/atualizacao")
async def api_atualizar():
    return await asyncio.to_thread(instalacao.atualizar)


class Reinicio(BaseModel):
    atraso: int = 0


@app.post("/api/reiniciar")
def api_reiniciar(r_: Reinicio | None = None):
    instalacao.reiniciar((r_ or Reinicio()).atraso)
    return {"ok": True}


FOTOS_LOCAIS = RAIZ / "dados" / "fotos-locais.json"


@app.get("/api/foto_local")
async def api_foto_local(lat: float, lng: float, nome: str = ""):
    """Foto da loja como no Google (Meu Negócio), pela API oficial do Places — precisa da chave "google_places" no
    cofre (projeto Google Cloud com faturamento ativo; o uso pessoal fica na cota grátis). Sem chave: a vista de cima
    da quadra (Esri). Guardado em disco: a mesma loja não gasta cota de novo."""
    chave = f"{lat:.5f},{lng:.5f}"
    try:
        guardadas = json.loads(FOTOS_LOCAIS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        guardadas = {}
    if chave in guardadas and guardadas[chave].get("foto"):
        return guardadas[chave]
    satelite = {"foto": lugares.satelite({"lat": lat, "lng": lng}, 90),
                "credito": "Vista de cima: Esri · foto da loja: ponha a chave do Google Places no cofre"}
    api = cofre.pegar("google_places")
    if not api:
        return satelite

    def buscar():
        r = httpx.post("https://places.googleapis.com/v1/places:searchText", timeout=10, headers={
            "X-Goog-Api-Key": api, "Content-Type": "application/json",
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.photos,places.rating,"
                                "places.userRatingCount,places.currentOpeningHours.openNow"},
            json={"textQuery": nome or "loja", "maxResultCount": 1, "languageCode": "pt-BR",
                  "locationBias": {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": 150.0}}})
        lugar = (r.json().get("places") or [None])[0]
        if not lugar:
            return None
        saida = {"endereco": lugar.get("formattedAddress"), "nota": lugar.get("rating"), "avaliacoes": lugar.get("userRatingCount"),
                 "aberto": (lugar.get("currentOpeningHours") or {}).get("openNow"), "credito": "Foto: Google"}
        fotos = lugar.get("photos") or []
        if fotos:
            m = httpx.get(f"https://places.googleapis.com/v1/{fotos[0]['name']}/media", timeout=10,
                          params={"maxWidthPx": 900, "key": api, "skipHttpRedirect": "true"}).json()
            saida["foto"] = m.get("photoUri")
            autor = (fotos[0].get("authorAttributions") or [{}])[0].get("displayName")
            if autor:
                saida["credito"] = f"Foto: {autor} (Google)"
        return saida
    try:
        achado = await asyncio.to_thread(buscar)
    except Exception:
        achado = None
    if not achado or not achado.get("foto"):
        return {**satelite, **{k: v for k, v in (achado or {}).items() if k != "foto" and v}}
    guardadas[chave] = achado
    FOTOS_LOCAIS.parent.mkdir(exist_ok=True)
    FOTOS_LOCAIS.write_text(json.dumps(guardadas, ensure_ascii=False), encoding="utf-8")
    return achado


@app.get("/api/olho/{camada}")
async def api_olho(camada: str, lat: float | None = None, lng: float | None = None, caixa: str = ""):
    if camada == "avioes" and caixa:
        s_, n_, o_, l_ = (float(x) for x in caixa.split(","))
        lista = await asyncio.to_thread(olho.avioes_na_caixa, s_, n_, o_, l_)
        olho.lembrar_lista(lista, ((s_ + n_) / 2, (o_ + l_) / 2))  # pra "que avião é esse?"
        return lista
    if camada == "avioes":
        la, ln = (lat if lat is not None else lugares.CASA["lat"]), (lng if lng is not None else lugares.CASA["lng"])
        lista = await asyncio.to_thread(olho.avioes, la, ln)
        olho.lembrar_lista(lista, (la, ln))
        return lista
    if camada == "satelites":
        return await asyncio.to_thread(olho.satelites)
    if camada == "terremotos":
        return await asyncio.to_thread(olho.terremotos)
    if camada == "clima":
        return await asyncio.to_thread(olho.clima)
    if camada == "noticias":
        return await asyncio.to_thread(olho.manchetes)
    raise HTTPException(404, "camada desconhecida")


@app.get("/api/aviao")
async def api_aviao(hex: str = "", voo: str = "", reg: str = "", tipo: str = "", lat: float | None = None, lng: float | None = None,
                    alt_m: float = 0, vel_kmh: float = 0):
    """Clique num avião do globo: quem é, de onde vem, pra onde vai, e a foto."""
    d = await asyncio.to_thread(olho.detalhes_aviao, hex, voo.strip(), reg, tipo)
    a = {"voo": voo.strip(), "alt_m": alt_m, "vel_kmh": vel_kmh}
    return {**d, "frase": olho.frase_do_aviao(a, d)}


class Destaque(BaseModel):
    id: str
    i: int


class Arrasto(BaseModel):
    id: str
    de: str = "extensao"
    dado: dict | None = None


@app.post("/api/holo/fechado")
def api_holo_fechado(d: dict):
    """Fechou o holograma no X: para de atualizar os dados."""
    if d.get("id") == holo_atual.get("id"):
        holo_atual.clear()
    return {"ok": True}


@app.post("/api/mover_item")
def api_mover_item(a: Arrasto):
    """Arrastou um painel/pop-up até a borda: ele passa pra outra tela."""
    fala = extensao.mover_por_id(a.id, a.de, CONFIG["porta"], a.dado)
    return {"ok": bool(fala), "fala": fala}


parar_agora = {"em": 0.0}


@app.post("/api/parar")
def api_parar():
    """"Para!" no meio de uma execução: o laço do cérebro desiste no próximo passo, e o que estava na fila sai."""
    parar_agora["em"] = time.time()
    for s_ in sessoes.values():
        s_["pendente"] = None
    plano_atual.clear()
    return {"ok": True}


@app.post("/api/destacar")
def api_destacar(d: Destaque):
    """A voz começou a ler o tópico i do painel: acende ele na tela."""
    if d.id == noticias_painel.atual.get("id") and d.i >= 0:
        noticias_painel.atual["lendo"] = d.i  # "abre essa notícia" = a que ele está contando
    extensao.publicar_tela({"destacar": {"id": d.id, "i": d.i}})
    return {"ok": True}


@app.get("/api/leitura")
async def api_leitura(url: str):
    """Modo leitura (clique numa fonte): texto limpo da página, mostrado dentro do Jarvis."""
    return await asyncio.to_thread(pesquisa_painel.leitura, url)


class Estado(BaseModel):
    estado: str
    texto: str = ""


@app.post("/api/estado")
def api_estado(e: Estado):
    """O HUD avisa o que está fazendo (ouvindo/pensando/agindo/falando): a extensão anima junto."""
    extensao.publicar({"estado": {"estado": e.estado, "texto": e.texto}})
    return {"ok": True}


# ---------------------------------------------------------------- Configurações

CAMPOS_DE_CONFIG = {"perfil", "usar_rosto", "casa", "nome_do_usuario", "como_chamar", "voz", "voz_velocidade", "voz_tom", "volume", "modelo", "contexto",
                    "keep_alive", "limite_ram_gb", "confirmar_acoes_perigosas", "proatividade", "animacoes_leves", "tema",
                    "idioma", "pastas_indexadas", "ler_topicos", "tela_dos_sites", "palavra_de_ativacao", "abertura"}


@app.get("/api/config")
async def api_config():
    cfg = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
    return {"config": {k: v for k, v in cfg.items() if k in CAMPOS_DE_CONFIG},
            "proatividade": proatividade.config(), "modo": modo_atual(),
            "cerebro": cerebro.nome_do_cerebro(), "nuvem": [p for p in cerebro.PROVEDORES if cerebro.chave(p)],
            "modelos_locais": await asyncio.to_thread(diagnostico.modelos_locais),
            "benchmark": diagnostico.ultimo_benchmark(), "cofre": cofre.nomes(), "indice": indice.situacao(),
            "maquina": diagnostico.maquina()}


@app.post("/api/config")
def api_salvar_config(novos: dict):
    validos = {k: v for k, v in novos.items() if k in CAMPOS_DE_CONFIG}
    if "proatividade" in validos:
        validos["proatividade"] = {**proatividade.config(), **(validos["proatividade"] or {})}
    if "tema" in validos and validos["tema"] in ("normal", "caverna"):
        mudar_modo(validos["tema"])
        extensao.publicar({"modo": validos["tema"]})
    mudar_config(validos)
    return {"ok": True, "salvo": sorted(validos)}


@app.get("/api/vozes")
async def api_vozes():
    try:
        vozes = await edge_tts.list_voices()
    except Exception:
        return []
    return [{"nome": v["ShortName"], "genero": v.get("Gender"), "local": v.get("Locale")}
            for v in vozes if v.get("Locale", "").startswith("pt-")]


@app.get("/api/memoria")
def api_memoria():
    linhas = [l[2:] for l in (ARQUIVO_MEMORIA.read_text(encoding="utf-8").splitlines() if ARQUIVO_MEMORIA.exists() else [])
              if l.startswith("- ")]
    return {"fatos": linhas, "habilidades": aprendizado.listar() if hasattr(aprendizado, "listar") else [],
            "frases": interpretador._aprendidas(), "resumo": memoria_conversa.resumo_guardado()}


class Memoria(BaseModel):
    fatos: list[str]


@app.post("/api/memoria")
def api_salvar_memoria(m: Memoria):
    """Ele editou o que o Jarvis lembra dele (Configurações → Memória)."""
    fatos = [" ".join(f.split())[:300] for f in m.fatos if f.strip()]
    ARQUIVO_MEMORIA.write_text("# O que o Jarvis aprendeu\n\n" + "".join(f"- {f}\n" for f in fatos), encoding="utf-8")
    recarregar_conhecimento()
    for s in sessoes.values():  # o prompt muda: as próximas conversas já usam a memória nova
        if s.get("mensagens"):
            s["mensagens"][0] = {"role": "system", "content": prompt_do_sistema()}
    return {"ok": True, "fatos": len(fatos)}


@app.delete("/api/memoria/resumo")
def api_esquecer_resumo():
    memoria_conversa.esquecer()
    for s in sessoes.values():
        s["resumo"] = ""
    return {"ok": True}


@app.delete("/api/memoria/frase")
def api_esquecer_frase(frase: str):
    interpretador.esquecer(frase)
    return {"ok": True}


@app.delete("/api/memoria/habilidade")
def api_esquecer_habilidade(nome: str):
    return {"fala": aprendizado.esquecer_habilidade(nome)}


@app.get("/api/registro")
def api_registro(n: int = 200):
    return registro.ultimas(n)


@app.post("/api/registro/desfazer")
def api_desfazer():
    return {"fala": registro.desfazer_ultimo()}


@app.delete("/api/registro")
def api_limpar_registro():
    registro.limpar()
    return {"ok": True}


class Segredo(BaseModel):
    nome: str
    valor: str


@app.get("/api/cofre")
def api_cofre():
    return {"nomes": cofre.nomes()}  # nunca os valores


@app.post("/api/cofre")
def api_cofre_guardar(s_: Segredo):
    nome = s_.nome.strip()
    if nome in ("groq", "gemini"):
        nome = f"chave:{nome}"
    cofre.guardar(nome, s_.valor.strip())
    return {"ok": True}


@app.delete("/api/cofre/{nome:path}")
def api_cofre_apagar(nome: str):
    cofre.apagar(nome)
    return {"ok": True}


@app.post("/api/cofre/proteger")
def api_cofre_proteger():
    return {"movidas": cofre.proteger_arquivos_antigos()}


# ---------------------------------------------------------------- Conectores

@app.get("/api/conectores")
def api_conectores():
    return conectores.lista()


@app.post("/api/conectores")
def api_conectores_salvar(dados: dict):
    try:
        return {"ok": True, "nome": conectores.salvar(dados)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.delete("/api/conectores/{nome}")
def api_conectores_remover(nome: str):
    conectores.remover(nome)
    return {"ok": True}


@app.post("/api/conectores/{nome}/testar")
async def api_conectores_testar(nome: str):
    return await conectores.testar(nome)


@app.get("/conectores/oauth/retorno")
def conectores_oauth_retorno(code: str = "", state: str = "", error: str = ""):
    if error or not code:
        return Response(f"O app não autorizou: {error}", media_type="text/plain; charset=utf-8")
    conectores.receber_oauth(code, state)
    return Response("Conectado! Pode fechar esta aba e voltar pro Jarvis.", media_type="text/plain; charset=utf-8")


@app.get("/conectores/google/retorno")
def conectores_google_retorno(code: str = "", error: str = ""):
    if error or not code:
        return Response(f"O Google não autorizou: {error}", media_type="text/plain; charset=utf-8")
    try:
        conectores.google_concluir(code)
    except Exception as e:
        return Response(f"Falhou: {e}", media_type="text/plain; charset=utf-8")
    return Response("Google conectado! Pode fechar esta aba.", media_type="text/plain; charset=utf-8")


# ---------------------------------------------------------------- diagnóstico, benchmark, índice

@app.get("/api/saude")
async def api_saude():
    return await asyncio.to_thread(diagnostico.saude)


@app.post("/api/benchmark")
async def api_benchmark():
    r = await asyncio.to_thread(diagnostico.benchmark)
    if r.get("trocou"):
        CONFIG["modelo"] = cerebro.CONFIG["modelo"] = r["recomendado"]
    return r


@app.get("/api/indice")
def api_indice():
    return indice.situacao()


@app.post("/api/indice/atualizar")
def api_indice_atualizar():
    threading.Thread(target=indice.atualizar, daemon=True).start()
    return {"ok": True}


# ---------------------------------------------------------------- exportar / importar (levar pra outro PC)

ARQUIVOS_EXPORTAVEIS = ["config.json", "conhecimento/memoria.md", "conhecimento/7sevencode.md",
                        "conhecimento/fatos-essenciais.md", "conhecimento/perguntas-e-respostas.md", "habilidades-aprendidas.json", "frases-aprendidas.json",
                        "musicas-aprendidas.json", "vocabulario-aprendido.json", "contatos.json", "automacoes.json",
                        "lugares-conhecidos.json", "apps-conhecidos.json", "dados/conectores.json", "dados/conversa.json"]


@app.get("/api/exportar")
def api_exportar():
    """Um .zip com configurações e o que ele aprendeu. Chaves NÃO vão (o cofre só abre neste PC)."""
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for nome in ARQUIVOS_EXPORTAVEIS:
            p = RAIZ / nome
            if p.exists():
                z.write(p, nome)
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="jarvis-dados-{datetime.now():%Y-%m-%d}.zip"'})


class Importacao(BaseModel):
    zip_base64: str


@app.post("/api/importar")
def api_importar(imp: Importacao):
    import base64
    import io
    import zipfile
    backup = RAIZ / "dados" / "backups" / f"antes-de-importar-{datetime.now():%Y%m%d-%H%M%S}"
    backup.mkdir(parents=True, exist_ok=True)
    trocados = []
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(imp.zip_base64))) as z:
        for nome in z.namelist():
            if nome not in ARQUIVOS_EXPORTAVEIS:
                continue  # só os arquivos conhecidos: nada de código ou caminho estranho dentro do zip
            destino = RAIZ / nome
            if destino.exists():
                (backup / nome).parent.mkdir(parents=True, exist_ok=True)
                (backup / nome).write_bytes(destino.read_bytes())
            destino.parent.mkdir(parents=True, exist_ok=True)
            if nome == "config.json" and destino.exists():
                # o que é DESTE PC fica (perfil, rosto, modelo, porta…); o resto vem do outro PC
                deste = json.loads(destino.read_text(encoding="utf-8"))
                veio = json.loads(z.read(nome).decode("utf-8"))
                for k in ("perfil", "usar_rosto", "modelo", "contexto", "keep_alive", "limite_ram_gb", "porta",
                          "tela_dos_sites", "pastas_indexadas", "pastas_permitidas"):
                    if k in deste:
                        veio[k] = deste[k]
                destino.write_text(json.dumps(veio, ensure_ascii=False, indent=2), encoding="utf-8")
            else:
                destino.write_bytes(z.read(nome))
            trocados.append(nome)
    return {"ok": True, "importados": trocados, "backup": str(backup), "obs": "Reinicie o Jarvis pra tudo valer."}


app.mount("/web", StaticFiles(directory=RAIZ / "web"), name="web")

if __name__ == "__main__":
    import sys
    import uvicorn
    if sys.stdout is None:  # pythonw (escondido) não tem console: o log vai para arquivo
        sys.stdout = sys.stderr = open(RAIZ / "jarvis.log", "a", encoding="utf-8", buffering=1)
    uvicorn.run(app, host="127.0.0.1", port=CONFIG["porta"], log_level="warning")
