# Smoke / Verificação — F4: Isolamento operacional

> **Status:** COBERTO por **suíte de regressão E2E automatizada** (2026-06-22).
> A F4 está implementada na branch `feat/multitenant-f4-isolamento`, com **revisão de segurança
> por subagentes em cada task** (que pegou e corrigiu **vários IDORs reais** — ver histórico
> abaixo). O isolamento agora tem `tests/test_isolamento_f4_e2e.py`: sobe o **servidor real numa
> thread** com **2 lojas** semeadas num **banco/diretório temporários** (sem depender do ambiente
> do usuário) e exercita a matriz de isolamento por HTTP com login real. **234 testes verdes**
> no total (33 no arquivo E2E). O smoke manual com 2 lojas em produção fica como **sanity final
> opcional**.
>
> **Achado da suíte E2E (corrigido):** `POST /api/clientes` tinha um `import threading` redundante
> dentro de `do_POST` que tornava `threading` local à função inteira, quebrando os usos anteriores
> (sync Omie em background; threads do fluxo de negociação) com `UnboundLocalError`. Removido o
> import redundante (commit de fix). Guard de regressão em `test_do_post_nao_faz_shadowing_de_threading`.
>
> Cobertura E2E (cada item é um teste): leitura cross-loja de cliente/projeto/orçamento/contrato
> → 404; listagens (clientes/projetos/orçamentos) escopadas por loja; super_admin/admin_rede → 403
> no operacional; endpoints sensíveis → 401 anônimo
> (status/descontos/valor/parceiros/briefings/ambientes); escrita cross-loja bloqueada com estado
> da outra loja intacto; criação carimba `loja_id` do autor em cliente/projeto/orçamento;
> sem-regressão na loja legítima; colisão de CPF cross-loja não vaza o cliente da outra loja
> (409 sem dados). Este documento segue útil para acelerar o diagnóstico se algum bug aparecer.

Spec/plano: `docs/superpowers/specs/multitenant/2026-06-21-multitenant-f4-isolamento-design.md` e
`docs/superpowers/plans/2026-06-21-multitenant-f4-isolamento.md`.

---

## 1. O que a F4 faz (resumo)

Cada usuário operacional (consultor, diretor, etc.) só **vê e opera** os dados da **própria
loja**. super_admin/admin_rede **não têm acesso operacional** (recebem 403). Aplicado em ~30
endpoints via 3 peças (todas testadas por unidade):

- `mod_tenancy.escopo_operacional(ator)` → `(loja_id, None)` p/ usuário de loja; `(None, motivo)`
  p/ perfil administrativo (vira **403**).
- `_obj_da_loja(db, Model, pk, loja_id)` → objeto se for da loja, senão `None` (vira **404**).
- `_projeto_da_loja(db, nome_safe, loja_id)` → projeto da loja, senão `None` (escopo das
  entidades "por projeto": pool/medição/ciclo/contrato).

Criação de cliente/projeto/orçamento **carimba** `loja_id` do autor. Backfill defensivo garante
que nenhuma linha operacional fique sem loja.

## 2. Pré-condições do smoke (precisa de 2 lojas)

1. Criar uma **2ª loja** (id=2) pelo console admin (super_admin) e um **usuário operacional**
   nela (ex.: um diretor da Loja 2).
2. Ter dados na Loja 1 (o estado atual) e criar alguns na Loja 2.

## 3. Smoke — o que verificar

| Cenário | Esperado |
|---|---|
| Logar como usuário da **Loja 2**, abrir a lista de **clientes/projetos/orçamentos** | vê só os da Loja 2 (não vê os da Loja 1) |
| Usuário da Loja 2 abre por **link/id direto** um cliente/projeto/contrato da **Loja 1** | **404 "Não encontrado"** (não vaza existência) |
| Usuário da Loja 2 **cria** cliente/projeto/orçamento | grava com `loja_id=2` (confere no banco) |
| Logar como **super_admin** e chamar qualquer endpoint operacional | **403** (sem acesso operacional) |
| Usuário da Loja 1 (estado de hoje) | continua vendo/operando **tudo** da Loja 1 (sem regressão) |
| Gerar contrato de um projeto da própria loja | funciona (F3 intacto: snapshot + número por código) |

