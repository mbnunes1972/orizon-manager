# Auditoria Florence — Sumário Executivo

**Sistema:** Orizon Manager / Dalmóbile — vendas de móveis planejados, multi-loja (tenancy), produção real.
**Data:** 2026-07-03
**Escopo:** Backend Python (`http.server` + SQLAlchemy/SQLite) e frontend SPA (`static/index.html`).
**Método:** 8 auditorias paralelas independentes (arquitetura, domínio financeiro, domínio de contrato/ciclo/integração, segurança, performance, dívida técnica, dependências/testes, frontend), cada uma com evidência `arquivo:linha` e severidade.
**Ótica:** software de **produção que deve ter arquitetura enterprise-grade "gold"**. Toda lacuna abaixo é medida contra esse padrão.

---

## Veredito

> **O núcleo de domínio é forte; a plataforma que o cerca ainda não é "gold".**

O que está **em nível gold** e deve ser preservado:
- **Motor de negociação e cálculo** puro, desacoplado e **bem testado** (golden anchors LELEU, reconciliação de waterfall com asserts numéricos reais). Invariante "a loja recebe exatamente `valor_avista`" garantido.
- **Autorização de tenancy de negócio**: o padrão `_ator_dict → escopo_operacional → _obj_da_loja/_projeto_da_loja` é aplicado com consistência — **nenhum IDOR entre lojas** foi encontrado nas rotas de projeto/cliente/orçamento/contrato/medição. Gestão de usuários tem anti-escalonamento e anti-lockout corretos.
- **Núcleo de contrato/ciclo/árvore** puro e bem testado. Segredo Omie **não vazou** para o histórico do Git.

O que **impede o rótulo "gold"** hoje (temas críticos transversais, detalhados abaixo):
1. Segredos e credenciais padrão expostos no runtime.
2. Autenticação de plataforma fraca (hash sem salt) e rotas administrativas sem sessão.
3. Estado global compartilhado + servidor single-thread → risco de vazamento cross-tenant e travamento sob concorrência.
4. Fronteira de I/O externo sem defesa (XML, upload, retry).
5. Sem rede de engenharia de release (sem CI, sem pin de dependências).

**Conclusão:** o sistema **funciona e o miolo financeiro é confiável**, mas em sua forma atual **não está pronto para operar como multi-usuário/multi-loja exposto** sem endereçar a Onda 1 abaixo. É uma base sólida a um conjunto delimitado de correções de distância do padrão enterprise.

---

## Placar consolidado

| # | Relatório | 🔴 Crítico | 🟠 Alto | 🟡 Médio | 🔵 Baixo | Total |
|---|-----------|:---:|:---:|:---:|:---:|:---:|
| 01 | [Arquitetura](01-arquitetura.md) | 4 | 5 | 4 | 2 | 16 |
| 02 | [Qualidade — Financeiro](02-qualidade-financeiro.md) | 2 | 3 | 5 | 4 | 14 |
| 03 | [Qualidade — Contrato/Ciclo/Integração](03-qualidade-dominio.md) | 2 | 5 | 4 | 6 | 17 |
| 04 | [Segurança](04-seguranca.md) | 4 | 5 | 3 | 2 | 15 |
| 05 | [Performance](05-performance.md) | 3 | 6 | 4 | 2 | 15 |
| 06 | [Dívida Técnica (inventário)](06-divida-tecnica.md) | 2 | ~9 | ~14 | ~13 | ~72 itens |
| 07 | [Dependências & Testes](07-dependencias-testes.md) | 6 | 5 | 5 | 0 | 18 |
| 08 | [Frontend (SPA)](08-frontend.md) | 1 | 4 | 5 | 2 | 13 |
| | **Total (aprox.)** | **~24** | **~42** | **~44** | **~31** | **~120 achados** |

> **Nota de calibração:** o porte atual é pequeno (orizon.db ≈ 1,2 MB, ~20 projetos, tipicamente 1 usuário). Vários achados de performance/concorrência são **latentes** — inofensivos hoje, graves quando o sistema virar multiusuário/multiloja de fato. As severidades refletem o risco **em produção com crescimento**, coerente com o objetivo enterprise.

---

## Temas críticos transversais (convergência entre auditores)

Estes são os pontos onde **múltiplos** relatórios independentes apontaram para a mesma raiz — os de maior prioridade.

