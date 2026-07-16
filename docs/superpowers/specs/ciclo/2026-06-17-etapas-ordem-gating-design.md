# Sub-projeto A — Etapas: Ordem + Gating Sequencial

**Data:** 2026-06-17
**Projeto:** Orizon Manager — Dalmóbile / Orizon Soluções
**Escopo:** Reordenar Briefing ↔ Criação do projeto; tornar o ciclo de etapas sequencial (gating); reabertura em cascata com autorização gerencial auditada.
**Parte de:** Redesenho do ciclo de vida do projeto (sub-projetos A/B/C/D). Este é o **A** — a fundação. B (cadastro completo na aprovação), C (semântica de aprovação) e D (briefing obrigatório) têm specs próprios.
**Ajusta:** `2026-06-16-bloco1-contrato-ciclo-design.md` — aquele spec assumia "briefing antes de criar o projeto"; este inverte para "criar o projeto, depois briefing" (requisito do usuário, ponto 4).

---

## 1. Contexto

O ciclo de 20 etapas (`CicloEtapa`) hoje:

- **Não tem gating sequencial** — nem no frontend (cada etapa é um card independente, `static/index.html:6218 renderCiclo`) nem no backend (`PATCH /api/projetos/<nome>/ciclo/<codigo>`, `main.py:2159` aceita qualquer etapa → qualquer status).
- Usa **códigos string** (`"1".."20"`, mais sub-etapas `"11a".."11e"`, `"17a"`), definidos em `ETAPAS_CICLO` (`static/index.html:6119`).
- Ao **criar um projeto**, marca etapas `"1","2","3"` como `"concluido"` de uma vez (`main.py:1003-1020`).
- Conclusão do **briefing** marca a etapa `"2"` (`main.py:1166` via `_marcar_etapa_cliente`).
- **Ordena por string** (`main.py:541 sorted(..., key=e.etapa_codigo)`) — bug latente: `"10"` vem antes de `"2"`.
- Já existe autorização gerencial por **credencial de usuário** (`desfazer_aprovacao`, `main.py:1835`) e auditoria de desconto em `log_autorizacoes` (`auth.py:111`, `database.py:67`). Senhas: SHA-256 (`database.py:38-42`). Níveis: `consultor | gerente | diretor | admin` (`database.py:30`).

### Decisões já validadas com o usuário
- **Renumeração real** dos códigos (não só reordenar exibição) — Opção 2.
- Gating em **todas as etapas principais** (não-sub); sub-etapas `11a-e` e `17a` ficam livres dentro do pai — alcance C.
- Reabrir etapa concluída → **cascata** (reabre as posteriores) — comportamento B.
- Cascata exige **login + senha do próprio gerente** (nível `gerente|diretor|admin`), com registro de auditoria em banco — opção A.

---

## 2. Mudança de ordem (renumeração)

A ordem de exibição passa de:

```
1 Captação · 2 Briefing · 3 Criação do projeto · 4 Primeiro orçamento · ...
```

para:

```
1 Captação · 2 Criação do projeto · 3 Briefing · 4 Primeiro orçamento · ...
```

Os **códigos** acompanham a posição: `"2" = Criação do projeto`, `"3" = Briefing`. Demais etapas (4–20, sub-etapas) **inalteradas**.

### 2.1 Migração de banco
Trocar `etapa_codigo` 2↔3 nas linhas existentes de `ciclo_etapas`. Como há `UniqueConstraint(projeto_nome, etapa_codigo)` (`database.py:262`), a troca direta colidiria. Algoritmo seguro, por projeto (idealmente numa transação):

1. `etapa_codigo = "2"` → `"_swap_2"`
2. `etapa_codigo = "3"` → `"2"`
3. `etapa_codigo = "_swap_2"` → `"3"`

A migração roda **uma vez**, idempotente: detectar se já foi aplicada (ex.: flag em tabela de versão de schema, ou verificar ausência de `"_swap_2"`). Reaproveitar o padrão de `_migrar_colunas()` já existente no projeto.

