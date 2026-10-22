// Portão do rosto: o Jarvis só abre depois de reconhecer o Rafael pela webcam.
// Tudo roda neste navegador; o servidor guarda só os números do rosto (rosto.json).
const LIMITE_RECONHECER = 0.5; // distância máxima para considerar o mesmo rosto
const ACERTOS_SEGUIDOS = 3;
const TEMPO_MAXIMO_MS = 15000;

const portao = {
  el: document.getElementById("portao"),
  texto: (t, negado = false) => {
    document.getElementById("portao-texto").textContent = t;
    document.getElementById("portao").classList.toggle("negado", negado);
  },
};
// fala sem travar o reconhecimento; devolve uma promessa para quem quiser esperar o fim
function dizer(texto) {
  const audio = new Audio("/api/voz?texto=" + encodeURIComponent(texto));
  return audio.play().then(() => new Promise((ok) => (audio.onended = audio.onerror = ok))).catch(() => {});
}
const espera = (ms) => new Promise((ok) => setTimeout(ok, ms));
const opcoesDeteccao = () => new faceapi.TinyFaceDetectorOptions({ inputSize: 320, scoreThreshold: 0.5 });

async function lerRostos(video, travado = false) {
  const rostos = await faceapi.detectAllFaces(video, opcoesDeteccao()).withFaceLandmarks().withFaceDescriptors();
  desenharMalha(video, rostos, travado);
  return rostos;
}

const progresso = (fracao) => (document.getElementById("progresso-barra").style.width = `${Math.min(1, fracao) * 100}%`);

// Animação de captura: contorno do rosto, pontos e mira por cima da câmera.
const GRUPOS = [[0, 16, false], [17, 21, false], [22, 26, false], [27, 30, false], [31, 35, false],
  [36, 41, true], [42, 47, true], [48, 59, true], [60, 67, true]];

function desenharMalha(video, rostos, travado) {
  const tela = document.getElementById("malha");
  if (tela.width !== video.videoWidth) { tela.width = video.videoWidth; tela.height = video.videoHeight; }
  const ctx = tela.getContext("2d");
  ctx.clearRect(0, 0, tela.width, tela.height);
  const cor = travado ? "#ffffff" : "#39d0ff";
  const pulso = 0.55 + 0.45 * Math.sin(Date.now() / 180);
  ctx.shadowColor = "#39d0ff";
  ctx.shadowBlur = 8;
  for (const r of rostos) {
    const pts = r.landmarks.positions;
    ctx.strokeStyle = cor;
    // fios até a ponta do nariz dão a cara de "malha" escaneada
    ctx.globalAlpha = 0.25;
    ctx.lineWidth = 1;
    for (const i of [0, 2, 4, 6, 8, 10, 12, 14, 16, 17, 21, 22, 26, 36, 45, 48, 54]) {
      ctx.beginPath(); ctx.moveTo(pts[i].x, pts[i].y); ctx.lineTo(pts[30].x, pts[30].y); ctx.stroke();
    }
    ctx.globalAlpha = 0.9;
    ctx.lineWidth = 1.5;
    for (const [de, ate, fechado] of GRUPOS) {
      ctx.beginPath();
      for (let i = de; i <= ate; i++) i === de ? ctx.moveTo(pts[i].x, pts[i].y) : ctx.lineTo(pts[i].x, pts[i].y);
      if (fechado) ctx.closePath();
      ctx.stroke();
    }
    ctx.fillStyle = cor;
    ctx.globalAlpha = pulso;
    for (const q of pts) { ctx.beginPath(); ctx.arc(q.x, q.y, 2, 0, Math.PI * 2); ctx.fill(); }
    // mira: quatro cantoneiras em volta do rosto
    const { x, y, width: w, height: h } = r.detection.box;
    const c = Math.min(w, h) * 0.22;
    ctx.globalAlpha = 1;
    ctx.lineWidth = 3;
    for (const [cx, cy, dx, dy] of [[x, y, 1, 1], [x + w, y, -1, 1], [x, y + h, 1, -1], [x + w, y + h, -1, -1]]) {
      ctx.beginPath(); ctx.moveTo(cx + dx * c, cy); ctx.lineTo(cx, cy); ctx.lineTo(cx, cy + dy * c); ctx.stroke();
    }
  }
}

