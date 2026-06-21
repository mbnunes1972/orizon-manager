# Multi-tenant — F3: Contrato puxa da loja

**Data:** 2026-06-21
**Status:** spec aprovado pelo usuário no brainstorm (aguardando revisão do spec escrito antes do plano)
**Origem:** terceira fase do programa multi-tenant. A F1
(`docs/superpowers/specs/2026-06-20-multitenant-f1-fundacao-design.md`) criou as tabelas e
colunas de tenant; a F2 (`docs/superpowers/specs/2026-06-21-multitenant-f2-tenancy-design.md`)
expôs a tenancy na UI/API e tornou os **dados da loja editáveis** (incl. testemunhas/CPF),
destravando esta fase. A F3 faz `mod_contrato.py` **abandonar as constantes** e gerar o
contrato a partir dos dados da **loja**.

---

## Contexto do programa (lembrete das 4 fases)

```
Plataforma (super_admin)
 ├─ Rede A (admin_rede)
 │   ├─ Loja A1 (diretor) → usuários, clientes, projetos, parceiros, contratos
 │   └─ Loja A2 (diretor)
 ├─ Rede B …
 └─ Loja avulsa X (rede_id = NULL; diretor)
```

- **F1 — Fundação de dados.** CONCLUÍDA (sessão 21). Aditiva.
- **F2 — Perfis e CRUD de tenancy.** CONCLUÍDA (sessão 22). Consoles Plataforma/Rede/Loja.
- **F3 — Contrato puxa da loja.** ESTE SPEC.
- **F4 — Isolamento.** Escopo por loja/rede em **todas** as queries operacionais.

---

## Decisões do brainstorm (2026-06-21)

1. **Snapshot dos dados da loja no contrato.** Cada contrato guarda uma "foto" dos dados da
   loja usados na geração (coluna JSON). Editar a loja depois **não** altera contratos já
   gerados.
2. **Avisar, mas deixar gerar** quando a loja está incompleta. Não bloqueia (diferente do
   cadastro do cliente, que bloqueia): mostra um aviso com os campos faltando e oferece
   "Gerar assim? / Cancelar".
3. **Remover as constantes de vez.** A tabela `lojas` vira a **fonte única**. Sem loja
   vinculada → campos saem em branco + o aviso da decisão 2 aparece. Sem fallback para os
   valores antigos do código.
4. **Refoto a cada geração, congela na assinatura (Abordagem A).** A cada geração o sistema
   relê a loja viva e regrava a foto; como regerar pós-assinatura é travado (trava
   pós-assinatura já existente), a foto **congela naturalmente** na última geração antes da
   assinatura. Resultado: rascunho sempre reflete a loja atual; contrato assinado fica imutável.

---

## Objetivo da F3

Tornar o contrato **independente de constantes hard-coded**, lendo nome/CNPJ/código/telefone/
e-mail e as **testemunhas (nome+CPF)** da loja do consultor que gera o contrato, e registrando
no próprio contrato a foto dos dados usados. Ao fim da F3:

- `mod_contrato.py` não tem mais nenhuma constante de loja;
- a numeração do contrato (`LOJA-AAAA-MM-DD-SEQ`) usa o **código da loja**;
- cada contrato grava `loja_snapshot_json` com os dados usados na última geração;
- gerar com a loja incompleta **avisa e deixa seguir** (confirmação no front);
- nenhuma regressão nas telas/queries operacionais (isolamento real é a F4).

## Não-objetivos da F3 (explícitos)

- **Sem isolamento operacional.** A loja usada é a do **consultor** (`usuario.loja_id`).
  Nenhuma query de clientes/projetos/orçamentos/contratos passa a filtrar por loja — isso é a F4.
- **Sem novos marcadores no modelo.** O endereço da loja é **obrigatório no cadastro**
  (validação — ver seção 3), mas **não** é renderizado no contrato: o
  `modelo_contrato_mapeado.docx` não tem marcadores de endereço de loja, e criá-los fica fora
  do escopo da F3. Telefone/e-mail também são obrigatórios no cadastro (e seguem servindo de
  fallback do consultor no documento).
- **Sem fallback para as constantes antigas** (decisão 3). Loja ausente → campos em branco + aviso.

---

## 1. Origem e aposentadoria das constantes