### T1 — 🔴 Segredos e credenciais padrão expostos
- `GET /config` retorna `app_key`/`app_secret` da API Omie **sem autenticação** (Seg. A-01, `main.py:287`).
- Super_admin semeado com **`sad2026` / `trocar123`** pela migração (Seg. A-04; Dívida #2; `database.py:636/710`).
- Fallback de senha de gerente **`"1234"`** para autorização financeira (Dívida #1, `main.py:1581`).
- `app_key`/`app_secret` em texto puro em `omie_config.json` (mitigado: gitignored, fora do histórico).
**Ação:** rotacionar o segredo Omie; autenticar `/config`; forçar troca de senha do super_admin no 1º login e remover o fallback "1234"; migrar segredos para cofre/variável de ambiente.

### T2 — 🔴 Autenticação de plataforma fraca e rotas administrativas sem sessão
- Senhas com **SHA-256 puro, sem salt, sem iterações**, comparação não constant-time (Seg. A-03; Arq. A-07; Deps A8; `database.py:13-15,49-53`).
- `POST /config`, `/perfis`, `/perfis/ativo`, `/exportar`, `/carregar` **mutam estado sem checagem de sessão** (Seg. A-02, `main.py:1357-1408`).
- Sem rate limiting no login, cookie sem `Secure`/`SameSite`, sem CSRF.
**Ação:** trocar para hash com sal + custo (bcrypt/argon2/PBKDF2); exigir sessão nas rotas administrativas; endurecer cookie + CSRF + rate limit.

### T3 — 🔴 Estado global compartilhado + servidor single-thread
- `_session` é um **dict global único** compartilhado por todos os usuários (Seg. A-05; Arq. A-01; Perf; `storage.py:151`), e `_REQ_LOJA_ATIVA` é global de request (`main.py:246/266`) → vazamento cross-loja sob concorrência.
- `HTTPServer` **single-thread** (Perf C1, `main.py:4981`): uma requisição lenta (PDF WeasyPrint, chamada Omie) **serializa e congela todos os usuários**.
**Ação (ordem segura):** **primeiro eliminar o estado global** (sessão por-request/por-token, escopo de loja sem global); **só depois** migrar para `ThreadingHTTPServer` + WAL — inverter a ordem introduz race conditions e `database is locked`.

### T4 — 🔴 Fronteira de I/O externo sem defesa
- Parsing de XML (Promob/Omie) via `ElementTree` **sem `defusedxml`** → billion-laughs derruba o servidor single-thread (Dom. #1, `promob_grupos.py:266`; Seg.).
- **Path traversal**: `filename` de multipart e `arq_nome` gravados/servidos sem `basename`/sanitização (Dom. #2, `main.py:171/2394/705`; Seg.).
- **Retry ilusório** na Omie: erro de rede faz `raise` na 1ª tentativa; o `for range(3)` só re-tenta rate-limit (Dom. #4, `mod_omie.py:26-70`).
**Ação:** adotar `defusedxml`; sanitizar todo nome de arquivo; corrigir a política de retry (backoff em erro de rede, com teto).

### T5 — 🔴 Sem rede de engenharia de release
- **Dependências sem pin** (Deps A1); risco concreto de **SQLAlchemy 2.x vs 1.4** — o código usa `DeclarativeBase` (2.x) e o app **não sobe** se o apt resolver 1.4 (Deps A6, `database.py:7`).
- **Sem CI** (Deps B3, `.github/` inexistente): a regra "não commitar sem verde" é puramente manual.
- **`main.py` (4.758 LOC) e `mod_omie.py` sem teste unitário** (Deps B1/B2) — os módulos de maior superfície/risco rodam sem rede.
**Ação:** pin + lockfile com hashes; pipeline de CI rodando `pytest` + `pip-audit`; começar a cobrir roteamento e integração Omie.

---

## Achados críticos por relatório (referência rápida)

**Arquitetura:** monólito `main.py` com `do_POST` de ~2.348 linhas misturando HTTP+regra+ORM (A-02); migrações que engolem exceção com `except Exception: pass` (A-04, schema incompleto silencioso); PK textual mutável `nome_safe` e "FKs" `String` sem `ForeignKey` real (A-08).

**Financeiro:** `total_flex.calcular` retorna `ok:True` com **última parcela negativa** e total errado — o wrapper descarta o `ok` do recálculo interno (F-01, 🔴, `mod_fin/total_flex.py:154-157`); **dinheiro em `float`** em todo o domínio (F-02); `total_flex`/`venda_programada` **sem teste de cálculo** (F-03).

**Domínio (contrato/integração):** XML sem defesa (billion laughs); path traversal no upload; `gerar_excel` com `NameError` latente (`io` não importado, `mod_omie.py:756`) — função morta; retry ilusório; zero teste em `mod_omie`/`promob_grupos`/`mod_proposta`.

**Segurança:** `/config` vaza secret sem auth (A-01); super_admin default (A-04); rotas admin sem sessão (A-02); SHA-256 sem salt (A-03); `_session` global cross-loja (A-05). **Positivo:** sem IDOR entre lojas; secret fora do Git.

**Performance:** servidor single-thread (C1); PDF WeasyPrint inline no handler bloqueia tudo (C2); **zero índices no banco** (A1, full scan em `loja_id`/`criado_por_id`/FKs); N+1 (A3); HTML de 500 KB sem cache/gzip/ETag lido do disco a cada request (A5).

**Dívida técnica:** ~72 itens rastreáveis. **0 TODO/FIXME reais** no código de produção (bom); mas ~11 `except: pass` (observabilidade), ~19 hardcodes (4 segredos/senhas, 5 caminhos de máquina), ~28 `print("[TAG]…")` de debug em handlers HTTP.

**Dependências & testes:** 6 críticos — sem pin, risco SQLAlchemy 2.x/1.4, `main.py`/`mod_omie` sem teste, sem CI. **Positivo:** deps diretas batem 1:1 com imports; núcleo financeiro bem coberto.

**Frontend:** `esc()` **não escapa aspas** → XSS via nome tipo `O'Brien` em `onclick` (F-01, 🔴); perfil do usuário salvo **só em `localStorage`** (viola regra de persistência no backend); 1 arquivo de 9.195 linhas / 345 funções (insustentável); nenhum `fetch` com timeout.

---

## Roteiro de remediação priorizado

### 🌊 Onda 1 — Bloqueadores de produção (fazer antes de expor multiusuário)
1. **Rotacionar o segredo Omie** e autenticar `GET /config` (T1 / Seg. A-01).
2. **Remover credenciais padrão**: forçar troca do super_admin, eliminar fallback `"1234"` (T1).
3. **Proteger rotas administrativas** com sessão (`/config`, `/perfis*`, `/exportar`, `/carregar`) (T2 / Seg. A-02).
4. **Hash de senha com sal + custo** (bcrypt/argon2/PBKDF2) + migração dos hashes existentes (T2).
5. **`defusedxml` + sanitização de nome de arquivo** em todos os pontos de upload/parse/serve (T4).
6. **Corrigir o defeito financeiro F-01** (parcela negativa aceita) e adicionar testes de `total_flex`/`venda_programada` (Fin.).

### 🌊 Onda 2 — Fundação enterprise
7. **Eliminar estado global** (`_session`, `_REQ_LOJA_ATIVA`) → sessão por-request/token (T3) — pré-requisito do item 8.
8. **`ThreadingHTTPServer` + SQLite WAL + índices** (`index=True` em `loja_id`/`criado_por_id`/FKs) e mover PDF/Omie/geração pesada para fora do handler (T3 / Perf).
9. **Pin de dependências + lockfile + CI** rodando `pytest` e `pip-audit`; travar SQLAlchemy 2.x (T5).
10. **Substituir `except Exception: pass`** por log + falha explícita nas migrações e handlers (Arq. A-04 / Dívida).
11. **Migrar dinheiro para `Decimal`** no domínio financeiro (Fin. F-02) e unificar as duas fórmulas de `Cust_Var` (Fin. F-05).

### 🌊 Onda 3 — Sustentabilidade e endurecimento
12. Extrair **camada de serviço/repositório** do `main.py`; quebrar `do_POST` (Arq.).
13. **Cabeçalhos de segurança, CSRF, rate limit, cookie `Secure`/`SameSite`** (Seg.).
14. **Refatorar o frontend** (`esc()` para contexto de atributo/JS; persistir perfil no backend; modularizar o `index.html`) (Front.).
15. Cache/gzip/ETag do HTML; paginação de listagens; retry correto na Omie (Perf/Dom.).
16. Higienizar debug residual (`print`/`console.log`) atrás de logger configurável (Dívida).

---

## Como ler esta pasta
Cada relatório é autocontido, com evidências `arquivo:linha` e um "Placar por severidade" próprio. Veja o [README](README.md) para o índice. Comece por [Segurança](04-seguranca.md) e [Dependências & Testes](07-dependencias-testes.md) (maior densidade de críticos), depois [Arquitetura](01-arquitetura.md) e [Performance](05-performance.md) para o plano estrutural.
