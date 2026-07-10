# Fase 1 — Mapa de Atribuições + escopo de visibilidade

**Data:** 2026-07-10 · **Status:** implementado (Sessão 59) · **Suíte:** 812 verdes

Implementa `Regras_Funcoes_Perfis_Atribuicoes §4–§7/§9`. Introduz o Mapa de Atribuições (quem faz
PE/Medição/Montagem/Assistência, por ambiente) com a atribuição concedendo visibilidade escopada;
backend como fronteira (404 fora de escopo), no padrão puro do `mod_tenancy`.

## Decisões desta fase (confirmadas)
- Papéis fora do §3 (Conferente/Logístico/Administrativo): **seguem vendo tudo na loja** — só
  PE/Medidor/Montagem são escopados por atribuição.
- Login do Terceiro: **só a coluna** `Terceiro.usuario_id` (fluxo da conta é passe seguinte).
- Visão do papel: **gate por capacidade + teste**; redação campo-a-campo é follow-up.

## Modelo (F1.1)
- `atribuicoes_ambiente` (`loja_id`, `projeto_nome`, `pool_ambiente_id` NULL=projeto inteiro,
  `papel` ∈ {projeto_executivo,medicao,montagem,assistencia}, `funcionario_id`|`terceiro_id`,
  `atribuido_por_id`, timestamps) + `UniqueConstraint(projeto_nome, pool_ambiente_id, papel)`.
  NULL é distinto no SQLite → a unicidade de "projeto inteiro" é garantida pelo **upsert** do CRUD.
- `Terceiro.usuario_id` (conta opcional). Migração idempotente. Manifesto: módulo núcleo `escopo`.

## Predicados puros (F1.2) — `mod_escopo.py`
Espelha `mod_tenancy` (sem I/O; main.py faz as queries e aplica o WHERE): `pode_ver_projeto`,
`pode_ver_ambiente`, `resolver_responsavel` (ambiente > projeto-inteiro > None), `projetos_visiveis`,
`visao_do_papel` ('comercial'|'operacional'|'nenhuma'), `funcao_compativel(papel, funcao_nome)` (§7).
Gerência+ (autorizar/aprovar_financeiro) tudo; Consultor posse; operacional
(projetista_executivo/medidor/supervisor_montagem) só o atribuído; admin nada.

## CRUD (F1.3)
`GET/POST /api/projetos/<nome>/atribuicoes`. POST = upsert `{papel, pool_ambiente_id|null,
funcionario_id|terceiro_id}`; alvo vazio limpa; alvo tem de pertencer à loja **e** ter Função
compatível com o papel; 1:1 por (papel, ambiente) — substitui; auditado em `LogAcaoGerencial`. Abrir/
editar só Gerência+ e Supervisor de Montagem.

## Enforcement (F1.4)
`_projeto_visivel_ao_ator` e `_filtrar_projetos_por_loja` roteados por `mod_escopo` (resolvendo o Mapa
para os operacionais via `Funcionario.usuario_id`/`Terceiro.usuario_id`). Acesso fora de escopo → **404**
(no `GET /projetos/<nome>` e nos POST parceiro/editar). F4 (isolamento por loja) intacto.

## Ciclo + visão do papel (F1.5)
- `/ciclo` expõe `responsavel_efetivo` = override da etapa (v12) **OU** default do Mapa (etapa→papel
  §7, atribuição projeto-inteiro). Mapa é a fonte por-projeto da pessoa da fase; sobreponível.
- Operacional barrado (403) nos endpoints comerciais (`margens`, `negociacao-preview`) via
  `_bloqueio_comercial` (`mod_escopo.visao_do_papel == "operacional"`).

## Frontend (F1.6)
Modal **Mapa de Atribuições** (botão no painel do Ciclo, só Gerência+/Supervisor): grade papel ×
[projeto inteiro + ambientes]; dropdown de Funcionário/Terceiro **filtrado pela função compatível**;
substitui/limpa via o endpoint. Listas/telas já chegam filtradas do backend.

## Testes (§9) — `tests/test_atribuicoes.py`
UniqueConstraint; predicados; CRUD (função compatível, substitui, auditoria, só gerência+); **Consultor
A não vê projeto de B (link → 404)**; operacional só o atribuído; F4 intacto; Gerência+ tudo; Medidor
barrado no comercial; Mapa = responsável default da fase.

## Follow-ups anotados
- Fluxo de conta do Terceiro (`usuario_id`) + perfil de acesso do Terceiro.
- Semear Funções na criação de loja nova (backfill é one-shot).
- Redação campo-a-campo do comercial em telas compartilhadas, se aparecer vazamento.
- Campo `papel` na Tabela de Funções (remove o acoplamento por nome em `PAPEL_FUNCOES`).
- Enforcement de escopo nos demais handlers por-projeto (hoje loja-only; os pontos-chave já cobertos).
