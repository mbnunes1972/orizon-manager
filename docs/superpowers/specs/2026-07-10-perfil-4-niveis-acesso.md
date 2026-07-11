# Perfil-4: Perfil vira 4 níveis de acesso; cargos viram Função (rev2 §2)

**Data:** 2026-07-10 · **Status:** implementado (Sessão 61) · **Suíte:** 816 verdes

Redefine o eixo **Perfil**: de ~13 níveis-cargo para **4 perfis de acesso por módulo/painel**. Os
cargos antigos viram **Função** (`Funcao`). NÃO trata escopo por Etapa nem visibilidade por
projeto/ambiente (frente posterior) — só não quebra os gates vigentes.

## Decisões confirmadas
- Migração pelo mapa do doc; capacidades mapeadas grosseiramente; desconto 50/20/10/0; escopo-por-Mapa
  dos operacionais **dormente** (viram Consultor=posse) até a re-chave por Função.

## Os 4 perfis (matriz §2)
| perfil | desc | operacional | fin/folha | fiscal | admin | config |
|--|--|--|--|--|--|--|
| diretoria | 50 | ✓ | ✓ | ✓ | ✓ | ✓ |
| gerencial | 20 | ✓ | ✗ | ✗ | ✓ | ✓ |
| consultor | 10 | ✓ | ✗ | ✗ | ✗ | ✗ |
| suporte | 0 | ✗ | ✗ | ✗ | ✓ | ✓ |

`super_admin`/`admin_rede` inalterados. Capacidades operacionais (autorizar, aprovar_financeiro,
executar_pe, registrar_medicao, ver_parametros, gerir_usuarios, editar_dados_loja, revisar_pe,
aprovar_medicao_reprovada) mapeadas p/ não quebrar gates (ex.: consultor mantém executar_pe/
registrar_medicao).

## Mudanças
- **`perfis.py`**: `PERFIS` = 4+2 perfis; `acesso_*` + `CAPACIDADES` (grupo "Acesso"); helpers
  `acessa_modulo(slug, modulo_id)` / `acessa_painel(slug, "admin"|"config")`; `matriz()` recalcula.
- **`database.py`**: `Usuario.funcao_id` (cargo da conta sem Funcionário) + migração `perfis_v3_2026`
  (renomeia nivel pelo mapa; seta `funcao_id` do cargo antigo via `Funcao` da loja; idempotente,
  guardada contra colunas ausentes).
- **Enforcement**: `_contabil_ctx` bloqueia Financeiro por `acesso_financeiro`; `/api/folha` e
  `/perfil-fiscal` por `acesso_financeiro`/`acesso_fiscal`; `auth_routes` filtra o **hub** pelos
  módulos que o perfil acessa + expõe `acessa_admin`/`acessa_config`; frontend esconde as navs Admin/
  Config e (via hub) os módulos fora do perfil.
- **Usuários da Loja**: `funcao_nome` = do Funcionário vinculado, senão de `Usuario.funcao_id` (cargo
  migrado). Perfil = `nivel`.
- **seed.py/conftest** nos 4 perfis; `_NIVEIS_ATRIBUIVEIS` deriva de `acesso_operacional`.

## Testes
- `test_perfis.py` reescrito (4 perfis, matriz, desconto, capacidades preservadas).
- `test_acesso_perfil.py` (§9): Consultor 403 em Financeiro/Folha; hub/`auth/me` reflete a matriz;
  Suporte só painéis; Função fallback via `funcao_id`.
- `test_migracao_perfis.py` (cadeia v2+v3); demais testes migrados aos novos slugs; o teste "sem
  capability" do PE passa a usar **Suporte** (consultor ganhou `executar_pe`).

## Follow-ups anotados
- Re-chave do escopo operacional (mod_escopo) para **Função** (hoje dormente após o colapso).
- Precisão fina das capacidades por Função (só Medidor registra medição, etc.).
- Gate backend dos módulos **operacionais** para Suporte (hoje escondido só na UI via hub).
- Semear Funções ao criar loja nova; atualizar o restante de `docs/USUARIOS.md`.
