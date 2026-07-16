# Lista de Projetos — Redesign (page-00)

**Status:** Aprovado para implementação — 2026-06-15

---

## Objetivo

Substituir os cards de projeto atuais por uma tabela com linhas clicáveis, adicionar status de pipeline por projeto (quente/morno/frio/convertido/perdido), filtro multi-seleção por status, e navegar automaticamente para o projeto ao criá-lo.

---

## 1. Modelo de dados — tabela `projetos`

Nova tabela SQLite via SQLAlchemy. Os projetos continuam existindo como pastas em disco; essa tabela armazena apenas metadados adicionais indexados pela chave natural `nome_safe`.

```
Projeto
  nome_safe   TEXT  PRIMARY KEY   -- mesmo valor da pasta do projeto
  status      TEXT  nullable      -- quente | morno | frio | convertido | perdido
  status_at   DATETIME nullable   -- timestamp da última mudança de status
  perdido_em  DATETIME nullable   -- preenchido apenas quando status = 'perdido'
```

### Regras de status

| Status | Origem | Observação |
|--------|--------|-----------|
| `quente` | Usuário (dropdown inline) | |
| `morno` | Usuário (dropdown inline) | |
| `frio` | Usuário (dropdown inline) | |
| `perdido` | Usuário (dropdown inline) | Grava `perdido_em = utcnow()` |
| `convertido` | Sistema automático | Setado ao concluir aprovação + exportação Omie |
| `null` | Padrão ao criar | Exibido como `—` na lista |

- `convertido` nunca é aceito via `PATCH /api/projetos/<nome_safe>/status`
- `perdido_em` é zerado se o usuário mudar o status de `perdido` para outro

### Migração

Seguir padrão de `_migrar_colunas` em `database.py`. Como é uma tabela nova (não ALTER TABLE), usar `Base.metadata.create_all(ENGINE)` — já cobre tabelas novas sem afetar as existentes.

---

## 2. Lista de projetos (page-00)

### Layout

Substitui os cards por uma tabela com linhas clicáveis. Clicar em qualquer célula da linha abre o projeto (exceto a célula de status, que abre o dropdown).

```
[Filtrar por nome, cliente ou CPF...]    [Status ▾]    [+ Novo Projeto]

 Status        Data        Projeto               Cliente          Último Orçamento
 ──────────────────────────────────────────────────────────────────────────────────
 🔥 Quente    12/06/2026  Cozinha Silva         Ana Silva        R$ 48.200,00
 ● Morno      10/06/2026  Dormitório Cardoso    João Cardoso     R$ 31.500,00
 ❄ Frio       08/06/2026  Home Office Pereira   —                —
 ✓ Convertido 05/06/2026  Suite Santos          Maria Santos     R$ 92.000,00
 ✗ Perdido    01/06/2026  Sala Lima             Pedro Lima       R$ 18.000,00
 —            15/05/2026  Quarto Infantil Ramos Cláudia Ramos    —
```

### Colunas

| Coluna | Fonte | Observação |
|--------|-------|-----------|
| Status | `Projeto.status` | Badge colorido; dropdown inline exceto "Convertido" |
| Data | `projeto.atualizado_em` | Formato DD/MM/AAAA; ordena por decrescente (padrão) |
| Projeto | `projeto.nome_projeto` | |
| Cliente | `projeto.cliente_nome` | `—` se sem cliente |
| Último Orçamento | `max(Orcamento.updated_at).valor_total` | `—` se sem orçamento salvo |

### Cores de status (rampas existentes do sistema)

| Status | Cor | Ícone |
|--------|-----|-------|
| quente | `var(--err)` coral | 🔥 |
| morno | `var(--warn)` âmbar | ● |
| frio | `var(--section)` azul | ❄ |
| convertido | `var(--ok)` teal | ✓ |
| perdido | `var(--muted)` cinza | ✗ |
| null | `var(--muted)` | — |

### Status inline

