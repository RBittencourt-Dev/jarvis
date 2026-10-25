const $ = (id) => document.getElementById(id);
let sessao = null;
let mudo = false;
// "muta o microfone": surdo = só reage a "desmuta"/"escuta". "…do PC": micDoWindows = mutado no Windows (volta no clique)
let surdo = false, micDoWindows = false;
const DESMUTAR = /^(jarvis[ ,]*)?(des ?mut\w*|desmute|escuta|me escuta|pode (escutar|ouvir)|volta a (ouvir|escutar)|(liga|ativa|abre) o (microfone|mic))\b/i;
const AVISO_SURDO = "Mutado: diga “desmuta”";
const AVISO_WINDOWS = "Microfone do PC mutado: clique no 7";

function aplicarMicrofone(como) {
  surdo = como === "surdo";
  micDoWindows = como === "windows";
  if (micDoWindows) { mudo = true; pararDeOuvir(); }
  if (como === "ligado") mudo = false;
  document.body.classList.toggle("mudo", surdo || micDoWindows);
  if (como === "ligado") voltarAEscutar();
}

// Desmutou (falando ou no clique): a escuta recomeça do zero — depois de muito tempo mutado ela podia estar morta —
// e a conversa fica aberta 30 s, sem precisar dizer "Jarvis".
function voltarAEscutar() {
  if (!Reconhecimento) return;
  criarReconhecimento();
  vivoEm = Date.now();
  ultimaTroca = Date.now();
  setTimeout(() => { ouvir(); if (!ocupado) estado("ouvindo", "Pode falar"); }, 250);
}
let ocupado = false; // pensando ou falando: o microfone não escuta a própria voz

