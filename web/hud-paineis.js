/* Painéis fixos do HUD (ref jarvis_hud.json): SISTEMA, REDE, VISÃO (stub), HOJE.
   Busca /api/hud a cada 2 s e preenche. Só no HUD grande (no celular eles ficam escondidos pelo CSS).
   Não mexe no núcleo nem nos cartões flutuantes; é uma camada a mais. */
(function () {
  const $ = (id) => document.getElementById(id);
  if (!$("hud-paineis")) return;
  document.body.classList.add("hud-on");

  const corpo = (id) => { const p = $(id); return p && p.querySelector(".corpo"); };
  const esc = (s) => String(s == null ? "" : s).replace(/[<>&]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[c]));

  // medidor horizontal com cor por limiar
  function gauge(label, val, un, warn, danger) {
    const nulo = val == null;
    const cls = nulo ? "" : val >= (danger ?? 101) ? "perigo" : val >= (warn ?? 101) ? "aviso" : "";
    const larg = nulo ? 0 : Math.min(100, Math.max(0, val));
    return `<div class="g ${cls}"><span class="gl">${label}</span><span class="gv">${nulo ? "—" : Math.round(val) + un}</span><b style="width:${larg}%"></b></div>`;
  }
  function linha(label, valor) { return `<div class="kv"><span>${label}</span><strong>${esc(valor)}</strong></div>`; }

  function pintarSistema(s) {
    const c = corpo("hp-sistema"); if (!c || !s) return;
    const bat = s.bateria ? `${s.bateria.pct}%${s.bateria.tomada ? " ⚡" : ""}` : "—";
    c.innerHTML =
      gauge("CPU", s.cpu, "%", 80, 95) +
      gauge("RAM", s.ram, "%", 80, 95) +
      gauge("GPU", s.gpu, "%", 85, 98) +
      gauge("DISCO", s.disco, "%", 90, 97) +
      linha("TEMP", s.temp == null ? "—" : s.temp + "°C") +
      linha("BATERIA", bat) +
      `<div class="sub">RAM ${s.ram_gb} / ${s.ram_total} GB</div>`;
  }

  function pintarRede(r) {
    const c = corpo("hp-rede"); if (!c || !r) return;
    c.innerHTML =
      linha("DOWNLOAD", r.down + " MB/s") +
      linha("UPLOAD", r.up + " MB/s") +
      linha("PING", r.ping == null ? "—" : r.ping + " ms") +
      linha("DISPOSITIVOS", r.dispositivos == null ? "escaneando…" : r.dispositivos);
    const n = $("radar-num"); if (n) n.textContent = r.dispositivos == null ? "" : r.dispositivos;
  }

  let noticias = [], iNot = 0;
  function pintarHoje(d) {
    const c = corpo("hp-hoje"); if (!c) return;
    const agora = new Date();
    const hora = agora.toLocaleTimeString("pt-BR");
    const dia = agora.toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "short" });
    let clima = "—";
    if (d && d.clima) clima = `${d.clima.temp}°C · ${d.clima.cond}` + (d.clima.chuva != null ? ` · ${d.clima.chuva}% chuva` : "");
    if (d && d.noticias && d.noticias.length) noticias = d.noticias;
    const noticia = noticias.length ? noticias[iNot % noticias.length] : "—";
    c.innerHTML =
      `<div class="relogio-g">${hora}</div><div class="data-g">${dia}</div>` +
      linha("CLIMA", clima) +
      `<div class="ticker" title="${esc(noticia)}">📰 ${esc(noticia)}</div>`;
  }

  function pintar(d) { pintarSistema(d.sistema); pintarRede(d.rede); pintarHoje(d); }

  async function tick() {
    try {
      const r = await fetch("/api/hud", { cache: "no-store" });
      pintar(await r.json());
    } catch (e) { /* offline: mantém o que tinha */ }
  }
  // relógio e rodízio de notícia andam a cada segundo; os dados pesados a cada 2 s
  setInterval(() => { iNot++; pintarHoje(window._hud || {}); }, 8000);
  setInterval(() => { const c = corpo("hp-hoje"); if (c) { const r = c.querySelector(".relogio-g"); if (r) r.textContent = new Date().toLocaleTimeString("pt-BR"); } }, 1000);
  async function loop() { try { const r = await fetch("/api/hud", { cache: "no-store" }); window._hud = await r.json(); pintar(window._hud); } catch {} }
  loop(); setInterval(loop, 2000);
})();
