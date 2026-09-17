# Rascunho para debate — o portão que ninguém consegue ler

> **Camada 4 · TRABALHO EM ANDAMENTO.** Rascunho para debate, não tarefa. Nada aqui é ordem de
> execução: o Claude Code vai ler, discordar do que achar errado, e o texto final sai depois.

**Data:** 2026-09-17
**Autor do rascunho:** Cowork (Claude), a partir do registro existente — **não medi nada disto eu
mesmo.** Tudo abaixo vem de `LISTA_PARALELA.md` (LP-22), `TAREFA_FLAKES_E2E.md`,
`TAREFA_ESTABILIDADE_SUITE.md`, `TAREFA_ESTABILIDADE_RODADA3.md` e dos relatórios da Sessão A.
Se alguma leitura estiver errada, é por isso — corrija.

**Decisão do Marcelo (17/09):** o assunto entra na sequência do lote do Aceite 6. Concordou com o
enunciado do problema antes de ver este rascunho.

---

## 1. O problema, enunciado

A `ESTEIRA.md` exige suíte verde para cortar tag. A suíte não consegue produzir verde de forma
confiável — a família de flakes de E2E de navegador (`#neg-subtotal` e o que sobrou) falha em
número e composição diferentes a cada rodada.

A consequência não é o tempo perdido. É que **o portão deixou de ser mecânico e virou julgamento.**
Cada tag agora exige que alguém olhe a lista de vermelhos e decida se "é o flake de sempre". Hoje
isso funciona porque quem está olhando é cuidadoso: em 17/09 a Sessão A fez um A/B contra o código
sem as mudanças, três rodadas, e **parou antes da tag para perguntar** em vez de decidir sozinha.
Foi exemplar.

Mas um portão que depende de alguém ser exemplar toda vez tem duas falhas previsíveis:

- **No caso bom, dá confiança falsa.** "8 vermelhos, todos conhecidos" vira hábito, e o dia em que
  o nono for de verdade, ele entra junto.
- **No caso ruim, convida racionalização.** A pressa aparece — 01/10 está marcado — e "é o flake de
  sempre" é a explicação mais barata disponível. Ela vai estar certa quase sempre. É exatamente por
  isso que é perigosa.

**Dois problemas, não um.** Vale separar, porque têm prazos diferentes:

- **(A) O portão.** Precisa voltar a ser legível **antes de 01/10**, porque a partir daí cada tag
  carrega dado de cliente real.
- **(B) O flake.** `#neg-subtotal` está sem causa raiz desde a RODADA3. Pode levar dias. Não pode
  bloquear (A).

---

## 2. O que já se sabe (e que o desenho precisa respeitar)

Do registro, sem interpretação nova:

1. **Não é contaminação cruzada pura.** Os 15 testes da família falham **também isolados**, com
   taxa de 1/10 a 10/10 (`TAREFA_FLAKES_E2E.md`, 8 rodadas completas + isolamento individual).
2. **Não é tempo de espera curto.** Medido: `#neg-subtotal` leva 783 ms isolado e 780–785 ms em
   suíte. Alargar o timeout esconderia o defeito atrás de um número maior, não o resolveria.
3. **Não é o timeout de 5 s do `HttpClient`.** Medido: p50 5 ms, máximo 1,18 s em 2767 chamadas.
4. **Não é o agendamento do pytest numa rodada serial.** São 30 arquivos com `servidor_e2e`
   `scope="module"`, sem `xdist`, rodando em série.
5. **Duas invocações simultâneas de `pytest` são catastróficas** — colisão sistemática nos bancos
   compartilhados. É por isso que a Sessão B nunca roda `pytest`.
6. **O travamento de 12 h está resolvido** (método `thread` no pytest-timeout, RODADA3) — o pior
   caso hoje é falha legível, não bloqueio silencioso.
7. **Uma família já foi fechada de verdade**: `#np-cli-dropdown`, causa nomeada (debounce implícito
   de 300 ms, corrigido com `expect_response`). Prova de que estas coisas têm causa e cedem quando
   a medição certa aparece.

**O que isso sugere, e é hipótese minha, não medição:** um teste que falha isolado com taxa
variável, sem relação com carga nem com tempo de espera, tem cara de **corrida dentro da própria
aplicação ou do próprio teste** — algo que às vezes não acontece, e não algo que acontece devagar.
A diferença importa: "devagar" se resolve esperando mais; "às vezes não acontece" não se resolve
esperando, e é por isso que alargar timeout nunca funcionou aqui.

