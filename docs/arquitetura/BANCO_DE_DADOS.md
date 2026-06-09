# Banco de Dados — Omie_V3

## Visão geral

O banco usa **SQLite** via **SQLAlchemy 2.0**. A migração para MySQL é possível trocando apenas a string de conexão em `database.py`.

---

## Tabelas implementadas

### `usuarios`
Usuários do sistema com controle de acesso por nível.

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| id | Integer PK | ✓ | Auto-incremento |
| nome | String(120) | ✓ | Nome completo |
| login | String(60) | ✓ único | Login de acesso |
| senha_hash | String(64) | ✓ | SHA-256 da senha |
| nivel | String(20) | ✓ | `diretor` / `gerente` / `consultor` |
| ativo | Integer | | 1=ativo, 0=inativo |
| criado_em | DateTime | | Automático |

**Limites de desconto por nível:**
- `consultor`: 10%
- `gerente`: 20%
- `diretor`: 50%

---

### `sessoes`
Sessões ativas de usuários autenticados.

| Campo | Tipo | Descrição |
|---|---|---|
| id | Integer PK | |
| token | String(64) único | Token hex-32 do cookie |
| usuario_id | FK → usuarios | |
| criada_em | DateTime | |
| expira_em | DateTime | 8 horas após criação |
| ativa | Integer | 1=ativa, 0=encerrada |

---

### `log_autorizacoes`
Registro de todas as autorizações delegadas de desconto.

| Campo | Tipo | Descrição |
|---|---|---|
| id | Integer PK | |
| solicitante_id | FK → usuarios | Quem pediu |
| autorizador_id | FK → usuarios | Quem autorizou (null se negado) |
| desconto_solicit | Float | Desconto solicitado (%) |
| desconto_limite | Float | Limite do solicitante (%) |
| autorizado | Integer | 0=negado, 1=autorizado |
| contexto | Text (JSON) | Detalhes da negociação |
| criado_em | DateTime | |

---

### `clientes`
Cadastro de clientes com endereço completo.

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| id | Integer PK | ✓ | |
| nome | String(150) | ✓ | Nome completo |
| cpf | String(14) | ✓ único | Formato: 000.000.000-00 |
| email | String(120) | | |
| telefone | String(20) | | Formato: (12) 3811-5199 |
| whatsapp | String(20) | | Formato: (12) 98115-1998 |
| cep | String(9) | | Formato: 00000-000 |
| logradouro | String(150) | | Preenchido via ViaCEP |
| numero | String(10) | | Manual |
| complemento | String(60) | | Manual, opcional |
| bairro | String(80) | | Preenchido via ViaCEP |
| cidade | String(80) | | Preenchido via ViaCEP |
| estado | String(2) | | UF, preenchido via ViaCEP |
| observacoes | Text | | |
| omie_codigo | String(40) | | Código do cliente no Omie |
| criado_em | DateTime | | Automático |
| atualizado_em | DateTime | | Automático via onupdate |

---

### `parceiros` `[TODO]`
Cadastro de parceiros comerciais (arquitetos, designers, corretores etc.)

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| id | Integer PK | ✓ | |
| nome | String(150) | ✓ | |
| cpf_cnpj | String(18) | | CPF ou CNPJ |
| tipo | String(30) | ✓ | Ver tipos abaixo |
| email | String(120) | | |
| telefone | String(20) | | |
| whatsapp | String(20) | | |
| comissao_padrao_pct | Float | | Padrão: 0.0 |
| criado_em | DateTime | | |

**Tipos de parceiro:** `arquiteto` / `designer` / `decorador` / `corretor` / `engenheiro` / `indicador`

---

## Dados em arquivo JSON

Além do banco SQLite, alguns dados são persistidos em arquivos JSON:

### `PROJETOS/<nome_safe>/projeto.json`
```json
{
  "nome_safe": "projeto_decorado",
  "nome_projeto": "Projeto Decorado",
  "cliente": {
    "nome": "João Silva",
    "cpf": "123.456.789-00",
    "email": "joao@email.com",
    "telefone": "(12) 99999-9999"
  },
  "cliente_id": 1,
  "parceiro_id": null,
  "criado_em": "2026-06-07T10:00:00",
  "atualizado_em": "2026-06-08T15:30:00",
  "codigo_projeto_omie": null,
  "bloqueado": false,
  "margens": {
    "desconto_pct": 10.0,
    "custo_financeiro_pct": 0.0,
    "fora_da_sede": false,
    "custo_viagem": 0.0,
    "brinde": 0.0,
    "brinde_ativo": false,
    "comissao_arq_pct": 0.0,
    "comissao_arq_ativa": false,
    "fidelidade_pct": 0.0,
    "fidelidade_ativa": false,
    "incluir_custos": false
  },
  "forma_pagamento": null,
  "ambientes": [],
  "orcamentos": []
}
```

---

## Relacionamentos

```
usuarios (1) ──── (N) sessoes
usuarios (1) ──── (N) log_autorizacoes (como solicitante)
usuarios (1) ──── (N) log_autorizacoes (como autorizador)
clientes (1) ──── (N) projetos (via cliente_id no projeto.json)
parceiros (1) ─── (N) projetos (via parceiro_id no projeto.json)
```

---

## Migrações

Ao adicionar colunas a tabelas existentes, usar o padrão de migração manual:

```python
def _migrar_colunas():
    """Adiciona colunas novas sem recriar a tabela."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    colunas_novas = [
        ("clientes", "cep", "TEXT"),
        ("clientes", "logradouro", "TEXT"),
        # ...
    ]
    for tabela, coluna, tipo in colunas_novas:
        try:
            cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
        except sqlite3.OperationalError:
            pass  # Coluna já existe
    conn.commit()
    conn.close()
```

Chamar `_migrar_colunas()` no início do `init_db()`.
