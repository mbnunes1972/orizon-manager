# TAREFA — ACHADO-69: unificar a assinatura ClickSign e trazer o Termo Aditivo para dentro

Achado do Marcelo em 10/09/2026, na etapa 11e de Homologação (`v2026.09.09-beta1`), Projeto 13.

> "Use o mesmo mecanismo de assinatura dos casos anteriores: opção de imprimir e assinar, pelo
> ClickSign."

Decisão do Marcelo em 11/09, depois de ver as duas saídas postas lado a lado:

> "Vamos fazer o mais certo. Testamos em sequência."

**Ou seja: NÃO é para espelhar a Aprovação do PE e deixar a quarta cópia.** É para extrair o
mecanismo comum, migrar os três que já existem para ele, e então o Aditivo entrar como quarto
caso — barato, porque o mecanismo já estará pronto.

---

## O que está medido — não re-medir

Quatro documentos são assinados por loja + cliente. **Três têm escolha de canal; o Aditivo não.**

| documento | `assinatura_canal` | rotas ClickSign | webhook/reconciliação |
|---|---|---|---|
| Contrato | `database.py:1323` | `/contrato/clicksign/{enviar,verificar,reenviar}` | sim |
| Aprovação do PE | `database.py:1432` | `/aprovacao-pe/clicksign/{enviar,verificar,reenviar}` | sim |
| Solicitação de medição | `database.py:1479` | sim | sim |
| **Termo Aditivo** | **não existe** | **nenhuma** | **não** |

O Aditivo tem só a porta interna: `POST /api/projetos/<nome>/aditivo/assinar` (`main.py:9587`),
cujo próprio comentário diz *"assinatura interna do termo aditivo (loja + cliente), espelho do
contrato"* — espelhou a assinatura **interna** do contrato, não a escolha de canal que o contrato
ganhou depois.

**O "imprimir" já existe** — o botão "Baixar PDF" está na tela. Falta a escolha de canal e o
caminho ClickSign inteiro.

**A duplicação que justifica unificar:** `_enviar_*_para_clicksign` e `_reconciliar_*_clicksign`
(`main.py:1271` e `1303`) existem em três versões paralelas, e o webhook
(`main.py:6642/6664/6686`) faz **três consultas** — uma por classe. Espelhar faria a quarta de
cada. É a regra dos irmãos (ACHADO-26) ao contrário: em vez de uma porta esquecida aberta, uma
capacidade que três irmãos têm e o quarto ficou sem — e o remédio errado seria criar um quarto
irmão para esquecer no futuro.

---

## A ordem — e por que ela é a própria proteção

O risco desta tarefa não é o Aditivo. É mexer em três documentos que **já funcionam em produção**.
A ordem abaixo existe para que nenhum passo dependa de confiança:

### Passo 0 — o inventário

Antes de escrever uma linha, liste para **cada um dos três** que já funcionam: modelo, colunas de
ClickSign, rotas de envio/verificação/reenvio, funções `_enviar_*` / `_reconciliar_*`, entrada no
webhook, entrada no job `/internal/clicksign/reconciliar`, cancelamento de envelope, e o ponto da
tela. Três colunas lado a lado.

**É neste inventário que a unificação se decide.** Se os três forem iguais a menos de nome, o
mecanismo comum é óbvio. **Se divergirem em comportamento** — um reenvia e outro não, um cancela
envelope e outro deixa órfão, um valida CPF em lugar diferente — então **pare e relate**: a
divergência pode ser um achado próprio, e unificar por cima dela apagaria a evidência. Não
"harmonize" silenciosamente escolhendo o comportamento que achar melhor.

### Passo 0 — feito (13/09) — DIVERGÊNCIA CONFIRMADA, parando aqui

