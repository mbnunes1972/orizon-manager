# Módulo de Contratos — SPEC

**Status:** `[IMPLEMENTADO]` — atualizado 2026-06-20

---

## Visão geral

O módulo de contratos gerencia a geração, assinatura e aprovação dos contratos de venda após a aprovação do orçamento. Segue o fluxo padrão de mercado para contratos de móveis planejados.

---

## Fluxo do contrato

```
Orçamento aprovado (1º orçamento concluído, com ambientes)
    → Geração do contrato (preenchimento direto do modelo .docx → PDF)
    → Revisão interna (gerente)
    → Envio ao cliente (para assinatura)
    → Assinatura digital (loja + cliente)
    → Confirmação da assinatura
    → Contrato vigente → Pós-venda inicia
```

A geração marca a **etapa 5 (Revisão)** e a **etapa 6 (Aprovação)** como concluídas e a **etapa 7 (Contrato)** como `em_andamento`.

---

## Tipos de contrato

| Tipo | Descrição |
|---|---|
| Contrato de Venda | Documento principal — condições comerciais, valores, prazo |
| Folha de Capa | Resumo do projeto com ambientes e valores `[VALIDAR]` |
| Termo de Venda Programada | Específico para modalidade Venda Programada |
| Projeto Executivo | Aprovação técnica — gerado na fase de pós-venda |

---

## Dados do contrato

O contrato é gerado automaticamente com base nos dados do projeto aprovado:

- **Partes:** dados da loja (CONTRATADA, INSPIRIUM — via constantes `_NOME_EMPRESA`/`_CNPJ_EMPRESA`) + dados do cliente (CONTRATANTE)
- **Objeto:** lista de ambientes com valores
- **Valor total:** conforme orçamento aprovado
- **Forma de pagamento:** conforme modalidade selecionada (normalizada a partir do JSON de pagamento)
- **Cronograma de pagamento:** entrada + parcelas
- **Prazo de entrega:** `[VALIDAR]` — definir prazo padrão por tipo de produto
- **Condições gerais:** cláusulas padrão do modelo `[VALIDAR]`

---

## Geração do contrato `[IMPLEMENTADO]`

A geração é feita por **`mod_contrato.preencher_contrato(contrato_id, ctx, protegido=True)`**, sobre o template **`modelo_contrato_mapeado.docx`** (raiz, versionado — `mod_contrato._MODELO`). O template é um **contrato completo com placeholders `[MARCADOR]`** em todos os campos (não há Jinja2). A geração tem duas etapas:

1. **Grade de parcelas (por posição):** `_preencher_grade(doc, pag)` escreve a tabela de pagamento (`tables[3]`, linhas 3–10, 24 parcelas) por posição de célula via `_unique_cells` — cada parcela = **valor + data, sem ordinal**. Slots sem parcela viram **traços `--------`** no valor e na data (as linhas são **preservadas**, não removidas).
   - **Cartão de crédito:** cada parcela na sua posição com o **valor e SEM data** (data = `""`); slots além do nº de parcelas = traço. O campo `[NUM_PARCELAS]` mostra o **número de parcelas** quando parcelado (ex.: `"12"`) e **`"à vista"`** quando 1x.
   - **Demais modalidades:** valor + data por parcela, como descrito acima.
2. **Substituição de marcadores:** `_substituir_marcadores(doc, mapping)` substitui todos os `[MARCADOR]` no corpo, tabelas e cabeçalho (tolera `[[` e maiúsc/minúsc; marcador desconhecido é mantido). O mapa vem de `_montar_mapping(ctx, pag)`. Reutiliza `_subst_paragrafo` em todos os contextos — **robusto a marcadores fragmentados em múltiplos runs** (opera no texto concatenado do parágrafo).

**Cabeçalho robusto:** o ramo de headers de `_substituir_marcadores` reutiliza `_subst_paragrafo` em parágrafos, tabelas **e caixas de texto** (`wps:txbx` / `mc:AlternateContent` → `w:txbxContent`) do cabeçalho. `[Num_Contrato]` e `[Data_contrato]` vivem em caixas de texto, não em parágrafos comuns.

**Marcadores do template:**

*Identificação do contrato:*
`[Num_Contrato]` (caixa de texto no cabeçalho), `[Data_contrato]` (caixa de texto no cabeçalho), `[DATA_CONTRATO]`

