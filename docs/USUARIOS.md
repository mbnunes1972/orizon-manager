# Perfis de Usuário — Omie_V3

> Fonte da verdade do código: `perfis.py`. Ao adicionar/alterar um perfil, atualize
> `perfis.py` **e** este documento. Usuários são criados no Painel Admin (Diretor ou
> Gerente Administrativo/Financeiro) ou via `seed.py`.

## Perfis e permissões

| Perfil | Desc. máx | Ver parâmetros | Autorizar desconto | Gerir usuários |
|---|---|---|---|---|
| Diretor | 50% | sim | sim | sim |
| Gerente de Vendas | 20% | sim | sim | não |
| Consultor | 10% | não | não | não |
| Gerente Administrativo/Financeiro | 0% | sim | não | sim |
| Assistente Logístico | 0% | não | não | não |
| Conferente | 0% | não | não | não |
| Supervisor de Montagem | 0% | não | não | não |
| Assistente Administrativo | 0% | não | não | não |
| Projetista Executivo | 0% | não | não | não |
| Medidor | 0% | não | não | não |

(Slugs internos: `diretor`, `gerente_vendas`, `consultor`, `gerente_adm_fin`,
`assistente_logistico`, `conferente`, `supervisor_montagem`,
`assistente_administrativo`, `projetista_executivo`, `medidor`.)

## Perfis administrativos de tenancy (F2 multi-tenant)

Dois perfis **puramente administrativos**: gerenciam a estrutura (redes, lojas, usuários)
e **não operam** dentro das lojas — todas as capacidades operacionais (desconto, autorizar,
aprovar financeiro, medição, ver parâmetros) são **0/False**.

| Perfil | Slug | Escopo | Gere |
|---|---|---|---|
| Administrador da Plataforma | `super_admin` | `loja_id`/`rede_id` NULL — tudo | redes, lojas (qualquer), usuários (qualquer), dados de qualquer loja |
| Administrador de Rede | `admin_rede` | `rede_id` setado, `loja_id` NULL — sua rede | lojas, diretores **da sua rede** e outros admin_rede da própria rede; dados das lojas da rede |

Capacidades de tenancy (em `perfis.py`): `gerir_redes` (só super_admin), `gerir_lojas`
(super_admin e admin_rede), `editar_dados_loja` (super_admin, admin_rede e **também o
Diretor** — só a própria loja). O escopo concreto (rede/loja) quem aplica é o `main.py`.

A área administrativa (page-07) é um console de 3 níveis espelhando a hierarquia:
**Plataforma → Rede → Loja**. Cada perfil aterrissa no seu nível (super_admin→Plataforma,
admin_rede→sua Rede, diretor/adm-fin→sua Loja) e os perfis altos descem por drill-down +
breadcrumb. A aba "Usuários da loja" do Nível 3 é o CRUD de usuários de sempre.

### super_admin de bootstrap

A migração `tenancy_v2_2026` (em `database.py`) cria, em banco sem nenhum super_admin, um
usuário dedicado de bootstrap (`sad2026`, "Administrador da Plataforma", `loja_id`/`rede_id`
NULL). É idempotente e respeita um super_admin pré-existente. **Senha de exemplo — trocar
antes de produção.**

## Capacidades adicionais (sub-projetos 3 e 4)

Além das colunas acima, `perfis.py` define capacidades específicas de fluxo:

| Capacidade | Perfis que têm | Usada em |
|---|---|---|
| `aprovar_financeiro` | Diretor, Gerente Adm/Financeiro | Concluir as etapas 8 e 11d (Aprovação financeira); **liberar a exibição dos campos de imposto** (base tributária e provisão) na tela de negociação — exige login+senha (`POST /api/auth/liberar_impostos`) |
| `registrar_medicao` | Medidor, Diretor | Confirmar a etapa 9 (Solicitação) e registrar o parecer da etapa 10 (Medição) |
| `aprovar_medicao_reprovada` | Gerente de Vendas, Gerente Adm/Financeiro, Diretor | Liberar a Medição quando o parecer é "Reprovado" (decisão comercial, 2º passo) |

> Gerente de **Vendas não** aprova financeiro; **Medidor não** decide o caso Reprovado.

## Responsabilidades no ciclo (resumo)

- **Diretor / Gerente de Vendas / Consultor:** negociação, orçamento, desconto.
- **Gerente Administrativo/Financeiro:** aprovação financeira (Sub-projeto 3); gestão de usuários.
- **Medidor:** confirma/registra a medição (Sub-projeto 4).
- **Projetista Executivo:** projeto executivo e suas sub-etapas.
- **Supervisor de Montagem / Conferente / Assistente Logístico / Assistente Administrativo:**
  etapas operacionais do ciclo (montagem, conferência, logística, apoio administrativo).

## Gestão de usuários

- Painel Admin → seção **Usuários**: criar, editar perfil/telefone, ativar/desativar, resetar senha.
- Acesso restrito a perfis com `gerir_usuarios` (Diretor, Gerente Adm/Financeiro).
- Usuários são **desativados** (não excluídos) para preservar histórico.
- Cadastro/edição via **modal** (não há mais `prompt()`): campos nome, login, senha,
  telefone, WhatsApp, e-mail, CPF e perfil. O `<select>` de perfil é populado pelo
  endpoint `GET /api/admin/usuarios/perfis-permitidos` (fonte: `perfis.py` + `mod_tenancy`).
- **Níveis do console:** usuários de loja no Nível 3 ("Usuários da loja"); administradores
  de rede no Nível 2 ("Administradores da rede"); gestores gerais (super_admin) no Nível 1
  ("Gestores gerais").
- **admin_rede gere seus pares:** um Administrador de Rede pode criar/editar outros
  admin_rede **da própria rede** (não cria super_admin).
- **Anti-lockout:** ninguém rebaixa o próprio perfil nem se inativa pelo modal.

## Migração de perfis antigos

A migração `perfis_v2_2026` (em `database.py`) renomeia automaticamente os níveis
legados: `gerente` → `gerente_vendas` e `admin` → `diretor` (perfil técnico `admin`
aposentado).

## Usuários-exemplo (seed.py)

| Login | Perfil |
|---|---|
| pdm2026 | Diretor |
| lds2026 | Gerente de Vendas |
| mds2026 | Consultor |
| gaf2026 | Gerente Administrativo/Financeiro |
| alg2026 | Assistente Logístico |
| ccf2026 | Conferente |
| smt2026 | Supervisor de Montagem |
| aad2026 | Assistente Administrativo |
| ppe2026 | Projetista Executivo |
| med2026 | Medidor |

> Senhas de exemplo definidas em `seed.py` — **trocar antes de produção**.

---

## Isolamento operacional por loja (F4)

A partir da F4, os dados **operacionais** (clientes, projetos, orçamentos, contratos, pool,
medição, ciclo, parceiros) são **isolados por loja**: cada usuário operacional só enxerga e
opera os da **própria loja**. Acesso a um registro de outra loja por id/link direto retorna
**404**. **super_admin** e **admin_rede** não têm acesso operacional (recebem **403** nesses
endpoints) — administram a estrutura pelo console de 3 níveis (F2), não operam dentro das lojas.
Detalhes e roteiro de verificação em `docs/processos/SMOKE_F4_ISOLAMENTO.md`.