Inventário completo abaixo. Achado central primeiro, porque muda o que vem depois: **os três NÃO
são iguais a menos de nome.** Há uma divergência de comportamento real, confirmada por dois
caminhos de investigação independentes (o dossiê do Contrato achou a função; o dossiê da
Solicitação de medição, sem saber disso, grepou o codebase inteiro por `cancelar_envelope` e achou
o mesmo único ponto de chamada) — exatamente o padrão que a instrução deste passo avisou pra não
atropelar.

#### Divergência 1 (a que manda parar): cancelamento de envelope só existe para o Contrato

`cancelar_envelope` (`integracoes/clicksign_client.py:165`) tem **um único call site em todo o
código**: `main.py:1067`, dentro de `_notificar_signatarios_clicksign_cancelamento(db, contrato,
loja_id, status_final)` (`main.py:1024-1071`) — função cujo próprio parâmetro se chama `contrato`,
chamada de dois pontos do fluxo de cancelamento de orçamento (`main.py:12451`, `12474`). Ela faz
duas coisas: avisa por e-mail cada signatário pendente que o convite não vale mais, e tenta (best
effort, nunca bloqueia o cancelamento) cancelar o envelope na ClickSign.

**Aprovação do PE e Solicitação de medição não têm nada equivalente.** Confirmado por grep
completo nos dois fluxos de "desfazer" que cada uma tem: a reprovação da AF2 (`/ciclo/11d/
reprovar`) e a redecisão de conciliação de PE (ACHADO-55, `mod_conciliacao_pe`, subfase 11e) —
zero menção a `clicksign`/`envelope` em qualquer um dos dois. Se uma Aprovação do PE ou uma
Solicitação de medição foi enviada pra ClickSign e depois é reprovada/redecidida antes de ser
assinada, **o envelope não é cancelado e o signatário não é avisado** — fica pendurado até alguém
notar (não há expiração automática nenhuma, nos três documentos: um envelope nunca assinado só
sai do limbo por reenvio manual).

#### Divergência 2: testemunhas (signatários extras) só existem no Contrato

`_enviar_contrato_para_clicksign` aceita uma lista opcional `testemunhas` (`main.py:1367-1374`) e
o modelo tem os campos de testemunha 1/2. `_enviar_aprovacao_pe_para_clicksign` não recebe esse
parâmetro. `SolicitacaoMedicaoAssinatura` não tem coluna de testemunha — e aqui há uma nota no
código dizendo que é decisão de usuário de 2026-08-17, ou seja, **essa metade já é documentada
como deliberada**; falta confirmar se a ausência em Aprovação do PE também foi uma decisão ou é
só reflexo de nunca terem pedido testemunha ali.

#### Diferença 3 (provavelmente NÃO é a divergência a investigar — já esperada pela Fronteira do pacote)

O efeito ao completar a assinatura (ambas as partes) é diferente nos três, e o próprio pacote já
avisa que isso é esperado ("o efeito contábil não muda, e é diferente por documento, de
propósito"): Contrato dispara uma cascata grande (fecha etapa 7, materializa AF1, cronograma,
segmentação, `_registrar_provisao_venda`, equipe, chat, e-mail — tudo fail-soft); Solicitação de
medição fecha a etapa 9 automaticamente; **Aprovação do PE não dispara cascata nenhuma** — o
docstring de `_registrar_assinatura_aprovacao_pe` diz explicitamente que fechar a subfase 11e
continua sendo ação manual/gerencial. Listada aqui por completude do inventário, não como achado
— mas registrando porque é o tipo exato de "comportamento diferente" que Passo 1 vai precisar
preservar através do registro parametrizado (é justamente o "o que fazer quando completa" que o
pacote já nomeia como o ponto de parametrização).

Em TODAS as outras dimensões abaixo, os três batem em comportamento — só o nome muda.

#### Tabela

