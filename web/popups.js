// Pop-ups com cara de tecnologia e sem ser tudo igual: cada cartão novo ganha um formato (chanfrado, cantoneiras,
// aba, moldura de scanner), uma entrada (zoom, desdobra, glitch, desliza, fade), um leve deslocamento da vaga e uma
// cor pelo que diz (vermelho = alerta/erro, laranja = números/uso, verde = feito, roxo = memória/aprendizado).
// Vale pra tela principal (HUD) e pra lateral/palco; só mexe em cartão que ainda não tem estilo.
(() => {
  const css = document.createElement("style");
  css.textContent = `
  .cartao.tom-alerta { --ciano: #ff3b3b; --ciano-fraco: #ff3b3b33; }
  .cartao.tom-dados  { --ciano: #ff9b3d; --ciano-fraco: #ff9b3d33; }
  .cartao.tom-ok     { --ciano: #2ee88a; --ciano-fraco: #2ee88a33; }
  .cartao.tom-mente  { --ciano: #c77dff; --ciano-fraco: #c77dff33; }
  .cartao.tom-ouro   { --ciano: #ffd23d; --ciano-fraco: #ffd23d33; }
  .cartao[class*="tom-"] { border-color: var(--ciano-fraco) !important; }
  .cartao[class*="tom-"] h3 { color: var(--ciano); opacity: .85; }

  .cartao.forma-1 { clip-path: polygon(16px 0, 100% 0, 100% calc(100% - 16px), calc(100% - 16px) 100%, 0 100%, 0 16px); }
  .cartao.forma-2 { border-color: transparent !important; background-image:
      linear-gradient(var(--ciano), var(--ciano)), linear-gradient(var(--ciano), var(--ciano)),
      linear-gradient(var(--ciano), var(--ciano)), linear-gradient(var(--ciano), var(--ciano)),
      linear-gradient(var(--ciano), var(--ciano)), linear-gradient(var(--ciano), var(--ciano)),
      linear-gradient(var(--ciano), var(--ciano)), linear-gradient(var(--ciano), var(--ciano)) !important;
    background-repeat: no-repeat !important;
    background-size: 18px 2px, 2px 18px, 18px 2px, 2px 18px, 18px 2px, 2px 18px, 18px 2px, 2px 18px !important;
    background-position: 0 0, 0 0, 100% 0, 100% 0, 0 100%, 0 100%, 100% 100%, 100% 100% !important;
    background-color: #06121dd9 !important; }
  .cartao.forma-2::before { display: none; }
  .cartao.forma-3 { border-radius: 0 18px 0 18px; }
  .cartao.forma-3 h3 { display: inline-block; padding: 2px 10px 2px 8px; margin-left: -8px; background: var(--ciano-fraco);
    clip-path: polygon(0 0, calc(100% - 10px) 0, 100% 50%, calc(100% - 10px) 100%, 0 100%); }
  .cartao.forma-4 { overflow: hidden; }
  .cartao.forma-4::after { content: ""; position: absolute; left: 0; right: 0; height: 40%; top: -40%; pointer-events: none;
    background: linear-gradient(transparent, var(--ciano-fraco), transparent); animation: pop-varre 3.6s linear infinite; }
  .cartao.forma-5 { clip-path: polygon(0 0, calc(100% - 28px) 0, 100% 28px, 100% 100%, 28px 100%, 0 calc(100% - 28px)); }
  .cartao.forma-5::after { content: ""; position: absolute; right: 4px; top: 4px; width: 20px; height: 20px; pointer-events: none;
    border-top: 2px solid var(--ciano); border-right: 2px solid var(--ciano); transform: skew(0); }

  .cartao.entra-zoom    { animation: pop-zoom .55s cubic-bezier(.2, 1.3, .4, 1) both !important; }
  .cartao.entra-desdobra{ animation: pop-desdobra .6s ease-out both !important; }
  .cartao.entra-glitch  { animation: pop-glitch .6s steps(2, end) both !important; }
  .cartao.entra-desliza { animation: pop-desliza .55s cubic-bezier(.2, .9, .3, 1) both !important; }
  .cartao.entra-fade    { animation: pop-fade .7s ease-out both !important; }
  @keyframes pop-zoom { from { opacity: 0; transform: scale(.3); filter: blur(8px) brightness(2.5); } }
  @keyframes pop-desdobra { from { opacity: 0; clip-path: inset(0 50% 0 50%); filter: brightness(2.5); } 60% { opacity: 1; } to { clip-path: inset(0 0 0 0); } }
  @keyframes pop-glitch { 0% { opacity: 0; transform: translate(-14px, 0) skewX(-12deg); filter: hue-rotate(90deg) brightness(2); }
    25% { opacity: 1; transform: translate(10px, 0) skewX(8deg); } 50% { transform: translate(-5px, 0); filter: none; } 75% { transform: translate(3px, 0); opacity: .7; } }
  @keyframes pop-desliza { from { opacity: 0; transform: translateX(var(--de, 60px)); filter: blur(4px); } }
  @keyframes pop-fade { from { opacity: 0; filter: blur(10px); } }
  @keyframes pop-varre { to { top: 100%; } }
  .cartao.saindo { animation: pop-sai .45s ease-in forwards !important; }
  @keyframes pop-sai { to { opacity: 0; transform: scale(.85); filter: blur(6px) brightness(2); clip-path: inset(48% 0 48% 0); } }
  /* X pra fechar na mão (pedido 25/10): longe dos cantos cortados de todas as formas */
  .cartao > .fechar-x { position: absolute; top: 6px; right: 36px; z-index: 5; width: 26px; height: 26px; padding: 0;
    border: 1px solid var(--ciano-fraco, #39d0ff44); background: #06121dcc; color: #8fb8cc; font: 16px/22px sans-serif;
    cursor: pointer; border-radius: 50%; transition: color .2s, border-color .2s, background .2s; pointer-events: auto; }
  .cartao > .fechar-x:hover { color: #fff; border-color: #ff5a6a; background: #ff5a6a33; }
  .cartao > h3:first-of-type { padding-right: 60px; }

  /* ---------- VISUAL MODERNO (pedido 25/10: "o design dos popups poderia ser mais moderno")
     vidro fosco arredondado + borda em gradiente que acende nos cantos + linha de luz no topo + sombra macia.
     A cor de destaque continua vindo do assunto (--ciano: alerta vermelho, dinheiro dourado...). ".cartao.cartao" =
     mais forte que o CSS antigo das duas telas, sem precisar de !important (as posições do HUD continuam as dele). */
  .cartao.cartao { border-radius: 16px; clip-path: none; border: 1px solid transparent;
    background:
      linear-gradient(160deg, rgba(16, 40, 62, .80), rgba(5, 13, 23, .90)) padding-box,
      linear-gradient(140deg, color-mix(in srgb, var(--ciano) 75%, transparent), rgba(57, 208, 255, .07) 32%,
        rgba(57, 208, 255, .07) 68%, color-mix(in srgb, var(--ciano) 45%, transparent)) border-box;
    backdrop-filter: blur(14px) saturate(140%);
    box-shadow: 0 22px 50px -16px rgba(0, 0, 0, .7), inset 0 1px 0 rgba(255, 255, 255, .06),
      0 0 34px -14px var(--ciano);
    transition: box-shadow .25s; }
  .cartao.cartao:hover { box-shadow: 0 26px 60px -16px rgba(0, 0, 0, .75), inset 0 1px 0 rgba(255, 255, 255, .08),
      0 0 46px -10px var(--ciano); }
  .cartao.cartao::before { left: 18px; right: 18px; top: -1px; width: auto; height: 1px; border-radius: 1px;
    background: linear-gradient(90deg, transparent, var(--ciano), transparent); box-shadow: 0 0 14px var(--ciano); opacity: .9; }
  .cartao.cartao > h3 { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; letter-spacing: .16em;
    color: color-mix(in srgb, var(--ciano) 70%, #fff); opacity: .9; }
  .cartao.cartao > h3::before { content: ""; flex: none; width: 6px; height: 6px; border-radius: 50%;
    background: var(--ciano); box-shadow: 0 0 10px var(--ciano); }
  .cartao.cartao .destaque { font-weight: 600; letter-spacing: -.01em; color: #fff;
    text-shadow: 0 0 18px color-mix(in srgb, var(--ciano) 55%, transparent); }
  .cartao.cartao li { border-top-color: rgba(255, 255, 255, .06); }
  .cartao.cartao .galeria img, .cartao.cartao pre, .cartao.cartao iframe { border-radius: 10px; }
  .cartao.cartao .galeria img { border-color: rgba(255, 255, 255, .08); }
  .cartao.cartao .some { left: 16px; right: 16px; border-radius: 2px; }
  .cartao.cartao.aguardando { opacity: .8; border-style: dashed; }
  body.caverna .cartao.cartao { background: linear-gradient(160deg, rgba(40, 6, 6, .85), rgba(10, 0, 0, .92)) padding-box,
      linear-gradient(140deg, #ff3b3bbb, #ff3b3b11 40%, #ff3b3b11 60%, #ff3b3b88) border-box; }
  body.leve .cartao.cartao { backdrop-filter: none; }
  .cartao.entra-surge { animation: pop-surge .6s cubic-bezier(.2, 1.1, .3, 1) both !important; }
  @keyframes pop-surge { from { opacity: 0; transform: translateY(12px) scale(.96); filter: blur(8px); } }`;
  document.head.append(css);

  // entrada macia (o "glitch" e o "desdobra" pareciam antigos); a forma sorteada (chanfros) saiu pelo visual novo
  const ENTRADAS = ["entra-surge", "entra-surge", "entra-desliza", "entra-fade"];
  const sorteia = (l) => l[Math.floor(Math.random() * l.length)];
  function tom(c) {
    const t = (c.textContent || "").toLowerCase();
    if (/\b(erro|falh|alerta|aten[cç][aã]o|cr[ií]tic|cuidado|n[aã]o consegui|perigo|cheio|terremoto)/.test(t)) return "tom-alerta";
    if (/\b(mem[oó]ri[ao]|aprend|habilidade|lembr|neural)/.test(t)) return "tom-mente";
    if (/\b(feito|pronto|conclu|sucesso|enviad|salv|gravad|ok)\b/.test(t)) return "tom-ok";
    if (/\b(r\$|cota[cç]|d[oó]lar|bitcoin|pre[cç]o|valor)/.test(t)) return "tom-ouro";
    if (/\d+\s*(%|gb|mb|ghz|mhz|°|km|ms)\b/.test(t)) return "tom-dados";
    return "";  // sem assunto claro: fica no ciano do Jarvis (cor sorteada parecia aleatória demais)
  }
  function estilizar(c) {
    if (c.dataset.estilo || c.classList.contains("radar-painel") || c.classList.contains("noticias")) return;
    c.dataset.estilo = "1";
    const t = tom(c); if (t) c.classList.add(t);
    const ent = sorteia(ENTRADAS);
    c.style.setProperty("--de", (c.classList.contains("v1") || c.classList.contains("v3") || c.classList.contains("v5") ? -60 : 60) + "px");
    c.classList.add(ent);
    // na tela principal, cada cartão cai num ponto um pouco diferente da vaga (e um pouco maior ou menor)
    if (/\bv[0-5]\b/.test(c.className)) {
      c.style.marginTop = Math.round((Math.random() - 0.5) * 6) + "vh";
      c.style.marginLeft = c.style.marginRight = Math.round((Math.random() - 0.5) * 3) + "vw";
      c.style.width = `min(${300 + Math.round(Math.random() * 90)}px, ${24 + Math.round(Math.random() * 6)}vw)`;
    }
    setTimeout(() => c.classList.remove(ent), 900);  // a animação de saída não briga com a de entrada
    // o texto pode chegar depois (pop-up "aguardando"): reavalia a cor uma vez
    setTimeout(() => { if (!/tom-/.test(c.className)) { const t2 = tom(c); if (t2) c.classList.add(t2); } }, 1500);
  }
  // X em todo pop-up: fecha na mão. Painel ao vivo fechado no X avisa o servidor, que para de consultar o site
  // (e a eleição para de falar). Na lateral/palco usa o remover() de lá (lembra que fechou); no HUD só some.
  function botarX(c) {
    if (c.querySelector(":scope > .fechar-x")) return;
    const x = document.createElement("button");
    x.className = "fechar-x"; x.textContent = "×"; x.title = "Fechar";
    x.onclick = (ev) => {
      ev.stopPropagation();
      const id = c.dataset.id || (c.dataset.id = "mao-" + Math.random().toString(36).slice(2));
      if (id.startsWith("vivo-")) fetch("/api/vivo/fechar?id=" + encodeURIComponent(id), { method: "POST" }).catch(() => {});
      if (typeof window.remover === "function") return window.remover([id]);
      c.classList.add("saindo");
      setTimeout(() => c.remove(), 450);
    };
    c.append(x);
  }
  new MutationObserver((ms) => {
    for (const m of ms) for (const n of m.addedNodes) {
      if (n.nodeType !== 1 || n.closest(".fantasma-tela") || n.classList.contains("fantasma-tela")) continue;  // cópia de arrastar: não mexe
      if (n.classList?.contains("cartao")) { estilizar(n); botarX(n); }
      n.querySelectorAll?.(".cartao").forEach((c) => { estilizar(c); botarX(c); });
    }
  }).observe(document.body, { childList: true, subtree: true });
  document.querySelectorAll(".cartao").forEach(botarX);
})();

