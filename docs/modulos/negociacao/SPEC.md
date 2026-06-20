# Módulo de Negociação — SPEC

**Status:** `[IMPLEMENTADO]` — atualizado 2026-06-20

---

## Visão geral

O módulo de negociação é o coração comercial do sistema. Permite ao consultor apresentar ao cliente o valor final do projeto com desconto, forma de pagamento e custos adicionais, respeitando os limites de cada perfil de acesso.

---

## Fluxo principal

```
Projeto carregado
    → Ambientes selecionados
    → Desconto aplicado (respeitando limite do perfil)
    → Forma de pagamento selecionada
    → Simulação financeira calculada
    → Orçamento salvo ou aprovado
```

---

## Tela de negociação (page-02)

### Cabeçalho
- Valor bruto total (soma dos XMLs selecionados)
- Desconto aplicado (R$ e %)
- Valor à vista

### Tabela de ambientes
- Lista de ambientes com checkbox de seleção (legado) ou listagem fixa do orçamento (EP-07)
- **Desconto individual por ambiente** — coluna "Desc.%" com input numérico editável
  - Fórmula: `à vista = bruto × (1 − desc_global%) × (1 − desc_individual%)`
  - Chave EP-07: `'ep07_' + pool_ambiente_id`; legado: nome do arquivo
  - Revertido automaticamente se ultrapassar o limite total de 35%
- Valor por ambiente após desconto (e financiamento distribuído proporcionalmente para Aymoré/TF)

### Sidebar — Parâmetros visíveis
- Campo de desconto (%) com validação de limite
- Botão "✓ OK" quando desconto excede limite
- Select de modalidade de pagamento
- Select de parcelas
- Painel de simulação financeira

### Botões de ação
- "Salvar orçamento" — salva estado sem avançar
- "Aprovar orçamento →" — bloqueia o projeto, conclui Revisão + Aprovação e gera o contrato (ver "Aprovação do orçamento")
- "⚙ Parâmetros" — abre modal de parâmetros internos

Após a aprovação, os botões passam a exibir **"✍ Assinar Contrato"** e **"✎ Rever Orçamento"** (senha gerencial → `POST /ciclo/desfazer_aprovacao`, libera a edição). Quando o contrato está assinado, **ambos** os botões somem.

---

## Parâmetros de negociação — Dois escopos

Os parâmetros de negociação são divididos em dois escopos distintos, com armazenamento e endpoints separados.

### 1. Parâmetros estruturais — Por PROJETO

Compartilhados por **todos os orçamentos** do projeto. Alterar num orçamento reflete em todos.

**Armazenamento:** `projetos_meta.parametros_json` (JSON com 10 chaves).

**Chaves (ver `PARAMETROS_DEFAULT` em `mod_orcamento_params.py`):**

| Chave | Tipo | Padrão | Descrição |
|---|---|---|---|
| `incluir_custos` | bool | `false` | Gross-up dos custos no valor bruto |
| `comissao_arq_pct` | float | `0.0` | Percentual da comissão do arquiteto |
| `comissao_arq_ativa` | bool | `false` | Liga/desliga a comissão do arquiteto |
| `fidelidade_pct` | float | `0.0` | Percentual do programa de fidelidade |
| `fidelidade_ativa` | bool | `false` | Liga/desliga o programa de fidelidade |
| `fora_da_sede` | bool | `false` | Liga o custo de viagem |
| `custo_viagem` | float | `0.0` | Custo de viagem em R$ |
| `brinde` | float | `0.0` | Valor do brinde em R$ |
| `brinde_ativo` | bool | `false` | Liga/desliga o brinde |
| `carga_trib` | float | `8.0` | Carga tributária em % |

**Endpoints:**
- `GET /api/projetos/<nome>/parametros` — retorna os parâmetros atuais do projeto.
- `POST /api/projetos/<nome>/parametros` — grava os parâmetros (com gate de bloqueio pós-aprovação e gate de assinatura — retorna 400 ou 403 se bloqueado). Usa `merge_parametros(atual, req)` do `mod_orcamento_params.py`.

**Carregamento no frontend:** ao ativar um orçamento (`GET /orcamentos/<id>/ambientes`), o backend devolve o campo `parametros` lido de `projetos_meta.parametros_json`. O frontend monta `projetoAtivo.margens` como `Object.assign({}, parametros, { desconto_pct })`, mesclando os parâmetros do projeto com o desconto do orçamento.

### 2. Parâmetros por ORÇAMENTO

Cada orçamento tem seu próprio desconto e snapshot de pagamento, independentes dos demais.

**a) Desconto global** — `orcamentos.margens` (TEXT/JSON):
- Armazena apenas `desconto_pct` (o endpoint ignora os demais campos enviados).
- **Endpoint:** `POST /api/orcamentos/<id>/margens` — grava somente `desconto_pct` (com gate de bloqueio/assinatura). Devolve `{ margens }` com apenas essa chave atualizada.
- Novo orçamento **copia o desconto** do orçamento de origem (`origem_id`).