| dimensão | Contrato | Aprovação do PE | Solicitação de medição |
|---|---|---|---|
| **modelo** | `Contrato` (`database.py:1284-1345`), tabela `contratos`; assinaturas em `ContratoAssinatura` (`1348-1362`) — suporta `parte` loja/cliente/testemunhaN | `AprovacaoPE` (`1410-1439`); assinaturas em `AprovacaoPEAssinatura` (`1441-1454`) — só loja/cliente | `SolicitacaoMedicao` (`1460-1484`); assinaturas em `SolicitacaoMedicaoAssinatura` (`1487-1500`) — só loja/cliente, sem testemunha por decisão de usuário 2026-08-17 |
| **colunas ClickSign** | `assinatura_canal`, `clicksign_envelope_id`, `clicksign_enviado_em`, `clicksign_signatarios_json` (`1323-1326`) | mesmas 4, mesmos tipos (`1430-1435`) | mesmas 4 (`1476-1479`) — alinhadas via migration 0006 (27/08); antes desta divergência já foi corrigida |
| **rota enviar** | `POST /contrato/clicksign/enviar` (`main.py:14626`) | `POST /aprovacao-pe/clicksign/enviar` (`10038`) | `POST /medicao/solicitacao/clicksign/enviar` (`15145`) |
| **ordem de validação em enviar** | auth → escopo → projeto → contrato → status/canal/assinatura-interna já existente → config → **testemunhas opcionais** → envia | auth → escopo → projeto → aprovação → status/canal/assinatura-interna → config → busca Contrato vinculado (erro se não houver) → envia | auth → escopo → projeto → solicitação → pdf existe/status/canal/assinatura-interna → config → exige Contrato existir → envia |
| **rota verificar** | `/contrato/clicksign/verificar` (`14711`) | `/aprovacao-pe/clicksign/verificar` (`10104`) | `/medicao/solicitacao/clicksign/verificar` (`15212`) — todas exigem `assinatura_canal=="clicksign"`, todas re-chamam a API (nunca confiam em cache) |
| **rota reenviar** | `/contrato/clicksign/reenviar` (`14750`) — `reenviar_notificacao`, notifica TODOS os signatários (limitação da API, não dá pra mirar só o pendente) | `/aprovacao-pe/clicksign/reenviar` (`10141`) — mesmo padrão | `/medicao/solicitacao/clicksign/reenviar` (`15249`) — mesmo padrão |
| **`_enviar_*`** | `_enviar_contrato_para_clicksign` (`1338-1382`) — únicoo com testemunhas | `_enviar_aprovacao_pe_para_clicksign` (`1453-1482`) | `_enviar_solicitacao_medicao_para_clicksign` (`1543-1573`) |
| **`_reconciliar_*`** | `_reconciliar_contrato_clicksign` (`1385-1423`) | `_reconciliar_aprovacao_pe_clicksign` (`1485-1509`) | `_reconciliar_solicitacao_medicao_clicksign` (`1576-1601`) — as três: `status=="closed"` é o único sinal confiável (ClickSign nunca popula `signed_at`, achado de 20/08); CPF inválido de um signatário não aborta os outros (log-and-continue) |
| **validação de CPF (ACHADO-28/F2-6)** | dentro de `_registrar_assinatura_contrato` (`1174-1195`) — único ponto, os dois canais passam por ele | dentro de `_registrar_assinatura_aprovacao_pe` — mesmo padrão | dentro de `_registrar_assinatura_solicitacao_medicao` (`1512-1540`) — mesmo padrão. **Idêntico nos três**: nunca duplicado, nunca só num canal |
| **efeito ao completar (loja+cliente assinam)** | cascata grande (ver Diferença 3) | **nenhuma cascata** — manual (ver Diferença 3) | fecha etapa 9 (ver Diferença 3) |
| **webhook** | `POST /webhooks/clicksign` (`6760-6813`), handler ÚNICO pros três — resolve por `clicksign_envelope_id` tentando Contrato → AprovacaoPE → SolicitacaoMedicao nessa ordem, despacha pro `reconciliar` correspondente. HMAC contra segredo por loja; sempre 200 mesmo em erro/sem match | idêntico (mesmo handler) | idêntico (mesmo handler) |
| **job `/internal/clicksign/reconciliar`** | bloco Contrato (`6827-6855`): canal clicksign + status em (para_assinatura/assinado_loja/assinado_cliente) + enviado há ≥10min | bloco idêntico em filtro e carência | bloco idêntico (`6878-6899`) — os três com exceção por linha isolada (uma falha não aborta o lote) |
| **cancelamento de envelope** | **existe** — `_notificar_signatarios_clicksign_cancelamento` (Divergência 1) | **não existe** | **não existe** |
| **ponto da tela** | `_renderSecaoAssinaturaContrato` (`24935`) + 3 funções de ação (`~25010-25070`) | `enviarAprovacaoPEParaClickSign`/`_confirmarEnvioClickSignPE`/`verificarClickSignPEAgora`/`reenviarConviteClickSignPE` (`22540-22604`) | `_confirmarEnvioClickSignMedicao`/`verificarClickSignMedicaoAgora`/`reenviarConviteClickSignMedicao` (`~24747-24800`) |