// ------------------------------------------------------------- sons tecnológicos (sintetizados, sem arquivo)
const sons = (() => {
  let ctx = null;
  const tom = (freq, ini, dur, vol = 0.05, tipo = "sine", ate = null) => {
    ctx = ctx || new AudioContext();
    const t0 = ctx.currentTime + ini;
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.type = tipo;
    o.frequency.setValueAtTime(freq, t0);
    if (ate) o.frequency.exponentialRampToValueAtTime(ate, t0 + dur);
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(vol, t0 + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    o.connect(g).connect(ctx.destination);
    o.start(t0); o.stop(t0 + dur + 0.02);
  };
  const caverna = () => document.body.classList.contains("caverna");
  // radar enquanto ele busca: um "ping" de sonar com eco a cada 1,2 s, e um tique fino no meio da volta
  let radar = null, radarInicio = null;
  const pingDoRadar = () => {
    const base = caverna() ? 620 : 1150;
    tom(base, 0, 0.42, 0.03, "sine", base * 0.92);
    tom(base, 0.2, 0.3, 0.01, "sine", base * 0.92);  // eco
    tom(base * 2.1, 0.62, 0.025, 0.012, "triangle");
  };
  return {
    radar(ligar) {
      clearTimeout(radarInicio); clearInterval(radar); radar = null;
      if (!ligar) return;
      // só começa se a resposta demorar: o que é na hora não precisa de radar
      radarInicio = setTimeout(() => { pingDoRadar(); radar = setInterval(pingDoRadar, 1200); }, 450);
    },
    pensando() { [880, 1320, 1760].forEach((f, i) => tom(caverna() ? f / 2 : f, i * 0.07, 0.06, 0.035)); },
    cartao() { tom(caverna() ? 900 : 1600, 0, 0.05, 0.04, "triangle"); tom(caverna() ? 1350 : 2400, 0.05, 0.05, 0.03, "triangle"); },
    abrir() { tom(caverna() ? 200 : 420, 0, 0.18, 0.045, "sawtooth", caverna() ? 600 : 1300); },
    // executando uma ferramenta: rajada de "dados" subindo; terminou: dois tons de confirmação; falhou: grave descendo
    passo() { for (let i = 0; i < 6; i++) tom(1400 + Math.random() * 1600, i * 0.045, 0.03, 0.014, "square"); tom(220, 0, 0.25, 0.02, "sawtooth", 440); },
    feito() { tom(880, 0, 0.08, 0.035, "sine"); tom(1320, 0.08, 0.14, 0.035, "sine"); },
    falhou() { tom(330, 0, 0.3, 0.05, "sawtooth", 110); },
    palco(ligar) { ligar ? (tom(90, 0, 0.6, 0.05, "sawtooth", 300), tom(1200, 0.2, 0.25, 0.02, "sine", 2400)) : tom(900, 0, 0.35, 0.03, "sine", 200); },
    modo(entrando) {
      if (entrando) { tom(110, 0, 0.6, 0.08, "sawtooth", 55); tom(220, 0.05, 0.5, 0.04, "square", 110); }
      else { tom(300, 0, 0.35, 0.05, "sine", 900); }
    },
  };
})();

function aplicarModo(modo) {
  document.body.classList.toggle("caverna", modo === "caverna");
}
fetch("/api/status").then((r) => r.json()).then((s) => aplicarModo(s.modo)).catch(() => {});

// modos de vista do HUD (ref jarvis_hud.json): completo (padrão) / foco / segurança. Fica guardado neste PC.
function aplicarVista(nome) {
  const cls = { foco: "modo-foco", minimalista: "modo-foco", completo: "", completa: "", seguranca: "modo-seguranca" }[nome];
  document.body.classList.remove("modo-foco", "modo-seguranca");
  if (cls) document.body.classList.add(cls);
  try { localStorage.setItem("vista", nome); } catch {}
}
try { const v = localStorage.getItem("vista"); if (v) aplicarVista(v); } catch {}
// "modo foco/completo/segurança" dito por voz troca a vista aqui mesmo, sem ir pro servidor
function trocouVista(texto) {
  const m = texto.toLowerCase().match(/\bmodo\s+(foco|minimalista|complet[oa]|seguran[çc]a)\b/);
  if (!m) return false;
  const nome = m[1].startsWith("complet") ? "completo" : m[1].replace("ç", "c");
  aplicarVista(nome === "minimalista" ? "foco" : nome);
  escrever(m[0], "eu");
  estado("", "Modo " + (nome === "foco" || nome === "minimalista" ? "foco" : nome));
  return true;
}

function estado(classe, texto) {
  if (classe === "pensando" && !document.body.classList.contains("pensando")) { sons.pensando(); sons.radar(true); }
  if (classe !== "pensando") sons.radar(false);
  document.body.classList.remove("ouvindo", "falando", "pensando", "agindo", "alerta");
  if (classe) document.body.classList.add(classe);
  $("estado").textContent = texto;
  if (classe !== estado.ultimo) {
    estado.ultimo = classe;
    fetch("/api/estado", { method: "POST", headers: { "Content-Type": "application/json" },
                           body: JSON.stringify({ estado: classe || "parado", texto }) }).catch(() => {});
  }
}

// Legenda embaixo do núcleo: só as últimas falas, as antigas apagadas.
// o nome como o reconhecimento costuma escrever: Jarvis, Járvis, Jarbis, Jarves, Jarvi
const NOME = /\bj[aá]r(?:v|b)[iíe]s?\b|\bjarvi\b/i;
let acordadoEm = 0;  // ouviu "Jar…" agora há pouco (antes de terminar a palavra)

function escrever(texto, quem = "jarvis") {
  const conversa = $("conversa");
  [...conversa.children].forEach((f) => f.classList.add("velha"));
  while (conversa.children.length > 2) conversa.firstElementChild.remove();
  const p = document.createElement("div");
  p.className = "fala " + quem;
  p.textContent = texto;
  conversa.append(p);
}

// Cartões em volta do núcleo: seis vagas; o sétimo empurra o mais antigo para fora.
const VAGAS = 6;
let proximaVaga = 0;
const cartoes = []; // { el, vaga }

function mostrarCartao({ id, onde, titulo, destaque, linhas = [], aguardando, texto, imagens = [], links = [], rapido, alerta }) {
  // "na outra tela" vai pra extensão; "aqui" fica no HUD; sem dizer, a extensão aberta leva
  if (onde === "outra" || onde === "palco" || (onde !== "aqui" && extensaoAberta && !aguardando)) { sons.cartao(); return; }
  const repetido = id && cartoes.find((x) => x.el.dataset.id === id);
  if (repetido) { cartoes.splice(cartoes.indexOf(repetido), 1); repetido.el.remove(); }
  if (alerta) {  // cartão de alerta acende o núcleo em vermelho por alguns segundos
    document.body.classList.add("alerta");
    clearTimeout(mostrarCartao._al); mostrarCartao._al = setTimeout(() => document.body.classList.remove("alerta"), 7000);
  }
  const vaga = proximaVaga++ % VAGAS;
  const ocupante = cartoes.find((c) => c.vaga === vaga);
  if (ocupante) {
    cartoes.splice(cartoes.indexOf(ocupante), 1);
    ocupante.el.classList.add("saindo");
    setTimeout(() => ocupante.el.remove(), 400);
  }
  const c = document.createElement("article");
  c.className = `cartao v${vaga}` + (aguardando ? " aguardando" : "");
  if (id) c.dataset.id = id;
  const h = document.createElement("h3"); h.textContent = titulo;
  const d = document.createElement("div"); d.className = "destaque"; d.textContent = destaque;
  const ul = document.createElement("ul");
  linhas.forEach((l, i) => { const li = document.createElement("li"); li.textContent = l; li.style.animationDelay = `${0.15 * (i + 1)}s`; ul.append(li); });
  c.append(h, d);
  if (imagens.length) {
    // fotos da pesquisa (Wikipédia/Commons): clicar abre grande no navegador
    const galeria = document.createElement("div");
    galeria.className = "galeria" + (imagens.length === 1 ? " uma" : "");
    for (const url of imagens) {
      const img = document.createElement("img");
      img.src = url; img.alt = destaque || titulo; img.loading = "lazy";
      img.onclick = () => ampliar(url, destaque || titulo);
      img.onerror = () => img.remove();
      galeria.append(img);
    }
    c.append(galeria);
  }
  if (texto) { const p = document.createElement("p"); p.className = "texto"; p.textContent = texto; c.append(p); }
  c.append(ul);
  if (arguments[0].codigo) {
    const pre = document.createElement("pre"); const code = document.createElement("code");
    code.className = "language-" + (arguments[0].linguagem || "plaintext"); code.textContent = arguments[0].codigo;
    pre.append(code); c.append(pre); c.classList.add("grande");
    try { window.hljs?.highlightElement(code); } catch {}
    if (arguments[0].saida != null) { const s = document.createElement("pre"); s.className = "saida" + (arguments[0].erro ? " erro" : ""); s.textContent = arguments[0].saida; c.append(s); }
  }
  if (imagens.length || texto) c.classList.add("grande");
  $("paineis").append(c);
  sons.cartao();
  // informação rápida some sozinha no tempo de ler (mínimo 12 s); foto e lista ficam
  if (rapido ?? (!imagens.length && !links.length && linhas.length <= 3 && (texto || "").length <= 220)) {
    const palavras = `${titulo} ${destaque} ${texto || ""} ${linhas.join(" ")}`.split(/\s+/).length;
    setTimeout(() => {
      const achado = cartoes.find((x) => x.el === c);
      if (!achado) return;
      cartoes.splice(cartoes.indexOf(achado), 1);
      c.classList.add("saindo");
      setTimeout(() => { c.remove(); desenharLigacoes(null); }, 400);
    }, (Math.max(12, Math.round(palavras / 3)) + (alerta ? 8 : 0)) * 1000);
  }
  cartoes.push({ el: c, vaga });
  c.__dado = arguments[0];
  arrastavelHud(c);
  desenharLigacoes(c);
}

// cartão em volta do núcleo arrastado até a borda da tela: vai pra tela lateral
function arrastavelHud(el) {
  el.addEventListener("pointerdown", (ev) => {
    if (ev.button !== 0 || ev.target.closest("button, a, input, img, pre")) return;
    const x0 = ev.clientX, y0 = ev.clientY;
    let ativo = false;
    const mover = (e) => {
      const dx = e.clientX - x0, dy = e.clientY - y0;
      if (!ativo && Math.hypot(dx, dy) < 8) return;
      if (!ativo) { el.setPointerCapture?.(ev.pointerId); window.travessia?.inicio(el, e); }
      ativo = true; el.classList.add("arrastando");
      el.style.transform = `translate(${dx}px, ${dy}px)`;
      window.travessia?.mover(el, e);  // a outra tela desenha a parte que passou da borda (igual ao Windows)
    };
    const soltar = async (e) => {
      removeEventListener("pointermove", mover); removeEventListener("pointerup", soltar);
      if (!ativo) return;
      const sair = window.travessia ? window.travessia.fim(el, e) : false;  // soltou com o mouse na outra tela?
      el.classList.remove("arrastando", "vai-sair");
      el.style.transform = "";
      if (!sair) return;
      const r = await (await fetch("/api/mover_item", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: el.dataset.id || "", de: "hud", dado: el.__dado || null }) })).json().catch(() => ({}));
      if (r.ok) { const achado = cartoes.find((x) => x.el === el); if (achado) cartoes.splice(cartoes.indexOf(achado), 1); el.remove(); desenharLigacoes(null); sons.abrir(); }
    };
    addEventListener("pointermove", mover); addEventListener("pointerup", soltar);
  });
}

// o palco (centro) avisa quando tem algo: o núcleo encolhe pro canto e os cartões vão pra direita
addEventListener("message", (e) => {
  if (e.origin !== location.origin || typeof e.data?.palco !== "boolean") return;
  if (document.body.classList.contains("palco-ativo") !== e.data.palco) sons.palco(e.data.palco);
  document.body.classList.toggle("palco-ativo", e.data.palco);
  setTimeout(() => desenharLigacoes(null), 650);
});

