# Multi-tenant — F4: Isolamento operacional

**Data:** 2026-06-21
**Status:** spec aprovado pelo usuário no brainstorm (aguardando revisão do spec escrito antes do plano)
**Origem:** quarta e última fase do programa multi-tenant. A F1 criou o schema; a F2 expôs a
tenancy na UI/API (escopo só nas telas admin); a F3 fez o contrato puxar da loja. A F4 aplica
**escopo por loja em TODAS as queries operacionais**, que hoje são globais.

---

## Contexto do programa (lembrete das 4 fases)

```
Plataforma (super_admin)
 ├─ Rede A (admin_rede)
 │   ├─ Loja A1 (diretor) → usuários, clientes, projetos, parceiros, contratos
 │   └─ Loja A2 (diretor)
 └─ Loja avulsa X (rede_id = NULL; diretor)
```

- **F1 — Fundação de dados.** CONCLUÍDA (sessão 21). Aditiva.
- **F2 — Perfis e CRUD de tenancy.** CONCLUÍDA (sessão 22). Escopo só nas telas admin.
- **F3 — Contrato puxa da loja.** CONCLUÍDA (sessão 23).
- **F4 — Isolamento operacional.** ESTE SPEC.

---

## Decisões do brainstorm (2026-06-21)

1. **Cada loja vê só o seu.** Usuários operacionais (consultor, diretor e demais) só enxergam e
   operam dados da **própria** loja. **super_admin/admin_rede continuam SEM acesso operacional**
   (coerente com a F2 — administram a estrutura, não operam dentro das lojas).
2. **Tudo de uma fase.** A F4 fecha o isolamento inteiro de uma vez: (a) **carimbar** a loja na
   criação, (b) **filtrar** as listagens, (c) **checar dono** no acesso por id e nas mutações
   (anti-IDOR). Sem janela de brecha.
3. **Cross-loja → 404.** Ao tentar acessar um registro de outra loja por id/link, o servidor
   responde **404 "não encontrado"** (não revela a existência do registro).

---

## Objetivo da F4

Tornar o isolamento **real e à prova de acesso direto**. Ao fim da F4:

- toda listagem operacional (clientes, projetos, orçamentos, contratos, pool, medição, parceiros)
  mostra **apenas** os dados da loja do ator;
- todo acesso/mutação por id ou `nome_safe` confere o dono — registro de outra loja → **404**;
- toda criação operacional **carimba** `loja_id = loja do ator`;
- perfis administrativos (super_admin/admin_rede) recebem **403** em endpoints operacionais;
- nenhuma mudança de UI e nenhum perfil novo.

## Não-objetivos da F4 (explícitos)

- **Sem mudança de UI.** As telas já renderizam só o que a API devolve; o filtro entra na API.
- **Sem supervisão de rede/plataforma no operacional** (Decisão 1). admin_rede **não** ganha
  visão das lojas da rede aqui; super_admin **não** ganha "god mode" operacional.
- **Sem perfis novos** e sem novas tabelas (todas as colunas de tenant vieram na F1).
- **Sem reescrita da estrutura de roteamento** do `http.server` (helpers aplicados endpoint a
  endpoint, não um interceptador central).

---

## 1. Modelo de escopo (puro, em `mod_tenancy.py`)

- **Quem opera tem `loja_id`.** O escopo operacional é exatamente `loja_id = ator.loja_id`.
- **super_admin/admin_rede têm `loja_id` NULL → sem acesso operacional.** Qualquer endpoint
  operacional responde **403**.
- Função pura nova `escopo_operacional(ator) -> (loja_id | None, erro | None)`: devolve o
  `loja_id` quando o ator é usuário de loja; devolve `(None, "<motivo>")` quando o ator não tem
  loja (→ a rota traduz em 403). Não faz I/O; a rota aplica.

## 2. Helpers de aplicação (em `main.py`)

