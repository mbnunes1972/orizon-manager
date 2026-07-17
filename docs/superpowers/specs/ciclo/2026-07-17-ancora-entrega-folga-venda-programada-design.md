# Âncora da Entrega, Folga com Bloqueio e Venda Programada + Medição — Design

**Data:** 2026-07-17 · **Status:** aprovado no brainstorm (pronto para plano) · **Frente:** A+B (C — execução
por ambiente — fica para spec própria depois).

Consolida o que foi levantado no teste manual do card do Contrato: a data de entrega esperada **não
persistia** na tela, a **folga** exibida era incompreensível, e faltavam **venda programada** + **previsão
de medição**. Reusa `mod_cronograma`, `Projeto` (`projetos_meta`), o padrão de reautenticação gerencial
(`LogAcaoGerencial` + `perfis.pode(nivel,"autorizar")`) e o Cronograma do Ciclo (v11).

## Contexto e modelo mental

O ciclo monitora **datas previstas × reais** por etapa. A **data de entrega esperada** é a meta/promessa ao
cliente e a **âncora regressiva** do cronograma. Duas alavancas determinam o cumprimento dessa data:

- **Medição** (etapas 9/10) — marco de continuidade; a produção realista só faz sentido a partir dela.
- **Aprovação do Projeto Executivo** (etapa 11) — o gargalo real: revisões de PE empurram a entrega.

A **venda programada** existe porque a **obra do cliente** controla *quando* a medição pode ocorrer. Nesse
modo registra-se uma **previsão de medição**, e a folga passa a medir apenas o trecho sob controle da loja
(medição → entrega).

O par previsto × real por etapa é o insumo que a **assistente IA (futura)** vai ler para notificar/cobrar a
execução. **Esta frente NÃO constrói a IA** — apenas garante que os dados existam, corretos e visíveis.

## Decisões fixadas no brainstorm

1. **Natureza da data de entrega:** previsão de trabalho **editável**; mora no `Projeto` (`projetos_meta`),
   como hoje. Não migra para o `Contrato`.
2. **Semântica do `prazo_dias`:** **duração própria da etapa** (não acumulado desde D0). `cronogramas()` já
   acumula corretamente; `gerar_cronograma_projeto` e o `default` estão errados e serão corrigidos.
3. **Folga mínima:** regra é **folga ≥ 0** ("tem que caber"). Sem colchão configurável. A diferença para
   hoje é que passa a **bloquear de verdade**, com **override gerencial**.
4. **Modos de venda e trava da assinatura:** a **data de entrega é sempre obrigatória** (nos dois modos). A
   **venda programada acrescenta** a previsão de medição como obrigatória.
5. **D0 permanece = confirmação das DUAS assinaturas** (loja + cliente). Inalterado.
6. **Monitoramento nesta frente:** card do Contrato + modal de Cronograma do projeto (o que já existe),
   **mais** um sinal de atraso da entrega na **lista de projetos**. Agenda Global e IA ficam para depois.

## Folga por modo (núcleo)

Com `prazo_dias` = duração da etapa e Σ = soma das durações no trecho:

| Modo | Folga = | Bloqueio |
|---|---|---|
| **Normal** | `(entrega − data_inicio) − Σ durações de todas as etapas até a "16"` | folga < 0 → só com override gerencial |
| **Programada** | `(entrega − previsao_medicao) − Σ durações das etapas da medição até a "16"` | idem |

Justificativa: as etapas **até a medição** são controladas pela obra do cliente (fora do controle da loja) —
não devem penalizar a folga na venda programada. As etapas **medição → entrega** (PE, produção, entrega) são
da loja e são o que a folga precisa garantir.

