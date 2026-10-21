// Botão ⚙: lista, cria, edita, liga/desliga, testa e apaga as automações (automacoes.json no servidor).
(() => {
  const painel = $("automacoes"), form = $("form-auto"), lista = $("lista-auto"), botao = $("abrir-automacoes");
  const DIAS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];
  let todas = [];

  const quando = (a) =>
    a.tipo === "frase" ? `Quando eu disser “${a.frase}”`
    : a.tipo === "ao_ligar" ? "Quando o PC ligar"
    : `${a.hora} · ${a.dias.length === 7 ? "todo dia" : a.dias.map((d) => DIAS[d]).join(", ")}`;

  async function carregar() {
    try { ({ automacoes: todas } = await (await fetch("/api/automacoes")).json()); } catch { todas = []; }
    lista.innerHTML = "";
    if (!todas.length) {
      const li = document.createElement("li");
      li.className = "vazio";
      li.textContent = "Nenhuma ainda. Monte a primeira aqui embaixo.";
      lista.append(li);
    }
    for (const a of todas) {
      const li = document.createElement("li");
      li.className = a.ativa ? "" : "desligada";
      const info = document.createElement("div");
      info.className = "info";
      info.title = "Editar";
      info.innerHTML = "<strong></strong><small></small>";
      info.querySelector("strong").textContent = a.nome;
      info.querySelector("small").textContent = `${quando(a)} → ${a.acoes.join(" · ")}`;
      info.onclick = () => editar(a);
      const testar = Object.assign(document.createElement("button"), { textContent: "Testar", title: "Rodar agora" });
      testar.onclick = () => { fechar(); chamar(`/api/automacoes/${a.id}/rodar` + (sessao ? `?sessao=${sessao}` : ""), {}); };
      const liga = Object.assign(document.createElement("button"), { className: "secundario", textContent: a.ativa ? "Pausar" : "Ativar" });
      liga.onclick = () => salvar({ ...a, ativa: !a.ativa });
      const apaga = Object.assign(document.createElement("button"), { className: "secundario", textContent: "Apagar" });
      apaga.onclick = async () => { await fetch(`/api/automacoes/${a.id}`, { method: "DELETE" }); carregar(); };
      li.append(info, testar, liga, apaga);
      lista.append(li);
    }
  }

  function limparForm() {
    form.reset();
    form.elements.id.value = "";
    form.dataset.tipo = form.tipo.value;
    $("erro-auto").hidden = true;
  }

  function editar(a) {
    limparForm();
    form.elements.id.value = a.id;
    form.nome.value = a.nome;
    form.tipo.value = a.tipo;
    form.frase.value = a.frase || "";
    form.hora.value = a.hora || "";
    form.querySelectorAll('[name="dia"]').forEach((c) => (c.checked = a.dias.includes(+c.value)));
    form.acoes.value = a.acoes.join("\n");
    form.dataset.tipo = a.tipo;
    form.nome.focus();
  }

  async function salvar(a) {
    const r = await fetch("/api/automacoes", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(a) });
    if (!r.ok) {
      $("erro-auto").textContent = (await r.json()).detail || "Não consegui salvar.";
      $("erro-auto").hidden = false;
      return false;
    }
    await carregar();
    return true;
  }

  form.tipo.onchange = () => (form.dataset.tipo = form.tipo.value);
  form.onsubmit = async (e) => {
    e.preventDefault();
    const atual = todas.find((a) => a.id === form.elements.id.value);
    const ok = await salvar({
      id: form.elements.id.value || undefined,
      nome: form.nome.value,
      tipo: form.tipo.value,
      frase: form.frase.value,
      hora: form.hora.value,
      dias: [...form.querySelectorAll('[name="dia"]:checked')].map((c) => +c.value),
      acoes: form.acoes.value.split("\n"),
      ativa: atual ? atual.ativa : true,
    });
    if (ok) limparForm();
  };
  $("nova-auto").onclick = limparForm;

  function fechar() {
    painel.hidden = true;
    botao.setAttribute("aria-expanded", "false");
  }
  botao.onclick = () => {
    if (!painel.hidden) return fechar();
    painel.hidden = false;
    botao.setAttribute("aria-expanded", "true");
    limparForm();
    carregar();
  };
  $("fechar-automacoes").onclick = fechar;
  addEventListener("keydown", (e) => { if (e.key === "Escape" && !painel.hidden) fechar(); });
})();
