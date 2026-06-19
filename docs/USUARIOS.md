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
