# Item 1 — Funções editáveis (atribuições/papéis, remuneração, regimes) — Plano

**Goal:** Config › Funções ganha edição completa: `Funcao` recebe **atribuições (papéis)**, **padrão de remuneração**, **regime de trabalho** e **regime de contratação**; `perfil_padrao` (já existe) passa a ser editável numa **modal única**. Baixo risco: cadastro/armazenamento (não liga ainda no escopo/Folha, mas nasce pronto p/ a Folha).

**Decisões:** papéis canônicos = `mod_escopo.PAPEIS` (projeto_executivo/medicao/montagem/assistencia); remuneração ∈ {fixa, variavel, fixa_variavel}; regime_trabalho ∈ {presencial, remoto, misto}; regime_contratacao ∈ {registrado, terceirizacao}. **Dev é Postgres** → migração nos DOIS caminhos (`_add_cols` SQLite + `_migrar_colunas_pg`). Base: `main` (288ef3c).

---

## Task B1 (backend, TDD): campos novos na Função + serialize/aplicar

**Files:** `database.py` (modelo Funcao + migrações), `mod_cadastro.py` (funcao_serialize/aplicar), `tests/test_funcao_campos.py`.

- [ ] **Test:** criar/editar função via `POST /api/funcoes/<id>` com os campos novos e ler de volta pelo `GET /api/funcoes` (confirmar a chave da resposta lendo o handler). Assert: atribuições (lista), remuneracao_padrao, regime_trabalho, regime_contratacao, perfil_padrao.
- [ ] **database.py:** `Funcao` ganha `atribuicoes_json Text`, `remuneracao_padrao String(20)`, `regime_trabalho String(20)`, `regime_contratacao String(20)`. Migração SQLite: estender `_add_cols("funcoes", [...])`. Migração Postgres: acrescentar em `_migrar_colunas_pg()` os `ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS ...`.
- [ ] **mod_cadastro.py:** `funcao_serialize` devolve `atribuicoes` (lista, de `atribuicoes_json`), `remuneracao_padrao`, `regime_trabalho`, `regime_contratacao`. `funcao_aplicar` aplica com validação de enum (valor inválido → ignora/None) e `atribuicoes` filtrada a `PAPEIS` (json.dumps).
- [ ] Suíte verde + regressão (`test_funcoes_seed.py`, `test_perfis_fonte_unica.py`).

## Task B2 (frontend): modal "Editar Função" na aba Config › Funções

**Files:** `static/index.html` (cfgFuncoesRender + nova modal).

- [ ] Modal com: nome, **Atribuições** (checkboxes PE/Medição/Montagem/Assistência), **Perfil de usuário** (select dos perfis = perfil_padrao), **Padrão de remuneração** (select), **Regime de trabalho** (select), **Regime de contratação** (select), status. Salva via `POST /api/funcoes/<id>`.
- [ ] Botão "Editar" por linha na aba Funções; o "Mapa de Funções" (editor solto de perfil) é absorvido pela modal.
- [ ] `node --check` → JS_OK.

## Task B3: verificação + FF
- [ ] Suíte completa verde; verificação manual (editar uma função, reabrir, campos persistem).
- [ ] FF na `main`; anotar no CLAUDE.md que **dev é Postgres** (coluna nova → `_migrar_colunas_pg`).

## Notas
- **Adiado (baixo risco):** papéis→Mapa de Atribuições/escopo; remuneração/regime→Folha/contratos. Campos já prontos p/ a **Folha** (próxima frente).
