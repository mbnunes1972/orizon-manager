# Multi-tenant — F1: Fundação de dados (redes, lojas, tenant columns)

**Data:** 2026-06-20
**Status:** spec aprovado (aguardando revisão do usuário antes do plano)
**Origem:** pedido "configurador de lojas" (pendência do contrato) que, ao ser explorado,
revelou a intenção de uma **plataforma multi-tenant com isolamento total**
(`Plataforma → Rede → Loja`).

---

## Contexto do programa (visão de várias fases)

O sistema hoje é **single-tenant**: usuários, clientes, projetos, orçamentos, parceiros e
contratos são globais, sem nenhum conceito de loja. Os dados da loja que vão ao contrato
(nome, CNPJ, telefone, e-mail, testemunhas, código de 3 letras) são **constantes hardcoded**
em `mod_contrato.py` (`_NOME_EMPRESA`, `_CNPJ_EMPRESA`, `_TELEFONE_LOJA`, `_EMAIL_LOJA`,
`_TESTEMUNHAS`, `_CODIGO_LOJA = "INS"`).

A visão alvo é multi-tenant, com 3 níveis de administração:

```
Plataforma (super-admin)
 ├─ Rede A (admin de rede)
 │   ├─ Loja A1 (diretor)  → usuários, clientes, projetos, parceiros, contratos
 │   └─ Loja A2 (diretor)
 ├─ Rede B …
 └─ Loja avulsa X (rede_id = NULL; diretor)
```

**Decisão de arquitetura:** schema único (SQLite) com **coluna de tenant** (`loja_id`/`rede_id`)
nas tabelas e escopo por query. Sem banco-por-tenant.

**Decomposição em fases (cada uma com seu próprio ciclo spec → plano → implementação):**

- **F1 (este spec) — Fundação de dados.** Tabelas `redes`/`lojas`, modelo de parceiros M:N,
  colunas de tenant + backfill. **Puramente aditivo: zero mudança de comportamento.**
- **F2 — Perfis e CRUD de tenancy.** Perfis `super_admin`/`admin_rede`; painel de redes/lojas;
  atribuição de usuários a lojas; UX de cadastro de parceiro (abrangência gateada).
- **F3 — Contrato puxa da loja.** `mod_contrato.py` deixa as constantes e usa a loja do
  usuário; numeração `CODIGO-AAAA-MM-DD-SEQ` por loja.
- **F4 — Isolamento.** Contexto de tenant na sessão; escopo por loja/rede em todas as
  listagens e mutações; testes de vazamento entre tenants. (Maior risco; entra por último.)

Este spec cobre **somente a F1**.

---

## Objetivo da F1

Preparar todo o schema para multi-tenant **sem alterar nenhum comportamento observável**.
Após a F1, o app roda idêntico ao de hoje (mesmas telas, mesmo contrato, mesma listagem
global), porém:

- existem as tabelas `redes`, `lojas`, `parceiro_lojas`;
- as entidades de topo têm `loja_id` preenchido;
- existe uma **loja seed** com os dados das constantes atuais;
- todos os dados e usuários existentes ficam vinculados a essa loja seed.

Isso torna a F4 (isolamento) uma questão de **adicionar `WHERE loja_id = …`** em vez de
re-migrar dados.

---

## Não-objetivos da F1 (explícitos)

- **Sem isolamento.** Nenhuma query passa a filtrar por loja/rede. Listagens continuam globais.
- **Sem CRUD/UI** de redes e lojas. (F2)
- **Sem novos perfis** (`super_admin`/`admin_rede`). (F2)
- **`mod_contrato.py` intacto** — continua usando as constantes. A loja seed já carrega os
  mesmos valores, mas a troca da fonte é na F3.
- **Sem UX de abrangência de parceiro.** O schema existe; a tela é F2.

---

## Modelo de dados

### Tabelas novas

**`redes`**
| coluna | tipo | nota |
|---|---|---|
| id | Integer PK | |
| nome | String(150) NOT NULL | |
| cnpj | String(18) nullable | |
| ativo | Integer default 1 | |
| criado_em | DateTime default utcnow | |