Clicar na célula de status (exceto "convertido") abre um dropdown posicionado abaixo da célula com as opções: `Quente / Morno / Frio / Perdido`. Selecionar chama `PATCH /api/projetos/<nome_safe>/status` e atualiza a linha sem recarregar a tabela.

"Convertido" é exibido como badge não interativo.

### Filtro de texto

Campo único busca simultaneamente em:
- Nome do projeto
- Nome do cliente
- CPF do cliente

Busca local no array já carregado (sem nova requisição), insensível a acentos e maiúsculas.

### Filtro multi-seleção de status

Botão `[Status ▾]` abre dropdown com checkboxes:

```
☑ Quente
☑ Morno
☑ Frio
☑ Convertido
☑ Perdido
☑ Sem status
```

Por padrão todos marcados (= mostrar tudo). Quando o usuário desmarca algum, o botão mostra quantos estão ativos: `Status (3)`. Filtra por qualquer um dos status marcados (OR lógico).

---

## 3. Fluxo de novo projeto

O formulário atual (nome + cliente + parceiro) permanece inalterado.

**Mudança:** após `criarProjeto()` bem-sucedido:
1. Sistema já cria Orçamento 1 automaticamente (comportamento existente)
2. Frontend navega diretamente para `page-02` com o orçamento ativo
3. Usuário já vê a barra de orçamentos com botões `Ambientes | Novo Ambiente | Novo Orçamento`

Não há tela intermediária — o projeto abre diretamente pronto para uso.

---

## 4. Status "Convertido" automático

Quando `aprovarOrcamento()` conclui com sucesso (exportação Omie finalizada, `d.done === true`), o backend já chama `bloquear_projeto()`. Nessa função, o status é setado para "convertido" automaticamente.

**Implementação:** o backend seta o status diretamente em `bloquear_projeto()` (já chamado ao aprovar), sem expor "convertido" via endpoint público. O frontend não precisa chamar nada extra — o status aparece na próxima vez que a lista de projetos for carregada.

---

## 5. Backend — alterações em `main.py`

### GET /projetos/buscar

Retorna campos adicionais por projeto:
```json
{
  "nome_safe": "...",
  "nome_projeto": "...",
  "cliente_nome": "...",
  "cliente_cpf": "...",
  "atualizado_em": "2026-06-12",
  "status": "quente",
  "perdido_em": null,
  "ultimo_orcamento_valor": 48200.00
}
```

`ultimo_orcamento_valor`: join com tabela `orcamentos`, pega `valor_total` do registro com `updated_at` mais recente para aquele `projeto_id`. Retorna `null` se nenhum orçamento.

`cliente_cpf`: necessário para o filtro de texto no frontend buscar por CPF.

### PATCH /api/projetos/\<nome_safe\>/status

```json
{ "status": "perdido" }
```

- Aceita: `quente | morno | frio | perdido`
- Rejeita: `convertido` (retorna 400)
- Se `perdido`: grava `perdido_em = utcnow()`
- Se mudando de `perdido` para outro: zera `perdido_em = null`
- Upsert: cria registro em `Projeto` se não existir

### bloquear_projeto() (existente em main.py)

Após bloquear o projeto em disco, adicionar:
```python
_upsert_projeto_status(nome_safe, "convertido")
```

Nova função auxiliar `_upsert_projeto_status(nome_safe, status)` faz upsert na tabela `Projeto`.

---

## 6. Critérios de aceite

- [ ] Tabela renderiza corretamente com todos os campos
- [ ] Clicar na linha abre o projeto (exceto célula de status)
- [ ] Filtro de texto busca por nome do projeto, nome do cliente e CPF simultaneamente
- [ ] Filtro de status multi-seleção funciona como OR lógico
- [ ] Dropdown inline muda status e persiste no banco
- [ ] Status "convertido" não é selecionável no dropdown
- [ ] "Perdido" grava `perdido_em`; mudar de perdido zera `perdido_em`
- [ ] Criar projeto → navega direto para negociação com Orçamento 1 ativo
- [ ] Aprovar orçamento → status setado para "convertido" automaticamente
- [ ] `ultimo_orcamento_valor` mostra valor do orçamento mais recente
