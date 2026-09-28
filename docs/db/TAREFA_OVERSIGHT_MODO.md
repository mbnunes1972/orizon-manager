# Tarefa — Oversight é um MODO, e precisa entregar os mesmos dados da lista normal

> **Camada 4 · TRABALHO EM ANDAMENTO.** Descartável quando fechar.
> Aberta em 28/09/2026, de uso real em Homologação na `v2026.09.26-beta1`, logo depois do
> OVERSIGHT-ENTRAR fechar. Duas queixas do Marcelo no mesmo print. SEM DDL.

## Queixa 1 — a lista do Oversight esconde informação que a lista normal mostra

Com o Oversight LIGADO o item aparece com "Grupo · Triagem". Com ele DESLIGADO, o mesmo item
aparece com "Triagem · **Janela fechada**".

**Medido em 28/09** (`chat/core.py::listar_todas_conversas`, ~1133-1160): a função monta o item
à mão e devolve `id, tipo, titulo, projeto_nome, segmento, urgente, status, pendente,
pode_entrar, participantes, assunto, ultima_previa, ultima_em, criado_em`. Não devolve
**`janela`** nem **`responsavel`**. A tarja não aparece porque o dado não chega à tela — não é
CSS, não é filtro, não é permissão.

É a MESMA causa que já tinha explicado o "Responsável: SAC" do dia 26 (o frontend cai no
fallback "sem responsável → SAC" porque o campo não vem). Dois sintomas, uma origem: o
serializer do Oversight divergiu do serializer da inbox e ninguém percebeu, porque cada um foi
crescendo do seu lado.

**Por que isso importa mais do que parece:** quem usa o Oversight é o gerente procurando o que
ninguém respondeu. A janela de 24h é a única informação da tela com PRAZO — passou, não se
responde mais por texto livre. Esconder justamente dele é esconder do único que pode agir.

### O conserto
1. `listar_todas_conversas` passa a entregar **`janela`** e **`responsavel`** com o mesmo
   conteúdo e o mesmo formato da inbox pessoal (`_atendimento_meta` / `serializar_conversa`).
2. **Não duplicar o cálculo.** Se hoje a inbox monta isso num ponto e o Oversight noutro, o
   certo é os dois chamarem a MESMA função. Já temos a lição das quatro cópias do predicado de
   partição (TAREFA_TRIAGEM_E_CONTADOR.md, Item 2) — não abrir a quinta.
3. Conferir o custo: `listar_todas_conversas` já faz uma query de última mensagem por conversa
   dentro do laço, e o teto de 300 da fila não se aplica aqui. Se `janela` acrescentar outra
   query por item, meça e reporte antes de aceitar — poll de 45s de todo gerente de toda loja.

### Custo medido (item 3 do conserto) — antes de aceitar

Medição real (contador de statements via `event.listen(engine, "before_cursor_execute", ...)`,
5 conversas de teste, `listar_todas_conversas` chamada uma vez):

| cenário | queries totais | por item | delta vs. hoje |
|---|---|---|---|
| HOJE (antes desta tarefa) | 16 | 3,2 | — |
| + `janela`/`responsavel`, todas COM responsável, SEM segmento próprio (pior caso comum) | 28 | 5,6 | **+2,4/item** |
| + só `janela`, responsável e segmento já setados (melhor caso) | 21 | 4,2 | **+1,0/item** (garantido — `janela_da_conversa` sempre roda) |

**Composição do custo novo:** `janela_da_conversa` é **+1 query/item, sempre** (não tem
condição que evite); `_resolver_responsavel` é **+1 query/item SE** `responsavel_usuario_id`
estiver setado (comum — a maioria das conversas atendidas tem responsável); o fallback de
segmento dentro de `_atendimento_meta` é **+1 query/item SE** `Conversa.segmento` for `NULL`
(menos comum — a triagem normalmente já grava o segmento na materialização). Faixa real:
**+1 a +3 queries por item**, dependendo do estado de cada conversa.

**Não é uma categoria nova de risco — é a mesma ausência de teto de hoje, mais cara.** A função
já fazia 2 queries garantidas por item (`_nomes_participantes` + última mensagem) sem limite
nenhum antes desta tarefa (diferente da fila de "sem dono", que tem `limite`) — o poll de 45s de
todo gerente de toda loja já pagava esse custo. Este item aumenta o custo por conversa em ~30-90%,
não introduz o problema do "sem teto", que já existia. **Não decidi sozinho colocar um teto aqui**
— não foi pedido, e mudaria comportamento (Oversight mostrando só as N mais recentes) que não é
desta tarefa; fica registrado como achado conhecido, não corrigido, se o volume real em campo
mostrar que precisa.

## Queixa 2 — o botão do Oversight parece um filtro, e não é

> "O botão do oversight não está claro pra mim como funciona exatamente. (...) Se é assim, o
> botão de oversight deve ser diferente e talvez posicionado em outro lugar para não confundir."
> — Marcelo, 28/09

A leitura dele está correta e é o que o código faz: os chips (Todas · Grupos · Projetos ·
Arquivadas · Urgentes · Pendentes) são **escolha única** e filtram; o Oversight é um **toggle
independente** que troca a FONTE da lista (minhas conversas → todas as da loja) e deixa o filtro
escolhido agir por cima. "Projetos + Oversight" = todas as conversas de projeto da loja.

O problema é só de forma: ele mora na mesma fileira, com a mesma aparência de chip, então parece
a sétima opção de uma escolha única — quando na verdade é um interruptor ortogonal.

