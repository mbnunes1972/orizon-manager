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

### Passo 3 — o Aditivo entra como quarto caso

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
