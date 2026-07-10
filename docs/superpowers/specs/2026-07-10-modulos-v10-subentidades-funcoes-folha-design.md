# Modulos_Orizon_v10 — Sub-entidades, Tabela de Funções e Folha de Pagamento

**Data:** 2026-07-10 · **Status:** implementado (Sessão 52) · **Suíte:** 783 verdes

Documento como-implementado das três frentes do `Modulos_Orizon_v10.docx`.

## Parte 1 — Sub-entidades reutilizáveis (Endereço + Dados Bancários + PIX)

**Objetivo:** padronizar Endereço e Dados Bancários como blocos reutilizáveis nos cadastros.

- **Endereço:** `cep, logradouro, numero, complemento, bairro, cidade, uf` (mesmo padrão ViaCEP de Clientes).
- **Dados Bancários:** `banco_nome, banco_codigo, agencia, conta, pix`.
- Aplicação por entidade:
  - **Funcionário** e **Terceiro (PF):** Endereço + Dados Bancários completos.
  - **Fornecedor:** Endereço + Dados Bancários.
  - **Parceiro:** só **Chave PIX** (`Parceiro.pix`).

**Backend:** colunas em `database.py` (`Funcionario`/`Fornecedor`/`Terceiro`/`Parceiro`), migração
idempotente ao fim de `_migrar_colunas` (`_ENDERECO`/`_BANCO` + `_add_cols` via PRAGMA+ALTER).
`mod_cadastro.py`: `ENDERECO_CAMPOS`/`BANCO_CAMPOS` + `_aplicar_campos`/`_serial_campos`, integrados aos
serialize/aplicar. Parceiro: `_parceiro_dict` + create/editar em `main.py` incluem `pix`.

**Frontend:** o modal genérico de cadastro (`_CAD_DEFS`/`cadEntRender`/`campoHtml`) ganhou tipos de campo:
`secao` (divisor de seção), `cep` (dispara `cadCepBuscar` → ViaCEP preenche logradouro/bairro/cidade/uf) e
`select_funcoes`. As seções entram por spread `..._CAMPOS_ENDERECO` / `..._CAMPOS_BANCO`. O Parceiro (modal
próprio) recebeu o campo **Chave PIX** com wiring em `parAbrirModal`/`parSalvar`.

## Parte 2 — Tabela de Funções (Config)

**Objetivo:** catálogo configurável de funções, referenciado pelos cadastros (fim do texto livre).

- Modelo `Funcao` (`funcoes`: `id, loja_id, nome, status, criado_em`), loja-scoped.
- `Funcionario.funcao_id` e `Terceiro.funcao_id` (FK) apontam para o catálogo. O `Terceiro.tipo_servico`
  passa a nullable (legado).
- Endpoints `/api/funcoes` (GET lista com filtro status / POST criar-editar) no dispatch `_cad_ent`.
- **Frontend:** aba **Config → Funções** (`cfgFuncoesRender`): adicionar, renomear, inativar/reativar.
  Selects `Função` nos cadastros de Funcionário e Terceiro alimentados por `/api/funcoes?status=ativo`
  (cache `_funcoesCache`, invalidado quando o catálogo muda).

## Parte 3 — Folha de Pagamento (§2.1)

**Princípio:** automatiza o pagamento — **motor de cálculo, nada digitado manualmente**.

- **Parte fixa:** `remuneracao_fixa` do cadastro do Funcionário.
- **Parte variável** (apenas `remuneracao_tipo == "fixa_variavel"`): soma das vendas **fechadas** do
  consultor no período (`Projeto.criado_por_id` + `status_at` no mês; `Orcamento.valor_liquido`) × % da
  faixa de meta atingida (`mod_provisoes.resolver_comissao_venda`, config de Comissão de Vendas).
- **Pagamento:** lança a despesa nas contas **5.3 já existentes** (sem conta nova): parte fixa → `5.3.06`
  (Salários de Vendas), parte variável → `5.3.01` (Comissão de Vendedor). Usa os Dados Bancários/PIX do
  cadastro.

**Backend:** `mod_folha.py` (`vendas_liquido_consultor`, `calcular_folha`, `gerar_folha` idempotente 1/
funcionário-ativo, `pagar` idempotente por `ref="folha:<id>"`, `serialize`/`listar`). Modelo
`FolhaPagamento` (`folha_pagamento`: competência AAAA-MM, `parte_fixa/vendas_liq/faixa_pct/parte_variavel/
total`, status `aberta|paga`, `ref_lancamento`, `pago_em`). Eventos `folha_fixa`/`folha_variavel` em
`mod_contabil.EVENTOS`. Endpoints GET `/api/folha`, POST `/api/folha/gerar`, POST `/api/folha/<id>/pagar`.
Domínio `folha` no manifesto (`modulos.py`).

**Frontend:** seção **Financeiro → Folha de Pagamento** (`folhaCarregar`/`folhaRender`): seletor de
competência (`input[type=month]`), botão **Gerar folha**, tabela (Funcionário · Parte fixa · Vendas líq. ·
Faixa · Parte variável · Total · Pagamento) com Totais e ação **Pagar** por linha.

## Testes
- `tests/test_folha.py`: cálculo fixa+variável, geração idempotente (só ativos), postagem nas 5.3,
  endpoints HTTP.
- `tests/test_cadastro.py`: catálogo de Funções + referência resolvida (`funcao_nome`), Endereço/Dados
  Bancários persistem.
- `tests/test_parceiro_vinculo_loja.py`: PIX do Parceiro round-trip (create + editar).

## Notas de decisão
- **Folha na UI vive sob Financeiro** (seção do submenu), reusando gating/panel do módulo financeiro,
  embora o backend a declare como domínio próprio (`folha`) — placement de UI ≠ fronteira de código.
- **Sem conta contábil nova:** exigência do spec; reaproveita `5.3.01`/`5.3.06` do Plano de Contas.
- **Idempotência** em `gerar_folha` (por funcionário+competência) e `pagar` (por `ref`) evita duplicidade
  em reprocessos — mesmo padrão de auto-constituição das Provisões.
