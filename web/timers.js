// Timers e cronômetros na tela (timer.py): a contagem regressiva fica à vista enquanto roda, com ✕ pra cancelar.
// Mesmo arquivo no HUD, na janela da extensão e no celular: <script src="/web/timers.js" data-onde="hud|ext|cel">.
// Cada aparelho só vê os seus (os "2 Jarvis": o timer pedido no celular não aparece no PC).
(() => {
  const script = document.currentScript;
  const onde = script?.dataset.onde || "hud";
  if (new URLSearchParams(location.search).has("embutido")) return;  // o palco embutido não repete o que a página de fora mostra
  const origem = onde === "cel" ? "celular" : "pc";

  const css = document.createElement("style");
  css.textContent = `
  #timers { position: fixed; z-index: 40; display: grid; gap: 8px; pointer-events: none; font-family: "Segoe UI", system-ui, sans-serif; }
  #timers.hud { top: 56px; right: 32px; width: 230px; }
  #timers.ext { bottom: 24px; right: 24px; width: 220px; }
  #timers.cel { top: calc(env(safe-area-inset-top) + 52px); left: 50%; transform: translateX(-50%); width: min(260px, calc(100vw - 32px)); }
  #timers .tm { position: relative; pointer-events: auto; padding: 10px 34px 10px 14px; border: 1px solid var(--ciano-fraco, #39d0ff33);
    background: #06121dd9; backdrop-filter: blur(6px); border-radius: 4px; overflow: hidden; }
  #timers.cel .tm { border-radius: 12px; padding: 8px 34px 8px 12px; }
  #timers .tm .nome { font: 600 10px/1.3 Consolas, monospace; letter-spacing: .16em; text-transform: uppercase; color: var(--apagado, #6c8aa0);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  #timers .tm .tempo { font: 300 34px/1.1 "Segoe UI", system-ui, sans-serif; color: var(--ciano, #39d0ff); letter-spacing: .04em;
    font-variant-numeric: tabular-nums; text-shadow: 0 0 14px var(--ciano-fraco, #39d0ff33); }
  #timers.cel .tm .tempo { font-size: 28px; }
  #timers .tm .barra { position: absolute; left: 0; bottom: 0; height: 2px; background: var(--ciano, #39d0ff); box-shadow: 0 0 8px var(--ciano, #39d0ff);
    transition: width 1s linear; }
  #timers .tm button { position: absolute; top: 6px; right: 6px; width: 24px; height: 24px; padding: 0; border: 0; border-radius: 50%;
    background: transparent; color: var(--apagado, #6c8aa0); font-size: 14px; cursor: pointer; }
  #timers .tm button:hover { color: var(--ciano, #39d0ff); background: #39d0ff1a; }
  #timers .tm.pausado .tempo { opacity: .45; animation: tm-pulsa 1.4s ease-in-out infinite; }
  #timers .tm.fim10 .tempo { color: #ffb547; text-shadow: 0 0 14px #ffb54766; }
  #timers .tm.acabou { border-color: #ff6b4a; box-shadow: 0 0 30px #ff6b4a55; }
  #timers .tm.acabou .tempo { color: #ff6b4a; animation: tm-pulsa .6s ease-in-out infinite; }
  @keyframes tm-pulsa { 50% { opacity: .35; } }`;
  document.head.append(css);

  const caixa = document.createElement("aside");
  caixa.id = "timers";
  caixa.className = onde;
  caixa.setAttribute("aria-live", "polite");
  caixa.setAttribute("aria-label", "Timers");
  document.body.append(caixa);

  let lista = [], lidoEm = 0;
  const relogio = (seg) => {
    seg = Math.max(0, Math.ceil(seg));
    const h = Math.floor(seg / 3600), m = Math.floor((seg % 3600) / 60), s = seg % 60;
    const dd = (n) => String(n).padStart(2, "0");
    return h ? `${h}:${dd(m)}:${dd(s)}` : `${dd(m)}:${dd(s)}`;
  };

  async function ler() {
    try {
      const r = await (await fetch(`/api/timers?origem=${origem}`, { cache: "no-store" })).json();
      lista = r.timers || [];
      lidoEm = Date.now();
      desenhar();
    } catch {}
  }

  function cancelar(id) {
    lista = lista.filter((t) => t.id !== id);
    desenhar();
    fetch(`/api/timers/${id}`, { method: "DELETE" }).catch(() => {});
  }

  function desenhar() {
    const passou = (Date.now() - lidoEm) / 1000;
    const ids = new Set(lista.map((t) => t.id));
    for (const el of [...caixa.children]) if (!ids.has(el.dataset.id)) el.remove();
    for (const t of lista) {
      let el = caixa.querySelector(`[data-id="${t.id}"]`);
      if (!el) {
        el = document.createElement("div");
        el.className = "tm";
        el.dataset.id = t.id;
        el.innerHTML = `<div class="nome"></div><div class="tempo"></div><div class="barra"></div><button type="button" title="Cancelar" aria-label="Cancelar">✕</button>`;
        el.querySelector("button").onclick = () => cancelar(t.id);
        caixa.append(el);
      }
      const cron = t.tipo === "cronometro";
      const seg = cron ? t.decorrido + (t.pausado ? 0 : passou) : t.restante - (t.pausado || t.acabou ? 0 : passou);
      el.querySelector(".nome").textContent = (cron ? "Cronômetro" : "Timer") + (t.assunto ? ` · ${t.assunto}` : "") +
        (t.pausado ? " · pausado" : "") + (t.acabou ? " · acabou!" : "");
      el.querySelector(".tempo").textContent = relogio(Math.max(0, seg));
      el.querySelector(".barra").style.width = cron ? "0" : `${Math.max(0, Math.min(100, (seg / t.duracao) * 100))}%`;
      el.classList.toggle("pausado", !!t.pausado);
      el.classList.toggle("acabou", !!t.acabou || (!cron && seg <= 0));
      el.classList.toggle("fim10", !cron && seg > 0 && seg <= 10);
    }
  }

  setInterval(ler, 2000);
  setInterval(desenhar, 250);
  ler();
})();
