# F2-41 — Rodada 1: medir a divergência do complemento, sem trocar o que é cobrado

Origem: teste do Marcelo em 08/09 (`Testes/2026-09-08 Teste_Revisão_PE.docx`). A tela
"Comparação de Valores" (Revisão de PE) e o modal "Complemento de Projeto — comparativo"
mostram valores diferentes para o MESMO ambiente. O valor CONTRATADO bate à casa decimal nos
dois; só o à vista do PE/complemento diverge.

| Ambiente | À vista PE (tela) | À vista compl. (modal) | Divergência |
|---|---|---|---|
| AQuarto 2 – Closet | 16.964,90 | 17.016,97 | **+52,07** |
| ASuite 03 – Liberado | 20.587,93 | 20.582,27 | **−5,66** |

## O que está medido

**São duas fórmulas.**

- Tela (`main.py:2666-2677`): roda o motor DUAS VEZES — `_negociacao_breakdown(orc, db)` e
  `_negociacao_breakdown(orc, db, vbva_override=vbva_pe)` — e lê o `VAVA` de cada ambiente da
  segunda passada.
- Modal (`mod_conciliacao_pe.valor_complemento_por_fator:118`, via `_complemento_diferencas`):
  `valor_venda_PE × (VAVA_contratado ÷ VBVA_contratado)`.

**Hipótese do mecanismo (NÃO provada — é o que esta rodada vai medir).** O à vista de um
ambiente é `k × VBVA + F`, com `F` = a parcela de custos adicionais daquele ambiente, que é um
VALOR FIXO. A proporção multiplica o `F` junto com a mercadoria; o motor não. Previsão: onde o
valor sobe a proporção infla, onde cai ela encolhe demais. Os dois casos medidos batem com a
previsão, e o `F` implícito sai ≈ 359 e ≈ 356 — praticamente o mesmo número em dois ambientes de
tamanhos e sinais diferentes. **Dois pontos não são prova.**

**Um buraco de observação.** A Comparação de Valores não consegue mostrar se substituir o VBVA
de um ambiente move o à vista de OUTRO: o dicionário comparado é montado só para os ambientes
com PE carregado (`main.py:2674`, `for i in vbva_pe`). Suite Master e Cozinha aparecem com 0,00
por construção, não por medição. A favor de não haver vazamento: no teste do Marcelo o total
veio por caminho independente (`VAVO` das duas passadas) e deu +1.818,30 = exatamente
2.151,33 − 333,03. É um caso só.

## Por que esta rodada não troca a fonte

A troca certa é fazer os consumidores lerem o motor em vez da proporção. Mas
`valor_complemento_por_fator` alimenta **três** consumidores — `_complemento_diferencas`,
`_complemento_diferencas_fase` e `diferenca_valor_contrato_estimada` (decisão da AF2) — e o
docstring de `mod_conciliacao_pe` registra que os três foram unificados em 15/08 exatamente
porque a AF2 mostrava um número e o complemento cobrava outro. Trocar um só recria aquele
achado ao contrário; trocar os três de uma vez, com a hipótese apoiada em dois pontos, arrisca
o único erro desta linha que não se desfaz com um commit: cobrar valor errado de um cliente.

Então: rodada 1 mede, rodada 2 troca.

## O que fazer

### 1. Sombra: calcular as duas, cobrar pela atual

Em `_complemento_diferencas` e `_complemento_diferencas_fase`, além do `va_compl` que já existe,
calcular o valor do MOTOR para os mesmos ambientes e devolvê-lo ao lado.

- **Uma chamada só de motor por invocação**, com todas as substituições de uma vez:
  `_negociacao_breakdown(orc_ct, db, vbva_override={pool_ambiente_id: valor_venda_pe, ...})`.
  **Não** chamar dentro do laço de ambientes. (Já temos um caso aberto de leitura de razão dentro
  de laço em `_negociacao_breakdown`; não criar outro.)
