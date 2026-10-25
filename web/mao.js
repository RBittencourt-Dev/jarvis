/* Controle por mão(s) na tela principal. gestos.py transmite {maos:[{id,x,y,pinca}]} pelo canal "hud".
   Cada mão tem id ESTÁVEL (slot 0/1 casado por proximidade no servidor), então o cursor não troca de mão.
   PINÇAR agarra o cartão mais próximo, arrasta e, ao soltar, o cartão FICA onde largou. Duas mãos = dois cursores.
   Suavização: EMA por cursor. Só mexe no DOM (leve). [VERSÃO ESTÁVEL confirmada funcionando] */
(function () {
  const COR = { 0: "#00e5ff", 1: "#ffb000" };  // mão 0 = ciano, mão 1 = âmbar
  const A = 0.45;                              // suavização (EMA)
  const EH_TOPO = (window.self === window.top); // só o doc de cima MOSTRA o cursor; o do iframe fica invisível e só agarra
  const sty = document.createElement("style");
  sty.textContent = `
    .mao-cursor{position:fixed;left:0;top:0;width:22px;height:22px;margin:-11px 0 0 -11px;border:2px solid #00e5ff;
      border-radius:50%;box-shadow:0 0 10px #00e5ff,inset 0 0 6px rgba(0,229,255,.5);pointer-events:none;z-index:99999;
      display:none;transition:width .06s,height .06s,background .06s}
    .mao-cursor::after{content:"";position:absolute;left:50%;top:50%;width:4px;height:4px;margin:-2px 0 0 -2px;
      border-radius:50%;background:currentColor;box-shadow:0 0 6px currentColor}
    .mao-cursor.pinca{width:14px;height:14px;margin:-7px 0 0 -7px;background:rgba(255,255,255,.18)}
    .cartao.mao-arrastando{outline:2px solid #00e5ff;outline-offset:3px;filter:drop-shadow(0 0 16px rgba(0,229,255,.6))}
  `;
  document.head.appendChild(sty);

  const cursores = new Map();

  function novoCursor(id) {
    const el = document.createElement("div");
    el.className = "mao-cursor";
    const cor = COR[id] || "#00e5ff";
    el.style.color = cor; el.style.borderColor = cor; el.style.boxShadow = `0 0 14px ${cor},inset 0 0 8px ${cor}88`;
    document.body.appendChild(el);
    const c = { el, sx: null, sy: null, agarrado: null, gx0: 0, gy0: 0, base: { x: 0, y: 0 }, pincAnt: false };
    cursores.set(id, c);
    return c;
  }
  function lerOff(el) {
    const t = (el.style.transform || "").match(/translate\(\s*([-\d.]+)px\s*,\s*([-\d.]+)px\s*\)/);
    return t ? { x: +t[1], y: +t[2] } : { x: 0, y: 0 };
  }
  function agarrar(c, x, y) {
    let perto = null, melhor = 1e9;
    for (const el of document.querySelectorAll(".cartao")) {
      if (el.__pego != null) continue;
      const r = el.getBoundingClientRect();
      if (r.width === 0) continue;
      const dentro = x >= r.left && x <= r.right && y >= r.top && y <= r.bottom;
      const d = dentro ? -1 : Math.hypot(r.left + r.width / 2 - x, r.top + r.height / 2 - y);
      if (d < melhor) { melhor = d; perto = el; }
    }
    if (!perto) return;
    c.agarrado = perto; c.gx0 = x; c.gy0 = y; c.base = lerOff(perto);
    perto.__pego = c; perto.classList.add("mao-arrastando");
  }
  // passar pra outra tela com a mão (25/10): a câmera só cobre ESTA tela, então segurando o card e encostando a mão
  // na borda do lado da outra tela (no PC dele a tela 1 fica à ESQUERDA) o card desliza reto pra lá e fica lá
  const LADO_DA_OUTRA_TELA = -1;  // -1 = esquerda, 1 = direita
  function arrastar(c, x, y) {
    if (!c.agarrado || c.agarrado.__indo) return;
    c.agarrado.style.transform = `translate(${c.base.x + (x - c.gx0)}px, ${c.base.y + (y - c.gy0)}px)`;
    const naBorda = LADO_DA_OUTRA_TELA < 0 ? x < innerWidth * 0.025 : x > innerWidth * 0.975;
    if (naBorda && window.travessia?.deslizar) {
      const el = c.agarrado;
      el.__indo = true;
      soltar(c);
      window.travessia.deslizar(el, LADO_DA_OUTRA_TELA, EH_TOPO ? "hud" : "palco", el.__dado).then((ok) => {
        el.__indo = false;
        if (!ok) { el.style.opacity = ""; el.style.transform = ""; return; }  // não deu: volta pro lugar
        if (EH_TOPO && typeof cartoes !== "undefined") {  // cartão do HUD: sai da lista dele (o servidor já mostrou na outra)
          const achado = cartoes.find((k) => k.el === el); if (achado) cartoes.splice(cartoes.indexOf(achado), 1);
          el.remove();
        }
      });
    }
  }
  function soltar(c) {
    if (!c.agarrado) return;
    c.agarrado.classList.remove("mao-arrastando"); c.agarrado.__pego = null; c.agarrado = null;
    try { window.desenharLigacoes && window.desenharLigacoes(null); } catch (e) {}
  }
  function clicar(x, y) {   // pinça rápida = clique no que está sob o cursor (botões, fechar, fotos…)
    const alvo = document.elementFromPoint(x, y);
    if (!alvo) return;
    const o = { bubbles: true, cancelable: true, clientX: x, clientY: y, view: window };
    alvo.dispatchEvent(new MouseEvent("mousedown", o));
    alvo.dispatchEvent(new MouseEvent("mouseup", o));
    alvo.dispatchEvent(new MouseEvent("click", o));
  }

  window.aoMaos = function (lista) {
    const vivos = new Set();
    for (const m of (lista || [])) {
      vivos.add(m.id);
      const c = cursores.get(m.id) || novoCursor(m.id);
      c.el.style.display = EH_TOPO ? "block" : "none";   // um cursor só (o de cima); o do iframe só agarra
      const px = m.x * innerWidth, py = m.y * innerHeight;
      c.sx = c.sx == null ? px : c.sx + (px - c.sx) * A;
      c.sy = c.sy == null ? py : c.sy + (py - c.sy) * A;
      c.el.style.left = c.sx + "px"; c.el.style.top = c.sy + "px";
      c.el.classList.toggle("pinca", !!m.pinca);
      const palco = EH_TOPO && document.body.classList.contains("palco-ativo");  // com popup aberto, quem age é o iframe
      if (m.pinca && !c.pincAnt) { c.t0 = performance.now(); c.x0 = c.sx; c.y0 = c.sy; if (!palco) agarrar(c, c.sx, c.sy); }
      else if (!m.pinca && c.pincAnt) {
        const rapido = (performance.now() - c.t0 < 320) && Math.hypot(c.sx - c.x0, c.sy - c.y0) < 18;  // pinça rápida sem arrastar = clique
        soltar(c);
        if (rapido && !palco) clicar(c.sx, c.sy);
      }
      else if (m.pinca && c.agarrado) arrastar(c, c.sx, c.sy);
      c.pincAnt = !!m.pinca;
    }
    for (const [id, c] of cursores) if (!vivos.has(id)) { soltar(c); c.el.style.display = "none"; c.sx = c.sy = null; c.pincAnt = false; }
  };

  window.aoMao = function (m) { window.aoMaos(m ? [{ id: 0, x: m.x, y: m.y, pinca: m.pinca }] : []); };
  console.log("[mao.js] v10 pronto — tracking na tela principal");
  const _orig = window.aoMaos;
  window.aoMaos = function (l) { if (!window.__maoLog) { window.__maoLog = 1; console.log("[mao.js] recebendo mãos:", JSON.stringify(l)); } return _orig(l); };
})();