// página / modo leitura na tela principal ("traz a notícia pra cá")
(() => {
  const d = document.createElement("div");
  d.id = "pagina-hud"; d.hidden = true;
  d.innerHTML = `<header><span id="ph-titulo"></span><button class="secundario" id="ph-fechar">✕</button></header>
    <iframe id="ph-quadro" title="Página"></iframe><div id="ph-texto"></div>`;
  document.body.append(d);
  $("ph-fechar").onclick = () => fecharPaginaHud();
})();
function abrirPaginaHud(url, titulo, leitura) {
  const d = $("pagina-hud");
  $("ph-titulo").textContent = titulo || "";
  $("ph-quadro").hidden = !url; $("ph-texto").hidden = !leitura;
  if (url) $("ph-quadro").src = url;
  if (leitura) {
    const t = $("ph-texto"); t.innerHTML = "";
    if (leitura.imagem) { const i = document.createElement("img"); i.src = leitura.imagem; t.append(i); }
    for (const p of leitura.paragrafos || []) { const el = document.createElement(p.startsWith("## ") ? "h2" : "p"); el.textContent = p.replace(/^## /, ""); t.append(el); }
  }
  d.hidden = false;
}
function fecharPaginaHud() { const d = $("pagina-hud"); if (d && !d.hidden) { d.hidden = true; $("ph-quadro").src = "about:blank"; } }

function ampliar(url, legenda) {
  const l = $("lupa");
  l.querySelector("img").src = url; l.querySelector("p").textContent = legenda || "";
  l.hidden = false;
}
$("lupa").onclick = () => ($("lupa").hidden = true);

// ------------------------------------------------------------- linha do tempo: plano e passos ao vivo
let passosVistos = new Map(), someLdt = null;
function mostrarPlano(plano) {
  const ldt = $("linha-do-tempo"), ol = $("ldt-passos");
  $("ldt-titulo").textContent = plano.objetivo || "Plano";
  ol.innerHTML = ""; passosVistos = new Map();
  plano.passos.forEach((p, i) => { const li = document.createElement("li"); li.textContent = p; li.dataset.plano = i; ol.append(li); });
  ldt.hidden = false; clearTimeout(someLdt);
}
function passoNaLinhaDoTempo(p) {
  const ldt = $("linha-do-tempo"), ol = $("ldt-passos");
  ldt.hidden = false; clearTimeout(someLdt);
  let li = passosVistos.get(p.id);
  if (!li) {
    // com plano na tela, o passo ocupa o próximo item do plano; sem plano, vira um item novo
    li = [...ol.querySelectorAll("li[data-plano]:not([data-feito])")][0];
    if (!li) { li = document.createElement("li"); ol.append(li); while (ol.children.length > 8) ol.firstElementChild.remove(); }
    li.dataset.feito = "1";
    if (!li.dataset.plano) li.textContent = p.resumo;
    else li.title = p.resumo;
    passosVistos.set(p.id, li);
  }
  li.className = p.estado;
  if (p.estado !== "rodando") someLdt = setTimeout(() => { if (!ocupado) { ldt.hidden = true; ol.innerHTML = ""; passosVistos.clear(); } }, 9000);
}

// Linha do núcleo até a borda de cada cartão, com um ponto na ponta.
function desenharLigacoes(novo) {
  const svg = $("ligacoes");
  svg.innerHTML = "";
  const n = $("nucleo").getBoundingClientRect();
  const cx = n.left + n.width / 2, cy = n.top + n.height / 2, raio = n.width / 2 + 8;
  for (const { el } of cartoes) {
    const r = el.getBoundingClientRect();
    if (!r.width) continue;
    const bx = r.left > cx ? r.left : r.right, by = r.top + Math.min(40, r.height / 2);
    const ang = Math.atan2(by - cy, bx - cx);
    const ax = cx + Math.cos(ang) * raio, ay = cy + Math.sin(ang) * raio;
    const linha = document.createElementNS("http://www.w3.org/2000/svg", "line");
    Object.entries({ x1: ax, y1: ay, x2: bx, y2: by }).forEach(([k, v]) => linha.setAttribute(k, v));
    if (el !== novo) { linha.style.animation = "none"; linha.style.strokeDashoffset = "0"; }
    const ponto = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    Object.entries({ cx: bx, cy: by, r: 3 }).forEach(([k, v]) => ponto.setAttribute(k, v));
    svg.append(linha, ponto);
  }
}
addEventListener("resize", () => desenharLigacoes(null));

// ------------------------------------------------------------- onda de voz em volta do núcleo
let analisador = null;
const volumes = new Uint8Array(128);

function ligarNoAnalisador(audio) {
  try {
    if (!analisador) {
      const ctx = new AudioContext();
      analisador = ctx.createAnalyser();
      analisador.fftSize = 256;
      analisador.smoothingTimeConstant = 0.75;
      analisador.connect(ctx.destination);
    }
    analisador.context.resume();
    analisador.context.createMediaElementSource(audio).connect(analisador);
  } catch {} // sem analisador a voz toca normal, só a onda fica parada
}

function animarOnda() {
  const tela = $("onda");
  const lado = tela.clientWidth * devicePixelRatio;
  if (tela.width !== lado) { tela.width = tela.height = lado; }
  const ctx = tela.getContext("2d");
  ctx.clearRect(0, 0, lado, lado);
  if (analisador) analisador.getByteFrequencyData(volumes); else volumes.fill(0);
  const barras = 96, meio = lado / 2, raio = lado / 3.6, t = Date.now() / 600;
  let soma = 0;
  const cor = getComputedStyle(document.body).getPropertyValue("--ciano").trim() || "#39d0ff"; // vermelho na caverna
  ctx.strokeStyle = cor;
  ctx.shadowColor = cor;
  ctx.shadowBlur = 10;
  ctx.lineWidth = Math.max(2, lado / 260);
  for (let i = 0; i < barras; i++) {
    // espelha as frequências para a onda ficar simétrica dos dois lados
    const v = volumes[Math.floor((i < barras / 2 ? i : barras - i) * 1.1)] / 255;
    soma += v;
    const repouso = 0.02 + 0.015 * Math.sin(t + i / 4);
    const tam = raio * (repouso + v * 0.55);
    const ang = (i / barras) * Math.PI * 2 - Math.PI / 2;
    ctx.globalAlpha = 0.35 + v * 0.65;
    ctx.beginPath();
    ctx.moveTo(meio + Math.cos(ang) * raio, meio + Math.sin(ang) * raio);
    ctx.lineTo(meio + Math.cos(ang) * (raio + tam), meio + Math.sin(ang) * (raio + tam));
    ctx.stroke();
  }
  document.documentElement.style.setProperty("--nivel", Math.min(1, (soma / barras) * 2.2).toFixed(3));
  requestAnimationFrame(animarOnda);
}
requestAnimationFrame(animarOnda);

// Fila de voz: cada frase pronta já vai pedindo o áudio enquanto a anterior toca.
// cancelar() cala na hora (quando ele interrompe dizendo "Jarvis").
function filaDeVoz() {
  let corrente = Promise.resolve();
  let cancelada = false;
  const audios = [];
  let tocando = null, pendentes = 0, ultimaFrase = "";
  return {
    // segundos que faltam pra ele acabar de falar (Infinity se ainda tem frase na fila)
    falta() {
      if (pendentes > 0) return Infinity;
      if (!tocando || !isFinite(tocando.duration)) return tocando ? Infinity : 0;
      return Math.max(0, tocando.duration - tocando.currentTime);
    },
    ultima: () => ultimaFrase,
    adicionar(frase, aoComecar) {
      if (cancelada) return;
      frase = frase.replace(/[*#_`]/g, "").trim();
      if (!frase) { if (aoComecar) corrente = corrente.then(() => !cancelada && aoComecar()); return; }
      const audio = new Audio("/api/voz?texto=" + encodeURIComponent(frase));
      audio.preload = "auto";
      audio.volume = window.volumeDaVoz ?? 1;  // Configurações → Voz → Volume
      audios.push(audio);
      ultimasFalas.push(frase);
      if (ultimasFalas.length > 6) ultimasFalas.shift();
      ultimaFrase = frase;
      ligarNoAnalisador(audio);
      pendentes++;
      corrente = corrente.then(async () => {
        pendentes--;
        if (cancelada) return;
        estado("falando", "Falando");
        if (aoComecar) aoComecar();
        tocando = audio;
        try {
          await audio.play();
          // nunca espera pra sempre: áudio que travou (servidor lento, Chrome segurando) libera depois do tempo dele
          await new Promise((ok) => {
            audio.onended = audio.onerror = audio.onpause = ok;
            const limite = () => setTimeout(ok, ((isFinite(audio.duration) ? audio.duration : 25) + 4) * 1000);
            if (isFinite(audio.duration)) limite(); else { audio.onloadedmetadata = limite; setTimeout(ok, 45000); }
          });
        } catch {}
        atividade();
        tocando = null;
      });
    },
    terminar: () => corrente,
    cancelar() {
      cancelada = true;
      audios.forEach((a) => { a.pause(); a.src = ""; });
    },
  };
}

// Iguais às do servidor (FRASES_FIXAS), que deixa o áudio delas pronto.
let ESPERAS = ["Deixa eu ver, chefe.", "Um instante.", "Já vejo isso.", "Só um momento, chefe.", "Hum, deixa eu pensar."];
let CHAMADO = ["Pois não, chefe?"], DEMORANDO = ["Tá demorando um pouco, chefe, mas já tô terminando."];
// as variações vêm do servidor (falas.py): mesmo sentido, frases diferentes, e o áudio de todas já pronto
fetch("/api/frases").then((r) => r.json()).then((f) => { ESPERAS = f.esperas; CHAMADO = f.chamado; DEMORANDO = f.demorando; }).catch(() => {});
const ultimaDe = new Map();
function sortear(lista) {
  const opcoes = lista.filter((f) => f !== ultimaDe.get(lista)) ;
  const f = (opcoes.length ? opcoes : lista)[Math.floor(Math.random() * (opcoes.length || lista.length))];
  ultimaDe.set(lista, f);
  return f;
}

// O que está acontecendo agora (resposta chegando / voz tocando), para poder interromper.
let emAndamento = null; // { voz, controlador }
let interrompidoEm = 0;

function interromper() {
  if (!emAndamento) return;
  interrompidoEm = Date.now();
  emAndamento.voz.cancelar();
  emAndamento.controlador?.abort();
  emAndamento = null;
  ocupado = false;
  estado("ouvindo", "Pode falar");
}

async function chamar(url, corpo) {
  ocupado = true;
  estado("pensando", "Pensando");
  const voz = filaDeVoz();
  const controlador = new AbortController();
  const meu = { voz, controlador };
  emAndamento = meu;
  let bolha = null, texto = "", falado = 0, dormir = false, minimizar = false;
  // a legenda cresce junto com a voz: cada pedaço aparece quando começa a ser falado
  const falarELegendar = (pedaco) => voz.adicionar(pedaco, () => {
    if (!bolha) { escrever(""); bolha = $("conversa").lastElementChild; }
    bolha.textContent += pedaco;
  });
  // se a resposta demorar, ele fala alguma coisa em vez de ficar mudo (frases com áudio pronto: saem na hora).
  // A frase combina com o pedido (/api/espera): "me mostra meu PC" → "Montando as peças do seu PC"; papo → fica quieto.
  let esperaCerta = null;
  if (corpo?.texto) fetch("/api/espera?texto=" + encodeURIComponent(corpo.texto)).then((r) => r.json())
    .then((j) => { esperaCerta = j; }).catch(() => {});
  const espera = setTimeout(() => {
    if (!texto && emAndamento === meu && $("autorizacao").hidden) {
      const frase = esperaCerta ? esperaCerta.frase : sortear(ESPERAS);
      if (frase) voz.adicionar(frase);
      // falou "um instante" e a resposta ainda não veio: o radar volta a girar até ela chegar
      voz.terminar().then(() => {
        if (!texto && emAndamento === meu && $("autorizacao").hidden) {
          document.body.classList.replace("falando", "pensando");
          $("estado").textContent = "Buscando";
          sons.radar(true);
        }
      });
    }
  }, 600);
  const demorou = setTimeout(() => {
    if (!texto && emAndamento === meu && $("autorizacao").hidden) voz.adicionar(sortear(DEMORANDO));
  }, 10000);
  try {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo),
                                 signal: controlador.signal });
    if (!r.ok) throw new Error((await r.json()).detail || r.status);
    const leitor = r.body.pipeThrough(new TextDecoderStream()).getReader();
    let resto = "";
    for (;;) {
      const { value, done } = await leitor.read();
      if (done) break;
      resto += value;
      const linhas = resto.split("\n");
      resto = linhas.pop();
      for (const linha of linhas.filter(Boolean)) {
        const e = JSON.parse(linha);
        atividade();
        if (e.sessao) sessao = e.sessao;
        if (e.cartao) mostrarCartao(e.cartao);
        if (e.dormir) dormir = true;
        if (e.minimizar) minimizar = true;
        if (e.modo) { aplicarModo(e.modo); sons.modo(e.modo === "caverna"); }
        if (e.vista) aplicarVista(e.vista);
        if (e.microfone) aplicarMicrofone(e.microfone);
        if (e.trecho && !texto && /^(Abrindo|Abri|Pesquisando|Tocando)/.test(e.trecho)) sons.abrir();
        if (e.entendido) {
          // mostra o que ele entendeu de fato (já corrigido: "seven code" vira "SevenCode")
          const minha = [...$("conversa").querySelectorAll(".fala.eu")].pop();
          if (minha) minha.textContent = e.entendido;
        }
        if (e.saida) mostrarCartao({ titulo: "Resultado", destaque: "Feito", linhas: e.saida.split("\n").slice(0, 8) });
        if (e.passo) {
          passoNaLinhaDoTempo(e.passo);
          if (e.passo.estado === "rodando") { estado("agindo", "Agindo"); sons.passo(); }
          else if (e.passo.estado === "ok") sons.feito(); else if (e.passo.estado === "erro") sons.falhou();
        }
        if (e.leitura) {
          // pesquisa: o que já veio de texto sai antes; depois cada frase acende o seu tópico no painel
          falarELegendar(texto.slice(falado)); falado = texto.length;
          e.leitura.frases.forEach((f, i) => voz.adicionar(f, () => {
            escrever(f);
            if (e.leitura.cartoes?.[i]) mostrarCartao(e.leitura.cartoes[i]);
            fetch("/api/destacar", { method: "POST", headers: { "Content-Type": "application/json" },
                                     body: JSON.stringify({ id: e.leitura.id, i: e.leitura.indices[i] }) }).catch(() => {});
          }));
        }
        if (e.erro) escrever("Falha: " + e.erro, "saida");
        if (e.trecho) {
          texto += e.trecho;
          if (e.falar_ja) {
            // comentário enquanto o servidor trabalha ("Boa escolha, chefe."): fala agora, não espera o resto
            falarELegendar(texto.slice(falado));
            falado = texto.length;
          }
          // só o PRIMEIRO pedaço sai antes (primeira frase, ou uma vírgula depois de umas palavras), pra voz
          // começar logo; o resto vai inteiro no fim, num áudio só, sem as pausas de emendar vários pedaços
          if (!falado) {
            const corte = texto.match(/^[\s\S]{20,}?(?:[.!?;:\n]\s|,\s)/);
            if (corte) { falarELegendar(corte[0]); falado = corte[0].length; }
          }
        }
        if (e.pendente) {
          sons.radar(false);
          $("aut-nome").textContent = e.pendente.nome.replace("_", " ");
          $("aut-args").textContent = Object.values(e.pendente.args).join("\n\n");
          $("autorizacao").hidden = false;
          voz.adicionar(e.pendente.fala || "Confirma, chefe? É só dizer sim ou não.");
        }
      }
    }
    clearTimeout(espera); clearTimeout(demorou);
    falarELegendar(texto.slice(falado));
    await voz.terminar();
    if (emAndamento !== meu) return; // foi interrompido: quem interrompeu já cuida do resto
    acabouDeFalar();
    if (dormir) return irDormir();
    if (minimizar) fetch("/api/minimizar", { method: "POST" }).catch(() => {});
  } catch (e) {
    clearTimeout(espera); clearTimeout(demorou);
    if (emAndamento !== meu) return; // interrompido de propósito, não é falha
    escrever("Falha: " + e.message + ". O Ollama está aberto?", "saida");
  }
  sons.radar(false);  // terminou, falhou ou ficou sem resposta: o radar não pode seguir tocando
  emAndamento = null;
  ocupado = false;
  ouvir();
  if (!$("autorizacao").hidden) estado("ouvindo", "Diga sim ou não");
}

function perguntar(texto, alternativas = [], tom = null) {
  texto = texto.trim();
  if (!texto) return;
  if (trocouVista(texto)) return;  // "modo foco/completo/segurança" é resolvido no HUD, não vai pro servidor
  escrever(texto, "eu");
  chamar("/api/conversar", { sessao, texto, alternativas, ...(tom ? { tom } : {}) });
}

async function irDormir() {
  estado("", "Dormindo");
  document.body.classList.add("dormindo");
  pararDeOuvir();
  await fetch("/api/dormir", { method: "POST" }).catch(() => {});
  window.close();
}

const SIM = /^(sim|pode|pode sim|autoriz|confirm|manda ver|pode ir|vai|claro|isso)/i;
const NAO = /^(n[aã]o|cancela|negativo|deixa|para|esquece|beleza|blz|t[aá] bom|ok|valeu|volta|pode voltar|j[aá] vi|normal)/i;

function decidir(autorizado) {
  $("autorizacao").hidden = true;
  chamar("/api/decidir", { sessao, autorizado });
}

// ------------------------------------------------------------- reconhecimento de voz
const Reconhecimento = window.SpeechRecognition || window.webkitSpeechRecognition;
let rec = null;
let ligado = false;
// saúde do ouvido: quando foi o último sinal de vida do reconhecimento (início, fim, resultado, erro)
let vivoEm = Date.now(), atividadeEm = Date.now();
const atividade = () => (atividadeEm = Date.now());

function criarReconhecimento() {
  try { if (rec) { rec.onend = rec.onresult = rec.onerror = rec.onstart = null; rec.abort(); } } catch {}
  ligado = false;
  rec = new Reconhecimento();
  rec.lang = "pt-BR";
  rec.continuous = true;
  rec.interimResults = true;
  rec.maxAlternatives = 5; // o servidor escolhe a versão que faz sentido
  rec.onresult = (e) => {
    vivoEm = Date.now();
    if (vivoEm - avisouQueOuviu > 800) { avisouQueOuviu = vivoEm; navigator.sendBeacon("/api/ouvi"); }
    const ultimo = e.results[e.results.length - 1];
    if (ocupado) {
      // ele está falando: o microfone ouve a própria voz. Só interrompe com o nome, ou com uma
      // ordem de parar dita SOZINHA ("deu!", "chega", "pera") que não esteja na frase que ele mesmo diz
      const ouvido = ultimo[0].transcript.trim().toLowerCase();
      if (respostaAntecipada(ultimo)) return;
      if (NOME.test(ouvido)) {
        // "Jarvis, para!" / "para, Jarvis": cala e cancela a execução
        if (/\b(para|pare|chega|deu|cancela|esquece|n[aã]o)\b/i.test(ouvido)) fetch("/api/parar", { method: "POST" }).catch(() => {});
        return interromper();
      }
      const parar = ouvido.match(/^(?:j[aá] )?(deu|chega|pera|espera(?: a[ií])?|para(?: a[ií]| j[aá]| de falar)?|pode parar|sil[eê]ncio|stop|cala(?: a)?(?: boca)?|fica quiet[oa]|quiet[oa]|xiu|shh+)(?: a[ií]| j[aá]| chefe)?[.!]?$/);
      if (parar && !ultimasFalas.some((f) => f.toLowerCase().includes(parar[1]))) {
        interromper();
        fetch("/api/parar", { method: "POST" }).catch(() => {});  // e o que ele estava EXECUTANDO para também
      }
      return;
    }
    if (Date.now() < surdoAte || ehEco(ultimo[0].transcript)) return; // o Chrome entregando a voz do próprio Jarvis
    if (surdo) {
      // mutado por voz: o microfone segue ligado só pra ouvir o "desmuta"; todo o resto é ignorado
      if (ultimo.isFinal && [...ultimo].some((a) => DESMUTAR.test(a.transcript.trim()))) perguntar("desmuta o microfone");
      return;
    }
    $("texto").value = (juntando.texto + " " + ultimo[0].transcript).trim();
    if (!juntando.inicio) juntando.inicio = performance.now() - 600;  // começo da fala (pra medir a entonação)
    // "Jar…" no meio da palavra: já responde (som curto + núcleo aceso), sem esperar ele terminar a frase.
    // Se ele emendar o pedido, executa direto; se ficar só no nome, aí sim vem o "Pois não, chefe?".
    if (!conversaAberta() && Date.now() - acordadoEm > 4000 && /\bj[aá]r/i.test(ultimo[0].transcript)) {
      acordadoEm = Date.now();
      sons.abrir();
      estado("ouvindo", "Pode falar");
    }
    clearTimeout(juntando.timer);
    if (ultimo.isFinal) {
      // cada pausa dele vira um pedaço; junta tudo e só age depois de um silêncio
      juntando.texto = (juntando.texto + " " + ultimo[0].transcript).trim();
      juntando.alternativas = [...ultimo].slice(1).map((a) => a.transcript.trim());
    }
    if (juntando.texto) juntando.timer = setTimeout(fimDaFala, 1000);  // 1 s de silêncio = acabou (pausa menor não corta)
  };
  // o reconhecimento fica ligado o tempo todo (também enquanto ele fala, para ouvir o "Jarvis" de interrupção)
  rec.onstart = () => { ligado = true; vivoEm = Date.now(); };
  rec.onend = () => { ligado = false; vivoEm = Date.now(); if (!mudo) setTimeout(ouvir, 300); };
  rec.onerror = (e) => {
    vivoEm = Date.now();
    if (e.error === "not-allowed") estado("", "Microfone bloqueado: libere no cadeado da barra");
    if (e.error !== "no-speech" && e.error !== "aborted") falhasDoOuvido++;
  };
}
let falhasDoOuvido = 0, avisouQueOuviu = 0;
if (Reconhecimento) criarReconhecimento();

// Vigia do ouvido. O bug: depois de muito tempo parado (ou de uma resposta que travou), o reconhecimento do Chrome
// morria calado — e o ouvido de segundo plano achava que a tela estava atendendo. Agora, a cada 5 s:
//  - "ocupado" preso há mais de 90 s sem nada acontecer → solta;
//  - 60 s sem sinal de vida do reconhecimento → reinicia; se nem assim voltar, cria um novo do zero;
//  - e avisa o servidor se o ouvido está vivo: morto, o segundo plano atende o "Jarvis" até a tela voltar.
setInterval(() => {
  if (!rec) return;
  const agora = Date.now();
  if (ocupado && agora - atividadeEm > 90000) {
    try { emAndamento?.voz?.cancelar(); emAndamento?.controlador?.abort(); } catch {}
    emAndamento = null; ocupado = false; sons.radar(false);
    ouvir();
  }
  if (mudo || surdo || document.hidden) return;
  if (agora - vivoEm > 60000 || falhasDoOuvido >= 5) {
    falhasDoOuvido = 0;
    if (agora - vivoEm > 75000 || !ligado) criarReconhecimento();  // nem o reinício respondeu: um novo do zero
    else { try { rec.abort(); } catch {} ligado = false; }
    vivoEm = agora - 50000;  // dá 10 s pro novo dar sinal antes de tentar de novo
    setTimeout(ouvir, 300);
  }
}, 5000);
function saudeDoOuvido() {
  if (!rec) return "morto";
  if (mudo || surdo || micDoWindows) return "mudo";  // mutado de propósito: o segundo plano também não atende
  return Date.now() - vivoEm < 65000 ? "ok" : "morto";
}

const juntando = { texto: "", alternativas: [], timer: null };
let surdoAte = 0;
const ultimasFalas = []; // o que o Jarvis disse por último, para reconhecer o eco

function ehEco(transcricao) {
  const palavras = new Set(transcricao.toLowerCase().match(/[\wà-ú]{3,}/g) || []);
  if (palavras.size < 2) return false;
  return ultimasFalas.some((fala) => {
    const dele = new Set(fala.toLowerCase().match(/[\wà-ú]{3,}/g) || []);
    const iguais = [...palavras].filter((p) => dele.has(p)).length;
    return iguais / palavras.size >= 0.6;
  });
}

// Quando ele termina de falar: o reconhecimento recomeça do zero (descarta o eco que estava no forno)
// e fica surdo um instante.
// Conversa aberta: até 30 s depois da última troca ele escuta direto. Depois disso só age se ouvir
// "Jarvis" — TV, gente conversando ou um vídeo não viram comando.
const CONVERSA_ABERTA_MS = 30000;
let ultimaTroca = Date.now();
// com música tocando, o microfone ouve a letra: aí só vale o que vier depois de "Jarvis"
let musicaTocando = false, extensaoAberta = false;
const lerStatus = () => fetch("/api/status").then((r) => r.json())
  .then((s) => { musicaTocando = !!s.musica; extensaoAberta = !!s.extensao; }).catch(() => {});
setInterval(lerStatus, 3000);
lerStatus();
const conversaAberta = () => !musicaTocando && Date.now() - ultimaTroca < CONVERSA_ABERTA_MS;
setInterval(() => {
  if (ocupado || !$("portao").hidden) return;
  if (surdo) return estado("", AVISO_SURDO);
  if (micDoWindows) return estado("", AVISO_WINDOWS);
  if (!mudo && rec && !conversaAberta()) estado("", "Diga “Jarvis”");
}, 2000);

// Pergunta dele ("Quer ver na rua?", "Confirma?"): no último 1,5 s da fala ele já aceita a resposta,
// corta a própria voz e faz. Só "sim"/"não" (ou, numa pergunta comum, uma frase que não seja eco da voz dele).
const FALTA_PRA_RESPONDER = 1.5;
function eMinhaPergunta() {
  const voz = emAndamento?.voz;
  if (!voz?.falta) return false;
  const pergunta = !$("autorizacao").hidden || /\?\s*$/.test(voz.ultima() || "");
  return pergunta && voz.falta() <= FALTA_PRA_RESPONDER;
}
function respostaAntecipada(ultimo) {
  if (!eMinhaPergunta()) return false;
  const opcoes = [...ultimo].map((a) => a.transcript.trim());
  // tira do começo as palavras que são o fim da fala dele (o microfone pega a caixa de som)
  const fala = (emAndamento.voz.ultima() || "").toLowerCase();
  const limpo = (t) => t.toLowerCase().split(/\s+/).filter((w) => w && !fala.includes(w.replace(/[?.!,]/g, ""))).join(" ");
  const dito = opcoes.map(limpo).find((t) => t) || "";
  if (!dito) return false;
  if (!$("autorizacao").hidden) {
    const sim = SIM.test(dito), nao = NAO.test(dito);
    if (!sim && !nao) return false;
    interromper();
    decidir(sim);
    return true;
  }
  if (!ultimo.isFinal || ehEco(dito)) return false;
  interromper();
  perguntar(dito);
  return true;
}

function acabouDeFalar() {
  ultimaTroca = Date.now();
  // depois de uma pergunta a surdez é curtinha: a resposta dele vem rápido
  const perguntou = !$("autorizacao").hidden || /\?\s*$/.test(ultimasFalas[ultimasFalas.length - 1] || "");
  surdoAte = Date.now() + (perguntou ? 250 : 900);
  juntando.texto = "";
  clearTimeout(juntando.timer);
  if (rec && ligado) { rec.abort(); ligado = false; }
}

function fimDaFala() {
  let dito = juntando.texto.trim();
  const alternativas = juntando.alternativas;
  // como ele falou (volume, ritmo, tom, fim da frase subindo/descendo) — o 1 s de silêncio do fim fica de fora
  let tom = null;
  try { tom = window.entonacao?.resumo(juntando.inicio || performance.now() - 8000, performance.now() - 1000, dito.split(/\s+/).length); } catch {}
  juntando.inicio = 0;
  juntando.texto = "";
  $("texto").value = "";
  if (!dito || ocupado) return;
  if (!conversaAberta() && $("autorizacao").hidden && Date.now() - interrompidoEm >= 8000) {
    // em silêncio fazia tempo: sem "Jarvis" na frase, não é com ele
    if (!NOME.test(dito)) return;
    // o nome pode vir no começo, no meio ou no fim ("abre o VS Code, Jarvis"): vale a frase toda, sem o nome
    dito = dito.replace(new RegExp(NOME.source, "gi"), " ").replace(/\s+/g, " ").replace(/^[\s,.!?]+|[\s,.!?]+$/g, "");
    ultimaTroca = Date.now();
    if (!dito) {
      // só chamou: responde e fica escutando direto
      const voz = filaDeVoz();
      ocupado = true;
      emAndamento = { voz };
      voz.adicionar(sortear(CHAMADO));
      voz.terminar().then(() => { if (emAndamento?.voz === voz) { emAndamento = null; ocupado = false; acabouDeFalar(); ouvir(); } });
      return;
    }
  }
  ultimaTroca = Date.now();
  if (Date.now() - interrompidoEm < 8000) {
    // a frase da interrupção pode ter pego o fim da fala dele: vale só o que vem depois de "Jarvis"
    const depois = dito.split(NOME).pop().replace(/^[\s,.!]+/, "");
    if (NOME.test(dito)) dito = depois;
    if (!dito || /^(j[aá] )?(para|pare|chega|deu|espera|pera|calma|cala|quiet|xiu|shh|sil[eê]ncio|stop|ok|t[aá] bom|beleza|pode parar)/i.test(dito)) return;
  }
  if (!$("autorizacao").hidden) {
    // esperando confirmação: só "sim" ou "não" valem, o resto é ignorado
    if (SIM.test(dito)) decidir(true);
    else if (NAO.test(dito)) decidir(false);
    return;
  }
  perguntar(dito, alternativas, tom);
}

function ouvir() {
  if (!rec || mudo) {
    if (!rec) estado("", "Sem reconhecimento de voz aqui: use o Chrome ou o Edge");
    else estado("", micDoWindows ? AVISO_WINDOWS : "Microfone desligado");
    return;
  }
  if (!ligado) { try { rec.start(); ligado = true; } catch {} }
  if (!ocupado) estado("ouvindo", "Ouvindo");
}

function pararDeOuvir() {
  if (rec && ligado) { rec.abort(); ligado = false; }
}

$("nucleo").onclick = () => {
  if (surdo || micDoWindows) {
    // desmuta pelo clique: no Windows também, se foi mutado lá
    if (micDoWindows) fetch("/api/microfone", { method: "POST", headers: { "Content-Type": "application/json" },
                                                body: JSON.stringify({ mudo: false }) }).catch(() => {});
    aplicarMicrofone("ligado");
    return;
  }
  mudo = !mudo;
  document.body.classList.toggle("mudo", mudo);
  mudo ? (pararDeOuvir(), estado("", "Microfone desligado")) : voltarAEscutar();
};
$("digitar").onsubmit = (e) => { e.preventDefault(); perguntar($("texto").value); $("texto").value = ""; };
$("abrir-chat").onclick = () => {
  const abrir = $("digitar").hidden;
  $("digitar").hidden = !abrir;
  $("abrir-chat").setAttribute("aria-expanded", String(abrir));
  if (abrir) $("texto").focus();
};
addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("digitar").hidden) $("abrir-chat").click(); });
$("aut-sim").onclick = () => decidir(true);
$("aut-nao").onclick = () => decidir(false);