Constantes de `mod_contrato.py` a **remover** e a coluna correspondente em `lojas`:

| Constante (hoje) | Marcador(es) no modelo | Coluna em `lojas` |
|---|---|---|
| `_NOME_EMPRESA` | `NOME_EMPRESA` | `nome` |
| `_CNPJ_EMPRESA` | `CNPJ_EMPRESA` | `cnpj` |
| `_CODIGO_LOJA` ("INS") | prefixo do `num_contrato` | `codigo` |
| `_TELEFONE_LOJA` | fallback `CONSULTOR_TELEFONE` | `telefone` |
| `_EMAIL_LOJA` | fallback e-mail do consultor | `email` |
| `_TESTEMUNHAS` (2× nome+CPF) | `TESTEMUNHA_1/2_NOME`, `TESTEMUNHA_1/2_DOC`, `NOME_TESTEMUNHA_*`, `CPF_TESTEMUNHA_*` | `testemunha1_nome`/`_cpf`, `testemunha2_nome`/`_cpf` |

`_TRACO` (preenchimento de parcelas vazias) **não** é dado de loja — permanece.

## 2. Modelo de dados (`database.py`)

- Coluna nova `Contrato.loja_snapshot_json` (TEXT, nullable), adicionada via `_migrar_colunas`
  (idempotente, mesmo padrão das migrações de coluna existentes).
- Nenhuma outra mudança de schema — `lojas` já tem todos os campos (F1/F2); `contratos.loja_id`
  já existe (F1, backfill para a loja seed).

## 3. `mod_contrato.py` — puro, recebe a loja por dict

O módulo **continua sem I/O de banco**. Mudanças:

- **Remover** as constantes da seção 1.
- `construir_contexto(cliente, usuario, forma_pagamento_json, loja)` — novo parâmetro `loja`
  (dict plano). O fallback de telefone/e-mail do consultor passa a usar `loja["telefone"]`/
  `loja["email"]` no lugar das constantes. O `ctx` carrega `loja` para o mapping.
- `_montar_mapping(ctx, pag)` — os marcadores `NOME_EMPRESA`, `CNPJ_EMPRESA` e todos os de
  testemunha passam a ler de `ctx["loja"]` (com `""` quando ausente).
- `gerar_num_contrato(existing_nums, loja_codigo, data=None)` — `loja_codigo` vira **parâmetro
  obrigatório** (remove o default `_CODIGO_LOJA`). A sequência contínua por código não muda.
  Código vazio (loja sem `codigo`) gera prefixo vazio — caso coberto pelo aviso da decisão 2.
- **Novo validador puro** `validar_loja_para_contrato(loja) -> list[str]`:
  - Obrigatórios: `nome`, `cnpj`, `codigo`, `telefone`, `email`,
    `testemunha1_nome`, `testemunha1_cpf`, `testemunha2_nome`, `testemunha2_cpf`,
    e o **endereço**: `cep`, `logradouro`, `numero`, `bairro`, `cidade`, `estado`
    (`complemento` é opcional, espelhando a regra do cadastro do cliente).
  - **CPF placeholder** conta como faltando (regex de dígitos não-numéricos do tipo
    `xxx.xxx.xxx-xx` / `yyy…`; um CPF sem dígitos reais é "faltando").
  - Lista vazia → loja completa.

## 4. `main.py` — I/O, snapshot e aviso

Dois pontos de geração de contrato (hoje em ~2670 e ~3112) recebem o mesmo tratamento, via
helper compartilhado para não duplicar lógica:

- **Helper** `_loja_dict_para_contrato(db, loja_id) -> dict | None` — carrega a `Loja` e devolve
  um dict plano com os campos da seção 1.
- **Resolver a loja:** `loja_id = contrato.loja_id or usuario["loja_id"]`; grava
  `contrato.loja_id` se ainda estiver nulo (fixa a loja do contrato na 1ª geração).
- **Validar + aviso (decisão 2):** chamar `validar_loja_para_contrato(loja_dict)`. Se houver
  faltas **e** a requisição **não** trouxer `confirmar_loja_incompleta: true`, responder
  **sem gerar**:
  `{ "ok": false, "precisa_confirmar_loja": true, "campos_loja_faltando": [...] }`.
  Com `confirmar_loja_incompleta: true`, segue a geração normalmente.