---

## 3. Proposta para (A) — devolver a legibilidade ao portão

**A ideia:** tornar o julgamento **dado**, não decisão de quem está cortando a tag.

Hoje: "8 vermelhos — serão os de sempre?" → alguém decide.
Proposta: existe uma **lista nomeada de quarentena**, teste a teste. O portão da tag passa a ser
**zero vermelho fora da quarentena**, o que é mecânico e não pede julgamento. A suíte inteira
continua rodando e reportando — a quarentena não esconde nada, só deixa de bloquear.

Três garantias para a quarentena não virar cemitério, que é o risco óbvio:

1. **Catraca que só desce.** Um teste afere o tamanho da lista e falha se ela crescer. É o mesmo
   mecanismo do `test_contagem_total_de_showtoast_de_erro_no_sistema`, que a casa já usa e entende.
   Entrar na quarentena passa a ser um ato deliberado, com número mudando no commit.
2. **Cada linha tem nome, data e motivo.** Não "flakes de E2E" — `arquivo::teste`, quando entrou,
   e qual assinatura de falha. Quem ler daqui a três meses sabe o que é.
3. **Validade.** A lista é revisitada em data marcada. Sem isso, item em quarentena nunca mais é
   olhado.

**O que explicitamente NÃO proponho, e por quê:** *rerun automático* (`pytest-rerunfailures`,
"passou na segunda tentativa = verde"). Seria a solução mais rápida e é a errada: ela esconde
justamente a classe de defeito que mais interessa — o intermitente de verdade. A casa já aprendeu
essa lição uma vez, quando alargar o timeout teria escondido o defeito real atrás de um número
maior.

---

## 4. Proposta para (B) — parar de raciocinar e capturar a falha

A RODADA3 mediu **quanto tempo** a espera leva quando dá certo (783 ms). O que não existe no
registro é **o que a página estava fazendo no instante em que deu errado**.

Sugestão: em vez de mais rodadas contando falhas, **capturar evidência no momento da falha**:

- Trace do Playwright retido só em falha, com snapshots de DOM.
- Console e requisições de rede do navegador anexados ao relatório do teste que falhou.
- No timeout de `#neg-subtotal`: o estado real daquele trecho do DOM — existe e está vazio, não
  existe, ou tem valor diferente do esperado? As três respostas apontam para causas diferentes.

Três falhas com trace provavelmente dizem mais que oito rodadas contando.

**Pergunta honesta, e é para o Claude Code responder:** isso é viável neste arranjo, em que cada
arquivo sobe o próprio servidor? Qual o custo em tempo e disco? Se o trace só aparecer em falha,
o custo na rodada boa deveria ser próximo de zero — mas é você quem sabe.

---

## 5. Perguntas abertas — o que este rascunho quer do Claude Code

1. **A quarentena resolve mesmo o portão, ou só o maquia?** Se a família anda (hoje falham estes
   8, amanhã outros da mesma assinatura), uma lista de nomes fixos não segura — e aí a unidade de
   quarentena talvez tenha de ser o *arquivo* ou a *assinatura*, não o teste. Qual é a unidade
   certa, medida?
2. **O trace é viável e informativo aqui?** Ver §4.
3. **O que é `#neg-subtotal` e quem o preenche?** O preenchimento é disparado por evento que pode
   se perder? Isso é leitura de código, não rodada de suíte — e pode ser o caminho mais curto.
4. **Vale separar o banco por arquivo de E2E?** O registro diz que isolamento não elimina o flake,
   então provavelmente não é a causa — mas removeria a causa raiz do LP-22 (DDL no boot, banco
   compartilhado) e permitiria duas sessões rodarem `pytest` ao mesmo tempo, o que hoje é proibido.
   Ganho colateral grande. Custo?
5. **Tem alguma coisa aqui que você já mediu e sabe que está errada?** Diga logo. Este rascunho foi
   escrito de fora, lendo o registro — é a posição mais sujeita a repetir hipótese já derrubada.

---

## 6. O que fica combinado antes de qualquer implementação

- Isto é debate. **Nada aqui é para implementar ainda.**
- O Claude Code responde com a visão dele; o Marcelo traz as considerações de volta; o texto final
  da tarefa sai depois disso.
- (A) e (B) podem andar em ritmos diferentes. Se (B) for longo, (A) sai antes — o portão precisa
  estar legível em 01/10, o flake não precisa estar morto.
