# Hub de Serviços da Rede — RASCUNHO INICIAL (2026-07-22)

> **Status: rascunho de partida** — criado ao abrir a branch `feat/hub-servicos-rede`. A frente
> ainda vai definir o desenho; este documento registra a demanda e as perguntas a responder.

## Demanda (do usuário, 2026-07-22)
Criar um **hub de serviços para as redes**: uma centralização de serviços comuns às lojas —
**marketing, jurídico, financeiro, compras, logística etc.** — operada no nível da rede.

## Contexto que o desenho deve considerar (já existe no sistema)
- **Tenancy**: `Rede` → `Loja` (+ PDVs com `loja_mae_id`, frente `feat/ponto-de-venda` em
  paralelo — os dois desenhos devem conversar: o PDV centraliza NA LOJA-MÃE; o hub centraliza
  NA REDE).
- **Fiscal**: já existe o conceito de **emitente central da rede** (`Rede.emitente_central_id`,
  spec 2026-07-06) e a política produto/serviço → self|central — precedente direto de "serviço
  comum operado pela rede".
- **Distribuidora Orizon Soluções** (spec `contrato-documentos/2026-07-16-segmentacao-…`):
  2ª pessoa jurídica assumindo papel de distribuidora (mercadoria) — é, na prática, o primeiro
  "serviço centralizado" (compras/fornecimento). O hub generaliza essa ideia.
- **Contabilidade**: razão por owner (`owner_tipo`/`owner_id`) já suporta owner "rede" — um
  serviço central pode ter razão próprio e ratear/faturar às lojas.
- **Perfis/escopo**: `admin_rede` existe; funções (`Funcao`) são por loja hoje.

## Perguntas a responder no desenho (sugestão de pauta)
1. **O que é um "serviço" no modelo?** Entidade própria (`ServicoRede`: tipo, responsáveis,
   lojas atendidas) ou só um conjunto de capacidades/painéis no nível rede?
2. **Pessoas**: a equipe do hub é contratada pela rede (usuários com `rede_id` e função no hub)
   ou cedida pelas lojas? Como entra na Folha (`remuneracoes-folha`)?
3. **Custo e rateio**: serviço central gera custo — fatura às lojas (intercompany), rateia por
   critério (receita? uso?), ou fica no resultado da rede? Ligação com o razão owner=rede e
   com os Acordos Financeiros.
4. **Fluxos por serviço**: cada serviço tem processos próprios (compras: pedido consolidado;
   logística: entrega multi-loja; jurídico: modelos de documento da REDE — os
   `documento_modelos` são por loja hoje; marketing: campanhas/leads). Priorizar 1–2 pilotos.
5. **UI**: painel "Hub da Rede" (visão do admin_rede) × o que a loja enxerga (solicitar
   serviço, acompanhar).
6. **Qual o piloto?** Sugestão: **Compras/distribuidora** (já tem a Orizon Soluções como
   motor real) ou **Jurídico** (modelos de documento da rede — extensão natural do painel de
   documentos da Sessão 106).

## Fora de escopo até o desenho fechar
Implementação. Esta frente começa por decidir o modelo (as 6 perguntas) e escrever a spec de
verdade, com o usuário.
