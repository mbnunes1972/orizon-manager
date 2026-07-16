# Navegação consistente: Painel Admin uniforme + Painel Orizon + seletor de empresa — Design

**Data:** 2026-07-16
**Status:** aprovado (brainstorming) — pré-plano
**Base:** `main` (inclui god-mode do super_admin, Sessão 80)

## Problema

A navegação das telas de configuração não é consistente entre perfis. O **Painel Admin** é um
**drill-down** (Plataforma → Rede → Loja → Projeto) para o `super_admin`, mas um conjunto **plano de
4 abas** para o usuário de loja (`master`). Resultado: a mesma "tela de Admin" oferece funções
diferentes conforme o perfil, e o `super_admin` não vê as abas operacionais de administração de uma
empresa. O usuário quer que **as telas de configuração tenham as mesmas abas para todos os perfis** — o
perfil apenas **libera ou tranca** cada aba, sem mudar o conjunto.

Além disso, a administração **do sistema** (criar redes/lojas, gestores da plataforma) está hoje
embutida no Painel Admin do `super_admin`, misturando dois níveis: administrar **uma empresa** (loja) e
administrar **o sistema** (o conjunto de redes/lojas).

## Princípios (do usuário)

1. **Mesmas abas para todos os perfis.** Uma tela de config tem o mesmo conjunto de abas em qualquer
   perfil; cada aba pode estar **trancada** (perfil sem permissão) ou **liberada**. O perfil define a
   *fronteira de uso*, não o *layout*.
2. **A unidade operacional é a loja (empresa).** `Config` e `Admin` têm **caráter de loja** — operam
   sobre **uma empresa selecionada**.
3. **Camadas distintas de administração:**
   - **super_admin = técnico/sistema.** Gere recursos do sistema (redes, lojas, gestores).
   - **gestor de rede (`admin_rede`) = econômico/negócios.** Precisa de visão sistêmica consolidada com
     particionamento (grupo ↔ unidade). **Isto é um dashboard analítico — frente FUTURA, fora deste
     spec.** Os dois papéis **não são análogos**; não se atende `admin_rede` com um "Painel Orizon
     escopado".

## Arquitetura — três telas de configuração

Todas "planas" (barra de abas no topo, sem drill-down):

| Tela | Item na sidebar | Quem vê | Escopo | Abas |
|------|-----------------|---------|--------|------|
| **Config** | `nav-cfg` (existe) | todos (perfil tranca/libera) | empresa selecionada | Provisões, Comissão de Vendas, Cronograma, Funções, Documentos |
| **Painel Admin** | `nav-07` (existe) | todos (perfil tranca/libera) | empresa selecionada | **Dados da empresa**, **Usuários**, **Perfis de Usuário**, **Módulos** |
| **Painel Orizon** 🆕 | `nav-orizon` (novo) | só `super_admin` (cap. `gerir_redes`, exclusiva) | o sistema | Redes, Lojas, Gestores gerais |

### Componente compartilhado — Seletor de empresa ("terminal de acesso")

- Aparece **no topo do Painel Admin e do Config** (mesmo componente/estado).
- Seleciona uma **empresa (loja)**, com as lojas **agrupadas/rotuladas por rede (grupo)** — grupo é só
  rótulo/agrupamento visual, o escopo efetivo é a **loja**.
- Fonte: `super_admin` → todas as lojas; `admin_rede` → lojas da sua rede; usuário de loja → sua(s)
  loja(s). **Uma loja só → aparece fixa (rótulo), sem dropdown.**
- Ao trocar, arma o **`X-Loja-Ativa`** (seta `_lojaAtiva` no front — o interceptor de fetch já existente
  envia o header). **Reaprovado do god-mode (Sessão 80):** `_loja_admin_alvo`/`resolver_loja_ativa(is_super)`
  já resolvem o escopo por esse header, então Admin e Config passam a funcionar para o `super_admin` sem
  novos caminhos de backend, só com o seletor alimentando o header.
- Persistência: `_lojaAtiva` já persiste em `localStorage('loja_ativa')` no fluxo operacional; o seletor
  reusa a mesma chave para manter a empresa entre telas.

### Painel Admin (deixa de ser drill-down)