**Nota de higiene do pacote:** as linhas do webhook citadas no cabeçalho deste documento
(6642/6664/6686) estão desatualizadas — a posição real hoje é `6776-6783`. Não é achado, é só o
código ter andado desde que o pacote foi escrito.

#### Decidido por Marcelo (13/09) — as duas divergências, resolvidas

**Divergência 1 (cancelamento de envelope) é defeito — ganhou número próprio: ACHADO-70**
(`docs/db/ACHADOS_CONTABEIS.md`). Um envelope órfão é um link vivo do ClickSign pra assinar um
documento que já não vale — PE reprovado, envelope antigo ainda na caixa do cliente, cliente
assina, e a reconciliação (webhook ou job) varre por canal/status sem checar se a decisão que
motivou o envio ainda é a atual, tratando essa assinatura tardia como boa.

**Como entra no Passo 1/2, sem misturar refatoração com mudança de comportamento:** o mecanismo
unificado ganha o cancelamento como **capacidade do registro** (todo documento pode declarar como
cancelar seu envelope), mas cada documento existente migra no Passo 2 **preservando o
comportamento de hoje** — Contrato continua cancelando, Aprovação do PE e Solicitação de medição
continuam SEM cancelar automaticamente, exatamente como estão em produção agora. Ligar o
cancelamento nesses dois é **mudança de comportamento**, não extração de mecanismo, e por isso não
entra de carona: vai em **commit separado, com teste próprio, depois que a migração de cada
documento já estiver com a suíte verde** — pra que o histórico deixe legível qual commit mudou o
quê, sem confundir "extrair sem mudar nada" com "mudar o que o sistema faz". Isso é trabalho do
Passo 2 e seguintes, não deste Passo 0.

**Divergência 2 (testemunha) fica FORA do escopo do ACHADO-69.** A ausência na Solicitação de
medição é decisão registrada de 17/08 — não mexer. A ausência na Aprovação do PE é **desconhecida**
(lacuna ou decisão nunca documentada), e desconhecido não se resolve unificando por cima. Registrada
como pergunta em aberto em `docs/db/LISTA_PARALELA.md`, citando a data da decisão da Solicitação de
medição para contraste. Este pacote não toca nisso.

Com as duas resolvidas (uma virou achado próprio e entra faseada; a outra saiu do escopo), o Passo
0 está fechado e o pacote segue para o Passo 1.

### ACHADO-70 — fechado (13/09), depois das três migrações do Passo 2

