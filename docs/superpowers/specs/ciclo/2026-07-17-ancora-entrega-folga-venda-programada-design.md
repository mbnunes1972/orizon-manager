# Prazo Contratual, Datas da Assinatura, Folga com Bloqueio e Monitoramento de Atraso — Design

**Data:** 2026-07-17 · **Status:** aprovado no brainstorm (pronto para plano) · **Frente:** A+B (C —
execução por ambiente — fica para spec própria depois).

Consolida o teste manual do card do Contrato + o refinamento do brainstorm: a data de entrega **não
persistia** na tela, a **folga** exibida era incompreensível, faltavam **medição esperada** e **expectativa
de entrega** na assinatura, o **prazo contratual** (dias úteis) não existia como parâmetro/cláusula, e o
**sinal de atraso** precisa ser geral. Reusa `mod_cronograma`, `Projeto` (`projetos_meta`), o padrão de
reautenticação gerencial (`LogAcaoGerencial` + `perfis.pode(nivel,"autorizar")`), o Cronograma do Ciclo
(v11) e os marcadores de contrato (`mod_marcadores.CATALOGO` × `mod_contrato._montar_mapping`).

## Contexto e modelo mental

O ciclo monitora **datas previstas × reais** por etapa e busca cumprir o **prazo contratual**. Duas medidas
de prazo coexistem, com propósitos distintos:

- **Prazo contratual** — a promessa **formal/jurídica**: ~**50 dias úteis** (seg–sex) a partir da
  **assinatura**, baseado nas etapas. O cronograma padrão da loja "busca atendê-lo". É o **único** prazo que
  conta em **dias úteis**.
- **Expectativa de entrega** — uma **data** (calendário/dias corridos) preenchida na assinatura. Ajusta o
  acordo no momento do contrato, entra como **observação no contrato** e é **monitorada internamente**.

Duas alavancas determinam o cumprimento na prática:
- **Medição** (etapas 9/10) — marco de continuidade; a produção realista só faz sentido a partir dela.
- **Aprovação do Projeto Executivo** (etapa 11) — o gargalo real: revisões de PE empurram a entrega.

A **venda programada** existe porque a **obra do cliente** controla *quando* a medição pode ocorrer — mas
deixa de ser um modo com regras próprias: vira uma **classificação** (ver §3). O par previsto × real por
etapa é o insumo que a **assistente IA (futura)** vai ler para notificar/cobrar. **Esta frente NÃO constrói
a IA** — apenas garante que os dados existam, corretos, monitoráveis e visíveis.

## Decisões fixadas no brainstorm

1. **Datas na assinatura — SEMPRE (ambos os casos):** **medição esperada** e **expectativa de entrega** são
   obrigatórias para finalizar a assinatura. Moram no `Projeto` (`projetos_meta`); são previsões editáveis.
   **Venda programada** é um checkbox importante: quando `true`, acrescenta uma **informação ao contrato**
   (marcador condicional, §5).
2. **Semântica do `prazo_dias`:** **duração própria da etapa** em **dias corridos** (não acumulado desde
   D0). `cronogramas()` já acumula corretamente; `gerar_cronograma_projeto` e o `default` estão errados e
   serão corrigidos.
3. **Folga = folga ≥ 0** ("tem que caber"), sem colchão configurável, mas passa a **bloquear de verdade**
   com **override gerencial**. Fórmula única (não depende de modo) — ver §3.
4. **Prazo contratual configurável por loja** (default **50 dias úteis**), a partir da assinatura. Gera uma
   **data-limite contratual** monitorada e alimenta o **marcador** do contrato (§5).
5. **Dias úteis (seg–sex, sem feriados) SÓ no prazo contratual.** Cronograma de etapas, folga e expectativa
   de entrega usam **dias corridos**.
6. **D0 permanece = confirmação das DUAS assinaturas** (loja + cliente). Inalterado.
7. **Sinal de atraso é GERAL:** qualquer etapa aberta cuja previsão já passou ilumina o projeto — não só a
   entrega, não só venda programada (§6).