// respostas do Claude que chegaram enquanto ele fazia outra coisa: fala assim que estiver livre
setInterval(async () => {
  if (ocupado || document.hidden || !$("portao").hidden || !$("autorizacao").hidden) return;
  let blocos = [];
  try { ({ blocos } = await (await fetch("/api/novidades")).json()); } catch { return; }
  if (!blocos.length) return;
  await falarBlocos(blocos);
}, 4000);

// Fala uma sequência de blocos (abertura, avisos), mostrando cada cartão na hora; "Jarvis" interrompe.
async function falarBlocos(blocos) {
  ocupado = true;
  const voz = filaDeVoz();
  const meu = { voz };
  emAndamento = meu;
  for (const b of blocos) {
    voz.adicionar(b.fala, () => { if (b.fala) escrever(b.fala); if (b.cartao) mostrarCartao(b.cartao); });
    // varredura de segurança que achou falhas: abre o sim/não pra mandar o Claude corrigir (voz ou botão)
    if (b.pendente) voz.adicionar(b.pendente.fala || "Confirma, chefe? É só dizer sim ou não.", () => {
      $("aut-nome").textContent = b.pendente.nome.replace("_", " ");
      $("aut-args").textContent = Object.values(b.pendente.args).join("\n\n");
      $("autorizacao").hidden = false;
    });
  }
  ouvir();
  await voz.terminar();
  if (emAndamento !== meu) return;
  acabouDeFalar();
  emAndamento = null;
  ocupado = false;
  ouvir();
  if (!$("autorizacao").hidden) estado("ouvindo", "Diga sim ou não");
}

