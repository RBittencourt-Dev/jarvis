---
nome: paineis-ao-vivo
descricao: Montar popup AO VIVO bonito que monitora um site e atualiza os números sozinho
quando: ao vivo|tempo real|monitor|acompanh|atualizando|placar|apuracao|eleic|cotacao ao vivo
---
Quando ele pedir pra monitorar algo e mostrar ao vivo (eleição, placar, cotação, status de um site):
1) Ache a FONTE: prefira uma API que devolve JSON (buscar_na_web "API JSON <assunto>", ex.: TSE = resultados.tse.jus.br/oficial/.../dados-simplificados/br/br-c0001-e000544-r.json). Confira o formato com rodar_codigo (python: httpx.get(url).json()) e ache o caminho de cada número (ex.: cand[0].pvap). Sem API: use a página e campos por descrição (atualiza mais devagar).
2) Faça BONITO: html com as classes prontas. Ex. de disputa: <div class="vivo-grade"><div class="vivo-item"><img class="vivo-foto" src="FOTO"><div class="vivo-nome">Nome</div><div class="vivo-num"><span data-campo="a_pct"></span>%</div><div class="vivo-barra"><i data-largura="a_pct"></i></div></div> ...o outro... </div> e embaixo <div class="vivo-rotulo">Apurado: <span data-campo="apurado"></span>%</div>. Fotos: ache a URL da foto (buscar_na_web/pesquisar fotos, Wikipedia/Wikimedia) e use https direto no src.
3) Chame criar_painel_ao_vivo e CONFIRA os valores que voltam; se vier vazio ou errado, corrija os caminhos e chame de novo.
4) Fale curto: "Tá na tela, atualizando a cada 30 segundos." Pra parar: parar_painel_ao_vivo.
