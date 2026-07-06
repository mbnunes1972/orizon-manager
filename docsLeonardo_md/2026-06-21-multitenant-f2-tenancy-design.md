# Multi-tenant — F2: Perfis e CRUD de tenancy (consoles Plataforma/Rede/Loja)

**Data:** 2026-06-21
**Status:** ✅ Implementado e mergeado na `main` (sessões 23–25). Ver DEV_LOG (F2 tenancy).
**Origem:** segunda fase do programa multi-tenant. A F1 (fundação de dados —
`docs/superpowers/specs/2026-06-20-multitenant-f1-fundacao-design.md`) criou as tabelas
`redes`/`lojas`/`parceiro_lojas`, as colunas de tenant e a loja seed, **sem nenhuma
mudança de comportamento**. A F2 expõe a tenancy na UI/API.

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
- **F2 — Perfis e CRUD de tenancy.** ESTE SPEC.
- **F3 — Contrato puxa da loja.** `mod_contrato.py` deixa as constantes e usa a loja.
- **F4 — Isolamento.** Escopo por loja/rede em **todas** as queries operacionais.

---

## Decisões do brainstorm (2026-06-21)

1. **Alcance:** F2 completa (visão do plano), mesmo sem clientes multi-loja ainda.
2. **super_admin:** usuário **dedicado novo** (separado da operação), não promoção do Diretor.
3. **Perfis novos são puramente administrativos:** gerenciam a estrutura, **não operam**
   dentro das lojas (não veem/editam negociação, contratos, medição).
4. **Abrangência do parceiro:** o **Diretor também** pode criar parceiro de abrangência
   `'rede'` (não fica restrito ao admin_rede).
5. **Escopo da F2:** aplicado **apenas nas superfícies administrativas novas**. Listagens
   **operacionais** (clientes/projetos/orçamentos/contratos) seguem **globais** até a F4
   (mantém a F2 de baixo risco — não toca nas queries existentes).
6. **Navegação:** 3 consoles espelhando a hierarquia (Plataforma → Rede → Loja), cada perfil
   aterrissa no seu nível, perfis altos descem por drill-down + breadcrumb.
7. **Editar "Dados da loja":** o **Diretor também** edita a própria loja (incl.
   testemunhas/CPF/código), além de admin_rede (lojas da rede) e super_admin (qualquer loja).

---

## Objetivo da F2

Tornar a tenancy **gerenciável pela interface**, com três níveis administrativos consistentes
e escopo aplicado nas telas novas. Ao fim da F2:

- existem os perfis `super_admin` e `admin_rede`;
- há um super_admin dedicado de bootstrap;
- super_admin gerencia redes, lojas avulsas e admins de rede;
- admin_rede gerencia as lojas e diretores da sua rede;
- diretor gerencia os usuários e edita os dados da sua loja;
- o cadastro de parceiro tem UX de abrangência (loja × rede) com vínculos M:N;
- os **dados da loja seed** (testemunhas/CPF reais) ficam editáveis — destravando a F3.

## Não-objetivos da F2 (explícitos)

- **Sem isolamento operacional.** Nenhuma query de clientes/projetos/orçamentos/contratos
  passa a filtrar por loja. Isso é a F4.
- **`mod_contrato.py` intacto.** Continua nas constantes; a troca da fonte é a F3. A F2 só
  provê a UI para preencher os dados reais da loja.
- **Sem capacidades operacionais nos perfis novos** (desconto, autorizar, aprovar financeiro,
  medição permanecem 0/False para super_admin e admin_rede).

---

## 1. Perfis e capacidades (`perfis.py`)

Dois perfis novos, **puramente administrativos**:

| Perfil | rótulo | escopo no banco | enxerga |
|---|---|---|---|
| `super_admin` | Administrador da Plataforma | `loja_id`=NULL, `rede_id`=NULL | tudo |
| `admin_rede` | Administrador de Rede | `loja_id`=NULL, `rede_id` setado | sua rede |

Capacidades (flags em `perfis.py`; o **escopo concreto** quem aplica é o `main.py`):

| capacidade | super_admin | admin_rede | diretor | gerente_adm_fin | demais |
|---|---|---|---|---|---|
| `gerir_redes` | ✓ todas | — | — | — | — |
| `gerir_lojas` | ✓ todas | ✓ da rede | — | — | — |
| `editar_dados_loja` | ✓ qualquer | ✓ da rede | ✓ **só a própria** | — | — |
| `gerir_usuarios` (já existe) | ✓ todos | ✓ da rede | ✓ da loja | ✓ da loja | — |
| operacionais (desconto/autorizar/aprovar_financeiro/medição) | — | — | (inalterado) | (inalterado) | (inalterado) |