8. **Contrato:** expectativa de entrega + prazo contratual entram via **marcadores automáticos** no template
   (§5). Agenda Global e IA ficam para frentes próprias.

## Componentes

### 1. Modelo de dados — `Projeto` (`projetos_meta`)

Colunas novas (migração idempotente via `_add_cols`, como `data_entrega`/`data_inicio` em `database.py:1355`):

- `venda_programada` — Boolean, default `False`. Classificação (obra do cliente controla a medição).
- `previsao_medicao` — Date, nullable. **Obrigatória na assinatura** (ambos os casos).

`data_entrega` (= expectativa de entrega) e `data_inicio` já existem (`database.py:471`) — reusados. A
`data_entrega` é sempre obrigatória na assinatura.

### 2. Correção do bug de persistência ("a data se perde")

- **Causa:** o card lê `contrato.data_entrega` (`static/index.html:13602`), campo que **não existe** no
  `Contrato` nem é serializado. A gravação em `Projeto.data_entrega` (`main.py:4721`) funciona; a releitura
  vem vazia → parece que sumiu.
- **Correção:** a serialização do contrato (`GET .../contrato`, `main.py:2369`) passa a incluir, **lidos do
  `Projeto`**: `data_entrega`, `venda_programada`, `previsao_medicao`. O card lê desses campos.

### 3. Cronograma, folga e o Cronograma Padrão

- **`mod_cronograma.gerar_cronograma_projeto`** (`mod_cronograma.py:37`): hoje grava
  `data_prevista_conclusao = D0 + prazo_dias` (trata prazo como offset direto de D0). Passa a **acumular**:
  `data_prevista_conclusao = D0 + Σ(durações das etapas até esta, inclusive)`, em **dias corridos**.
- **`cronogramas()`** (`mod_cronograma.py:90`) já acumula durações — **mantido**; é a referência da semântica.
- **Reescrever o `default` `cronograma_padrao`** em `mod_provisoes.config_financeira_default`
  (`mod_provisoes.py:37`) com **durações realistas por etapa** (os valores atuais 2,5,10,…,70 só fazem
  sentido como acumulado; somariam ~525 dias se lidos como duração). Alvo: o padrão de referência da loja
  reflete o prazo contratual pretendido.
- **Folga operacional — fórmula única (SEMPRE):**
  `folga = (data_entrega − previsao_medicao) − Σ durações (dias corridos) das etapas da medição até a "16"`.
  As etapas **até a medição** são controladas pela obra do cliente (fora do controle da loja) e não entram.
  As etapas **medição → entrega** (PE, produção, entrega) são o que a folga precisa garantir. `folga < 0`
  bloqueia (§4). `cabe_no_cronograma` inalterada (folga ≥ 0).

> A etapa de entrega ao cliente é a **"16"** (`mod_ciclo.ETAPA_NOME["16"] = "Entrega no cliente"`; "17" =
> Montagem). O regressivo já ancora em `codigo_entrega="16"`. O "início da contagem" da folga é a **primeira
> etapa de medição** do Cronograma Padrão (definição operacional: etapa "10" — Medição; se ausente, a "9").

> **Migração de config (durações) — decisão:** lojas que já salvaram `cronograma_padrao` com os valores
> acumulados antigos ficariam com durações absurdas, e o merge com default **não** basta (a chave já existe).
> **Marcador de versão idempotente:** a config ganha `cronograma_formato` (int). Ausente/`1` = formato-legado
> **acumulado**; `2` = **durações**. Na leitura (`_cfg_financeira_loja`), config em `formato 1` é convertida
> para durações por diferença (`dur[i] = acc[i] − acc[i-1]`, `dur[0] = acc[0]`) e reescrita como `formato 2`
> (conversão única, idempotente); config já em `formato 2` é usada como está. O novo default nasce em
> `formato 2`. Cobrir com teste dedicado.

### 4. Bloqueio da data + override gerencial + trava de assinatura

