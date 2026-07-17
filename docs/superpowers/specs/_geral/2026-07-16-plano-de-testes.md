# Plano de Testes — Orizon Manager | Dalmóbile

**Data:** 2026-07-16 · **Go-live de produção:** 01/08/2026 (4 lojas + 1 PDV configurados)

Define a nomenclatura dos ambientes, a disciplina de git/promoção entre eles, o papel de cada
ambiente no ciclo de testes e o formato dos roteiros de pré-homologação para usuários leigos.
Documentos irmãos:
- **Frentes de trabalho:** `2026-07-16-frentes-de-trabalho.md` (segmentação para devs em paralelo).
- **Roteiros de pré-homologação:** arquivos `roteiro-PH-*.md` (um por fluxo) — o *template* está aqui
  (Seção 4); os roteiros completos vivem em arquivos separados.

---

## 1. Nomenclatura e ambientes

Quatro ambientes, do menos ao mais protegido. Cada push tem um destino claro.

| # | Ambiente | Onde | Banco | Quem usa / propósito | Como atualiza |
|---|----------|------|-------|----------------------|---------------|
| 1 | **DEV (local)** | `localhost:8765` na máquina de cada dev | SQLite (`orizon.db`) | Cada dev: testes rápidos + **Vera** (QA principal) | Manual, local |
| 2 | **INTEGRAÇÃO** | `167.88.33.121:8765` — instância A | Postgres | Devs descentralizados: integração contínua | **Auto** do `main` |
| 3 | **PRÉ-HOMOLOGAÇÃO** | `167.88.33.121:8766` — instância B (serviço + DB próprios) | Postgres | Leigos executando roteiros: aceite formal | **Tag fixada**, gated por você |
| 4 | **PRODUÇÃO** | `orizonsolution.com.br` (`179.197.77.9`) | Postgres | Dados reais; go-live 01/08/2026 | **Tag**, deploy manual, protegido |

**Fluxo do código:** `feature branch → main (INTEGRAÇÃO) → tag → PRÉ-HOMOLOGAÇÃO → mesma tag → PRODUÇÃO`.

### Notas de arquitetura
- **INTEGRAÇÃO e PRÉ-HOMOLOGAÇÃO convivem no mesmo servidor antigo (`167.88.33.121`)** como duas
  instâncias isoladas (serviços/portas + bancos separados). Isso separa dois propósitos que conflitam:
  a integração é instável por natureza (vários devs empurrando código); a pré-homologação precisa de um
  build **parado e estável** para o leigo não tropeçar num bug recém-introduzido por outro dev.
- **Paridade com produção:** a pré-homologação roda **Postgres**, igual à prod — não SQLite. O motivo é o
  motor contábil de partida dobrada (razão da migração para Postgres): constraint e transação se comportam
  diferente, e queremos pegar isso *antes* da prod. Ver
  `docs/superpowers/specs/_geral/2026-07-15-migracao-postgresql.md`.
- **Produção é 100% protegida:** nenhum teste destrutivo, sem acesso SSH compartilhado dos devs, deploy
  só de tag aprovada. A "camada extra de pré-homologação" prevista (servidor dedicado) pode nascer depois
  promovendo a instância B para uma VPS própria, sem mudar este conceito.

### Levantar a instância B (PRÉ-HOMOLOGAÇÃO) — CÓDIGO PRONTO, falta provisionar
Os dois pré-requisitos de **código** estão implementados e na `main` (2026-07-16):
1. ✅ **Porta parametrizável** — `ORIZON_PORT` (default 8765) em `main.py` (`porta_do_ambiente`). B sobe com
   `ORIZON_PORT=8766`. Valor inválido/fora de faixa → erro claro no bootstrap.
2. ✅ **Banco separado por instância** — `database._resolver_config_db`: com `DATABASE_URL=sqlite:///<arquivo>`,
   `DB_PATH` segue o arquivo, então as migrações `sqlite3` não tocam o `orizon.db` da instância A
   (contaminação cruzada). Postgres também isola (via `DATABASE_URL`).

**Falta (não é código):** provisionar a instância B no servidor `167.88.33.121` — clone separado
`/root/orizon-homolog` na tag de homolog, `:8766`, banco próprio. **Runbook pronto** em `DEV_RULES.md`
(subseção "Instância B — PRÉ-HOMOLOGAÇÃO (:8766)"). Precisa de sessão SSH interativa (não automatizável
sem risco no servidor compartilhado).

**Paridade:** a ponte é um **SQLite separado** (isola já, sem instalar Postgres no servidor antigo); o alvo
da spec é **Postgres** na homolog — trocar a `DATABASE_URL` por um Postgres dedicado quando o servidor
antigo migrar. Ver `2026-07-15-migracao-postgresql.md`.

---

## 2. Disciplina de git e promoção

Regras **obrigatórias**. O agente (Claude) deve **travar** qualquer tentativa de furá-las — não só avisar.

### Obrigatório
1. Todo trabalho sai de uma **feature branch** nomeada pela frente (`feat/A-…`, `feat/C-…`, `docs/…`).
2. Antes de **merge no `main`**: suíte verde (`python3 -m pytest -q`) + `test_arquitetura_modulos` +
   passagem da **Vera** em área sensível.
