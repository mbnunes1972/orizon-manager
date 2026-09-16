# Plano — Semana 2 (21–27/09/2026)

Escrito pela Sessão B, 15/09/2026. Uma página, para rodar a semana sem abrir os pacotes de novo —
cada um só quando o dia chegar. Pacotes referenciados: `TAREFA_MANIFESTO_ROTAS.md` (6.6),
`TAREFA_MANIFESTO_ADMIN_CONFIG.md` (6.5), `TAREFA_TELA_UNICA_PROVISOES.md` (6.2),
`TAREFA_SPLIT_FRONTEND.md`, `TAREFA_TRANSICOES_RASCUNHO.md` (6.1, ainda sem desenho).

## Sequência

| Dia | O quê | Depende de |
|---|---|---|
| **Seg 21** | Checkpoint: o que sobrou da fila da beta (LP-02 e qualquer achado de Semana 1 ainda aberto) fecha primeiro, antes de abrir Semana 2. Depois: **6.6** (rotas no manifesto). | Nada — é o ponto de partida. |
| **Ter 22** | **6.5** (Admin/Config no manifesto). Depois, início do **split**: `admin.js`, `expedicao.js` — as duas provam o mecanismo e a segunda resolve o Caso 1 (`_expPoll`). | 6.5 depende de 6.6 pronto (mesmo arquivo `modulos.py`, mesma ordem já registrada no pacote da 6.5). |
| **Qua 23** | Split, onda de baixo risco: `plataforma.js`, `fiscal.js`, `assistencias.js`, `montagem.js`. | Mecanismo já provado na terça. |
| **Qui 24** | Split: `cadastro.js`, `ciclo.js`, `chat.js`. | Nenhuma — mas precisam existir antes de sexta (ver Config abaixo). |
| **Sex 25** | **Exceção deliberada à ordem de risco do split** (ver nota): `financeiro.js` e `folha.js` saem agora, com escrutínio extra (diff de conteúdo + E2E rodado mais de uma vez — `TAREFA_SPLIT_FRONTEND.md` § 5). Na sequência, `config.js` (remanejamento das funções `cfg*` — Caso 5 do split). | `config.js` depende de `cadastro.js` (quinta) + `folha.js`/`financeiro.js` (hoje) já existirem — as cinco funções `cfg*` migram para eles. |
| **Sáb 26** | **6.2** — Tela Única de Provisões, construída DENTRO do `financeiro.js` já extraído. | `financeiro.js` extraído (sexta). Esta é a dependência mais importante da semana: construir a 6.2 antes da extração faria o split reconciliar código que mudou de forma no meio do caminho. |
| **Dom 27** | **Espaço reservado — 6.1**, só se o desenho já estiver decidido (ver abaixo). Se sobrar tempo: `comercial.js` (não bloqueia nada esta semana, pode continuar depois). Fechamento da semana (ver critério abaixo). | 6.1 depende de decisão externa a este plano. |

**Se a semana apertar, a ordem de corte é a inversa da tabela**: `comercial.js` primeiro a ceder
lugar, depois `chat.js` (é grande, não bloqueia nada), depois o resto do split de baixo risco —
nessa ordem, porque nenhum dos três impede o fechamento da semana (ver critério, último item).
**O que NÃO pode ceder**: 6.6, 6.5, `financeiro.js`+`folha.js` extraídos, e 6.2 funcionando.

## Por que `financeiro.js` sai fora de ordem

`TAREFA_SPLIT_FRONTEND.md` recomenda money-critical por último, para provar o mecanismo em área
barata primeiro. Isso continua valendo — só que a 6.2 é a exceção conhecida: ela só pode ser
construída dentro do arquivo já extraído (não no monólito, não depois). Resolução: prova-se o
mecanismo em quatro áreas baratas (terça–quinta) antes de tocar em `financeiro.js`, e quando a
vez dele chegar (sexta), a extração recebe cuidado extra — não porque a ordem geral mudou de
princípio, mas porque este arquivo específico foi puxado para a frente por uma dependência real.

## Espaço reservado — Fronteira 6.1

**Sem conteúdo definido de propósito.** O desenho (`TAREFA_TRANSICOES_RASCUNHO.md`, três opções)
é decisão do Marcelo com o Claude do navegador — este plano só reserva o lugar, domingo, depois de
`ciclo.js`/`core.js` já existirem (se o desenho escolhido tocar frontend, tem onde morar). **Se a
decisão não sair a tempo, o espaço fica vazio** — LP-25 e LP-26 continuam em FRONTEIRA/6.1,
esperando a próxima janela. Não é atraso: é o Marcelo tendo decidido tomar esse tempo.

## Fora da Semana 2 — nomeado, para não reaparecer no meio dela

- **6.3 (Estoque como domínio)** e **6.4 (Montagem como domínio)** — fora por decisão do Marcelo,
  pós-1.0.
- **LP-18 (fases/recebimento)** — o desenho de tela fechou, mas a medição confirmou que a peça
  cara (Conferência de Volumes item a item) não existe e não é barata; fica em FRONTEIRA/6.3,
  então herda o adiamento dela.
- **Fila da 1.0** (LP-01, LP-12, LP-14) — decisões já tomadas, implementação agendada de propósito
  para depois de 01/10.
- **6.7 (Captação real)** — pós-1.0; o `Lead` provisório segura a demanda até lá.
- **HIGIENE (LP-03, LP-11, LP-27, LP-28)** — não agendado, não proibido: se sobrar uma tarde,
  cabe; se não sobrar, não bloqueia nada e continua na lista.
- **6.8 (ratchet de linha)** — não é item à parte: resolve-se sozinho como consequência da Seção 4
  do `TAREFA_SPLIT_FRONTEND.md`, no dia em que `financeiro.js`/`ciclo.js` forem extraídos.

## Como saber que a semana terminou

No dia 27, a semana está fechada quando:
1. `modulos.py` tem as rotas corrigidas (aceite da 6.6) e Admin/Config como núcleo (aceite da 6.5).
2. A Tela Única de Provisões funciona nos dois pontos de montagem (aceite da 6.2), dentro de
   `financeiro.js` já extraído.
3. Pelo menos `admin.js`, `expedicao.js`, `financeiro.js` e `folha.js` estão extraídos e provados
   idênticos (diff de conteúdo — `TAREFA_SPLIT_FRONTEND.md` § 5). O resto do split pode continuar
   depois sem prejuízo: é mecânico, de baixo risco, e não tem mais nada desta semana esperando por
   ele.
4. Todo defeito encontrado pelo caminho virou linha em `LISTA_PARALELA.md` — nenhum conserto
   escondido dentro de um commit de split ou de manifesto.
5. A 6.1 está OU decidida-e-em-andamento, OU explicitamente adiada — nunca "esquecida no meio".
6. Nenhuma rodada nova de caça a flakes E2E (regra que já vem da Semana 1) — flake achado no
   caminho é `LISTA_PARALELA.md` também, não investigação nova.
