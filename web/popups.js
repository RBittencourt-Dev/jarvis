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
  @keyframes pop-sai { to { opacity: 0; transform: scale(.85); filter: blur(6px) brightness(2); clip-path: inset(48% 0 48% 0); } }`;
  document.head.append(css);

  const ENTRADAS = ["entra-zoom", "entra-desdobra", "entra-glitch", "entra-desliza", "entra-fade"];
  const sorteia = (l) => l[Math.floor(Math.random() * l.length)];
  function tom(c) {
    const t = (c.textContent || "").toLowerCase();
    if (/\b(erro|falh|alerta|aten[cç][aã]o|cr[ií]tic|cuidado|n[aã]o consegui|perigo|cheio|terremoto)/.test(t)) return "tom-alerta";
    if (/\b(mem[oó]ri[ao]|aprend|habilidade|lembr|neural)/.test(t)) return "tom-mente";
    if (/\b(feito|pronto|conclu|sucesso|enviad|salv|gravad|ok)\b/.test(t)) return "tom-ok";
    if (/\b(r\$|cota[cç]|d[oó]lar|bitcoin|pre[cç]o|valor)/.test(t)) return "tom-ouro";
    if (/\d+\s*(%|gb|mb|ghz|mhz|°|km|ms)\b/.test(t)) return "tom-dados";
    return Math.random() < 0.3 ? sorteia(["tom-dados", "tom-mente", "tom-ouro"]) : "";
  }
  function estilizar(c) {
    if (c.dataset.estilo || c.classList.contains("radar-painel") || c.classList.contains("noticias")) return;
    c.dataset.estilo = "1";
    const forma = Math.floor(Math.random() * 6);  // 0 = o padrão
    if (forma) c.classList.add("forma-" + forma);
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
  new MutationObserver((ms) => {
    for (const m of ms) for (const n of m.addedNodes) {
      if (n.nodeType !== 1) continue;
      if (n.classList?.contains("cartao")) estilizar(n);
      n.querySelectorAll?.(".cartao").forEach(estilizar);
    }
  }).observe(document.body, { childList: true, subtree: true });
})();