3. `main` sempre **deployável**. INTEGRAÇÃO auto-atualiza dele.
4. PRÉ-HOMOLOGAÇÃO e PRODUÇÃO só sobem **build tagueado** (`git tag`), nunca commit solto.
5. Push para **PRODUÇÃO** exige, em ordem: suíte verde → Vera → **backup de prod** → **autorização
   explícita do responsável**.

### Bloqueado (o agente recusa e nomeia a regra violada)
- Commit direto no `main` sem branch/PR.
- Deploy de build **não-tagueado** em homolog ou prod.
- **Pular a pré-homologação** e ir direto do `main` para a prod.
- Push para prod sem suíte verde + Vera + backup.
- `git add .` / commit de ruído (`orizon.db`, `perfis_config.json`, `.claude/…`, `XML/…`, `*.bak`, `*.tmp`).

---

## 3. Papel de cada ambiente no teste

| Ambiente | O que se testa aqui | Responsável |
|----------|---------------------|-------------|
| **DEV local** | Testes rápidos do dev + **QA principal pela Vera**: backend (pytest/TDD), fluxo de telas do frontend, tema claro/escuro, simulação financeira ponta a ponta com dados reais | Dev + Vera |
| **INTEGRAÇÃO** | Que o código de vários devs **convive** (sem quebra de import/rota/arquitetura). Não é onde o leigo testa. | Devs |
| **PRÉ-HOMOLOGAÇÃO** | **Aceite formal**: leigos executam os roteiros num build parado, com dados previsíveis | Leigos + você |
| **PRODUÇÃO** | Nada destrutivo. Só operação real. | — |

**Vera não substitui a pré-homologação e vice-versa:** a Vera cobre o *sistema* (regressão técnica,
regras de negócio, financeiro); o leigo cobre a *usabilidade real* (se uma pessoa sem treino consegue
executar a tarefa seguindo a tela). São camadas complementares.

---

## 4. Formato dos roteiros para leigos (template)

Cada cenário segue este template, em **linguagem 100% leiga, clique a clique**. Os roteiros completos
ficam em arquivos separados (`roteiro-PH-<fluxo>.md`), um por fluxo.

| Campo | Conteúdo |
|-------|----------|
| **ID / Cenário** | Identificador + título curto. Ex.: `PH-01 — Cadastrar uma loja` |
| **Persona** | Qual usuário-tipo e nível (Consultor / Gerente / Admin) executa |
| **Pré-condições** | O que já precisa existir antes de começar |
| **Passos** | Numerados, ação literal: *"Clique em X", "Digite Y no campo Z"* |
| **Resultado esperado** | O que conferir, em qual tela/módulo, para dizer que deu certo |
| **Registro** | Testador marca ✅ OK / ❌ NOK + observação |

**Fluxo do processo:** o agente **gera** os roteiros → o leigo **executa** → o resultado alimenta o
**aceite**. A Vera valida o build no DEV *antes* de ele virar tag e chegar à pré-homologação.

### Escopo dos roteiros para o go-live de 01/08
Cobertura **obrigatória** (aceite leigo):
1. **Setup de loja/rede + usuários** — criar as 4 lojas + 1 PDV (tenancy), níveis de usuário, escopo por
   projetista. Pré-requisito de tudo. → `roteiro-PH-setup-loja-usuarios.md`
2. **Ciclo de venda ponta a ponta** — projeto → orçamento (EP07) → negociação → proposta (PDF) →
   contrato (PDF + assinatura) → etapas do ciclo. → `roteiro-PH-ciclo-venda.md`

Fora do aceite leigo nesta fase (seguem cobertos pela Vera no DEV, viram roteiros numa fase 2):
**Fiscal (NF-e)** e **Fechamento contábil / conciliação final**.

---

## 5. Checklist de prontidão do go-live (01/08/2026)

### Por loja (×4) + PDV
- [ ] Loja/tenancy cadastrada (rede, loja, vínculo `usuario_lojas`).
- [ ] Usuários criados com níveis corretos (Consultor / Gerente / Admin) e escopo por projetista.
- [ ] Modelo de documento/contrato **ativo** por loja (`documento_modelos`, versão imutável).
- [ ] Parâmetros mínimos de operação preenchidos (orçamento/margens/negociação).
- [ ] PDV configurado e vinculado à loja correta.

### Critérios de promoção PRÉ-HOMOLOGAÇÃO → PRODUÇÃO
- [ ] **Todos** os roteiros marcados ✅ OK.
- [ ] **Zero** bug bloqueante em aberto.
- [ ] Build **tagueado** aprovado pela **Vera** (suíte verde + `test_arquitetura_modulos`).
- [ ] **Backup de produção** feito antes do deploy.
- [ ] Autorização explícita do responsável.

---

## Rastreabilidade
- Migração Postgres (base da paridade): `2026-07-15-migracao-postgresql.md`.
- Runbook de deploy e servidores: `DEV_RULES.md` (seções de servidor DEV e produção).
- Segmentação para trabalho paralelo: `2026-07-16-frentes-de-trabalho.md`.
