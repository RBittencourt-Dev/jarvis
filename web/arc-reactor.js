/* Arc Reactor do núcleo do JARVIS — render em canvas fiel ao jarvis_core JSON que o Rafael mandou.
   8 camadas (HUD externo, anel técnico, ticks radiais, 2 anéis de energia, anel mecânico, raios internos,
   núcleo concêntrico) + rótulo "JARVIS" + partículas + varredura + ignição na abertura.
   Lê o estado pelas classes do body e o nível de áudio por --nivel (o mesmo que a onda de voz já calcula).
   A pedido do Rafael a cor fica SEMPRE azul/ciano (sem verde/âmbar); só o MOVIMENTO muda por estado;
   vermelho só em alerta. Pra ligar as cores de estado do JSON é só pôr CORES_DE_ESTADO = true. */
(function () {
  const tela = document.getElementById("reator");
  if (!tela || !tela.getContext) return;
  const ctx = tela.getContext("2d");
  const CORES_DE_ESTADO = false; // false = núcleo sempre azul (só movimento muda); true = verde/âmbar/azul do JSON

  // paleta e camadas (direto do JSON)
  const C = { prim: "#00E5FF", sec: "#0077FF", alto: "#B8F7FF", escuro: "#003344", nucleo: "#061A2B", alerta: "#FF1744" };
  const REF = 390; // o JSON foi desenhado para um reator de 390px; tudo escala a partir disso
  const CAMADAS = {
    outer_hud:        { r: 190, w: 1,  seg: 96, cor: C.sec,  vel: 0.08,  dir: 1,  a: 0.45 },
    tecnico:          { r: 174, w: 4,  seg: 48, ativos: 30, gap: 3, cor: "#00BFFF", vel: 0.16, dir: -1, glow: 1 },
    ticks:            { r: 158, n: 120, maior: 10, menorL: 5, maiorL: 12, cor: C.prim, a: 0.8 },
    energia_fora:     { r: 140, w: 12, seg: 16, ativos: 11, cor: "#00CFFF", vel: 0.4, dir: 1,  glow: 1, audio: 1 },
    energia_dentro:   { r: 116, w: 8,  seg: 24, ativos: 18, cor: C.sec,    vel: 0.7, dir: -1, glow: 1, audio: 1 },
    mecanico:         { r: 91,  w: 7,  seg: 12, ativos: 12, gap: 6, cor: C.prim, vel: 1.1, dir: 1, glow: 1 },
    raios:            { r: 72,  n: 32, cor: "#00BFFF", centro: C.alto, audio: 1 },
    central:          { r: 48,  aneis: 4, fill: C.nucleo, cont: C.prim, contW: 2, luz: "#00CFFF" },
  };
  const VEL = 60;       // rotation_speed do JSON é "por frame" a 60fps → graus/seg = vel*60
  const t0 = performance.now();

  // estado atual (movimento) — a cor só muda em alerta (ou se CORES_DE_ESTADO=true)
  function estado() {
    const b = document.body.classList;
    if (b.contains("alerta")) return { mult: 2.5, pulso: 2.2, cor: C.alerta, anim: "alerta" };
    if (b.contains("ouvindo")) return { mult: 1.2, pulso: 1.6, cor: CORES_DE_ESTADO ? "#00E676" : null, anim: "ouvindo" };
    if (b.contains("pensando")) return { mult: 2.0, pulso: 0.9, cor: CORES_DE_ESTADO ? "#FFB300" : null, anim: "pensando" };
    if (b.contains("falando") || b.contains("agindo")) return { mult: 1.4, pulso: 1.2, cor: CORES_DE_ESTADO ? C.sec : null, anim: "falando" };
    return { mult: 1.0, pulso: 1.0, cor: null, anim: "idle" };
  }
  const nivel = () => { const v = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--nivel")); return isNaN(v) ? 0 : v; };
  const suave = (a, b, x) => { const t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

  // partículas de energia (36) subindo em espiral e sumindo
  const parts = [];
  function passoParts(cx, cy, esc, cor) {
    if (document.body.classList.contains("leve")) return;
    if (parts.length < 36 && Math.random() < 0.4) parts.push({ ang: Math.random() * 6.283, r: 50 * esc, v: (0.3 + Math.random() * 0.5), vida: 1 });
    ctx.save(); ctx.globalCompositeOperation = "lighter";
    for (let i = parts.length - 1; i >= 0; i--) {
      const p = parts[i]; p.r += p.v * esc; p.vida -= 0.012; p.ang += 0.01;
      if (p.vida <= 0 || p.r > 185 * esc) { parts.splice(i, 1); continue; }
      const x = cx + Math.cos(p.ang) * p.r, y = cy + Math.sin(p.ang) * p.r;
      ctx.globalAlpha = p.vida * 0.8; ctx.fillStyle = cor; ctx.shadowColor = cor; ctx.shadowBlur = 8 * esc;
      ctx.beginPath(); ctx.arc(x, y, 1.6 * esc, 0, 6.283); ctx.fill();
    }
    ctx.restore();
  }

  function anelSegmentado(cx, cy, r, w, seg, ativos, gapDeg, cor, rot, esc, nvl) {
    const passo = 360 / seg, span = (passo - gapDeg) * Math.PI / 180;
    ctx.lineWidth = w * esc; ctx.strokeStyle = cor; ctx.shadowColor = cor;
    for (let i = 0; i < seg; i++) {
      const ativo = i < ativos;
      ctx.globalAlpha = ativo ? (0.9 + nvl * 0.1) : 0.12;
      ctx.shadowBlur = ativo ? (8 + nvl * 10) * esc : 0;
      const a0 = (i * passo) * Math.PI / 180 + rot;
      ctx.beginPath(); ctx.arc(cx, cy, r * esc, a0, a0 + span); ctx.stroke();
    }
    ctx.globalAlpha = 1; ctx.shadowBlur = 0;
  }

  function desenhar() {
    if (document.hidden) return requestAnimationFrame(desenhar);
    const lado = tela.clientWidth, dpr = Math.min(2, devicePixelRatio || 1), px = Math.round(lado * dpr);
    if (tela.width !== px) { tela.width = tela.height = px; }
    const esc = (px / dpr) / REF; // escala relativa ao desenho de 390
    const cx = px / (2 * dpr), cy = cx;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, lado, lado);

    const now = performance.now(), seg = (now - t0) / 1000, st = estado(), nvl = nivel();
    const prog = suave(0, 1, Math.min(1, (now - t0) / 2200)); // ignição
    const resp = 1 + Math.sin(seg * 1.6) * 0.012;             // idle_breathing
    const ang = (v, dir) => dir * seg * v * VEL * st.mult * Math.PI / 180;
    const corE = st.cor; // sobrepõe a cor só em alerta (ou se CORES_DE_ESTADO)
    const cor = (padrao) => corE || padrao;

    ctx.save();
    ctx.translate(cx, cy); ctx.scale(resp, resp); ctx.translate(-cx, -cy);

    // 1) HUD externo — círculo fino + 96 notas
    let L = CAMADAS.outer_hud, aL = prog * L.a;
    ctx.globalAlpha = aL; ctx.strokeStyle = cor(L.cor); ctx.lineWidth = L.w * esc;
    ctx.beginPath(); ctx.arc(cx, cy, L.r * esc, 0, 6.283); ctx.stroke();
    for (let i = 0; i < L.seg; i++) { const a = (i / L.seg) * 6.283 + ang(L.vel, L.dir); const r1 = (L.r - 4) * esc, r2 = L.r * esc;
      ctx.beginPath(); ctx.moveTo(cx + Math.cos(a) * r1, cy + Math.sin(a) * r1); ctx.lineTo(cx + Math.cos(a) * r2, cy + Math.sin(a) * r2); ctx.stroke(); }
    ctx.globalAlpha = 1;

    // 2) anel técnico segmentado (48/30)
    L = CAMADAS.tecnico; ctx.globalAlpha = suave(0.55, 0.8, prog);
    anelSegmentado(cx, cy, L.r, L.w, L.seg, L.ativos, L.gap, cor(L.cor), ang(L.vel, L.dir), esc, 0);

    // 3) ticks radiais (120, maior a cada 10) — estáticos
    L = CAMADAS.ticks; ctx.globalAlpha = prog * L.a; ctx.strokeStyle = cor(L.cor); ctx.lineWidth = 1 * esc; ctx.shadowBlur = 0;
    for (let i = 0; i < L.n; i++) { const a = (i / L.n) * 6.283 - Math.PI / 2; const comp = (i % L.maior === 0 ? L.maiorL : L.menorL) * esc;
      const r2 = L.r * esc, r1 = r2 - comp; ctx.beginPath(); ctx.moveTo(cx + Math.cos(a) * r1, cy + Math.sin(a) * r1); ctx.lineTo(cx + Math.cos(a) * r2, cy + Math.sin(a) * r2); ctx.stroke(); }
    ctx.globalAlpha = 1;

    // 4) e 5) anéis de energia (reagem ao áudio)
    L = CAMADAS.energia_fora; ctx.globalAlpha = suave(0.55, 0.85, prog);
    anelSegmentado(cx, cy, L.r, L.w, L.seg, L.ativos, 4, cor(L.cor), ang(L.vel, L.dir), esc, nvl);
    L = CAMADAS.energia_dentro; ctx.globalAlpha = suave(0.3, 0.6, prog);
    anelSegmentado(cx, cy, L.r, L.w, L.seg, L.ativos, 3, cor(L.cor), ang(L.vel, L.dir), esc, nvl);

    // 6) anel mecânico (12 blocos)
    L = CAMADAS.mecanico; ctx.globalAlpha = suave(0.2, 0.5, prog);
    anelSegmentado(cx, cy, L.r, L.w, L.seg, L.ativos, L.gap, cor(L.cor), ang(L.vel, L.dir), esc, 0);
    ctx.globalAlpha = 1;

    // 7) raios internos (32) + brilho central
    L = CAMADAS.raios; const pulso = (1 + Math.sin(seg * 0.8 * st.pulso) * 0.04) * (1 + nvl * 0.25);
    const g = ctx.createRadialGradient(cx, cy, 2, cx, cy, L.r * esc * pulso);
    g.addColorStop(0, cor(L.centro)); g.addColorStop(0.5, cor(L.cor)); g.addColorStop(1, "transparent");
    ctx.globalAlpha = 0.9 * prog; ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, L.r * esc * pulso, 0, 6.283); ctx.fill();
    ctx.strokeStyle = cor(L.cor); ctx.lineWidth = 1 * esc; ctx.globalAlpha = (0.35 + nvl * 0.4) * prog;
    for (let i = 0; i < L.n; i++) { const a = (i / L.n) * 6.283 + ang(0.3, 1); const r2 = L.r * esc * pulso;
      ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + Math.cos(a) * r2, cy + Math.sin(a) * r2); ctx.stroke(); }
    ctx.globalAlpha = 1;

    // 8) núcleo concêntrico (4 anéis) + bloom central pulsante
    L = CAMADAS.central; const op = 0.65 + Math.abs(Math.sin(seg * 0.6 * st.pulso)) * 0.35;
    for (let i = L.aneis; i >= 1; i--) { const r = (L.r * i / L.aneis) * esc;
      ctx.fillStyle = L.fill; ctx.globalAlpha = 0.9 * prog; ctx.beginPath(); ctx.arc(cx, cy, r, 0, 6.283); ctx.fill();
      ctx.strokeStyle = cor(L.cont); ctx.lineWidth = L.contW * esc; ctx.globalAlpha = (0.5 + i / L.aneis * 0.5) * prog; ctx.shadowColor = cor(L.cont); ctx.shadowBlur = 6 * esc; ctx.stroke(); }
    const gb = ctx.createRadialGradient(cx, cy, 0, cx, cy, L.r * esc);
    gb.addColorStop(0, cor(L.luz)); gb.addColorStop(0.6, cor(C.prim)); gb.addColorStop(1, "transparent");
    ctx.globalAlpha = op * prog; ctx.fillStyle = gb; ctx.shadowBlur = 0; ctx.beginPath(); ctx.arc(cx, cy, L.r * esc * 0.9, 0, 6.283); ctx.fill();
    ctx.globalAlpha = 1;

    // partículas + varredura
    passoParts(cx, cy, esc, cor(C.prim));
    if (!document.body.classList.contains("leve")) {
      const sw = seg * 0.35 * 60 * Math.PI / 180;
      const gs = ctx.createConicGradient ? ctx.createConicGradient(sw, cx, cy) : null;
      if (gs) { gs.addColorStop(0, "transparent"); gs.addColorStop(0.08, "rgba(0,229,255,0.18)"); gs.addColorStop(0.16, "transparent"); gs.addColorStop(1, "transparent");
        ctx.fillStyle = gs; ctx.beginPath(); ctx.arc(cx, cy, 185 * esc, 0, 6.283); ctx.fill(); }
    }

    // rótulo JARVIS
    if (prog > 0.85) { const al = suave(0.85, 1, prog);
      ctx.globalAlpha = al; ctx.fillStyle = cor(C.alto); ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.font = `bold ${Math.round(22 * esc)}px Orbitron, system-ui, sans-serif`;
      try { ctx.letterSpacing = `${5 * esc}px`; } catch {}
      ctx.shadowColor = cor(C.prim); ctx.shadowBlur = 14 * esc; ctx.fillText("JARVIS", cx, cy);
      ctx.globalAlpha = 1; ctx.shadowBlur = 0; try { ctx.letterSpacing = "0px"; } catch {}
    }

    ctx.restore();
    requestAnimationFrame(desenhar);
  }
  requestAnimationFrame(desenhar);
})();