// avisa o servidor que a tela está aberta, para as palmas não abrirem outra
// minimizada (escondida) ela não escuta: o ouvido de segundo plano atende o "Jarvis" enquanto isso
const avisarQueEstouAqui = () => fetch("/api/sinal", { method: "POST", headers: { "Content-Type": "application/json" },
                                                    body: JSON.stringify({ visivel: !document.hidden, ouvido: saudeDoOuvido() }) }).catch(() => {});
setInterval(avisarQueEstouAqui, 2000);
avisarQueEstouAqui();
document.addEventListener("visibilitychange", () => {
  avisarQueEstouAqui();
  if (document.hidden) pararDeOuvir(); else if (!mudo) { acabouDeFalar(); ouvir(); }
});
// gesto vindo da webcam (gestos.py, via SSE): o HUD age aqui — punho para, joinha=sim, polegar baixo=não, mão aberta troca o modo
function aoGesto(g) {
  try { window.mostrarGesto && window.mostrarGesto(g); } catch (e) {}  // mostra o gesto no painel VISÃO
  if (g === "punho") { try { interromper(); } catch (e) {} fetch("/api/parar", { method: "POST" }).catch(() => {}); }
  else if (g === "sim" || g === "nao") { const a = document.getElementById("autorizacao"); const b = document.getElementById(g === "sim" ? "aut-sim" : "aut-nao"); if (a && !a.hidden && b) b.click(); }
  else if (g === "aberta") { aplicarVista(document.body.classList.contains("modo-foco") ? "completo" : "foco"); }
}