- **`POST /api/projetos/<nome>/data-entrega`** (`main.py:4698`) — persiste as três datas/flag
  (`data_entrega`, `previsao_medicao`, `venda_programada`) e valida a folga:
  - `folga ≥ 0` → grava (`ok:true, cabe:true`).
  - `folga < 0` **sem** reautenticação → **não grava**; retorna `ok:true, cabe:false, folga_min` (só
    diagnóstico). Hoje grava mesmo sem caber — este é o "primeiro problema".
  - `folga < 0` **com** `login`/`senha` de nível `autorizar` (`perfis.pode`) → grava e registra
    `LogAcaoGerencial(acao="data_entrega_sem_folga", projeto_nome, contexto={data_entrega, previsao_medicao, folga})`.
- **Trava da assinatura** (guard em `main.py:6159`, a 2ª assinatura que completa loja+cliente): exige
  `data_entrega` **e** `previsao_medicao` preenchidas (ambos os casos). Faltando qualquer uma → 400, sem
  assinar. **D0/`gerar_cronograma_projeto` inalterados** no disparo (já corrigido em §3).

### 5. Prazo contratual (dias úteis) + marcadores no contrato

- **Parâmetro de config da loja** `prazo_contratual_dias_uteis` (default **50**), merge com default como os
  demais campos de `config_financeira_json`.
- **Cálculo de dias úteis** — novo helper puro (ex.: `mod_cronograma.somar_dias_uteis(data, n)`): avança `n`
  dias contando apenas seg–sex (sem feriados). **Data-limite contratual** = `assinatura + prazo_contratual_dias_uteis`
  (dias úteis). Calculada no D0 e monitorada.
- **Marcadores automáticos** (entram em `mod_marcadores.CATALOGO` **e** `mod_contrato._montar_mapping` no
  mesmo commit — teste anti-drift):
  - `PRAZO_CONTRATUAL` — "N dias úteis a partir da assinatura" (+ a data-limite calculada).
  - `DATA_PREVISTA_ENTREGA` — a expectativa de entrega (observação do acordo).
  - `PREVISAO_MEDICAO` — a medição esperada (quando pertinente ao texto).
  - `VENDA_PROGRAMADA` — informação condicional: quando `venda_programada` é `true`, rende o texto/observação
    da venda programada (obra do cliente controla a medição); quando `false`, rende vazio.
  - Escopo `documento`. O corpo do template pode referenciá-los como cláusula/observação; `_html_corpo`
    continua **escapando** o valor (defesa já existente).
