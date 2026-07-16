# Spec — Sub-projeto 2: Perfis + Painel Admin de Usuários + Documentação

> Orizon Manager | Dalmóbile | Data: 2026-06-18
> Parte 2 de 4 da decomposição (itens 4 e 5). Fundação reutilizada pelos sub-projetos 3 e 4. Status: aprovado para plano.

## Contexto

Hoje o sistema tem apenas 4 níveis (`Usuario.nivel`: `diretor | gerente | consultor | admin`),
com permissões espalhadas em checks de string (`limite_desconto` em `database.py`,
`nivel in (...)` em `main.py`/`auth.py`, `_LIMITES_NIVEL` fixo no frontend). Usuários
nascem só via `seed.py` (3 usuários); não há criação por UI. O painel admin (page-07)
só tem a fila de sync Omie + uma seção legada de perfis. Existe um `perfis_config.json`
legado (`perfil_ativo`), pré-autenticação, sem uso real relevante.

Este sub-projeto estabelece os **10 perfis oficiais**, centraliza as permissões, cria
o **CRUD de usuários** no painel admin e a **documentação** de perfis/usuários.

## Decisões (confirmadas com o usuário)

- **10 perfis** com a matriz de permissões abaixo.
- Limites de desconto: Diretor 50%, Gerente de Vendas 20%, Consultor 10%, demais 0%.
- Gestão de usuários (CRUD + painel): **Diretor ou Gerente Adm/Financeiro**.
- Perfil técnico `admin` **aposentado** (migra `admin` → `diretor`).
- Documentação: **ambos** — doc de perfis no repo + lista viva de usuários no painel.
- `seed.py` cria **um usuário-exemplo por perfil** (idempotente).
- Autorizar desconto: Diretor + Gerente de Vendas. "Ver parâmetros/margens": Diretor +
  Gerente de Vendas + Gerente Adm/Financeiro.

## Matriz de perfis

| Slug | Rótulo | desconto_max | ver_parametros | autorizar | gerir_usuarios |
|---|---|---|---|---|---|
| `diretor` | Diretor | 50 | ✓ | ✓ | ✓ |
| `gerente_vendas` | Gerente de Vendas | 20 | ✓ | ✓ | – |
| `consultor` | Consultor | 10 | – | – | – |
| `gerente_adm_fin` | Gerente Administrativo/Financeiro | 0 | ✓ | – | ✓ |
| `assistente_logistico` | Assistente Logístico | 0 | – | – | – |
| `conferente` | Conferente | 0 | – | – | – |
| `supervisor_montagem` | Supervisor de Montagem | 0 | – | – | – |
| `assistente_administrativo` | Assistente Administrativo | 0 | – | – | – |
| `projetista_executivo` | Projetista Executivo | 0 | – | – | – |
| `medidor` | Medidor | 0 | – | – | – |

Os perfis operacionais (logístico, conferente, supervisor de montagem, assistente
administrativo, projetista executivo, medidor) têm apenas login + acesso base nesta
fase; seus papéis no ciclo (medição, montagem, conferência) entram nos sub-projetos 3/4.

## Detalhamento

### 1. Módulo central de perfis — `perfis.py` (novo)

```python
PERFIS = {
  "diretor": {"rotulo": "Diretor", "desconto_max": 50.0,
              "ver_parametros": True, "autorizar": True, "gerir_usuarios": True},
  "gerente_vendas": {"rotulo": "Gerente de Vendas", "desconto_max": 20.0,
              "ver_parametros": True, "autorizar": True, "gerir_usuarios": False},
  "consultor": {"rotulo": "Consultor", "desconto_max": 10.0,
              "ver_parametros": False, "autorizar": False, "gerir_usuarios": False},
  "gerente_adm_fin": {"rotulo": "Gerente Administrativo/Financeiro", "desconto_max": 0.0,
              "ver_parametros": True, "autorizar": False, "gerir_usuarios": True},
  "assistente_logistico": {"rotulo": "Assistente Logístico", ...0/False...},
  "conferente": {...}, "supervisor_montagem": {...},
  "assistente_administrativo": {...}, "projetista_executivo": {...}, "medidor": {...},
}
```

Helpers: `rotulo(slug)`, `desconto_max(slug)`, `pode(slug, cap)` (lê a flag; slug
desconhecido → defaults seguros: 0 / False), `existe(slug)`, `slugs()`.