- Cada linha ganha `vava_motor` e `divergencia = round(vava_motor − vava_complemento, 2)`.
- `resumo` ganha `divergencia_total` e `divergencia_maxima_abs`.
- **O que é cobrado não muda**: `diferenca` continua vindo de `va_compl`. Nenhum valor, nenhum
  aditivo, nenhum lançamento muda de número nesta rodada.
- Se o motor falhar por qualquer motivo, `vava_motor = None` e a linha segue normalmente — a
  sombra nunca pode derrubar o caminho que cobra.

### 2. Registro da divergência

- Uma linha de log estruturada e "grepável" por invocação, com projeto, ambiente, os dois
  valores e a divergência. Prefixo fixo (ex.: `[F2-41-SOMBRA]`) para dar `grep` depois.
- Na tela: uma linha discreta no rodapé do modal com a divergência total — **marcada com o selo
  do item 4**, portanto invisível para o cliente por padrão.

### 3. Testes de propriedade (escrever agora, rodar contra o comportamento ATUAL)

1. **XML idêntico ⇒ diferença zero** — nas duas fórmulas.
2. **Sem vazamento**: substituir o VBVA de UM ambiente não altera o `VAVA` de nenhum outro na
   saída do motor. É o teste que a tela hoje não consegue fazer.
3. **Soma fecha**: a soma das diferenças por ambiente = a diferença do total (`VAVO` das duas
   passadas).
4. **Não cobra duas vezes**: complemento gerado depois de um aditivo assinado, sem mudança de
   XML, dá zero.

**Se o teste 2 falhar, PARE e relate.** Não "conserte" o motor para o teste passar — uma falha
ali muda a decisão da rodada 2 e é exatamente o que esta rodada existe para descobrir.

### 4. Selo dos textos de apoio + retirada do cabeçalho do modal

O parágrafo em `static/index.html:22400-22405` expõe o desconto global ("global +30,00%") e a
carga de custos adicionais na tela que o gerente abre na frente do cliente. Sai da vista.

Mecanismo (decisão do Marcelo, 08/09): **marcar, não apagar** — o texto continua disponível para
nós em Homologação e some para o cliente, com um interruptor único.

- Classe `apoio-dev` no elemento.
- Interruptor único no `<body>`: `data-apoio="on" | "off"`, **default `off`**.
- Uma regra de CSS: `body:not([data-apoio="on"]) .apoio-dev { display: none !important; }`.
- Aplicar nesta rodada **apenas** aos textos que este pacote já toca (o cabeçalho do modal e a
  linha de divergência do item 2). A varredura do resto do sistema é pacote próprio — são muitos
  arquivos e não entra junto com uma mudança de cálculo.
- Um teste: com `data-apoio` ausente ou `off`, nenhum elemento `.apoio-dev` fica visível.

## Aceite

1. Modal e tela continuam mostrando EXATAMENTE os mesmos valores cobrados de hoje — a sombra não
   muda número nenhum. Prova: um teste que fixa `diferenca` antes e depois da mudança.
2. `vava_motor` e `divergencia` presentes em cada linha; `divergencia_total` no resumo.
3. Uma única chamada de `_negociacao_breakdown` por invocação de `_complemento_diferencas[_fase]`
   — provado por contagem de chamadas no teste, não por leitura.
4. Os quatro testes de propriedade escritos e rodando. Se algum falhar, relatar sem consertar.
5. Cabeçalho do modal fora da vista do cliente com `data-apoio` no default; visível com
   `data-apoio="on"`.
6. Camadas b + c verdes.

## NÃO AUTORIZA

- Trocar a fonte do valor cobrado. Esta rodada NÃO troca.
- Tocar o motor (`mod_negociacao.calcular_orcamento`) ou a fórmula de
  `valor_complemento_por_fator`.
- Alterar `diferenca`, o Termo Aditivo, ou qualquer lançamento contábil.
- Varrer o sistema inteiro atrás de textos de apoio nesta rodada.
- Tocar Produção.
