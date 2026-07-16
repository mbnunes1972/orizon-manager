# Smoke / Verificação — F3: Contrato puxa da loja

> **Status:** PENDENTE de execução no ambiente do usuário (2026-06-21).
> A F3 está mergeada na `main` (merge `4e4ffc9`) com **195 testes unitários verdes** e
> revisão dupla + revisão final por subagentes. Falta apenas o **smoke manual / runtime**
> (API + UI), que não pôde ser rodado na sessão. Este documento existe para que, **se algum
> bug aparecer**, o diagnóstico seja rápido: passos esperados, mapa sintoma→local, inspeção do
> banco e edges conhecidos.

Spec/plano: `docs/superpowers/specs/multitenant/2026-06-21-multitenant-f3-contrato-loja-design.md` e
`docs/superpowers/plans/2026-06-21-multitenant-f3-contrato-loja.md`.

---

## 1. O que a F3 mudou (resumo de 30s)

O contrato deixou de ler dados da loja de **constantes hard-coded** em `mod_contrato.py` e passou
a lê-los da tabela **`lojas`** (a loja do consultor que gera o contrato):

- empresa: `nome` → `[NOME_EMPRESA]`, `cnpj` → `[CNPJ_EMPRESA]`
- número do contrato: `codigo` (3 letras) vira o prefixo `LOJA-AAAA-MM-DD-SEQ`
- contato: `telefone`/`email` (fallback do consultor)
- testemunhas: `testemunha1/2_nome` + `testemunha1/2_cpf`

A cada geração grava-se uma **foto** dos dados usados em `contratos.loja_snapshot_json`.
Loja incompleta **não bloqueia**: avisa e deixa gerar (Decisão 2). Telefone/email/endereço da
loja são **obrigatórios no cadastro** (validação), mas o endereço **não** é renderizado no contrato.

## 2. Pré-condições

- App rodando (`python3 main.py` → `http://127.0.0.1:8765`).
- **A loja-semente (id=1, "INSPIRIUM") tem CPF de testemunha _placeholder_** `xxx.xxx.xxx-xx` /
  `yyy.yyy.yyy-yy` (`database.py:534+`) **e endereço vazio**. Logo, **na 1ª vez o smoke DEVE
  cair no aviso "loja incompleta"** — isso é o comportamento correto, não um bug.
- Usuário operacional de loja (ex.: consultor `mds2026`, `loja_id=1`).

## 3. Smoke manual (UI) — passos e resultado esperado

### A. Gerar contrato com a loja incompleta (fluxo de aprovação)
1. Abrir um projeto com orçamento ativo → **Aprovar Orçamento** → **Gerar Contrato**.
2. Responder ao popup de signatário (cliente ou override).
3. **Esperado:** aparece o diálogo **"Loja incompleta — Dados da loja incompletos: • CPF da
   Testemunha 1 • CPF da Testemunha 2 • CEP • … — Gerar assim? / Cancelar"**.
   - **Cancelar** → não gera, modal de aprovação segue aberto.
   - **Gerar assim** → gera o contrato; empresa/CNPJ saem preenchidos (a loja tem isso), mas os
     CPFs das testemunhas saem em branco/placeholder. Número = `INS-AAAA-MM-DD-SEQ`.

### B. Completar a loja e gerar de novo (o caminho feliz da F3)
1. **Admin (page-07) → Dados da loja** → preencher CPFs reais das 2 testemunhas, telefone,
   e-mail e endereço completo (cep/logradouro/número/bairro/cidade/UF). Salvar.
2. Voltar e **Gerar Contrato** de novo.
3. **Esperado:** **sem** diálogo de aviso; contrato sai com nome/CNPJ/testemunhas reais.

### C. Editar Adendo (fluxo de regeração — `salvarAdendo`)
1. Na tela do contrato → **Editar Adendo** → digitar algo → **Salvar e Regenerar PDF**.
2. **Esperado:** se a loja ainda estiver incompleta, **o mesmo diálogo "Gerar assim?/Cancelar"**
   aparece (este caminho foi corrigido na revisão final). Confirmar regenera; cancelar aborta.

## 4. Verificação por API (sem UI)

Endpoint dos dois fluxos: `/api/projetos/<nome_safe>/contrato`
(`POST` = aprovação/geração; `PATCH` = regeração com adendo).

- **1ª chamada sem confirmação, loja incompleta →** HTTP **400** com
  `{"ok": false, "precisa_confirmar_loja": true, "campos_loja_faltando": [...], "erro": "Dados da loja incompletos."}`.
- **Repetir com `"confirmar_loja_incompleta": true` no corpo →** gera (HTTP 200, `ok: true`).
- **Cadastro do cliente incompleto** continua **bloqueando** (campo `campos_faltando`, sem
  `precisa_confirmar_loja`) — comportamento distinto e intencional.

## 5. Inspeção no banco (SQLite `orizon.db`)

