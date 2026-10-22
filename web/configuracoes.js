// Configurações do Jarvis: um painel com abas. O painel de Automações (⚙) continua existindo do jeito que era;
// a aba "Automações" daqui só mostra ele dentro (o mesmo elemento, o mesmo automacoes.js).
(() => {
  const ABAS = [
    ["geral", "Geral"], ["modelos", "Modelos"], ["voz", "Voz"], ["proatividade", "Proatividade"], ["memoria", "Memória"],
    ["privacidade", "Privacidade"], ["automacoes", "Automações"], ["falas", "Falas programadas"], ["conectores", "Conectores"], ["instalacao", "Instalação"],
  ];
  const painel = $("configuracoes"), corpo = $("cfg-corpo"), abas = $("cfg-abas"), botao = $("abrir-configuracoes");
  let dados = null, abaAtual = "geral";
  const h = (tag, props = {}, ...filhos) => {
    const el = Object.assign(document.createElement(tag), props);
    for (const f of filhos.flat()) if (f != null) el.append(f.nodeType ? f : document.createTextNode(String(f)));
    return el;
  };
  const api = async (url, metodo = "GET", corpo_) => {
    const r = await fetch(url, { method: metodo, headers: { "Content-Type": "application/json" },
                                 body: corpo_ === undefined ? undefined : JSON.stringify(corpo_) });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.status);
    return r.headers.get("content-type")?.includes("json") ? r.json() : r;
  };
  const aviso = (texto, erro = false) => {
    const a = $("cfg-aviso");
    a.textContent = texto; a.className = erro ? "erro" : ""; a.hidden = false;
    clearTimeout(aviso.t); aviso.t = setTimeout(() => (a.hidden = true), 4000);
  };
  const salvarConfig = async (novos) => {
    try { await api("/api/config", "POST", novos); aviso("Salvo."); dados = await api("/api/config"); }
    catch (e) { aviso("Não salvei: " + e.message, true); }
  };
  const campo = (rotulo, el, dica) => h("label", { className: "cfg-campo" }, h("span", {}, rotulo), el, dica ? h("small", {}, dica) : null);
  const secao = (titulo, ...filhos) => h("section", { className: "cfg-secao" }, h("h3", {}, titulo), ...filhos);
  const seletor = (opcoes, valor, aoMudar) => {
    const s = h("select");
    for (const [v, t] of opcoes) s.append(h("option", { value: v, textContent: t, selected: String(v) === String(valor) }));
    s.onchange = () => aoMudar(s.value);
    return s;
  };
  const chave = (ligado, aoMudar) => {
    const c = h("input", { type: "checkbox", checked: !!ligado, className: "cfg-chave" });
    c.onchange = () => aoMudar(c.checked);
    return c;
  };

  // ------------------------------------------------------------ abas
  const telas = {
    geral() {
      const c = dados.config;
      const nome = h("input", { value: c.nome_do_usuario || "", placeholder: "Rafael" });
      nome.onchange = () => salvarConfig({ nome_do_usuario: nome.value.trim() });
      const arquivo = h("input", { type: "file", accept: ".zip", hidden: true });
      arquivo.onchange = async () => {
        const f = arquivo.files[0]; if (!f) return;
        const b64 = await new Promise((ok) => { const r = new FileReader(); r.onload = () => ok(r.result.split(",")[1]); r.readAsDataURL(f); });
        try { const r = await api("/api/importar", "POST", { zip_base64: b64 }); aviso(`Importado: ${r.importados.length} arquivos. Reinicie o Jarvis.`); }
        catch (e) { aviso("Falhou: " + e.message, true); }
      };
      const pcNome = h("input", { value: c.perfil?.nome || "", placeholder: "Ex.: PC do colégio" });
      const pcCtx = h("textarea", { rows: 3, value: c.perfil?.contexto || "", placeholder: "Ex.: Aqui eu reviso o projeto 7planner. Foque nele e anote o que eu pedir." });
      const salvarPerfil = () => salvarConfig({ perfil: { nome: pcNome.value.trim(), contexto: pcCtx.value.trim() } });
      pcNome.onchange = pcCtx.onchange = salvarPerfil;
      const cidade = h("input", { value: c.casa?.cidade || "", placeholder: "Sua cidade (tempo, mapa, “perto de mim”)" });
      cidade.onchange = () => salvarConfig({ casa: { ...(c.casa || {}), cidade: cidade.value.trim() } });
      const autoinicio = h("input", { type: "checkbox", className: "cfg-chave" });
      api("/api/instalacao/autoinicio").then((r) => (autoinicio.checked = r.ligado)).catch(() => {});
      autoinicio.onchange = async () => { await api("/api/instalacao/autoinicio", "POST", { ligado: autoinicio.checked }); aviso(autoinicio.checked ? "Liga junto com o Windows." : "Não liga mais sozinho."); };
      return [
        secao("Este PC",
          campo("Nome deste PC", pcNome),
          campo("O que eu faço neste PC", pcCtx, "Vai pro “cérebro” dele: cada PC pode ter um papel diferente."),
          campo("Reconhecimento facial neste PC", chave(c.usar_rosto !== false, (v) => salvarConfig({ usar_rosto: v })),
            "Desligado: abre direto, sem câmera (bom pra PC que não é só seu)."),
          campo("Ligar junto com o Windows", autoinicio)),
        secao("Você",
          campo("Como você se chama", nome),
          campo("Cidade", cidade),
          campo("Como ele te chama", seletor([["chefe", "chefe"], ["senhor", "senhor"], ["nome", "pelo nome"], ["misto", "varia (chefe/senhor)"]],
            c.como_chamar || "misto", (v) => salvarConfig({ como_chamar: v }))),
          campo("Idioma", seletor([["pt-BR", "Português (Brasil)"]], "pt-BR", () => {}), "A voz e o ouvido estão afinados pro português do Brasil.")),
        secao("Aparência",
          campo("Tema", seletor([["normal", "Azul (normal)"], ["caverna", "Vermelho (modo caverna)"]], dados.modo, (v) => salvarConfig({ tema: v }))),
          campo("Animações leves", chave(c.animacoes_leves, (v) => { salvarConfig({ animacoes_leves: v }); document.body.classList.toggle("leve", v); }),
            "Menos brilho e movimento (pra PC mais fraco ou pra quem prefere).")),
        secao("Levar pra outro PC",
          h("p", { className: "cfg-texto" }, "Exporta configurações e tudo que ele aprendeu (memória, habilidades, contatos, automações). As chaves não vão: o cofre só abre neste PC."),
          h("div", { className: "botoes" },
            h("a", { className: "botao", href: "/api/exportar", textContent: "Exportar meus dados" }),
            Object.assign(h("button", { className: "secundario", textContent: "Importar…" }), { onclick: () => arquivo.click() }), arquivo)),
      ];
    },

    modelos() {
      const c = dados.config, b = dados.benchmark;
      const tabela = h("table", { className: "cfg-tabela" },
        h("tr", {}, h("th", {}, "Modelo"), h("th", {}, "Tokens/s"), h("th", {}, "Início")),
        ...(b?.locais || []).map((m) => h("tr", {}, h("td", {}, m.modelo + (m.modelo === b.recomendado ? " ★" : "")),
          h("td", {}, m.tokens_s ?? "erro"), h("td", {}, m.processar_pedido_s != null ? m.processar_pedido_s + " s" : "–"))));
      const rodar = h("button", { textContent: "Rodar benchmark" });
      rodar.onclick = async () => {
        rodar.disabled = true; rodar.textContent = "Medindo… (1–3 min)";
        try { const r = await api("/api/benchmark", "POST"); aviso(r.trocou ? `Troquei o modelo local pra ${r.recomendado}.` : `Recomendado: ${r.recomendado || "–"}.`); }
        catch (e) { aviso("Falhou: " + e.message, true); }
        dados = await api("/api/config"); mostrar("modelos");
      };
      return [
        secao("Cérebro principal",
          h("p", { className: "cfg-texto" }, `Agora: ${dados.cerebro}. ` + (dados.nuvem.length
            ? `Na nuvem (grátis): ${dados.nuvem.join(", ")} — rápido. Sem internet ele cai sozinho no modelo local.`
            : "Sem chave da nuvem: tudo roda no modelo local (mais lento). Ponha a chave do Groq em Privacidade → Cofre."))),
        secao("Modelo local (reserva, Ollama)",
          campo("Modelo", seletor((dados.modelos_locais || [c.modelo]).map((m) => [m, m]), c.modelo, (v) => salvarConfig({ modelo: v })),
            "Um modelo carregado por vez. Sem GPU, 3B é o ponto certo nesse PC."),
          campo("Contexto", seletor([[2048, "2048"], [4096, "4096 (padrão)"], [8192, "8192 (mais RAM, mais lento)"]], c.contexto || 4096,
            (v) => salvarConfig({ contexto: +v }))),
          campo("Manter carregado (keep_alive)", seletor([["5m", "5 min"], ["30m", "30 min"], ["2h", "2 h (padrão)"], ["24h", "24 h"]],
            c.keep_alive || "2h", (v) => salvarConfig({ keep_alive: v }))),
          campo("Limite de RAM pro modelo", seletor([[6, "6 GB"], [8, "8 GB"], [10, "10 GB (padrão)"], [12, "12 GB"]], c.limite_ram_gb || 10,
            (v) => salvarConfig({ limite_ram_gb: +v })), `PC: ${dados.maquina.ram_gb} GB de RAM, ${dados.maquina.nucleos} núcleos.`)),
        secao("Velocidade (benchmark)",
          b ? h("p", { className: "cfg-texto" }, `Último: ${new Date(b.quando * 1000).toLocaleString("pt-BR")}` +
            (b.nuvem?.resposta_s ? ` · nuvem respondeu em ${b.nuvem.resposta_s} s` : "")) : h("p", { className: "cfg-texto" }, "Nunca rodou."),
          tabela, h("div", { className: "botoes" }, rodar)),
      ];
    },

    voz() {
      const c = dados.config;
      const vozSel = h("select"); vozSel.append(h("option", { textContent: c.voz }));
      api("/api/vozes").then((vs) => {
        vozSel.innerHTML = "";
        for (const v of vs) vozSel.append(h("option", { value: v.nome, textContent: `${v.nome.replace(/^pt-..-/, "").replace("Neural", "")} · ${v.local} · ${v.genero === "Male" ? "masc." : "fem."}`, selected: v.nome === c.voz }));
      }).catch(() => {});
      vozSel.onchange = () => salvarConfig({ voz: vozSel.value });
      const num = (txt, padrao) => parseInt(String(txt || padrao).replace(/[^\d-]/g, ""), 10) || 0;
      const ritmo = h("input", { type: "range", min: -20, max: 50, value: num(c.voz_velocidade, "+18") });
      const tom = h("input", { type: "range", min: -20, max: 15, value: num(c.voz_tom, "-3") });
      const vol = h("input", { type: "range", min: 10, max: 100, value: c.volume ?? 100 });
      const rot = (el, f) => { const s = h("output", { textContent: f(el.value) }); el.oninput = () => (s.textContent = f(el.value)); return s; };
      ritmo.onchange = () => salvarConfig({ voz_velocidade: `${ritmo.value >= 0 ? "+" : ""}${ritmo.value}%` });
      tom.onchange = () => salvarConfig({ voz_tom: `${tom.value >= 0 ? "+" : ""}${tom.value}Hz` });
      vol.onchange = () => { salvarConfig({ volume: +vol.value }); window.volumeDaVoz = vol.value / 100; };
      const ouvir = h("button", { className: "secundario", textContent: "Ouvir amostra" });
      ouvir.onclick = () => { const a = new Audio("/api/voz?texto=" + encodeURIComponent("Tudo certo por aqui, chefe. Essa é a minha voz agora.") + "&t=" + Date.now()); a.volume = vol.value / 100; a.play(); };
      const mic = h("select");
      navigator.mediaDevices?.enumerateDevices().then((ds) => {
        for (const d of ds.filter((x) => x.kind === "audioinput")) mic.append(h("option", { textContent: d.label || "Microfone" }));
      }).catch(() => {});
      return [
        secao("Voz do Jarvis",
          campo("Voz", vozSel), campo("Velocidade", h("div", { className: "cfg-linha" }, ritmo, rot(ritmo, (v) => `${v >= 0 ? "+" : ""}${v}%`))),
          campo("Tom", h("div", { className: "cfg-linha" }, tom, rot(tom, (v) => `${v >= 0 ? "+" : ""}${v} Hz`))),
          campo("Volume", h("div", { className: "cfg-linha" }, vol, rot(vol, (v) => `${v}%`))),
          h("div", { className: "botoes" }, ouvir)),
        secao("Ouvido",
          campo("Microfone", mic, "A tela usa o microfone padrão do Windows (Configurações → Sistema → Som → Entrada). Aqui é só pra conferir qual está ligado."),
          campo("Palavra de ativação", h("input", { value: "Jarvis", disabled: true }),
            "Fixa em “Jarvis” (o detector offline foi treinado nessa palavra). Interrompe a fala dele também.")),
      ];
    },

    proatividade() {
      const p = dados.proatividade;
      const de = h("input", { type: "time", value: p.silencio_de }), ate = h("input", { type: "time", value: p.silencio_ate });
      const horario = () => salvarConfig({ proatividade: { silencio_de: de.value, silencio_ate: ate.value } });
      de.onchange = ate.onchange = horario;
      return [
        secao("Quanto ele fala sozinho",
          campo("Nível", seletor([["alto", "Alto — avisa tudo e sugere automações"], ["baixo", "Baixo — só lembretes e problemas sérios"],
                                  ["desligado", "Desligado — só o que você marcou (lembrete, pomodoro)"]], p.nivel,
            (v) => salvarConfig({ proatividade: { nivel: v } }))),
          campo("Sugerir o próximo passo depois de responder", chave(p.sugerir_proximo_passo, (v) => salvarConfig({ proatividade: { sugerir_proximo_passo: v } })))),
        secao("Não perturbe",
          campo("Ligado agora", chave(p.nao_perturbe, (v) => salvarConfig({ proatividade: { nao_perturbe: v } })),
            "Também por voz: “ativa o não perturbe”. Avisos viram pop-up mudo."),
          campo("Silêncio automático", h("div", { className: "cfg-linha" }, "das", de, "às", ate))),
      ];
    },

    // falas programadas: num horário ele FALA sozinho (mesmo com a tela fechada, pelo segundo plano)
    falas() {
      const DIAS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];
      const lista = h("ul", { className: "cfg-itens" }, "Carregando…");
      const quando = (f) => f.data ? `${f.data.slice(8, 10)}/${f.data.slice(5, 7)} às ${f.hora} (uma vez)`
        : (f.dias.length === 7 ? "todo dia" : f.dias.map((d) => DIAS[d]).join(", ")) + ` às ${f.hora}`;
      const carregar = async () => {
        const { falas } = await api("/api/falas-programadas");
        lista.innerHTML = "";
        if (!falas.length) lista.append(h("li", {}, h("div", {}, h("small", {}, "Nenhuma ainda. Crie aqui embaixo ou fale: “todo dia às 18h fala hora de ir embora”."))));
        for (const f of falas.sort((a, b) => a.hora.localeCompare(b.hora))) {
          const ativa = chave(f.ativa, async (v) => { await api("/api/falas-programadas", "POST", { ...f, ativa: v }); aviso(v ? "Ligada." : "Desligada."); });
          const ouvir = h("button", { className: "secundario", textContent: "Ouvir" });
          ouvir.onclick = () => api("/api/falas-programadas/testar", "POST", { texto: f.texto });
          const apagar = h("button", { className: "secundario", textContent: "Apagar" });
          apagar.onclick = async () => { await api("/api/falas-programadas/" + f.id, "DELETE"); carregar(); };
          lista.append(h("li", {}, ativa, h("div", {}, h("strong", {}, f.texto), h("small", {}, quando(f))), ouvir, apagar));
        }
      };
      carregar().catch((e) => (lista.textContent = "Erro: " + e.message));
      const texto = h("input", { placeholder: "O que ele vai falar. Ex.: São {hora}, chefe. Hora de ir embora." });
      const hora = h("input", { type: "time", value: "18:00" });
      const marcas = DIAS.map((d, i) => { const c = h("input", { type: "checkbox", checked: true, className: "cfg-chave" }); c.dataset.dia = i;
                                          return h("span", { className: "cfg-linha" }, c, d); });
      const umaVez = h("input", { type: "date" });
      const criar = h("button", { textContent: "Programar fala" });
      criar.onclick = async () => {
        const dias = marcas.map((m) => m.firstChild).filter((c) => c.checked).map((c) => +c.dataset.dia);
        try {
          await api("/api/falas-programadas", "POST", { texto: texto.value, hora: hora.value, dias, data: umaVez.value || null });
          texto.value = ""; umaVez.value = ""; aviso("Programado."); carregar();
        } catch (e) { aviso("Não salvei: " + e.message, true); }
      };
      const testar = h("button", { className: "secundario", textContent: "Ouvir agora" });
      testar.onclick = () => texto.value.trim() && api("/api/falas-programadas/testar", "POST", { texto: texto.value });
      return [
        secao("Falas programadas", h("p", { className: "cfg-texto" },
          "No horário ele fala sozinho, com a tela aberta ou fechada (o PC precisa estar ligado). Dá pra usar {hora}, {data} e {dia} na frase."), lista),
        secao("Nova fala",
          campo("Frase", texto),
          campo("Horário", hora),
          campo("Dias", h("div", { className: "cfg-linha" }, ...marcas)),
          campo("Só uma vez, no dia", umaVez, "Se escolher um dia aqui, os dias da semana são ignorados e ela some depois de falada."),
          h("div", { className: "botoes" }, criar, testar)),
      ];
    },

    memoria() {
      const caixa = h("div", { className: "cfg-lista" }, "Carregando…");
      api("/api/memoria").then((m) => {
        caixa.innerHTML = "";
        const fatos = h("textarea", { rows: Math.min(14, m.fatos.length + 2), value: m.fatos.join("\n") });
        const salvar = h("button", { textContent: "Salvar memória" });
        salvar.onclick = async () => { await api("/api/memoria", "POST", { fatos: fatos.value.split("\n") }); aviso("Memória atualizada."); };
        caixa.append(secao("O que ele sabe de você (um fato por linha)", fatos, h("div", { className: "botoes" }, salvar)));
        const habs = h("ul", { className: "cfg-itens" });
        for (const hb of m.habilidades) {
          const apagar = h("button", { className: "secundario", textContent: "Esquecer" });
          apagar.onclick = async () => { await fetch("/api/memoria/habilidade?nome=" + encodeURIComponent(hb.nome), { method: "DELETE" }); habs.removeChild(li); };
          const li = h("li", {}, h("div", {}, h("strong", {}, hb.nome), h("small", {}, `quando ${hb.quando} → ${hb.como}`)), apagar);
          habs.append(li);
        }
        caixa.append(secao("Habilidades que você ensinou", m.habilidades.length ? habs : h("p", { className: "cfg-texto" }, "Nenhuma ainda. Fale “aprende que…”.")));
        const frases = h("ul", { className: "cfg-itens" });
        for (const [frase, cmd] of Object.entries(m.frases)) {
          const apagar = h("button", { className: "secundario", textContent: "Esquecer" });
          const li = h("li", {}, h("div", {}, h("strong", {}, frase), h("small", {}, "→ " + cmd)), apagar);
          apagar.onclick = async () => { await fetch("/api/memoria/frase?frase=" + encodeURIComponent(frase), { method: "DELETE" }); li.remove(); };
          frases.append(li);
        }
        caixa.append(secao("Frases que ele aprendeu a entender", Object.keys(m.frases).length ? frases : h("p", { className: "cfg-texto" }, "Nenhuma.")));
        const esquecer = h("button", { className: "secundario", textContent: "Esquecer o resumo" });
        esquecer.onclick = async () => { await fetch("/api/memoria/resumo", { method: "DELETE" }); aviso("Resumo esquecido."); esquecer.disabled = true; };
        caixa.append(secao("Resumo das últimas conversas", h("p", { className: "cfg-texto pre" }, m.resumo || "(vazio)"), h("div", { className: "botoes" }, esquecer)));
      });
      return [caixa];
    },

    privacidade() {
      const c = dados.config;
      const nomes = h("ul", { className: "cfg-itens" });
      const desenharCofre = (lista) => {
        nomes.innerHTML = "";
        for (const n of lista) {
          const apagar = h("button", { className: "secundario", textContent: "Apagar" });
          apagar.onclick = async () => { await fetch("/api/cofre/" + encodeURIComponent(n), { method: "DELETE" }); desenharCofre((await api("/api/cofre")).nomes); };
          nomes.append(h("li", {}, h("div", {}, h("strong", {}, n), h("small", {}, "•••••• (criptografado)")), apagar));
        }
        if (!lista.length) nomes.append(h("li", { className: "vazio" }, "Cofre vazio."));
      };
      desenharCofre(dados.cofre);
      const tipo = seletor([["groq", "Chave do Groq (gsk_…)"], ["gemini", "Chave do Gemini (AIza…)"],
                            ["google_places", "Chave do Google Places (foto das lojas)"], ["windy", "Chave da Windy (câmeras ao vivo)"], ["outro", "Outro nome…"]], "groq", () => {
        outroNome.hidden = tipo.querySelector("select")?.value !== "outro";
      });
      const sel = tipo; const outroNome = h("input", { placeholder: "nome da chave", hidden: true });
      sel.onchange = () => (outroNome.hidden = sel.value !== "outro");
      const valor = h("input", { type: "password", placeholder: "cole aqui", autocomplete: "off" });
      const guardar = h("button", { textContent: "Guardar no cofre" });
      guardar.onclick = async () => {
        if (!valor.value.trim()) return;
        await api("/api/cofre", "POST", { nome: sel.value === "outro" ? outroNome.value : sel.value, valor: valor.value });
        valor.value = ""; aviso("Guardado criptografado."); desenharCofre((await api("/api/cofre")).nomes);
      };
      const proteger = h("button", { className: "secundario", textContent: "Proteger chaves antigas (groq.json…)" });
      proteger.onclick = async () => { const r = await api("/api/cofre/proteger", "POST"); aviso(r.movidas.length ? "Movidas pro cofre: " + r.movidas.join(", ") : "Nada pra mover."); desenharCofre((await api("/api/cofre")).nomes); };
      const log = h("table", { className: "cfg-tabela log" });
      const carregarLog = async () => {
        const linhas = await api("/api/registro?n=150");
        log.innerHTML = "";
        log.append(h("tr", {}, h("th", {}, "Quando"), h("th", {}, "Pedido"), h("th", {}, "O que fez")));
        for (const r of linhas) log.append(h("tr", { className: r.desfazer && !r.desfeito ? "desfazivel" : "" },
          h("td", {}, new Date(r.quando * 1000).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })),
          h("td", {}, r.pedido), h("td", {}, (r.ferramentas?.length ? `[${r.ferramentas.join(", ")}] ` : "") + r.resposta)));
        if (!linhas.length) log.append(h("tr", {}, h("td", { colSpan: 3 }, "Nada registrado ainda.")));
      };
      carregarLog();
      const desfazer = h("button", { textContent: "Desfazer a última ação" });
      desfazer.onclick = async () => { const r = await api("/api/registro/desfazer", "POST"); aviso(r.fala); carregarLog(); };
      const limpar = h("button", { className: "secundario", textContent: "Apagar o histórico" });
      limpar.onclick = async () => { await fetch("/api/registro", { method: "DELETE" }); carregarLog(); };
      return [
        secao("Confirmação",
          campo("Pedir “sim” antes de ações perigosas", chave(c.confirmar_acoes_perigosas, (v) => salvarConfig({ confirmar_acoes_perigosas: v })),
            "Comandos que apagam, instalam, desligam ou mandam dados pra fora. Apagar/editar arquivo seu e conectores que enviam, publicam ou gastam pedem SEMPRE, mesmo desligado.")),
        secao("Cofre de chaves (criptografado pelo Windows)",
          h("p", { className: "cfg-texto" }, "Só tokens e chaves de API que você gerou. Nunca senhas. Só abre com a sua conta, neste PC."),
          nomes, h("div", { className: "cfg-linha" }, sel, outroNome, valor), h("div", { className: "botoes" }, guardar, proteger)),
        secao("Tudo que ele fez (log)", h("div", { className: "botoes" }, desfazer, limpar), h("div", { className: "cfg-rolagem" }, log)),
      ];
    },

    automacoes() {
      const lugar = h("div", { className: "cfg-automacoes" });
      const auto = $("automacoes");
      lugar.append(auto);
      auto.hidden = false;
      auto.classList.add("embutido");
      // depois de estar na tela: recarrega a lista do jeito do automacoes.js (fecha e abre pelo próprio ⚙)
      setTimeout(() => { $("abrir-automacoes").click(); $("abrir-automacoes").click(); auto.hidden = false; }, 0);
      return [lugar];
    },

    conectores() {
      const caixa = h("div", { className: "cfg-conectores" }, "Carregando…");
      const desenhar = async () => {
        const lista = await api("/api/conectores");
        caixa.innerHTML = "";
        for (const c of lista) caixa.append(cartaoConector(c, desenhar));
        caixa.append(formMcp(desenhar));
      };
      desenhar();
      return [h("p", { className: "cfg-texto" }, "Apps conectados viram ferramentas do Jarvis. Ele só carrega as de um app quando o pedido precisa dele (\"cria um post no Canva…\"). O que envia, publica, apaga ou gasta pede o seu “sim”."), caixa];
    },

    instalacao() {
      const lista = h("ul", { className: "cfg-itens saude" }, h("li", {}, "Verificando…"));
      const verificar = async () => {
        lista.innerHTML = ""; lista.append(h("li", {}, "Verificando…"));
        const r = await api("/api/saude");
        lista.innerHTML = "";
        for (const i of r.itens) lista.append(h("li", { className: i.ok ? "ok" : "falta" },
          h("div", {}, h("strong", {}, (i.ok ? "✓ " : "✗ ") + i.nome), h("small", {}, i.detalhe + (i.ok || !i.como ? "" : " — " + i.como)))));
        lista.append(h("li", {}, h("div", {}, h("strong", {}, "Esta máquina"), h("small", {}, `${r.maquina.sistema} · ${r.maquina.nucleos} núcleos · ${r.maquina.ram_gb} GB RAM`))));
      };
      verificar();
      const de_novo = h("button", { textContent: "Verificar instalação" }); de_novo.onclick = verificar;
      const idx = dados.indice;
      const reindexar = h("button", { className: "secundario", textContent: "Atualizar índice agora" });
      reindexar.onclick = async () => { await api("/api/indice/atualizar", "POST"); aviso("Indexando em segundo plano."); };
      const assistente = h("button", { className: "secundario", textContent: "Abrir assistente de instalação" });
      assistente.onclick = () => { fechar(); window.assistenteDeInstalacao && window.assistenteDeInstalacao(true); };
      const resAtt = h("p", { className: "cfg-texto" });
      const verAtt = h("button", { textContent: "Verificar atualizações" });
      const fazerAtt = h("button", { textContent: "Atualizar agora", hidden: true });
      verAtt.onclick = async () => {
        resAtt.textContent = "Conferindo no GitHub…";
        const r = await api("/api/atualizacao");
        resAtt.textContent = r.texto + (r.novidades?.length ? " · " + r.novidades.slice(0, 5).join(" · ") : "");
        fazerAtt.hidden = !r.novas;
      };
      fazerAtt.onclick = async () => {
        fazerAtt.disabled = true; resAtt.textContent = "Baixando a atualização…";
        const r = await api("/api/atualizacao", "POST");
        resAtt.textContent = r.texto;
        if (!r.ok) { fazerAtt.disabled = false; return; }
        const voz = new Audio("/api/voz?texto=" + encodeURIComponent("Chefe, tudo pronto, subindo atualização!"));
        voz.onended = voz.onerror = () => api("/api/reiniciar", "POST", { atraso: 0 });
        voz.play().catch(() => api("/api/reiniciar", "POST", { atraso: 0 }));
      };
      const reiniciar = h("button", { className: "secundario", textContent: "Reiniciar o Jarvis" });
      reiniciar.onclick = () => api("/api/reiniciar", "POST", { atraso: 1 });
      return [secao("Saúde do Jarvis", h("div", { className: "botoes" }, de_novo, assistente), lista),
              secao("Atualizações (GitHub)", h("p", { className: "cfg-texto", textContent: "Atualizar não apaga nada seu: memória, chaves e configurações ficam fora do código." }),
                    h("div", { className: "botoes" }, verAtt, fazerAtt, reiniciar), resAtt),
              secao("Índice dos seus arquivos", h("p", { className: "cfg-texto" },
                `${idx.arquivos} arquivos indexados (${idx.pastas.join(" · ")}). Atualiza sozinho a cada 30 min.`), h("div", { className: "botoes" }, reindexar))];
    },
  };

  function cartaoConector(c, recarregar) {
    const corpoC = h("div", { className: "con-corpo", hidden: true });
    const cabeca = h("div", { className: "con-cabeca" },
      h("strong", {}, c.titulo), h("span", { className: "con-status " + c.status.replace(/\s/g, "-") }, c.status),
      c.ferramentas ? h("small", {}, `${c.ferramentas} ferramentas`) : null);
    cabeca.onclick = () => (corpoC.hidden = !corpoC.hidden);
    const card = h("article", { className: "conector" }, cabeca, corpoC);
    if (c.custo) corpoC.append(h("p", { className: "cfg-texto" }, "💲 " + c.custo));
    if (c.como) corpoC.append(h("p", { className: "cfg-texto" }, "Como conectar: " + c.como));
    if (c.tipo === "embutido") return card;
    const campos = {};
    const add = (nome, rotulo, props = {}) => { campos[nome] = h("input", { autocomplete: "off", ...props }); corpoC.append(campo(rotulo, campos[nome])); };
    if (c.nome === "github" || c.nome === "telegram") add("token", c.nome === "github" ? "Token do GitHub" : "Token do bot", { type: "password", placeholder: "fica no cofre" });
    if (c.precisa_cliente) { add("client_id", "Client ID"); add("client_secret", "Client Secret", { type: "password", placeholder: "fica no cofre" }); }
    if (c.personalizado && c.tipo === "http" && !c.oauth) add("token", "Chave (Bearer)", { type: "password", placeholder: "opcional; fica no cofre" });
    const perm = seletor([["leitura", "Só leitura"], ["escrita", "Leitura e escrita (com o seu sim)"]], c.permissao, () => {});
    corpoC.append(campo("Permissão", perm));
    const ligado = h("input", { type: "checkbox", checked: c.ligado });
    corpoC.append(campo("Ligado", ligado));
    const salvar = h("button", { textContent: "Salvar" });
    const testar = h("button", { className: "secundario", textContent: c.oauth || c.nome === "google" ? "Conectar / Testar" : "Testar" });
    const remover = h("button", { className: "secundario", textContent: c.personalizado ? "Remover" : "Desconectar" });
    const resultado = h("p", { className: "cfg-texto" });
    salvar.onclick = async () => {
      const d = { nome: c.nome, permissao: perm.value, ligado: ligado.checked, tipo: c.tipo, url: c.url, oauth: c.oauth };
      for (const [k, el] of Object.entries(campos)) if (el.value.trim()) d[k] = el.value.trim();
      await api("/api/conectores", "POST", d); aviso("Conector salvo."); recarregar();
    };
    if (c.oauth && !c.precisa_cliente) {  // um clique, igual no Claude: liga, abre o login e pronto
      testar.textContent = c.status === "conectado" ? "Testar" : "Conectar";
      if (c.status !== "conectado") testar.className = "";
    }
    testar.onclick = async () => {
      if (c.oauth && !c.ligado) {
        await api("/api/conectores", "POST", { nome: c.nome, permissao: perm.value, ligado: true, tipo: c.tipo, url: c.url, oauth: true });
        ligado.checked = true;
      }
      resultado.textContent = c.oauth ? "Abrindo o login no navegador… autorize lá e volte aqui (eu espero até 5 min)." : "Testando…";
      const r = await api(`/api/conectores/${c.nome}/testar`, "POST").catch((e) => ({ texto: e.message }));
      resultado.textContent = r.texto; if (r.ok) recarregar();
    };
    remover.onclick = async () => { await fetch(`/api/conectores/${c.nome}`, { method: "DELETE" }); recarregar(); };
    corpoC.append(h("div", { className: "botoes" }, salvar, testar, remover), resultado);
    return card;
  }

  function formMcp(recarregar) {
    const nome = h("input", { placeholder: "ex.: arquivos" });
    const tipo = seletor([["stdio", "Programa local (stdio)"], ["http", "Servidor remoto (HTTP)"]], "stdio", (v) => (form.dataset.tipo = v));
    const comando = h("input", { placeholder: "npx" }), args = h("input", { placeholder: "-y @modelcontextprotocol/server-filesystem C:\\pasta\\que\\ele\\pode\\ver" });
    const env = h("textarea", { rows: 2, placeholder: "VARIAVEL=valor (uma por linha; fica no cofre)" });
    const url = h("input", { placeholder: "https://…/mcp" }), oauth = h("input", { type: "checkbox" }), token = h("input", { type: "password", placeholder: "Bearer (opcional)" });
    const salvar = h("button", { textContent: "Adicionar servidor MCP" });
    const form = h("section", { className: "cfg-secao mcp" }, h("h3", {}, "Adicionar servidor MCP"),
      campo("Nome", nome), campo("Tipo", tipo),
      h("div", { className: "so-stdio" }, campo("Comando", comando), campo("Argumentos", args), campo("Variáveis secretas", env)),
      h("div", { className: "so-http" }, campo("URL", url), campo("Login OAuth no navegador", oauth), campo("Chave", token)),
      h("div", { className: "botoes" }, salvar));
    form.dataset.tipo = "stdio";
    salvar.onclick = async () => {
      try {
        await api("/api/conectores", "POST", { nome: nome.value, titulo: nome.value, tipo: tipo.value, comando: comando.value.trim(), args: args.value,
          env: env.value, url: url.value.trim(), oauth: oauth.checked, token: token.value, ligado: true, permissao: "leitura" });
        aviso("Adicionado. Clique em Testar no cartão dele."); recarregar();
      } catch (e) { aviso("Falhou: " + e.message, true); }
    };
    return form;
  }

  // ------------------------------------------------------------ abrir, fechar, trocar de aba
  function devolverAutomacoes() {
    const auto = $("automacoes");
    if (auto.classList.contains("embutido")) {
      auto.classList.remove("embutido"); auto.hidden = true;
      document.querySelector("main").append(auto);  // volta pro lugar original (o ⚙ segue funcionando)
    }
  }
  async function mostrar(aba) {
    devolverAutomacoes();
    abaAtual = aba;
    for (const b of abas.children) b.setAttribute("aria-selected", String(b.dataset.aba === aba));
    corpo.innerHTML = "";
    try { corpo.append(...telas[aba]()); } catch (e) { corpo.append(h("p", { className: "erro" }, "Erro: " + e.message)); }
  }
  for (const [id, nome] of ABAS) {
    const b = h("button", { textContent: nome, role: "tab" });
    b.dataset.aba = id;
    b.onclick = () => mostrar(id);
    abas.append(b);
  }
  async function abrir() {
    painel.hidden = false;
    botao.setAttribute("aria-expanded", "true");
    try { dados = await api("/api/config"); } catch (e) { corpo.textContent = "Servidor fora do ar."; return; }
    mostrar(abaAtual);
  }
  function fechar() {
    devolverAutomacoes();
    painel.hidden = true;
    botao.setAttribute("aria-expanded", "false");
  }
  botao.onclick = () => (painel.hidden ? abrir() : fechar());
  $("fechar-configuracoes").onclick = fechar;
  addEventListener("keydown", (e) => { if (e.key === "Escape" && !painel.hidden) fechar(); });
  window.abrirConfiguracoes = abrir;
  fetch("/api/config").then((r) => r.json()).then((d) => {
    document.body.classList.toggle("leve", !!d.config.animacoes_leves);
    if (d.config.volume != null) window.volumeDaVoz = d.config.volume / 100;
  }).catch(() => {});
})();