- `_exigir_loja_operacional(self, db, usuario) -> int | None` — resolve o ator (`_ator_dict`),
  retorna o `loja_id`; se o ator não tiver loja, **envia 403** e retorna `None` (a rota
  interrompe). Guarda no topo de cada handler operacional.
- `_scoped_get_or_404(self, db, Model, pk, loja_id) -> obj | None` — `db.get(Model, pk)`; se
  ausente **ou** `obj.loja_id != loja_id`, **envia 404** e retorna `None`. Para entidades com
  `loja_id` próprio (Cliente, Orçamento, Contrato, Projeto).
- `_projeto_da_loja_ou_404(self, db, nome_safe, loja_id) -> projeto | None` — resolve
  `projetos_meta` por `nome_safe`; se ausente **ou** de outra loja, **envia 404**. **Ponto único**
  que dá escopo às entidades sem `loja_id` próprio (Pool/Medição/Ciclo, todas chaveadas por
  `projeto_nome`/`projeto_id`) e a tudo que é "por projeto".

Padrão de retorno: helpers que já enviaram a resposta (403/404) retornam `None`; o handler checa
`if x is None: return`.

## 3. Onde aplica (por entidade)

| Entidade | `loja_id` | Listagem | Acesso por id / mutação |
|---|---|---|---|
| **Cliente** | próprio | `.filter(Cliente.loja_id == L)` | `_scoped_get_or_404` (GET/editar) |
| **Projeto** (`projetos_meta`) | próprio | filtra a lista do storage (ver §5) | `_projeto_da_loja_ou_404` |
| **Orçamento** | próprio | `.filter(Orcamento.loja_id == L)` | `_scoped_get_or_404` (margens, rename, ambientes) |
| **Contrato** | próprio (F3) | via projeto | guard nos `assinar`/`editar`/pdf |
| **Pool / Medição / Ciclo** | herda do projeto | via projeto | `_projeto_da_loja_ou_404` |
| **Parceiro** | rede + `parceiro_lojas` (M:N) | escopa a lista por visibilidade do ator | mutação já escopada (F2) |

Endpoints concretos a cobrir (do mapa da superfície): `clientes` (list, `<id>`, `<id>/projetos`,
`<id>/briefing`), `projetos` (list, buscar, `<nome>`, ciclo, orçamentos), `orcamentos`
(`<oid>/ambientes`, `<oid>/margens`, rename, add/remove ambientes), `contrato` (get, pdf,
assinar, editar, gerar — gerar já resolve a loja na F3, falta o guard de dono no projeto), `pool`
(get, sobrescrever, nova-versão, renomear, criar_forçado, remover/adicionar ambiente), `medicao`
(get, arquivo, solicitação, parecer, decisão-reprovado), `ciclo` (desfazer_aprovacao, reabrir),
`parceiros` (list, `<id>`).

## 4. Carimbo na criação

Setar `loja_id = L` ao criar **Cliente, Projeto (`projetos_meta`), Orçamento**. (Contrato já
carimba desde a F3; Pool/Medição/Ciclo herdam do projeto, sem coluna própria.) Sem isso, dado
novo nasceria "órfão" (NULL) e — depois do filtro — invisível para todos.

## 5. Listagem de projetos (ponto mais delicado)

A lista de projetos vem do **storage/disco** (`_listar_projetos`/`_buscar_projetos` em
`mod_omie.py`), não de uma query SQL. O filtro: montar o conjunto de `nome_safe` cujo
`projetos_meta.loja_id == L` e **interceptar a lista** mantendo só esses. Requer que todo projeto
tenha linha em `projetos_meta` com `loja_id` (garantido pelo carimbo da §4 + backfill da §6). O
GET de projeto individual usa `_projeto_da_loja_ou_404`.

## 6. Migração defensiva

Passo idempotente em `_migrar_dados`: qualquer `loja_id` NULL em
`clientes`/`projetos_meta`/`orcamentos`/`contratos` → loja-semente (id=1). **Hoje afeta 0 linhas**
(tudo já está na loja 1); é rede de segurança para não sumir dado caso algum create escape do
carimbo antes do deploy da F4.