**b) Desconto individual por ambiente** — `orcamento_ambientes.desconto_individual_pct` (Float, default 0):
- **Endpoint:** `PUT /api/orcamentos/<id>/descontos` — lote de `{pool_ambiente_id: pct}` (com gate de bloqueio/assinatura; `sanear_descontos` filtra ids fora do orçamento e exige 0 ≤ pct ≤ 100; `ValueError` → 400).

**c) Snapshot completo da negociação** — `orcamentos.negociacao_json` (JSON):
- Captura o estado completo das **entradas** da negociação: modalidade, formas (entrada e parcela), nº de parcelas, valor/data/forma da entrada, e datas manuais do Total Flex e da Venda Programada.
- **Não** inclui a taxa do Total Flex (campo gateado por gerente, excluído intencionalmente).
- Gravado via `PATCH /orcamentos/<id>/valor` (campo `negociacao_json`; omitir não apaga).
- Lido via `GET /orcamentos/<id>/ambientes` (campo `negociacao`).
- **Reprodução ao reabrir:** `_restaurarNegociacao()` no frontend reinjecta todas as entradas após `carregarModalidades()` e reproduz o plano com as datas salvas.

**d) Data da entrada** — existe em **todas** as modalidades com entrada:
- Cartão (`cc-entrada-data`), Aymoré (`ay-entrada-data`), Venda Programada (`vp-entrada-data`), Total Flex (`tf-entrada-data`), À Vista (campo próprio).
- Pré-preenchida com "hoje" ao abrir o painel.
- Salva no `negociacao_json` e refletida no contrato como `[DATA_ENTRADA]`.

---

## Modal de parâmetros

Acessível apenas para gerentes e diretores (consultor não vê).

### Campos
| Campo | Tipo | Descrição | Escopo |
|---|---|---|---|
| Incluir custos adicionais? | Toggle | Gross-up dos custos no valor bruto | Projeto |
| Desconto de venda | % | Mesmo campo da sidebar | Orçamento |
| Comissão do arquiteto | Toggle + % | Custo interno | Projeto |
| Programa de fidelidade | Toggle + % | Custo interno | Projeto |
| Custo Viagem | Toggle + R$ | Custo interno | Projeto |
| Brinde | Toggle + R$ | Custo interno | Projeto |
| Carga tributária | % | Imposto embutido no cálculo | Projeto |

Ao salvar, os campos estruturais são enviados ao `POST /api/projetos/<nome>/parametros` e o desconto ao `POST /api/orcamentos/<id>/margens`. O frontend atualiza `projetoAtivo.margens` com os `parametros` recém-salvos (preserva os estruturais ao reabrir o modal).

### Painel de apoio à negociação
Visível somente no modal. Mostra ao consultor a margem interna:
- Valor bruto total
- Desconto
- Valor à vista
- − Comissão arquiteto
- − Programa de fidelidade
- − Custo de viagem
- − Brinde
- **Valor líquido final** (margem da loja)
- **Desconto Total** (calculado sempre sobre bruto original dos XMLs)

---

## Regras de desconto

### Limites por perfil
- Consultor: máximo 10%
- Gerente de Vendas: máximo 20%
- Diretor: máximo 50%

### Autorização delegada
- Desconto acima do limite → solicita credenciais de gerente ou diretor
- O limite autorizado é o desconto específico aprovado (não o limite do autorizador)
- Ex: gerente autoriza 15% → novo limite é 15%, não 20%
- Persiste durante a negociação, reseta ao trocar de projeto
- Desconto salvo no projeto vira limite ao reabrir

### Toggle "Incluir custos adicionais?"
- Desligado (padrão): valor bruto = valor original dos XMLs
- Ligado: gross-up aplicado na seguinte ordem:
  1. `bruto_arq = bruto / (1 − arq%)` (se arquiteto ativo)
  2. `bruto_fid = bruto_arq / (1 − fid%)` (se fidelidade ativa)
  3. `bruto_viagem = bruto_fid + custo_viagem` (se fora da sede)
  4. `bruto_cliente = bruto_viagem + brinde` (se brinde ativo)

---

## Cálculo do Desconto Total

O "Desconto Total" no painel de apoio é calculado **sempre** sobre o valor bruto original dos XMLs, independente do toggle "Incluir custos adicionais?":

```
Desconto Total % = (bruto_original − valor_liquido_final) / bruto_original × 100
```

onde `bruto_original = Σ budget_total` dos XMLs (nunca o valor majorado pelo gross-up).

---

## Limite de Desconto Total

O sistema impõe um **teto absoluto de 35%** no desconto total, independente do nível do usuário.

- **Salvar parâmetros:** bloqueado se `desconto_total > 35%` com mensagem: *"Desconto total excede o limite máximo de descontos."*
- **Desconto individual:** revertido automaticamente para o valor anterior se ultrapassar o limite
- `_margemAtual` é atualizado em tempo real por `mpAtualizarApoio()` a cada mudança nos parâmetros
- O limite de nível do usuário (10/20/50%) e o teto de 35% são validações independentes e cumulativas

---

## Salvar vs Aprovar

