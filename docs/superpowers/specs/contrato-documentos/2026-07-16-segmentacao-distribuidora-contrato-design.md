# Segmentação Mercadoria/Serviço no Contrato — Distribuidora Orizon Soluções — Design

**Data:** 2026-07-16
**Estado:** aprovado, não implementado
**Escopo:** documentar a decisão de negócio + preparar o terreno (dados/marcadores) para o momento em que
o CNPJ da distribuidora existir
**Fora de escopo:** emissão real de NFS-e (US-32, já fora de escopo da spec fiscal multi-CNPJ); redação
jurídica final das cláusulas de responsabilidade entre as duas CONTRATADAS (precisa de advogado); CNAE/
regime tributário da nova empresa (precisa de contador)

---

## 1. Contexto

A venda hoje mistura, num único CONTRATADA (a loja, ex. INSPIRIUM), duas naturezas de receita: **mercadoria**
(os móveis) e **serviço** (projeto, montagem, instalação). O motor fiscal já segrega isso — `mod_orcamento_params.
SEGMENTACAO_DEFAULT = {"pct_mercadoria": 65.0, "pct_servico": 35.0}`, ajustável por loja
(`Loja.pct_mercadoria/pct_servico`) e por venda via override do Diretor (`Projeto.parametros_json`,
gate `aprovar_financeiro`) — e usa isso pra fazer a NF-e de produto sair com Σitens = parcela Mercadoria e a
NFS-e de serviço com a parcela Serviço (`mod_nfe.rescalar_itens_para_total`, provado em
`test_face_fiscal_alinhada_a_segmentacao`). Isso já é sustentável **mesmo com um único CNPJ**: uma empresa do
Simples Nacional que vende mercadoria e presta serviço é tributada em anexos diferentes (I para comércio,
III/V para serviço), cada um com sua própria faixa — a segregação de receita por atividade é enquadramento
correto, não é uma otimização artificial.

O que falta é: (a) o **contrato entregue ao cliente** não mostra nenhuma discriminação de valor — é um
"VALOR DO CONTRATO" indiviso (conferido no modelo real da loja, `contrato_7.pdf`/`.docx`, INS2026071400007);
e (b) o Marcelo está abrindo uma segunda pessoa jurídica, **Orizon Soluções** (CNPJ em processo de abertura,
2026-07), que vai assumir o papel de **distribuidora** — quem efetivamente vende a mercadoria — enquanto a
loja (INSPIRIUM ou equivalente por franquia) segue vendendo o serviço.

**Achado importante:** a infraestrutura fiscal pra isso **já existe e já foi desenhada pra este cenário
exato** — `docs/superpowers/specs/fiscal/2026-07-06-fiscal-plano-faturamento-multicnpj-design.md`
(IMPLEMENTADA, Sessão 49) já modela `Rede.emitente_central_id` como "a distribuidora central da rede", e o
próprio exemplo da spec original já cita nominalmente "rede Orizon → (rede, Orizon, produto,
Emitente_Central)". Esta spec não cria mecanismo fiscal novo — só fecha o lado do **contrato**, que ficou de
fora daquela entrega.

## 2. Decisão

1. **Sem CNPJ, sem parte contratante.** Enquanto a Orizon Soluções não existir como CNPJ, o contrato
   **continua exatamente como hoje** — 1 CONTRATADA (a loja), sem menção à distribuidora. Não faz sentido
   jurídico nomear como parte uma empresa que ainda não existe.
2. **Quando o CNPJ sair, o contrato passa a ter 2 CONTRATADAS no mesmo instrumento** (não dois contratos
   separados): Orizon Soluções responde pela cláusula 1.1 (fornecimento de material) por sua parcela do
   valor; a loja responde pela cláusula 1.2 (prestação de serviços) pela dela. Um instrumento só mantém a
   experiência atual (1 assinatura, 1 PDF) — casa com o desenho existente (`Contrato` é 1 registro por venda).
3. **O valor é discriminado, não só a existência das duas partes.** Cláusula nova mostrando R$ e % de cada
   parcela, alimentada pela **mesma função** que já gera a NF-e/NFS-e (`segmentar(Val_Cont, pct_mercadoria)`)
   — contrato e notas fiscais nunca divergem, porque vêm da mesma fonte.
4. **Gating automático pela presença do Emitente da distribuidora.** Não é uma flag manual "liga/desliga" —
   o sistema decide sozinho: `Rede.emitente_central_id` apontando para um `Emitente` real ⇒ formato novo;
   `NULL` (hoje) ⇒ formato atual. Zero mudança de comportamento pra quem usa o sistema até lá.

## 3. Mapeamento pra infraestrutura existente

Nenhuma tabela nova. Reusa o que a spec `2026-07-06-fiscal-plano-faturamento-multicnpj-design.md` já criou:

- **`Emitente`** — quando sair o CNPJ, cria 1 linha com os dados reais (`razao_social="ORIZON SOLUÇÕES ..."`,
  `cnpj`, `inscricao_estadual`, endereço, regime tributário — a definir com o contador).
- **`Rede.emitente_central_id`** — aponta pra esse Emitente. É literalmente o campo "a distribuidora central
  da rede" que a spec original já previu.
- **`PerfilEmissao(owner_tipo="rede", owner_id=<rede.id>, tipo_doc="produto", emitente_id=<Orizon Soluções>)`**
  — resolve a NF-e de produto pro CNPJ da distribuidora; a NFS-e de serviço continua resolvendo pra loja
  (self, via `resolver_emitente`, sem política nova ali).

Ou seja: **"um campo a ser preenchido com os dados da empresa"**, como o Marcelo pediu, é exatamente criar 1
`Emitente` e apontar `Rede.emitente_central_id` — não precisa de tabela, migração de schema, nem tela nova.

## 4. Contrato — o que muda no texto

Hoje (conferido no modelo real, `contrato_7.docx`): Cláusula Primeira já **separa** as obrigações — 1.1
fornecimento de material, 1.2 prestação de serviços — mas sob 1 CONTRATADA e sem valor por obrigação.

Rascunho de cláusula nova (⚠ **texto ilustrativo, não final** — ver §6):

> **1.7.** Do VALOR DO CONTRATO indicado na capa, R$ [VALOR_MERCADORIA] ([PCT_MERCADORIA]%) corresponde ao
> fornecimento do material descrito no item 1.1, obrigação de ORIZON SOLUÇÕES [razão social completa], CNPJ
> [CNPJ], e R$ [VALOR_SERVICO] ([PCT_SERVICO]%) corresponde aos serviços descritos no item 1.2, obrigação de
> [razão social da loja], discriminação que corresponde aos respectivos documentos fiscais (Nota Fiscal de
> Produto e Nota Fiscal de Serviço) emitidos por cada CONTRATADA.

Também precisa (fora do escopo de redação desta spec, mas mapeado): um bloco de qualificação da segunda
CONTRATADA no preâmbulo (hoje só qualifica a INSPIRIUM) e uma cláusula de responsabilidade — cada CONTRATADA
responde pela sua obrigação, isoladamente ou solidariamente (decisão jurídica, não técnica).

## 5. Marcadores novos (`mod_marcadores.CATALOGO`)

| Marcador | Fonte | Disponível quando |
|---|---|---|
| `VALOR_MERCADORIA` | `segmentar(Val_Cont, pct)[0]`, formatado | sempre (funciona já hoje, mesmo sem distribuidora) |
| `VALOR_SERVICO` | `segmentar(Val_Cont, pct)[1]`, formatado | sempre |
| `PCT_MERCADORIA` / `PCT_SERVICO` | `segmentacao_efetiva(loja, projeto)` | sempre |
| `DISTRIBUIDORA_RAZAO_SOCIAL` / `DISTRIBUIDORA_CNPJ` / `DISTRIBUIDORA_ENDERECO` | `Emitente` via `Rede.emitente_central_id` | só quando o Emitente existir — ausência = sinal de gating (§2.4) |

Calculados em `mod_contrato._montar_mapping`, mesmo ponto que hoje monta `TOTAL_CONTRATO` — trava anti-drift
existente (teste que compara `CATALOGO` × `_montar_mapping`) cobre os novos também sem mudança de desenho.

## 6. Pendências / precisa de humano (não é decisão técnica)

- **Razão social e CNPJ definitivos** da Orizon Soluções — preencher assim que sair a abertura.
- **Redação jurídica final** das cláusulas de qualificação da 2ª CONTRATADA e de responsabilidade
  (individual vs. solidária) — o rascunho do §4 é ilustrativo, precisa de advogado.
- **Validação do contador** de que a Orizon Soluções vai operar com substância econômica real (compra/revenda
  efetiva dos móveis, gestão própria, preços de mercado) — um split que exista só no papel, sem operação de
  fato por trás, é o cenário clássico que o Fisco pode desconsiderar como simulação.
- **Percentual real por venda**: o default 65/35 já existe; confirmar se esse é o número certo pra Orizon
  Soluções ou se muda quando a operação for formalizada.

## 7. Porquê documentar agora, sem o CNPJ ainda existir

Pedido explícito do Marcelo (sessão 2026-07-16): deixar o terreno preparado — "basicamente um campo a ser
preenchido" — pro momento em que o CNPJ sair, sem que a abertura da empresa fique esperando o sistema, e sem
arriscar nomear no contrato uma parte que ainda não existe juridicamente. A implementação (marcadores +
template + gating) fica pra quando os dados reais da Orizon Soluções e a validação jurídica/contábil
estiverem prontos — este documento é o registro da decisão e do desenho, não o código.