Cancelamento de envelope ligado para Aprovação do PE (`/ciclo/11d/reprovar` E `/aprovacao-pe/
gerar` — a regeração era um SEGUNDO ponto de órfão, independente da reprovação, achado ao medir)
e Solicitação de Medição (só `/medicao/solicitacao/gerar`, sem verbo de reprovação próprio).
Commit e teste próprios (`tests/test_achado70_cancelamento_envelope.py`, 8 testes, as três
propriedades pedidas: cancela no evento, não explode em chamada repetida/documento nunca
enviado, ClickSign fora do ar não trava o evento de negócio). Detalhe completo, inclusive as
respostas às três perguntas de medição, em `docs/db/ACHADOS_CONTABEIS.md` § ACHADO-70.

### Passo 1 — extrair o mecanismo, sem mudar comportamento

Um módulo (sugestão: `mod_assinatura.py`) com o ciclo de vida do envelope parametrizado por
documento: envio, verificação, reenvio, cancelamento, reconciliação. Cada classe entra por um
**registro** — modelo, como achar o signatário, que PDF gerar, o que fazer quando a assinatura
completa (é aqui que cada documento difere de verdade).

O webhook e o `/internal/clicksign/reconciliar` passam a **iterar o registro** em vez de repetir a
consulta por classe. Acrescentar um documento vira uma entrada no registro — que é exatamente o
que torna o Passo 3 barato.

**Aceite deste passo, e ele é duro:** os três documentos continuam com **exatamente** o mesmo
comportamento, e a suíte que já existe prova isso **sem nenhuma asserção mudar**. Se um teste
precisar mudar o que afirma para passar, isso não é refatoração — é mudança de comportamento
disfarçada. Pare e relate.

### Passo 2 — provar um a um, não os três de uma vez

Migre **um** documento por commit, na ordem: **Solicitação de medição → Aprovação do PE →
Contrato**. Do menos exposto para o mais exposto. Suíte verde entre cada um.

O Contrato por último de propósito: é o que mais dói se quebrar, e chega quando o mecanismo já
sobreviveu a duas migrações.

### Passo 3 — fechado (13/09) — o Aditivo como quarto caso

Feito: migration `5325ac7badfa` (4 colunas, `server_default='interno'`, `schema.sql` no mesmo
commit — `ERD.mmd` conferido e não precisou mudar, é só FK); entrada no registro +
`/aditivo/clicksign/{enviar,verificar,reenviar}` espelhando os irmãos; cancelamento de envelope
já ligado desde o primeiro commit (sem comportamento anterior pra preservar, ao contrário dos
três irmãos); CPF (ACHADO-28) e a checagem de recebível (ACHADO-24) cobrindo o canal ClickSign;
ACHADO-21 6-c resolvido exigindo `forma_pagamento` no ENVIO (não há instante síncrono na
conclusão remota); igualdade contábil provada por teste que compara `Lancamento` reais das duas
rodadas (aceite 6). Tela da 11e oferece a escolha, "Baixar PDF" manteve o nome. Detalhe completo
em `docs/db/ACHADOS_CONTABEIS.md` § ACHADO-69.

Aceite 10 fechado: `pytest -q` completo, 2793 passed / 4 xfailed / 0 failed, 604,5s, zero `+++
Timeout`. **Não fechado:** aceite 9 (E2E de navegador) — deliberadamente adiado pra não somar
mais um arquivo à rodada de flakes de E2E ainda não investigada (RODADA3) — e o percurso manual
(`docs/db/PERCURSO_HOMOLOGACAO.md`, "testamos em sequência"), que é item do Marcelo.

### Passo 3 — especificação original (arquivada, já executada acima)

**O dado.** `Aditivo` (`database.py:1365`) ganha `assinatura_canal` e os campos de ClickSign que os
irmãos têm (o inventário do Passo 0 diz quais).

> **R1:** vai em **migration**, nunca em `_migrar_colunas_pg`, que está congelado. As linhas
> 2535/2539 do `database.py` acrescentaram `assinatura_canal` a `contratos` e `aprovacoes_pe` por
> lá — **não repita esse caminho**; é dívida registrada, não exemplo. `assinatura_canal` do Aditivo
> nasce com `server_default='interno'`, como os irmãos, para que aditivo já existente continue no
> canal interno sem migração de dado.
> **R4:** `docs/db/schema.sql` e `docs/db/ERD.mmd` regerados no mesmo commit. **R10/R11:** a
> declaração equivalente no modelo.

