/* OFICINA holográfica — bancada de montagem por GESTOS (pinça=pega, toque=clica, encaixe magnético + ANIMAÇÃO).
   Ao abrir sem dizer o quê, mostra ESCOLHA (PC ou carro). Dois kits:
   - PC: placa-mãe gruda na bandeja do gabinete; CPU/RAM/GPU/SSD/fonte encaixam na posição certa SOBRE ela.
   - CARRO: chassi + 4 rodas + motor + carroceria.
   Onde cada peça entra aparece um FANTASMA (wireframe) da própria peça — você encosta a peça real e ela gruda RENTE,
   peça-na-peça (nada de círculo flutuando). Quem não encaixa VOLTA pra prateleira (nada boiando no ar).
   LOW-POLY procedural + PBR (metal/PCB/cobre/tinta) — leve (lição 41MB). Three r128 (window.THREE, no index.html).
   Mão: gestos.py → {maos} → jarvis.js → window.oficinaMaos. PEGA = peça mais PRÓXIMA do cursor. */
(() => {
  if (!window.THREE) { console.warn("[oficina] THREE não carregou"); return; }
  const T = THREE;

  // ----------------------------------------------------------------- overlay
  const css = document.createElement("style");
  css.textContent = `
    #oficina{position:fixed;inset:0;z-index:7;display:none;overflow:hidden;
      background:radial-gradient(ellipse at 55% 55%,rgba(0,40,60,.5),rgba(0,6,12,.93) 72%)}
    body.oficina-on #oficina{display:block;animation:of-liga .6s ease-out}
    #oficina canvas{position:absolute;inset:0;width:100%;height:100%}
    #oficina .of-scan{position:absolute;inset:0;pointer-events:none;mix-blend-mode:screen;
      background:repeating-linear-gradient(0deg,rgba(120,240,255,.045) 0 1px,transparent 1px 4px)}
    #oficina .of-titulo{position:absolute;top:16px;left:0;right:0;text-align:center;pointer-events:none;
      font:600 20px/1.2 "Segoe UI",sans-serif;letter-spacing:.3em;text-transform:uppercase;color:#8ff3ff;text-shadow:0 0 18px #2ad4ff}
    #oficina .of-titulo small{display:block;margin-top:6px;font:11px Consolas,monospace;letter-spacing:.3em;color:#5fb8c8}
    #oficina .of-ajuda{position:absolute;left:50%;bottom:18px;transform:translateX(-50%);width:min(880px,88%);text-align:center;
      pointer-events:none;font:14px/1.5 "Segoe UI",sans-serif;color:#cdeefc;text-shadow:0 0 10px rgba(0,200,255,.5)}
    #oficina .of-passo{position:absolute;top:66px;right:22px;width:min(330px,34%);font:13px/1.5 Consolas,monospace;color:#c8fbff;
      border:1px solid rgba(120,240,255,.4);border-left:3px solid #4fe3ff;background:rgba(0,18,28,.74);padding:12px 14px;
      box-shadow:0 0 24px rgba(0,200,255,.15);animation:of-entra .5s ease-out}
    #oficina .of-passo b{display:block;color:#8ff3ff;letter-spacing:.18em;font-size:11px;margin-bottom:6px}
    #oficina .of-passo .ok{color:#7CFFB0}
    #oficina .of-prog{position:absolute;top:66px;left:22px;font:12px Consolas,monospace;letter-spacing:.14em;color:#8ff3ff;
      border:1px solid rgba(120,240,255,.3);background:rgba(2,18,26,.72);padding:8px 12px;border-radius:9px}
    #oficina .of-x{position:absolute;top:16px;right:18px;z-index:4;width:38px;height:38px;cursor:pointer;border-radius:10px;
      background:rgba(2,18,26,.8);border:1px solid rgba(120,240,255,.35);color:#7fe8ff;font-size:18px}
    #oficina .of-x:hover{background:rgba(120,240,255,.18);border-color:#4fe3ff}
    #oficina .of-escolha{position:absolute;inset:0;z-index:5;display:none;flex-direction:column;align-items:center;justify-content:center;
      gap:26px;background:rgba(2,10,16,.55);backdrop-filter:blur(3px)}
    #oficina .of-escolha-t{font:600 24px "Segoe UI",sans-serif;letter-spacing:.14em;color:#8ff3ff;text-shadow:0 0 16px #2ad4ff}
    #oficina .of-escolha-b{display:flex;gap:26px;flex-wrap:wrap;justify-content:center}
    #oficina .of-escolha-b button{min-width:200px;padding:28px 30px;cursor:pointer;border-radius:16px;font:600 20px "Segoe UI",sans-serif;
      color:#d6fbff;background:rgba(10,30,44,.85);border:1px solid rgba(120,240,255,.4);box-shadow:0 0 24px rgba(0,150,220,.2);transition:all .15s}
    #oficina .of-escolha-b button:hover{background:rgba(79,227,255,.22);border-color:#4fe3ff;transform:translateY(-3px)}
    #oficina .of-escolha-b button .ico{display:block;font-size:46px;margin-bottom:10px}
    #oficina .of-ligar{position:absolute;left:50%;bottom:64px;transform:translateX(-50%);display:none;z-index:4;cursor:pointer;
      padding:16px 34px;border-radius:40px;font:700 19px "Segoe UI",sans-serif;letter-spacing:.1em;color:#02121a;
      background:linear-gradient(180deg,#9ff0ff,#1fd0ff);border:1px solid #cdfbff;box-shadow:0 0 30px rgba(31,208,255,.7),0 0 70px rgba(31,208,255,.35);
      animation:of-pulsa 1.1s ease-in-out infinite}
    #oficina .of-ligar:hover{transform:translateX(-50%) scale(1.05)}
    @keyframes of-liga{from{opacity:0;transform:scale(.98)}to{opacity:1;transform:none}}
    @keyframes of-entra{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
    @keyframes of-pulsa{0%,100%{box-shadow:0 0 30px rgba(31,208,255,.7),0 0 70px rgba(31,208,255,.3)}50%{box-shadow:0 0 44px rgba(31,208,255,.95),0 0 110px rgba(31,208,255,.5)}}
  `;
  document.head.appendChild(css);
  const el = document.createElement("div");
  el.id = "oficina";
  el.innerHTML =
    `<div class="of-titulo">Oficina<small id="of-sub">bancada de montagem</small></div>` +
    `<div class="of-prog" id="of-prog">0 / 0</div>` +
    `<div class="of-passo" id="of-passo"><b>Como funciona</b>Pince uma peça da lateral e leve até o fantasma dela — gruda sozinha.</div>` +
    `<div class="of-ajuda">✋ pince e arraste · 👌 toque rápido = clique · diga “fecha a oficina”</div>` +
    `<button class="of-x" id="of-x" title="fechar">✕</button>` +
    `<button class="of-ligar" id="of-ligar">⚡ LIGAR O CARRO</button>` +
    `<div class="of-escolha" id="of-escolha"><div class="of-escolha-t">O que vamos montar, chefe?</div>` +
      `<div class="of-escolha-b"><button data-kit="pc"><span class="ico">🖥️</span>PC</button>` +
      `<button data-kit="carro"><span class="ico">🚗</span>Carro</button>` +
      `<button data-kit="quebra"><span class="ico">🧩</span>Quebra-cabeça</button></div></div>` +
    `<div class="of-scan"></div>`;
  document.body.appendChild(el);

  // ----------------------------------------------------------------- Three base
  let renderer, scene, camera, raf = 0, aberta = false, kitAtual = null, grupoKit = null, profAlvo = 5, carroAnim = null;
  const pecas = [];   // {g, nome, tipo, colocada, origem, alvo}
  const slots = [];   // {pos, tipo, nome, dica, cor, ocupado, marca, mat}
  let pegando = null, pincaAnt = false;

  const M = {
    metal: () => new T.MeshStandardMaterial({ color: 0x9fb3c0, metalness: 0.95, roughness: 0.32 }),
    alum: () => new T.MeshStandardMaterial({ color: 0xcdd7de, metalness: 0.8, roughness: 0.45 }),
    pcb: () => new T.MeshStandardMaterial({ color: 0x0c7a3a, metalness: 0.2, roughness: 0.6, emissive: 0x031a0d }),
    cobre: () => new T.MeshStandardMaterial({ color: 0xc87a33, metalness: 1, roughness: 0.35, emissive: 0x200a00 }),
    preto: () => new T.MeshStandardMaterial({ color: 0x161a1e, metalness: 0.4, roughness: 0.7 }),
    pneu: () => new T.MeshStandardMaterial({ color: 0x0e0f11, metalness: 0.1, roughness: 0.95 }),
    tinta: () => new T.MeshStandardMaterial({ color: 0xc02030, metalness: 0.6, roughness: 0.3, emissive: 0x200306 }),
    vidro: () => new T.MeshStandardMaterial({ color: 0x8fd8ff, metalness: 0.2, roughness: 0.05, transparent: true, opacity: 0.4 }),
    neon: (c) => new T.MeshStandardMaterial({ color: c, emissive: c, emissiveIntensity: 0.9, metalness: 0.3, roughness: 0.4 }),
  };
  const caixa = (w, h, d, mat) => new T.Mesh(new T.BoxGeometry(w, h, d), mat);
  const cil = (r1, r2, h, mat, seg = 24) => new T.Mesh(new T.CylinderGeometry(r1, r2, h, seg), mat);

  // ============================================================ KIT PC
  function pcPlaca() {
    const g = new T.Group();
    g.add(caixa(1.5, 1.8, 0.06, M.pcb()));
    const sock = caixa(0.34, 0.34, 0.05, M.alum()); sock.position.set(-0.3, 0.42, 0.05); g.add(sock);
    const soq = caixa(0.26, 0.26, 0.06, M.preto()); soq.position.set(-0.3, 0.42, 0.07); g.add(soq);
    for (let i = 0; i < 4; i++) { const r = caixa(0.05, 0.62, 0.04, M.preto()); r.position.set(0.18 + i * 0.1, 0.42, 0.05); g.add(r); }
    const pcie = caixa(0.9, 0.05, 0.04, M.neon(0x1f6fd0)); pcie.position.set(0.0, -0.3, 0.05); g.add(pcie);
    const m2 = caixa(0.42, 0.06, 0.04, M.cobre()); m2.position.set(0.35, -0.02, 0.05); g.add(m2);
    return g;
  }
  function pcCPU() { const g = new T.Group(); g.add(caixa(0.3, 0.3, 0.08, M.alum())); const t = caixa(0.05, 0.05, 0.085, M.neon(0xffd060)); t.position.set(-0.11, -0.11, 0.0); g.add(t); return g; }
  function pcRAM() { const g = new T.Group(); for (let i = 0; i < 2; i++) { const s = caixa(0.07, 0.62, 0.16, M.pcb()); s.position.x = -0.06 + i * 0.12; g.add(s); const h = caixa(0.075, 0.5, 0.17, M.neon(0x00e5ff)); h.material.wireframe = true; h.position.x = s.position.x; g.add(h); } return g; }
  function pcGPU() { const g = new T.Group(); g.add(caixa(1.1, 0.22, 0.5, M.preto())); const pcb = caixa(1.1, 0.05, 0.5, M.pcb()); pcb.position.y = -0.13; g.add(pcb); for (const x of [-0.27, 0.27]) { const f = cil(0.17, 0.17, 0.06, M.metal(), 20); f.rotation.x = Math.PI / 2; f.position.set(x, 0.13, 0); g.add(f); } return g; }
  function pcFonte() { const g = new T.Group(); g.add(caixa(0.8, 0.5, 0.56, M.alum())); const fan = cil(0.2, 0.2, 0.03, M.preto(), 24); fan.rotation.x = Math.PI / 2; fan.position.z = 0.29; g.add(fan); const tr = new T.Mesh(new T.TorusGeometry(0.19, 0.012, 6, 20), M.metal()); tr.position.z = 0.3; g.add(tr); return g; }
  function pcSSD() { const g = new T.Group(); g.add(caixa(0.5, 0.14, 0.08, M.metal())); const l = caixa(0.34, 0.1, 0.09, M.neon(0x1f6fd0)); l.material.wireframe = true; g.add(l); return g; }

  const KIT_PC = {
    sub: "montagem de PC",
    cam: { pos: [0.1, 1.2, 5.0], alvo: [0.1, 1.05, -0.2] },
    base() {
      const outline = new T.Mesh(new T.BoxGeometry(2.1, 2.5, 1.0), M.neon(0x1f6fd0)); outline.material.wireframe = true; outline.position.set(0.1, 1.05, 0); grupoKit.add(outline);
      const tray = caixa(2.0, 2.4, 0.05, new T.MeshStandardMaterial({ color: 0x0b2233, metalness: 0.6, roughness: 0.5, transparent: true, opacity: 0.5 })); tray.position.set(0.1, 1.05, -0.46); grupoKit.add(tray);
    },
    pecas: [
      { nome: "placa-mãe", tipo: "mae", fab: pcPlaca, slot: [0.1, 1.15, -0.4], shelf: [-2.5, 1.9, 0.9], cor: 0x7CFFB0, dica: "Placa-mãe → presa na bandeja do gabinete. É a base: todo o resto encaixa NELA." },
      { nome: "processador", tipo: "cpu", fab: pcCPU, slot: [-0.2, 1.57, -0.34], shelf: [-2.5, 1.4, 0.9], cor: 0xffb000, dica: "CPU → socket da placa-mãe; alinhe o triângulo dourado. Depois pasta térmica + cooler." },
      { nome: "memória RAM", tipo: "ram", fab: pcRAM, slot: [0.37, 1.57, -0.33], shelf: [-2.5, 0.9, 0.9], cor: 0x00e5ff, dica: "RAM → slots ao lado do CPU; empurre até travar as presilhas. 2 pentes = dual channel." },
      { nome: "placa de vídeo", tipo: "gpu", fab: pcGPU, slot: [0.1, 0.75, -0.2], shelf: [-2.5, 0.4, 0.9], cor: 0xff6b6b, dica: "GPU → slot PCIe x16 (o de cima). Ligue o cabo PCIe vindo da fonte." },
      { nome: "fonte", tipo: "fonte", fab: pcFonte, slot: [0.1, 0.1, -0.2], shelf: [-2.5, -0.15, 0.9], cor: 0xcdd7de, dica: "Fonte → embaixo do gabinete. Alimenta placa-mãe (24 pinos), CPU (8) e GPU." },
      { nome: "SSD", tipo: "ssd", fab: pcSSD, slot: [0.45, 1.03, -0.33], shelf: [-2.5, -0.65, 0.9], cor: 0x8ff3ff, dica: "SSD → M.2 na placa-mãe. É onde ficam o Windows e seus arquivos." },
    ],
    fim: "PC MONTADO! Agora é ligar os cabos da fonte, dar boot e instalar o sistema.",
  };

  // ============================================================ KIT CARRO
  function carRoda() { const g = new T.Group(); const p = cil(0.34, 0.34, 0.2, M.pneu(), 28); p.rotation.z = Math.PI / 2; g.add(p); const a = cil(0.2, 0.2, 0.21, M.alum(), 18); a.rotation.z = Math.PI / 2; g.add(a); const c = cil(0.06, 0.06, 0.24, M.metal(), 10); c.rotation.z = Math.PI / 2; g.add(c); return g; }
  function carMotor() { const g = new T.Group(); g.add(caixa(0.6, 0.4, 0.6, M.metal())); for (const x of [-0.15, 0.15]) for (const z of [-0.15, 0.15]) { const cc = cil(0.07, 0.07, 0.18, M.alum(), 10); cc.position.set(x, 0.28, z); g.add(cc); } const belt = cil(0.14, 0.14, 0.05, M.preto(), 18); belt.rotation.z = Math.PI / 2; belt.position.set(-0.33, 0.05, 0); g.add(belt); return g; }
  function carBody() { const g = new T.Group(); g.add(caixa(1.5, 0.4, 2.4, M.tinta())); const cab = caixa(1.3, 0.45, 1.2, M.tinta()); cab.position.set(0, 0.42, -0.1); g.add(cab); const vidro = caixa(1.24, 0.38, 1.1, M.vidro()); vidro.position.set(0, 0.45, -0.1); g.add(vidro); const far = (x) => { const m = M.neon(0xfff0c0); m.emissiveIntensity = 0.28; const f = caixa(0.18, 0.12, 0.05, m); f.position.set(x, 0.05, 1.22); f.userData.farol = true; g.add(f); }; far(-0.5); far(0.5); return g; }

  const KIT_CARRO = {
    sub: "montagem de carro",
    cam: { pos: [2.8, 2.4, 3.8], alvo: [0, 0.35, 0] },
    base() {
      const plat = caixa(1.4, 0.12, 2.3, M.preto()); plat.position.y = 0.2; grupoKit.add(plat);
      const borda = new T.Mesh(new T.BoxGeometry(1.46, 0.16, 2.36), M.neon(0x1f6fd0)); borda.material.wireframe = true; borda.position.y = 0.2; grupoKit.add(borda);
      for (const z of [0.7, -0.7]) { const eixo = cil(0.05, 0.05, 1.6, M.metal(), 10); eixo.rotation.z = Math.PI / 2; eixo.position.set(0, 0.2, z); grupoKit.add(eixo); }
    },
    pecas: [
      { nome: "roda diant. esquerda", tipo: "roda", fab: carRoda, slot: [-0.78, 0.2, 0.7], shelf: [-2.6, 1.7, 1.2], cor: 0x00e5ff, dica: "Roda → ponta do eixo dianteiro esquerdo. As 4 rodas sustentam o carro." },
      { nome: "roda diant. direita", tipo: "roda", fab: carRoda, slot: [0.78, 0.2, 0.7], shelf: [-2.6, 1.2, 1.2], cor: 0x00e5ff, dica: "Roda → eixo dianteiro direito. As dianteiras esterçam (direção)." },
      { nome: "roda tras. esquerda", tipo: "roda", fab: carRoda, slot: [-0.78, 0.2, -0.7], shelf: [-2.6, 0.7, 1.2], cor: 0x00e5ff, dica: "Roda → eixo traseiro esquerdo. As traseiras costumam receber a tração." },
      { nome: "roda tras. direita", tipo: "roda", fab: carRoda, slot: [0.78, 0.2, -0.7], shelf: [-2.6, 0.2, 1.2], cor: 0x00e5ff, dica: "Roda → eixo traseiro direito. Pronto, o carro se apoia nas 4." },
      { nome: "motor", tipo: "motor", fab: carMotor, slot: [0, 0.45, 0.75], shelf: [-2.6, -0.4, 1.2], cor: 0xffb000, dica: "Motor → cofre dianteiro. Gira o eixo pela transmissão e move as rodas." },
      { nome: "carroceria", tipo: "body", fab: carBody, slot: [0, 0.58, 0], shelf: [-2.6, -1.0, 1.2], cor: 0xff6b6b, dica: "Carroceria → por cima do chassi. Cobre tudo e dá a forma do carro." },
    ],
    fim: "CARRO MONTADO! 4 rodas, motor no cofre e carroceria. Dá a partida! 🚗",
  };

  const KITS = { pc: KIT_PC, carro: KIT_CARRO };

  // ============================================================ QUEBRA-CABEÇA (imagem do JARVIS, sem arquivo — desenhada em canvas)
  function jarvisCanvas() {
    const cv = document.createElement("canvas"); cv.width = cv.height = 512;
    const x = cv.getContext("2d");
    const bg = x.createRadialGradient(256, 256, 20, 256, 256, 320);
    bg.addColorStop(0, "#083246"); bg.addColorStop(1, "#02070c");
    x.fillStyle = bg; x.fillRect(0, 0, 512, 512);
    x.save(); x.translate(256, 248);
    for (let i = 0; i < 12; i++) { x.rotate(Math.PI / 6); x.fillStyle = "rgba(120,240,255,.45)"; x.fillRect(96, -9, 54, 18); }
    x.restore();
    x.strokeStyle = "#4fe3ff"; x.lineWidth = 7;
    for (const r of [168, 126, 84]) { x.beginPath(); x.arc(256, 248, r, 0, 7); x.stroke(); }
    const cg = x.createRadialGradient(256, 248, 0, 256, 248, 78);
    cg.addColorStop(0, "#eaffff"); cg.addColorStop(.6, "#7fe8ff"); cg.addColorStop(1, "rgba(79,227,255,0)");
    x.fillStyle = cg; x.beginPath(); x.arc(256, 248, 78, 0, 7); x.fill();
    x.fillStyle = "#eaffff"; x.textAlign = "center"; x.font = "900 60px 'Segoe UI',sans-serif";
    x.shadowColor = "#2ad4ff"; x.shadowBlur = 24; x.fillText("J.A.R.V.I.S.", 256, 470);
    return new T.CanvasTexture(cv);
  }
  function montarQuebra() {
    if (grupoKit) scene.remove(grupoKit);
    grupoKit = new T.Group(); scene.add(grupoKit); grupoKit.visible = true;
    pecas.length = 0; slots.length = 0; pegando = null; pincaAnt = false; carroAnim = null;
    document.getElementById("of-ligar").style.display = "none";
    document.getElementById("of-sub").textContent = "quebra-cabeça do JARVIS";
    camera.position.set(0, 0.2, 4.7); camera.lookAt(0, 0.2, 0);
    profAlvo = camera.position.distanceTo(new T.Vector3(0, 0.2, 0));
    const COLS = 3, ROWS = 3, S = 0.9, GAP = 0.03, tex = jarvisCanvas();
    const quadro = new T.Mesh(new T.PlaneGeometry(COLS * S + 0.14, ROWS * S + 0.14), new T.MeshBasicMaterial({ color: 0x05202c }));
    quadro.position.set(0, 0.2, -0.05); grupoKit.add(quadro);
    let idx = 0;
    for (let r = 0; r < ROWS; r++) for (let c = 0; c < COLS; c++) {
      const pos = new T.Vector3((c - (COLS - 1) / 2) * S, 0.2 + ((ROWS - 1) / 2 - r) * S, 0), tipo = "pz" + idx;
      const fm = new T.MeshBasicMaterial({ color: 0x4fe3ff, wireframe: true, transparent: true, opacity: 0.22 });
      const fg = new T.Mesh(new T.PlaneGeometry(S - GAP, S - GAP), fm); fg.position.copy(pos); grupoKit.add(fg);
      slots.push({ pos, tipo, nome: `peça ${idx + 1}`, dica: "Peça no lugar — a imagem do JARVIS vai se formando.", cor: 0x4fe3ff, ocupado: false, marca: fg, mat: fm });
      const t2 = tex.clone(); t2.needsUpdate = true; t2.repeat.set(1 / COLS, 1 / ROWS); t2.offset.set(c / COLS, (ROWS - 1 - r) / ROWS);
      const pg = new T.Group();
      pg.add(new T.Mesh(new T.PlaneGeometry(S - GAP, S - GAP), new T.MeshBasicMaterial({ map: t2 })));
      const edge = new T.Mesh(new T.PlaneGeometry(S - GAP, S - GAP), new T.MeshBasicMaterial({ color: 0x4fe3ff, wireframe: true, transparent: true, opacity: 0.5 })); edge.position.z = 0.002; pg.add(edge);
      const sx = -2.8 + (idx % 2) * 0.55, sy = 1.95 - idx * 0.43;
      pg.position.set(sx, sy, 0.2); grupoKit.add(pg);
      pecas.push({ g: pg, nome: `peça ${idx + 1}`, tipo, colocada: false, origem: new T.Vector3(sx, sy, 0.2), alvo: null });
      idx++;
    }
    grupoKit.userData.fim = "QUEBRA-CABEÇA COMPLETO! É o meu rosto de dados, chefe. 🧩";
    document.getElementById("of-passo").innerHTML = `<b>QUEBRA-CABEÇA</b>Pince cada peça da lateral e leve até o contorno certo — cada peça só encaixa no lugar dela.`;
    prog();
  }

  // ------------------------------------------------- som do motor (sintetizado, sem arquivo) + ligar o carro
  function somMotor() {
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext; if (!Ctx) return;
      const ac = new Ctx(), now = ac.currentTime;
      const g = ac.createGain(); g.gain.value = 0; g.connect(ac.destination);
      const lp = ac.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.setValueAtTime(380, now); lp.connect(g);
      const o1 = ac.createOscillator(), o2 = ac.createOscillator(); o1.type = o2.type = "sawtooth";
      o1.frequency.setValueAtTime(52, now); o2.frequency.setValueAtTime(80, now); o1.connect(lp); o2.connect(lp); o1.start(); o2.start();
      g.gain.linearRampToValueAtTime(0.28, now + 0.14);                 // ignição
      o1.frequency.setValueAtTime(68, now + 0.55); o2.frequency.setValueAtTime(104, now + 0.55);
      o1.frequency.linearRampToValueAtTime(280, now + 2.3); o2.frequency.linearRampToValueAtTime(410, now + 2.3);  // acelera
      lp.frequency.linearRampToValueAtTime(2800, now + 2.3);
      g.gain.setValueAtTime(0.28, now + 1.7); g.gain.linearRampToValueAtTime(0, now + 2.7);                        // some ao sair
      setTimeout(() => { try { o1.stop(); o2.stop(); ac.close(); } catch (e) {} }, 3000);
    } catch (e) {}
  }
  function ligarCarro() {
    if (carroAnim) return;
    document.getElementById("of-ligar").style.display = "none";
    const l1 = new T.PointLight(0xfff0c0, 0, 9), l2 = new T.PointLight(0xfff0c0, 0, 9);
    l1.position.set(-0.5, 0.65, 1.4); l2.position.set(0.5, 0.65, 1.4); grupoKit.add(l1); grupoKit.add(l2);
    grupoKit.traverse((o) => { if (o.userData && o.userData.farol && o.material) o.material.emissiveIntensity = 2.4; });
    somMotor();
    carroAnim = { t0: performance.now(), l1, l2 };
  }
  function concluir() {
    if (kitAtual === "carro") document.getElementById("of-ligar").style.display = "block";
  }
  function mostrarProximo() {   // depois do carro sair: reabre a escolha (agora com quebra-cabeça)
    kitAtual = null;
    const esc = document.getElementById("of-escolha");
    esc.querySelector(".of-escolha-t").textContent = "🚗 Vrum! E agora, chefe?";
    esc.style.display = "flex";
  }

  // ----------------------------------------------------------------- montar
  function fantasma(fab, cor) {   // "ghost" wireframe da peça no lugar certo (mostra que gruda ALI, na peça)
    const g = fab(); const mat = new T.MeshBasicMaterial({ color: cor, wireframe: true, transparent: true, opacity: 0.22 });
    g.traverse((o) => { if (o.isMesh) o.material = mat; });
    return { g, mat };
  }
  function montar(kitNome) {
    if (grupoKit) scene.remove(grupoKit);
    grupoKit = new T.Group(); scene.add(grupoKit);
    pecas.length = 0; slots.length = 0; pegando = null; pincaAnt = false;
    const K = KITS[kitNome] || KIT_PC;
    document.getElementById("of-sub").textContent = K.sub;
    camera.position.set(...K.cam.pos); camera.lookAt(...K.cam.alvo);
    profAlvo = camera.position.distanceTo(new T.Vector3(...K.cam.alvo));
    K.base();
    for (const d of K.pecas) {
      const pos = new T.Vector3(...d.slot);
      const f = fantasma(d.fab, d.cor); f.g.position.copy(pos); grupoKit.add(f.g);
      slots.push({ pos, tipo: d.tipo, nome: d.nome, dica: d.dica, cor: d.cor, ocupado: false, marca: f.g, mat: f.mat });
      const g = d.fab(); g.position.set(...d.shelf); grupoKit.add(g);
      pecas.push({ g, nome: d.nome, tipo: d.tipo, colocada: false, origem: new T.Vector3(...d.shelf), alvo: null });
    }
    grupoKit.userData.fim = K.fim;
    document.getElementById("of-passo").innerHTML = `<b>${K.sub.toUpperCase()}</b>Pince uma peça da lateral e leve até o fantasma dela — ela gruda no lugar certo.`;
    prog();
  }

  // ----------------------------------------------------------------- interação
  const proj = (v) => { const q = v.clone().project(camera); return { x: (q.x + 1) / 2, y: (1 - q.y) / 2 }; };
  function pecaEm(xf, yf) { let best = null, bd = 0.14; for (const p of pecas) { if (p.colocada) continue; const s = proj(p.g.position); const d = Math.hypot(s.x - xf, s.y - yf); if (d < bd) { bd = d; best = p; } } return best; }
  function pegar(xf, yf) { const p = pecaEm(xf, yf); if (p) { pegando = p; p.alvo = null; p.g.scale.setScalar(1.1); } }
  function mover(xf, yf) { if (!pegando) return; const v = new T.Vector3(xf * 2 - 1, -(yf * 2 - 1), 0.5).unproject(camera); const dir = v.sub(camera.position).normalize(); pegando.g.position.copy(camera.position.clone().add(dir.multiplyScalar(profAlvo))); }
  function soltar() {
    if (!pegando) return;
    const p = pegando; p.g.scale.setScalar(1); pegando = null;
    const ps = proj(p.g.position);
    let melhor = null, dist = 0.13;
    for (const s of slots) { if (s.ocupado || s.tipo !== p.tipo) continue; const ss = proj(s.pos); const d = Math.hypot(ps.x - ss.x, ps.y - ss.y); if (d < dist) { dist = d; melhor = s; } }
    if (melhor) { melhor.ocupado = true; p.colocada = true; p.alvo = melhor.pos.clone(); melhor.marca.visible = false; ensinar(melhor); sino(); prog(); if (slots.every((x) => x.ocupado)) concluir(); }
    else { p.alvo = p.origem.clone(); }   // não encaixou → volta pra prateleira (nada flutuando)
  }
  function ensinar(s) {
    const feitos = slots.filter((x) => x.ocupado).length;
    const fim = (feitos === slots.length && grupoKit.userData.fim) ? `<br><br><b class="ok">${grupoKit.userData.fim}</b>` : "";
    document.getElementById("of-passo").innerHTML = `<b class="ok">✓ ${s.nome.toUpperCase()}</b>${s.dica}${fim}`;
  }
  function prog() { const f = slots.filter((x) => x.ocupado).length; document.getElementById("of-prog").textContent = `${f} / ${slots.length} peças`; }
  function sino() { try { window.sons && window.sons.trava && window.sons.trava(); } catch (e) {} }

  window.oficinaMaos = (maos) => {
    if (!aberta || !kitAtual) return;
    const m = (maos && maos[0]) || null;
    if (!m) { if (pincaAnt) soltar(); pincaAnt = false; return; }
    if (m.pinca && !pincaAnt) pegar(m.x, m.y);
    else if (!m.pinca && pincaAnt) soltar();
    else if (m.pinca && pegando) mover(m.x, m.y);
    pincaAnt = !!m.pinca;
  };
  let mouseOn = false;
  el.addEventListener("mousedown", (e) => { if (e.target.closest("#of-x,.of-escolha,#of-ligar")) return; mouseOn = true; const r = el.getBoundingClientRect(); pegar((e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height); });
  el.addEventListener("mousemove", (e) => { if (!mouseOn) return; const r = el.getBoundingClientRect(); mover((e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height); });
  addEventListener("mouseup", () => { if (mouseOn) { mouseOn = false; soltar(); } });

  // ----------------------------------------------------------------- loop / abrir / fechar / escolher
  function criar() {
    renderer = new T.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); renderer.setSize(innerWidth, innerHeight);
    el.insertBefore(renderer.domElement, el.firstChild);
    scene = new T.Scene();
    camera = new T.PerspectiveCamera(46, innerWidth / innerHeight, 0.1, 100);
    camera.position.set(0.1, 1.2, 5.0); camera.lookAt(0.1, 1.05, -0.2);
    scene.add(new T.AmbientLight(0x3a6a8a, 0.95));
    const d = new T.DirectionalLight(0xbfefff, 1.15); d.position.set(3, 6, 5); scene.add(d);
    const pl = new T.PointLight(0x18a0ff, 0.9, 50); pl.position.set(0, 3, 5); scene.add(pl);
    const pl2 = new T.PointLight(0x00e5ff, 0.5, 40); pl2.position.set(-4, 2, 2); scene.add(pl2);
    const grade = new T.GridHelper(18, 36, 0x1f8fcf, 0x0b3550); grade.position.y = -0.52; scene.add(grade);
  }
  function loop() {
    if (!aberta) return; raf = requestAnimationFrame(loop);
    const t = performance.now() / 1000;
    slots.forEach((s) => { if (!s.ocupado) { s.marca.rotation.y += 0.01; s.mat.opacity = 0.14 + 0.12 * (0.5 + 0.5 * Math.sin(t * 3)); } });
    pecas.forEach((p) => { if (p.alvo) { p.g.position.lerp(p.alvo, 0.28); if (p.g.position.distanceTo(p.alvo) < 0.008) { p.g.position.copy(p.alvo); p.alvo = null; } } });
    if (carroAnim && grupoKit) {   // dá a partida: faróis acendem, acelera e sai da tela
      const e = (performance.now() - carroAnim.t0) / 1000;
      carroAnim.l1.intensity = carroAnim.l2.intensity = Math.min(1, e / 0.5) * 2.4;
      if (e > 0.6) {
        const a = e - 0.6, d = 4.6 * a * a;
        grupoKit.position.set(d * 1.5, 0, d * 1.7);
        const op = Math.max(0, 1 - a / 1.7);
        grupoKit.traverse((o) => { if (o.isMesh && o.material && !o.material.wireframe) { o.material.transparent = true; o.material.opacity = op; } });
        if (a > 1.75) { carroAnim = null; grupoKit.visible = false; mostrarProximo(); }
      }
    }
    renderer.render(scene, camera);
  }
  function onResize() { if (!renderer) return; renderer.setSize(innerWidth, innerHeight); camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); }

  function escolher(kit) {
    document.getElementById("of-escolha").style.display = "none";
    document.getElementById("of-ligar").style.display = "none";
    if (kit !== kitAtual) { if (kit === "quebra") montarQuebra(); else montar(kit); kitAtual = kit; }
  }
  window.abrirOficina = (kit) => {
    if (!renderer) criar();
    document.body.classList.add("oficina-on"); aberta = true;
    addEventListener("resize", onResize); onResize(); if (!raf) loop();
    if (kit === "pc" || kit === "carro" || kit === "quebra") { escolher(kit); }
    else {   // "escolher": pergunta PC, carro ou quebra-cabeça
      document.getElementById("of-escolha").querySelector(".of-escolha-t").textContent = "O que vamos montar, chefe?";
      document.getElementById("of-escolha").style.display = "flex";
    }
  };
  window.fecharOficina = () => { if (!aberta) return; aberta = false; cancelAnimationFrame(raf); raf = 0; document.body.classList.remove("oficina-on"); removeEventListener("resize", onResize); };
  Object.defineProperty(window, "oficinaAtiva", { get: () => aberta });
  document.getElementById("of-x").addEventListener("click", () => window.fecharOficina());
  document.getElementById("of-ligar").addEventListener("click", ligarCarro);
  el.querySelectorAll(".of-escolha-b button").forEach((b) => b.addEventListener("click", () => escolher(b.dataset.kit)));
  console.log("[oficina] pronta (PC + carro + quebra-cabeça, partida do carro)");
})();
