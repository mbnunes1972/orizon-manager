# Resultado da Venda + Aprovações Financeiras (AF1/AF2/AF3) — design

> Consolida a conversa de design de 2026-07-13. Fecha o **modelo de resultado da venda**: traz pro
> razão TODOS os custos/receitas que hoje ficam fora do monitoramento contábil (custos adicionais,
> resultado financeiro), formaliza o papel de cada Aprovação Financeira, e corrige o tratamento de
> impostos (revisável, com devolução). **Contas novas marcadas "⚠ confirmar contador".**

## 1. Objetivo
Toda a margem de uma venda de planejados (ciclo de até ~1 ano) precisa estar no **razão**, não só em
painel. Hoje há três buracos: (a) os **custos adicionais** (Comissão de Arquiteto, Fidelidade, Viagem,
Brinde) reduzem a margem gerencial mas não são lançados; (b) o **resultado financeiro** (`Cust_Fin`) não
é tratado por natureza; (c) **impostos** não têm rota de **devolução**. As **Aprovações Financeiras**
(AF1/AF2/AF3) são os checkpoints onde o gerente confirma/ajusta esses valores — e o sistema faz **toda a
contabilidade sozinho** (o gerente adm/fin não é contador).

## 2. Princípios herdados (não renegociar)
- **Fonte única = razão contábil.** Painéis são views derivadas; nada de verdade só no painel.
- **Rigor contábil sobre escopo.** Booking correto mesmo que abra conta/módulo; entregar o MVP dela.
- **FASE D2.** No contrato, custo vira **ativo diferido × provisão** (`1.1.06.0X × 2.1.04.0X`) **sem tocar
  a DRE**; a despesa entra na DRE só na **NF-e real** (matching). Impostos têm rota fiscal própria (§4).
- **Gerente adm/fin não vê débito/crédito.** Ele só **seleciona** e **ajusta**; o sistema books.

## 3. O conjunto COMPLETO de rubricas do resultado

### 3.1 Operacionais (custo de execução/fornecedor) — 10, já existem
montagem, garantia, assistência, frete de fábrica, frete local, insumos, comissão de medidor, comissão de
projeto/executivo, retenção de comissão de vendas, **custo de fábrica**. Cada uma `1.1.06.0X × 2.1.04.0X`;
matching na NF-e (`reconhecimento_despesa_*`).

### 3.2 Impostos — 11ª rubrica: rota fiscal própria **E revisável**
- **Constituição (contrato):** `fechamento_venda_impostos` = `1.1.05 (Impostos a Apropriar) × 2.1.04.13
  (Provisão de Impostos)` — sem tocar a DRE.
- **Emissão (NF-e):** `efetivar_impostos_segmento` → dedução na DRE (`4.3.01 × baixa 1.1.05`) + obrigação
  fiscal real (`2.1.04.13 × 2.1.03`). Fica **fora** do matching operacional e da conciliação final.
- **É REVISÁVEL** (correção 2026-07-13 — a versão anterior deste raciocínio dizia "imutável", errado):
  muda com o **Val_Cont** (revisão nas AFs — o `ajustar_provisao_delta` já cobre via `1.1.05 × 2.1.04.13`,
  com teste) e com **devolução** (§5).