*Dados do cliente:*
`[NOME_CLIENTE]`, `[CPF_CLIENTE]`, `[CPF]`, `[EMAIL]`, `[TELEFONE]`, `[RES_*]`, `[INST_*]`

*Bloco de assinatura (separados em marcadores distintos):*
`[NOME_EMPRESA]`, `[CNPJ_EMPRESA]`, `[NOME_CLIENTE]`, `[CPF_CLIENTE]`, `[NOME_TESTEMUNHA_1]`, `[CPF_TESTEMUNHA_1]`, `[NOME_TESTEMUNHA_2]`, `[CPF_TESTEMUNHA_2]`

*Pagamento:*
`[VALOR_ENTRADA]`, `[FORMA_ENTRADA]`, `[DATA_ENTRADA]`, `[MODALIDADE]`, `[NUM_PARCELAS]`, `[TIPO]` (forma das parcelas), **`[TOTAL_CONTRATO]`** (= "Valor do Contrato"), grade `[VALOR_PARCELA]`/`[DATA_PARCELA_1..24]`

*Consultor:*
`[CONSULTOR_NOME]`, `[CONSULTOR_TELEFONE]`

> A diagramação (rótulos dos campos, layout das assinaturas) é **propriedade do template** — o código só substitui valores, preservando a formatação. Os helpers antigos `_set_cell`/`_set_para` (rótulos Pt-7) e `_relabel_cpf_cnpj` foram **removidos**.

**Número do contrato:** gerado uma vez por `gerar_num_contrato(existing_nums)` no formato **`LOJA-AAAA-MM-DD-SEQ`** (ex.: `INS-2026-06-18-001`), sequência **contínua por loja** (máximo existente + 1). Loja fixa `INS` (`_CODIGO_LOJA`, `[TODO]` painel de loja). Guardado em `Contrato.num_contrato`, estável em regerações. Renderizado no **cabeçalho** (direita) com a **data** logo abaixo — ambos **gerados pelo sistema** (não editáveis).

**Dados de pagamento:** o frontend monta `window._planoPagamento` (estruturado: só parcelas reais com `valor` numérico + `data`, mais `total_cliente` e `texto_cartao`); `_capturarPagamento` retorna esse objeto (não raspa mais o DOM — era a causa de um bug em que data/valor saíam trocados). O backend `_parse_pagamento` produz `datas[24]`, `valores[24]` (dinheiro), `num_parcelas_int`, `valor_contrato` e `texto_cartao`. Para cartão, `num_parcelas_disp` é `"à vista"` quando 1x ou o número como string quando >1x.

**Entrada no contrato:** `[VALOR_ENTRADA]`, `[DATA_ENTRADA]` e `[FORMA_ENTRADA]` vêm do `_planoPagamento` capturado no frontend — que lê o campo de data da entrada (`cc-entrada-data`, `ay-entrada-data`, `vp-entrada-data`, `tf-entrada-data`, ou campo próprio da modalidade À Vista). A data da entrada está disponível em **todas as modalidades com entrada**; antes, algumas modalidades usavam a data do contrato como fallback.

**Construção do contexto:** `construir_contexto(cliente, usuario, forma_pagamento_json)` monta o `ctx` (dados do cliente, consultor e `_pag` parseado).

**Conversão para PDF:** `_converter_pdf(docx_path)` converte um `.docx` existente em PDF via **LibreOffice** (sem regenerar o docx). `gerar_pdf_contrato` = `preencher_contrato` + `_converter_pdf`. Sem LibreOffice → **fallback gracioso** (`LibreOfficeIndisponivel`, capturada no endpoint): salva o `.docx` e avança o fluxo.

---

## Bloco de assinatura `[IMPLEMENTADO]`

O bloco de assinatura foi reestruturado para usar **marcadores separados** para nome e documento, cada par em linhas distintas:

| Signatário | Marcador nome | Marcador documento |
|---|---|---|
| Empresa (CONTRATADA) | `[NOME_EMPRESA]` | `[CNPJ_EMPRESA]` |
| Cliente (CONTRATANTE) | `[NOME_CLIENTE]` | `[CPF_CLIENTE]` |
| Testemunha 1 | `[NOME_TESTEMUNHA_1]` | `[CPF_TESTEMUNHA_1]` |
| Testemunha 2 | `[NOME_TESTEMUNHA_2]` | `[CPF_TESTEMUNHA_2]` |

