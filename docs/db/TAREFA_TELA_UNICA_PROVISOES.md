# Tarefa — Tela Única de Provisões (Fronteira 6.2 / LP-13)

Pacote de execução da Semana 2 (21–27/09), escrito pela Sessão B a partir da Seção 6.2 do
`docs/db/MAPA_MODULOS.md` e do desenho que o Marcelo fechou em 05/09 (`docs/db/
LISTA_PARALELA.md`, item LP-13). **Diferente das outras duas fronteiras desta rodada, aqui não há
decisão de desenho pendente** — o trabalho é implementar o que já foi decidido, não desenhar algo
novo.

## O que está medido

**Os quatro caminhos de hoje, com âncora exata (nome de função/id, não linha):**

1. **Financeiro em leitura** — aba `#fin-panel-prov`, conteúdo montado em `#loja-panel-financeiro`.
   Monitoramento (saldo em aberto), sem ação.
2. **Modal de Reconciliação do projeto** — `#recon-proj-box`, renderizado por `reconProjRender()`.
   Ações: `reconProvEfetivar`, `reconProvResolver`, `reconProvSalvarData`.
3. **Tabela da Conciliação Final** — aba `#fin-panel-recon`, montada por `reconRodar()`/
   `reconInit()`.
4. **A Fila** — aba `#fin-panel-filaprov`, conteúdo em `#filaprov-box`; backend `GET /api/
   financeiro/fila-provisoes` (lista) e `POST /api/financeiro/fila-provisoes/veredito` (decide).

**Backend que já existe e não muda de lugar:** `mod_contabil.vereditos_validos_para_saldo(saldo)`
(fonte única das opções válidas — já corrigiu o ACHADO-41, dois pontos de chamada hoje:
`mod_contabil.py`, dentro da montagem de linha da reconciliação e da fila), `mod_contabil.
conciliar_final(...)` (fecha o projeto aplicando os vereditos), `database.VeredictoProvisao` (onde
o veredito é gravado), `mod_contabil.provisoes_em_aberto(db, owner_tipo, owner_id)` (a consulta
que lista provisão aberta — hoje já é usada tanto pela Fila quanto, possivelmente, por outros
pontos; **confirmar exatamente quais dos quatro caminhos já compartilham esta consulta e quais
ainda têm a própria**, é o primeiro passo de medição da Sessão A antes de tocar em UI).

**O desvio que o ACHADO-26 nomeou:** `POST /api/financeiro/resolver-saldo-provisao` zera saldo
**sem veredito**, e é usado legitimamente por duas rubricas que a regra de veredito exclui de
propósito — Impostos (2.1.04.13) e Custo Financeiro (2.1.04.19). `docs/db/
TAREFA_FILA_PROVISOES.md` (Parte 2) já mediu isto antes de restringir; a medição continua válida,
reconfirme os usos legítimos antes de mexer no endpoint.

**Contexto histórico que NÃO é o desenho a seguir:** `docs/db/TAREFA_CONCILIACAO_UI.md` (01/09) é
um documento **anterior e parcialmente superado** por este redesenho — os itens 1 e 6 dele (o
botão que o servidor recusa, e a correção do que quebrou) já viraram os ACHADO-32/33, hoje
resolvidos (`docs/db/MAPA_MODULOS.md`, § 2.3). Os itens 2, 3, 4, 5, 7, 8 desse documento antigo
podem ainda ter pontos válidos (status de veredito na linha, tooltip explicando cada veredito), mas
**o desenho que manda agora é o das sete decisões de 05/09 abaixo** — onde os dois divergirem,
vale o mais novo.

## O que fazer

O desenho fechado com o Marcelo em 05/09, ponto a ponto:

1. **Uma tela só, a Fila, morando no módulo Financeiro** (`#fin-panel-filaprov` continua sendo o
   lugar — não cria aba nova), filtrável por projeto e por conta, agrupada por projeto com as
   contas abrindo ao selecionar, no design que hoje é usado na tela do ciclo (`#recon-proj-box`
   é a referência visual, não o código a copiar).
2. **A tela de provisões DO CICLO permanece** (`#recon-proj-box`/`reconProjRender()` continuam
   existindo como ponto de entrada, alcançado de dentro do projeto) — mas passa a apontar para o
   MESMO endpoint, a MESMA consulta e o MESMO box de veredito que a Fila usa. **Um componente, dois
   pontos de montagem.** O risco que este pacote existe para evitar não é ter duas telas — é ter
   duas implementações do mesmo componente. Concretamente: extrair o box de veredito (hoje
   espalhado entre `reconProvEfetivar`/`reconProvResolver` e o equivalente da Fila) para uma função
   JS só, chamada dos dois lugares com o contexto (projeto vs fila) como parâmetro.