## 7. super_admin / admin_rede

Sem acesso operacional (Decisão 1): `_exigir_loja_operacional` os barra com **403** em todos os
endpoints operacionais. Eles mantêm exclusivamente o console administrativo da F2.

## 8. Parceiros

A **listagem** de parceiros (`GET /api/parceiros`) passa a mostrar só os visíveis ao ator:
abrangência `'loja'` via `parceiro_lojas` da loja do ator; `'rede'` via a rede da loja do ator.
As **mutações** já são escopadas pela F2 (`_aplicar_abrangencia_parceiro`). (Baixo risco hoje —
tabela `parceiros` vazia — mas incluído para consistência.)

---

## Modelo de dados

Sem tabelas ou colunas novas (tudo veio na F1). Apenas a migração defensiva de dados (§6).

## Arquivos afetados (previsão)

- `mod_tenancy.py` — função pura `escopo_operacional(ator)`.
- `main.py` — helpers `_exigir_loja_operacional`, `_scoped_get_or_404`, `_projeto_da_loja_ou_404`;
  aplicação do escopo nas listagens, GETs por id/`nome_safe` e mutações operacionais; carimbo de
  `loja_id` na criação de cliente/projeto/orçamento; filtro da lista de projetos (storage) e da
  lista de parceiros.
- `database.py` — passo de backfill defensivo em `_migrar_dados`.
- `docs/USUARIOS.md` — nota de que o operacional passa a ser isolado por loja.
- `DEV_LOG.md` — registrar a sessão da F4.

---

## Verificação

**pytest (novos/puros):**
- `escopo_operacional`: usuário de loja → seu `loja_id`; super_admin/admin_rede → `(None, erro)`.
- Backfill defensivo idempotente (NULL → loja 1; roda 2× sem duplicar efeito).

**pytest (cenário 2 lojas, com `_scoped_get_or_404`/`_projeto_da_loja_ou_404` testáveis por stub
de db):** ator da Loja A não obtém objeto da Loja B (→ 404/None); criação carimba a loja do ator;
super_admin → 403.

**API real (servidor, 2 lojas + usuários):** A não lista nem abre dado de B; link cruzado por
id/`nome_safe` → 404; criar cliente/projeto/orçamento na Loja A grava `loja_id=A`; super_admin
recebe 403 nos endpoints operacionais.

**Regressão:** suíte atual (195) verde; com uma única loja, o comportamento visível é idêntico ao
de hoje (tudo é da loja 1).

**Critério de pronto:** suíte verde + cenário 2-lojas isolado (listas, por-id 404, criação
carimbada, 403 administrativo); nenhuma regressão na operação de loja única.

---

## Riscos e mitigação

- **Superfície grande (~30 endpoints) → fácil esquecer um.** Mitigação: helpers únicos
  (`_exigir_loja_operacional` + os dois `*_ou_404`) reaplicados; checklist de endpoints na §3; o
  plano cobre entidade por entidade.
- **Lista de projetos é storage-based** → o filtro depende de `projetos_meta` em sincronia.
  Mitigação: carimbo na criação + backfill; o GET individual e tudo "por projeto" passa pelo
  `_projeto_da_loja_ou_404` (que é a fonte de verdade do escopo).
- **Esconder dado por engano (falso isolamento).** Mitigação: como hoje só existe a loja 1 e tudo
  é dela, qualquer "sumiço" indica `loja_id` faltando → coberto pelo backfill; teste de regressão
  de loja única.
- **403 administrativo quebrar algum fluxo legítimo.** Mitigação: confirmar que super_admin/
  admin_rede realmente não dependem de nenhum endpoint operacional (a F2 já os manteve fora).
- **Entidades transitivas (pool/medição/ciclo) acessadas por id próprio sem passar pelo projeto.**
  Mitigação: rotear todo acesso por `nome_safe` do projeto e, quando o id for de uma sub-entidade
  (ex.: `pool/<pid>`), validar que ela pertence ao projeto escopado antes de agir.