> A etapa de entrega ao cliente é a **"16"** (`mod_ciclo.ETAPA_NOME["16"] = "Entrega no cliente"`; "17" =
> Montagem). O regressivo já ancora em `codigo_entrega="16"` (`mod_cronograma.cronograma_do_projeto`). O
> "início da contagem" da venda programada é a **primeira etapa de medição** presente no Cronograma Padrão
> (definição operacional: a etapa "10" — Medição; se ausente do padrão, cai para a "9").

## Componentes

### 1. Modelo de dados — `Projeto` (`projetos_meta`)

Colunas novas (migração idempotente via `_add_cols`, como `data_entrega`/`data_inicio` em `database.py:1355`):

- `venda_programada` — Boolean, default `False`.
- `previsao_medicao` — Date, nullable. Obrigatório **sse** `venda_programada`.

`data_entrega` e `data_inicio` já existem (`database.py:471`) — reusados.

### 2. Correção do bug de persistência ("a data se perde")

- **Causa:** o card lê `contrato.data_entrega` (`static/index.html:13602`), campo que **não existe** no
  `Contrato` nem é serializado. A gravação em `Projeto.data_entrega` (`main.py:4721`) funciona; a releitura
  vem vazia → parece que sumiu.
- **Correção:** a serialização do contrato (`GET .../contrato`, `main.py:2369`) passa a incluir, **lidos do
  `Projeto`**: `data_entrega`, `venda_programada`, `previsao_medicao`. O card lê desses campos.

### 3. Correção da folga e do Cronograma Padrão

- **`mod_cronograma.gerar_cronograma_projeto`** (`mod_cronograma.py:37`): hoje grava
  `data_prevista_conclusao = D0 + prazo_dias` (trata prazo como offset direto de D0). Passa a **acumular**:
  `data_prevista_conclusao = D0 + Σ(durações das etapas até esta, inclusive)`.
- **`cronogramas()`** (`mod_cronograma.py:90`) já acumula durações — **mantido**. É a referência da semântica.
- **Reescrever o `default` `cronograma_padrao`** em `mod_provisoes.config_financeira_default`
  (`mod_provisoes.py:37`) com **durações realistas por etapa** (os valores atuais 2,5,10,…,70 só fazem
  sentido como acumulado e somariam ~525 dias se lidos como duração). Merge com default preservado (lojas
  antigas): ver nota de migração de config abaixo.
- **Folga por modo:** a função de cálculo passa a receber o modo. Para normal, âncora do progressivo =
  `data_inicio`; para programada, âncora = `previsao_medicao` e o somatório considera só as etapas da
  medição em diante. `cabe_no_cronograma` inalterada (folga ≥ 0).

> **Migração de config (durações) — decisão:** lojas que já salvaram `cronograma_padrao` com os valores
> acumulados antigos ficariam com durações absurdas, e o merge com default **não** basta (a chave já existe).
> **Escolha — marcador de versão idempotente:** a config ganha `cronograma_formato` (int). Ausente/`1` =
> formato-legado **acumulado**; `2` = **durações**. Na leitura (`_cfg_financeira_loja`), config em `formato 1`
> é convertida para durações por diferença (`dur[i] = acc[i] − acc[i-1]`, `dur[0] = acc[0]`) e reescrita como
> `formato 2` (conversão única, idempotente); config já em `formato 2` é usada como está. O novo default nasce
> em `formato 2`. Robusto (não depende de heurística sobre os números) e não deixa dado legado passar como
> duração. Cobrir com teste dedicado.

### 4. Bloqueio da data + override gerencial

- **`POST /api/projetos/<nome>/data-entrega`** (`main.py:4698`):
  - Calcula a folga no modo do projeto. Se `folga ≥ 0` → grava (fluxo normal, `ok:true, cabe:true`).
  - Se `folga < 0` e **sem** reautenticação → **não grava**; retorna `ok:true, cabe:false, folga_min` (só
    diagnóstico). Hoje grava mesmo sem caber — este é o "primeiro problema" a corrigir.
  - Se `folga < 0` **com** `login`/`senha` de nível `autorizar` (`perfis.pode`) → grava e registra
    `LogAcaoGerencial(acao="data_entrega_sem_folga", projeto_nome, contexto={data, folga})`.
  - O mesmo endpoint (ou irmão) persiste `venda_programada`/`previsao_medicao`.
