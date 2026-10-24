// Hologramas 3D (three.js): apresentações ("me mostra as camadas da Terra"), peças do PC com dados ao vivo
// ("quanto de RAM tá usando") e o núcleo neural (as memórias do Jarvis num cérebro de nós ligados).
// Cada frase falada acende a peça do trecho (evento "destacar" com o id da cena); "fecha"/"oculta" some com ele.
(() => {
  if (!window.THREE) return;
  const T = THREE;
  // o palco da tela do celular (?celular): ângulo e rótulos ajustados pra tela pequena; no PC fica tudo como era
  const CELULAR_HOLO = new URLSearchParams(location.search).has("celular");
  const css = document.createElement("style");
  css.textContent = `
  #holo { position: fixed; inset: 0; z-index: 6; display: none; overflow: hidden;
    background: radial-gradient(ellipse at 50% 55%, rgba(0, 40, 60, .55), rgba(0, 6, 12, .88) 70%); }
  body.embutido #holo { background: radial-gradient(ellipse at 50% 55%, rgba(0, 40, 60, .35), rgba(0, 6, 12, .6) 75%); border-radius: 18px; }
  body.apresentando #holo { display: block; animation: holo-liga .8s ease-out; }
  #holo.saindo { animation: holo-sai .45s ease-in forwards; }
  #holo canvas { position: absolute; inset: 0; width: 100%; height: 100%; cursor: grab; }
  #holo svg { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
  #holo .h-menu { position: absolute; top: 70px; left: 18px; width: min(230px, 30%); max-height: 72%; overflow-y: auto; z-index: 3;
    background: rgba(2, 18, 26, .72); border: 1px solid rgba(120, 240, 255, .25); border-radius: 12px; padding: 10px; display: none;
    backdrop-filter: blur(4px); box-shadow: 0 0 24px rgba(0, 0, 0, .4); }
  #holo .h-menu.ver { display: block; }
  #holo .h-menu h4 { margin: 2px 0 7px; font: 700 10px Consolas, monospace; letter-spacing: .22em; color: #7fe8ff; }
  #holo .h-menu h4:not(:first-child) { margin-top: 12px; border-top: 1px dashed rgba(120, 240, 255, .18); padding-top: 10px; }
  #holo .h-menu button { display: block; width: 100%; text-align: left; margin: 3px 0; padding: 6px 9px; cursor: pointer;
    font: 12px "Segoe UI", sans-serif; color: #d6fbff; background: rgba(120, 240, 255, .06); border: 1px solid rgba(120, 240, 255, .18);
    border-radius: 7px; transition: all .15s; }
  #holo .h-menu button:hover { background: rgba(120, 240, 255, .18); border-color: #4fe3ff; }
  #holo .h-menu button.ativa { background: rgba(79, 227, 255, .22); border-color: #4fe3ff; color: #fff; }
  #holo .h-menu button i { width: 9px; height: 9px; display: inline-block; border-radius: 50%; margin-right: 7px; vertical-align: middle; box-shadow: 0 0 6px currentColor; }
  #holo .h-menu-btn { position: absolute; top: 18px; left: 18px; z-index: 4; width: 36px; height: 36px; cursor: pointer; border-radius: 9px;
    background: rgba(2, 18, 26, .72); border: 1px solid rgba(120, 240, 255, .3); color: #7fe8ff; font-size: 16px; display: none; }
  body.apresentando #holo .h-menu-btn { display: block; }
  html.holo-celular #holo .h-menu { top: 58px; width: 46%; max-height: 40%; font-size: 11px; }
  #holo .h-titulo { position: absolute; top: 16px; left: 0; right: 0; text-align: center; font: 600 20px/1.2 "Segoe UI", sans-serif;
    letter-spacing: .32em; text-transform: uppercase; color: #8ff3ff; text-shadow: 0 0 18px #2ad4ff; pointer-events: none; }
  #holo .h-titulo small { display: block; margin-top: 6px; font: 11px Consolas, monospace; letter-spacing: .3em; color: #5fb8c8; }
  #holo .h-rot { position: absolute; transform: translate(0, -50%); font: 12px Consolas, monospace; letter-spacing: .1em; color: var(--c, #c8fbff);
    padding: 4px 9px; border: 1px solid color-mix(in srgb, var(--c, #4fe3ff) 45%, transparent); border-left-width: 3px; background: rgba(0, 18, 28, .7); white-space: nowrap; pointer-events: none;
    transition: opacity .35s, box-shadow .35s, border-color .35s, color .35s; }
  #holo .h-rot.esq { transform: translate(-100%, -50%); }
  #holo .h-rot.aceso { color: #fff; border-color: var(--c); box-shadow: 0 0 16px var(--c), inset 0 0 10px var(--c); }
  #holo .h-rot.apagado { opacity: .22; }
  #holo .h-dados { position: absolute; top: 70px; right: 22px; width: min(320px, 34%); font: 13px/1.5 Consolas, monospace; color: #c8fbff;
    border: 1px solid rgba(120, 240, 255, .4); background: rgba(0, 18, 28, .72); padding: 12px 14px; display: none;
    box-shadow: 0 0 24px rgba(0, 200, 255, .15); animation: holo-entra .6s ease-out; }
  #holo .h-dados.ver { display: block; }
  #holo .h-dados b { display: block; color: #8ff3ff; letter-spacing: .2em; font-size: 11px; margin-bottom: 6px; }
  #holo .h-dados .lin { display: flex; justify-content: space-between; gap: 10px; border-bottom: 1px dashed rgba(120, 240, 255, .15); padding: 3px 0; }
  #holo .h-dados .lin span:last-child { color: #fff; text-align: right; }
  #holo .h-dados .barra { height: 5px; background: rgba(120, 240, 255, .15); margin: 6px 0 2px; }
  #holo .h-dados .barra i { display: block; height: 100%; background: #4fe3ff; box-shadow: 0 0 10px #4fe3ff; transition: width .8s; }
  #holo .h-texto { position: absolute; left: 50%; bottom: 24px; transform: translateX(-50%); width: min(820px, 80%); text-align: center;
    font: 17px/1.45 "Segoe UI", sans-serif; color: #e0fdff; text-shadow: 0 0 12px rgba(0, 200, 255, .7); pointer-events: none; min-height: 1em; }
  #holo .h-texto.troca { animation: holo-entra .5s ease-out; }
  #holo .h-scan { position: absolute; inset: 0; pointer-events: none; mix-blend-mode: screen;
    background: repeating-linear-gradient(0deg, rgba(120, 240, 255, .045) 0 1px, transparent 1px 4px); }
  #holo .h-varre { position: absolute; left: 0; right: 0; height: 140px; top: -140px; pointer-events: none;
    background: linear-gradient(transparent, rgba(120, 240, 255, .14), transparent); animation: holo-varre 3.4s linear infinite; }
  #holo .h-carrega { position: absolute; inset: 0; display: none; place-items: center; font: 12px Consolas, monospace; letter-spacing: .5em;
    color: #8ff3ff; text-shadow: 0 0 12px #2ad4ff; pointer-events: none; }
  #holo.carregando .h-carrega { display: grid; animation: holo-pisca 1s ease-in-out infinite; }
  #holo .h-fechar { position: absolute; top: 12px; right: 14px; width: 32px; height: 32px; border: 1px solid rgba(120, 240, 255, .4);
    background: rgba(0, 18, 28, .7); color: #8ff3ff; font-size: 15px; cursor: pointer; }
  #holo .h-fechar:hover { box-shadow: 0 0 14px #2ad4ff; }
  @keyframes holo-liga { 0% { opacity: 0; filter: brightness(3) blur(8px); clip-path: inset(49% 0 49% 0); }
    45% { opacity: 1; clip-path: inset(0 0 0 0); } 100% { filter: none; } }
  @keyframes holo-sai { to { opacity: 0; filter: brightness(2.5) blur(6px); clip-path: inset(49% 0 49% 0); } }
  @keyframes holo-varre { to { top: 100%; } }
  @keyframes holo-entra { from { opacity: 0; transform: translateY(8px); filter: brightness(2); } }
  #holo .h-dados { animation: holo-entra .6s ease-out; }
  @keyframes holo-pisca { 50% { opacity: .35; } }
  /* só no palco do celular (tela estreita): tudo dentro da margem, dados embaixo, letras menores */
  @media (max-width: 700px) {
    html.holo-celular #holo .h-titulo { top: 10px; font-size: 14px; letter-spacing: .18em; padding: 0 44px; }
    html.holo-celular #holo .h-titulo small { font-size: 9px; letter-spacing: .2em; }
    html.holo-celular #holo .h-rot { font-size: 10px; padding: 2px 6px; letter-spacing: .04em; max-width: 42vw; overflow: hidden; text-overflow: ellipsis; }
    html.holo-celular #holo .h-dados { top: auto; bottom: 64px; left: 10px; right: 10px; width: auto; max-height: 32%; overflow-y: auto; font-size: 11px; padding: 8px 10px; }
    html.holo-celular #holo .h-texto { bottom: 10px; width: calc(100% - 24px); font-size: 14px; }
    html.holo-celular #holo .h-fechar { top: 6px; right: 6px; }
  }`;
  document.head.append(css);
  if (CELULAR_HOLO) document.documentElement.classList.add("holo-celular");

  // ------------------------------------------------------------ sons do holograma (sintetizados)
  let actx = null;
  function som(freq, ini, dur, vol = 0.04, tipo = "sine", ate = null) {
    try {
      actx = actx || new AudioContext();
      const t0 = actx.currentTime + ini, o = actx.createOscillator(), g = actx.createGain();
      o.type = tipo; o.frequency.setValueAtTime(freq, t0);
      if (ate) o.frequency.exponentialRampToValueAtTime(ate, t0 + dur);
      g.gain.setValueAtTime(0.0001, t0); g.gain.exponentialRampToValueAtTime(vol, t0 + 0.015); g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
      o.connect(g).connect(actx.destination); o.start(t0); o.stop(t0 + dur + 0.05);
    } catch {}
  }
  function chiado(dur = 0.5, vol = 0.03, de = 3000, ate = 300) {
    try {
      actx = actx || new AudioContext();
      const n = actx.sampleRate * dur, buf = actx.createBuffer(1, n, actx.sampleRate), d = buf.getChannelData(0);
      for (let i = 0; i < n; i++) d[i] = Math.random() * 2 - 1;
      const src = actx.createBufferSource(), f = actx.createBiquadFilter(), g = actx.createGain(), t0 = actx.currentTime;
      src.buffer = buf; f.type = "bandpass"; f.Q.value = 3;
      f.frequency.setValueAtTime(de, t0); f.frequency.exponentialRampToValueAtTime(ate, t0 + dur);
      g.gain.setValueAtTime(vol, t0); g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
      src.connect(f).connect(g).connect(actx.destination); src.start();
    } catch {}
  }
  const somH = {
    liga() { som(90, 0, 0.9, 0.06, "sawtooth", 260); som(520, 0.15, 0.5, 0.025, "sine", 1560); chiado(0.8, 0.03, 400, 4000); [0, .08, .16].forEach((t, i) => som(1800 + i * 400, 0.5 + t, 0.05, 0.02, "triangle")); },
    peca(i) { som(900 + i * 140, 0, 0.06, 0.018, "triangle"); },
    passo() { som(1320, 0, 0.07, 0.03, "sine"); som(1980, 0.07, 0.09, 0.025, "sine"); },
    abre() { chiado(0.55, 0.04, 200, 2600); som(140, 0, 0.5, 0.04, "sawtooth", 70); },
    junta() { chiado(0.4, 0.03, 2600, 300); },
    sai() { som(1200, 0, 0.4, 0.04, "sine", 140); chiado(0.35, 0.025, 3000, 200); },
    dado() { som(2400, 0, 0.03, 0.015, "square"); },
  };

  // ------------------------------------------------------------ cena
  let el, canvas, svg, ren, cena, cam, grupo, rede = null, raf = 0, atual = null, modeloAtual = null;
  let pecas = [], giroX = 0.32, giroY = 0, zoom = 7.5, zoomAlvo = 7.5, explode = 0, explodeAlvo = 0, arrastou = 0, inicio = 0, apertado = null;

  function montarDom() {
    if (el) return;
    el = document.createElement("div"); el.id = "holo";
    el.innerHTML = `<canvas></canvas><svg></svg><div class="h-scan"></div><div class="h-varre"></div>
      <div class="h-titulo"></div><div class="h-dados"></div><div class="h-texto"></div>
      <button class="h-menu-btn" title="Partes">☰</button><div class="h-menu"></div>
      <div class="h-carrega">MONTANDO HOLOGRAMA</div><button class="h-fechar" title="Fechar">✕</button>`;
    document.body.append(el);
    el.querySelector(".h-menu-btn").onclick = () => el.querySelector(".h-menu").classList.toggle("ver");
    canvas = el.querySelector("canvas"); svg = el.querySelector("svg");
    ren = new T.WebGLRenderer({ canvas, antialias: true, alpha: true });
    ren.setPixelRatio(Math.min(2, devicePixelRatio || 1));
    cam = new T.PerspectiveCamera(38, 1, 0.1, 200);
    cena = new T.Scene();
    cena.add(new T.AmbientLight(0x7fd8ff, 0.7));
    const l1 = new T.PointLight(0xffffff, 1.1); l1.position.set(6, 7, 9); cena.add(l1);
    const l2 = new T.PointLight(0x2ad4ff, 0.8); l2.position.set(-7, -3, -5); cena.add(l2);
    const grade = new T.PolarGridHelper(5.5, 24, 10, 96, 0x2aa8c8, 0x0b3f4d);
    grade.position.y = -2.6; grade.material.transparent = true; grade.material.opacity = 0.3; cena.add(grade);
    // poeira holográfica
    const pts = new T.BufferGeometry(), arr = new Float32Array(600 * 3);
    for (let i = 0; i < arr.length; i++) arr[i] = (Math.random() - 0.5) * 16;
    pts.setAttribute("position", new T.BufferAttribute(arr, 3));
    const poeira = new T.Points(pts, new T.PointsMaterial({ color: 0x5fe8ff, size: 0.025, transparent: true, opacity: 0.55 }));
    poeira.name = "poeira"; cena.add(poeira);
    grupo = new T.Group(); cena.add(grupo);
    // mouse: arrastar gira, roda aproxima
    canvas.addEventListener("pointerdown", (e) => { apertado = { x: e.clientX, y: e.clientY, gx: giroX, gy: giroY }; canvas.setPointerCapture(e.pointerId); canvas.style.cursor = "grabbing"; });
    canvas.addEventListener("pointermove", (e) => {
      if (!apertado) return;
      giroY = apertado.gy + (e.clientX - apertado.x) * 0.008;
      giroX = Math.max(-1.2, Math.min(1.2, apertado.gx + (e.clientY - apertado.y) * 0.006));
      arrastou = performance.now();
    });
    canvas.addEventListener("pointerup", () => { apertado = null; canvas.style.cursor = "grab"; });
    canvas.addEventListener("wheel", (e) => { e.preventDefault(); zoomAlvo = Math.max(2.5, Math.min(18, zoomAlvo * (e.deltaY > 0 ? 1.1 : 0.9))); }, { passive: false });
    el.querySelector(".h-fechar").onclick = () => {
      fechar();
      fetch("/api/holo/fechado", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: atual?.id || "" }) }).catch(() => {});
    };
    new ResizeObserver(redimensionar).observe(el);
  }

  function redimensionar() {
    const w = el.clientWidth || innerWidth, h = el.clientHeight || innerHeight;
    ren.setSize(w, h, false); cam.aspect = w / h;
    // tela em pé (celular): abre o ângulo pra largura caber inteira, o holograma não corta dos lados
    const largura = 2 * Math.atan(Math.tan((38 / 2) * Math.PI / 180) * 1.3);
    cam.fov = CELULAR_HOLO && cam.aspect < 1.3 ?Math.min(100, 2 * Math.atan(Math.tan(largura / 2) / cam.aspect) * 180 / Math.PI) : 38;
    cam.updateProjectionMatrix();
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  }

  function geometria(p) {
    const t = p.tam || [0.8];
    switch (p.forma) {
      case "esfera": return new T.SphereGeometry(t[0], 48, 32);
      case "esfera_cortada": return new T.SphereGeometry(t[0], 64, 40, 0, Math.PI * 1.5);
      case "cilindro": return new T.CylinderGeometry(t[0], t[0], t[1] ?? t[0] * 2, 40, 1, false);
      case "cone": return new T.ConeGeometry(t[0], t[1] ?? t[0] * 2, 40);
      case "toro": return new T.TorusGeometry(t[0], t[1] ?? t[0] / 4, 20, 64);
      default: return new T.BoxGeometry(t[0], t[1] ?? t[0], t[2] ?? t[0]);
    }
  }

  function limparCena() {
    for (const p of pecas) { p.rot?.remove(); p.linha?.remove(); }
    pecas = [];
    while (grupo.children.length) {
      const c = grupo.children.pop();
      c.traverse?.((o) => { o.geometry?.dispose(); o.material?.dispose?.(); });
    }
    rede = null; modeloAtual = null;
    el.querySelector(".h-dados").classList.remove("ver");
  }

  // ------------------------------------------------------------ modelo 3D real (.glb), ex.: corpo humano em raio-x
  function montarModelo(c) {
    if (!T.GLTFLoader) { el.querySelector(".h-texto").textContent = "Modelo 3D indisponível (GLTFLoader não carregou)."; return; }
    new T.GLTFLoader().load(c.modelo, (gltf) => {
      if (atual !== c) return;  // trocou de cena enquanto baixava
      const raiox = c.estilo === "raiox";
      const obj = gltf.scene;
      obj.traverse((o) => {
        if (!o.isMesh) return;
        o.material = raiox
          ? new T.MeshPhongMaterial({ color: 0x4aa8ff, emissive: 0x1f6fd0, transparent: true, opacity: 0.3,
              side: T.DoubleSide, depthWrite: false, blending: T.AdditiveBlending, shininess: 70 })
          : new T.MeshStandardMaterial({ color: 0xd8c6b0, roughness: 0.8, metalness: 0 });
      });
      const box = new T.Box3().setFromObject(obj);
      const size = box.getSize(new T.Vector3()), centro = box.getCenter(new T.Vector3());
      const escala = 4.8 / (Math.max(size.x, size.y, size.z) || 1);
      obj.scale.setScalar(escala);
      obj.position.copy(centro).multiplyScalar(-escala);
      grupo.add(obj); modeloAtual = obj;
      el.classList.remove("carregando");
      zoomAlvo = c.zoom || 11;
    }, undefined, () => { if (atual === c) el.querySelector(".h-texto").textContent = "Não consegui carregar o modelo 3D, chefe."; });
  }

  function montarPecas(lista) {
    lista.forEach((p, i) => {
      const cor = new T.Color(p.cor || "#4fe3ff");
      const geo = geometria(p);
      const fantasma = !!p.fantasma;
      const solido = !!p.solido;  // órgãos/coisas "de verdade": preenchimento opaco, não o wireframe fantasma
      // estilo "contorno" (igual o globo holograma): preenchimento quase transparente, contorno forte e uma grade fina
      const mat = solido
        ? new T.MeshPhongMaterial({ color: cor, emissive: cor.clone().multiplyScalar(0.12), transparent: true, opacity: 0.9,
            shininess: 35, side: T.FrontSide, depthWrite: true })
        : new T.MeshPhongMaterial({ color: cor, emissive: cor.clone().multiplyScalar(0.5), transparent: true, opacity: fantasma ? 0.02 : 0.07,
            shininess: 90, side: T.DoubleSide, depthWrite: false, blending: T.AdditiveBlending });
      const malha = new T.Mesh(geo, mat);
      let grade = null;
      if (!(p.forma.startsWith("esfera") || p.forma === "toro")) {
        const t = p.tam || [0.8];
        const seg = (x) => Math.max(1, Math.min(8, Math.round((x ?? t[0]) / 0.25)));
        const g2 = p.forma === "cilindro" || p.forma === "cone"
          ? (p.forma === "cone" ? new T.ConeGeometry(t[0], t[1] ?? t[0] * 2, 16, 3, true) : new T.CylinderGeometry(t[0], t[0], t[1] ?? t[0] * 2, 16, 3, true))
          : new T.BoxGeometry(t[0], t[1] ?? t[0], t[2] ?? t[0], seg(t[0]), seg(t[1]), seg(t[2]));
        grade = new T.LineSegments(new T.WireframeGeometry(g2), new T.LineBasicMaterial({ color: cor, transparent: true, opacity: fantasma ? 0.05 : 0.16,
          blending: T.AdditiveBlending, depthWrite: false }));
      }
      const arestas = p.forma.startsWith("esfera") || p.forma === "toro"
        ? new T.LineSegments(new T.WireframeGeometry(p.forma === "toro" ? new T.TorusGeometry(p.tam[0], p.tam[1] ?? p.tam[0] / 4, 8, 24)
            : new T.SphereGeometry(p.tam[0], 20, 12, 0, p.forma === "esfera_cortada" ? Math.PI * 1.5 : Math.PI * 2)),
            new T.LineBasicMaterial({ color: cor, transparent: true, opacity: 0.35, blending: T.AdditiveBlending, depthWrite: false }))
        : new T.LineSegments(new T.EdgesGeometry(geo, 20), new T.LineBasicMaterial({ color: cor, transparent: true, opacity: 0.95 }));
      const g = new T.Group(); g.add(malha, arestas); if (grade) g.add(grade);
      const pos = new T.Vector3(...(p.pos || [0, 0, 0]));
      g.position.copy(pos); g.rotation.set(...(p.rot || [0, 0, 0])); g.scale.setScalar(0.001);
      grupo.add(g);
      const rot = document.createElement("div");
      rot.className = "h-rot"; rot.textContent = p.nome; rot.style.setProperty("--c", p.cor || "#4fe3ff");
      el.append(rot);
      const linha = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
      linha.setAttribute("fill", "none"); linha.setAttribute("stroke", p.cor || "#4fe3ff"); linha.setAttribute("stroke-width", "1"); linha.setAttribute("opacity", ".7");
      svg.append(linha);
      pecas.push({ p, g, mat, solido, linhaMat: arestas.material, base: pos, explode: new T.Vector3(...(p.explode || [0, 0, 0])),
                   ancora: p.ancora ? new T.Vector3(...p.ancora) : null, opBase: fantasma ? 0.02 : solido ? 0.9 : 0.07, op: fantasma ? 0.02 : solido ? 0.9 : 0.07, grade,
                   linhaBase: p.forma.startsWith("esfera") || p.forma === "toro" ? 0.35 : 0.95,
                   aceso: false, nasce: 300 + i * 220, rot, linha, somou: false, i });
    });
  }

  // núcleo neural: cada memória é um neurônio, ligado aos mais parecidos (mesmo grupo)
  function montarRede(r) {
    const grupos = r.grupos || [];
    const cores = ["#4fe3ff", "#c77dff", "#ffd23d", "#2ee88a", "#ff5d8f", "#ff9b3d", "#9ad8ff", "#7cff6b"];
    const nos = [], posicoes = [];
    grupos.forEach((gr, gi) => {
      const ang = (gi / Math.max(1, grupos.length)) * Math.PI * 2;
      const centro = new T.Vector3(Math.cos(ang) * 3.1, Math.sin(gi * 1.7) * 1.1, Math.sin(ang) * 3.1);
      const cor = new T.Color(cores[gi % cores.length]);
      // o "lobo": um nó maior com o nome do grupo
      const lobo = new T.Mesh(new T.SphereGeometry(0.3, 24, 16), new T.MeshBasicMaterial({ color: cor, transparent: true, opacity: 0.95 }));
      lobo.position.copy(centro); grupo.add(lobo);
      const halo = new T.Mesh(new T.SphereGeometry(0.7, 24, 16), new T.MeshBasicMaterial({ color: cor, transparent: true, opacity: 0.1, depthWrite: false }));
      halo.position.copy(centro); grupo.add(halo);
      const rot = document.createElement("div"); rot.className = "h-rot"; rot.style.setProperty("--c", cores[gi % cores.length]);
      rot.textContent = `${gr.nome} · ${gr.itens.length}`; el.append(rot);
      const linha = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
      linha.setAttribute("fill", "none"); linha.setAttribute("stroke", cores[gi % cores.length]); linha.setAttribute("opacity", ".6"); svg.append(linha);
      pecas.push({ p: { nome: gr.nome }, g: lobo, halo, mat: lobo.material, base: centro.clone(), explode: new T.Vector3(), ancora: null, opBase: 0.95, op: 0.95,
                   nasce: 200 + gi * 260, rot, linha, i: gi, lobo: true });
      gr.itens.forEach((it, k) => {
        const v = new T.Vector3((Math.random() - 0.5), (Math.random() - 0.5), (Math.random() - 0.5)).normalize().multiplyScalar(0.8 + Math.random() * 1.0);
        const pos = centro.clone().add(v);
        const no = new T.Mesh(new T.SphereGeometry(it.novo ? 0.13 : 0.075, 12, 10), new T.MeshBasicMaterial({ color: it.novo ? 0xffffff : cor, transparent: true, opacity: 0.9 }));
        no.position.copy(pos); no.userData = { texto: it.texto, grupo: gi, fase: Math.random() * 6, nasce: 600 + gi * 260 + k * 40, novo: it.novo };
        no.scale.setScalar(0.001); grupo.add(no); nos.push(no); posicoes.push(centro, pos);
      });
    });
    // o núcleo no meio (o "eu" do Jarvis), ligado a todos os lobos, e os lobos ligados entre si
    const meio = new T.Vector3();
    const nucleo = new T.Mesh(new T.IcosahedronGeometry(0.75, 1), new T.MeshBasicMaterial({ color: 0x4fe3ff, wireframe: true, transparent: true, opacity: 0.55 }));
    const brilho = new T.Mesh(new T.SphereGeometry(0.45, 24, 16), new T.MeshBasicMaterial({ color: 0x9ff6ff, transparent: true, opacity: 0.5 }));
    nucleo.name = "nucleo"; grupo.add(nucleo, brilho);
    for (const pc of pecas) posicoes.push(meio, pc.base);
    for (let a = 0; a < pecas.length; a++) for (let b = a + 1; b < pecas.length; b++) posicoes.push(pecas[a].base, pecas[b].base);
    const geo = new T.BufferGeometry().setFromPoints(posicoes);
    const sinapses = new T.LineSegments(geo, new T.LineBasicMaterial({ color: 0x4fe3ff, transparent: true, opacity: 0.3 }));
    grupo.add(sinapses);
    // impulsos correndo pelas ligações
    const pulsos = [];
    for (let i = 0; i < 40; i++) {
      const m = new T.Mesh(new T.SphereGeometry(0.05, 8, 6), new T.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.95 }));
      grupo.add(m); pulsos.push({ m, par: Math.floor(Math.random() * (posicoes.length / 2)), t: Math.random(), v: 0.004 + Math.random() * 0.01 });
    }
    rede = { nos, posicoes, pulsos, cores };
  }

  function dados(painel) {
    const d = el.querySelector(".h-dados");
    if (!painel) { d.classList.remove("ver"); return; }
    d.innerHTML = `<b>${painel.titulo || "DADOS"}</b>`;
    for (const [k, v] of painel.linhas || []) {
      const l = document.createElement("div"); l.className = "lin";
      l.innerHTML = "<span></span><span></span>"; l.children[0].textContent = k; l.children[1].textContent = v; d.append(l);
    }
    if (painel.uso != null) {
      const cor = painel.uso >= 85 ? "#ff3b3b" : painel.uso >= 60 ? "#ff9b3d" : "#2ee88a";  // vermelho = apertado
      const b = document.createElement("div"); b.className = "barra"; b.innerHTML = "<i></i>"; d.append(b);
      b.firstChild.style.background = cor; b.firstChild.style.boxShadow = `0 0 10px ${cor}`;
      d.style.borderColor = cor + "99";
      requestAnimationFrame(() => (b.firstChild.style.width = Math.max(1, Math.min(100, painel.uso)) + "%"));
    }
    for (const l of d.querySelectorAll(".lin")) if (/^aten/i.test(l.children[0].textContent)) l.style.color = "#ff5050";
    d.classList.remove("ver"); void d.offsetWidth; d.classList.add("ver");
    somH.dado();
  }

  function abrir(c) {
    montarDom();
    const mesma = atual && atual.id === c.id;
    atual = c;
    document.body.classList.add("apresentando");
    el.classList.remove("saindo");
    el.querySelector(".h-titulo").innerHTML = "";
    el.querySelector(".h-titulo").append(document.createTextNode(c.titulo || ""));
    if (c.subtitulo) { const s = document.createElement("small"); s.textContent = c.subtitulo; el.querySelector(".h-titulo").append(s); }
    el.classList.toggle("carregando", !!c.carregando);
    redimensionar();
    if (c.carregando) { if (!mesma) somH.liga(); limparCena(); arrancar(); return; }
    if (mesma && c.so_dados) { dados(c.dados); return; }
    limparCena();
    if (c.modelo) montarModelo(c); else if (c.rede) montarRede(c.rede); else montarPecas(c.partes || []);
    montarMenu(c);
    dados(c.dados);
    let raio = 2.2;
    for (const p of c.partes || []) {
      const v = new T.Vector3(...(p.pos || [0, 0, 0])).add(new T.Vector3(...(p.explode || [0, 0, 0])));
      raio = Math.max(raio, v.length() + Math.max(...(p.tam || [0.8])) * (p.forma?.startsWith("esfera") ? 1 : 0.6));
    }
    explode = explodeAlvo = 0; zoomAlvo = c.zoom || (c.rede ? 13 : Math.min(16, raio * 2.9)); zoom = zoomAlvo * 1.6; giroY = 0; giroX = 0.32;
    inicio = performance.now();
    el.querySelector(".h-texto").textContent = c.intro || "";
    if (!mesma) somH.liga();
    arrancar();
    clearInterval(autoPasso);
    if (c.auto && c.passos?.length) {
      let i = -1;
      autoPasso = setInterval(() => { if (atual !== c) return clearInterval(autoPasso); i = (i + 1) % c.passos.length; passo(i); }, 6500);
    }
  }
  let autoPasso = 0;

  function passo(i) {
    if (!atual) return;
    const s = i >= 0 ? (atual.passos || [])[i] : null;
    const acesos = new Set(s?.destaque || []);
    for (const p of pecas) {
      p.aceso = acesos.has(p.p.nome);
      p.op = acesos.size ? (p.aceso ? (p.solido ? 1 : 0.28) : p.opBase * (p.solido ? 0.5 : 0.3)) : p.opBase;
      p.rot.classList.toggle("aceso", p.aceso);
      p.rot.classList.toggle("apagado", acesos.size > 0 && !p.aceso);
    }
    const novo = s ? (s.explodir ? 1 : 0) : 0;
    if (novo !== explodeAlvo) (novo ? somH.abre : somH.junta)();
    explodeAlvo = novo;
    if (s?.dados) dados(s.dados);
    const t = el.querySelector(".h-texto");
    t.textContent = s ? s.fala : atual.intro || "";
    t.classList.remove("troca"); void t.offsetWidth; t.classList.add("troca");
    somH.passo();
  }

  // ------------------------------------------------------------ janelinha de anatomia (filtrar partes e trocar de sistema)
  const SISTEMAS = [
    ["Corpo humano", "mostra o corpo humano"], ["Esqueleto", "mostra o esqueleto"], ["Músculos", "mostra os músculos"],
    ["Sistema nervoso", "mostra o sistema nervoso"], ["Crânio", "mostra o crânio"], ["Coração", "mostra o coração"],
    ["Cérebro", "mostra o cérebro humano"],
  ];
  function trocarSistema(cmd) {
    fetch("/api/holograma/mostrar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ assunto: cmd }) }).catch(() => {});
  }
  function focarParte(nome, btn) {
    const i = (atual && atual.passos || []).findIndex((s) => (s.destaque || []).includes(nome));
    passo(i >= 0 ? i : -1);
    for (const b of el.querySelectorAll(".h-menu .parte")) b.classList.toggle("ativa", b === btn);
  }
  function montarMenu(c) {
    const m = el && el.querySelector(".h-menu"); if (!m) return;
    m.innerHTML = "<h4>SISTEMAS</h4>";
    for (const [rot, cmd] of SISTEMAS) {
      const b = document.createElement("button"); b.textContent = rot; b.onclick = () => trocarSistema(cmd); m.append(b);
    }
    const partes = (c.partes || []).filter((p) => !p.sem_rotulo);
    if (partes.length) {
      const h = document.createElement("h4"); h.textContent = "PARTES"; m.append(h);
      for (const p of partes) {
        const b = document.createElement("button"); b.className = "parte";
        b.innerHTML = `<i style="color:${p.cor || "#4fe3ff"}"></i>${p.nome}`;
        b.onclick = () => focarParte(p.nome, b); m.append(b);
      }
    }
    m.classList.toggle("ver", partes.length > 0 && !CELULAR_HOLO);
  }

  function fechar() {
    if (!el || !document.body.classList.contains("apresentando")) return;
    somH.sai();
    el.classList.add("saindo");
    setTimeout(() => {
      document.body.classList.remove("apresentando");
      el.classList.remove("saindo");
      limparCena(); atual = null;
      cancelAnimationFrame(raf); raf = 0;
    }, 450);
  }
  window.fecharHolograma = fechar;

  // ------------------------------------------------------------ animação
  const tmp = new T.Vector3();
  function arrancar() { if (!raf) raf = requestAnimationFrame(quadro); }
  function quadro(agora) {
    raf = requestAnimationFrame(quadro);
    if (document.hidden) return;
    const t = (agora - inicio) / 1000;
    zoom += (zoomAlvo - zoom) * 0.06;
    explode += (explodeAlvo - explode) * 0.05;
    if (!apertado && agora - arrastou > 4000) giroY += 0.0025;  // gira sozinho, devagar, até ele mexer
    cam.position.set(Math.sin(giroY) * Math.cos(giroX) * zoom, Math.sin(giroX) * zoom, Math.cos(giroY) * Math.cos(giroX) * zoom);
    cam.lookAt(0, 0, 0);
    const poeira = cena.getObjectByName("poeira"); if (poeira) poeira.rotation.y += 0.0006;
    for (const p of pecas) {
      const k = Math.min(1, Math.max(0, (agora - inicio - p.nasce) / 650));
      if (k > 0 && !p.somou) { p.somou = true; somH.peca(p.i); }
      const e = 1 - Math.pow(1 - k, 3);
      const pulso = p.aceso ? 1 + Math.sin(agora / 180) * 0.035 : 1;
      p.g.scale.setScalar(Math.max(0.001, e * pulso));
      p.g.position.copy(p.base).addScaledVector(p.explode, explode);
      if (p.halo) { p.halo.position.copy(p.g.position); p.halo.scale.setScalar(1 + Math.sin(agora / 400 + p.i) * 0.15); }
      p.mat.opacity += ((p.op * (0.88 + Math.sin(agora / 90 + p.i) * 0.04)) - p.mat.opacity) * 0.1;  // tremidinha de holograma
      if (p.linhaMat) {
        const apagado = pecas.some((x) => x.aceso) && !p.aceso;
        p.linhaMat.opacity = p.aceso ? 1 : apagado ? (p.linhaBase ?? 0.9) * 0.18 : (p.linhaBase ?? 0.9);
        if (p.grade) p.grade.material.opacity = p.aceso ? 0.45 : apagado ? 0.03 : 0.16;
      }
    }
    if (rede) {
      const nu = grupo.getObjectByName("nucleo");
      if (nu) { nu.rotation.y += 0.01; nu.rotation.x += 0.004; nu.scale.setScalar(1 + Math.sin(agora / 350) * 0.06); }
      for (const n of rede.nos) {
        const k = Math.min(1, Math.max(0, (agora - inicio - n.userData.nasce) / 500));
        n.scale.setScalar(Math.max(0.001, k * (1 + Math.sin(agora / 300 + n.userData.fase) * (n.userData.novo ? 0.5 : 0.25))));
      }
      for (const pu of rede.pulsos) {
        pu.t += pu.v;
        if (pu.t > 1) { pu.t = 0; pu.par = Math.floor(Math.random() * (rede.posicoes.length / 2)); }
        pu.m.position.lerpVectors(rede.posicoes[pu.par * 2], rede.posicoes[pu.par * 2 + 1], pu.t);
      }
    }
    ren.render(cena, cam);
    rotulos();
  }

  function rotulos() {
    const w = el.clientWidth, h = el.clientHeight, cx = w / 2;
    const painel = el.querySelector(".h-dados");
    // rótulo não invade o painel de dados (no celular o painel fica embaixo, não do lado)
    const limiteDir = CELULAR_HOLO ? w - 8 : painel.classList.contains("ver") ? painel.offsetLeft - 16 : w - 16;
    const lados = { esq: [], dir: [] };
    for (const p of pecas) {
      tmp.copy(p.ancora || new T.Vector3()).applyEuler(p.g.rotation);
      if (!p.ancora) tmp.set(0, 0, 0);
      tmp.add(p.g.position).applyMatrix4(grupo.matrixWorld).project(cam);
      const x = (tmp.x + 1) / 2 * w, y = (1 - tmp.y) / 2 * h;
      const visivel = p.g.scale.x > 0.3 && tmp.z < 1 && !p.p.sem_rotulo;
      (x < cx ? lados.esq : lados.dir).push({ p, x, y, visivel });
    }
    for (const [lado, lista] of Object.entries(lados)) {
      lista.sort((a, b) => a.y - b.y);
      let ultimoY = -1e9;
      for (const r of lista) {
        let ty = Math.max(r.y, ultimoY + 30);
        if (CELULAR_HOLO) ty = Math.max(40, Math.min(h - 40, ty));  // no celular nunca sai por cima/baixo
        ultimoY = ty;
        let tx = lado === "esq" ? Math.min(r.x - 60, cx - w * 0.2) : Math.max(r.x + 60, cx + w * 0.2);
        if (lado === "dir") tx = Math.min(tx, limiteDir - (r.p.rot.offsetWidth || 160));
        else tx = Math.max(tx, (r.p.rot.offsetWidth || 160) + (CELULAR_HOLO ? 8 : 12));
        if (CELULAR_HOLO) tx = Math.max(8, Math.min(w - 8, tx));
        r.p.rot.style.left = tx + "px"; r.p.rot.style.top = ty + "px";
        r.p.rot.classList.toggle("esq", lado === "esq");
        r.p.rot.style.display = r.visivel ? "" : "none";
        r.p.linha.setAttribute("points", r.visivel ? `${r.x},${r.y} ${(r.x + tx) / 2},${ty} ${tx},${ty}` : "");
      }
    }
  }

  // ------------------------------------------------------------ eventos do servidor
  fonte.addEventListener("message", (m) => {
    const e = JSON.parse(m.data);
    if (e.apresentacao) abrir(e.apresentacao);
    if (e.holo_dados && atual && e.holo_dados.id === atual.id) dados(e.holo_dados.dados);
    if (e.destacar && atual && e.destacar.id === atual.id) passo(e.destacar.i);
    if (e.fechar_holo) fechar();
    if (e.remover && atual && e.remover.includes(atual.id)) fechar();
  });
})();