```sql
-- O snapshot e a loja do último contrato gerado
SELECT id, num_contrato, loja_id, substr(loja_snapshot_json, 1, 120) AS snap
FROM contratos ORDER BY id DESC LIMIT 3;
```
Esperado após gerar: `loja_id` preenchido (fixado na 1ª geração), `num_contrato` com o prefixo do
**código da loja**, e `loja_snapshot_json` com o JSON dos dados usados. Editar a loja **depois**
não muda contratos já gerados (a foto é por geração; congela na assinatura pela trava existente).

```sql
-- Estado atual da loja (placeholders pendentes?)
SELECT codigo, telefone, email, cidade, testemunha1_cpf, testemunha2_cpf FROM lojas WHERE id=1;
```

## 6. Mapa de triagem — sintoma → local provável

| Sintoma | Olhar primeiro |
|---|---|
| Diálogo "loja incompleta" **não** aparece quando deveria | front: `gerarContrato` (`static/index.html:8071`) / `salvarAdendo` (`:8244`); backend: guarda `precisa_confirmar_loja` (`main.py:2666`/`:3126`) |
| Diálogo aparece mas **"Gerar assim" não gera** | front re-chama com `confirmar_loja_incompleta:true` (`:8076`/`:8254`); backend deve então **não** retornar 400 |
| Diálogo **re-pergunta o signatário** na 2ª passada | `gerarContrato(confirmarLojaIncompleta, signatarioPre)` — `signatarioPre` deve vir não-`undefined` (`:8076`) |
| Empresa/CNPJ/testemunhas **em branco** no .docx | `loja_dict` chegou vazio → `_loja_dict_para_contrato(db, loja_id)` (`main.py:3679`); ou `_montar_mapping` não leu `ctx["loja"]` (`mod_contrato.py:447`) |
| Número do contrato com **prefixo vazio** `-AAAA-…` | loja **sem `codigo`** → ver §7 (edge aceito); origem em `gerar_num_contrato` (`mod_contrato.py:27`) recebendo código vazio |
| `loja_snapshot_json` **NULL** após gerar | gravação em `main.py:2713`/`:3161` (antes do `db.commit()`); confirmar que a geração chegou ao fim |
| Telefone/e-mail do consultor **sumiram** no contrato | fallback agora vem da loja: `construir_contexto` (`mod_contrato.py:537`, linhas de `consultor_tel`/`consultor_email`) — loja sem esses campos → fica em branco (sem fallback de constante, por design) |
| Contrato antigo (pré-F3) sem snapshot | coluna é nullable; só preenche em geração nova; render usa a loja viva — esperado |

## 7. Edges conhecidos / minors aceitos (não são bugs)

- **Loja sem `codigo` + geração confirmada →** `num_contrato` sai com prefixo vazio
  (`-AAAA-MM-DD-001`) e a sequência por prefixo pode colidir em `001`. Só ocorre se a loja não
  tiver código (a validação avisa "Código da loja"). Mantido leniente por coerência com a
  **Decisão 2** (avisar mas deixar gerar). Se virar problema real, o ponto de correção é
  `gerar_num_contrato` (`mod_contrato.py:27`) — usar um sentinela ou recusar número sem código.
- **Bloco de aviso duplicado** nos 2 sites do `main.py` (`:2662` e `:3122`) — funcional; se for
  mexer, extrair um helper compartilhado (e isso destrava um teste de handler — ver abaixo).
- **Sem testes de handler HTTP** (o app usa `BaseHTTPRequestHandler` cru, que o repo nunca
  testou). Cobertos por unidade: `validar_loja_para_contrato`, `_loja_dict_para_contrato`
  (stub de db), e a migração da coluna — em `tests/test_contrato_loja.py`. **Gap conhecido:**
  o *write* do snapshot e o branch warn-but-allow não têm teste automatizado; a verificação é
  este smoke. Se extrair o helper acima, dá para testá-los.

## 8. Referência rápida — onde está cada peça

- `mod_contrato.py`: `validar_loja_para_contrato` (`:410`), `_montar_mapping` lê `ctx["loja"]`
  (`:447`), `construir_contexto(…, loja=None)` (`:537`), `gerar_num_contrato(…, loja_codigo)` (`:27`).
- `database.py`: coluna `contratos.loja_snapshot_json` (model + `_migrar_colunas`); loja-semente
  e placeholders em `:528-587`.
- `main.py`: helper `_loja_dict_para_contrato` (`:3679`); Site #1 `do_POST` (geração, ~`:2662-2719`);
  Site #2 `do_PATCH` (regeração, ~`:3122-3161`).
- `static/index.html`: `gerarContrato` (`:8019`), `abrirModalAdendo` (`:8204`), `salvarAdendo` (`:8227`).

> Números de linha são aproximados (pós-merge da F3). Em caso de drift, ancore por conteúdo
> (`grep -n "precisa_confirmar_loja\|_loja_dict_para_contrato\|validar_loja_para_contrato"`).