- **Trava da assinatura** (guard em `main.py:6159`, a 2ª assinatura que completa loja+cliente):
  - Venda **normal:** exige `data_entrega` (como hoje).
  - Venda **programada:** exige `data_entrega` **e** `previsao_medicao`.
  - Faltando o campo do modo → 400, sem assinar. **D0/`gerar_cronograma_projeto` inalterados** no disparo.

### 5. UI — card do Contrato (`static/index.html`)

- O bloco "Data de entrega esperada" (`index.html:13598`) passa a ler `contrato.data_entrega` já servido.
- **Checkbox "Venda programada"** → revela o campo **"Previsão de medição"** (input date). Ambos persistem
  no mesmo POST.
- Retorno da validação: `cabe:false` mostra o aviso e, para Gerente+ (`_podeAutorizarFront`), oferece o
  **registro com autorização** (modal de senha do próprio autorizador, mesmo padrão do `modal-crono` v11).

### 6. Sinal de atraso na lista de projetos

- View read-only (sem tabela nova): para cada projeto, expõe `data_entrega` e um flag `entrega_atrasada`
  = `hoje > data_entrega` **e** etapa "16" não concluída.
- A lista/painel de projetos (`renderProjResultados`) exibe a data de entrega + selo de atraso.

## Fluxo (venda programada)

1. Orçamento aprovado → contrato. No card, marca **Venda programada**, informa **previsão de medição** e a
   **data de entrega** esperada.
2. Validar: folga = `(entrega − previsao_medicao) − Σ(medição→16)`. Se < 0, bloqueia (ou grava com senha
   gerencial + log).
3. 2ª assinatura exige entrega **e** previsão de medição → **D0** dispara `gerar_cronograma_projeto`
   (durações acumuladas a partir de D0).
4. Medição real conclui a etapa → `concluido_em` alimenta o monitoramento previsto × real (base da IA).

## Faseamento (3 fatias incrementais, cada uma testável/mergeável)

- **Fatia 1 — Correções (destrava o uso):** bug de persistência (§2) + correção de folga e default (§3).
  Sem mudança de contrato de UI além de religar a leitura.
- **Fatia 2 — Enforcement:** bloqueio da data com override gerencial (§4) + trava de assinatura por modo.
- **Fatia 3 — Programada + monitoramento:** flag venda programada + previsão de medição (§1, §5) + sinal de
  atraso na lista (§6).

## Testes (TDD no núcleo)

- **`mod_cronograma`:** folga por modo (normal × programada), `gerar_cronograma_projeto` acumulando
  durações (previsão da etapa = D0 + Σ durações até ela), `cabe_no_cronograma` inalterada.
- **HTTP:**
  - Round-trip da data: `POST /data-entrega` → `GET .../contrato` devolve a data (regressão do bug).
  - `folga < 0` sem senha → não grava; com senha gerencial → grava + `LogAcaoGerencial`.
  - Trava de assinatura: normal sem entrega → 400; programada sem previsão de medição → 400; com os campos
    do modo → 200 e D0 dispara.
  - Lista de projetos: `entrega_atrasada` verdadeiro quando `hoje > entrega` e etapa 16 aberta.

## Fora de escopo (frentes próprias, depois)

- **C — Execução individualizada por ambiente** (segmentável pela obra do cliente): rascunho em
  `docs/superpowers/specs/ciclo/2026-07-14-fases-por-ambiente-prazos-devolucao-design.md`.
- **Agenda Global** (`docs/superpowers/specs/ciclo/2026-07-14-agenda-global-projetos-design.md`).
- **Assistente IA** que notifica/cobra execução — consome o previsto × real desta frente.
