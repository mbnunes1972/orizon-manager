# Sub-projeto B — Cadastro completo na aprovação

**Data:** 2026-06-17
**Projeto:** Omie_V3 — Dalmóbile / Orizon Soluções
**Escopo:** Cadastro mínimo na criação (nome/e-mail/telefone); gate de cadastro completo ao aprovar o orçamento, com popup "Cadastro Incompleto" que leva ao painel de cadastro; backend como autoridade única da validação.
**Parte de:** Redesenho do ciclo de vida do projeto (A/B/C/D). Este é o **B**. O **A** (etapas + gating) já foi entregue e mergeado.
**Pré-requisito já entregue:** `validar_cliente_para_contrato(cliente)` em `mod_contrato.py` (criado e testado no contexto do A) e o gate no endpoint `POST /api/projetos/<nome>/contrato` que retorna **HTTP 400** com `campos_faltando`.
**Cobre os pontos do usuário:** 3 (indicar cliente), 5 (cadastro mínimo), 12 (popup "Cadastro Incompleto"), 14 (contrato pré-preenchido).

---

## 1. Contexto

Estado atual relevante:

- **Criação de cliente** (`POST /api/clientes`, `main.py:1064`) exige apenas `nome`; `email`/`telefone` são opcionais.
- **Modal de aprovação** (`gerarContrato()` em `static/index.html`) tem campos editáveis de cliente (`apr-nome`, `apr-cpf`, `apr-telefone`, `apr-email`, `apr-end`), faz um `PATCH /api/clientes/<id>` com `{cpf, telefone, email}` antes de gerar, e roda um **pré-check próprio** (`camposFaltando`) que verifica só esses 5 campos.
- **Descompasso:** esse pré-check do frontend diverge de `validar_cliente_para_contrato` (backend), que exige o **endereço estruturado completo** (logradouro, número, bairro, cidade, CEP, UF residenciais; e os `inst_*` quando a instalação difere do residencial). O frontend pode "passar" e o backend rejeitar.
- **Popup já existe:** `mostrarErroComAcao(msg, label, callback)` exibe uma mensagem com botão de ação; hoje é usado com "Abrir Cadastro" → `cliAbrirModal(cliId)`.
- **Painel de cadastro** já possui os campos necessários: residenciais (`cli-logradouro`, `cli-numero`, `cli-bairro`, `cli-cidade`, `cli-cep`, `cli-estado`) e de instalação (`cli-inst-*`, toggle `inst_mesmo`). O `PUT/POST /api/clientes/<id>/editar` persiste todos eles, incluindo `inst_*`.

### Decisões validadas com o usuário
- **Bloqueio total** quando o cadastro está incompleto na aprovação — **sem** override gerencial.
- **Fonte única:** o painel de cadastro é o único lugar para editar dados do cliente; o modal de aprovação **deixa de editar** dados do cliente. `validar_cliente_para_contrato` (backend) é a **única autoridade** sobre "o que falta".

---

## 2. Cadastro mínimo na criação (ponto 5)

- **Backend `POST /api/clientes`** (`main.py:1064`): passar a exigir `nome`, `email` e `telefone`. Se algum faltar (após `.strip()`), retornar `{"ok": False, "erro": "..."}` (HTTP 400) indicando os campos faltantes. CPF e endereço seguem **opcionais** na criação (preenchidos depois, antes da aprovação).
- **Frontend (formulário de novo cliente):** marcar e-mail e telefone como obrigatórios e validar antes do submit, com mensagem clara. Não permitir salvar sem eles.

> Coerência com o gate de aprovação: CPF e endereço **não** são exigidos na criação, mas **são** exigidos na aprovação (via `validar_cliente_para_contrato`). Isso é intencional — o cliente nasce com o mínimo e é completado antes de virar contrato.

---

## 3. Gate de cadastro completo na aprovação (ponto 12)

### 3.1 Backend — já pronto
O endpoint `POST /api/projetos/<nome>/contrato` já chama `validar_cliente_para_contrato(cliente_dict)` e, havendo faltas, retorna:
```json
{ "ok": false,
  "erro": "Cadastro do cliente incompleto — preencha antes de gerar o contrato. Campos faltando: ...",
  "campos_faltando": ["E-mail", "Logradouro (residencial)", ...] }
```
com HTTP 400. **Nenhuma mudança de backend necessária** nesta seção.