**Consumidores ajustados:**
- `database.py`: `Usuario.limite_desconto` → `perfis.desconto_max(self.nivel)`;
  `Usuario.pode_ver_parametros` → `perfis.pode(self.nivel, "ver_parametros")`.
- `main.py`/`auth.py`: checks `nivel in ("gerente","diretor","admin")` para autorizar
  → `perfis.pode(nivel, "autorizar")`; gate do painel admin → `perfis.pode(nivel, "gerir_usuarios")`.

### 2. Migração + seed

- **Migração idempotente** (em `database.py`, junto às demais): `UPDATE usuarios SET nivel='gerente_vendas' WHERE nivel='gerente'`; `... ='diretor' WHERE nivel='admin'`.
- **`seed.py`:** mantém os 3 atuais (com `gerente`→`gerente_vendas`) e adiciona um
  usuário-exemplo para cada perfil restante (logins padronizados, ex.: `gaf2026`
  Gerente Adm/Fin, `med2026` Medidor, etc.), idempotente (pula existentes).

### 3. Painel Admin — CRUD de usuários (page-07)

Nova seção "Usuários" (acima/abaixo da fila de sync). Gate: `gerir_usuarios`.
- **Lista viva:** tabela `nome | login | perfil (rótulo) | ativo | ações`.
- **Novo usuário:** `nome`, `login`, `senha`, `perfil` (select dos 10 rótulos), `telefone`.
- **Editar:** `perfil`, `telefone`, ativar/desativar, **resetar senha**.
- **Endpoints** (todos com gate `gerir_usuarios`; ver `get_usuario_sessao`):
  - `GET /api/admin/usuarios` → lista `[{id, nome, login, nivel, rotulo, telefone, ativo}]`.
  - `POST /api/admin/usuarios` → cria (valida `login` único e `perfil` válido; `set_senha`).
  - `PATCH /api/admin/usuarios/<id>` → atualiza `nivel`/`telefone`/`ativo` e, se vier
    `senha`, redefine via `set_senha`.
  - Desativar = `PATCH ativo=0` (não exclui — preserva histórico/sessões).
- Validações: login único; perfil ∈ `PERFIS`; nome/login/senha obrigatórios na criação.

### 4. Permissões no frontend (sem hardcode)

- `GET /api/auth/me` passa a incluir `desconto_max` (de `perfis`) e `rotulo`.
- Frontend: substituir `_LIMITES_NIVEL[...]` pelo `desconto_max` vindo de `/api/auth/me`
  (`_usuarioAtual.desconto_max`), cobrindo os 10 perfis sem duplicar a tabela.
- `nav-07` (Admin) visível quando `_usuarioAtual` tem `gerir_usuarios` (expor flag no
  `/api/auth/me`, ex.: `pode_gerir_usuarios`).

### 5. Documentação

- **`docs/USUARIOS.md`:** referência dos 10 perfis — rótulo, permissões (desconto, ver
  parâmetros, autorizar, gerir usuários) e responsabilidade no ciclo (resumo). Inclui
  nota de manutenção: "ao adicionar/alterar perfis, atualizar `perfis.py` e este doc".
- **Lista viva** de usuários no painel admin (seção 3).

## Fora de escopo (YAGNI)

- Aprovação financeira pelo Gerente Adm/Fin (Sub-projeto 3).
- Vínculo dos perfis operacionais às etapas do ciclo / medição (Sub-projeto 4).
- Autosserviço de troca de senha pelo próprio usuário; e-mail no cadastro (modelo não
  tem campo e-mail — manter mínimo: nome/login/senha/perfil/telefone).
- Remoção do `perfis_config.json` legado (deixar como está; não é tocado aqui).

## Verificação

- **pytest:** `perfis.py` (desconto_max e flags por perfil; slug desconhecido → 0/False);
  migração idempotente (`gerente`→`gerente_vendas`, `admin`→`diretor`); endpoints
  de usuário (criar; login duplicado rejeitado; editar perfil/telefone/ativo; reset de
  senha; gate de acesso bloqueia perfil sem `gerir_usuarios`).
- **Playwright (dados reais):** logar como Diretor → abrir painel → criar usuário,
  editar perfil, resetar senha, desativar; confirmar que um perfil sem `gerir_usuarios`
  não vê `nav-07`. Suíte completa verde.

## Processo

Pipeline superpowers: spec → plano (writing-plans) → implementação com revisão a nível
de controlador → verificação (pytest + Playwright) → merge local.