// pop-up fechado por voz ("fecha o pop-up da BMW") some daqui também
const doServidor = new EventSource("/api/extensao/eventos?canal=hud");
doServidor.onmessage = (m) => {
  const e = JSON.parse(m.data);
  if (e.gesto) return aoGesto(e.gesto);
  if (e.oficina) return window.abrirOficina && window.abrirOficina(e.oficina);   // bancada de montagem por gestos
  if (e.oficina_fechar) return window.fecharOficina && window.fecharOficina();
  if ("maos" in e) {   // cursores/arrastar (mao.js) + a bancada 3D quando estiver aberta
    if (window.aoMaos) window.aoMaos(e.maos);
    if (window.oficinaAtiva) window.oficinaMaos(e.maos);
    return;
  }
  if (e.remover) for (const id of e.remover) {
    const achado = cartoes.find((c) => c.el.dataset.id === id);
    if (achado) { cartoes.splice(cartoes.indexOf(achado), 1); achado.el.classList.add("saindo"); setTimeout(() => achado.el.remove(), 400); }
  }
  if (e.remover) setTimeout(() => desenharLigacoes(null), 450);
  if (e.cartao) mostrarCartao(e.cartao);
  if (e.painel) mostrarCartao({ id: e.painel.id, onde: "aqui", titulo: "Pesquisa", destaque: e.painel.titulo,
                                texto: e.painel.resumo, linhas: e.painel.topicos, imagens: e.painel.imagens.slice(0, 6).map((f) => f.url),
                                fontes: e.painel.fontes, rapido: false });
  if (e.destacar) {
    const c = document.querySelector(`[data-id="${e.destacar.id}"]`);
    if (c) c.querySelectorAll("li").forEach((li, i) => li.classList.toggle("lendo", i === e.destacar.i));
  }
  if (e.fechar_painel && cartoes.length) {
    const alvo = e.fechar_painel === "todos" ? [...cartoes] : [cartoes[cartoes.length - 1]];
    for (const a of alvo) { cartoes.splice(cartoes.indexOf(a), 1); a.el.classList.add("saindo"); setTimeout(() => a.el.remove(), 400); }
    setTimeout(() => desenharLigacoes(null), 450);
  }
  if (e.limpar_palco) {  // "limpa a tela": tira todos os cartões do HUD e fecha a página aberta, volta ao núcleo
    for (const a of [...cartoes]) { cartoes.splice(cartoes.indexOf(a), 1); a.el.classList.add("saindo"); setTimeout(() => a.el.remove(), 400); }
    setTimeout(() => desenharLigacoes(null), 450);
    document.getElementById("ph-fechar")?.click();
  }
  if (e.noticias) mostrarCartao({ id: e.noticias.id, onde: "aqui", titulo: `Notícias · ${e.noticias.tema}`,
    destaque: e.noticias.itens[0]?.titulo || "", imagens: e.noticias.itens.map((n) => n.imagem).filter(Boolean).slice(0, 4),
    linhas: e.noticias.itens.map((n, i) => `${i + 1}. ${n.titulo} (${n.fonte})`), rapido: false });
  if (e.pagina) abrirPaginaHud(e.pagina.url, e.pagina.titulo, null);
  if (e.leitura_pagina) abrirPaginaHud(null, e.leitura_pagina.titulo, e.leitura_pagina);
  if (e.fechar_painel || (e.remover && e.remover.includes($("pagina-hud")?.dataset.id))) fecharPaginaHud();
  if (e.plano) mostrarPlano(e.plano);
  if (e.passo && !emAndamento) passoNaLinhaDoTempo(e.passo);
  // o segundo plano ouviu "Jarvis" e a tela não reagiu: reanima o ouvido daqui
  if (e.reouvir && !mudo && !surdo) { criarReconhecimento(); vivoEm = Date.now(); setTimeout(ouvir, 300); }
};
setInterval(() => ($("relogio").textContent = new Date().toLocaleTimeString("pt-BR")), 1000);

