# Perfis de Acesso Configuráveis por Loja — Design (rev3)

**Data:** 2026-07-10/11 · **Sessão DEV_LOG:** 62 · **Plano:** `docs/superpowers/plans/2026-07-10-perfis-configuraveis-por-loja.md`

Substitui o modelo hardcoded de 4 perfis (Diretoria/Gerencial/Consultor/Suporte, Sessão 61) por **perfis de acesso configuráveis no banco, por loja**.

## Modelo de dados

`perfil_acesso` (por loja):

| coluna | papel |
|---|---|
| `loja_id` | perfis são **por loja** (rede fica p/ futuro; a coluna já nasce pronta) |
| `slug` | identificador **globalmente único** (sistema: `master`/`gerencial`/`operador`; custom: slugificado + sufixo) |
| `nome` | rótulo exibido |
| `base` | `master`/`gerencial`/`operador` — **preset das capacidades finas** (detalhe interno, não aparece na UI) |
| `modulos_json` | lista de ids de módulo/painel acessíveis (fonte do acesso) |
| `capacidades_json` | `{cap: bool}` — **overrides** das capacidades finas sobre a base |
| `sistema` | 1 = padrão (não editável/apagável) |

Também: `Funcao.perfil_padrao` (slug do perfil default da função — Mapa de Funções) e `LogAcessoDelegado` (auditoria do step-up).

## Regra de resolução (perfis.py = adaptador com registro do DB)

- **Acesso a módulo/painel:** `acessa_modulo/acessa_painel(slug, id)` lê `modulos_json` do registro (cache carregado do banco; `recarregar()` após escrita e no fim de `init_db`). Núcleo nunca bloqueia. Plataforma (`super_admin/admin_rede`, fora da tabela) e registro vazio → fallback no `PERFIS` hardcoded.
- **Capacidades finas** (`gerir_usuarios`, `autorizar`, `aprovar_financeiro`, `gerir_perfis`, execução/medição…): `pode(slug, cap)` = override do perfil (`capacidades_json`) senão `PERFIS[base][cap]`. `desconto_max` = da base.
- Slug **global único** permite `pode(slug)` sem `loja_id` → os ~40 gates existentes não mudam de assinatura.

## Matriz dos 3 perfis padrão

| perfil | operacionais* | fiscal | financeiro/folha | painel admin | painel config |
|---|---|---|---|---|---|
| Master | ✔ | ✔ | ✔ | ✔ | ✔ |
| Gerencial | ✔ | ✔ | ✔ | ✖ | ✖ |
| Operador | ✔ | ✔ | ✖ | ✖ | ✖ |

*operacionais = captacao, cadastro, comercial, producao, estoque, expedicao, montagem, assistencias.

Migração de `Usuario.nivel`: `diretoria→master`, `consultor→operador`, `suporte→operador`, `gerencial`/plataforma inalterados (`perfis_v4_2026`, idempotente). Seed dos 3 por loja: `perfil_acesso_seed_v1` (idempotente por `(loja_id, slug)`).

## Telas (Admin › Perfis de Usuário)

- Seletor **Perfis | Funções** (sombra, não sublinhado).
- **Perfis:** lista (nome + botão "?" que abre detalhe read-only de módulos/capacidades + tipo Sistema/Personalizado). Master vê "+ Novo perfil" e "Editar" (só custom). Modal com **duas tabelas**: módulos/painéis e capacidades finas (liberar/bloquear). Sem o conceito "Base" na UI.
- **Funções (Mapa de Funções):** cada função (catálogo `/api/funcoes`) recebe um **perfil de acesso padrão** (dropdown dos perfis da loja).

## Step-up por senha (acesso fora do perfil)

Quando o usuário tenta um módulo/painel fora do perfil: backend retorna `403 {precisa_stepup: <recurso>}`. `POST /api/auth/step-up` valida login+senha de **quem tem o recurso** (`acessa_modulo/painel`), grava `LogAcessoDelegado`, concede grant em memória `(token, recurso)` TTL 30 min; `_sem_acesso_modulo` honra o grant. Frontend: interceptor de fetch trata `precisa_stepup` → modal → refaz a requisição; **módulos bloqueados aparecem no hub/sidebar com cadeado** → clique dispara o step-up.

**Fora de escopo (PENDENTE):** step-up dos **painéis Admin/Config** — hoje escondidos; os endpoints de painel são gateados por capacidade fina (não pelo grant de módulo), então "elevar para um painel" exige definir **quais capacidades** uma autorização de painel concede (decisão de modelo futura).

## Decisões (não reverter sem discussão)

- Perfis por **LOJA** (não rede — depende de painel de gestão de rede futuro).
- **Base + módulos** (não derivar as finas dos módulos): base dá o preset das finas + `desconto_max`; `modulos_json` define acesso.
- **Slug global único** (evita propagar `loja_id` nos gates).
- Capacidades finas **selecionáveis por perfil** (override sobre a base).
- Plataforma fora da tabela (fallback hardcoded).

## Deferido

- `desconto_max` e capacidades finas por Etapa do Processo seguem como estão (não quebrar os gates).
- Perfis de **rede**.
