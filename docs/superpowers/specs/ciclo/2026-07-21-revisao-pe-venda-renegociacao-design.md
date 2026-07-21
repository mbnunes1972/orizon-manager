# Revisão de PE por VALORES DE VENDA + renegociação de ambientes (2026-07-21)

## Demanda (decisão de processo do usuário)
A Revisão de PE (11c) deve tratar de **valores de venda**; a comparação de **custo de fábrica** (CFO)
pertence à **Aprovação Financeira II** (11d), que ganha o botão "Comparar Valores" (sem "carregar" —
os PEs já subiram na 11c). Na 11c, cada ambiente ganha um checkbox **"Renegociar"**; os marcados
aparecem na **Aprovação do PE pelo Cliente** (11e) com um botão **"Negociar Ajuste"** que abre a tela
de negociação original, porém só com esses ambientes.

## Decisões (AskUser, 2026-07-21)
1. **Efeito do ajuste:** gerencial por ora (SEM lançamento contábil imediato; acerto na liquidação/
   NF-e), **mas com Termo Aditivo contratual**: modelo próprio no painel de documentos
   (`documento_modelos`, tipo novo), assinatura **loja + cliente**, cobrindo **apenas a diferença**
   dos ambientes renegociados.
2. **Base da renegociação:** valores do **PE** (a realidade nova) — renegociação ocorre nos ambientes
   marcados (tipicamente com valores maiores).
3. **Assinatura:** via termo aditivo nos moldes do contrato (item 1); sem novo fluxo além disso.

## Viabilidade técnica (verificada)
- O XML de PE usa o MESMO parser do pool (`promob_grupos.ler_xml_str`); dele o pool extrai `total`
  (venda → `budget_total` = VBVA) e Σ `order_total` (CFO). O PE já continha a venda; a Fatia 1 do
  desmembramento só extraía o custo (decisão #4 de 2026-07-13 — superada aqui para a 11c).
- O motor é puro: `_negociacao_breakdown(orc, db, vbva_override={pool_ambiente_id: VBVA_pe})` roda o
  MESMO motor com os MESMOS parâmetros/descontos salvos, trocando só o bruto dos ambientes com PE →
  `ambientes[].VAVA` = venda à vista por ambiente. **Motor inalterado.**
- Contexto de rateio (viagem/brinde): as duas rodadas usam o pool ORIGINAL como denominador —
  só o VBVA do ambiente varia; comparação maçã-com-maçã.

## Fatia 1 — 11c compara VENDA (implementada)
- `mod_pe_comparacao.extrair_venda_pe` (o `total`) + `montar_comparacao_venda` (puras, testadas).
- Colunas novas: `arquivo_pe.valor_venda` e `pool_ambientes.renegociar_pe`
  (`_migrar_colunas`/`_migrar_colunas_pg`). **Backfill lazy**: PE carregado antes da coluna →
  o GET `/pe/comparacao` re-parseia o arquivo salvo e persiste.
- GET `/pe/comparacao` → `comparacao_venda` (VAVA original × PE, Δ, Δ%, `pe_carregado`,
  `renegociar`, `pool_ambiente_id`) + `venda_totais` (VAVO/Val_Cont das duas rodadas). O payload de
  CFO (`comparacao`) permanece — a AF2 o consome.
- POST `/pe/renegociar` `{pool_ambiente_id, renegociar}` — flag por ambiente (escopo de loja).
- UI 11c: tabela À vista (contrato) × À vista (PE) × Δ × Δ% × **Renegociar** × Carregar (por
  ambiente). Venda maior = verde. KPIs: à vista contrato/PE, Δ venda, Δ%.
- E2E HTTP: `tests/test_pe_comparacao_venda_e2e.py`.

## Fatia 2 — AF2 "Comparar Valores" (implementada)
A 11d já tinha um espelho da comparação; virou a casa DEFINITIVA do CFO: botão "Comparar Valores",
tabela read-only sem coluna Carregar, container próprio (`pe-cmp-container-af` — antes colidia com o
id da 11c). Cores: custo maior = vermelho.

## Notas do QA (Vera, 2026-07-21)
- **Gate da 11c (achado alto, corrigido):** o universo da conclusão é o **orçamento do contrato**
  (o que a tabela exibe), não o pool inteiro — ambiente removido do orçamento antes da assinatura
  não trava a subfase (regressão em `test_conclusao_11c_ignora_ambiente_fora_do_orcamento`).
  Sem contrato (legado), cai no pool inteiro como antes.
- **Limitação documentada:** em `venda_totais`, `val_cont_pe` usa o `total_cliente` do plano de
  pagamento ORIGINAL (fixo) — se o VAVO do PE ultrapassá-lo, o `cust_fin` da rodada PE colapsa e os
  `val_cont_*` deixam de ser comparáveis. A UI só usa `vavo_*`; a **Fatia 3 NÃO deve construir sobre
  `val_cont_pe`** sem recalcular o plano de pagamento do ajuste.
- **Backfill lazy:** o GET re-parseia XML salvo sem `valor_venda` e persiste (commit no GET); parse
  que falha é silencioso e re-tentado a cada GET (sem cache negativo) — aceito por simplicidade.

## Fatia 3 — 11e "Negociar Ajuste" + Termo Aditivo (PRÓXIMA — não implementada)
- Card 11e lista os ambientes `renegociar_pe=1` e o botão **Negociar Ajuste**.
- **Orçamento de ajuste**: novo `Orcamento` (flag própria, ex.: `is_ajuste`/`ajuste_de_id`) contendo
  SÓ os ambientes marcados, com VBVA inicial = `arquivo_pe.valor_venda` (base = PE). Tela de
  negociação normal (motor/preview/parâmetros do projeto). **Atenção:** a trava `_contrato_assinado`
  bloqueia hoje QUALQUER orçamento de projeto assinado — a Fatia 3 precisa de isenção deliberada e
  gated (etapa 11e ativa + permissão) só para o orçamento de ajuste.
- **Termo Aditivo**: tipo novo em `documento_modelos` (modelo versionado por loja, imutável, como o
  contrato), marcadores próprios (ambientes renegociados, valor original × novo, diferença), PDF via
  WeasyPrint (`mod_contrato` pattern), assinatura loja + cliente. SEM lançamentos contábeis.
- Congelar `modelo_versao_id` no aditivo gerado (mesmo padrão do contrato).