| Ação | Efeito |
|---|---|
| Salvar orçamento | Salva o snapshot completo da negociação (`negociacao_json`) e o `valor_negociado` — pode continuar editando |
| Aprovar orçamento | Bloqueia o projeto — não permite mais alterações — conclui as etapas 5 (Revisão) e 6 (Aprovação) juntas e gera o contrato (etapa 7 em andamento). **Abortado** se o salvamento do snapshot falhar ou se o total for 0. |

---

## Garantia de salvamento ao aprovar

`salvarValorNegociado()` retorna `{ok, erro}`. Os fluxos `aprovarOrcamento`, `salvarOrcamento` e `abrirAprovacaoComDados` **abortam com mensagem de erro** se o salvamento falhar. Salvamento com total 0 é bloqueado (evita sobrescrever valor bom com 0).

---

## Aprovação do orçamento

"Aprovar Orçamento" só é possível quando **todas** as pré-condições estão atendidas:

1. **≥1 ambiente no orçamento** (etapa 4 — Primeiro orçamento — concluída, vinda de XML do Promob).
2. **Briefing do projeto completo** (os 5 campos obrigatórios; ver módulo de Projetos — briefing por projeto).
3. **Cadastro do cliente completo** (`validar_cliente_para_contrato`; ver módulo de Clientes — "Cadastro completo antes do contrato").

O **modal de aprovação não edita mais dados do cliente** — exibe o **nome como read-only** e captura apenas o **pagamento** (entrada/parcelas/forma) e o adendo. Dados de cadastro faltando disparam o popup "Cadastro Incompleto" (não há edição inline).

Ao aprovar:
- Conclui as etapas **5 (Revisão)** e **6 (Aprovação)** juntas.
- Gera o **contrato** e entra na **etapa 7 (Contrato em andamento)**.
- A negociação inteira fica **somente-leitura** (`aplicarBloqueioNegociacao`, cobre `#sb-params` + `#page-02`, exceto o `#ciclo-panel`).
- Os botões de aprovação são substituídos por **"✍ Assinar Contrato"** e **"✎ Rever Orçamento"**.

---

## Bloqueio pós-aprovação e pós-assinatura

### Após aprovação (etapa 6 concluída)
- UI: tela de negociação inteira somente-leitura; apenas `#ciclo-panel` permanece interativo.
- Backend: `_projeto_esta_bloqueado` retorna `true` → rotas de mutação retornam 400.
- Desbloqueio por "✎ Rever Orçamento": senha gerencial → `POST /ciclo/desfazer_aprovacao` → reseta etapas 6+7, libera a edição.

### Após 1ª assinatura do contrato
- UI: esconde Salvar/Parâmetros/Ambientes/Novo Orçamento/"✎ Rever Orçamento"; mantém "✍ Assinar Contrato" se a 2ª parte ainda não assinou.
- Backend: `_contrato_assinado` retorna `true` → rotas de mutação retornam **403**. Cobre: novo orçamento, pool, adicionar/remover/renomear ambiente, renomear orçamento, PATCH valor, margens, descontos, PATCH status.

### Após 2ª assinatura (ambas as partes)
- Status terminal **"🔒 Fechado"** setado automaticamente (como "convertido", nunca editável manualmente).
- Botão "✍ Assinar Contrato" some; ambos os botões ficam ausentes.

---

## Migrações automáticas no startup

- **`migrar_margens_para_orcamentos`:** copia margens do `projeto.json` para orçamentos sem margens (idempotente — só preenche vazias).
- **`migrar_parametros_para_projeto`:** copia os parâmetros estruturais de um orçamento para `projetos_meta.parametros_json` (idempotente — só roda se o projeto ainda não tem `parametros_json`).

---

## Comportamento de Modais

Todos os modais do sistema respondem à tecla **Esc** como equivalente ao botão "Cancelar" / "Voltar" (sem salvar). Um listener global `keydown` percorre os modais do z-index mais alto ao mais baixo e fecha o primeiro visível.

Modais cobertos: `modal-autorizacao`, `modal-perfil`, `modal-exportar`, `modal-gerente-senha`, `modal-tf-aviso`, `modal-cli-encontrado`, `modal-parceiro`, `modal-cliente`, `modal-pool-sobrescrever`, `modal-pool-renomear`, `modal-remover-amb-orc`, `modal-pool-ambientes`, `modal-novo-orc`, `modal-novo-ambiente`, `modal-params`.

---

## Arquivos relevantes

- `static/index.html` — todo o frontend da negociação
- `mod_orcamento_params.py` — `MARGENS_DEFAULT`, `merge_margens`, `PARAMETROS_DEFAULT`, `merge_parametros`, `sanear_descontos`
- `mod_fin/` — módulos financeiros (Total Flex, Venda Programada, Aymoré, Cartão)
- `main.py` — rotas `GET`/`POST /api/projetos/<nome>/parametros`, `POST /api/orcamentos/<id>/margens`, `PUT /api/orcamentos/<id>/descontos`, `GET /orcamentos/<id>/ambientes`, `PATCH /orcamentos/<id>/valor`
- `_enriquecer_projetos_com_pool()` em `main.py` — corrige contadores de ambientes em listagens