`super_admin` e `admin_rede`: `desconto_max=0`, `ver_parametros=False`, `autorizar=False`,
`aprovar_financeiro=False`, `registrar_medicao=False`, `aprovar_medicao_reprovada=False`.

## 2. Bootstrap do super_admin

- **Migração de dados `tenancy_v2_2026`** (rastreada em `schema_migrations`, idempotente):
  se não existir nenhum usuário com perfil `super_admin`, cria um usuário dedicado
  (sugestão `sad2026`, rótulo "Administrador da Plataforma", `loja_id`/`rede_id` NULL,
  **senha de exemplo → trocar antes de produção**, no mesmo padrão dos seeds).
- **`seed.py`:** em banco novo, cria o super_admin **antes** da loja seed (que segue da F1).
- Idempotência: rodar de novo não duplica o super_admin (guarda "nenhum super_admin existe").

## 3. Navegação — 3 consoles com drill-down (page-07, adaptável ao perfil)

```
┌─ NÍVEL 1 · PLATAFORMA ──────────────────  (super_admin / gerir_redes)
│   • Redes            → CRUD de redes
│   • Lojas avulsas    → CRUD (a loja seed INSPIRIUM vive aqui; rede_id NULL)
│   • Admins de rede   → criar/atribuir usuários admin_rede
│   └─ [entrar numa rede] ↓        [entrar numa loja avulsa] ↓ (pula N2)
│
├─ NÍVEL 2 · REDE ────────────────────────  (admin_rede / gerir_lojas, na sua rede)
│   Breadcrumb: Plataforma › Rede "X"
│   • Dados da rede    → nome/CNPJ
│   • Lojas da rede    → CRUD de lojas
│   • Diretores        → criar/atribuir usuários de loja
│   └─ [entrar numa loja] ↓
│
└─ NÍVEL 3 · LOJA ────────────────────────  (diretor/adm-fin; níveis acima que desceram)
    Breadcrumb: Plataforma › Rede "X" › Loja "Y"
    • Dados da loja    → nome/CNPJ/endereço/telefone/email/testemunhas+CPF/código (alimenta F3)
    • Usuários da loja → o CRUD que JÁ existe hoje (page-07 → Usuários)
    • Parceiros da loja
```

**Aterrissagem por perfil:** super_admin→N1; admin_rede→N2 da sua rede; diretor/adm-fin→N3
da sua loja. Loja avulsa pula o N2 (breadcrumb `Plataforma › Loja Y`).

A página page-07 vira a área administrativa, renderizando o nível conforme o perfil e a
navegação (breadcrumb + drill-down). O CRUD de **Usuários** de hoje passa a ser a aba
"Usuários da loja" do Nível 3 (caminho atual preservado para diretor/adm-fin).

## 4. Endpoints (todos sob `/api/admin/`, com gate + escopo)

- **Redes:** `GET/POST/PATCH /api/admin/redes` — gate `gerir_redes` (só super_admin).
- **Lojas:** `GET/POST/PATCH /api/admin/lojas` — gate `gerir_lojas`/`editar_dados_loja`.
  **Escopo:** admin_rede limitado às lojas da sua `rede_id`; diretor só `PATCH` dos dados da
  **própria** loja. Valida `codigo` = **3 letras, UNIQUE** (sequência do contrato é por código).
- **Usuários:** estende `GET/POST/PATCH /api/admin/usuarios` para atribuir `loja_id`/`rede_id`
  conforme quem cria — diretor herda a própria loja; admin_rede escolhe loja da sua rede ou
  cria outro usuário de loja; super_admin escolhe rede/loja **ou** cria `admin_rede`
  (`rede_id` setado, `loja_id` NULL) / outro `super_admin` — **e escopo na listagem**.
- **Parceiros (abrangência):** estende o cadastro existente — campo `abrangencia`
  (`'loja'`/`'rede'`); se `'loja'`, vincula a 1+ lojas via `parceiro_lojas` com
  `comissao_padrao_pct` **por loja**; se `'rede'`, grava `rede_id` + `comissao_padrao_pct`
  padrão. **Diretor pode criar ambos.** Escopo: só lojas visíveis ao ator.

