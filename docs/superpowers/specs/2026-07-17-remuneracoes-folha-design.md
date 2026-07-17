# Remunerações + Folha de Pagamento — Design

**Data:** 2026-07-17 · **Status:** brainstorming (pré-plano) · **Base:** `main`

## Problema
A **Folha de Pagamento** tem motor/endpoints/tela prontos (`mod_folha`, `/api/folha*`, `folhaCarregar`) e teste verde, mas **não "funciona"** na prática: (a) a loja tem **0 funcionários** cadastrados e (b) o **cadastro de Funcionário foi removido** do módulo Cadastro (item 3 dos 9 tópicos). Além disso, hoje a remuneração vem de campos do **Funcionário** (`remuneracao_fixa/tipo`), não da **Função**, e a parte variável só existe para consultores. O usuário quer a Folha operante, com a remuneração **configurada por Função** e os **benefícios** compondo a despesa.

## Decisões (do brainstorming)
1. **A Folha paga FUNCIONÁRIOS** (entidade RH). O cadastro de Funcionário é **restaurado dentro do módulo Folha de Pagamento** (é RH, junto de onde se paga; o Cadastro segue sem Funcionários). O modelo `Funcionario` **já existe** (só a UI saiu) — reaproveitado.
2. **A remuneração é configurada por FUNÇÃO**, num painel **Config › "Remunerações"** (renomeia "Comissão de Vendas"): lista de funções → modal de remuneração por função.
3. **Parte fixa** (salário base) é **um campo do próprio modal de remuneração da função** (ao lado da Comissão) e mora na **Função** — todos com a mesma função ganham o mesmo fixo **agora**. Os campos de salário do **Funcionário** (`remuneracao_fixa/tipo/var`) ficam **legado/ignorados** pela Folha. **[FUTURO]** níveis por função (diferenciação por experiência) — o desenho não deve impedir (ver "Extensões").
4. **Comissão/variável:** o motor atual (`comissao_vendas` por faixas de meta, em `config_financeira_json`) **está correto** e alimenta a função **Consultor de Vendas** — mantido. Outras funções comissionadas (item 2): config de comissão **fixa (%)** ou **por meta**, com **base** = valor líquido de vendas OU valor de fábrica — **armazenada** nesta rodada (cálculo na Folha para não-consultor fica como extensão).
5. **Benefícios** (AT = Auxílio Transporte, VA = Vale Alimentação, PS = Plano de Saúde): por Função, cada um com **checkbox + valor R$**. **Compõem a despesa de salários** (entram no total da Folha). **[PENDENTE contador]** contas contábeis exatas dos benefícios e o tratamento no contra-cheque — por ora somam na despesa de salários (conta a definir, default abaixo).

## Modelo de dados
### `Funcao` (novas colunas — migração SQLite **e** Postgres, via `_add_cols` + `_migrar_colunas_pg`)
- `salario_fixo` (Float) — parte fixa mensal da função.
- `beneficios_json` (Text/JSON) — `{"at":{"on":bool,"valor":float}, "va":{...}, "ps":{...}}`.
- `comissao_json` (Text/JSON) — comissão das funções **não-consultor**: `{"por_meta":bool, "base":"liquido"|"fabrica", "pct":float | "faixas":[{"venda_ate":float|None,"pct":float}]}`. (A função Consultor de Vendas **não** usa este campo — usa o `comissao_vendas` da loja, mantido — ver roteamento no painel.)
- `usa_comissao_vendas` (Bool, default False) — marca a função cuja comissão vem do `comissao_vendas` da loja (semeada True na "Consultor de Vendas").
- _(Já existem do item 1: `perfil_padrao`, `remuneracao_padrao`, `regime_trabalho`, `regime_contratacao`, `descricao`. O `remuneracao_padrao` (tipo) passa a ser derivável/coadjuvante; a fonte de valor é `salario_fixo` + comissão + benefícios.)_

### `Funcionario` (reuso; sem novas colunas)
- Já tem `nome, cpf, telefone, email, funcao_id, cep/endereço, banco/agencia/conta/pix, status`. **A remuneração NÃO é mais editada no Funcionário** (vem da Função). Os campos `remuneracao_fixa/tipo/var` ficam **ignorados** pela Folha (legado; não removidos para não quebrar migração).

### Como a Folha identifica a função "Consultor de Vendas"
Por um marcador estável, não pelo texto do nome. Opção: um campo `Funcao.eh_consultor_vendas` (Bool) marcado no seed/edição, OU casar `perfil`/uma flag. **Decisão:** usar o **catálogo** — a função-semente "Consultor de Vendas" recebe a comissão via `comissao_vendas` da loja; identificamos por um flag `Funcao.usa_comissao_vendas` (Bool, default False; True na semente do Consultor). Assim o vínculo é dado, não string.

