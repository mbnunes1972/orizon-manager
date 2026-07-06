# 06 — Inventário Exaustivo de Dívida Técnica (estilo Florence)

**Projeto:** Orizon Manager / Dalmóbile — backend Python (`main.py` 4.758 linhas + `mod_*.py`), frontend `static/index.html` (~9.195 linhas de JS inline).
**Raiz:** `E:\2026\ESTUDO_DE_IA\orizon-manager`
**Data da auditoria:** 2026-07-03
**Método:** varredura Grep case-insensitive (`.py`, `.html`, `.js`, `.json`, `.md`, `.bat`) + leitura dirigida.
**Escopo excluído:** `.claude\worktrees\` (cópia stale/duplicada), `.git`, `__pycache__`, `.pytest_cache`, `orizon.db*`, `*.bak*`. Testes (`tests/`) e scripts one-shot (`scripts/`) catalogados à parte quando relevantes, mas **não** são código de produção em runtime.

> **Legenda de severidade:** 🔴 Crítico (segredo/senha/caminho de máquina que compromete produção) · 🟠 Alto (dívida que muda comportamento ou trava evolução) · 🟡 Médio (ruído/hardcode gerenciável) · 🔵 Baixo (cosmético) · ℹ️ Info (contexto).

---

## 1. Marcadores (TODO / FIXME / HACK / XXX / WIP / provisório / temporário / legado)

Boa notícia: **o código de produção na raiz está praticamente limpo de `TODO`/`FIXME`/`HACK`**. Os únicos `TODO` reais aparecem em `.claude\worktrees\...\mod_contrato.py` (cópia stale, fora de escopo) — o `mod_contrato.py` **de produção foi refatorado** e já lê nome/CNPJ/testemunhas/código da loja do banco (F2/F3). Restam marcadores de *legado documentado* e comentários "temporário" que descrevem migrações intencionais.

| arquivo:linha | trecho | por que é dívida | sev |
|---|---|---|---|
| `mod_contrato.py:5-9` | "Ainda expõe um pequeno motor de substituição em .docx … Não remover sem migrar a Proposta primeiro" | Motor `.docx`/LibreOffice mantido só para `mod_proposta`. Dívida de migração pendente (aposentar docx). | 🟡 |
| `mod_contrato.py:253` | `# ── Motor de substituição de marcadores em .docx (legado — usado por mod_proposta) ──` | Bloco legado vivo por dependência da Proposta. | 🟡 |
| `mod_contrato.py:817` | `# ── LibreOffice (legado — usado por mod_proposta …) ─` | Idem — caminho LibreOffice sobrevive só pela Proposta. | 🟡 |
| `mod_fin/total_flex.py:169` | `"""Wrapper legado — taxa lida do config, taxa_mensal_pct do request ignorada."""` | Função `calcular_total_flex` legada; parâmetro do request **silenciosamente ignorado** — risco de confusão. | 🟠 |
| `mod_margens.py:5` | "O cálculo legado de margens `calcular_margens` foi removido na faxina — o motor…" | Comentário-lápide de código já removido; ok manter como nota. | ℹ️ |
| `database.py:654-655` | "trocar etapa_codigo 2<->3 … usa código temporário `_swap2`" | "Temporário" = truque de migração idempotente (correto), não dívida. | ℹ️ |
| `static/index.html:1095` | `<!-- PAGE 01 DUMMY (mantido para não quebrar unlockNav) -->` + `<div id="page-01" style="display:none">` | Página fantasma preservada só para não quebrar navegação — acoplamento frágil em `unlockNav`. | 🟠 |

**Contagem categoria 1 (produção):** `TODO/FIXME/HACK/XXX` reais = **0** · legado documentado/lápides = **6** · dummy/fantasma = **1**.

---

## 2. Mocks / Stubs / POCs / NotImplementedError / funções vazias

Nenhum `mock`, `stub`, `fake`, `dummy` (exceto o "PAGE 01 DUMMY" acima), `NotImplementedError` ou `poc` no código de produção. Os `pass` encontrados são **swallow de exceção legítimo** (try/except robustos), não stubs.

