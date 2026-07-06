# Bloqueio dos Campos de Impostos (cadeado + liberação por senha) — Design

**Data:** 2026-06-23
**Status:** Em revisão (design)
**Branch:** `feat/cutover-negociacao` (continuação). **Rollback:** tag `pre-refator-negociacao`.

## 1. Problema / Objetivo

Os campos de imposto da tela — **base tributária** (`-r-base-trib`) e **provisão de impostos**
(`-r-impostos`), nos painéis de pagamento `ay/cc/vp/tf` — ficam visíveis ao consultor (e, numa
apresentação, ao cliente). O usuário quer que esses campos fiquem **ocultos por padrão (com um
cadeado)** e só sejam **revelados mediante senha de um Diretor ou Gerente Administrativo-Financeiro**.
O sistema continua **calculando** os valores normalmente — apenas a exibição é mascarada.

### Modelo de ameaça (honesto)
É um **bloqueio de apresentação** (esconder da vista na tela), **não** uma barreira criptográfica:
os valores são calculados no frontend e permanecem no cliente (inspecionáveis tecnicamente). Para
o caso de uso "para apresentação" isso atende. Sigilo real (não enviar ao frontend sem
autorização) seria outro escopo, futuro.

### Não-escopo (tratamento futuro, conforme o usuário)
- Persistir a liberação por sessão/tempo. Nesta fase a liberação vale **só na visualização atual**
  (re-bloqueia ao recarregar / trocar de orçamento). Sem estado persistido.

### Decisões confirmadas
- **Campos mascarados:** `-r-base-trib` **e** `-r-impostos` dos 4 painéis (ay/cc/vp/tf), na tela de
  negociação **e** na tela do projeto fechado (mesmos IDs).
- **Quem libera:** capacidade **`aprovar_financeiro`** (têm: `diretor` e `gerente_adm_fin`;
  `gerente_vendas` **não** tem — daí não usar `autorizar`).
- **Modal dedicado** novo (`modal-liberar-impostos`), não reaproveitar o `modal-autorizacao`
  (acoplado a desconto).
- **Re-bloquear manual:** clicar no rótulo/cadeado re-oculta na hora.

---

## 2. §1 — Estado e renderização (frontend)

- Variável global **`_impostosLiberados = false`** (não persistida).
- Cache **`_impostosValores = {}`** — por prefixo: `{ base: <number>, imp: <number> }`.
- **`_atualizarImpostos(prefixo, valorBase)`** (já existe): continua calculando
  `imp = valorBase × carga%`, **grava** `_impostosValores[prefixo] = {base: valorBase, imp}`, e
  chama **`_renderImpostosLock()`** em vez de escrever os valores direto.
- **`_renderImpostosLock()`**: para cada prefixo com valores em cache, escreve nos elementos
  `-r-base-trib` / `-r-impostos`:
  - se `_impostosLiberados` → `'R$ ' + fmt(valor)`;
  - senão → um cadeado clicável `🔒` (com `title="Liberar com senha de diretor/gerente adm-fin"`,
    `cursor:pointer`, `onclick=abrirModalLiberarImpostos()`).

## 3. §2 — Modal de liberação

- **`modal-liberar-impostos`** (HTML novo, espelha o visual do `modal-autorizacao`): título
  "Liberar impostos", campos **login** + **senha** do autorizador, botões Cancelar/Confirmar,
  área de erro.
- **`abrirModalLiberarImpostos()`** — abre o modal e foca o login.
- **`confirmarLiberarImpostos()`** — lê login/senha → `POST /api/auth/liberar_impostos`. Em
  sucesso: `_impostosLiberados = true; _renderImpostosLock(); fecharModalLiberarImpostos(); showToast('Impostos liberados por <nome>')`.
  Em erro: mostra a mensagem no modal (sem revelar).

## 4. §3 — Re-bloquear

- O rótulo da seção de impostos vira um toggle: quando liberado, mostra "Impostos 🔓 (clique para
  ocultar)"; clicar → `_impostosLiberados = false; _renderImpostosLock()`. Quando bloqueado, os
  próprios cadeados nos campos abrem o modal.

## 5. §4 — Backend

**`POST /api/auth/liberar_impostos`** — espelha `/api/auth/autorizar_desconto`, mas:
- Recebe `{ login_autorizador, senha_autorizador }`.
- Autentica as credenciais (mesmo mecanismo do `autorizar_desconto`: valida usuário+senha na loja).
- Checa **`perfis.pode(autorizador.nivel, "aprovar_financeiro")`** (NÃO `autorizar`).
- Sucesso → `{ ok: True, autorizador: { nome } }`. Falha (credencial inválida ou sem capacidade)
  → `{ ok: False, erro: <msg> }` com código apropriado (401/403).
- (Opcional, se já houver padrão) registrar a liberação em log gerencial. Manter simples; não
  inventar tabela nova.

## 6. §5 — Tela do projeto fechado

`_renderImpostosLock()` opera sobre os IDs `-r-base-trib`/`-r-impostos` onde existirem. Na
implementação, **verificar** se a tela do projeto fechado usa esses mesmos IDs (ou os mesmos
painéis de pagamento). Se usar, está coberto automaticamente; se usar outros IDs, aplicar o mesmo
`_renderImpostosLock` a eles (lista de IDs parametrizável).

## 7. §6 — Testes

- **Backend E2E (`tests/`):** `/api/auth/liberar_impostos` — diretor → ok; gerente_adm_fin → ok;
  gerente_vendas → 403 (tem `autorizar` mas não `aprovar_financeiro`); senha errada → 401;
  login inexistente → 401.
- **Frontend (manual, sem harness JS):** campos nascem com 🔒; clicar → modal; senha de diretor →
  revela base+provisão; clicar no rótulo 🔓 → re-oculta; recarregar a página → volta a 🔒.

## 8. Arquivos afetados

- `main.py` — novo endpoint `POST /api/auth/liberar_impostos` (espelha `autorizar_desconto`,
  checa `aprovar_financeiro`).
- `static/index.html` — `_impostosLiberados`/`_impostosValores`/`_renderImpostosLock`;
  `_atualizarImpostos` passa a cachear e delegar ao render; modal `modal-liberar-impostos` +
  `abrirModalLiberarImpostos`/`confirmarLiberarImpostos`/`fecharModalLiberarImpostos`; rótulo de
  re-bloqueio.
- `tests/` — E2E do endpoint de liberação.
- docs — esta spec.