### 3.2 Frontend — `gerarContrato()`
1. **Remover os campos editáveis de cliente** do modal de aprovação: `apr-nome`, `apr-cpf`, `apr-telefone`, `apr-email`, `apr-end` (endereço de instalação free-text). Em seu lugar, exibir apenas o **nome do cliente como texto read-only** (contexto). O modal mantém: seleção de orçamento, pagamento (entrada/parcelas/forma via `_capturarPagamento`) e adendo.
2. **Remover o `PATCH /api/clientes/<id>`** que salvava `{cpf, telefone, email}` — o modal não edita mais dados do cliente.
3. **Remover o pré-check `camposFaltando`** do frontend (o que divergia do backend).
4. `gerarContrato()` faz o `POST /api/projetos/<nome>/contrato` direto (com `orcamento_id`, `pagamento_json`, `adendo`). O campo `endereco_instalacao` do request deixa de ser enviado (ou vai vazio) — a instalação vem de `cliente.inst_*`.
5. **Tratar a resposta 400 com `campos_faltando`:** exibir popup **"Cadastro Incompleto"** (via `mostrarErroComAcao`, com título/wording ajustados) listando exatamente os itens de `campos_faltando` retornados pelo backend, com botão **"Abrir Cadastro"** → `cliAbrirModal(projetoAtivo.cliente_id)`. Outros erros (não-400 / sem `campos_faltando`) seguem o tratamento de erro genérico atual.

### 3.3 Efeito colateral controlado
`contrato.endereco_instalacao` (coluna existente) deixará de ser preenchido pelo modal. Como o documento usa `cliente.inst_*` (não essa string), o campo fica vestigial — aceitável. Não remover a coluna agora (fora de escopo).

---

## 4. Contrato pré-preenchido (ponto 14)

Nada novo. Com o gate da Seção 3, o contrato só é gerado quando `validar_cliente_para_contrato` passa — ou seja, com todos os dados do cadastro presentes. O preenchimento do documento (`construir_contexto` + `preencher_contrato`) já foi validado no Sub-projeto A e produz o contrato completo a partir do cadastro.

---

## 5. Testes

1. **Backend (novo):** `POST /api/clientes` rejeita criação sem `email` ou sem `telefone` (HTTP 400, mensagem cita o campo) e aceita quando nome+email+telefone presentes. (Padrão: teste de unidade da lógica de validação, ou teste do handler se viável; o projeto não tem harness HTTP — extrair a checagem mínima numa função testável se necessário.)
2. **Backend (existente):** `validar_cliente_para_contrato` já coberto por `tests/test_contrato.py`.
3. **Frontend:** verificação manual (sem harness JS):
   - Criar cliente sem e-mail/telefone → bloqueado no formulário.
   - Aprovar orçamento com cadastro incompleto → popup "Cadastro Incompleto" listando os campos do backend + botão que abre o cadastro.
   - Completar o cadastro (contato + endereço) → aprovar de novo → contrato gerado e preenchido.

---

## 6. Fora de escopo (outros sub-projetos)

- **C** — "Aprovar Orçamento" concluir Revisão+Aprovação juntas; 1º orçamento concluído por ≥1 XML; renomear/tornar clicável "orçamento aprovado – assinar contrato".
- **D** — Briefing obrigatório após criação do projeto.
- Remoção da coluna vestigial `contrato.endereco_instalacao` e dos campos `apr-*` órfãos no HTML — limpeza opcional futura.

---

## 7. Arquivos afetados (estimativa)

| Arquivo | Mudança |
|---|---|
| `main.py` | `POST /api/clientes` exige nome+email+telefone |
| `static/index.html` | remove campos de cliente + PATCH + pré-check do modal de aprovação; popup "Cadastro Incompleto" tratando `campos_faltando`; formulário de novo cliente exige e-mail/telefone |
| `tests/` | teste da validação mínima de criação de cliente |