| arquivo:linha | trecho | natureza | sev |
|---|---|---|---|
| `auth_routes.py:21` | `...` (ellipsis) | Está **dentro de uma docstring** de instruções — não é código executável. | ℹ️ |
| `database.py:26,614,769` · `main.py:255,1589,1836,4524` · `contrato_editar.py:41` · `mod_contrato.py:100` · `mod_margens.py:23` · `storage.py:197` | `pass` | Todos em `except:`/guarda — swallow de erro. Nenhum é stub. **Alerta transversal:** `except` genérico que engole exceção é dívida de observabilidade. | 🟡 |
| `static/index.html:197` `.placeholder-note` + ~40× `placeholder="…"` | atributos HTML | **Falsos positivos** — são dicas de input, não placeholders de código. | ℹ️ |

**Contagem categoria 2:** stubs/mocks/POCs reais = **0** · `pass` de swallow = **~11** (dívida de observabilidade, não de funcionalidade).

---

## 3. Hardcodes

Aqui está o grosso da dívida. Divididos em **perigosos** (segredos/senhas/caminhos de máquina) vs **legítimos** (constantes de negócio bem nomeadas).

### 3a. Segredos e senhas 🔴/🟠

| arquivo:linha | trecho | por que é dívida | sev |
|---|---|---|---|
| `omie_config.json:2-3` | `"app_key": "7704233295759"`, `"app_secret": "05fc0d8f6098464b4ca7c29a515ac663"` | **Credenciais reais da API Omie em texto puro no disco.** Mitigante: arquivo **está no `.gitignore` e NÃO é versionado** (não vazou para o GitHub). Ainda assim é segredo em claro localmente e será lido por qualquer processo. | 🟠 |
| `database.py:636` | `_SEED_SA_SENHA = "trocar123"` | Senha default do **super_admin de plataforma** (login `sad2026`, linha 635). Comentário manda "TROCAR antes de produção" (632-633) — se não trocarem, é porta dos fundos. | 🔴 |
| `main.py:1581` | `senha_correta = _perfis_cfg…get("senha_gerente", "1234")` | **Fallback hardcoded "1234"** para autorização de gerente (libera impostos/descontos). Se `perfis_config.json` não tiver a chave, qualquer um com "1234" autoriza. | 🔴 |
| `.claude/settings.local.json:40` | `-d '{"login":"pdm2026","senha":"teste123"}'` | Credencial de teste embutida em allow-list de comando. Arquivo de config local (não versionado), mas expõe login/senha de teste. | 🟡 |

### 3b. Caminhos absolutos de máquina 🟠/🟡

| arquivo:linha | trecho | por que é dívida | sev |
|---|---|---|---|
| `criar_estrutura_ep08.bat:9` | `set BASE=E:\2026\ESTUDO_DE_IA\secretaria_orizon` | Script de scaffolding de **outro projeto** (secretaria_orizon) com caminho de máquina fixo. Ruído: não pertence a este repo. | 🟡 |
| `criar_estrutura_ep08.bat:35` | `echo ANTHROPIC_API_KEY=sk-ant-...` | Gera `.env.example` com placeholder de key — inofensivo (é template `.example`), mas mistura projeto alheio. | 🔵 |
| `criar_docs.bat` | (script de scaffolding análogo) | Mesmo tipo de artefato leftover. | 🔵 |
| `_audit_probe.py` (raiz, 45 linhas) | script de probe manual (`print(...)` de sondagem do motor financeiro) | **Arquivo scratch de auditoria no root.** Untracked (não versionado), mas polui a raiz do projeto de produção. Deveria ser removido ou movido para `scripts/`. | 🟡 |
| `.claude/settings.local.json` (dezenas de linhas) | `E:\\2026\\ESTUDO_DE_IA\\…`, `E:\\tmp\\verify_*.py`, `C:\\Users\\mbn19\\…` | Allow-list cheia de caminhos de máquina do dev. É config local por natureza — aceitável, mas denota fluxo de verificação ad-hoc com arquivos em `E:\tmp`. | 🔵 |

### 3c. URLs / hosts / portas 🟡/ℹ️