**Validadores puros novos em `mod_tenancy.py`** (espelha `mod_usuarios.py`):
`validar_rede`, `validar_loja` (código 3-letras único; campos obrigatórios), e
`validar_abrangencia_parceiro` (abrangência ∈ {loja, rede}; coerência rede×vínculos).

## 5. Escopo aplicado APENAS nas superfícies novas

O `WHERE`/escopo entra **só** nos endpoints de tenancy/usuários/parceiros acima. As listagens
operacionais existentes (clientes, projetos, orçamentos, contratos, pool, medição) **não são
tocadas** e seguem globais — isolamento real é a F4. Regressão por construção nas telas
operacionais.

## 6. `mod_contrato.py` — intacto

Continua usando as constantes. A F2 só provê a UI para o usuário (super_admin ou diretor)
preencher os **CPFs reais das testemunhas** e demais dados da loja seed, destravando a F3.

---

## Modelo de dados

Sem tabelas novas (todas vieram na F1). Possíveis ajustes menores, a confirmar no plano:
- Garantir `UNIQUE` lógico de `lojas.codigo` no validador (a coluna já é UNIQUE na F1).
- Nenhuma coluna nova prevista; se algum campo de form faltar em `lojas`, adicionar via
  `_migrar_colunas` (idempotente).

---

## Arquivos afetados (previsão)

- `perfis.py` — perfis `super_admin`/`admin_rede` + capacidades `gerir_redes`/`gerir_lojas`/
  `editar_dados_loja`.
- `database.py` — migração `tenancy_v2_2026` (cria super_admin de bootstrap); `_migrar_colunas`
  se faltar algum campo de loja.
- `mod_tenancy.py` — **novo**, validadores puros (redes, lojas, abrangência de parceiro).
- `main.py` — rotas `/api/admin/redes`, `/api/admin/lojas`; extensão de `/api/admin/usuarios`
  (atribuição + escopo) e do cadastro de parceiros (abrangência + vínculos); helpers de gate
  e de escopo (comparar `rede_id`/`loja_id` do ator com o alvo).
- `seed.py` — cria o super_admin antes da loja seed.
- `static/index.html` — page-07 reorganizada nos 3 níveis com breadcrumb/drill-down; aba
  "Dados da loja"; UX de abrangência no cadastro de parceiro.
- `docs/USUARIOS.md` — documentar os 2 perfis novos e suas capacidades.

---

## Verificação

**pytest (novos):**
- Perfis `super_admin`/`admin_rede` existem com a matriz correta (sem capacidades operacionais).
- `mod_tenancy`: código 3-letras único; abrangência válida; campos obrigatórios.
- Migração `tenancy_v2_2026`: cria exatamente 1 super_admin; idempotente (roda 2× → 1).
- Gate/escopo dos endpoints: admin_rede não enxerga/edita outra rede (403/filtro); diretor
  403 fora da própria loja; consultor 403 em tudo administrativo novo.
- Parceiro: abrangência `'loja'` cria N vínculos; `'rede'` grava `rede_id`; diretor pode `'rede'`.

**API real:** CRUD redes/lojas/usuários com escopo; editar dados da loja (incl. testemunhas/CPF);
parceiro abrangência loja×rede.

**Playwright (servidor real):** os 3 consoles renderizam conforme o perfil; drill-down +
breadcrumb funcionam; editar dados da loja persiste; criar rede→loja→diretor; cadastro de
parceiro com abrangência; 0 erros de console.

**Critério de pronto:** suíte verde (167 atuais + novos) e os 3 níveis navegáveis com escopo
correto; nenhuma regressão nas telas operacionais.

---

## Riscos e mitigação

- **Reorganizar a page-07 em 3 níveis** é a maior superfície de frontend → preservar o caminho
  atual do diretor/adm-fin (Usuários da loja) intacto; testar cada nível por perfil no Playwright.
- **Escopo vazar para o operacional** → congelar a F2 em "escopo só no admin"; qualquer `WHERE`
  em query operacional é F4.
- **Bootstrap duplicado** → guarda por `schema_migrations` + "nenhum super_admin existe".
- **`codigo` de loja colidir** (numeração do contrato) → validador 3-letras + UNIQUE antes de gravar.
- **Perfis novos com poder operacional acidental** → matriz explícita com tudo operacional em
  0/False; teste que afirma isso.
