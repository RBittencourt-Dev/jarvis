// Extensão, parte 3 (21/10, 2ª rodada): globo de verdade e interativo.
//  - roda do mouse dá zoom; arrastar gira (e ele para de girar sozinho enquanto você mexe);
//  - "globo real / via satélite / camadas da terra" (e o Olho de Deus): foto de satélite. De longe, a imagem de ONTEM
//    da NASA (nuvens de verdade); chegando perto, a foto em alta resolução da Esri (dá pra ver a rua);
//  - clique num país → seleciona e aproxima; no Brasil aparecem os estados (clique de novo → estado);
//    clique de novo → a cidade. O Jarvis fica sabendo ("me fala desse país", "procura pizzaria nessa cidade");
//  - estabelecimentos (pois), notícias com foto, página do site dentro dele, "volta o globo ao normal".
(() => {
  const css = document.createElement("style");
  css.textContent = `
  #selecao-globo { position: fixed; z-index: 5; left: 50%; top: 52px; transform: translateX(-50%); display: none; padding: 8px 16px;
    background: #06121de6; border: 1px solid var(--ciano); box-shadow: 0 0 24px var(--ciano-fraco); text-align: center; pointer-events: auto; }
  #selecao-globo.ativa { display: block; animation: surge .35s ease-out both; }
  #selecao-globo b { display: block; font: 300 22px/1.2 "Segoe UI", sans-serif; color: var(--ciano); letter-spacing: .12em; }
  #selecao-globo small { font: 10px Consolas, monospace; letter-spacing: .2em; color: var(--apagado); }
  #selecao-globo button { margin-top: 4px; }
  body.com-cartoes:not(.lugar) #selecao-globo { display: none; }
  body.lugar #sobre-globo:not(:empty) ~ #selecao-globo, body.lugar.tem-unidade #selecao-globo { display: none; }
  .pino { width: 12px; height: 12px; border-radius: 50% 50% 50% 0; transform: rotate(-45deg) translate(2px, -6px); background: #ffd36b;
    box-shadow: 0 0 8px #ffd36b; border: 1px solid #fff8; pointer-events: auto; cursor: pointer; }
  .pino:hover { background: #fff; transform: rotate(-45deg) translate(2px, -6px) scale(1.4); }
  .pino-nome { position: absolute; left: 16px; top: -2px; transform: rotate(45deg); font: 10px Consolas, monospace; color: #fff;
    text-shadow: 0 0 4px #000; white-space: nowrap; display: none; }
  .pino:hover .pino-nome, body.poucos-pinos .pino-nome { display: block; }
  .cidade-mira { width: 14px; height: 14px; border: 2px solid var(--ciano); border-radius: 50%; box-shadow: 0 0 12px var(--ciano); }
  .noticias .nt { display: grid; grid-template-columns: 150px 1fr; gap: 12px; padding: 10px 0; border-top: 1px solid #39d0ff1a; cursor: pointer;
    transition: background .3s; }
  .noticias .nt img { width: 150px; height: 96px; object-fit: cover; border: 1px solid var(--ciano-fraco); transition: all .4s; }
  .noticias .nt h4 { margin: 0 0 4px; font-size: 17px; font-weight: 500; line-height: 1.3; }
  .noticias .nt small { color: var(--apagado); font: 11px Consolas, monospace; letter-spacing: .1em; }
  .noticias .nt p { margin: 4px 0 0; font-size: 14px; color: var(--apagado); }
  .noticias .nt.lendo-agora { background: #39d0ff12; grid-template-columns: 1fr; }
  .noticias .nt.lendo-agora img { width: 100%; height: 300px; }
  .noticias .nt.lendo-agora h4 { color: var(--ciano); font-size: 21px; } .noticias .nt.lendo-agora p { color: var(--texto); }
  #pagina-ext { position: fixed; z-index: 8; left: 12px; right: 12px; top: 56px; bottom: 16px; display: none; flex-direction: column;
    border: 1px solid var(--ciano); background: #020a12; box-shadow: 0 0 50px var(--ciano-fraco); animation: surge .4s cubic-bezier(.2,.9,.3,1.2); }
  body.vendo-pagina #pagina-ext { display: flex; }
  #pagina-ext header { position: static; pointer-events: auto; padding: 8px 12px; border-bottom: 1px solid var(--ciano-fraco); gap: 8px; }
  #pagina-ext iframe { flex: 1; width: 100%; border: 0; background: #fff; }
  #leitor .imagem-topo { width: 100%; max-height: 380px; object-fit: cover; border: 1px solid var(--ciano-fraco); margin-bottom: 14px; }
  `;
  document.head.append(css);
  const novo = (html) => { const d = document.createElement("div"); d.innerHTML = html.trim(); return d.firstElementChild; };
  document.body.append(
    novo(`<div id="selecao-globo"><small id="sel-tipo"></small><b id="sel-nome"></b><small>PERGUNTE: "ME FALA DESSE LUGAR"</small></div>`),
    novo(`<section id="pagina-ext"><header><span><span class="ponto"></span><span class="marca" id="pg-fonte">PÁGINA</span> · <span id="pg-titulo"></span></span>
      <span><button class="pp-botao" id="pg-nav">↗ navegador</button> <button class="pp-botao" id="pg-fechar">✕</button></span></header>
      <iframe id="pg-quadro" title="Página" referrerpolicy="no-referrer-when-downgrade"></iframe></section>`),
  );
  window.extrasHtml = window.extrasHtml || [];
  const redesenhar = () => window.redesenharHtml && window.redesenharHtml();

  // ------------------------------------------------------------ mouse: zoom e giro
  const ctl = globo.controls();
  ctl.enableZoom = true;
  ctl.zoomSpeed = 1.1;
  ctl.addEventListener("start", () => { ctl.autoRotate = false; clearTimeout(window.voltaAGirarMouse); });
  ctl.addEventListener("end", () => {
    clearTimeout(window.voltaAGirarMouse);
    // 2 min sem mexer e sem nada aberto: volta a girar sozinho
    window.voltaAGirarMouse = setTimeout(() => { if (!selecaoAtual && !document.body.classList.contains("olho") && !pinos.length) ctl.autoRotate = true; }, 120000);
  });

  // ------------------------------------------------------------ imagem: holograma ou satélite
  let modo = "holograma", nuvens = false;  // padrão sem nuvens (pedido dele): a foto limpa da Esri; "mostra as nuvens" = NASA de ontem
  const ontem = () => new Date(Date.now() - 86400000).toISOString().slice(0, 10);
  function satelite(ligar, comNuvens) {
    if (!globo.globeTileEngineUrl) return;
    if (comNuvens !== undefined && comNuvens !== nuvens) { nuvens = comNuvens; if (modo === "satelite") modo = "trocando"; }
    if (ligar && modo !== "satelite") {
      modo = "satelite";
      const dia = ontem();
      const esri = (x, y, l) => `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${l}/${y}/${x}`;
      globo.globeTileEngineUrl((x, y, l) => nuvens && l <= 6
        ? `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_SNPP_CorrectedReflectance_TrueColor/default/${dia}/GoogleMapsCompatible_Level9/${l}/${y}/${x}.jpg`
        : esri(x, y, l));
      globo.hexPolygonsData([]);
      const c = corCiano();
      globo.polygonCapColor((f) => (f === selecaoAtual?.forma ? c + "44" : "rgba(0,0,0,0)"))
        .polygonSideColor(() => "rgba(0,0,0,0)").polygonStrokeColor((f) => (f === selecaoAtual?.forma ? "#ffffff" : c + "88"));
      const m = globo.globeMaterial(); m.opacity = 1; m.transparent = false; m.color.set("#ffffff"); m.emissive.set("#000000");
      $("coordenadas").textContent = nuvens ? `SATÉLITE · NUVENS DE ${dia.split("-").reverse().join("/")} (NASA)` : "SATÉLITE · ESRI WORLD IMAGERY";
      sons.trava();
    } else if (!ligar && modo !== "holograma") {
      modo = "holograma";
      globo.globeTileEngineUrl(null);
      globo.hexPolygonsData(paises || []);
      pintar();
      $("coordenadas").textContent = "ESCANEANDO · ÓRBITA BAIXA";
    }
  }
  window.modoSatelite = () => modo === "satelite";
  // o pintar() da parte 1 refaz as cores do holograma; no modo satélite ele precisa manter o mapa limpo
  const pintarOriginal = pintar;
  pintar = function () { pintarOriginal(); if (modo === "satelite") { modo = "holograma"; satelite(true); } };

  // ------------------------------------------------------------ seleção por clique: país → estado → cidade
  let selecaoAtual = null, estadosBR3 = null;
  const nomePais = (f) => {
    const iso = [f.properties.ISO_A2, f.properties.WB_A2].find((x) => x && x !== "-99");
    try { if (iso) return new Intl.DisplayNames(["pt-BR"], { type: "region" }).of(iso); } catch {}
    return f.properties.NAME || f.properties.ADMIN;
  };
  function caixaDe(forma) {
    const aneis = forma.geometry.type === "MultiPolygon" ? forma.geometry.coordinates.flat(1) : forma.geometry.coordinates;
    const pts = aneis.flat(1);
    const lats = pts.map((p) => p[1]), lngs = pts.map((p) => p[0]);
    return [Math.min(...lats), Math.max(...lats), Math.min(...lngs), Math.max(...lngs)];
  }
  function voarPara(caixa) {
    const [s, n, o, l] = caixa;
    const tam = Math.max(n - s, (l - o) * Math.cos((((s + n) / 2) * Math.PI) / 180));
    globo.pointOfView({ lat: (s + n) / 2, lng: (o + l) / 2, altitude: Math.min(2.6, Math.max(0.12, tam / 30)) }, 1500);
  }
  async function mostrarEstados(ligar) {
    if (ligar) {
      estadosBR3 = estadosBR3 || (await (await fetch("/web/vendor/estados-br.geojson")).json()).features;
      globo.polygonsData([...(paises || []).filter((f) => f.properties.ISO_A2 !== "BR"), ...estadosBR3]);
    } else globo.polygonsData(paises || []);
  }
  function anunciar(sel) {
    selecaoAtual = sel;
    $("sel-tipo").textContent = sel ? `SELECIONADO · ${sel.tipo.toUpperCase()}` : "";
    $("sel-nome").textContent = sel ? sel.nome.toUpperCase() : "";
    $("selecao-globo").classList.toggle("ativa", !!sel);
    fetch("/api/selecao", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(sel ? { tipo: sel.tipo, nome: sel.nome, lat: sel.lat, lng: sel.lng, caixa: sel.caixa } : { nome: "" }) }).catch(() => {});
    if (sel) sons.trava();
    if (modo === "satelite") { modo = "holograma"; satelite(true); } else pintar();
  }
  async function cidadeEm(lat, lng) {
    const r = await (await fetch(`/api/onde?lat=${lat}&lng=${lng}`)).json().catch(() => ({}));
    if (!r.cidade) return;
    const el = document.createElement("div"); el.className = "cidade-mira";
    window.extrasHtml = window.extrasHtml.filter((x) => x.tipo !== "cidade");
    window.extrasHtml.push({ tipo: "cidade", lat, lng, el });
    redesenhar();
    anunciar({ tipo: "cidade", nome: `${r.cidade}${r.estado ? ", " + r.estado : ""}`, lat, lng, caixa: r.caixa, forma: selecaoAtual?.forma });
    if (r.caixa) voarPara(r.caixa);
  }
  globo.onPolygonClick(async (f, ev, { lat, lng } = {}) => {
    ctl.autoRotate = false;
    const ehEstado = !!f.properties.sigla;
    const mesmo = selecaoAtual?.forma === f;
    if (mesmo || selecaoAtual?.tipo === "cidade" && selecaoAtual.forma === f) return cidadeEm(lat, lng);  // 2º clique: a cidade
    selecionada = f;  // o pintar() da parte 1 acende o selecionado
    const caixa = caixaDe(f);
    voarPara(caixa);
    if (ehEstado) {
      anunciar({ tipo: "estado", nome: f.properties.name, sigla: f.properties.sigla, lat: (caixa[0] + caixa[1]) / 2, lng: (caixa[2] + caixa[3]) / 2, caixa, forma: f });
    } else {
      const nome = nomePais(f);
      await mostrarEstados(f.properties.ISO_A2 === "BR");
      anunciar({ tipo: "país", nome, lat: (caixa[0] + caixa[1]) / 2, lng: (caixa[2] + caixa[3]) / 2, caixa, forma: f });
    }
  });
  globo.onGlobeClick(({ lat, lng }) => {
    // clique fora de qualquer país (mar) limpa; bem de perto, dentro de um país sem estados, acha a cidade
    if (globo.pointOfView().altitude < 0.35 && selecaoAtual) return cidadeEm(lat, lng);
    limparSelecao();
  });
  function limparSelecao() {
    if (!selecaoAtual) return;
    selecionada = null;
    window.extrasHtml = window.extrasHtml.filter((x) => x.tipo !== "cidade");
    redesenhar(); mostrarEstados(false); anunciar(null);
  }

  // ------------------------------------------------------------ estabelecimentos
  let pinos = [];
  function mostrarPois({ termo, area, itens, mais }) {
    pinos = itens;
    window.extrasHtml = window.extrasHtml.filter((x) => x.tipo !== "pino");
    for (const p of itens) {
      const el = document.createElement("div"); el.className = "pino"; el.title = `${p.nome}\n${p.endereco || ""}`;
      el.innerHTML = `<span class="pino-nome"></span>`; el.firstChild.textContent = p.nome;
      el.onclick = (ev) => { ev.stopPropagation(); abrirUnidade(p, termo); };
      window.extrasHtml.push({ tipo: "pino", lat: p.lat, lng: p.lng, el });
    }
    document.body.classList.toggle("poucos-pinos", itens.length <= 12);
    redesenhar();
    document.body.classList.add("lugar");  // o globo fica grande
    ctl.autoRotate = false; clearTimeout(voltaAGirar);
    if (!mais && itens.length) {
      const lats = itens.map((p) => p.lat), lngs = itens.map((p) => p.lng);
      const c = [Math.min(...lats) - 0.01, Math.max(...lats) + 0.01, Math.min(...lngs) - 0.01, Math.max(...lngs) + 0.01];
      voarPara(c);
      if (globo.pointOfView().altitude < 0.4 || c[1] - c[0] < 2) satelite(true);  // de perto, a foto real ajuda a achar
    }
    $("coordenadas").style.whiteSpace = "pre";
    $("coordenadas").textContent = `${itens.length} × ${termo.toUpperCase()}\n${(area?.nome || "").toUpperCase()}`;
    if (!mais) sons.trava();
  }

  // clique num pino: a unidade de perto, com a fachada (vista da rua), o nome e o endereço
  function abrirUnidade(p, termo) {
    globo.pointOfView({ lat: p.lat, lng: p.lng, altitude: 0.006 }, 1200);
    satelite(true);
    const caixa = $("sobre-globo");
    caixa.innerHTML = "";
    const c = document.createElement("article"); c.className = "cartao"; c.dataset.id = "u" + (p.id || Math.random());
    // foto da loja (Google Meu Negócio, pela API do Places, se ele pôs a chave) ou a vista de cima da quadra
    const rua = document.createElement("div");
    rua.style.cssText = "position:relative;height:280px;background:#000 center/cover no-repeat";
    const aviso = document.createElement("span");
    aviso.style.cssText = "position:absolute;right:8px;bottom:6px;font:10px Consolas,monospace;color:#fffc;text-shadow:0 0 4px #000";
    aviso.textContent = "carregando foto…";
    rua.append(aviso);
    fetch(`/api/foto_local?lat=${p.lat}&lng=${p.lng}&nome=${encodeURIComponent(p.nome)}`).then((r) => r.json()).then((f) => {
      if (f.foto) rua.style.backgroundImage = `url("${f.foto}")`;
      aviso.textContent = f.credito || "";
      if (f.endereco) end.textContent = f.endereco;
      if (f.nota) { const n = document.createElement("p"); n.className = "texto"; n.style.color = "#ffd36b";
        n.textContent = `★ ${f.nota} (${f.avaliacoes} avaliações)` + (f.aberto === true ? " · aberto agora" : f.aberto === false ? " · fechado agora" : ""); end.after(n); }
    }).catch(() => (aviso.textContent = ""));
    const leg = document.createElement("div"); leg.className = "legenda";
    const h = document.createElement("h3"); h.textContent = (termo || "Local").toUpperCase();
    const d = document.createElement("div"); d.className = "destaque"; d.textContent = p.nome;
    const end = document.createElement("p"); end.className = "texto"; end.textContent = p.endereco || `${p.lat.toFixed(5)}, ${p.lng.toFixed(5)}`;
    const botoes = document.createElement("div"); botoes.style.cssText = "display:flex;gap:8px;margin-top:10px";
    const rota = Object.assign(document.createElement("button"), { className: "pp-botao", textContent: "Rota no Maps ↗" });
    rota.onclick = () => window.open(`https://www.google.com/maps/dir/?api=1&destination=${p.lat},${p.lng}`, "_blank");  // clique dele
    const fecha = Object.assign(document.createElement("button"), { className: "pp-botao", textContent: "✕" });
    fecha.onclick = () => { caixa.innerHTML = ""; document.body.classList.remove("tem-unidade"); sons.fecha(); };
    botoes.append(rota, fecha);
    leg.append(h, d, end, botoes);
    c.append(rua, leg);
    caixa.append(c);
    document.body.classList.add("lugar", "tem-unidade");
    // o Jarvis passa a saber qual unidade é ("me fala desse lugar", "como chego lá")
    anunciar({ tipo: "local", nome: `${p.nome}${p.endereco ? ", " + p.endereco : ""}`, lat: p.lat, lng: p.lng,
               caixa: [p.lat - 0.003, p.lat + 0.003, p.lng - 0.003, p.lng + 0.003], forma: null });
    sons.popup();
  }

  // ------------------------------------------------------------ notícias
  function mostrarNoticias(p) {
    const c = document.createElement("article");
    c.className = "cartao noticias painel-pesquisa"; c.dataset.id = p.id;
    const topo = document.createElement("div"); topo.className = "pp-topo";
    const h = document.createElement("h3"); h.textContent = `Notícias · ${p.tema}`;
    const fecha = Object.assign(document.createElement("button"), { className: "pp-botao", textContent: "✕" });
    fecha.onclick = () => remover([p.id]);
    topo.append(h, fecha);
    const corpo = document.createElement("div"); corpo.style.padding = "0 18px 14px";
    p.itens.forEach((n, i) => {
      const linha = document.createElement("div"); linha.className = "nt"; linha.dataset.i = i;
      const img = document.createElement("img"); img.src = n.imagem || ""; img.alt = ""; img.loading = "lazy"; img.onerror = () => img.remove();
      if (!n.imagem) img.remove();
      const txt = document.createElement("div");
      const t = document.createElement("h4"); t.textContent = `${i + 1}. ${n.titulo}`;
      const meta = document.createElement("small");
      const min = n.quando ? Math.max(1, Math.round((Date.now() / 1000 - n.quando) / 60)) : null;
      meta.textContent = `${n.fonte.toUpperCase()}${min ? " · HÁ " + (min < 60 ? min + " MIN" : Math.round(min / 60) + " H") : ""}`;
      const f = document.createElement("p"); f.textContent = n.fala || n.resumo || "";
      txt.append(t, meta, f);
      if (n.imagem) linha.append(img);
      linha.append(txt);
      linha.onclick = () => fetch("/api/conversar", { method: "POST", headers: { "Content-Type": "application/json" },
                                                       body: JSON.stringify({ texto: `abre a notícia ${i + 1}` }) }).then((r) => r.text()).catch(() => {});
      corpo.append(linha);
    });
    c.append(topo, corpo);
    document.body.classList.remove("lugar", "silhueta");
    lista.prepend(c); podar(); atualizarEstado(); sons.popup();
  }
  function destacarNoticia(id, i) {
    const c = document.querySelector(`.noticias[data-id="${id}"]`);
    if (!c) return;
    c.querySelectorAll(".nt").forEach((el) => el.classList.toggle("lendo-agora", +el.dataset.i === i));
    const atual = c.querySelector(".lendo-agora");
    if (atual) atual.scrollIntoView({ block: "start", behavior: "smooth" });
  }

  // ------------------------------------------------------------ página do site dentro do Jarvis
  let paginaUrl = "", paginaId = "";  // o id fica aqui (no elemento, o remover() da parte 1 apagaria a moldura)
  function abrirPagina({ id, url, titulo, fonte }) {
    paginaUrl = url;
    $("pg-fonte").textContent = (fonte || "PÁGINA").toUpperCase();
    $("pg-titulo").textContent = (titulo || "").slice(0, 80);
    paginaId = id || "";
    $("pg-quadro").src = url;
    document.body.classList.add("vendo-pagina"); sons.viagem();
  }
  function fecharPagina() {
    if (!document.body.classList.contains("vendo-pagina")) return false;
    document.body.classList.remove("vendo-pagina"); $("pg-quadro").src = "about:blank"; sons.fecha();
    return true;
  }
  $("pg-fechar").onclick = fecharPagina;
  $("pg-nav").onclick = () => paginaUrl && window.open(paginaUrl, "_blank");  // clique dele = pedido dele

  // ------------------------------------------------------------ "volta o globo ao normal"
  function globoNormal() {
    document.body.classList.remove("globo-ativo");
    window.olhoCamada && ["avioes", "satelites", "terremotos", "clima", "noticias"].forEach((n) => window.olhoCamada(n, false, null, true));
    limparSelecao();
    pinos = []; window.extrasHtml = []; redesenhar();
    satelite(false);
    fecharPagina();
    document.body.classList.remove("lendo-pagina", "silhueta", "lugar", "mirando");
    if (typeof fecharStreet === "function") fecharStreet();
    selecionada = null; globo.polygonsData(paises || []); pintar();
    globo.ringsData([]).labelsData([]).arcsData([]);
    $("sobre-globo").innerHTML = ""; $("silhueta").innerHTML = "";
    globo.pointOfView({ lat: -15, lng: -50, altitude: ALTURA_PARADO() }, 1600);
    ctl.autoRotate = true;
    $("coordenadas").textContent = "ESCANEANDO · ÓRBITA BAIXA";
    sons.fecha();
  }

  window.globoNormal = globoNormal;

  // "fecha tudo" / "limpa a interface" e o X do celular: some com tudo que ele abriu (holograma, página, painéis, globo)
  window.limparPalco = () => {
    window.fecharHolograma?.();
    fecharPagina();
    document.body.classList.remove("lendo-pagina");
    $("lupa-ext")?.classList.remove("aberta");
    if (typeof lista !== "undefined") [...lista.children].forEach((el) => el.remove());
    globoNormal();
  };
  addEventListener("message", (e) => { if (e.origin === location.origin && e.data?.limpar) window.limparPalco(); });

  // ------------------------------------------------------------ câmeras públicas ao vivo (Windy)
  const cssCam = document.createElement("style");
  cssCam.textContent = `
  .cam-pino { width: 16px; height: 16px; border: 2px solid #ff3b3b; border-radius: 3px; background: #ff3b3b33; cursor: pointer;
    box-shadow: 0 0 10px #ff3b3b; pointer-events: auto; position: relative; animation: cam-pulsa 1.6s ease-in-out infinite; }
  .cam-pino.parada { border-color: #8aa; background: #8aa3; box-shadow: none; animation: none; }
  .cam-pino::after { content: ""; position: absolute; right: -6px; top: 3px; border-left: 6px solid currentColor; border-top: 4px solid transparent;
    border-bottom: 4px solid transparent; color: #ff3b3b; }
  @keyframes cam-pulsa { 50% { box-shadow: 0 0 22px #ff3b3b; transform: scale(1.15); } }
  .cartao.camera iframe, .cartao.camera img { width: 100%; aspect-ratio: 16 / 9; border: 1px solid #ff3b3b55; background: #000; display: block; margin-top: 10px; }
  .cartao.camera .ao-vivo { color: #ff3b3b; font: 11px Consolas, monospace; letter-spacing: .25em; animation: holo-pisca 1.2s infinite; }`;
  document.head.append(cssCam);
  function camerasNoGlobo(d) {
    window.extrasHtml = (window.extrasHtml || []).filter((x) => x.tipo !== "camera");
    for (const c of d.lista || []) {
      const el = document.createElement("div");
      el.className = "cam-pino" + (c.ativa ? "" : " parada"); el.title = c.nome;
      el.onclick = (ev) => { ev.stopPropagation(); abrirCamera(c); };
      window.extrasHtml.push({ tipo: "camera", lat: c.lat, lng: c.lng, el });
    }
    if (d.lugar && d.lista?.length) {
      globo.controls().autoRotate = false;
      globo.pointOfView({ lat: d.lugar.lat, lng: d.lugar.lng, altitude: 0.18 }, 2200);
      sons.viagem();
    } else if (!d.lista?.length) sons.fecha();
    window.redesenharHtml?.();
  }
  function abrirCamera(c) {
    document.querySelector(".cartao.camera")?.remove();
    const k = document.createElement("article");
    k.className = "cartao camera tom-alerta"; k.dataset.id = "cam" + c.id;
    k.innerHTML = `<h3></h3><div class="ao-vivo">● AO VIVO</div><div class="pp-resumo" style="font-size:13px"></div>`;
    k.querySelector("h3").textContent = c.nome;
    k.querySelector(".pp-resumo").textContent = c.cidade || "";
    if (c.player) { const f = document.createElement("iframe"); f.src = c.player; f.allow = "autoplay; fullscreen"; k.append(f); }
    else if (c.foto) { const i = document.createElement("img"); i.src = c.foto; k.append(i); }
    lista.prepend(k); sons.popup();
  }

  // ------------------------------------------------------------ Radar de Leads trabalhando (progresso ao vivo)
  const ROTULO_SITE = { sem_site: "sem site", rede_social: "só rede social", site_gratuito: "site gratuito", site_proprio: "site próprio" };
  function painelRadar(r) {
    let c = document.querySelector('.cartao[data-id="radar"]');
    const novo = !c;
    if (novo) {
      c = document.createElement("article"); c.className = "cartao painel-pesquisa radar-painel"; c.dataset.id = "radar";
      lista.prepend(c);
    }
    const pct = r.meta ? Math.min(100, Math.round((100 * (r.encontrados || 0)) / r.meta)) : 0;
    c.innerHTML = `<div class="pp-topo"><h3>Radar de Leads · ${r.status === "rodando" ? "varrendo o Google Maps" : (r.status || "parado")}</h3></div>
      <div class="destaque" style="padding:4px 18px 0">${r.encontrados || 0} leads novos${r.meta ? " de " + r.meta : ""}</div>
      <div style="margin:8px 18px 0;height:4px;background:var(--ciano-fraco)"><div style="height:100%;width:${pct}%;background:var(--ciano);box-shadow:0 0 10px var(--ciano);transition:width .6s"></div></div>
      <p class="pp-resumo" style="font-size:14px"></p><ul class="pp-fontes"></ul>`;
    c.querySelector(".pp-resumo").textContent = [r.busca && `Buscando: ${r.busca}`, r.progresso && `busca ${r.progresso}`, r.mensagem].filter(Boolean).join(" · ");
    const ul = c.querySelector(".pp-fontes");
    for (const l of r.leads || []) {
      const li = document.createElement("li");
      li.textContent = `${l.nome || "—"} · ${l.cidade || ""} · ${ROTULO_SITE[l.site] || l.site || ""}${l.nota ? " · ★ " + l.nota : ""}`;
      ul.append(li);
    }
    if (novo) { podar(); atualizarEstado(); sons.popup(); }
  }

  // ------------------------------------------------------------ arrastar um painel até a borda = passa pra outra tela
  // As duas telas são janelas separadas (o navegador não deixa um elemento atravessar de uma pra outra), então:
  // segurou e levou até a borda, ele "sai" daqui e o servidor manda aparecer na outra tela.
  const css2 = document.createElement("style");
  css2.textContent = `
  .arrastando { transition: none !important; z-index: 50 !important; opacity: .92; box-shadow: 0 0 40px var(--ciano) !important; cursor: grabbing; }
  .vai-sair { outline: 2px dashed var(--ciano); outline-offset: 6px; }
  .vai-sair::after { content: "SOLTE PRA MANDAR PRA OUTRA TELA"; position: absolute; left: 0; right: 0; top: -26px; text-align: center;
    font: 11px Consolas, monospace; letter-spacing: .2em; color: var(--ciano); }
  .cartao h3, .pp-topo { cursor: grab; }`;
  document.head.append(css2);
  const MARGEM = 46;
  function arrastavel(el) {
    if (el.__arrasta) return;
    el.__arrasta = true;
    el.addEventListener("pointerdown", (ev) => {
      if (ev.button !== 0 || ev.target.closest("button, a, input, textarea, select, iframe, .galeria, .pp-fontes, .nt")) return;
      const x0 = ev.clientX, y0 = ev.clientY;
      let ativo = false;
      const mover = (e) => {
        const dx = e.clientX - x0, dy = e.clientY - y0;
        if (!ativo && Math.hypot(dx, dy) < 8) return;
        if (!ativo) { ativo = true; el.classList.add("arrastando"); el.setPointerCapture?.(ev.pointerId); }
        el.style.transform = `translate(${dx}px, ${dy}px) scale(.97)`;
        const borda = e.clientX < MARGEM || e.clientY < MARGEM || e.clientX > innerWidth - MARGEM || e.clientY > innerHeight - MARGEM;
        el.classList.toggle("vai-sair", borda);
      };
      const soltar = async () => {
        removeEventListener("pointermove", mover); removeEventListener("pointerup", soltar);
        if (!ativo) return;
        const sair = el.classList.contains("vai-sair");
        el.classList.remove("arrastando", "vai-sair");
        if (!sair) { el.style.transform = ""; return; }
        el.style.transition = "opacity .25s, transform .25s"; el.style.opacity = "0";
        sons.viagem();
        const id = el.dataset.id || "";
        try {
          const r = await (await fetch("/api/mover_item", { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id, de: EMBUTIDO ? "palco" : "extensao" }) })).json();
          if (!r.ok) { el.style.opacity = ""; el.style.transform = ""; }
        } catch { el.style.opacity = ""; el.style.transform = ""; }
      };
      addEventListener("pointermove", mover); addEventListener("pointerup", soltar);
    });
  }
  new MutationObserver(() => document.querySelectorAll("#lista > .cartao, #sobre-globo > .cartao").forEach(arrastavel))
    .observe(document.body, { childList: true, subtree: true });

  // ------------------------------------------------------------ embutida: avisa o HUD quando tem algo pra mostrar
  if (EMBUTIDO) {
    let antes = null;
    const conferir = () => {
      const b = document.body.classList;
      const ativo = lista.children.length > 0 || ["lugar", "olho", "silhueta", "street", "vendo-pagina", "lendo-pagina",
        "apresentando", "globo-ativo", "tem-unidade"].some((c) => b.contains(c));
      if (ativo === antes) return;
      antes = ativo;
      try { ativo ? globo.resumeAnimation() : globo.pauseAnimation(); } catch {}  // sem nada no palco, o globo não gasta GPU
      parent.postMessage({ palco: ativo }, location.origin);
    };
    new MutationObserver(conferir).observe(document.body, { attributes: true, attributeFilter: ["class"] });
    new MutationObserver(conferir).observe(lista, { childList: true });
    setTimeout(conferir, 500);
  }

  // ------------------------------------------------------------ "que avião é esse?" / clique no avião
  function cartaoDoAviao(a) {
    const caixa = $("sobre-globo");
    caixa.innerHTML = "";
    const c = document.createElement("article"); c.className = "cartao"; c.dataset.id = "av" + (a.hex || a.id || "");
    if (a.foto) {
      const img = document.createElement("img"); img.src = a.foto; img.alt = a.modelo || "avião"; img.style.cssText = "width:100%;height:260px;object-fit:cover;display:block";
      img.onerror = () => img.remove(); c.append(img);
    }
    const leg = document.createElement("div"); leg.className = "legenda";
    const h = document.createElement("h3"); h.textContent = `VOO ${a.voo || "—"}${a.companhia ? " · " + a.companhia.toUpperCase() : ""}`;
    const d = document.createElement("div"); d.className = "destaque"; d.textContent = a.origem && a.destino ? `${a.origem} → ${a.destino}` : (a.modelo || "Avião");
    const t = document.createElement("p"); t.className = "texto";
    t.textContent = [a.modelo, a.matricula, a.alt_m ? `${Math.round(a.alt_m / 100) * 100} m` : "", a.vel_kmh ? `${a.vel_kmh} km/h` : ""].filter(Boolean).join(" · ");
    const cr = document.createElement("p"); cr.style.cssText = "margin:6px 0 0;font:10px Consolas,monospace;color:var(--apagado)"; cr.textContent = a.credito || "";
    const fecha = Object.assign(document.createElement("button"), { className: "pp-botao", textContent: "✕" });
    fecha.onclick = () => { caixa.innerHTML = ""; document.body.classList.remove("tem-unidade"); sons.fecha(); };
    leg.append(h, d, t, cr, fecha); c.append(leg); caixa.append(c);
    document.body.classList.add("lugar", "tem-unidade");
    if (a.lat != null) globo.pointOfView({ lat: a.lat, lng: a.lng, altitude: Math.max(0.12, Math.min(0.35, globo.pointOfView().altitude)) }, 1000);
    sons.trava();
  }
  window.cartaoDoAviao = cartaoDoAviao;
  window.clicarAviao = async (a) => {
    cartaoDoAviao({ ...a, modelo: a.modelo, voo: a.voo });
    const q = new URLSearchParams({ hex: a.id || "", voo: a.voo || "", tipo: a.modelo || "", alt_m: a.alt_m || 0, vel_kmh: a.vel_kmh || 0 });
    try { const d = await (await fetch("/api/aviao?" + q)).json(); cartaoDoAviao({ ...a, ...d }); } catch {}
  };

  // ------------------------------------------------------------ eventos
  fonte.addEventListener("message", (m) => {
    const e = JSON.parse(m.data);
    if (e.modo_globo) satelite(e.modo_globo !== "holograma", e.modo_globo === "nuvens" ? true : e.modo_globo === "satelite" ? false : undefined);
    if (e.mostrar_globo) document.body.classList.add("globo-ativo");
    if (e.globo_normal) globoNormal();
    if (e.pois) mostrarPois(e.pois);
    if (e.noticias) mostrarNoticias(e.noticias);
    if (e.destacar) destacarNoticia(e.destacar.id, e.destacar.i);
    if (e.pagina) abrirPagina(e.pagina);
    if (e.fechar_painel && fecharPagina()) return;
    if (e.remover && paginaId && e.remover.includes(paginaId)) fecharPagina();
    if (e.limpar_selecao) limparSelecao();
    if (e.aviao) cartaoDoAviao(e.aviao);
    if (e.radar) painelRadar(e.radar);
    if (e.cameras) camerasNoGlobo(e.cameras);
  });
})();
