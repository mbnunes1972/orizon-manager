# Fiscal — Destinatário Contribuinte / Isento / Não Contribuinte — Design

> Spec de design · 2026-07-06 · Orizon Manager | Dalmóbile
> Status: **IMPLEMENTADO (branch `feat/fiscal-destinatario-contribuinte`, suíte 562)** — emissão correta para
> os 3 tipos de destinatário (contribuinte/isento/não contribuinte): Cliente ganha tipo+CNPJ+IE; cadastro com
> seletor; contrato exige o documento certo (não a IE); IE pedida na emissão e persistida; `mapa_fiscal`
> ramifica indicador IE (1/2/9), envio de IE, CSOSN (override Emitente + default código 101/102) e
> `consumidor_final`. Origem: smoke autorizado (CSOSN 101 rejeitado p/ não contribuinte → 102).

## 1. Motivação

Hoje o payload é **cravado para não-contribuinte** (`indicador_inscricao_estadual_destinatario=9` fixo,
`consumidor_final` derivado só de CPF×CNPJ, CSOSN único do Emitente), e o `Cliente` **só tem `cpf`** — não
dá nem para representar um contribuinte (PJ com CNPJ/IE). O smoke autorizou justamente porque a venda era a
não-contribuinte com CSOSN 102. Para faturar a um **contribuinte** (indicador 1 + IE + CSOSN com crédito) ou
**isento** (indicador 2), falta modelar o destinatário e ramificar o bloco fiscal.

## 2. Decisões (brainstorming)

- **3 estados do destinatário:** Contribuinte / Isento / Não Contribuinte → `indicador_ie` **1 / 2 / 9**.
- **CSOSN:** **defaults no código (101 contribuinte / 102 demais) + override opcional no Emitente** — funciona
  de fábrica; editável por loja/segmento quando o contador exigir.
- **Obrigatoriedade por etapa:** o **documento** (CPF/CNPJ) é obrigatório **na geração do contrato** (não no
  cadastro); a **IE não bloqueia o contrato** — pode ser preenchida **no ato da emissão** (persistida no Cliente).
- **UI:** seletor de 3 estados no cadastro do cliente, com campos condicionais.

## 3. Modelo — `Cliente` (novos campos)

```
Cliente:
  + tipo_dest       Text  default "nao_contribuinte"   # "contribuinte" | "isento" | "nao_contribuinte"
  + cnpj            Text  nullable
  + inscricao_estadual Text nullable
  # mantém: cpf
```
Migração idempotente (ADD COLUMN). Mapa `tipo_dest → indicador_ie`: contribuinte→1, isento→2, nao_contribuinte→9.

## 4. Modelo — `Emitente` (CSOSN por tipo, com override)

- Mantém `csosn_padrao` (semântica: **CSOSN de não-contribuinte/isento**, sem crédito — hoje 102).
- **Novo** `csosn_contribuinte` (nullable — CSOSN de contribuinte, com crédito).
- **Defaults no código** (`mapa_fiscal`): `CSOSN_CONTRIBUINTE = "101"`, `CSOSN_SEM_CREDITO = "102"`.
- Resolução: `csosn = (emitente.csosn_contribuinte or CSOSN_CONTRIBUINTE)` se indicador==1;
  senão `(emitente.csosn_padrao or CSOSN_SEM_CREDITO)`.

## 5. Cadastro (UI) — `static/index.html`

No modal de cliente (`cli-*`, ~linha 1276): **seletor "Tipo de destinatário"** (3 opções) que controla os campos:
- **Não contribuinte** (padrão) → **CPF** (como hoje).
- **Contribuinte** → **CNPJ** + **IE** (IE opcional no cadastro).
- **Isento** → **CNPJ** (sem IE).

`cliCriar`/`cliSalvar` (o POST/PUT `/api/clientes`) passam `tipo_dest`, `cnpj`, `inscricao_estadual` conforme
o seletor. **Nenhum obrigatório no cadastro** (só o nome, como hoje).

## 6. Obrigatoriedade por etapa

- **Contrato (etapa 7):** exige **o documento do tipo certo** — CPF se não-contribuinte, **CNPJ** se
  contribuinte/isento. Generaliza o branch existente `sem_cpf` → **`sem_doc`** (a UI de contrato já trata
  "sem_cpf"; estende para exigir CNPJ quando contribuinte/isento). **IE NÃO é exigida no contrato.**
- **Emissão (etapa 15):** se `tipo_dest=="contribuinte"` e **IE ausente**, o painel abre um **campo IE
  obrigatório para emitir**; ao emitir, a IE é **persistida no `Cliente`** (para as próximas). Isento/não
  contribuinte não exigem IE.

## 7. Fiscal — `mapa_fiscal.montar_nota`/`montar_payload`

`montar_nota` passa a receber o **indicador_ie do cliente** (derivado de `cliente.tipo_dest`) e ramifica:

| tipo_dest | doc | doc_tipo | `indicador_ie` | IE enviada | CSOSN | `consumidor_final` |
|---|---|---|---|---|---|---|
| **contribuinte** | CNPJ | cnpj | **1** | **sim** (`inscricao_estadual`) | `csosn_contribuinte`→101 | **0** |
| **isento** | CNPJ | cnpj | **2** | não | `csosn_padrao`→102 | 1 |
| **nao_contribuinte** | CPF | cpf | **9** | não | `csosn_padrao`→102 | 1 |

- `doc` continua normalizado (`_so_digitos`).
- `montar_payload`: `indicador_inscricao_estadual_destinatario` deixa de ser fixo `9` — vem do `nota`; envia
  `inscricao_estadual_destinatario` só quando indicador==1; `consumidor_final` do `nota` (não mais só CPF×CNPJ).
- A nota neutra ganha `destinatario.indicador_ie`, `destinatario.ie`, e `destinatario.consumidor_final`.

## 8. Testes

- **`mapa_fiscal`:** os 3 ramos (contribuinte→indicador 1+IE+CSOSN 101+consumidor 0; isento→2, sem IE, 102;
  não-contribuinte→9, CPF, 102, consumidor 1); override de CSOSN no Emitente respeitado; default no código quando null.
- **Cliente model/migração:** `tipo_dest`/`cnpj`/`inscricao_estadual` persistem; migração idempotente.
- **Contrato:** exige CNPJ quando contribuinte/isento e CPF quando não-contribuinte (`sem_doc`); **não** exige IE.
- **Emissão (etapa 15):** contribuinte sem IE → 400/pedido de IE; com IE → emite e persiste a IE no Cliente.
- Suíte verde (baseline 546).

## 9. Fora de escopo

- Não-contribuinte **PJ** (CNPJ com indicador 9) — o comum é CPF; tratar como refinamento se surgir.
- CSOSN por operação além de contribuinte×não (ex.: ST, devolução) — contador, futuro.
- A migração do Painel Fiscal de config `PerfilFiscal → Emitente` (EP-11/US-36) — independente.