## 4. Inspeção no banco (SQLite `orizon.db`)

```sql
-- carimbo de loja nos operacionais
SELECT 'clientes' t, loja_id, COUNT(*) FROM clientes GROUP BY loja_id
UNION ALL SELECT 'projetos', loja_id, COUNT(*) FROM projetos_meta GROUP BY loja_id
UNION ALL SELECT 'orcamentos', loja_id, COUNT(*) FROM orcamentos GROUP BY loja_id
UNION ALL SELECT 'contratos', loja_id, COUNT(*) FROM contratos GROUP BY loja_id;
-- nenhuma linha deve ter loja_id NULL (backfill garante)
```

## 5. Mapa de triagem — sintoma → local provável

| Sintoma | Olhar primeiro |
|---|---|
| Usuário de loja recebe **403** onde deveria operar | `escopo_operacional` (`mod_tenancy.py`) — o usuário tem `loja_id`? Sessão expõe `loja_id`? (`_ator_dict`, `auth._usuario_dict`) |
| **Dados somem** para um usuário legítimo (loja 1) | alguma linha com `loja_id` NULL → rodar/conferir `_backfill_loja_operacional` (database.py); criação que não carimbou; `upsert_projeto_status` cria projeto sem loja? (corrigido p/ `loja_seed_id`) |
| Consigo abrir dado de **outra loja** por id/link | o handler não passou por `_obj_da_loja`/`_projeto_da_loja`, OU o guard está **depois** de uma query que já vaza estado → mover o 404 p/ antes |
| Lista de **projetos** mostra de outras lojas | `_filtrar_projetos_por_loja` (main.py) — a lista vem do storage e é cruzada com `projetos_meta.loja_id` |
| **Parceiro** de outra loja aparece na lista | `_parceiro_visivel_loja` (abrangência 'loja' via `parceiro_lojas` / 'rede' via rede da loja) |
| Endpoint operacional **sem auth** responde a anônimo | falta o guard de 401 (`get_usuario_sessao`) — vários foram adicionados na F4 |

## 6. Endpoints sensíveis corrigidos na revisão (histórico — onde IDORs foram fechados)

A revisão de segurança por task pegou e **corrigiu** estes (todos já fechados na branch):
- `POST /api/clientes/<id>/briefing` (IDOR de escrita cross-loja) e vazamento de cliente de
  outra loja na **colisão de CPF**.
- `POST /api/projetos/<nome>/parametros` (ordem: checagem de loja agora vem antes do estado).
- `GET /api/projetos/<nome>/briefing` (estava sem auth/escopo).
- `PUT /api/orcamentos/<id>/descontos` e `PATCH /orcamentos/<id>/valor` (**sem auth nenhuma**).
- "Orçamento 1" auto-criado em `/projetos/novo` ficava com `loja_id` NULL (quebra funcional).
- `_origem` (cópia de margens de orçamento-modelo) lia cross-loja.
- `POST /projetos/<nome>/ambientes/...` (**sem auth**) e `POST /api/projetos/<nome>/briefing`
  (sem checagem de sessão).
- **(revisão final do conjunto)** `PATCH /api/projetos/<nome>/status` (**sem auth** — qualquer um
  mudava o funil de qualquer projeto), `POST /api/parceiros` (sem auth) e
  `POST /api/parceiros/<id>/editar` (sem auth + edição cross-loja de parceiro).

## 7. Achado pré-existente (FORA do escopo da F4 — decisão sua)

`contrato_editar.py` → `validar_gerencial` usa nomes de perfil **antigos** (`"gerente"`,
`"admin"`) que foram renomeados na migração de perfis. Resultado: hoje **só `diretor`** consegue
editar contrato pelo gate gerencial; `gerente_vendas`/`gerente_adm_fin` ficam de fora. Não é da
F4 (a F4 só adicionou o escopo de loja por cima desse gate). **Decisão de política sua:** quem
deve poder editar contrato? Se for atualizar, trocar a allow-list em `contrato_editar.py` pelos
nomes atuais.

## 8. Não-objetivos (lembrete)

Sem mudança de UI; sem supervisão de rede/plataforma no operacional; sem perfis novos. Com **uma
única loja** (estado de hoje), o comportamento visível é **idêntico** ao de antes da F4.