| arquivo:linha | trecho | avaliação | sev |
|---|---|---|---|
| `mod_omie.py:27` | `url = "https://app.omie.com.br/api/v1" + endpoint` | Endpoint oficial da Omie. **Hardcode legítimo** (constante externa fixa). | ℹ️ |
| `mod_omie.py:234` | `"versao": "3.0"` | Versão da API Omie — legítimo, mas número mágico solto; poderia ser constante nomeada. | 🔵 |
| `mod_omie.py:660` | `time.sleep(2.0)` | Sleep mágico entre chamadas. Número mágico sem nome. | 🔵 |
| `main.py:4980` | `host = os.environ.get("ORIZON_HOST", "127.0.0.1")` + `:8765` | Bind configurável por env var, default seguro e **documentado** (comentário 4978-4979). Boa prática, não dívida. | ℹ️ |
| `auth_routes.py:112` | `Max-Age=28800` (8h de cookie) | Número mágico (28800s) sem constante nomeada. | 🔵 |

### 3d. Números financeiros mágicos 🟠/🟡

| arquivo:linha | trecho | por que é dívida | sev |
|---|---|---|---|
| `mod_fin/aymore.py:25-32` | `_TAXAS_FALLBACK = {1: 0.043891, 2: 0.031261, … 24: 0.025157}` | **24 taxas de juros hardcoded** como fallback quando o JSON de config falta. Se o JSON sumir, o sistema calcula parcelas com taxas fixas de 2026 **silenciosamente** — risco financeiro real. | 🟠 |
| `mod_fin/cartao.py:24-30` | `_FAIXAS_FALLBACK = {1: 2.85, … 21: 13.16}` | Tabela de retenção de cartão hardcoded (21 faixas) como fallback. Mesmo risco: cálculo de cliente com números embutidos se o config sumir. | 🟠 |
| `mod_fin/aymore.py:34` | `CARENCIA_MIN = 15; CARENCIA_MAX = 120` | Limites de carência hardcoded — bem nomeados, mas regra de negócio no código, não no config. | 🟡 |
| `mod_fin/cartao.py:22` | `PARCELAS_MAX = 21` | Constante bem nomeada. Regra de negócio no código. | 🔵 |
| `mod_fin/venda_programada.py:13` | `_PRAZO_LIMITE_DIAS_PADRAO = 395` | Prazo-limite mágico bem nomeado; regra de negócio no código. | 🔵 |
| `mod_fin/total_flex.py:32` | `(1 + taxa) ** (dias / 30)` | O `30` (dias/mês) é convenção mágica embutida na fórmula de juros compostos. | 🔵 |

> **Nota:** `database.py:621-629` — nome/CNPJ/telefone/email/CPFs da loja seed (`INSPIRIUM…`, `19.152.134/0001-56`, CPFs `xxx.xxx.xxx-xx`) são **constantes de bootstrap** documentadas como placeholders corrigíveis no configurador (F2). CPFs já são placeholders `xxx…`/`yyy…` — 🔵. `mod_provisoes.py` e `mod_negociacao.py`: **cálculo puro sem números mágicos** (defaults 0.0, tudo do config) — ℹ️ limpos.

**Contagem categoria 3:** segredos/senhas = **4** (2× 🔴, 1× 🟠, 1× 🟡) · caminhos de máquina = **~5** · números financeiros/mágicos = **~10**.

---

## 4. Debug residual (print / console.log / pdb)