// ------------------------------------------------------------ arrastar entre as telas IGUAL AO WINDOWS (25/10)
// Pedido dele: "enquanto some de um lado aparece no outro". As telas são janelas separadas, então:
//  - a tela de onde o popup sai manda a posição dele NA ÁREA DE TRABALHO (screenX/screenY: o mesmo sistema de
//    coordenadas do Windows, que já sabe que a tela 1 fica à esquerda da 2) pro servidor, umas 30 vezes por segundo;
//  - a outra tela desenha uma cópia ("fantasma") no mesmo ponto: a parte que passou da borda aparece lá;
//  - soltou com o mouse já na outra tela → o popup muda de tela de verdade (/api/mover_item). Soltou na mesma → volta.
window.travessia = (() => {
  const EU = Math.random().toString(36).slice(2);
  const TOPO = window.top === window;
  let arraste = null, ultimoEnvio = 0, pendente = null;

  const mandar = (msg) => fetch("/api/arraste", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...msg, de: EU, topo: TOPO }) }).catch(() => {});

  // retângulo da janela inteira na área de trabalho (no palco, que é um iframe, é a janela do HUD em volta dele)
  function minhaTela(e) {
    const ox = e.screenX - e.clientX, oy = e.screenY - e.clientY;  // canto de cima/esquerda desta página no Windows
    if (TOPO) return { x: ox, y: oy, w: innerWidth, h: innerHeight };
    const r = frameElement.getBoundingClientRect();
    return { x: ox - r.left, y: oy - r.top, w: top.innerWidth, h: top.innerHeight };
  }
  const dentro = (t, x, y) => x >= t.x && x < t.x + t.w && y >= t.y && y < t.y + t.h;

  // cópia com a cara EXATA de agora: cada parte (título, selo, rodapé, quadro do painel) leva o próprio estilo junto,
  // senão o CSS da outra tela muda margens e o conteúdo fica mais alto/baixo de um lado que do outro (medido 25/10)
  const PROPS = ["display", "position", "box-sizing", "width", "height", "margin", "padding", "border", "border-radius",
    "background", "color", "font", "line-height", "letter-spacing", "text-transform", "text-align", "white-space",
    "clip-path", "box-shadow", "opacity", "gap", "grid-template-columns", "flex-direction", "align-items", "justify-content",
    "overflow", "left", "top", "right", "bottom", "backdrop-filter"];
  function copiaFiel(el) {
    const copia = el.cloneNode(true);
    const orig = [el, ...el.querySelectorAll("*")], novos = [copia, ...copia.querySelectorAll("*")];
    orig.forEach((o, i) => {
      const cs = getComputedStyle(o), n = novos[i];
      if (!n || !n.style) return;
      for (const p of PROPS) n.style.setProperty(p, cs.getPropertyValue(p));
      n.style.animation = "none"; n.style.transition = "none";
    });
    copia.style.transform = "none"; copia.style.margin = "0"; copia.style.position = "relative";
    copia.style.left = copia.style.top = "0"; copia.style.opacity = "1";
    copia.querySelector(":scope > .fechar-x")?.remove();
    // o quadro do painel ao vivo não é recarregado do outro lado (demora e vinha vazio): vira um espaço do mesmo
    // tamanho onde a "foto" pronta dele (números e fotos já no lugar) é desenhada
    copia.querySelectorAll("iframe").forEach((fr) => {
      const vaga = document.createElement("div");
      vaga.setAttribute("data-foto-quadro", "");
      vaga.style.cssText = fr.style.cssText + ";overflow:hidden";
      fr.replaceWith(vaga);
    });
    return copia;
  }

  // x0/y0 = onde ele APERTOU (o card ainda não andou nessa hora): a pegada no card fica exata, sem os 8 px do início
  function inicio(el, e, x0 = e.clientX, y0 = e.clientY) {
    const r = el.getBoundingClientRect();
    const tela = minhaTela(e);
    const copia = copiaFiel(el);
    arraste = { id: el.dataset.id || "", px: x0 - r.left, py: y0 - r.top, tela };
    // no palco (quadro no meio do HUD) o original seria cortado na borda do quadro: quem desenha é o HUD, por cima
    if (!TOPO) el.style.opacity = "0";
    mandar({ acao: "inicio", id: arraste.id, html: copia.outerHTML, w: r.width, h: r.height, tela, dados: el.__dados || null, foto: el.__foto || null });
  }

  function mover(el, e) {
    if (!arraste) return false;
    const msg = { acao: "mover", id: arraste.id, x: e.screenX - arraste.px, y: e.screenY - arraste.py, tela: arraste.tela };
    const agora = performance.now();
    if (agora - ultimoEnvio > 33) { ultimoEnvio = agora; mandar(msg); pendente = null; }
    else pendente = msg;  // o último ponto sempre chega (no fim)
    return !dentro(arraste.tela, e.screenX, e.screenY);  // true = o mouse já está na outra tela
  }

  function fim(el, e) {
    if (!arraste) return false;
    if (pendente) mandar(pendente);
    const fora = !dentro(arraste.tela, e.screenX, e.screenY);
    mandar({ acao: "fim", id: arraste.id, fora, tela: arraste.tela });
    arraste = pendente = null;
    return fora;
  }

  // COM A MÃO (gestos): a câmera só cobre esta tela, então segurou o card e encostou a mão na borda do lado da
  // outra tela → o card DESLIZA reto (mesma altura) pra lá, aparecendo do outro lado enquanto passa, e fica lá.
  // de = "palco" | "hud" (pro servidor saber de onde sai); dado = o cartão do HUD (que não fica guardado no servidor)
  function deslizar(el, lado, de, dado) {
    const r = el.getBoundingClientRect();
    const canto = TOPO ? { x: screenX, y: screenY }
      : (() => { const f = frameElement.getBoundingClientRect(); return { x: top.screenX + f.left, y: top.screenY + f.top }; })();
    const tela = TOPO ? { x: screenX, y: screenY, w: innerWidth, h: innerHeight }
      : { x: top.screenX, y: top.screenY, w: top.innerWidth, h: top.innerHeight };
    const x0 = canto.x + r.left, y = canto.y + r.top;
    const alvo = lado < 0 ? tela.x - r.width - 60 : tela.x + tela.w + 60;  // inteiro do outro lado da borda
    arraste = { id: el.dataset.id || "", tela };
    mandar({ acao: "inicio", id: arraste.id, html: copiaFiel(el).outerHTML, w: r.width, h: r.height, tela, dados: el.__dados || null, foto: el.__foto || null });
    el.style.opacity = "0";  // daqui pra frente quem aparece é a cópia que desliza (nas duas telas)
    const t0 = performance.now(), dur = 700;
    return new Promise((pronto) => {
      const passo = () => {
        const p = Math.min(1, (performance.now() - t0) / dur), k = 1 - Math.pow(1 - p, 3);
        mandar({ acao: "mover", id: arraste.id, x: Math.round(x0 + (alvo - x0) * k), y, tela });
        if (p < 1) return setTimeout(passo, 33);
        mandar({ acao: "fim", id: arraste.id, fora: true, tela });
        arraste = null;
        fetch("/api/mover_item", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: el.dataset.id || "", de, dado: dado || null }) })
          .then((x) => x.json()).then((j) => pronto(!!j.ok)).catch(() => pronto(false));
      };
      passo();
    });
  }

  // ---- quem RECEBE: só a janela de cima de cada tela (o palco usa a do HUD) e nunca o celular
  if (TOPO && !/celular/.test(location.search)) {
    const css = document.createElement("style");
    css.textContent = `.fantasma-tela { position: fixed; z-index: 99999; pointer-events: none; opacity: .95; transition: none;
      box-sizing: border-box; overflow: hidden; }
      .fantasma-tela.sumindo { transition: opacity .5s; opacity: 0; }`;
    document.head.append(css);
    const fantasmas = {};
    // SEGURANÇA: a "foto" do painel vem do quadro isolado onde roda HTML que o cérebro escreveu. Antes de pôr na página
    // do Jarvis, monta num <template> (lá nada roda) e tira tudo que executa: scripts, quadros, links externos,
    // atributos on... (onerror=, onload=) e endereços javascript:
    function limpo(html) {
      const t = document.createElement("template");
      t.innerHTML = String(html || "");
      t.content.querySelectorAll("script, iframe, frame, object, embed, link, meta, base, form, noscript").forEach((n) => n.remove());
      t.content.querySelectorAll("*").forEach((n) => {
        for (const a of [...n.attributes]) {
          const nome = a.name.toLowerCase(), valor = a.value.replace(/\s+/g, "").toLowerCase();
          if (nome.startsWith("on") || (/^(href|src|xlink:href|action|formaction|srcdoc)$/.test(nome) && valor.startsWith("javascript:")))
            n.removeAttribute(a.name);
        }
      });
      return t.content;
    }
    // onde fica o canto desta janela no Windows (janela sem barra: o Jarvis abre em tela cheia)
    const meuCanto = () => ({ x: screenX + (outerWidth - innerWidth) / 2, y: screenY + (outerHeight - innerHeight) });
    const mesmaTela = (t) => t && Math.abs(t.x - meuCanto().x) < 40 && Math.abs(t.y - meuCanto().y) < 80 && Math.abs(t.w - innerWidth) < 40;
    const fonte = new EventSource("/api/extensao/eventos?canal=arraste");
    fonte.onmessage = (m) => {
      let d; try { d = JSON.parse(m.data); } catch { return; }
      if (d.de === EU || (d.topo && mesmaTela(d.tela))) return;  // a própria tela já mostra o original
      const chave = d.de + d.id;
      if (d.acao === "inicio") {
        fantasmas[chave]?.remove();
        const f = document.createElement("div");
        f.className = "fantasma-tela"; f.style.width = d.w + "px"; f.style.height = d.h + "px"; f.style.left = "-9999px";
        // dentro de uma "sombra" (shadow DOM): o CSS desta tela não mexe na cópia → fica idêntica nas duas telas
        const sombra = f.attachShadow({ mode: "open" });
        sombra.append(limpo(d.html));
        const vaga = sombra.querySelector("[data-foto-quadro]");  // painel ao vivo: a "foto" com números e fotos
        if (vaga && d.foto) vaga.attachShadow({ mode: "open" }).append(limpo(d.foto));
        document.body.append(f);
        fantasmas[chave] = f;
      } else if (d.acao === "mover" && fantasmas[chave]) {
        const c = meuCanto();
        fantasmas[chave].style.left = (d.x - c.x) + "px";
        fantasmas[chave].style.top = (d.y - c.y) + "px";
      } else if (d.acao === "fim" && fantasmas[chave]) {
        const f = fantasmas[chave]; delete fantasmas[chave];
        if (!d.fora) return f.remove();
        // soltou aqui: o popup de verdade chega em instantes pelo servidor; o fantasma some devagar por cima
        setTimeout(() => { f.classList.add("sumindo"); setTimeout(() => f.remove(), 550); }, 350);
      }
    };
  }
  return { inicio, mover, fim, deslizar };
})();