- `adminCarregarConsole` **não** decide mais nível por papel; sempre renderiza o **plano de 4 abas** da
  empresa selecionada (o corpo de hoje `adminRenderLoja`, generalizado). Os níveis Plataforma/Rede do
  `_adminNav` saem do Admin (vão para o Painel Orizon); o nível Projeto (`adminEntrarProjeto`) e o breadcrumb
  do drill-down são removidos do Admin.
- **Renomeações de legenda:** `Dados da loja` → **Dados da empresa**; `Usuários da loja` → **Usuários**.
  `Perfis de Usuário` e `Módulos` mantêm o nome.
- Conteúdo por aba (inalterado no backend, já existe):
  - **Dados da empresa** — edita os dados operacionais da loja selecionada (`adminLojaCarregarDados`).
  - **Usuários** — CRUD de contas de login da empresa (`/api/admin/usuarios`).
  - **Perfis de Usuário** — matriz/CRUD de perfis da empresa (`/api/admin/perfis*`, já escopados pela
    loja ativa via `_loja_admin_alvo` desde a Sessão 80).
  - **Módulos** — módulos de domínio ativos na empresa (`/api/admin/lojas/<id>/modulos`).

### Painel Orizon 🆕 (administração do sistema — `super_admin`)

- Novo item na sidebar (`nav-orizon`), **oculto** salvo para quem tem `gerir_redes` — capacidade
  **exclusiva do `super_admin`**. O `admin_rede` **não** vê o Painel Orizon (papel de negócios; sua tela
  é o dashboard consolidado, frente futura), embora `gerir_lojas` (que o `admin_rede` também possui)
  ainda gate os endpoints de loja no backend.
- Absorve o que hoje é o drill-down de plataforma do Admin (`adminRenderPlataforma` + `adminRenderRede`):
  - **Redes** — listar/criar/editar (`/api/admin/redes`).
  - **Lojas** — listar/criar/editar, avulsas e por rede (`/api/admin/lojas`).
  - **Gestores gerais** — contas `super_admin`/`admin_rede` (o card "Gestores gerais" atual).
- **Não** faz seleção de ambiente (não arma `X-Loja-Ativa`); é gestão do conjunto.
- **Sem** o card "Credenciais e Tokens (Omie)** — essa remoção é da Frente 2 (Omie), tratada à parte; se a
  Frente 2 vier antes, o card nem migra; se vier depois, migra e é removido lá. Este spec **não** recria
  o painel de chaves do Omie.

### Abas trancadas + step-up (consistência plena)

- Em **Admin** e **Config**, toda aba aparece para todo perfil. Uma aba cuja capacidade o perfil não tem
  é renderizada com **cadeado**; ao clicar, dispara **step-up de senha** (mecanismo da Sessão 62:
  `POST /api/auth/step-up`, grant em memória TTL 30 min; o interceptor de fetch já trata `403
  precisa_stepup`). Concedido o step-up, a aba abre.
- **Mapa aba → capacidade** (fonte única em `perfis.py`, exposto no `/api/auth/me`):
  - Admin: Dados da empresa → `editar_dados_loja`; Usuários → `gerir_usuarios`; Perfis de Usuário →
    `gerir_perfis`; Módulos → `editar_dados_loja`.
  - Config: Provisões/Comissão/Cronograma → `ver_parametros`; Funções → `gerir_usuarios` (cadastro de
    função é administração de identidade); Documentos → `gerir_documentos`.
  - _(Mapa a validar no plano; qualquer ajuste fino é decisão do usuário na revisão do spec.)_
- **super_admin**: god-mode (Sessão 80) → nunca vê cadeado (tudo liberado).

## Backend

- **Novo endpoint — empresas administráveis (seletor):** `GET /api/admin/empresas` → lista
  `[{loja_id, nome, rede_id, rede_nome}]` que o ator pode administrar (super_admin: todas; admin_rede:
  da rede; loja: a própria / membership). Reusa `mod_tenancy.pode_ver_loja`.
- **Flags de aba no `/api/auth/me`:** expor as capacidades relevantes (`gerir_usuarios`, `gerir_perfis`,
  `editar_dados_loja`, `gerir_documentos`, `ver_parametros`) para o front decidir cadeado vs liberado
  **sem** ida ao servidor por aba (o `usuario` do `/auth/me` já traz `acessa_admin/acessa_config`; ampliar
  para as caps de aba).