### O conserto
4. O Oversight deixa de ser um chip igual aos outros e passa a se apresentar como **modo**:
   forma visual distinta (interruptor, não pílula), separado dos filtros por um espaço ou uma
   divisória, e com rótulo que diga o que ele faz — "Ver toda a loja" comunica mais que
   "Oversight".
5. Quando ligado, a lista deve dizer que está em outro modo — não só o botão aceso. Um cabeçalho
   discreto do tipo "Todas as conversas da loja" acima da lista basta, e mata a dúvida de "estou
   vendo o quê agora".
6. O comportamento NÃO muda: continua empilhando com o filtro, continua abrindo em leitura, o
   botão Entrar na conversa continua como está.
7. **Isto é item de aparência: fecha com aceite visual do Marcelo**, capturas em 1280 e 1600,
   claro e escuro — mesmo critério do LI-4. Não marque FECHADO sem a resposta dele.

## Prova
- item com janela fechada aparece com a tarja nos DOIS modos, com o mesmo texto;
- item com janela fechando (< 2h) mostra o mesmo aviso nos dois modos;
- `responsavel` vem preenchido no Oversight quando existe, e o cabeçalho para de cair no
  fallback do SAC quando há responsável de verdade;
- a mesma conversa, listada pelos dois caminhos, devolve os mesmos valores nos campos comuns —
  teste que compara os dois serializers e falha se divergirem de novo;
- o toggle continua empilhando com cada chip (Todas, Grupos, Projetos, Arquivadas, Urgentes,
  Pendentes), um caso por chip.

## Estado

**Queixa 1 (dado) — FECHADA em 28/09/2026.** `chat/core.py`: `listar_todas_conversas` passou a
reusar `_atendimento_meta` (segmento+janela, mesma função de `listar_inbox`) e
`_resolver_responsavel` (extraída de dentro de `serializar_conversa` pra não duplicar). Custo
medido ANTES de fechar (ver seção acima): +1 query/item garantida (`janela_da_conversa`), até
+2 a mais conforme o estado de cada conversa (responsável setado / segmento ainda não derivado)
— registrado, não corrigido (não é desta tarefa colocar teto onde nunca houve). Frontend:
`_ocTodasItemHTML` ganhou a tarja de janela via `_atdJanelaBadge` — a MESMA função que a lista
normal já usa, nenhuma cor/texto novo. `responsavel` chegando de verdade já resolve o fallback
"SAC" sozinho, sem tocar `_ocSetHeaderExtras` (o código de lá já lia `c.responsavel.nome`
corretamente — só faltava o dado chegar).

Prova central: `tests/test_oversight_modo.py::test_oversight_e_inbox_concordam_nos_campos_comuns`
(+ variante sem segmento explícito) — compara os dois serializers pra mesma conversa, é o que
impede o terceiro sintoma da mesma causa. Portão: `-k "chat or oversight or inbox or atendimento
or janela"` — 163 passed, 0 failed.

**Queixa 2 (forma) — implementada em 28/09/2026, aguardando aceite visual do Marcelo.**
O Oversight deixou de ser `.oc-chip` (a regra CSS e a classe no HTML foram removidas) e virou um
switch: reusa `.sw`/`.sw-slider`, o MESMO componente de Fiscal → Configuração Fiscal ("Discrimina
impostos") — nenhum CSS de switch novo. Fica separado dos chips por `margin-left:auto` + uma
divisória (`#atd-modo-divisor` / `#int-modo-divisor`), com o rótulo "Ver toda a loja" em vez de
"Oversight". Quando ligado, aparece um aviso discreto acima da lista ("Todas as conversas da
loja", `#atd-modo-aviso` / `#int-modo-aviso`). Um único `_ocModoSetar(prefixo, ligado,
podeOversight)` decide a aparência do switch/aviso nos dois canais — `atendRender()` e
`intRender()` chamam a MESMA função, não duas cópias.

Comportamento não tocado (item 6 do conserto): o toggle continua trocando só a FONTE
(`_atdOversight ? _ocTodasDoCanal('atd') : _atdInbox`) e o filtro por chip continua agindo por
cima (`base.filter(c=>_ocDaChip(c,_atdChip))`) — linhas intactas, confirmado por teste. O botão
"Entrar na conversa" (OVERSIGHT-ENTRAR) não foi mexido.

Verificado num navegador real (Playwright, servidor local, `pdm2026`/master,
`ver_todas_conversas=true`) em 1280 e 1600px, claro e escuro: em 1600px o switch fica
nitidamente separado dos chips; em 1280px a topbar rola horizontalmente para alcançar o switch —
comportamento de overflow já existente na topbar (não é regressão desta tarefa). Capturas
publicadas: ver link na resposta desta tarefa.

Prova: `tests/test_oversight_modo_forma.py` (7 testes, trava estrutura/texto — sem teste JS no
projeto). Portão: `tests/test_aceite_achado36.py` + `test_oversight_modo_forma.py` verdes (12
passed); faixas de linha de `test_aceite_achado36.py` recalibradas (+46 na maioria, +32 na
faixa de `abrirProjeto`, que fica antes de parte dos hunks desta queixa).

**Não marcar FECHADA** — item 7 do conserto exige aceite visual explícito do Marcelo.

## Regras deste lote
1. Sem DDL.
2. Não abrir achado novo — anotar e reportar.
3. Testes alvo verdes por commit; suíte completa ao fim, pelo procedimento do
   `PLANO_SEMANA_1.md`; o log só se apaga depois do número lido, reportado e escrito aqui.
4. `OVERSIGHT-MODO` na mensagem dos commits.