- **Evolução fiscal (CONSIDERADA — não cristalizar como % fixo):** hoje a carga é um **percentual
  fixo** (`carga_trib_pct` na config da loja). Roadmap, já com ganchos no código: (1) puxar a carga do
  **modelo fiscal por faixa de tributação** (Simples/anexo — o padrão de "faixas" já existe na comissão
  de vendas); (2) **segmentar distribuidora (mercadoria → NF-e / `4.1.01`) × loja (serviço → NFS-e /
  `4.2.01`)** — `faturar_segmento(mercadoria|servico)` já existe e a emissão de impostos já prevê
  "proporcional Merc/Serv". O tratamento **revisável** dos impostos (delta #11 + devolução §5) acomoda
  essas mudanças sem re-arquitetar: quando a carga passar a vir por faixa/segmento, o valor por versão
  muda e o delta reconcilia; a rota fiscal (`1.1.05`/`2.1.04.13`/`4.3.01`/`2.1.03`) permanece.
- **Nota do drift observado no qa-sim:** a coluna "valor atual" do modal é recalculada ao vivo
  (`_negociacao_breakdown → Prov_Imp`, depende do `carga_trib` dos parâmetros atuais); quando o parâmetro
  está diferente do que valia no snapshot, aparece 0 (o flag `desatualizado` sinaliza). Os snapshots
  (venda/rev) e o `orcamentos.prov_imp` seguem corretos. É drift de recálculo, não erro de booking — mas
  §5 (devolução) é o buraco estrutural de verdade.

### 3.3 Custos adicionais — NOVOS (o buraco do monitoramento)
`com_arq` (Comissão de Arquiteto), `pro_fid` (Fidelidade), `cust_via` (Viagem), `brinde`. Hoje são
**deduzidos do Val_Liq** e exibidos "à parte" (main.py:1623-1631), **não somam no Cust_Var** e **não estão
nas chaves da provisão** → reduzem a margem gerencial mas **não existem no razão**. Quando viram despesa,
não há provisão pra baixar. **Recomendação:** viram **provisões** (`1.1.06.xx × 2.1.04.xx`, contas novas,
padrão FASE D2), constituídas no contrato, reconhecidas quando ocorrem, **confirmadas/ajustadas na AF1**
(delta #11). Independem do toggle de custos adicionais — a despesa ocorre de qualquer forma.

### 3.4 Resultado financeiro — NOVO (`Cust_Fin`, dois ramos)
`Val_Cont = VAVO + Cust_Fin`. Toda a margem operacional roda sobre o **VAVO**; o `Cust_Fin` (calculado
pelas tabelas financeiras, já embutido no Val_Cont por forma de pagamento) é uma **grandeza financeira
separada**, com **sinal oposto conforme quem financia**:

| Quem financia | `Cust_Fin` é | Tratamento (automático) |
|---|---|---|
| **Financeira** (Aymoré, Cartão, futura) | **despesa** financeira (taxa/deságio absorvido) | provisão de **despesa** financeira; ajustável na AF1 (delta #11) |
| **Loja** (direto, capital próprio) | **receita** financeira (juro), **sem despesa** | recebível + receita financeira **a apropriar por parcela** (§3.5) |

**Box na AF1** seleciona o ramo, com **default automático pela forma de pagamento** (Aymoré/Cartão →
financeira; modalidade própria → loja) — o gerente em geral **só confirma**. O mesmo número `Cust_Fin`,
tratamento oposto: é por isso que o box é necessário.

### 3.5 Financiamento direto pela loja — recebíveis com juros a apropriar
- **Fechamento (automático):** cria o recebível dos **juros** e difere a receita:
  `DR Recebíveis de Parcelamentos (só a parte de juros) × CR Receita Financeira a Apropriar`.
  *(o VAVO segue no `1.1.02` operacional da FASE D2 — o recebível de parcelamento carrega SÓ os juros,
  pra não duplicar receita. Decisão confirmada com o usuário.)*
- **A cada parcela recebida (automático):** (i) `DR Caixa × CR Recebíveis de Parcelamentos`; (ii)
  apropriação: `DR Receita Financeira a Apropriar × CR Receita Financeira (resultado)` — competência por
  parcela. **Sem despesa** (capital próprio; o custo é de oportunidade, não lança).
- **No razão = Resultado Financeiro**; o painel da AF **deriva** disso a leitura "resultado adicional da
  venda" (não duplica; fonte única no razão).

### 3.6 ⚠ PENDENTE — gatilhos de reconhecimento do custo financeiro (achado da Vera, e2e 2026-07-14)
A constituição (contrato) e a troca de ramo (box da AF) estão prontas e testadas, mas o **reconhecimento**
do custo financeiro ainda **não dispara** no app:
- **Ramo financeira/antecipação:** o evento `reconhecimento_despesa_custo_financeiro` (`5.5.04 × baixa
  1.1.06.19`) existe mas **não tem call-site**. Falta decidir o gatilho: quando o custo REAL é apurado
  (financeira liquida / banco desconta os boletos) — análogo ao `efetivar_impostos_segmento` na NF-e, ou
  um evento "pagamento à financeira/antecipação". A provisão `2.1.04.19` foi **excluída da Conciliação
  Final** (como impostos) pra não virar receita fictícia em `4.4.02` até o reconhecimento existir.
- **Ramo loja:** `receber_parcela_direto`/`apropriar_receita_financeira` dependem da **infra de parcelas
  recebidas** (ainda não há endpoint de "parcela recebida") — reconhecimento da receita por competência
  fica pra essa infra.
Decisão de negócio pendente: o gatilho usa o valor **estimado** (Cust_Fin) ou o **custo real apurado**?
(A #11/reconciliação absorve a diferença de qualquer forma.)

## 4. As Aprovações Financeiras (o gate)
- **AF1 — confirma a MARGEM da venda.** Revisa os 4 custos adicionais (§3.3) + seleciona/confirma o box de
  financiamento (§3.4) + eventual pequena revisão de fábrica. Ao aprovar, **trava Rev1**. Efeito contábil:
  delta ativo×provisão (#11) das rubricas que mudaram; **nunca DRE**.
- **AF2 — revisão de custo de fábrica/PE** (a Fatia 1 do desmembramento alimenta isto). Trava Rev2.
- **AF3 (futura) — pós-Conferência**; transferência fábrica→Outros Fornecedores (`2.1.04.06→2.1.04.14`,
  pode já ocorrer na AF2 — #13 do desmembramento). Rev3 é placeholder por ora.
- **Limite/step-up:** aumento acima do limite (config **Limite de Aprovação Financeira 1/2**, defaults
  **1%/2%**) exige **Diretor** (`exige_aprovacao_diretor`, já implementado). O limite mede sobre a
  **margem** (que agora inclui os 4 custos), não sobre `cust_var`.
- Quando o projeto está **desmembrado**, o gate roda **por parcela**.

## 5. Devolução — gap a fechar (projeto dura ~1 ano)
- No plano existem `2.1.04.04 "Provisão de Devolução"` e `4.3.02 "Devolução de Vendas"`, mas a
  **`2.1.04.04` está morta** (mod_contabil.py:862 — "sem evento/percentual de constituição hoje, saldo
  sempre 0") e **não há evento de devolução**.
- Numa devolução (parcial ou total, possível ao longo do ano), é preciso **estornar proporcionalmente**:
  a receita, os **impostos** (`4.3.02` + reversão de `2.1.04.13`/`2.1.03`) e as **provisões operacionais**
  da parte devolvida.
- **Recomendação:** evento de **devolução por ambiente/parcela** (reaproveita a fração congelada #5 do
  desmembramento) que estorna proporcional — é a razão pela qual impostos precisam ser revisáveis. É o
  buraco estrutural por trás do "problema no lançamento dos impostos".

## 6. Automação — o gerente não é contador
O gerente adm/fin faz **só duas coisas** na AF: **seleciona/confirma** o box de financiamento e **ajusta**
os valores revisáveis. **Todo o resto (partida dobrada, constituição, apropriação, deltas, dedução fiscal)
é automático.** O box default vem da forma de pagamento; os valores de custo financeiro/impostos vêm das
tabelas financeiras. Nenhuma tela pede débito/crédito.

## 7. Plano de contas — novas/ativar (⚠ confirmar contador)
- **Custos adicionais:** 4 pares novos `1.1.06.xx (a apropriar) × 2.1.04.xx (provisão)` — Comissão de
  Arquiteto, Fidelidade, Viagem, Brinde. Reaproveitar `2.1.04.04` livre? Não — é Devolução; usar códigos novos.
- **Resultado financeiro:** `Recebíveis de Parcelamentos` (ativo, `1.1.0x`), `Receita Financeira a
  Apropriar` (redutora do recebível ou passivo `2.1.07`), `Receita Financeira` (resultado `4.x`),
  `Despesa Financeira` (resultado, p/ o ramo financeira).
- **Devolução:** ativar `2.1.04.04` + `4.3.02` (hoje dormentes) com evento próprio.

## 8. O que JÁ está implementado (branch feat/desmembramento-fatia2-ciclo)
- `mod_contabil.ajustar_provisao_delta` (#11) — delta ativo×provisão, nunca DRE; **cobre qualquer rubrica,
  inclusive impostos** (`1.1.05`). Testado (6 testes, incl. impostos).
- `mod_parcelas`: `congelar_parcelas` (#5), `exige_aprovacao_diretor` (#10 gate), `validar_particao_parcelas`
  (#1). Todos com TDD. Suíte 982 verde.
- **Falta fiar:** endpoints, box da AF, disparo do delta na tela, e as rubricas novas (§3.3/§3.4/§5).

## 9. Fatiamento sugerido (cada uma testável e entregável)
- **Fatia A — Custos adicionais viram provisão.** Contas novas + constituição no contrato + entram em
  `itens_provisao`/`_PROV_FECHAMENTO` + matching na NF-e. Fecha o buraco do §3.3. (TDD contábil.)
- **Fatia B — Resultado financeiro.** Box loja×financeira na AF1 (default pela forma de pagamento); ramo
  financeira (provisão de despesa) e ramo loja (recebível + receita financeira a apropriar por parcela).
- **Fatia C — Gate da AF na tela.** Coluna de trava em `ProvisaoRegistro` + migração; endpoint recusa
  reedição travada + step-up do Diretor acima do limite; dispara `ajustar_provisao_delta` por rubrica
  revisada; por parcela quando desmembrado. (Núcleos #10/#11 já prontos.)
- **Fatia D — Devolução.** Evento de estorno proporcional (receita + impostos + provisões), por
  ambiente/parcela; ativa `2.1.04.04`/`4.3.02`.
- Todas integram com o **desmembramento** (por parcela quando aplicável). Vera antes de mergear cada uma
  (área sensível: contábil/fiscal).

## 10. Riscos e cuidados
- **Não duplicar receita:** Val_Liq é gerencial; o razão só ganha o custo/receita que faltava. Recebível
  de parcelamento carrega só juros (VAVO fica no `1.1.02`).
- **Impostos:** manter a rota fiscal própria (não entram no matching operacional nem na conciliação
  final); a devolução estorna proporcional.
- **Sinal do custo financeiro:** o box (loja×financeira) é o que evita inverter receita×despesa.
- **⚠ confirmar contador** nas contas novas e na apresentação (resultado financeiro × "adicional de venda").
