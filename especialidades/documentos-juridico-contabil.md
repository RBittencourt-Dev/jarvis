# Documentos da 7 SevenCode — contrato e proposta de software (jurídico + contábil)

Esta é a cabeça do Jarvis pra **montar e revisar documentos de software** da 7 SevenCode: proposta comercial e
contrato de prestação de serviço / licença de uso. Não é parecer jurídico nem contábil; pra caso sério, procurar
advogado/contador. Mas pro dia a dia da empresa, serve pra deixar o documento pronto, correto e sem furo.

A lei que rege: **Código Civil** (prestação de serviço, arts. 593+), **CDC** quando o cliente é consumidor final,
**LGPD** (Lei 13.709/2018) sempre que o sistema trata dado pessoal (o Porthon trata — moradores), e **Lei do Software**
(Lei 9.609/98) pra licença e propriedade do código.

## Realidade da 7 SevenCode (usar isto, não inventar)
- Fundada por **Rafael Bittencourt** (CEO, dev fullstack); sócio **Jesus** (dev fullstack). Software house sob medida.
- **Hoje recebe como Pessoa Física** (Pix e transferência). Plano: **Asaas como PF** (boleto + Pix recorrente) e depois
  abrir uma **ME no Simples Nacional**. O gatilho pra abrir CNPJ é: cliente exigir **nota fiscal**, entrar uma
  administradora, ou o faturamento passar de ~R$ 1.500–2.000/mês.
- **Enquanto é PF, NÃO emite nota fiscal.** Então o documento NÃO deve prometer nota. Se o cliente exige nota, é o
  sinal de abrir o CNPJ — avisar isso, não fingir que emite.
- Porthon: SaaS de portaria/condomínio, planos **a partir de R$ 149,90 / 199,97 / 299,99 por mês**. A landing mostra só
  o "a partir de"; o valor fechado sai na conversa de orçamento pelo WhatsApp.
- Site 7sevencode.com.br; identidade visual: fundo escuro `#17191f`, azul `#0479da`, fonte Space Grotesk.

## PROPOSTA comercial de software — o que PRECISA ter
1. **Cabeçalho**: 7 SevenCode, contato (WhatsApp/e-mail), data e validade da proposta (ex.: "válida por 15 dias").
2. **Para quem** (cliente) e **o problema** que ele tem, em uma linha — mostra que entendeu a dor.
3. **Escopo**: o que será entregue, item a item, claro. E, separado, o que **NÃO** está incluído (evita briga depois).
4. **Prazo** estimado (em semanas/etapas), deixando claro que conta a partir do aceite e do envio do material do cliente.
5. **Investimento**: valor, forma (setup único, ou mensalidade de SaaS), forma de pagamento (Pix/transferência hoje;
   boleto/Pix recorrente via Asaas). Se for SaaS, dizer o que a mensalidade cobre (hospedagem, suporte, atualizações).
6. **Condições**: o que o cliente precisa fornecer (conteúdo, acessos, logo), e o que acontece se atrasar.
7. **Próximo passo** / validade / como aceitar (responder, assinar).

## PROPOSTA — o que NÃO pode
- **Não prometer resultado que não controla**: "primeiro lugar no Google", "vai triplicar vendas", "100% livre de
  bug". Pode falar de SEO, estabilidade, boas práticas — nunca garantir número.
- Não inventar prazo curto demais pra ganhar o cliente e depois não cumprir.
- Não prometer nota fiscal enquanto PF. Não citar CNPJ que não existe.
- Não deixar o escopo vago ("fazemos tudo que precisar") — isso vira trabalho infinito de graça.

## CONTRATO de software — o que PRECISA ter (cláusulas)
1. **Partes**: CONTRATADA (7 SevenCode — enquanto PF, Rafael Bittencourt, CPF) e CONTRATANTE (nome/CPF ou CNPJ, endereço).
2. **Objeto**: o que é — desenvolvimento sob medida e/ou **licença de uso** do sistema (SaaS). Diferenciar desenvolver
   (feito uma vez) de licenciar/hospedar (contínuo, mensal).
3. **Escopo e entregáveis** + o que está fora. Pode remeter ao escopo da proposta anexa.
4. **Prazo e etapas**; vigência (se SaaS, prazo + renovação automática).
5. **Preço e pagamento**: valor, vencimento, forma, reajuste anual (ex.: IGP-M/IPCA), multa e juros de atraso
   (padrão: multa 2% + juros 1% a.m., CDC/Código Civil), e o que acontece na inadimplência (suspender o serviço após
   aviso).
6. **Propriedade intelectual** (Lei 9.609/98): deixar claro de quem é o código. Em SaaS, o código é **da 7 SevenCode** e
   o cliente tem **licença de uso** enquanto paga — não compra o código. Em projeto sob medida, combinar: cedido ou
   licenciado. Nunca entregar o código-fonte por acidente de redação.
7. **LGPD** (obrigatória quando trata dado pessoal): papéis (cliente = **controlador**, 7 SevenCode = **operador**),
   finalidade, segurança, que a 7 SevenCode só trata o dado pra prestar o serviço, sigilo, e devolução/eliminação ao
   fim. O Porthon trata dado de morador → esta cláusula é obrigatória nos contratos do Porthon.
8. **Confidencialidade** (mútua).
9. **Garantia e manutenção**: correção de defeito (bug) por X dias sem custo; o que é bug (corrige de graça) x o que é
   **nova funcionalidade** (orça à parte). Suporte: canal e horário.
10. **Limitação de responsabilidade**: a 7 SevenCode não responde por lucro cessante nem por mau uso/dado errado posto
    pelo cliente; responsabilidade limitada ao valor pago. (Com consumidor, o CDC limita o quanto dá pra excluir —
    não dá pra eximir de tudo.)
11. **Rescisão**: como encerra, aviso prévio (ex.: 30 dias), e o que acontece com os dados (exporta e entrega) e com
    valores já pagos.
12. **Foro** e assinatura das duas partes (data; o painel da 7 SevenCode tem assinatura eletrônica).

## CONTRATO — o que NÃO pode / cuidados
- **Cláusula abusiva (CDC, art. 51) é nula**: não dá pra se eximir de TODA responsabilidade, nem obrigar o cliente a
  renunciar direitos, nem reajuste em prazo menor que 12 meses.
- Não cobrar nota/imposto que não emite (PF). Não citar foro de comarca errada.
- Não misturar "venda do software" com "licença de uso" — some com a propriedade do código. Em SaaS é **licença**.
- Não esquecer a LGPD quando há dado pessoal — é o furo mais comum e mais caro.
- Não deixar "serviço ilimitado" ou "suporte 24h" se não vai cumprir.
- Não garantir disponibilidade de 100% (usar algo realista, ex.: "melhor esforço" ou um SLA só se der conta).

## Como o Jarvis monta
- Tom: **profissional, claro e direto**, português do Brasil, sem juridiquês desnecessário mas com as cláusulas certas.
- Sempre preencher com o que sabe da 7 SevenCode; o que faltar (CPF do cliente, valor fechado, prazo), deixar um campo
  visível tipo `[preencher: CPF do cliente]` em vez de inventar.
- Ao final, lembrar em uma linha: documento base, revisar antes de enviar; e que não substitui advogado/contador.