3. **O contador ("N provisões em aberto")** sai da MESMA consulta da lista, escopos diferentes só
   pelo filtro — número divergente entre as duas telas é defeito por construção a partir de agora
   (vira caso de teste, ver Aceite).
4. **O veredito deixa de ser texto e vira botão "Resolver"**, que NÃO navega: abre o box na própria
   linha, valha ela no ciclo do projeto ou na Fila.
5. **As opções do box vêm do SERVIDOR** (`vereditos_validos_para_saldo`), nunca fixas na tela —
   isso já é verdade hoje (ACHADO-41); este pacote não pode regredir isso. Se a extração do
   componente (item 2) reescrever a chamada, o teste de regressão do ACHADO-41 continua sendo o
   controle.
6. **"Vai Chegar" NÃO é veredito, é ADIAMENTO:** Absorver, Receber e Encerrar fecham a conta;
   Adiar mantém a linha viva, com data prevista, marcada como aguardando na fila. Confirmar que
   `vereditos_validos_para_saldo` e `VeredictoProvisao` já expressam essa distinção ou se precisam
   de um campo/flag novo — não estava explícito na medição desta rodada, é o primeiro ponto a
   confirmar por leitura antes de escrever código.
7. **O valor da despesa vem PRÉ-PREENCHIDO com o saldo disponível da provisão e continua
   editável** — mesma regra da LP-15 ("sugere, não manda"): o número calculado nunca é a única
   opção, é só o ponto de partida.

## Fronteiras — o que este pacote toca, e o que não

**Toca:** os quatro pontos de montagem listados em "O que está medido" (unificando 2 e 3 num
componente com 4), mais qualquer ajuste em `VeredictoProvisao`/`vereditos_validos_para_saldo`
necessário para expressar "Adiar" como não-veredito (item 6 — a confirmar por leitura antes de
decidir se precisa mudar).

**Não toca:**
- `POST /api/financeiro/resolver-saldo-provisao` além do necessário para os usos legítimos
  continuarem funcionando — não é este pacote que decide se ele fica mais restrito; isso já foi
  medido e resolvido nas rodadas anteriores (`TAREFA_FILA_PROVISOES.md`, Parte 2). Se a unificação
  do componente tocar nele incidentalmente, o aceite 3 abaixo é o controle positivo.
- O motor de cálculo de saldo, provisão, ou qualquer conta do plano — este pacote é interface,
  não contabilidade. Nenhuma conta muda de natureza, nenhum lançamento novo é inventado.
- Fronteiras 6.1, 6.3, 6.4, 6.5, 6.6 — nenhuma dependência entre elas e esta. Pode ser feita em
  paralelo ou em qualquer ordem em relação às outras duas desta rodada.

## Aceite

1. **Zerar o saldo pelo desvio e concluir o projeto continua recusado** — reconfirmar o teste que
   já prova o ACHADO-26 fechado (se existir `xfail(strict=True)` citando ACHADO-26, ele vira
   asserção normal; se não existir, este pacote o cria).
2. **Cada veredito pela Fila, isolado** — inclusive "Adiar" mantendo o projeto aberto e "Encerrar"/
   "Absorver"/"Receber" fechando a conta.
3. **Controle positivo:** os usos legítimos de `resolver-saldo-provisao` (Impostos, Custo
   Financeiro) continuam funcionando depois da unificação do componente.
4. **Fluxo completo pela tela, nos DOIS pontos de montagem:** dar veredito na Fila e ver o projeto
   refletir; dar veredito de dentro do projeto (`#recon-proj-box`) e ver a Fila refletir. É o
   aceite que prova "um componente, dois pontos de montagem" de verdade — não duas telas que
   coincidem hoje e divergem amanhã.
5. **O contador da Fila e a contagem por projeto nunca divergem** — teste que cria N provisões em
   aberto espalhadas por M projetos e confere que a soma bate dos dois lados.
6. **ACHADO-37 (a fila empilhando todos os projetos sem filtro) fecha "de graça"** — teste
   específico filtrando por projeto e por conta.
7. Suíte de Financeiro/Provisões/Conciliação passa inteira — comando e verificação são decisão da
   Sessão A, não desta tarefa.