- **Refoto (decisão 4 / Abordagem A):** `contrato.loja_snapshot_json = json.dumps(loja_dict)` a
  cada geração. A renderização usa o `loja_dict` vivo; o snapshot fica como registro/auditoria
  do que foi usado naquele contrato.
- **Passagem:** `construir_contexto(cliente_dict, usuario_ctx, pag_json, loja_dict)` e
  `gerar_num_contrato(_existing, loja_dict["codigo"])`.

Sem loja resolvível (`loja_id` nulo, ex.: ator sem loja) → `loja_dict` vazio: o validador acusa
tudo faltando, cai no fluxo de confirmação (decisão 2/3), e se confirmado gera com campos em branco.

## 5. Front (`static/index.html`)

Sem tela nova (a edição de "Dados da loja" é da F2). O fluxo de geração passa a tratar a
resposta `precisa_confirmar_loja`:

- recebeu `precisa_confirmar_loja: true` → diálogo "Loja incompleta — campos: …. Gerar assim?"
  com **[Gerar assim] / [Cancelar]**;
- "Gerar assim" → repete a mesma chamada com `confirmar_loja_incompleta: true`;
- "Cancelar" → aborta, sem gerar.

---

## Arquivos afetados (previsão)

- `mod_contrato.py` — remove as constantes de loja; `loja` em `construir_contexto`/mapping;
  `gerar_num_contrato(..., loja_codigo)`; novo `validar_loja_para_contrato`.
- `database.py` — coluna `Contrato.loja_snapshot_json` via `_migrar_colunas`.
- `main.py` — helper `_loja_dict_para_contrato`; resolução de loja + snapshot + validação/aviso
  nos 2 pontos de geração; passagem da loja para `construir_contexto`/`gerar_num_contrato`.
- `static/index.html` — confirmação `precisa_confirmar_loja` no fluxo de geração.
- `DEV_LOG.md` — registrar a sessão da F3.

---

## Verificação

**pytest (novos/puros):**
- `validar_loja_para_contrato`: loja completa → `[]`; CPF placeholder (`xxx…`) conta como
  faltando; faltam nome/cnpj/codigo/telefone/email/endereço/testemunhas conforme o caso
  (`complemento` opcional não acusa).
- `gerar_num_contrato`: usa o código da loja no prefixo; sequência contínua por código.
- `construir_contexto`: injeta nome/CNPJ/testemunhas da loja nos marcadores; fallback de
  telefone/e-mail do consultor usa a loja.
- `mod_contrato` sem nenhuma constante de loja (garante a remoção).

**Migração:** `loja_snapshot_json` criada de forma idempotente (roda 2× → 1 coluna).

**API real:** gerar contrato grava `loja_snapshot_json`; loja incompleta → resposta
`precisa_confirmar_loja` (não gera); com `confirmar_loja_incompleta` → gera; `contrato.loja_id`
fixado na 1ª geração.

**Playwright (servidor real):** gerar contrato com a loja seed incompleta → diálogo "Gerar
assim?"; preencher CPFs das testemunhas na tela "Dados da loja" e gerar → sai sem aviso e com os
dados reais; 0 erros de console.

**Critério de pronto:** suíte verde (167 atuais + novos); contrato renderiza dados da loja;
nenhuma constante de loja em `mod_contrato.py`; nenhuma regressão operacional.

---

## Riscos e mitigação

- **Dois pontos de geração divergirem** → centralizar resolução de loja + snapshot + validação
  num helper único; os dois call sites chamam o mesmo helper.
- **Contrato antigo sem `loja_snapshot_json`** → coluna nullable; só é preenchida em geração
  nova; nenhuma leitura de volta obrigatória (render usa a loja viva).
- **Número de contrato com código vazio** (loja sem `codigo`) → o validador acusa `codigo`
  faltando e o aviso aparece; gerar mesmo assim é escolha explícita do usuário (decisão 2).
- **Vazar escopo para o operacional** → a F3 só lê a loja do consultor para preencher o
  documento; nenhuma query operacional ganha `WHERE loja_id` (isso é a F4).
- **Quebrar a pureza de `mod_contrato`** → o módulo continua recebendo dicts; todo o I/O
  (carregar `Loja`, snapshot) fica no `main.py`.