**`lojas`**
| coluna | tipo | nota |
|---|---|---|
| id | Integer PK | |
| rede_id | Integer FK→redes nullable | **NULL = loja avulsa** |
| nome | String(150) NOT NULL | |
| cnpj | String(18) nullable | |
| codigo | String(8) | **3 letras**, usado na numeração do contrato; UNIQUE |
| telefone | String(20) nullable | |
| email | String(120) nullable | |
| cep, logradouro, numero, complemento, bairro, cidade, estado | (espelha `clientes`) | endereço da loja |
| testemunha1_nome | String(120) nullable | |
| testemunha1_cpf | String(14) nullable | |
| testemunha2_nome | String(120) nullable | |
| testemunha2_cpf | String(14) nullable | |
| ativo | Integer default 1 | |
| criado_em | DateTime default utcnow | |

> `codigo` é UNIQUE porque a sequência de número de contrato (`gerar_num_contrato`) é
> contínua **por código de loja**. Restrição aplicada no nível da app (validador em F2);
> na F1 a loja seed usa `"INS"`.

**`parceiro_lojas`** (vínculo M:N parceiro × loja)
| coluna | tipo | nota |
|---|---|---|
| id | Integer PK | |
| parceiro_id | Integer FK→parceiros NOT NULL | |
| loja_id | Integer FK→lojas NOT NULL | |
| comissao_padrao_pct | Float default 0.0 | comissão **por loja** |
| ativo | Integer default 1 | |

### Colunas adicionadas a tabelas existentes (todas nullable no banco; backfill no mesmo passo)

- `usuarios.loja_id` (FK→lojas, nullable) e `usuarios.rede_id` (FK→redes, nullable)
  - usuário de loja → `loja_id` setado; `admin_rede` (F2) → só `rede_id`; `super_admin` (F2) → ambos NULL.
- `clientes.loja_id`
- `projetos_meta.loja_id`
- `orcamentos.loja_id`
- `contratos.loja_id`
- `parceiros.rede_id` (FK→redes, nullable) — dono/escopo do parceiro
- `parceiros.abrangencia` (String(10), default `'loja'`) — `'loja'` | `'rede'`

> A `comissao_padrao_pct` já existente em `parceiros` é mantida como **default para parceiros
> de abrangência `'rede'`**; para abrangência `'loja'`, a comissão efetiva vem do vínculo.

### Tabelas-filhas NÃO recebem `loja_id`

`briefings`, `medicoes`, `pool_ambientes`, `orcamento_ambientes`, `contratos_assinaturas`
são sempre acessadas via o projeto/orçamento/contrato pai e herdam o escopo dele na F4.
Denormalizamos `loja_id` apenas nas entidades de topo consultadas diretamente
(`usuarios`, `clientes`, `projetos_meta`, `orcamentos`, `contratos`, `parceiros`).

### Modelo de parceiros — casos cobertos

| Caso | Representação |
|---|---|
| Cada loja tem seu parceiro | `abrangencia='loja'` + 1 vínculo em `parceiro_lojas` |
| Mesma pessoa em 2 lojas (mesma rede/avulsa) | **1** `parceiro` + **2** vínculos |
| Parceiro global da rede | `abrangencia='rede'` → visível a todas as lojas da `rede_id` (inclusive futuras) |
| Segmentar dentro da rede | `abrangencia='loja'` + vínculos só com as lojas escolhidas |
| Comissão diferente por loja | `comissao_padrao_pct` no vínculo |

**Fronteira de isolamento:** o parceiro pertence a uma **rede** (ou a uma **loja avulsa**,
quando `rede_id` é NULL). Uma loja da Rede A nunca enxerga parceiros da Rede B. A dedupe
"mesma pessoa, duas lojas" só vale **dentro da mesma rede/loja-avulsa** — entre tenants
diferentes, a mesma pessoa física vira cadastros separados (correto p/ isolamento).
A aplicação efetiva dessa visibilidade é F4; a F1 só cria a estrutura.

---

## Migração

Segue o padrão existente em `database.py`:

- **`_migrar_colunas()`** (schema, idempotente via `PRAGMA table_info`): cria as tabelas novas
  (`Base.metadata.create_all` já cobre, pois os models são novos) e adiciona as colunas novas
  às tabelas existentes (`usuarios`, `clientes`, `projetos_meta`, `orcamentos`, `contratos`,
  `parceiros`).
- **`_run_migracoes()`** (dados, idempotente, rastreado em `schema_migrations`): nova migração
  **`tenancy_v1_2026`**:
  1. Se ainda não existe nenhuma loja, cria a **loja seed** a partir das constantes de
     `mod_contrato.py`:
     `nome=INSPIRIUM MOVEIS PLANEJADOS E DECORACAO LTDA`, `cnpj=19.152.134/0001-56`,
     `codigo="INS"`, `telefone="(12) 3341-8777"`, `email="sac@dalmobilesjc.com.br"`,
     testemunhas (`Jaime Perinazzo` / `Felipe Guizalberte`, **CPFs placeholder `xxx…` —
     a corrigir na F2**), `rede_id=NULL` (avulsa).
  2. Backfill: todo `usuarios`/`clientes`/`projetos_meta`/`orcamentos`/`contratos` existente
     com `loja_id` NULL recebe o id da loja seed.
  3. Backfill de parceiros: cada `parceiros` existente recebe `rede_id=NULL`,
     `abrangencia='loja'`, e **um** vínculo em `parceiro_lojas` com a loja seed, copiando a
     `comissao_padrao_pct` atual para o vínculo.
  4. Grava `tenancy_v1_2026` em `schema_migrations`.

**Idempotência:** rodar `init_db()`/a migração duas vezes não duplica a loja seed nem os
vínculos (guardas por `schema_migrations` + checagem "nenhuma loja existe").

### `seed.py`

`seed.py` (criação dos 10 usuários-exemplo do zero) passa a criar a loja seed **antes** dos
usuários e a vinculá-los a ela (`loja_id`). Mantém saída ASCII-safe. Em banco já existente, a
migração `tenancy_v1_2026` cobre o backfill; em banco novo via `seed.py`, a loja já nasce.

---

## Arquivos afetados

- `database.py` — models `Rede`, `Loja`, `ParceiroLoja`; colunas novas nos models existentes;
  `_migrar_colunas` (colunas); `_run_migracoes` (migração `tenancy_v1_2026`).
- `seed.py` — cria a loja seed e vincula os usuários.
- **Nenhuma rota nova, nenhuma mudança em `main.py`, `mod_contrato.py`, `static/index.html`.**
  (A F1 não expõe nada na UI nem na API.)

---

## Verificação

**pytest (novos testes):**
- Migração `tenancy_v1_2026` é **idempotente** (rodar 2× → 1 loja seed, 1 vínculo por parceiro).
- Colunas criadas em todas as tabelas-alvo (`PRAGMA table_info`).
- Loja seed carrega exatamente os valores das constantes (`codigo="INS"`, CNPJ, etc.).
- Backfill: nenhum registro de topo fica com `loja_id` NULL após a migração.
- Parceiro existente → exatamente 1 vínculo, `comissao_padrao_pct` copiada, `abrangencia='loja'`.
- `seed.py` em banco limpo: 10 usuários todos com `loja_id` da loja seed.

**Regressão (manual/Playwright):** app sobe; login, listagem de projetos, geração de contrato
e listagem de parceiros funcionam **idênticos** ao de hoje; 0 erros de console.

**Critério de pronto:** suíte verde (atual 157 + os novos) e nenhuma regressão observável.

---

## Riscos e mitigação

- **SQLite `ALTER TABLE ADD COLUMN` não aceita NOT NULL sem default prático** → colunas de
  tenant entram **nullable**; a obrigatoriedade é lógica (app) e só passa a importar na F4.
- **Ordem de criação na migração** (loja antes do backfill; FK) → a migração cria a loja,
  pega o id e só então faz os `UPDATE`/inserts de vínculo, tudo na mesma transação.
- **Bancos parciais/antigos** → guarda `_tabela_existe` antes de cada `UPDATE` (padrão já usado).
- **Escopo "rastejar" para F2/F4** → este spec congela F1 em "aditivo + backfill"; qualquer
  isolamento/UI é explicitamente fora de escopo.