**Constantes da empresa** em `mod_contrato.py`:
```python
_NOME_EMPRESA = "INSPIRIUM MOVEIS PLANEJADOS E DECORACAO LTDA"  # TODO: configurador de lojas
_CNPJ_EMPRESA = "19.152.134/0001-56"                            # TODO: configurador de lojas
```

**Testemunhas provisórias** (`_TESTEMUNHAS` em `mod_contrato.py`):
- `("Jaime Perinazzo", "xxx.xxx.xxx-xx")`
- `("Felipe Guizalberte", "yyy.yyy.yyy-yy")`

`[TODO]` — nome/CNPJ e testemunhas virão do painel de configuração de loja (sub-projeto futuro).

---

## Contrato editável protegido + edição pontual `[IMPLEMENTADO]`

O `.docx` gerado sai **protegido por padrão** (`protegido=True`): o documento inteiro fica
**somente leitura** (`w:documentProtection edit="readOnly" enforcement="1"`) e **apenas os
valores de campo** ficam editáveis, cada um envolto por uma região
`w:permStart`/`w:permEnd` (grupo "everyone") — `_proteger_editaveis(doc, runs)`. O texto
fixo (cláusulas) e o **cabeçalho (número + data)** ficam travados. A automação
(LibreOffice→PDF, assinatura) **lê** o arquivo normalmente; a proteção só afeta a edição
interativa.

**Edição pontual (gerencial):** botão "✎ Editar contrato" na tela do contrato →
`POST /api/projetos/<nome>/contrato/editar` (gate **gerente/diretor/admin**, auditado em
`log_acoes_gerenciais`, ação `editar_contrato`). O backend abre o `.docx` no app escolhido
(**Word** via `os.startfile`, **LibreOffice** via `soffice`) e inicia um **watcher**
(`contrato_editar.watcher_regerar_pdf`) que, a cada salvamento (mtime cresce + lock
`~$`/`.~lock` liberado, com debounce e timeout de 30 min), regera o PDF via
`_converter_pdf` e atualiza `Contrato.pdf_path`. Helper testável de gate:
`contrato_editar.validar_gerencial(db, login, senha)`.

> A trava "só campos editáveis" se confirma de verdade abrindo no Word/LibreOffice
> (interativo); os testes cobrem a estrutura OOXML e a lógica de gate/watcher.

---

## Assinatura `[IMPLEMENTADO]`

### Signatários no documento

- **1º signatário = empresa** (CONTRATADA) — preenchido pelos marcadores `[NOME_EMPRESA]`/`[CNPJ_EMPRESA]` (valores reais das constantes `_NOME_EMPRESA`/`_CNPJ_EMPRESA`).
- **2º signatário = o CLIENTE** (CONTRATANTE) — preenchido com `[NOME_CLIENTE]`/`[CPF_CLIENTE]` vindos do `ctx`.
- O **consultor NUNCA** aparece como signatário; consta apenas no cabeçalho "Consultor:" no topo do documento.
- **Duas testemunhas provisórias:** **Jaime Perinazzo** e **Felipe Guizalberte** (constante `_TESTEMUNHAS` em `mod_contrato.py`). `[TODO]` — virão do painel de configuração de loja.

### Signatário diferente do cliente cadastrado (`signatario_override`)

O `POST /api/projetos/<nome>/contrato` aceita um dict opcional **`signatario_override`** que **substitui os dados do cadastro apenas para aquele contrato** (usado quando o signatário não é o cliente cadastrado). Quando presente (e com `nome` preenchido), o override é mesclado sobre `cliente_dict` antes de montar o contexto e de validar; sem ele, vale o cadastro. No frontend, ao gerar o contrato, pergunta-se "o signatário é o próprio cliente cadastrado?"; se não, abre-se um modal com todos os dados do contrato, que viram o `signatario_override` no corpo do POST.

### Assinatura digital

A assinatura digital registra um **`ContratoAssinatura`** por parte (loja / cliente) com **hash SHA-256**.

### Trava pós-assinatura