| arquivo | contagem | detalhe | sev |
|---|---|---|---|
| `main.py` | **28×** `print("[TAG] …")` | Prints de depuração **dentro dos handlers HTTP de produção**: `[ORC]`, `[POOL]`, `[OMIE]`, `[CALC]`, `[CICLO]`, `[ORC-AMB]`, `[FECHADO]`, `[CUTOVER]`, `[FAIXAS]`. Ex.: `main.py:1748` imprime prefixo do **app_key da Omie** no stdout. Poluem log de produção e um deles vaza início de credencial. | 🟠 |
| `main.py:4967-4996` | ~6× `print("  …")` | Prints de **startup/banner** (bind, versão, "Acesse:"). Legítimos (CLI feedback). | ℹ️ |
| `database.py:757` | `print("[FAXINA] drop coluna margens:", e)` | Print de migração em erro — deveria ser logging. | 🟡 |
| `static/index.html:3655` | `console.log('[PAG] parcelas='+n+' custo_pct='+_acrescimoFin)` | **Único `console.log` de debug** cru, no fluxo de seleção de parcelas. | 🟡 |
| `static/index.html` | 21× `console.warn(…)` | Handlers de erro em `catch` (`[AUTH]`, `[AYMORE]`, `[VP]`, `[TF]`, auto-save). Aceitáveis como telemetria de erro, mas ruidosos. | 🔵 |
| `mod_fin/cartao.py:14-16`, `mod_fin/aymore.py:17-19` | `print(...)` em **docstring** (exemplos de uso) | Falsos positivos — dentro de `"""`. | ℹ️ |
| `seed.py`, `promob_grupos.py`, `reset_ep07.py`, `scripts/*` | vários `print(...)` | São **CLIs/one-shot** — print é a interface. Não é dívida. | ℹ️ |

Nenhum `debugger`, `import pdb`, `pdb.set_trace`, `breakpoint()` ou `alert(` encontrado.

**Contagem categoria 4:** debug real em produção = **~30** (28 prints no `main.py` + 1 `console.log` + 1 `print` migração).

---

## 5. Código morto / comentado / não usado

| arquivo:linha | trecho | por que é dívida | sev |
|---|---|---|---|
| `static/index.html` — `_negBaseValues` | `let _negBaseValues = []` (l.1854) + **~25 referências** (l.3510, 3550, 3769-3772, 4841, 4850, 4892, 4911, 5009-5066, 5161, 5303, 5392-5596…) | **Variável documentada como SEMPRE VAZIA no EP-07** (CLAUDE.md e comentário l.3502: "_negBaseValues fica vazio no EP-07"). Sobrevivem **ramos inteiros de código legado** que iteram sobre ela (ex.: `renderNegTabela` l.5019, `atualizarSubtotalNeg` l.5066) — código morto no caminho EP-07, mas mesclado com o vivo → **armadilha de manutenção nº 1 do frontend**. | 🟠 |
| `static/index.html:1095-1096` | `PAGE 01 DUMMY` (`<div id="page-01" style="display:none">`) | Página vazia mantida só para satisfazer `unlockNav`. Código morto estrutural. | 🟠 |
| `mod_contrato.py:253-816` | motor `.docx` `_substituir_marcadores`/`_subst_paragrafo` + LibreOffice `_converter_pdf` | **Vivo apenas por `mod_proposta`.** Morto para o Contrato (que virou HTML/WeasyPrint). Não removível sem migrar a Proposta. Bloco grande de dívida de migração. | 🟡 |
| `mod_fin/total_flex.py:166-247` | `calcular_total_flex` (wrapper legado) | Função legada mantida "para compat" com param ignorado. Suspeita de dead-code se nenhum handler novo a chama. | 🟡 |
| `_audit_probe.py` | arquivo inteiro (scratch) | Código de sondagem manual no root; morto para runtime. | 🟡 |
| `reset_ep07.py`, `scripts/reset_para_teste.py`, `scripts/snapshot_*.py`, `scripts/backfill_*.py` | scripts one-shot destrutivos/migração | Não são chamados pelo app; ferramentas pontuais. Ok manter em `scripts/`, mas `reset_ep07.py` está **no root** (deveria estar em `scripts/`). | 🔵 |

**Contagem categoria 5:** dead-code em runtime = **~2** grandes (`_negBaseValues` legado, PAGE 01 DUMMY) · blocos legados vivos-por-dependência = **2** (`mod_contrato` docx, `total_flex` wrapper) · scripts/scratch = **1 no root indevido** (`_audit_probe.py`, `reset_ep07.py`).

---

## Placar

### Total por categoria

