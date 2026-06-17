# Módulo de Contratos — SPEC

**Status:** `[IMPLEMENTADO]`

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

- **Partes:** dados da loja (CONTRATADA, INSPIRIUM — fixa no modelo) + dados do cliente (CONTRATANTE)
- **Objeto:** lista de ambientes com valores
- **Valor total:** conforme orçamento aprovado
- **Forma de pagamento:** conforme modalidade selecionada (normalizada a partir do JSON de pagamento)
- **Cronograma de pagamento:** entrada + parcelas
- **Prazo de entrega:** `[VALIDAR]` — definir prazo padrão por tipo de produto
- **Condições gerais:** cláusulas padrão do modelo `[VALIDAR]`

---

## Geração do contrato `[IMPLEMENTADO]`

A geração é feita por **`mod_contrato.preencher_contrato(contrato_id, ctx)`**, que faz o **preenchimento direto com `python-docx`** sobre o arquivo **`modelo_contrato_final.docx`** (raiz do projeto). **Não** há template Jinja2 nem documento pré-processado por variáveis — o código abre o modelo final e escreve nas tabelas/parágrafos de capa e assinatura.

**Estrutura da capa — 4 tabelas preenchidas pelo código:**
1. Identificação do cliente (nome, CPF/CNPJ, e-mail, telefone…)
2. Endereço residencial
3. Endereço de instalação
4. Forma de pagamento (modalidade, entrada, parcelas)

Além das tabelas, o código preenche os **parágrafos de assinatura** (ver seção Assinatura) e a data.

**Construção do contexto:** `construir_contexto(cliente, usuario, forma_pagamento_json)` monta o `ctx` a partir dos dados do cliente, do usuário (consultor) e do JSON de pagamento. O helper `_parse_pagamento` normaliza o JSON da forma de pagamento. Os helpers `_set_cell` / `_set_para` aceitam um `rotulo` opcional que adiciona a tag de nomenclatura (ver abaixo).

**Conversão para PDF:** após o preenchimento, o **LibreOffice** converte o `.docx` em PDF. Se o LibreOffice não estiver disponível, o código faz **fallback gracioso** para o próprio `.docx` (exceção `LibreOfficeIndisponivel`, capturada no endpoint), salvando o `.docx` e avançando o fluxo mesmo sem PDF.

### Formatação do documento

- **"CPF" → "CPF/CNPJ":** o helper `_relabel_cpf_cnpj(doc)` varre o documento (parágrafos + células de tabela) e exibe todo "CPF" como "CPF/CNPJ", sem duplicar onde já está "CPF/CNPJ".
- **Tags de nomenclatura:** cada campo editável preenchido pelo código recebe uma "tag" — um **rótulo cinza pequeno (~7pt) acima do valor** (ex.: Nome, CPF/CNPJ, CEP, Logradouro, Número, Bairro, Cidade, Estado/UF, Telefone, E-mail, Modalidade, Entrada, Data). Implementado via o parâmetro `rotulo` de `_set_cell` / `_set_para`.

---

## Assinatura `[IMPLEMENTADO]`

### Signatários no documento

- **1º signatário = INSPIRIUM** (CONTRATADA) — fixo no modelo, **não é tocado** pelo código.
- **2º signatário = o CLIENTE** (CONTRATANTE) — preenchido com **nome + CPF/CNPJ** vindos do `ctx`.
- O **consultor NUNCA** aparece como signatário; consta apenas no cabeçalho "Consultor:" no topo do documento.
- **Duas testemunhas provisórias:** **Jaime Perinazzo** e **Felipe Guizalberte** (constantes hardcoded em `mod_contrato.py`). `[TODO]` — virão do painel de configuração de loja.

### Signatário diferente do cliente cadastrado (`signatario_override`)

O `POST /api/projetos/<nome>/contrato` aceita um dict opcional **`signatario_override`** que **substitui os dados do cadastro apenas para aquele contrato** (usado quando o signatário não é o cliente cadastrado). Quando presente (e com `nome` preenchido), o override é mesclado sobre `cliente_dict` antes de montar o contexto e de validar; sem ele, vale o cadastro. No frontend, ao gerar o contrato, pergunta-se "o signatário é o próprio cliente cadastrado?"; se não, abre-se um modal com todos os dados do contrato, que viram o `signatario_override` no corpo do POST.

### Assinatura digital

A assinatura digital registra um **`ContratoAssinatura`** por parte (loja / cliente) com **hash SHA-256**.

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

- O modelo único utilizado é **`modelo_contrato_final.docx`**, na **raiz do projeto** (não em `templates/contratos/`).
- O preenchimento é feito por código (`python-docx`) escrevendo nas tabelas/parágrafos do modelo final — **não** há campos de template Jinja2.
- `[VALIDAR]` — quais outros modelos (Folha de Capa, Termo de Venda Programada, Projeto Executivo) devem existir além do contrato de venda.

---

## User Stories

**US-CON-001** — Como gerente, quero gerar automaticamente o contrato após a aprovação do orçamento (com cadastro completo e orçamento com ambientes).

**US-CON-002** — Como gerente, quero revisar e aprovar o contrato antes de enviá-lo ao cliente.

**US-CON-003** — Como consultor, quero registrar a assinatura digital (loja e cliente) no sistema.

**US-CON-004** — Como qualquer usuário, quero consultar o histórico de contratos de um projeto.

**US-CON-005** — Como consultor, quero gerar o contrato para um signatário diferente do cliente cadastrado, informando os dados só para aquele contrato (`signatario_override`).