## Config › "Remunerações" (renomeia painel Comissão de Vendas)
- `cfg-tab-comissao` → rótulo **"Remunerações"**; `cfgComissaoRender` vira **lista de funções** (de `/api/funcoes`), cada linha com **"Configurar remuneração"**.
- **Modal de remuneração da função** — **um só, igual para toda função** (do usuário: "adicionar uma faixa Salário Fixo e outra Comissão"); `POST /api/funcoes/<id>` estendido via `funcao_aplicar`:
  - **Salário Fixo** (R$) → `salario_fixo`.
  - **Comissão:** checkbox **"por meta?"** (true/false) + **base** (líquido/fábrica):
    - **por meta = não:** um **% simples**.
    - **por meta = sim:** **faixas** `[{venda_ate, pct}]`.
    - **Roteamento do dado (importante):** para a função **Consultor de Vendas** (`usa_comissao_vendas = True`) a comissão **É** o `config_financeira_json.comissao_vendas` da loja — que **também alimenta a negociação/margem** (`resolver_comissao_venda`, main.py:8425). Então o modal do Consultor **edita esse config da loja** (não pode migrar pra fora, senão quebra o cálculo do negócio). Para as demais funções, grava em `comissao_json` (usado só na Folha/futuro).
  - **Benefícios:** AT/VA/PS, cada um checkbox + valor R$ → `beneficios_json`.
- Fonte única: tudo por função; nada digitado no funcionário.

## Funcionários no módulo Folha
- Nova **aba "Funcionários"** no módulo Folha (ou seção no submenu). Lista + form: `nome, cpf, telefone, email, Função (select /api/funcoes), dados bancários/PIX, status`. **Sem** campos de salário.
- Backend: reusa `/api/funcionarios` (GET/POST — **ainda existem**; só a UI foi removida). O form omite remuneração.
- `func_sync_acesso` (conta de login vinculada) — fora de escopo aqui; a ligação Funcionário↔Usuário permanece como está.

## Motor da Folha (rework de `mod_folha.calcular_folha`)
Por Funcionário ATIVO, resolvendo pela **Função** (`funcionario.funcao_id`):
- **parte_fixa** = `funcao.salario_fixo` (0 se sem função/valor).
- **parte_variavel** = se `funcao.usa_comissao_vendas`: `resolver_comissao_venda(cfg_loja, vendas_liquido_consultor(...), 0)` (motor atual, inalterado). Senão 0 nesta rodada (comissão das outras funções é config; cálculo = extensão).
- **beneficios** = soma dos valores dos benefícios ativos da função (`beneficios_json`); serializados discriminados (AT/VA/PS) para a tela e o contra-cheque futuro.
- **total** = fixa + variável + benefícios.
- **pagar:** `folha_fixa`→5.3.06, `folha_variavel`→5.3.01 (já existem). **Benefícios:** novo evento `folha_beneficios` → conta a definir (**default proposto:** `5.3.06` "Salários de Vendas" agregado, OU criar `5.3.07 Benefícios` — **decisão do contador**; o spec deixa como parâmetro, implementação usa uma conta única configurável).

## Faseamento (um spec, plano em 3 fases)
- **Fase 1 — Remunerações (config):** colunas na Função (fixa/benefícios/comissao_json/usa_comissao_vendas) + migração SQLite/PG; `funcao_aplicar`/`serialize`; painel Config › Remunerações (lista + modal por função, com fixa/comissão/benefícios). Backend TDD.
- **Fase 2 — Funcionários no módulo Folha:** aba Funcionários (form sem salário) reusando `/api/funcionarios`. Frontend + verificação.
- **Fase 3 — Motor calcula:** `calcular_folha` resolve pela Função (fixa + Consultor variável + benefícios); `pagar` lança benefícios; tela discrimina fixa/variável/benefícios/total. Backend TDD (sensível — motor contábil).

## Fora de escopo / pendências
- **[Contador]** contas contábeis dos benefícios e tratamento no contra-cheque (descontos do empregado × custo do empregador, encargos). Fase 3 usa uma conta única, a refinar.
- **[Extensão]** cálculo da comissão das funções **não-consultor** na Folha (a config já fica pronta na Fase 1).
- **[Extensão futura]** **níveis** por função (faixas salariais por experiência): previsto — `salario_fixo` viraria por nível, ou uma tabela `funcao_nivel`. Não implementado agora, mas o modelo (fixa na função) admite evolução.

## Testes
- **Backend (pytest/TDD):**
  - Fase 1: `funcao_aplicar/serialize` gravam/retornam salario_fixo, beneficios, comissao_json; validação (base ∈ {liquido,fabrica}, tipo ∈ {fixa,meta}); migração PG (ADD COLUMN).
  - Fase 3: `calcular_folha` — fixa vem da Função; Consultor soma variável (vendas×comissão); benefícios somam; funcionário sem função → 0; folha paga não recalcula; `pagar` lança fixa/variável/benefícios nas contas certas (prova via razão, como os testes de provisão fazem).
- **Frontend:** `node --check` + verificação manual (configurar remuneração de uma função; cadastrar funcionário; gerar folha; conferir fixa/variável/benefícios/total; pagar).

## Arquivos afetados (previstos)
- `database.py` (Funcao colunas + migrações), `mod_cadastro.py` (funcao_serialize/aplicar), `mod_folha.py` (motor), `mod_contabil.py` (evento `folha_beneficios` + conta), `main.py` (se precisar de endpoint de comissão por função), `static/index.html` (painel Remunerações + modal + aba Funcionários na Folha), `tests/*`, `DEV_LOG.md`.