| # | Categoria | Itens de produção relevantes |
|---|---|---|
| 1 | Marcadores (TODO/FIXME/legado/dummy) | 7 (0 TODO/FIXME reais; 6 legado documentado; 1 dummy) |
| 2 | Mocks/Stubs/POCs/`pass` | ~11 `pass` de swallow (0 stubs reais) |
| 3 | Hardcodes | ~19 (4 segredos/senhas, 5 caminhos de máquina, 10 números/URLs mágicos) |
| 4 | Debug residual | ~30 (28 `print` no `main.py`, 1 `console.log`, 1 `print` migração) |
| 5 | Código morto/comentado | ~5 (2 dead-code runtime, 2 legado-por-dependência, 1 scratch no root) |
| — | **Total rastreável** | **~72 itens** |

### Total por severidade

| Sev | Qtd | Principais |
|---|---|---|
| 🔴 Crítico | **2** | Senha default super_admin `trocar123`; fallback gerente `"1234"` |
| 🟠 Alto | **~9** | Credenciais Omie em claro; 24 taxas Aymoré fallback; tabela cartão fallback; `_negBaseValues` legado; PAGE 01 DUMMY; 28 prints debug no `main.py`; wrapper total_flex ignora param |
| 🟡 Médio | **~14** | `pass`/except genérico; motor docx legado; `_audit_probe.py`; `.bat` de outro projeto; carência hardcoded; senha teste em settings |
| 🔵 Baixo | **~13** | Números mágicos nomeados (PARCELAS_MAX, 28800, sleep 2.0, dias/30); console.warn; scripts |
| ℹ️ Info | resto | Constantes externas legítimas (URL Omie, bind por env), lápides, docstrings |

---

## Top 10 itens a resolver primeiro

1. 🔴 **`main.py:1581` — fallback de senha de gerente `"1234"`.** Autorização financeira cai para senha trivial se a chave faltar. Remover fallback ou falhar fechado (negar autorização se `senha_gerente` ausente).
2. 🔴 **`database.py:636` — `_SEED_SA_SENHA = "trocar123"` (super_admin `sad2026`).** Forçar troca no 1º login ou gerar senha aleatória no bootstrap; nunca deixar default previsível em produção.
3. 🟠 **`omie_config.json` — app_key/app_secret Omie em texto puro.** Já está gitignored (bom), mas migrar para variável de ambiente / cofre; garantir que nunca seja versionado nem logado.
4. 🟠 **`main.py:1748` (dentro dos 28 prints) — vaza início do app_key no stdout.** Remover; combinar com a limpeza geral dos 28 `print("[TAG]…")` de debug em handlers de produção → trocar por `logging` com nível.
5. 🟠 **`mod_fin/aymore.py:25` + `mod_fin/cartao.py:24` — tabelas de taxas/retenção hardcoded como fallback silencioso.** Se o JSON de config sumir, o sistema cobra o cliente com taxas fixas de 2026 sem avisar. Fazer o fallback **falhar alto** (erro visível) em vez de calcular em silêncio, ou externalizar 100%.
6. 🟠 **`static/index.html` `_negBaseValues` — ~25 refs a variável sempre vazia no EP-07.** Excisar os ramos legados mortos; hoje mesclam-se ao código vivo e são a maior armadilha de manutenção do frontend (confirmado no CLAUDE.md).
7. 🟠 **`static/index.html:1095` PAGE 01 DUMMY** — remover a página fantasma e desacoplar `unlockNav` da existência de `#page-01`.
8. 🟡 **`mod_fin/total_flex.py:169` — wrapper legado que ignora `taxa_mensal_pct` do request silenciosamente.** Verificar se ainda é chamado; se não, remover; se sim, logar/avisar quando o param for ignorado.
9. 🟡 **`_audit_probe.py` (root) + `reset_ep07.py` (root) + `criar_*.bat` (scaffolding de outro projeto).** Limpar a raiz: mover scripts para `scripts/`, apagar o probe e os `.bat` de secretaria_orizon (ruído sem relação com o app).
10. 🟡 **`except: pass` genéricos (~11 locais em `main.py`/`database.py`/`storage.py`/`contrato_editar.py`).** Dívida de observabilidade: erros engolidos em silêncio. Ao menos logar a exceção antes do `pass`.

---

*Fim do inventário. Auditoria READ-ONLY — nenhum arquivo de código foi alterado; única escrita foi este documento.*