- **Check de coerência padrão × prazo contratual (AVISO, não bloqueio):** na aba **Config → Cronograma**, ao
  editar/salvar o Cronograma Padrão, o sistema compara o **total do padrão** com o **prazo contratual**. Como
  o padrão é em dias corridos e o prazo em dias úteis, compara **datas resultantes** a partir de um D0 de
  referência: `D0 + Σ durações (corridos)` (entrega pelo padrão) × `D0 + prazo_contratual_dias_uteis` (úteis).
  Se o padrão ultrapassa o prazo contratual, exibe **aviso** ("o Cronograma Padrão soma X dias corridos e não
  cabe no prazo contratual de N dias úteis") — orienta a calibrar, **sem** impedir o salvamento.

### 6. Monitoramento de atraso (GERAL) na lista de projetos

- View read-only (sem tabela nova): um projeto está **atrasado** se **qualquer** `CicloEtapa` aberta
  (`concluido_em` nulo, etapa não concluída) tem `data_prevista_conclusao < hoje`, **ou** `hoje > data_entrega`
  com a etapa "16" aberta.
- A lista/painel de projetos (`renderProjResultados`) exibe a **data de entrega** + um **selo de atraso**
  (qualquer etapa vencida ilumina o projeto). Deriva de `CicloEtapa` + `Projeto` — mesma base que a futura
  Agenda Global consumirá.

### 7. UI — card do Contrato (`static/index.html`)

- O bloco "Data de entrega esperada" (`index.html:13598`) lê `contrato.data_entrega` já servido.
- **Campo "Previsão de medição"** (input date) ao lado da entrega — **obrigatório** para validar/assinar.
- **Checkbox "Venda programada"** — classificação (obra do cliente controla a medição); não muda a fórmula
  da folga, apenas sinaliza para acompanhamento/IA futura.
- Retorno da validação: `cabe:false` mostra o aviso e, para Gerente+ (`_podeAutorizarFront`), oferece o
  **registro com autorização** (modal de senha do próprio autorizador, padrão do `modal-crono` v11).

## Fluxo

1. Orçamento aprovado → contrato. No card, informa **medição esperada** e **expectativa de entrega** (marca
   **venda programada** se a obra do cliente ainda controla a medição).
2. Validar: `folga = (entrega − medição) − Σ(medição→16)` (dias corridos). Se < 0, bloqueia (ou grava com
   senha gerencial + log).
3. 2ª assinatura exige as duas datas → **D0** dispara `gerar_cronograma_projeto` (durações acumuladas em
   dias corridos) e fixa a **data-limite contratual** (`assinatura + 50 dias úteis`). O contrato gerado traz
   os marcadores `PRAZO_CONTRATUAL` / `DATA_PREVISTA_ENTREGA`.
4. Execução: cada etapa concluída grava `concluido_em`; o sinal de atraso ilumina o projeto se qualquer
   previsão vencer. Base do previsto × real que a IA cobrará.

## Faseamento (4 fatias incrementais, cada uma testável/mergeável)

- **Fatia 1 — Correções (destrava o uso):** bug de persistência (§2) + correção de folga/`gerar_cronograma`
  e default (§3), incluindo a normalização `cronograma_formato`.
- **Fatia 2 — Datas + enforcement:** medição esperada obrigatória (§1), bloqueio folga<0 com override
  gerencial (§4) + trava de assinatura pelas duas datas.
- **Fatia 3 — Prazo contratual + contrato:** parâmetro por loja, `somar_dias_uteis`, data-limite e
  marcadores no template (§5).
- **Fatia 4 — Monitoramento:** sinal de atraso geral na lista de projetos (§6) + UI final do card (§7).

## Testes (TDD no núcleo)

- **`mod_cronograma`:** folga (fórmula única medição→entrega, dias corridos), `gerar_cronograma_projeto`
  acumulando durações, `somar_dias_uteis` (pula fim de semana; N dias úteis), normalização
  `cronograma_formato` (legado acumulado → durações; idempotente), check de coerência padrão × prazo
  contratual (aviso quando o total corrido excede a data-limite em dias úteis; sem aviso quando cabe).
- **HTTP:**
  - Round-trip: `POST /data-entrega` → `GET .../contrato` devolve as datas (regressão do bug).
  - `folga < 0` sem senha → não grava; com senha gerencial → grava + `LogAcaoGerencial`.
  - Trava de assinatura: sem `data_entrega` **ou** sem `previsao_medicao` → 400; com ambas → 200, D0 dispara
    cronograma + data-limite contratual.
  - Lista de projetos: `atrasado` verdadeiro quando qualquer etapa aberta tem previsão vencida.
- **Contrato/marcadores:** anti-drift `CATALOGO` × `_montar_mapping` cobre os novos marcadores;
  `PRAZO_CONTRATUAL`/`DATA_PREVISTA_ENTREGA` renderizam no PDF de teste; `VENDA_PROGRAMADA` rende o texto
  quando `true` e vazio quando `false`.

## Fora de escopo (frentes próprias, depois)

- **C — Execução individualizada por ambiente** (segmentável pela obra do cliente): rascunho em
  `docs/superpowers/specs/ciclo/2026-07-14-fases-por-ambiente-prazos-devolucao-design.md`.
- **Agenda Global** (`docs/superpowers/specs/ciclo/2026-07-14-agenda-global-projetos-design.md`) — consome a
  mesma base de atraso do §6.
- **Assistente IA** que notifica/cobra execução — consome o previsto × real desta frente.
- **Feriados** no cálculo de dias úteis (MVP: só fins de semana).