(async () => {
  // PC novo: o assistente de instalação vem antes de tudo (só aparece se faltar algo essencial)
  if (window.assistenteDeInstalacao) await window.assistenteDeInstalacao();
  await verificarIdentidade();
  ocupado = true;
  // enquanto os dados da abertura carregam, "Jarvis" já interrompe: cancela a abertura e vai direto pro pedido
  const meu = { voz: { cancelar() {} }, controlador: new AbortController() };
  emAndamento = meu;
  ouvir();
  let blocos = [{ fala: "Todos os sistemas online, chefe. O que vamos fazer hoje?" }];
  // quem decide se é a 1ª abertura desde que o PC ligou é o servidor (resumo-falado.json). Antes a tela pedia a versão
  // curta sempre que o rosto já tinha sido conferido — e PC sem rosto (ou rosto conferido em outra janela) nunca ouvia
  // o "Todos os sistemas online" com os dados do dia.
  try { ({ blocos, sessao } = await (await fetch("/api/abertura", { signal: meu.controlador.signal })).json()); } catch {}
  if (emAndamento !== meu) return;
  // cada cartão aparece na hora em que o Jarvis começa a falar dele
  await falarBlocos(blocos);
})();

// ------------------------------------------------------------- barra lateral: o menu ao lado do nome recolhe Digitar/Automações/Configurações
(function () {
  const menu = document.getElementById("menu-jarvis");
  const barra = document.getElementById("barra");
  if (!menu || !barra) return;
  const fechar = () => { document.body.classList.remove("barra-aberta"); menu.setAttribute("aria-expanded", "false"); };
  menu.addEventListener("click", (e) => { e.stopPropagation(); const aberto = document.body.classList.toggle("barra-aberta"); menu.setAttribute("aria-expanded", aberto ? "true" : "false"); });
  document.addEventListener("click", (e) => { if (document.body.classList.contains("barra-aberta") && !barra.contains(e.target) && !menu.contains(e.target)) fechar(); });
  addEventListener("keydown", (e) => { if (e.key === "Escape") fechar(); });
  barra.querySelectorAll(".icone").forEach((b) => b.addEventListener("click", fechar)); // abrir uma ação já recolhe a barra
})();
