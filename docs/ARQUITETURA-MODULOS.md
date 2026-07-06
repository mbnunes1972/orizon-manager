# Arquitetura de Módulos — Orizon Manager | Dalmóbile

> **Documento vivo · 2026-07-06.** Mapa lógico dos módulos do sistema — a taxonomia de "onde mora cada
> coisa" e "onde mora código novo". **Não é um plano de refatoração:** nada de código se move por causa
> deste doc; ele nomeia fronteiras sobre o código que já existe (monolito `main.py` + `database.py` de
> schema único + `~20 mod_*.py`) e guia o que vem. Atualize-o ao criar/mover um módulo.

## Por que existe

Sem um mapa explícito, cada peça nova (auth, orçamento EP-07, Total Flex, fiscal) virou um fragmento
ad-hoc. Este documento resolve três coisas: (1) **onde colocar código novo** sem inventar padrão a cada
vez; (2) tornar visível o que **já existe vs. é lacuna**; (3) habilitar a **venda a topologias diferentes**
— ligar/desligar módulos de domínio por cliente (uma loja avulsa não precisa de Rede nem de Produção pesada).

## Forma: dois níveis

```
┌─ MÓDULOS DE DOMÍNIO (ligáveis/desligáveis por cliente) ───────────────┐
│  Cadastro · Comercial · Produção/Projetos · Fiscal · Estoque ·        │
│  Expedição/Logística · Financeiro · Pós-venda                         │
└───────────────────────────────────────────────────────────────────────┘
              usa ▼ (nunca o contrário)
┌─ NÚCLEO / PLATAFORMA (transversal, sempre ligado) ────────────────────┐
│  Auth · Tenancy/Rede · Auditoria · Ciclo (orquestrador) · Integrações │
└───────────────────────────────────────────────────────────────────────┘
```

**Regra de dependência:** domínio depende do Núcleo; o Núcleo **não** depende de domínio; módulos de
domínio referenciam-se por **Cadastro** e são orquestrados pelo **Ciclo** — não se chamam livremente.

---

## Núcleo / Plataforma (transversal — não desligável)

| Camada | Arquivos / tabelas hoje | Papel |
|---|---|---|
| **Auth** | `mod_usuarios`, `perfis.py`; `usuarios`, `sessoes` | identidade + capabilities (`perfis.pode(nivel, cap)`) |
| **Tenancy / Rede** | `mod_tenancy`; `redes`, `lojas`, `usuario_lojas`, `parceiro_lojas` | escopo multi-loja/rede — **é o que torna os domínios ligáveis por cliente** |
| **Auditoria** | `log_autorizacoes`, `log_acoes_gerenciais` | trilha de autorizações e ações gerenciais |
| **Ciclo (orquestrador)** | `mod_ciclo`; `ciclo_etapas`, `ciclo_documentos`, `ciclo_revisoes` | máquina de estados (etapas 1→20, com sub-etapas) que **sequencia os domínios** por **faixas de titularidade** (ver Governança do Ciclo); docs/revisões são o artefato genérico do ciclo. **É o "event flow" pronto — não introduzir event bus.** |
| **Integrações** | `emissor_fiscal` (contrato **ABC**), `focus_client`/`focus_config`, `mod_omie` (legado); *futuros* Promob parser, Evolution/WhatsApp, n8n | todo client HTTP externo vira **adapter** aqui; a abstração (ex.: `EmissorFiscal`) mora no Núcleo, a implementação de domínio mora no módulo |

---

## Módulos de domínio (ligáveis por cliente)

Status: **EXISTE** (implementado) · **PARCIAL** (parte feita) · **NOVO** (a modelar do zero).

### 1. Cadastro — base referenciada, nunca duplicada
- **Hoje:** `clientes`, `parceiros` (ex.: Arch Decor Points BH). **EXISTE.**
- **Lacuna central:** **Catálogo de Produtos/Serviços não tem tabela** — produto hoje é implícito no XML
  Promob e em `orcamento_ambientes` (código-base + peças sob medida `cProd[ID]`). Modelar o catálogo é
  **pré-requisito do Estoque** (cada peça cortada precisa de identidade de produto). **PARCIAL/NOVO.**
- **Nota de fronteira:** Colaboradores/Consultores = **Auth** (`usuarios`); Lojas/CNPJs = **Tenancy**.
  Cadastro não os duplica — referencia.

### 2. Comercial — Vendas / Compras / Negociação
- **Vendas (EXISTE, rico):** `mod_orcamento_params`, `mod_margens`, `mod_negociacao`, `mod_proposta`,
  `mod_contrato`; `briefings`, `pool_ambientes`, `orcamentos`, `orcamento_ambientes`, `contratos`,
  `contratos_assinaturas`. Orçamento EP-07, proposta, negociação/desconto, contrato.
- **Compras (NOVO):** triangulação **fábrica (Dal Mobile) → rede** — o fluxo em desenho; a NF-e da fábrica
  (`mod_nfe` parser) é o documento de entrada dessa compra.
- **Costura:** **Total Flex** (motor de financiamento) mora aqui como *condição financeira* da venda; o
  **recebível resultante** é do Financeiro.