async function cadastrar(video) {
  const descritores = [];
  const passos = ["olhe direto para a câmera", "vire um pouco para a esquerda", "vire um pouco para a direita", "levante um pouco o queixo", "abaixe um pouco o queixo", "olhe direto de novo"];
  for (const passo of passos) {
    portao.texto(`Primeiro acesso — ${passo}`);
    await espera(1200);
    for (;;) {
      const rostos = await lerRostos(video);
      if (rostos.length === 1 && rostos[0].detection.score > 0.7) {
        descritores.push(Array.from(rostos[0].descriptor));
        progresso(descritores.length / passos.length);
        break;
      }
      portao.texto(rostos.length > 1 ? "Só uma pessoa na frente da câmera" : `Primeiro acesso — ${passo}`);
      await espera(300);
    }
  }
  const r = await fetch("/api/rosto", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ descritores }) });
  if (!r.ok) throw new Error((await r.json()).detail);
}

async function reconhecer(video, conhecidos) {
  let acertos = 0;
  const fim = Date.now() + TEMPO_MAXIMO_MS;
  while (Date.now() < fim) {
    const rostos = await lerRostos(video, acertos > 0);
    const melhor = Math.min(Infinity, ...rostos.flatMap((r) => conhecidos.map((c) => faceapi.euclideanDistance(r.descriptor, c))));
    acertos = melhor < LIMITE_RECONHECER ? acertos + 1 : 0;
    progresso(acertos / ACERTOS_SEGUIDOS);
    portao.texto(rostos.length ? "Analisando…" : "Procurando um rosto…");
    if (acertos >= ACERTOS_SEGUIDOS) return true;
    await espera(250);
  }
  return false;
}

async function verificarIdentidade() {
  let video, boasVindas;
  try {
    // já conferiu desde que o PC ligou: entra direto, sem câmera
    const ficha = await (await fetch("/api/rosto")).json();
    if (ficha.ja_conferido) { portao.el.hidden = true; return false; }
    portao.el.hidden = false;
    portao.texto("Carregando reconhecimento facial…");
    await Promise.all([
      faceapi.nets.tinyFaceDetector.loadFromUri("/web/models"),
      faceapi.nets.faceLandmark68Net.loadFromUri("/web/models"),
      faceapi.nets.faceRecognitionNet.loadFromUri("/web/models"),
    ]);
    video = document.getElementById("camera");
    video.srcObject = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
    await new Promise((ok) => (video.onloadeddata = ok));

    const { descritores } = await (await fetch("/api/rosto")).json();
    if (!descritores.length) {
      fetch("/api/autenticacao", { method: "POST", headers: { "Content-Type": "application/json" }, body: '{"estado":"cadastrando"}' }).catch(() => {});
      dizer("Primeiro acesso. Vou registrar o seu rosto.");
      await cadastrar(video);
      portao.texto("Rosto cadastrado");
    } else {
      fetch("/api/autenticacao", { method: "POST", headers: { "Content-Type": "application/json" }, body: '{"estado":"verificando"}' }).catch(() => {});
      dizer("Verificando identidade.");
      for (;;) {
        portao.texto("Verificando identidade…");
        if (await reconhecer(video, descritores.map((d) => new Float32Array(d)))) break;
        portao.texto("Acesso negado", true);
        fetch("/api/autenticacao", { method: "POST", headers: { "Content-Type": "application/json" }, body: '{"estado":"negado"}' }).catch(() => {});
        dizer("Acesso negado. Não reconheço você.");
        const repetir = document.getElementById("portao-repetir");
        repetir.hidden = false;
        await new Promise((ok) => (repetir.onclick = ok));
        repetir.hidden = true;
      }
      portao.texto("Identidade confirmada");
    }
    fetch("/api/rosto/conferido", { method: "POST" }).catch(() => {});
    boasVindas = dizer(Math.random() < 0.5 ? "Identidade confirmada. Bem-vindo de volta, chefe." : "Identidade confirmada. Bem-vindo de volta, senhor.");
  } catch (e) {
    // sem câmera o portão não abre: a trava é o rosto, não há como pular
    portao.texto("Câmera indisponível: " + e.message, true);
    throw e;
  }
  progresso(1);
  portao.el.classList.add("confirmado");
  await lerRostos(video, true);
  await espera(900);
  video.srcObject.getTracks().forEach((t) => t.stop());
  portao.el.hidden = true;
  await boasVindas;
  return true;  // primeira vez desde que o PC ligou: a tela fala o resumo do dia
}
