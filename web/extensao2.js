// Extensão, parte 2 (21/10): painel de pesquisa, modo leitura, lupa, linha do tempo, animações de estado e o
// Olho de Deus (aviões voando ao vivo, satélites, terremotos, clima e manchetes). Usa o globo e as funções da
// parte 1 (extensao.html): globo, cartao, lista, remover, podar, atualizarEstado, sons, CASA, $.
(() => {
  const estilo = document.createElement("style");
  estilo.textContent = `
  .painel-pesquisa { padding: 0; }
  .painel-pesquisa .pp-topo { display: flex; align-items: center; gap: 8px; padding: 16px 18px 0; }
  .painel-pesquisa .pp-topo h3 { flex: 1; margin: 0; }
  .pp-botao { background: transparent; color: var(--apagado); border: 1px solid var(--ciano-fraco); padding: 3px 9px; font-size: 12px; cursor: pointer; }
  .pp-botao:hover, .fixo .pp-fixar { color: var(--ciano); border-color: var(--ciano); }
  .painel-pesquisa .destaque { padding: 4px 18px 0; }
  .pp-resumo { margin: 8px 18px 0; font-size: 17px; transition: color .3s, text-shadow .3s; }
  .pp-topicos { margin: 10px 18px 0; padding-left: 20px; font-size: 16px; display: grid; gap: 6px; }
  .pp-topicos li { transition: color .3s, text-shadow .3s, transform .3s; }
  .lendo { color: var(--ciano) !important; text-shadow: 0 0 12px var(--ciano-fraco); transform: translateX(4px); }
  .painel-pesquisa .galeria { padding: 0 18px; }
  .painel-pesquisa figure { margin: 0; position: relative; }
  .painel-pesquisa figcaption { position: absolute; left: 0; right: 0; bottom: 0; padding: 4px 6px; font-size: 10px; color: #fffc;
    background: linear-gradient(transparent, #000c); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .pp-fontes { margin: 12px 18px 16px; padding: 0; list-style: none; font-size: 13px; display: grid; gap: 4px; }
  .pp-fontes li { display: flex; gap: 8px; align-items: baseline; }
  .pp-fontes a { color: var(--ciano); cursor: pointer; flex: 1; }
  .pp-fontes .n { color: var(--apagado); font: 11px Consolas, monospace; }
  .cartao.fixo { border-color: var(--ciano); }
  .cartao pre { margin: 10px 0 0; max-height: 46vh; overflow: auto; font: 12px/1.45 Consolas, monospace; background: #0009; border: 1px solid #39d0ff1f; }
  .cartao pre code { display: block; padding: 10px; background: transparent !important; }
  .cartao pre.saida { padding: 8px 10px; color: #b8f5d0; white-space: pre-wrap; } .cartao pre.saida.erro { color: #ff6b4a; }

  #leitor { position: fixed; z-index: 7; left: 16px; right: 16px; top: 60px; bottom: 24px; display: none; flex-direction: column;
    border: 1px solid var(--ciano); background: #020a12f5; box-shadow: 0 0 50px var(--ciano-fraco); animation: surge .4s cubic-bezier(.2,.9,.3,1.2); }
  body.lendo-pagina #leitor { display: flex; }
  #leitor header { position: static; pointer-events: auto; padding: 10px 14px; border-bottom: 1px solid var(--ciano-fraco); gap: 8px; }
  #leitor .conteudo { flex: 1; overflow-y: auto; padding: 18px 26px 40px; font-size: 18px; line-height: 1.65; }
  #leitor .conteudo h2 { font-size: 22px; color: var(--ciano); font-weight: 400; margin: 18px 0 6px; }
  #leitor .conteudo p { margin: 0 0 12px; }

  #lupa-ext { position: fixed; z-index: 30; inset: 0; display: none; place-items: center; align-content: center; gap: 10px; background: #000e; cursor: zoom-out; }
  #lupa-ext.aberta { display: grid; }
  #lupa-ext img { max-width: 94vw; max-height: 80vh; border: 1px solid var(--ciano); box-shadow: 0 0 60px var(--ciano-fraco); animation: surge .3s ease-out both; }
  #lupa-ext p { margin: 0; color: var(--texto); max-width: 90vw; text-align: center; } #lupa-ext small { color: var(--apagado); }

  #ldt { position: fixed; z-index: 6; left: 24px; top: 56px; width: min(380px, 70vw); padding: 12px 14px; display: none;
    background: linear-gradient(135deg, #0c2236ee, #06121dee); border: 1px solid var(--ciano-fraco); animation: surge .3s ease-out both; }
  #ldt.ativo { display: block; }
  #ldt h3 { margin: 0 0 6px; font-size: 11px; letter-spacing: .22em; text-transform: uppercase; color: var(--ciano); }
  #ldt ol { margin: 0; padding: 0; list-style: none; display: grid; gap: 5px; font-size: 13px; }
  #ldt li { position: relative; padding-left: 22px; color: var(--apagado); }
  #ldt li::before { content: ""; position: absolute; left: 3px; top: 5px; width: 9px; height: 9px; border-radius: 50%; border: 1px solid var(--apagado); }
  #ldt li.rodando { color: var(--texto); } #ldt li.rodando::before { border-color: var(--ciano); border-top-color: transparent; animation: gira .8s linear infinite; }
  #ldt li.ok { color: var(--texto); } #ldt li.ok::before { background: #6dffb0; border-color: #6dffb0; }
  #ldt li.erro { color: #ff6b4a; } #ldt li.erro::before { background: #ff6b4a; border-color: #ff6b4a; }
  #ldt .barra { height: 2px; margin-top: 8px; background: var(--ciano-fraco); overflow: hidden; }
  #ldt .barra div { height: 100%; width: 0; background: var(--ciano); box-shadow: 0 0 8px var(--ciano); transition: width .5s; }

  /* animações de estado: pesquisando (radar), pensando (núcleo pulsando), agindo (anéis + barra), ok, erro */
  #fx { position: fixed; z-index: 2; inset: 0; pointer-events: none; display: grid; place-items: center; }
  #fx .radar { width: 70vmin; height: 70vmin; border-radius: 50%; opacity: 0; transition: opacity .5s;
    background: conic-gradient(from 0deg, transparent 0 300deg, var(--ciano-fraco) 340deg, var(--ciano) 360deg);
    -webkit-mask: radial-gradient(circle, transparent 30%, #000 31%); mask: radial-gradient(circle, transparent 30%, #000 31%); animation: gira 1.6s linear infinite; }
  #fx .pulso, #fx .aneis { position: absolute; width: 46vmin; height: 46vmin; border-radius: 50%; opacity: 0; transition: opacity .4s; }
  #fx .pulso { border: 2px solid var(--ciano); box-shadow: 0 0 40px var(--ciano-fraco), inset 0 0 40px var(--ciano-fraco); animation: pulsoFx 1.4s ease-in-out infinite; }
  #fx .aneis { border: 2px dashed var(--ciano); animation: gira 3s linear infinite; }
  #fx .aneis::after { content: ""; position: absolute; inset: 12%; border-radius: 50%; border: 2px solid var(--ciano-fraco); border-top-color: var(--ciano); animation: gira 1s linear infinite reverse; }
  body.fx-pesquisando #fx .radar, body.fx-pensando #fx .pulso, body.fx-agindo #fx .aneis { opacity: .55; }
  body.com-cartoes #fx { display: none; }
  #flash { position: fixed; z-index: 25; inset: 0; pointer-events: none; opacity: 0; }
  #flash.ok { animation: flashOk .9s ease-out; } #flash.erro { animation: flashErro 1.6s ease-out; }
  @keyframes pulsoFx { 50% { transform: scale(1.08); opacity: .25; } }
  @keyframes flashOk { 20% { opacity: 1; box-shadow: inset 0 0 120px var(--ciano); } }
  @keyframes flashErro { 15%, 45% { opacity: 1; box-shadow: inset 0 0 160px #ff2a2a; } }
  #estado-ext { position: fixed; z-index: 5; left: 50%; bottom: 20px; transform: translateX(-50%); font: 11px Consolas, monospace;
    letter-spacing: .3em; color: var(--ciano); text-transform: uppercase; pointer-events: none; }
  body.com-cartoes #estado-ext { display: none; }

  /* Olho de Deus */
  .aviao { width: 18px; height: 18px; transform-origin: center; pointer-events: auto; position: relative; }
  .aviao svg { width: 100%; height: 100%; fill: var(--ciano); filter: drop-shadow(0 0 4px var(--ciano)); }
  .aviao span { position: absolute; left: 20px; top: 2px; font: 9px Consolas, monospace; color: var(--texto); white-space: nowrap;
    text-shadow: 0 0 4px #000; opacity: .8; }
  .sat { width: 4px; height: 4px; border-radius: 50%; background: #e8f6ff; box-shadow: 0 0 6px #bfe9ff; pointer-events: auto; }
  .iss { font: 11px Consolas, monospace; color: #ffd36b; text-shadow: 0 0 6px #000; white-space: nowrap; transform: translate(8px, -8px); }
  .iss::before { content: "◆ "; }
  .clima-rotulo { font: 11px Consolas, monospace; color: var(--texto); background: #06121dcc; border: 1px solid var(--ciano-fraco);
    padding: 1px 5px; white-space: nowrap; }
  #olho-hud { position: fixed; z-index: 5; left: 24px; top: 56px; display: none; font: 11px/1.7 Consolas, monospace; letter-spacing: .12em;
    color: var(--apagado); pointer-events: none; }
  body.olho #olho-hud { display: block; } body.olho.com-cartoes:not(.lugar) #olho-hud { display: none; } body.olho #olho-hud b { color: var(--ciano); font-weight: normal; }
  #letreiro { position: fixed; z-index: 5; left: 0; right: 0; bottom: 0; height: 26px; overflow: hidden; display: none;
    background: #020a12d9; border-top: 1px solid var(--ciano-fraco); font: 12px/26px Consolas, monospace; color: var(--texto); }
  body.olho-noticias #letreiro { display: block; }
  #letreiro div { display: inline-block; white-space: nowrap; padding-left: 100%; animation: letreiro 90s linear infinite; }
  @keyframes letreiro { to { transform: translateX(-100%); } }
  body.leve #fx { display: none; }
  `;
  document.head.append(estilo);
  const novo = (html) => { const d = document.createElement("div"); d.innerHTML = html.trim(); return d.firstElementChild; };
  document.body.append(
    novo(`<section id="leitor" aria-label="Modo leitura"><header><span><span class="ponto"></span><span class="marca">LEITURA</span> · <span id="leitor-titulo"></span></span>
      <span><button class="pp-botao" id="leitor-nav">↗ navegador</button> <button class="pp-botao" id="leitor-fechar">✕</button></span></header>
      <div class="conteudo" id="leitor-conteudo"></div></section>`),
    novo(`<div id="lupa-ext"><img alt=""><p></p><small></small></div>`),
    novo(`<aside id="ldt"><h3 id="ldt-titulo">Executando</h3><ol id="ldt-lista"></ol><div class="barra"><div></div></div></aside>`),
    novo(`<div id="fx" aria-hidden="true"><div class="radar"></div><div class="pulso"></div><div class="aneis"></div></div>`),
    novo(`<div id="flash" aria-hidden="true"></div>`),
    novo(`<div id="estado-ext"></div>`),
    novo(`<div id="olho-hud"></div>`),
    novo(`<div id="letreiro"><div></div></div>`),
  );

  // ------------------------------------------------------------ lupa e modo leitura
  let leituraUrl = "";
  window.ampliarFoto = (url, legenda, credito) => {
    const l = $("lupa-ext");
    l.querySelector("img").src = url; l.querySelector("p").textContent = legenda || ""; l.querySelector("small").textContent = credito || "";
    l.classList.add("aberta"); sons.popup();
  };
  $("lupa-ext").onclick = () => $("lupa-ext").classList.remove("aberta");
  window.abrirLeitura = async (url) => {
    leituraUrl = url;
    $("leitor-titulo").textContent = "carregando…"; $("leitor-conteudo").innerHTML = "";
    document.body.classList.add("lendo-pagina"); sons.viagem();
    try { mostrarLeitura(await (await fetch("/api/leitura?url=" + encodeURIComponent(url))).json()); }
    catch { $("leitor-titulo").textContent = "não consegui abrir"; }
  };
  function mostrarLeitura(l) {
    leituraUrl = l.url || leituraUrl;
    document.body.classList.add("lendo-pagina");
    $("leitor-titulo").textContent = (l.titulo || "").toUpperCase().slice(0, 90);
    const c = $("leitor-conteudo"); c.innerHTML = "";
    if (l.imagem) { const img = document.createElement("img"); img.className = "imagem-topo"; img.src = l.imagem; img.onerror = () => img.remove(); c.append(img); }
    for (const p of l.paragrafos || []) {
      const el = document.createElement(p.startsWith("## ") ? "h2" : "p");
      el.textContent = p.replace(/^## /, ""); c.append(el);
    }
    sons.trava();
  }
  $("leitor-fechar").onclick = () => { document.body.classList.remove("lendo-pagina"); sons.fecha(); };
  // ele clicou: abrir no navegador é pedido dele
  $("leitor-nav").onclick = () => leituraUrl && window.open(leituraUrl, "_blank");

  // ------------------------------------------------------------ painel de pesquisa
  function painelDePesquisa(p) {
    const c = document.createElement("article");
    c.className = "cartao painel-pesquisa"; c.dataset.id = p.id;
    const topo = document.createElement("div"); topo.className = "pp-topo";
    const h = document.createElement("h3"); h.textContent = "Pesquisa · " + (p.termo || "");
    const fixar = Object.assign(document.createElement("button"), { className: "pp-botao pp-fixar", textContent: "📌", title: "Fixar" });
    fixar.onclick = () => { c.classList.toggle("fixo"); sons.trava(); };
    const mais = Object.assign(document.createElement("button"), { className: "pp-botao", textContent: "+ fotos" });
    mais.onclick = () => pedir("mostra mais fotos");
    const fecha = Object.assign(document.createElement("button"), { className: "pp-botao", textContent: "✕" });
    fecha.onclick = () => remover([p.id]);
    topo.append(h, mais, fixar, fecha);
    const d = document.createElement("div"); d.className = "destaque"; d.textContent = p.titulo;
    const resumo = document.createElement("p"); resumo.className = "pp-resumo"; resumo.textContent = p.resumo;
    const ol = document.createElement("ol"); ol.className = "pp-topicos";
    for (const t of p.topicos) { const li = document.createElement("li"); li.textContent = t; ol.append(li); }
    const g = document.createElement("div"); g.className = "galeria";
    adicionarFotos(g, p.imagens);
    const fontes = document.createElement("ul"); fontes.className = "pp-fontes";
    p.fontes.forEach((f, i) => {
      const li = document.createElement("li"), n = document.createElement("span"), a = document.createElement("a"), nav = document.createElement("button");
      n.className = "n"; n.textContent = `[${i + 1}]`;
      a.textContent = f.titulo; a.title = f.url; a.onclick = () => abrirLeitura(f.url);
      nav.className = "pp-botao"; nav.textContent = "↗"; nav.title = "Abrir no navegador"; nav.onclick = () => window.open(f.url, "_blank");
      li.append(n, a, nav); fontes.append(li);
    });
    c.append(topo, d, resumo, ol, g, fontes);
    document.body.classList.remove("lugar", "silhueta");
    lista.prepend(c);
    podar(); atualizarEstado(); sons.popup();
  }
  function adicionarFotos(g, imagens) {
    for (const f of imagens || []) {
      const fig = document.createElement("figure"), img = document.createElement("img"), cap = document.createElement("figcaption");
      img.src = f.url; img.loading = "lazy"; img.alt = f.legenda || "";
      img.onclick = () => ampliarFoto(f.grande || f.url, f.legenda, f.credito);
      img.onerror = () => fig.remove();
      cap.textContent = f.credito || ""; fig.append(img, cap); g.append(fig);
    }
  }
  async function pedir(texto) {  // botão na tela = mesma coisa que falar
    try { const r = await fetch("/api/conversar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ texto }) }); await r.text(); } catch {}
  }
  const ultimoPainel = () => lista.querySelector(".painel-pesquisa") || lista.firstElementChild;

  // ------------------------------------------------------------ linha do tempo do plano
  const passos = new Map(); let someLdt = null;
  function plano(pl) {
    $("ldt-titulo").textContent = pl.objetivo || "Plano"; $("ldt-lista").innerHTML = ""; passos.clear();
    pl.passos.forEach((t, i) => { const li = document.createElement("li"); li.textContent = `${i + 1}. ${t}`; li.dataset.plano = i; $("ldt-lista").append(li); });
    $("ldt").classList.add("ativo"); clearTimeout(someLdt); barra(); sons.popup();
  }
  function passo(p) {
    const ol = $("ldt-lista");
    $("ldt").classList.add("ativo"); clearTimeout(someLdt);
    let li = passos.get(p.id);
    if (!li) {
      li = ol.querySelector("li[data-plano]:not([data-feito])");
      if (!li) { li = document.createElement("li"); li.textContent = p.resumo; ol.append(li); while (ol.children.length > 9) ol.firstElementChild.remove(); }
      li.dataset.feito = "1"; passos.set(p.id, li);
    }
    li.className = p.estado; if (p.detalhe) li.title = p.detalhe;
    barra();
    if (p.estado === "erro") flash("erro");
    if (p.estado !== "rodando") someLdt = setTimeout(() => { $("ldt").classList.remove("ativo"); $("ldt-lista").innerHTML = ""; passos.clear(); }, 12000);
  }
  function barra() {
    const itens = [...$("ldt-lista").children];
    const feitos = itens.filter((li) => li.classList.contains("ok") || li.classList.contains("erro")).length;
    $("ldt").querySelector(".barra div").style.width = (itens.length ? (100 * feitos) / itens.length : 0) + "%";
  }

  // ------------------------------------------------------------ estados e efeitos
  function efeito(tipo) {
    document.body.classList.remove("fx-pesquisando", "fx-pensando", "fx-agindo");
    if (tipo) document.body.classList.add("fx-" + tipo);
  }
  function flash(tipo) {
    const f = $("flash"); f.className = ""; void f.offsetWidth; f.className = tipo;
    if (tipo === "erro") sons.fecha();
  }
  const NOMES_ESTADO = { ouvindo: "Ouvindo", pensando: "Pensando", agindo: "Executando", falando: "Falando", parado: "" };
  function estadoDoHud({ estado }) {
    $("estado-ext").textContent = NOMES_ESTADO[estado] ?? "";
    efeito(estado === "pensando" ? "pensando" : estado === "agindo" ? "agindo" : null);
  }

  // ------------------------------------------------------------ Olho de Deus
  const AVIAO_SVG = '<svg viewBox="0 0 24 24"><path d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"/></svg>';
  const olho = { avioes: false, satelites: false, terremotos: false, clima: false, noticias: false };
  let avioes = [], sats = [], quakes = [], climas = [], ultimaBusca = 0, centro = null;
  const elAviao = new Map();
  function elementoDoAviao(a) {
    let el = elAviao.get(a.id);
    if (!el) {
      el = document.createElement("div"); el.className = "aviao"; el.innerHTML = AVIAO_SVG + `<span></span>`;
      el.title = ""; elAviao.set(a.id, el);
      el.style.cursor = "pointer";
      el.onclick = (ev) => { ev.stopPropagation(); const atual = avioes.find((x) => x.id === a.id) || a; window.clicarAviao && window.clicarAviao(atual); };
    }
    el.querySelector("svg").style.transform = `rotate(${a.rumo}deg)`;
    el.querySelector("span").textContent = a.voo || "";
    el.title = `${a.voo || a.id} · ${a.modelo || ""} · ${Math.round(a.alt_m)} m · ${a.vel_kmh} km/h`;
    return el;
  }
  function desenharHtml() {
    const itens = [];
    if (olho.avioes) itens.push(...avioes.map((a) => ({ ...a, tipo: "aviao" })));
    if (olho.satelites) itens.push(...sats.map((s) => ({ ...s, tipo: s.destaque ? "iss" : "sat" })));
    if (olho.clima) itens.push(...climas.map((c) => ({ ...c, tipo: "clima" })));
    itens.push(...(window.extrasHtml || []));  // pinos de estabelecimento e a mira da cidade (parte 3)
    globo.htmlElementsData(itens)
      .htmlLat((d) => d.lat).htmlLng((d) => d.lng)
      .htmlAltitude((d) => d.el ? 0.002 : d.tipo === "aviao" ? 0.005 + Math.min(0.02, (d.alt_m || 0) / 600000) : d.tipo === "iss" || d.tipo === "sat" ? Math.min(0.6, d.alt_km / 6371) : 0.01)
      .htmlElement((d) => {
        if (d.el) return d.el;
        if (d.tipo === "aviao") return elementoDoAviao(d);
        const el = document.createElement("div");
        if (d.tipo === "sat") { el.className = "sat"; el.title = `${d.nome} · ${d.alt_km} km · ${d.vel_kms} km/s`; return el; }
        if (d.tipo === "iss") { el.className = "iss"; el.textContent = d.nome.replace(" (ZARYA)", ""); }
        else { el.className = "clima-rotulo"; el.textContent = `${d.nome} ${d.temp}°`; }
        return el;
      });
  }
  function desenharPontos() {
    const pts = [];
    if (olho.terremotos) pts.push(...quakes.map((q) => ({ ...q, tipo: "quake" })));
    globo.pointsData(pts).pointLat((d) => d.lat).pointLng((d) => d.lng)
      .pointAltitude((d) => d.tipo === "sat" ? Math.min(0.6, d.alt_km / 6371) : 0.003 + d.mag * 0.002)
      .pointRadius((d) => d.tipo === "sat" ? (d.destaque ? 0.5 : 0.18) : 0.25 + d.mag * 0.12)
      .pointColor((d) => d.tipo === "sat" ? (d.destaque ? "#ffd36b" : "#e8f6ff") : d.mag >= 5 ? "#ff3b30" : "#ffb547")
      .pointLabel((d) => d.tipo === "sat" ? `${d.nome} · ${d.alt_km} km · ${d.vel_kms} km/s` :
        `M${d.mag.toFixed(1)} · ${d.lugar} · ${new Date(d.quando * 1000).toLocaleString("pt-BR")}`)
      .pointsMerge(false).pointsTransitionDuration(0);
  }
  async function buscar(camada, extra = "") {
    try { return await (await fetch(`/api/olho/${camada}${extra}`)).json(); } catch { return []; }
  }
  let olhoArea = null;  // "aviões sobrevoando o Brasil": a região inteira (o servidor varre aos poucos)
  async function atualizarAvioes() {
    if (!olho.avioes) return;
    const pov = globo.pointOfView();
    centro = pov.altitude < 1.6 ? { lat: pov.lat, lng: pov.lng } : CASA;
    const novos = olhoArea ? await buscar("avioes", `?caixa=${olhoArea.caixa.map((x) => x.toFixed(2)).join(",")}`)
                           : await buscar("avioes", `?lat=${centro.lat.toFixed(2)}&lng=${centro.lng.toFixed(2)}`);
    const antigos = new Map(avioes.map((a) => [a.id, a]));
    avioes = novos.map((a) => ({ ...a, _t: Date.now() }));
    for (const id of [...elAviao.keys()]) if (!avioes.some((a) => a.id === id)) elAviao.delete(id);
    desenharHtml(); painelDoOlho();
    void antigos;
  }
  // os aviões andam entre uma leitura e outra (rumo + velocidade): voo animado ao vivo
  setInterval(() => {
    if (!olho.avioes || !avioes.length || document.hidden) return;
    const agora = Date.now();
    for (const a of avioes) {
      const dt = (agora - a._t) / 3600000; a._t = agora;  // horas
      const km = a.vel_kmh * dt, r = (a.rumo * Math.PI) / 180;
      a.lat += (km * Math.cos(r)) / 111.2;
      a.lng += (km * Math.sin(r)) / (111.2 * Math.max(0.2, Math.cos((a.lat * Math.PI) / 180)));
    }
    desenharHtml();
  }, 500);
  async function atualizarSats() {
    if (!olho.satelites) return;
    sats = await buscar("satelites");
    desenharPontos(); desenharHtml(); painelDoOlho();
  }
  async function atualizarQuakes() { if (olho.terremotos) { quakes = await buscar("terremotos"); desenharPontos(); painelDoOlho(); } }
  async function atualizarClima() { if (olho.clima) { climas = await buscar("clima"); desenharHtml(); } }
  async function atualizarNoticias() {
    if (!olho.noticias) return;
    const m = await buscar("noticias");
    $("letreiro").firstElementChild.textContent = m.length ? "  ◆  " + m.join("   ◆   ") : "";
  }
  setInterval(atualizarAvioes, 10000);
  setInterval(atualizarSats, 3000);
  setInterval(atualizarQuakes, 300000);
  setInterval(atualizarClima, 900000);
  setInterval(atualizarNoticias, 900000);
  function painelDoOlho() {
    const linhas = ["<b>OLHO DE DEUS</b>"];
    if (olho.avioes) linhas.push(`AVIÕES · <b>${avioes.length}</b> NO AR`);
    if (olho.satelites) {
      const iss = sats.find((s) => s.destaque);
      linhas.push(`SATÉLITES · <b>${sats.length}</b>`);
      if (iss) linhas.push(`ISS · ${Math.abs(iss.lat).toFixed(1)}°${iss.lat < 0 ? "S" : "N"} ${Math.abs(iss.lng).toFixed(1)}°${iss.lng < 0 ? "O" : "L"}`);
    }
    if (olho.terremotos) linhas.push(`TERREMOTOS 24H · <b>${quakes.length}</b>` + (quakes.length ? ` · MAIOR M${Math.max(...quakes.map((q) => q.mag)).toFixed(1)}` : ""));
    if (olho.clima) linhas.push("CLIMA · CAPITAIS");
    $("olho-hud").innerHTML = linhas.join("<br>");
  }
  function camada(nome, ligar, area, silencioso) {
    if (nome === "avioes") olhoArea = ligar ? area || null : null;
    olho[nome] = ligar;
    document.body.classList.toggle("olho", Object.values(olho).some(Boolean));
    document.body.classList.toggle("olho-noticias", olho.noticias);
    if (nome === "avioes") {
      if (ligar) {
        clearTimeout(window.voltaAGirarOlho);
        globo.controls().autoRotate = false;
        if (area) {  // a câmera vai pra região pedida
          const [s_, n_, o_, l_] = area.caixa;
          globo.pointOfView({ lat: (s_ + n_) / 2, lng: (o_ + l_) / 2, altitude: Math.min(2.4, Math.max(0.4, Math.max(n_ - s_, l_ - o_) / 28)) }, 2000);
        } else globo.pointOfView({ lat: CASA.lat, lng: CASA.lng, altitude: 0.55 }, 2000);  // perto pra ver os aviões voando
        setTimeout(atualizarAvioes, 2100);
      } else { avioes = []; elAviao.clear(); }
    }
    ({ satelites: atualizarSats, terremotos: atualizarQuakes, clima: atualizarClima, noticias: atualizarNoticias }[nome] || (() => {}))();
    desenharHtml(); desenharPontos(); painelDoOlho();
    if (!silencioso) sons[ligar ? "trava" : "fecha"]();
  }
  window.olhoCamada = camada;
  window.redesenharHtml = desenharHtml;
  // o globo voltando a girar sozinho não pode tirar os aviões de vista
  const voltarOriginal = voltarAGirar;
  voltarAGirar = function () {
    voltarOriginal();
    if (olho.avioes && !olhoArea) { globo.controls().autoRotate = false; globo.pointOfView({ lat: CASA.lat, lng: CASA.lng, altitude: 0.55 }, 1500); }
  };

  // ------------------------------------------------------------ eventos do servidor
  fonte.addEventListener("message", (m) => {
    const e = JSON.parse(m.data);
    if (e.painel) { painelDePesquisa(e.painel); efeito(null); }
    if (e.painel_fotos) {
      const c = document.querySelector(`[data-id="${e.painel_fotos.id}"] .galeria`);
      if (c) { adicionarFotos(c, e.painel_fotos.imagens); sons.popup(); }
    }
    if (e.destacar) {
      const c = document.querySelector(`[data-id="${e.destacar.id}"]`);
      if (c) {
        c.querySelectorAll(".lendo").forEach((x) => x.classList.remove("lendo"));
        const alvo = c.classList.contains("noticias") ? null : e.destacar.i < 0 ? c.querySelector(".pp-resumo") : c.querySelectorAll(".pp-topicos li")[e.destacar.i];
        if (alvo) { alvo.classList.add("lendo"); alvo.scrollIntoView({ block: "nearest", behavior: "smooth" }); }
      }
    }
    if (e.leitura_pagina) mostrarLeitura(e.leitura_pagina);
    if (e.ampliar) {
      const imgs = ultimoPainel()?.querySelectorAll(".galeria img") || [];
      const i = e.ampliar.n < 0 ? imgs.length - 1 : e.ampliar.n - 1;
      if (imgs[i]) imgs[i].click();
    }
    if (e.fechar_painel) {
      if (document.body.classList.contains("vendo-pagina")) { /* a parte 3 fecha a página */ }
      else if (document.body.classList.contains("lendo-pagina")) { document.body.classList.remove("lendo-pagina"); sons.fecha(); }
      else if ($("lupa-ext").classList.contains("aberta")) $("lupa-ext").classList.remove("aberta");
      else {
        const alvos = e.fechar_painel === "todos" ? [...lista.children] : [ultimoPainel()].filter(Boolean);
        remover(alvos.map((el) => el.dataset.id || (el.dataset.id = "t" + Math.random())));
      }
    }
    if (e.fixar) { const p = ultimoPainel(); if (p) { p.classList.add("fixo"); sons.trava(); } }
    if (e.plano) plano(e.plano);
    if (e.passo) passo(e.passo);
    if (e.atividade) {
      if (e.atividade.tipo === "pesquisando") { efeito("pesquisando"); $("estado-ext").textContent = e.atividade.texto; }
      if (e.atividade.tipo === "concluido") { efeito(null); flash("ok"); }
      if (e.atividade.tipo === "erro") { efeito(null); flash("erro"); }
    }
    if (e.estado) estadoDoHud(e.estado);
    if (e.olho) for (const nome of Object.keys(olho)) camada(nome, e.olho.ligado && e.olho.camadas.includes(nome), null, true);
    if (e.olho) sons[e.olho.ligado ? "viagem" : "fecha"]();
    if (e.olho_camada) {
      if (e.olho_camada.exclusivo)  // só o que ele pediu: as outras camadas saem
        for (const outra of Object.keys(olho)) if (outra !== e.olho_camada.camada && olho[outra]) camada(outra, false, null, true);
      camada(e.olho_camada.camada, e.olho_camada.ligado, e.olho_camada.area);
      // ocultou a última camada que estava na tela: o globo volta ao normal (sem zoom, girando)
      if (!e.olho_camada.ligado && !Object.values(olho).some(Boolean)) window.globoNormal && window.globoNormal();
    }
  });
})();