Após a **1ª assinatura** (qualquer parte), o backend recusa **403** todas as mutações (novo orçamento, pool, adicionar/remover/renomear ambiente, renomear orçamento, PATCH valor, margens, descontos, PATCH status). Quando **ambas** as partes assinam, o projeto recebe o status terminal **"🔒 Fechado"** (automático, como "convertido" — não editável via dropdown).

A função `_contrato_assinado(nome_safe, db)` é a **fonte única** para esta verificação (status assinado_loja/cliente/assinado/vigente OU `len(assinaturas) > 0`). Exposta em `GET /api/projetos/<nome>/ciclo` como `contrato_assinado` e `contrato_totalmente_assinado`.

---

## Pré-condições para gerar (gates do `POST /api/projetos/<nome>/contrato`)

1. **Cadastro do cliente completo** — validado por `validar_cliente_para_contrato` (nome, CPF, e-mail, telefone, endereço residencial; instalação se diferente). Se faltar algo → **HTTP 400** com a lista em `campos_faltando`.
2. **Orçamento com ao menos um ambiente** (1º orçamento concluído) — se `orcamento_dict` não tiver ambientes → **HTTP 400**.

A validação roda sobre os dados que serão **de fato renderizados** (já considerando o `signatario_override`, se houver).

---

## Status do contrato

| Status | Descrição |
|---|---|
| `rascunho` | Contrato gerado, em preparação |
| `para_assinatura` | Documento pronto (PDF ou .docx), aguardando assinaturas |
| `assinado` / `vigente` | Loja e cliente assinaram — em vigor; pós-venda pode iniciar |
| `cancelado` | Contrato cancelado |

Fluxo de status: **rascunho → para_assinatura → assinado/vigente**.

---

## Repositório de modelos

- O modelo único utilizado é **`modelo_contrato_mapeado.docx`**, na **raiz do projeto** e **versionado no git** (o antigo `modelo_contrato_final.docx` foi **aposentado**).
- O template usa **marcadores `[MARCADOR]`** em todos os campos; o preenchimento é por substituição de marcadores + grade por posição (`python-docx`/lxml) — **não** há Jinja2. O usuário edita este mesmo arquivo para mudar layout/cláusulas.
- `[VALIDAR]` — quais outros modelos (Folha de Capa, Termo de Venda Programada, Projeto Executivo) devem existir além do contrato de venda.

---

## User Stories

**US-CON-001** — Como gerente, quero gerar automaticamente o contrato após a aprovação do orçamento (com cadastro completo e orçamento com ambientes).

**US-CON-002** — Como gerente, quero revisar e aprovar o contrato antes de enviá-lo ao cliente.

**US-CON-003** — Como consultor, quero registrar a assinatura digital (loja e cliente) no sistema.

**US-CON-004** — Como qualquer usuário, quero consultar o histórico de contratos de um projeto.

**US-CON-005** — Como consultor, quero gerar o contrato para um signatário diferente do cliente cadastrado, informando os dados só para aquele contrato (`signatario_override`).

**US-CON-006** — Como gerente/diretor, quero corrigir pontualmente os campos do contrato abrindo o `.docx` no Word/LibreOffice (só os valores editam; o restante fica travado) e ter o PDF regerado automaticamente ao salvar.

---

## Direção futura — Modelo de contrato por loja (registrado 2026-06-27)

Decisão de produto (a virar slice próprio, dentro do "banco de documentos padronizados da loja" — item #8 da config de loja):

- **Sem edição inline do contrato.** O sistema **gera sempre a partir dos dados** (cadastro do
  cliente + dados da loja) e produz **PDF**. Remover o fluxo de edição via `contrato_editar.py`
  ("Abrir para editar" + watcher do .docx).
- **Modelos por loja** no banco de documentos da loja:
  - **Contrato Padrão** — modelo base (do sistema / da loja).
  - **Contrato Personalizado** — versão acessória da loja, na mesma base de dados da loja.
  - `Contrato.template_path` passa a apontar para o modelo da loja (não para o global
    `config/contrato_template.docx`).
- **Testemunhas e demais dados hoje hardcoded** (`_TESTEMUNHAS` em `mod_contrato.py`) passam a vir
  da config da loja (já marcado como TODO no código).
- A confirmar no brainstorm: quando a loja tem Padrão **e** Personalizado, como o sistema escolhe
  qual usar (default da loja? escolha por projeto? Personalizado sempre que existir?).
