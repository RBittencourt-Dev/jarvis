// Assistente de primeira vez (PC novo). Aparece antes de tudo quando falta algo essencial e some pra sempre ao concluir.
// 1. Quem é você e o que esse PC faz.  2. As peças: o que dá eu baixo (com barra, velocidade e log; continua de onde
// parou), o que é chave você cola, o que é manual tem o link oficial e "Já instalei, verificar de novo".  3. Pronto.
// Configurações → Instalação abre de novo quando quiser ("Abrir assistente").
(() => {
  const css = document.createElement("style");
  css.textContent = `
  #instalador { position: fixed; z-index: 40; inset: 0; display: grid; place-items: center; background: #02070dee; backdrop-filter: blur(6px); }
  #instalador[hidden] { display: none; }
  #instalador .caixa { width: min(860px, calc(100vw - 32px)); max-height: calc(100vh - 40px); overflow-y: auto; padding: 22px 26px;
    background: linear-gradient(135deg, #0c2236f7, #06121df7); border: 1px solid var(--ciano); box-shadow: 0 0 60px var(--ciano-fraco); }
  #instalador h2 { margin: 0 0 4px; font-weight: 300; letter-spacing: .2em; color: var(--ciano); text-transform: uppercase; font-size: 20px; }
  #instalador .passo { color: var(--apagado); font: 11px Consolas, monospace; letter-spacing: .25em; margin-bottom: 14px; }
  #instalador p.dica { color: var(--apagado); font-size: 13px; margin: 4px 0 12px; }
  #instalador label.campo { display: grid; grid-template-columns: 220px 1fr; gap: 6px 12px; align-items: center; margin: 8px 0; font-size: 14px; }
  #instalador input[type=text], #instalador input[type=password], #instalador select, #instalador textarea { background: #0b1d2dcc;
    border: 1px solid var(--ciano-fraco); color: var(--texto); padding: 9px 11px; font: inherit; width: 100%; }
  #instalador .itens { display: grid; gap: 8px; margin: 10px 0; }
  #instalador .item { border: 1px solid #39d0ff22; background: #0006; padding: 10px 12px; }
  #instalador .item .linha { display: flex; align-items: center; gap: 10px; }
  #instalador .item .nome { flex: 1; } #instalador .item .nome strong { display: block; } #instalador .item small { color: var(--apagado); }
  #instalador .item.ok .icone-st { color: #6dffb0; } #instalador .item.falta .icone-st { color: #ffb547; } #instalador .item.obrig.falta .icone-st { color: #ff6b4a; }
  #instalador .icone-st { font-size: 18px; width: 20px; text-align: center; }
  #instalador .barra { height: 4px; background: var(--ciano-fraco); margin-top: 8px; overflow: hidden; }
  #instalador .barra div { height: 100%; width: 0; background: var(--ciano); box-shadow: 0 0 8px var(--ciano); transition: width .5s; }
  #instalador .barra.indeterminada div { width: 30% !important; animation: vaivem 1.2s ease-in-out infinite alternate; }
  @keyframes vaivem { from { margin-left: 0; } to { margin-left: 70%; } }
  #instalador pre.log { max-height: 120px; overflow: auto; font: 11px/1.4 Consolas, monospace; background: #0008; padding: 6px 8px; margin: 6px 0 0; color: #b8f5d0; white-space: pre-wrap; }
  #instalador .rodape { display: flex; gap: 8px; justify-content: flex-end; margin-top: 14px; flex-wrap: wrap; }
  #instalador .botoes-item { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px; }
  #instalador .botoes-item button, #instalador .botoes-item a { padding: 5px 10px; font-size: 12px; }
  #instalador .aviso-net { border: 1px solid #ffb547; color: #ffb547; padding: 8px 12px; margin: 8px 0; font-size: 13px; }
  #instalador .maquina { font: 12px Consolas, monospace; color: var(--apagado); border: 1px solid #39d0ff1f; padding: 8px 12px; }
  @media (max-width: 700px) { #instalador label.campo { grid-template-columns: 1fr; } }`;
  document.head.append(css);
  const raiz = document.createElement("div");
  raiz.id = "instalador"; raiz.hidden = true;
  raiz.innerHTML = `<div class="caixa"></div>`;
  document.body.append(raiz);
  const caixa = raiz.firstElementChild;
  const h = (tag, props = {}, ...f) => { const el = Object.assign(document.createElement(tag), props); el.append(...f.flat().filter((x) => x != null)); return el; };
  const api = async (url, metodo = "GET", corpo) => (await fetch(url, { method: metodo, headers: { "Content-Type": "application/json" },
    body: corpo === undefined ? undefined : JSON.stringify(corpo) })).json();
  let resolver = null, estado = null, timer = null, hw = null;

  // ------------------------------------------------------------ passo 1: você e este PC
  function passo1() {
    const c = estado.config || {};
    const nome = h("input", { type: "text", value: c.nome_do_usuario || "", placeholder: "Ex.: Rafael" });
    const chamar = h("select");
    for (const [v, t] of [["misto", "chefe ou senhor (varia)"], ["chefe", "chefe"], ["senhor", "senhor"], ["nome", "pelo nome"]])
      chamar.append(h("option", { value: v, textContent: t, selected: (c.como_chamar || "misto") === v }));
    const cidade = h("input", { type: "text", value: c.casa?.cidade || "", placeholder: "Ex.: Porto Alegre" });
    const pc = h("input", { type: "text", value: c.perfil?.nome || "", placeholder: "Ex.: PC do colégio" });
    const ctx = h("textarea", { rows: 3, value: c.perfil?.contexto || "", placeholder: "Ex.: Aqui eu reviso o 7planner. Foque nele e anote o que eu pedir." });
    const rosto = h("input", { type: "checkbox", checked: c.usar_rosto !== false });
    const auto = h("input", { type: "checkbox", checked: true });
    const seguir = h("button", { textContent: "Continuar →" });
    seguir.onclick = async () => {
      seguir.disabled = true; seguir.textContent = "Salvando…";
      await api("/api/instalacao/perfil", "POST", { nome_do_usuario: nome.value.trim(), como_chamar: chamar.value, cidade: cidade.value.trim(),
        perfil: { nome: pc.value.trim() || "Meu PC", contexto: ctx.value.trim() }, usar_rosto: rosto.checked, autoinicio: auto.checked });
      passo2();
    };
    caixa.replaceChildren(
      h("h2", { textContent: "Bem-vindo ao J.A.R.V.I.S." }), h("div", { className: "passo", textContent: "PASSO 1 DE 3 · VOCÊ E ESTE PC" }),
      h("p", { className: "dica", textContent: "Cada PC pode ter um papel. O que você escrever aqui vai pro “cérebro” dele." }),
      h("label", { className: "campo" }, "Como você se chama", nome), h("label", { className: "campo" }, "Como ele te chama", chamar),
      h("label", { className: "campo" }, "Sua cidade (tempo, mapa)", cidade), h("label", { className: "campo" }, "Nome deste PC", pc),
      h("label", { className: "campo" }, "O que ele faz neste PC", ctx),
      h("label", { className: "campo" }, "Reconhecimento facial", h("span", {}, rosto, " pedir o rosto na 1ª abertura do dia")),
      h("label", { className: "campo" }, "Ligar junto com o Windows", h("span", {}, auto, " abrir sozinho quando o PC ligar")),
      h("div", { className: "rodape" }, seguir));
  }

  // ------------------------------------------------------------ passo 2: as peças
  let marcados = new Set();
  async function passo2() {
    clearInterval(timer);
    caixa.replaceChildren(h("h2", { textContent: "Peças do Jarvis" }), h("div", { className: "passo", textContent: "PASSO 2 DE 3 · CONFERINDO…" }));
    estado = await api("/api/instalacao");
    for (const i of estado.itens) if (i.tipo === "auto" && !i.ok && !(i.depende && !estado.itens.find((x) => x.id === i.depende)?.ok)) marcados.add(i.id);
    desenhar2();
    if (!hw) api("/api/instalacao/hardware").then((r) => { hw = r; desenhar2(); }).catch(() => {});
    let assinatura = "";
    timer = setInterval(async () => {
      const novo = await api("/api/instalacao").catch(() => null);
      if (!novo) return;
      const sig = JSON.stringify(novo.itens.map((i) => [i.ok, i.tarefa?.estado, i.tarefa?.pct, i.tarefa?.log?.length]));
      // só redesenha se algo mudou, e nunca com ele digitando (a chave não pode sumir do campo)
      if (sig === assinatura || caixa.contains(document.activeElement) && document.activeElement.tagName === "INPUT") return;
      assinatura = sig; estado = novo; desenhar2();
    }, 1500);
  }
  function desenhar2() {
    const itens = estado.itens;
    const net = itens.find((i) => i.id === "internet");
    const lista = h("div", { className: "itens" });
    for (const i of itens.filter((x) => x.id !== "internet")) {
      const t = i.tarefa;
      const div = h("div", { className: `item ${i.ok ? "ok" : "falta"} ${i.obrigatorio ? "obrig" : ""}` });
      const icone = h("span", { className: "icone-st", textContent: i.ok ? "✓" : t?.estado === "rodando" ? "⟳" : i.obrigatorio ? "!" : "○" });
      const info = h("div", { className: "nome" }, h("strong", { textContent: i.nome + (i.obrigatorio ? "" : " (opcional)") }),
        h("small", { textContent: [i.descricao, i.tamanho && !i.ok ? i.tamanho : ""].filter(Boolean).join(" · ") }));
      const linha = h("div", { className: "linha" }, icone, info);
      if (i.tipo === "auto" && !i.ok) {
        const bloqueado = i.depende && !itens.find((x) => x.id === i.depende)?.ok;
        const cb = h("input", { type: "checkbox", checked: marcados.has(i.id), disabled: bloqueado, title: bloqueado ? "Precisa do Ollama antes" : "" });
        cb.onchange = () => (cb.checked ? marcados.add(i.id) : marcados.delete(i.id));
        linha.append(cb);
      }
      div.append(linha);
      if (i.id === "modelo" && hw) {
        const sel = h("select", { style: "max-width:260px" });
        for (const m of estado.modelos) sel.append(h("option", { value: m, textContent: m + (m === hw.recomendado.modelo ? " (recomendado)" : ""), selected: m === estado.config.modelo }));
        sel.onchange = () => api("/api/instalacao/perfil", "POST", { modelo: sel.value });
        div.append(h("div", { className: "botoes-item" }, h("small", { textContent: "Modelo: " }), sel));
      }
      if (i.tipo === "chave" && !i.ok) {
        const campo = h("input", { type: "password", placeholder: "cole a chave aqui (gsk_…)", autocomplete: "off" });
        const salvar = h("button", { textContent: "Testar e guardar" });
        const msg = h("small");
        salvar.onclick = async () => { salvar.disabled = true; const r = await api("/api/instalacao/chave", "POST", { provedor: "groq", valor: campo.value });
          msg.textContent = r.texto; salvar.disabled = false; if (r.ok) estado = await api("/api/instalacao"), desenhar2(); };
        div.append(h("div", { className: "botoes-item" }, h("a", { className: "botao", href: i.link, target: "_blank", textContent: "Pegar a chave (grátis) ↗" })),
                   h("div", { className: "botoes-item" }, campo, salvar), msg);
      }
      if (i.tipo === "manual" && !i.ok) {
        const ver = h("button", { className: "secundario", textContent: "Já instalei, verificar de novo" });
        ver.onclick = () => passo2();
        div.append(h("div", { className: "botoes-item" }, h("a", { className: "botao", href: i.link, target: "_blank", textContent: "Baixar no site oficial ↗" }), ver));
      }
      if (t) {
        const barra = h("div", { className: "barra" + (t.pct == null && t.estado === "rodando" ? " indeterminada" : "") }, h("div", { style: `width:${t.pct ?? 0}%` }));
        const status = h("small", { textContent: t.estado === "rodando" ? `${t.pct != null ? t.pct + "%" : "instalando…"} ${t.velocidade || ""}`
                                                  : t.estado === "ok" ? "concluído" : "parou com erro — clique em Instalar de novo (continua de onde parou)" });
        const log = h("pre", { className: "log", textContent: (t.log || []).join("\n") });
        div.append(barra, status, log);
        requestAnimationFrame(() => (log.scrollTop = log.scrollHeight));
      }
      lista.append(div);
    }
    const rodando = itens.some((i) => i.tarefa?.estado === "rodando");
    const faltaObrig = itens.filter((i) => i.obrigatorio && !i.ok);
    const tudo = h("button", { textContent: "Instalar tudo", disabled: rodando });
    tudo.onclick = () => instalar(itens.filter((i) => i.tipo === "auto" && !i.ok && !(i.depende && !itens.find((x) => x.id === i.depende)?.ok)).map((i) => i.id));
    const sel = h("button", { className: "secundario", textContent: "Instalar só os marcados", disabled: rodando });
    sel.onclick = () => instalar([...marcados]);
    const proximo = h("button", { className: faltaObrig.length ? "secundario" : "", textContent: faltaObrig.length ? "Pular por agora →" : "Continuar →" });
    proximo.onclick = () => { clearInterval(timer); passo3(faltaObrig); };
    const maquina = hw ? h("div", { className: "maquina", textContent:
      `ESTA MÁQUINA · ${hw.hardware.cpu} · ${hw.hardware.nucleos} núcleos · ${hw.hardware.ram_gb} GB RAM · ` +
      (hw.hardware.vram_gb ? `placa de vídeo ${hw.hardware.vram_gb} GB` : "sem placa de vídeo dedicada") + ` · ${hw.hardware.disco_livre_gb} GB livres` +
      `\nCÉREBRO LOCAL RECOMENDADO · ${hw.recomendado.modelo} (${hw.recomendado.porque})` }) : h("div", { className: "maquina", textContent: "Analisando esta máquina…" });
    maquina.style.whiteSpace = "pre-wrap";
    caixa.replaceChildren(...[h("h2", { textContent: "Peças do Jarvis" }), h("div", { className: "passo", textContent: "PASSO 2 DE 3 · O QUE FALTA NESTE PC" }),
      net && !net.ok ? h("div", { className: "aviso-net", textContent: "Sem internet agora. Pode pular e voltar depois: os downloads continuam de onde pararam." }) : null,
      maquina, lista, h("div", { className: "rodape" }, sel, tudo, proximo)].filter(Boolean));
  }
  async function instalar(ids) {
    for (const id of ids) await api("/api/instalacao/instalar", "POST", { id });
    estado = await api("/api/instalacao"); desenhar2();
  }

  // ------------------------------------------------------------ passo 3: pronto
  function passo3(faltando) {
    const fim = h("button", { textContent: "Abrir o Jarvis" });
    fim.onclick = async () => { await api("/api/instalacao/concluir", "POST"); raiz.hidden = true; resolver && resolver(); };
    const voltar = h("button", { className: "secundario", textContent: "← Voltar às peças" });
    voltar.onclick = () => passo2();
    caixa.replaceChildren(h("h2", { textContent: faltando.length ? "Quase lá" : "Tudo pronto" }), h("div", { className: "passo", textContent: "PASSO 3 DE 3" }),
      h("p", { textContent: faltando.length ? `Ainda falta: ${faltando.map((i) => i.nome).join(", ")}. O Jarvis abre assim mesmo, mas sem isso ele fica limitado. Dá pra terminar depois em Configurações → Instalação.`
                                           : "Pode falar comigo. Se precisar mudar algo: Configurações (botão de controles, embaixo à esquerda)." }),
      h("p", { className: "dica", textContent: "Spotify, conectores (Canva, Notion, Google…) e o resto ficam em Configurações quando você quiser." }),
      h("div", { className: "rodape" }, voltar, fim));
  }

  // ------------------------------------------------------------ entrada
  window.assistenteDeInstalacao = async (forcar = false) => {
    try { if (!forcar && !(await api("/api/instalacao/precisa")).precisa) return; } catch { return; }  // decide na hora
    raiz.hidden = false;
    caixa.replaceChildren(h("h2", { textContent: "Bem-vindo ao J.A.R.V.I.S." }), h("div", { className: "passo", textContent: "CONFERINDO ESTE PC…" }));
    api("/api/instalacao/hardware").then((r) => (hw = r)).catch(() => {});  // já vai analisando a máquina
    try { estado = await api("/api/instalacao"); } catch { raiz.hidden = true; return; }
    passo1();
    await new Promise((ok) => (resolver = ok));
  };
})();