### 2.2 Pontos de código a ajustar
- **`ETAPAS_CICLO`** (`static/index.html:6119`): trocar a ordem das duas primeiras entradas e seus códigos.
- **Criação de projeto** (`main.py:1003-1020`): marcar `"1"` (Captação) e `"2"` (Criação) como `"concluido"`. **Não** marcar `"3"` (Briefing) — ver Seção 5.
- **Conclusão de briefing** (`main.py:1166`): `_marcar_etapa_cliente(cliente_id, "3", ...)` (era `"2"`).
- **Auto-complete legado** (`main.py:521-540`): continua marcando `"1".."5"` — códigos seguem válidos, sem mudança semântica relevante (todas concluídas).
- Verificar qualquer outra referência literal a `"2"`/`"3"` ligada a etapa (busca global antes de implementar).

---

## 3. Ordem canônica + gating sequencial

### 3.1 Ordem canônica
Fonte única da verdade para "qual é a etapa anterior". Lista ordenada das **etapas principais** (não-sub):

```
["1","2","3","4","5","6","7","8","9","10","11","12","13","14","15","16","17","18","19","20"]
```

Sub-etapas (`"11a".."11e"`, `"17a"`) **não** entram na cadeia de gating — são livres dentro do pai (etapa 11 / 17). Essa lista e os helpers de gating ficam num **novo módulo `mod_ciclo.py`** (fonte única da verdade no backend), espelhando a ordem do `ETAPAS_CICLO` do frontend.

### 3.2 Regra de gating
> Uma etapa principal `N` só pode passar para `em_andamento` ou `concluido` se a etapa principal **imediatamente anterior** na ordem canônica estiver `concluido`.

- A "etapa corrente" = primeira etapa principal não concluída. É a única acionável.
- Sub-etapas não são bloqueadas pela regra (livres dentro do pai).
- Etapa 1 (Captação) não tem anterior → sempre liberada.

### 3.3 Backend (camada rígida)
- **`PATCH /api/projetos/<nome>/ciclo/<codigo>`** (`main.py:2159`): se `<codigo>` é etapa principal e a anterior não está `concluido`, **rejeitar** com HTTP 400 e mensagem clara (`"Conclua a etapa anterior (<nome>) antes de iniciar esta."`). Sub-etapas isentas.
- **Endpoints de ação** que avançam etapas (ex.: geração de contrato = etapa 7, `main.py:2039`): validar o gating antes de executar a ação.
- Corrigir a **ordenação** (`main.py:541`): ordenar pela posição na ordem canônica (ou parse numérico robusto que trate sufixos `a-e`), eliminando o bug `"10"` antes de `"2"`.

### 3.4 Frontend (camada visual)
- `renderCiclo` (`static/index.html:6218`): além de `concluido/em_andamento/pendente`, derivar um estado **`bloqueado`** = etapa principal cuja anterior não está concluída.
- Etapa bloqueada: ícone 🔒, card não-expansível (ou expansível só-leitura), botões de ação/toggle desabilitados.
- Só a "etapa corrente" mostra ações ativas.

### 3.5 Helper testável
Extrair a lógica de gating numa função pura, ex.:
`proxima_acao_permitida(codigo, ciclo_por_codigo) -> bool` e
`etapa_anterior(codigo) -> str | None`,
para teste unitário independente do servidor HTTP.

---

## 4. Reabertura em cascata com autorização gerencial

### 4.1 Comportamento
Reabrir uma etapa principal concluída `N` → todas as principais posteriores (`N+1..20`, na ordem canônica) voltam a `"pendente"` (limpa `concluido_em`, `iniciado_em`, `responsavel_id`). Sub-etapas das posteriores também são resetadas junto com o pai.

### 4.2 Autorização
A reabertura exige um **modal de autorização**: o gerente digita **login + senha**. Validação (reaproveitando o padrão de `desfazer_aprovacao`, `main.py:1842-1850`):
- Usuário existe, ativo, e `check_senha` confere (SHA-256).
- `nivel ∈ {gerente, diretor, admin}`.

### 4.3 Trava de segurança
Se a cascata fosse reabrir uma etapa que desfaz um **contrato `assinado` ou `vigente`** (etapa 7 já assinada), **bloquear** com mensagem — igual `desfazer_aprovacao` já faz (`main.py:1854`). Protege contra zerar contrato assinado.

