# Fase 0 — Separar Função de Perfil: perfis.py fonte única + seed da Tabela de Funções

**Data:** 2026-07-10 · **Status:** implementado (Sessão 58) · **Suíte:** 799 verdes

Pré-requisito da frente "Mapa de Atribuições" (`Regras_Funcoes_Perfis_Atribuicoes §8`). Separa os três
eixos: **Perfil** (acesso, `perfis.py`) × **Função** (cargo, `Funcao`) × Escopo (Fase 1).

## 0a — `perfis.py` como fonte única dos perfis de acesso

**Problema:** dois lugares competiam com `perfis.py` e um tinha bug real.
- `mod_cadastro.PERFIS_ACESSO = ("consultor","gerente","diretor")` — `"gerente"` **não é** slug de
  `perfis.py` (os reais são `gerente_vendas`/`gerente_adm_fin`); uma conta de Funcionário criada com
  `perfil="gerente"` recebia `nivel="gerente"` → caía no default sem permissão.
- `perfis_config.json` (legado single-user) trazia `desconto_max_pct`, `pode_ver_margens` e uma
  `senha_gerente:"1234"` embutida.

**Mudanças:**
- `perfis.py`: `slugs_loja()` / `opcoes_loja()` — perfis atribuíveis a um login de loja (exclui
  `super_admin`/`admin_rede`). Fonte única.
- `mod_cadastro.py`: aposenta a tupla; `func_sync_acesso` valida `perfil in perfis.slugs_loja()`;
  `META["perfis_acesso"]` = `perfis.opcoes_loja()` (`[{slug, rotulo}]`).
- `storage.py`: `perfis_carregar()` **deriva** as definições de `perfis.py` (chaves legadas da UI —
  consultor/gerente/diretoria — mapeadas para os slugs reais consultor/gerente_vendas/diretor); só o
  `perfil_ativo` (estado de UI) é lido do arquivo. Sem `senha_gerente`. `perfis_config.json` deixa de
  ser fonte de verdade.
- `static/index.html`: o dropdown "Perfil de Usuário" do Funcionário lê `META.perfis_acesso` (slugs
  reais) em vez do 3-tuplo hardcoded.

**Fora de escopo (anotado):** `POST /api/gerente/verificar` ainda tem fallback `"1234"` no próprio
handler (gate legado, anterior à reautenticação por `check_senha`) — merece um passe dedicado.

## 0b — Seed da Tabela de Funções por loja

- `database.FUNCOES_PADRAO`: 11 cargos (rótulos de cargo de `perfis.py` + **Montador**, que é Terceiro
  sem perfil próprio).
- `seed.criar_funcoes_seed(db, loja_id)`: idempotente por `(loja_id, nome)`; chamada em `seed()`.
- `database._run_migracoes`: backfill único `funcoes_seed_v1` — semeia todas as lojas existentes
  (idempotente por nome), para o DB preservado (VPS/local) ganhar o catálogo sem reseed.
- **Follow-up anotado:** semear no momento de criação de loja nova (o backfill é one-shot).

## Testes
- `tests/test_perfis_fonte_unica.py`: `slugs_loja` exclui plataforma/rede; `META.perfis_acesso`
  derivado sem o órfão `gerente`; `func_sync_acesso` rejeita slug inválido e aceita `gerente_vendas`;
  `perfis_carregar` derivado de `perfis.py` sem `senha_gerente`.
- `tests/test_funcoes_seed.py`: seed idempotente por loja; escopado por loja (F4).

## Evidência
`META.perfis_acesso` lista os 10 slugs de loja (sem `gerente`); `perfis_carregar` deriva
consultor=10 / gerente=20 / diretoria=50 de `perfis.py`; catálogo padrão de 11 cargos inclui
Medidor/Montador/Projetista Executivo.
