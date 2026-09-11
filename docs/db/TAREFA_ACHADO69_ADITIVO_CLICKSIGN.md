# TAREFA — ACHADO-69: o Termo Aditivo é o único documento assinado sem ClickSign

Achado do Marcelo em 10/09/2026, na etapa 11e de Homologação (`v2026.09.09-beta1`), Projeto 13.

> "Use o mesmo mecanismo de assinatura dos casos anteriores: opção de imprimir e assinar, pelo
> ClickSign."

## Medido antes de escrever — três irmãos têm, o quarto não

Quatro documentos do sistema são assinados por loja + cliente. **Três têm escolha de canal;
o Termo Aditivo não tem.**

| documento | `assinatura_canal` | rotas ClickSign | webhook/reconciliação |
|---|---|---|---|
| Contrato | `database.py:1323` | `/contrato/clicksign/{enviar,verificar,reenviar}` | sim |
| Aprovação do PE | `database.py:1432` | `/aprovacao-pe/clicksign/{enviar,verificar,reenviar}` | sim |
| Solicitação de medição | `database.py:1479` | sim | sim |
| **Termo Aditivo** | **não existe** | **nenhuma** | **não** |

O Aditivo tem só a porta interna: `POST /api/projetos/<nome>/aditivo/assinar`
(`main.py:9587`), cujo próprio comentário diz *"assinatura interna do termo aditivo (loja +
cliente), espelho do contrato"* — espelhou a assinatura **interna** do contrato, não a escolha
de canal que o contrato ganhou depois.

É a **regra dos irmãos (ACHADO-26) ao contrário**: em vez de uma porta esquecida aberta, uma
capacidade que três irmãos têm e o quarto ficou sem.

**O "imprimir" já existe** — o botão "Baixar PDF" está na tela. O que falta é a **escolha de
canal** e o caminho ClickSign inteiro.

## O que fazer

**Passo 1 — enumerar antes de mexer.** Liste, para UMA das três classes que já funcionam
(sugestão: `AprovacaoPE`, a mais nova e a mais parecida em ciclo de vida), **todos** os pontos
que compõem o mecanismo: modelo, migration, rotas de envio/verificação/reenvio, funções
`_enviar_*_para_clicksign` e `_reconciliar_*_clicksign` (`main.py:1271` e `1303`), o webhook
(`/webhooks/clicksign`), o job `/internal/clicksign/reconciliar`, o cancelamento de envelope, e
a tela. Esse inventário é o gabarito do que o Aditivo precisa — e é o que impede entregar meio
mecanismo.

**Passo 2 — o dado.** `Aditivo` (`database.py:1365`) precisa de `assinatura_canal` e dos campos
de ClickSign que os irmãos têm (`clicksign_enviado_em` e companhia — o inventário do Passo 1
diz quais).

> **R1:** isso vai em **migration**, nunca em `_migrar_colunas_pg`, que está congelado. Repare
> que as linhas 2535/2539 do `database.py` acrescentaram `assinatura_canal` a `contratos` e
> `aprovacoes_pe` por lá — **não repita esse caminho**; ele é dívida registrada, não exemplo.
> `assinatura_canal` do Aditivo nasce com `server_default='interno'`, como os irmãos, para que
> aditivo já existente continue no canal interno sem migração de dado.

**Passo 3 — o backend.** As rotas espelhando as da Aprovação do PE, `_enviar_aditivo_para_
clicksign` / `_reconciliar_aditivo_clicksign`, e o Aditivo entrando nas **duas** varreduras
coletivas: o webhook e o `/internal/clicksign/reconciliar` (`main.py:6642/6664/6686` — hoje são
três consultas, vira a quarta). Um envelope que ninguém reconcilia é assinatura que some.

**Passo 4 — a tela.** Na 11e, o bloco do Termo Aditivo passa a oferecer a mesma escolha dos
outros: assinar internamente (com nome + CPF, como está hoje) **ou** enviar pelo ClickSign, com
o estado do envelope visível e o reenvio disponível. Imprimir continua pelo "Baixar PDF".

## Fronteiras

- **A validação de CPF continua valendo** nos dois canais (ACHADO-28, F2-6:
  `validacao_doc.erro_doc` dentro dos `_registrar_assinatura_*`).
- **O efeito contábil não muda.** A assinatura completa (loja + cliente) do Aditivo constitui as
  provisões da diferença negociada — o docstring de `Aditivo` registra isso, e vale igual venha
  a assinatura de qual canal for. Se o caminho ClickSign não disparar a mesma constituição, o
  pacote está errado.
- **ACHADO-25 é a lição a não repetir:** foi exatamente na tela do aditivo que um campo
  obrigatório novo passou despercebido e nenhum aditivo pôde ser assinado em produção, com
  2466 testes verdes. Toda mudança de contrato de endpoint aqui diz **quem chama** e confere o
  chamador real em `static/index.html`.
- Não tocar em Produção, tag ou deploy.

## Aceite

1. O inventário do Passo 1, escrito.
2. Migration criada, com `docs/db/schema.sql` e `docs/db/ERD.mmd` regerados no mesmo commit (R4),
   e a declaração equivalente no modelo (R10/R11).
3. Aditivo existente (canal interno) segue assinável pelo caminho de hoje — sem regressão.
4. Aditivo novo pelo ClickSign: envia, o webhook reconhece, a reconciliação varre, e a
   assinatura completa **constitui as provisões** exatamente como pelo canal interno. Prove a
   igualdade contábil entre os dois canais com um teste que compare os lançamentos.
5. CPF inválido recusado nos dois canais.
6. E2E de navegador da tela da 11e com as duas opções.
7. Suíte verde.

Registrar como **ACHADO-69** em `docs/db/ACHADOS_CONTABEIS.md`.