### 3. Produção / Projetos — o diferencial competitivo
- **Hoje (PARCIAL):** subfases do PE (`mod_ciclo` etapas 11a–e), `mod_medicao` + `medicoes`, `mod_arvore`,
  `mod_qualidade_xml` (validação do XML), parser de `mod_nfe`. Papéis Projetista Executivo/Medidor (Auth).
- **Lacuna:** motor de **corte paramétrico** (projeto Finep) — gera as peças `cProd[ID]`. **NOVO.**
- **Nota:** o `mod_ciclo` é bifronte — a **orquestração** (máquina de etapas) é Núcleo; o **domínio de PE**
  (subfases, medição, projeto executivo) é Produção.

### 4. Fiscal — NF-e/NFS-e + obrigações
- **Hoje (EXISTE, recém):** `mod_fiscal`, `mapa_fiscal`, `emissor_focus`, `fiscal_cripto`, `nfe_emissao`,
  pricing/preview de `mod_nfe`; `perfil_fiscal`, `nfe_emissao`. Emissão via `EmissorFiscal`(Núcleo)+`focus_client`.
- **Lacuna (NOVO):** SPED Fiscal (restrição de design já citada), CC-e, cancelamentos/eventos completos, NFS-e real.
- **Costura:** **`perfil_fiscal`** é config fiscal por CNPJ (1:1 com `loja`) — mora no Fiscal, chaveado pela
  loja (Tenancy). **`mod_nfe`** é compartilhado: **parser** de `cProd[ID]` = Produção, **pricing/preview** = Fiscal.

### 5. Estoque — NOVO (zero hoje)
- Saldo, **reserva** (consumida pelo Comercial na venda), **baixa** (consumida pelo Fiscal na NF-e),
  reconciliação. **Rastreabilidade peça-a-peça:** cada `cProd[ID]` de peça cortada é um item de estoque de
  rastreio único — modelagem de Estoque, acoplada ao paramétrico (Produção) e ao Catálogo (Cadastro).
- **Neste doc:** entra só como **fronteira (stub)**; design interno depois (YAGNI).

### 6. Financeiro — Plano de contas / DRE / Financeiras
- **Hoje (PARCIAL):** `mod_provisoes` + `provisao_registro`; Total Flex (motor).
- **Lacuna (NOVO):** plano de contas, contas a pagar/receber, conciliação bancária, DRE, Balanço.
  Contratos → recebíveis; movimentações → DRE.

### 7. Pós-venda — NOVO (zero hoje)
- Assistência técnica (reporta direto ao Diretor — governança), garantia, trocas, devoluções.
- **Cruzamentos:** Fiscal (nota de devolução) + Estoque (retorno de mercadoria).
- **Neste doc:** só **fronteira (stub)**.

### 8. Expedição / Logística — NOVO (módulo fino + faixa do Ciclo)
Dono operacional das etapas logísticas (12–16 — ver **Governança do Ciclo**). É ao mesmo tempo uma **faixa**
que orquestra outros módulos e um **módulo fino** com um núcleo próprio: agendamento de entrega, **expedição**
e **conhecimento de transporte (CT-e)** — atividades que hoje não têm casa (não são de Estoque, Fiscal nem
Compras).

**⚠️ Disciplina de fronteira (regra explícita — módulo-agregador tende a engordar):**
- **PODE conter:** o **estado agregado do ciclo logístico** (status atual, histórico de transições) e
  **referências por ID** a entidades de outros módulos — ordem de produção (Produção), movimentos de estoque
  (Estoque), NF-e (Fiscal), conhecimento de transporte/CT-e.
- **NÃO PODE conter:** **duplicação** de dado que já pertence a Produção, Estoque ou Fiscal. Expedição
  **nunca é fonte da verdade** desses dados — só **consulta e referencia**. Se surgir a tentação de "só mais
  um campinho" que já existe noutro módulo, ele **não** entra aqui.

---

## Governança do Ciclo — faixas de titularidade

O Ciclo (Núcleo) não é só uma sequência: ele tem uma dimensão de **titularidade** — cada trecho de etapas
pertence a uma **equipe/faixa**, e as transições entre faixas são **gates de controle** (alguns financeiros,
donos do Financeiro). Essa dimensão existe nos requisitos (coluna "Responsável" das 38 etapas) mas **hoje não
é atributo explícito** de `ciclo_etapas` — está só implícita nas capabilities (`aprovar_financeiro`,
`executar_pe`, …) e em `ETAPAS_APROVACAO_FINANCEIRA = {8, 11d}` / `ETAPAS_OPERACIONAIS = {12,13,14}`.