- **Gate do Painel Orizon:** os endpoints de redes/lojas/gestores já existem e já são gateados por
  `gerir_redes`/`gerir_lojas`/`gerir_usuarios` — sem mudança de backend, só de posição no front.
- **Endpoints de Admin/Config por loja:** já resolvem a loja pela loja ativa (`_loja_admin_alvo`,
  `escopo_operacional`) desde a Sessão 80 — o seletor só alimenta o header.

## Renomeações (legendas)

- `Dados da loja` → **Dados da empresa** (aba do Admin).
- `Usuários da loja` → **Usuários** (aba do Admin).
- Subtítulo do Config "Parâmetros de regra de negócio **da loja**" → "**da empresa**" (consistência).

## Faseamento (um spec, um plano em duas fases)

- **Fase 1 — estrutura:** Painel Orizon (extrai plataforma/rede do Admin) + Admin vira plano de 4 abas +
  seletor de empresa compartilhado (Admin/Config) + `nav-orizon` na sidebar + endpoint `GET /api/admin/empresas`
  + renomeações. Entrega a consistência do super_admin (miolo do pedido) e o Painel Orizon.
- **Fase 2 — travas:** abas trancadas com cadeado + step-up em Admin/Config, iguais para todos os perfis
  (expõe caps no `/auth/me`, cadeado no front, step-up no clique). Realiza a regra ampla de consistência.

## Fora de escopo (frente futura própria)

- **Dashboard consolidado do gestor de rede (`admin_rede`)** — visão sistêmica, resultados consolidados,
  particionamento grupo↔unidade. Perfil econômico/negócios, distinto do super_admin técnico. Merece
  brainstorming/spec dedicados. Este spec apenas **prepara o terreno** (seletor empresa/grupo, separação
  Sistema × Empresa) sem gerar retrabalho.
- **Comportamento interino do `admin_rede`:** usa os painéis **Admin/Config padrão** com o seletor
  **limitado às lojas da sua rede** (administra unidades). **Criar** lojas/redes é função técnica do
  `super_admin` (Painel Orizon); o `admin_rede` deixa de criar lojas pelo drill-down (que sai). Se isso
  for regressão indesejada, o usuário sinaliza na revisão — a alternativa é dar ao `admin_rede` um
  "criar loja na minha rede" dentro do Orizon escopado, mas o default deste spec é **não**, para manter
  a distinção técnica × negócios.
- **Remoção do Omie** (Frente 2) — o card de chaves do Omie **não** é recriado aqui; a remoção é tratada
  no spec/plano próprios da Frente 2.

## Testes

- **Backend (pytest/TDD):**
  - `GET /api/admin/empresas`: super_admin lista todas; admin_rede só da rede; loja só a própria; sem
    login → 401.
  - `/auth/me` expõe as flags de capacidade de aba corretas por perfil (master, operador, super_admin).
  - Regressão: Admin/Config seguem escopados pela loja ativa (já coberto pela Sessão 80; reusar
    `X-Loja-Ativa` no `HttpClient`).
- **Frontend (verificação manual + `node --check`):** o projeto não tem teste JS; validar navegação
  (as 3 telas, abas iguais por perfil, cadeado/step-up, seletor troca de empresa e Admin/Config seguem)
  no navegador, com a checklist de perfis (super_admin, master, operador, admin_rede).

## Arquivos afetados (previstos)

- `static/index.html` — sidebar (`nav-orizon`), `page-orizon` (nova), reescrita de `adminCarregarConsole`/
  `adminRender*` (Admin plano), seletor de empresa (Admin+Config), cadeado/step-up nas abas, renomeações.
- `main.py` — `GET /api/admin/empresas`; ampliar o `usuario` do `/auth/me` com as caps de aba.
- `auth/perfis.py` — (se necessário) helper do mapa aba→capacidade / lista de caps expostas.
- `tests/` — `test_admin_empresas.py` (novo), asserts de `/auth/me`.
- `DEV_LOG.md` — nova sessão; este spec.