**O backend.** Uma entrada no registro. Se o Passo 1 estiver certo, é pouca coisa — e se não for
pouca coisa, o Passo 1 não terminou.

**A tela.** Na 11e, o bloco do Termo Aditivo passa a oferecer a mesma escolha dos outros: assinar
internamente (nome + CPF, como hoje) **ou** enviar pelo ClickSign, com o estado do envelope visível
e o reenvio disponível. Imprimir continua pelo "Baixar PDF".

---

## Fronteiras

- **A validação de CPF continua valendo nos dois canais** (ACHADO-28, F2-6:
  `validacao_doc.erro_doc` dentro dos `_registrar_assinatura_*`). Ao unificar, ela não pode cair
  para dentro de um caminho só.
- **O efeito contábil não muda, e é diferente por documento.** A assinatura completa (loja +
  cliente) do Aditivo constitui as provisões da diferença negociada — o docstring de `Aditivo`
  registra isso. É justamente o "o que fazer quando completa" que o registro parametriza; se o
  mecanismo comum achatar isso, está errado. **Se o caminho ClickSign não disparar a mesma
  constituição que o interno, o pacote está errado.**
- **ACHADO-25 é a lição a não repetir:** foi na tela do aditivo que um campo obrigatório novo
  passou despercebido e nenhum aditivo pôde ser assinado em produção, com 2466 testes verdes. Toda
  mudança de contrato de endpoint aqui diz **quem chama** e confere o chamador real em
  `static/index.html`.
- **Nenhum teste sai do `pytest -q`.** Se algum precisar de isolamento, resolva o isolamento.
- Não tocar em Produção, tag ou deploy.

---

## Aceite

1. O inventário do Passo 0, escrito — inclusive as divergências entre os três, se houver.
2. Passo 1 fechado **sem nenhuma asserção alterada** nos testes existentes.
3. Três commits de migração (Passo 2), suíte verde em cada um.
4. Migration do Aditivo criada, com `schema.sql` e `ERD.mmd` no mesmo commit.
5. Aditivo existente (canal interno) segue assinável pelo caminho de hoje — sem regressão.
6. Aditivo novo pelo ClickSign: envia, o webhook reconhece, a reconciliação varre, e a assinatura
   completa **constitui as provisões** exatamente como pelo canal interno. **Prove a igualdade
   contábil entre os dois canais com um teste que compare os lançamentos**, não com inspeção.
7. CPF inválido recusado nos dois canais, nos **quatro** documentos.
8. Webhook e `/internal/clicksign/reconciliar` cobrindo os quatro — teste que falha se um documento
   ficar de fora do registro. Envelope que ninguém reconcilia é assinatura que some.
9. E2E de navegador da tela da 11e com as duas opções.
10. `python3 -m pytest -q` completo, verde.

## O teste em sequência (Marcelo, manual)

Depois da suíte, o percurso pelos quatro na ordem em que aparecem no ciclo, cada um nos **dois**
canais: **Contrato → Aprovação do PE → Solicitação de medição → Termo Aditivo**. É o que a decisão
de 11/09 chamou de "testamos em sequência" — a suíte prova o servidor, o percurso prova o sistema.

Item novo no `docs/db/PERCURSO_HOMOLOGACAO.md` para essa sequência.

## Registro

Registrar como **ACHADO-69** em `docs/db/ACHADOS_CONTABEIS.md` — ele ainda **não está lá**, só
existe como pacote. Linha no `docs/db/ROTEIRO.md`.

Se o Passo 0 revelar divergência de comportamento entre os três, ela vira **achado próprio**, com
número próprio, e não some dentro deste.