> ### ⚠️ CONFLITO ABERTO — numeração de etapas (NÃO decidir operação pelo número de etapas)
> O **`REQUIREMENTS.md` §4 descreve 38 etapas em 6 fases** (fonte `1_FLUXO_DE_PROCESSOS.docx`), com fases que
> **já são estas faixas** (Fase 4 = "CD: Compra e Logística"; passo 11 = "Handoff para pós-venda"; passo 20 =
> "Aprovação financeira"). A **implementação** (`mod_ciclo` / `ETAPAS_CICLO`) tem **~20 etapas renumeradas
> (1‑4, 7‑20)** e **não** carrega as fases/donos. **Os dois modelos divergem em número e rótulo.** Até a
> reconciliação entre o fluxo de 38 etapas e este modelo de módulos acontecer (tarefa própria, futura),
> **nenhuma decisão operacional deve se apoiar no número/rótulo de etapa** — use as **faixas** abaixo, que são
> estáveis. (O MCP confirma o débito: etapas aparecem "sem uso"/sem rastro a requisito.)

**Faixas sobre as etapas realmente implementadas:**

| Faixa (dono) | Etapas | Papel |
|---|---|---|
| **Vendas** (Consultor/Gerente) | 1–4, 7 | capta → orçamento → **contrato** |
| **⛬ Gate — Aprovação Financeira I** (Financeiro) | **8** | libera Venda → Execução |
| **Pós-venda / Execução‑Projeto** (Conferente, Projetista Exec., Medidor) | 9, 10, 11(a–e) | medição + PE; contém o gate **11d** |
| **⛬ Gate — Aprovação Financeira II** (Financeiro) | **11d** | libera Projeto → Produção (empenha $ na fábrica — "ponto sem volta") |
| **Expedição / Logística** (Assist. Logístico) | 12–16 | pedido à fábrica, produção, recebimento (Estoque), NF‑e (Fiscal), entrega |
| **Pós-venda / Montagem** (Supervisor Montagem/Consultor) | 17–20 | montagem, assistência, vistoria, aprovação final |

Fluxo: **Vendas → (gate) → Pós-venda executa (Projeto) → (gate) → Logística → volta ao Pós-venda (Montagem).**
Cada seta é uma transição de `ciclo_etapas`; o estado vive no Ciclo, **não** num barramento.

### Gates financeiros como transições de controle (8 e 11d) — e o papel da IA

Os gates são **costuras entre faixas**, donas do **Financeiro** (capability `aprovar_financeiro`; já exigem
login+senha de quem aprova). A **Secretária Orizon (IA / EP‑08)** atua no gate como **aceleradora, nunca como
autoridade**. Dois pontos **inequívocos**:

1. **A aprovação é sempre ação humana do Financeiro.** A IA **nunca** aprova nem libera o gate de forma
   autônoma — ela apenas prepara, notifica e registra.
2. **Todo gate financeiro gera registro de auditoria** (`log_autorizacoes`) contendo: **quem** aprovou,
   **quando**, e um **snapshot dos dados que a IA apresentou** para a decisão (situação de crédito, histórico
   de inadimplência, consistência contrato × orçamento, alertas de risco). Isso protege o processo **e** a
   Financeiro/Diretoria caso a aprovação seja questionada depois.

Fora disso, a IA (Núcleo/Integrações — Evolution/WhatsApp): pré-checa os pré-requisitos e monta o dossiê,
**notifica/cobra** o Financeiro quando a etapa chega ao gate, e após a aprovação **dispara** o handoff para a
próxima faixa. Ela *lê* o estado do Ciclo e *escreve* notificação/auditoria — **nunca é dona de lógica de
domínio**.

---

## Convenções de fronteira ("onde mora código novo")

1. **Cadastro é referenciado por FK, nunca duplicado.**
2. **Tenancy carimba tudo** — `loja_id`/`rede_id` + escopo (`mod_tenancy`) em toda query de domínio.
3. **O Ciclo orquestra** — uma etapa gateia/dispara um módulo; nada de event bus.
4. **Nenhum módulo de domínio fala HTTP externo direto** — só via adapter no Núcleo/Integrações (o
   `EmissorFiscal` ABC é o molde; Promob parser e Evolution seguem o mesmo formato).
5. **Regra de lotação de código novo:** decidir por *(a) quem é dono do dado* e *(b) qual etapa do ciclo
   dispara*. Na prática: um cluster de `mod_<modulo>*.py`; uma **seção de rotas por módulo** no `main.py`
   (comentário-âncora); tabelas agrupadas por módulo no `database.py`. **Não** há split físico de schema.

## O que este mapa habilita
- **Ligar/desligar domínios por cliente** (loja avulsa = Cadastro+Comercial+Fiscal+Financeiro, sem
  Rede/Produção pesada) — porque o Núcleo (Tenancy) é a única dependência obrigatória.
- Colocar peça nova (ex.: Estoque, SPED, Secretária Orizon/Evolution) sem decidir arquitetura do zero.

## Fora de escopo (deliberado)
- **Zero** split físico de banco por módulo, **zero** event bus, **zero** reescrita do monolito.
- Design **interno** de Estoque, Pós-venda e do Financeiro completo — entram aqui só como **fronteira**;
  aprofundar quando forem construídos (cada um vira seu próprio ciclo brainstorming → spec → plano).

## Manutenção
Ao adicionar/mover módulo ou tabela: atualize a tabela da camada correspondente e o mapa do fluxo. Este
doc é a fonte da taxonomia; o `DEV_LOG.md` segue sendo a narrativa de estado/decisões.
