// Entonação (25/10): o Jarvis entende COMO o Rafael falou, não só o QUE falou.
// Pedido dele: "faz ele entender minha entonação".
//
// O reconhecimento do Chrome só devolve texto. Aqui eu escuto o mesmo microfone e meço, enquanto ele fala:
//   - volume (alto / normal / baixo), comparado com o jeito NORMAL dele (a média vai se ajustando sozinha)
//   - velocidade (palavras por segundo)
//   - variação do tom (animado / neutro / monótono)
//   - o fim da frase: a voz SOBE (pergunta, dúvida) ou DESCE (afirmação, ordem)
// Nada de áudio sai do PC: só esses números vão junto com o texto pro servidor.
(() => {
  const quadros = [];            // {t, db, f0} dos últimos 20 s
  const base = { db: null, f0: null, pps: null };  // o "normal" dele (média que se ajusta a cada frase)
  let analisador = null, buffer = null, taxa = 48000;

  async function ligar() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      const ctx = new AudioContext();
      taxa = ctx.sampleRate;
      analisador = ctx.createAnalyser();
      analisador.fftSize = 2048;
      buffer = new Float32Array(analisador.fftSize);
      ctx.createMediaStreamSource(stream).connect(analisador);
      setInterval(medir, 50);
      document.addEventListener("click", () => ctx.state === "suspended" && ctx.resume(), { once: true });
    } catch (e) { console.warn("entonação desligada:", e.message); }
  }

  // altura da voz (Hz) por autocorrelação: acha de quanto em quanto tempo a onda se repete
  function tomDaVoz(sinal) {
    let melhor = -1, melhorCorr = 0;
    const min = Math.floor(taxa / 400), max = Math.floor(taxa / 70);  // voz humana: 70 a 400 Hz
    for (let atraso = min; atraso <= max; atraso++) {
      let corr = 0;
      for (let i = 0; i < 1024; i++) corr += sinal[i] * sinal[i + atraso];
      if (corr > melhorCorr) { melhorCorr = corr; melhor = atraso; }
    }
    return melhor > 0 ? taxa / melhor : null;
  }

  function medir() {
    analisador.getFloatTimeDomainData(buffer);
    let soma = 0;
    for (const v of buffer) soma += v * v;
    const db = 20 * Math.log10(Math.sqrt(soma / buffer.length) + 1e-9);
    const agora = performance.now();
    const falando = db > -50;  // abaixo disso é silêncio/ruído de fundo
    quadros.push({ t: agora, db, f0: falando ? tomDaVoz(buffer) : null, voz: falando });
    while (quadros.length && agora - quadros[0].t > 20000) quadros.shift();
  }

  const media = (xs) => xs.reduce((a, b) => a + b, 0) / (xs.length || 1);
  const mediana = (xs) => { const s = [...xs].sort((a, b) => a - b); return s.length ? s[Math.floor(s.length / 2)] : null; };
  const ajustar = (chave, valor) => { if (valor != null) base[chave] = base[chave] == null ? valor : base[chave] * 0.85 + valor * 0.15; };

  // resumo da frase que ele acabou de falar (inicio/fim em performance.now(), palavras = quantas o Chrome ouviu)
  function resumo(inicio, fim, palavras) {
    const voz = quadros.filter((q) => q.t >= inicio && q.t <= fim && q.voz);
    if (voz.length < 6) return null;  // frase curtinha demais pra medir
    const db = mediana(voz.map((q) => q.db));
    const f0s = voz.map((q) => q.f0).filter((f) => f && f > 70 && f < 400);
    const f0 = mediana(f0s);
    const duracao = (voz[voz.length - 1].t - voz[0].t) / 1000 || 1;
    const pps = palavras / duracao;
    const r = {};
    if (base.db != null) r.volume = db > base.db + 6 ? "alto" : db < base.db - 6 ? "baixo" : "normal";
    if (base.pps != null) r.ritmo = pps > base.pps * 1.3 ? "rápido" : pps < base.pps * 0.75 ? "devagar" : "normal";
    if (f0s.length > 8) {
      const variacao = Math.sqrt(media(f0s.map((f) => (f - f0) ** 2))) / f0;
      r.energia = variacao > 0.22 ? "animado" : variacao < 0.08 ? "monótono" : "neutro";
      // fim da frase: os últimos ~0,4 s de voz comparados com o resto
      const fimVoz = voz[voz.length - 1].t;
      const ultimos = voz.filter((q) => q.t > fimVoz - 400 && q.f0).map((q) => q.f0);
      const antes = voz.filter((q) => q.t <= fimVoz - 400 && q.t > fimVoz - 1600 && q.f0).map((q) => q.f0);
      if (ultimos.length >= 3 && antes.length >= 3) {
        const d = (mediana(ultimos) - mediana(antes)) / mediana(antes);
        r.final = d > 0.1 ? "sobe" : d < -0.1 ? "desce" : "reto";
      }
      if (base.f0 != null) r.altura = f0 > base.f0 * 1.15 ? "mais aguda que o normal" : f0 < base.f0 * 0.88 ? "mais grave que o normal" : "normal";
    }
    ajustar("db", db); ajustar("f0", f0); ajustar("pps", pps);
    return Object.keys(r).length ? r : null;
  }

  window.entonacao = { resumo, base };
  ligar();
})();