### 4.4 Auditoria (nova tabela)
Criar `log_acoes_gerenciais` (genérica, para ações destrutivas autorizadas):

| campo | tipo | descrição |
|---|---|---|
| `id` | Integer PK | |
| `solicitante_id` | FK usuarios | quem pediu (consultor logado) |
| `autorizador_id` | FK usuarios | gerente que autorizou |
| `acao` | Text | ex.: `"reabrir_cascata"` |
| `projeto_nome` | Text | projeto afetado |
| `etapa_alvo` | Text | código da etapa reaberta |
| `contexto` | Text (JSON) | etapas resetadas, status anterior |
| `criado_em` | DateTime | timestamp |

Endpoint novo (ou estender existente), ex.: **`POST /api/projetos/<nome>/ciclo/<codigo>/reabrir`** com `{login, senha}`. Em sucesso, grava o log e executa a cascata numa transação.

> Observação: `desfazer_aprovacao` (reset das etapas 6/7) hoje **não** audita. Fica como melhoria opcional alinhá-lo a `log_acoes_gerenciais` — fora do escopo mínimo deste sub-projeto, anotado aqui.

---

## 5. Ajuste do auto-marcar na criação de projeto

Hoje criar projeto marca `"1","2","3"` concluídas. Com a nova ordem e o gating:

- Marcar **`"1"` (Captação)** — cliente já cadastrado.
- Marcar **`"2"` (Criação do projeto)** — acabou de ser criado.
- **Não** marcar **`"3"` (Briefing)** — fica `pendente` e vira a "etapa corrente".

Assim o gating aponta naturalmente para o Briefing como próximo passo. **Obrigar** o preenchimento do briefing (impedir avançar ao 1º orçamento sem ele) é responsabilidade do **Sub-projeto D**; aqui apenas garantimos que o Briefing não nasça "concluído sozinho".

---

## 6. Testes

Testes automáticos (pytest, padrão do projeto em `tests/`) escritos **antes** da implementação:

1. **Ordem canônica / etapa anterior** — `etapa_anterior("4") == "3"`, `etapa_anterior("1") is None`, sub-etapas tratadas (ex.: `"11b"` não quebra).
2. **Gating** — não permite concluir etapa `N` com anterior pendente; permite quando anterior concluída; sub-etapas isentas.
3. **Ordenação correta** — lista ordenada coloca `"2"` antes de `"10"`.
4. **Cascata de reabertura** — reabrir `"2"` reseta `"3".."20"` para pendente; preserva etapas anteriores; reseta sub-etapas dos pais afetados.
5. **Autorização** — cascata sem credencial válida de gerente é rejeitada; com gerente válido, executa e grava `log_acoes_gerenciais`.
6. **Trava de contrato assinado** — cascata que desfaria contrato `assinado`/`vigente` é bloqueada.
7. **Migração** — após migrar, projeto que tinha `"2"=briefing,"3"=criação` passa a `"2"=criação,"3"=briefing`; idempotente (rodar 2× não corrompe).

---

## 7. Fora de escopo (outros sub-projetos)

- **B** — validação de cadastro completo na aprovação + popup "Cadastro Incompleto" + contrato pré-preenchido (a função `validar_cliente_para_contrato` em `mod_contrato.py` já foi criada como building block).
- **C** — "Aprovar Orçamento" conclui Revisão+Aprovação juntas; 1º orçamento concluído por ≥1 XML; renomear/tornar clicável "orçamento aprovado – assinar contrato".
- **D** — Briefing obrigatório após criação do projeto antes do 1º orçamento.

---

## 8. Arquivos afetados (estimativa)

| Arquivo | Mudança |
|---|---|
| `database.py` | nova tabela `LogAcaoGerencial` |
| `mod_ciclo.py` (novo) | ordem canônica + helpers de gating (testáveis) |
| `main.py` | migração 2↔3; gating no `PATCH /ciclo`; novo endpoint `reabrir`; ajuste auto-marcar criação; ajuste marca briefing; fix ordenação |
| `static/index.html` | `ETAPAS_CICLO` reordenado; estado `bloqueado` + 🔒 em `renderCiclo`; modal de autorização gerencial; cascata na UI |
| `tests/test_ciclo.py` (novo) | testes das Seções 6 |
