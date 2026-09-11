# TAREFA — a família de instabilidades da suíte (LP-16, LP-21, LP-22)

Aberta em 10/09/2026, depois que a linha do complemento fechou (F2-43, `a1647b4`). O
`CADERNO_DE_BORDO.md` e a `LISTA_PARALELA.md` já nomeavam isto como "candidato natural a uma
rodada curta quando a linha do complemento fechar". Fechou.

**Esta rodada não toca regra de negócio, nem dinheiro, nem tela.** É infraestrutura de teste.
Por isso pode andar sozinha, sem decisão minha no meio.

## Por que agora

Em 09/09 uma bateria de E2E ficou **12 horas pendurada** — pytest vivo, Chromium vivo, `main.py`
vivo, CPU zerada, segurando o lock do `orizon_e2e` e bloqueando qualquer execução seguinte. Só
apareceu porque alguém foi olhar o `ps`. Isso não é um flake a mais: é a mesma doença chegando ao
pior desfecho possível, que é **travar em silêncio em vez de falhar**.

## As sete ocorrências

Seis com a MESMA assinatura — timeout sob carga paralela, nunca falha de lógica, sempre verde
isolado:

1. `test_aceite_achado12.py::test_projeto_com_aditivo_termina_com_2106_zerado` (LP-16)
2. `test_bateria_ciclo.py` — cenários "financeira" (LP-21)
3. `test_achado_c4_reaprovar_af_silenciosa.py`
4. `test_e2e_browser_conciliacao_final.py`
5. `test_e2e_browser_remover_ciclo.py` — ordenação de módulo
6. `test_e2e_browser_negociacao_layout.py` — travou no upload do XML (09/09)

E uma de espécie diferente, mesma causa de fundo (LP-22):

7. Servidor E2E morto no boot com `DeadlockDetected` em `_migrar_colunas_pg()`, no
   `ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS senha_provisoria`. Dois processos travados um
   no outro fazendo DDL no MESMO `orizon_e2e`.

**Cinco casos com a mesma assinatura deixam de ser cinco problemas e passam a ser um.** Sete,
mais ainda. A regra já registrada para LP-16/LP-21 vale para o conjunto: **procurar a causa
comum, não perseguir cada um.**

## Medir antes de consertar

**Passo 1 — o timeout do cliente HTTP.** `tests/conftest.py:267` e `:301` usam
`urllib.request.urlopen(req, timeout=5)`, e `:360` usa `timeout=1` no boot. Cinco segundos é um
número dimensionado para máquina ociosa. Meça: instrumente o cliente para registrar a duração
real de cada chamada durante uma execução da suíte completa, e me diga a distribuição — qual é o
p50, o p95, e quantas chegam perto de 5s. **Se a cauda encostar no teto, a causa comum está
achada e é uma linha.** Se não encostar, o timeout não é a causa e a hipótese cai — diga isso em
vez de ajustar o número "por via das dúvidas".

**Passo 2 — a corrida de boot.** Cada módulo de E2E de navegador sobe o **próprio servidor**
(fixture `servidor_e2e` por arquivo, porta própria), e todo boot passa por `init_db()` →
`_migrar_colunas_pg()`, que roda DDL. Todos contra o mesmo `orizon_e2e`. Meça quantos boots
acontecem numa execução completa e se algum par se sobrepõe no tempo. O deadlock do item 7 é a
prova de que se sobrepõem pelo menos às vezes.

**Passo 3 — o travamento.** Não existe timeout global. Descubra o que o processo estava
esperando quando pendurou: se der para reproduzir, `py-spy dump` no pytest travado responde em
um comando. Se não reproduzir, não invente — o item 1 da entrega abaixo já cobre o pior caso.

## O que entregar

**(a) Timeout global no `pytest.ini`.** Hoje `pytest.ini` só tem `norecursedirs`. Acrescente um
`--timeout` (pytest-timeout) generoso — o suficiente para o E2E mais lento com folga, não
apertado. Isso **não resolve a causa; resolve a descoberta**: transforma um travamento de 12
horas numa falha legível com stack trace. É a entrega mais barata e a que mais protege a
bancada. Faça esta primeiro, antes de investigar o resto.

**(b) O que a medição do Passo 1 indicar.** Se o teto de 5s for a causa comum, o conserto é
único e vale para os seis. Prefira parametrizar (variável de ambiente com default folgado) a
fixar um número novo — máquina de CI e bancada não são a mesma coisa.

**(c) Serializar o boot dos servidores E2E.** Duas saídas possíveis; escolha com medição, não
por gosto: um servidor **compartilhado** entre os módulos de E2E (fixture de sessão, não de
módulo), ou um **lock** em volta do boot para que dois `init_db()` nunca se cruzem. A primeira é
mais rápida e mais limpa; a segunda é menos invasiva. Diga qual escolheu e por quê.

## Fronteiras — não negociáveis

- **Nenhum teste sai do `pytest -q`.** A `ESTEIRA.md` é explícita: *"um teste que só roda quando
  alguém lembra de invocá-lo é da mesma família do `logging.warning` que ninguém lê. Se um teste
  precisa ficar fora, o problema é o isolamento dele — resolva o isolamento, não a convocação."*
  Marcar como `skip`, mover para fora da coleta, ou pôr atrás de uma flag é **recusado**.
- **Nenhuma asserção muda.** Se algum teste precisar mudar o que afirma para ficar estável, pare
  e me conte — isso não é instabilidade, é outra coisa.
- **`_migrar_colunas_pg` está congelado (R1).** Não receba coluna nova ali. Se o conserto passar
  perto de `init_db()`, saiba que `tests/test_schema_boot_estavel.py` compara o schema de
  `alembic upgrade head` com o de `init_db()` — ele é quem denuncia divergência, e tem que
  continuar verde.
- **Todo teste que abre banco continua afirmando o nome do banco antes de qualquer coisa.** Um
  `DATABASE_URL` esquecido já fez o E2E escrever registro órfão no banco de dev (31/08).
- Não tocar em código de negócio, Produção, tag ou deploy.

## O aceite

1. `python3 -m pytest -q` **três vezes seguidas**, do zero, sem nenhuma das sete ocorrências.
   Uma execução verde não prova nada aqui — o que se está consertando é justamente o que às
   vezes passa.
2. Os E2E de navegador uma vez a mais, um por vez, verdes.
3. Um travamento **provocado de propósito** (um `sleep` maior que o timeout dentro de um teste
   descartável) tem que virar falha legível em vez de pendurar. Prove que (a) funciona.
4. Relato do que a medição achou — inclusive se derrubou alguma hipótese minha. Hipótese
   derrubada com medição vale mais que conserto sem causa.

Registro em `docs/db/LISTA_PARALELA.md`, LP-16, LP-21 e LP-22. Atualize os três ao fechar,
dizendo o que era a causa comum — ou que não havia uma, se for o caso.

---

# Rodada 2 — a medição derrubou o enunciado, inclusive o meu

Escrita em 10/09, depois da Rodada 1 (entrega (a) + Passos 1 e 2).

## O que a Rodada 1 estabeleceu

**Entrega (a), feita:** `timeout = 300` no `pytest.ini` (pytest-timeout, em `requirements.txt`),
provado com um `time.sleep(600)` descartável virando falha legível. O travamento de 12 horas não
volta a acontecer em silêncio. Isto sozinho já pagou a rodada.

**Passo 1 — hipótese do teto de 5s: MORTA.** 2767 chamadas reais medidas em duas execuções
completas: p50 = 0,005s, p95 ≈ 0,06s, **máximo 1,18s** contra um teto de 5s. Folga de quatro
vezes no pior caso observado. A hipótese era minha e estava errada; foi derrubada por medição, e
o número **não** foi ajustado "por via das dúvidas". É o desfecho certo.

**O achado que ninguém pediu, e que é o mais importante:** duas execuções de `pytest -q`
completas, do zero, **2750 passed / 4 xfailed / 0 failed**, ~590s cada — e **nenhuma das sete
ocorrências apareceu**.

## O enunciado estava errado, e agora dá para dizer melhor

Eu chamei a família de *"timeout sob carga paralela"*. A medição diz outra coisa: numa execução
**única** de `pytest -q` não há flake nenhum, e o cliente HTTP nem chega perto do teto. Sem
`pytest-xdist`, os ~30 boots de `servidor_e2e` rodam **em série** dentro de um processo — não há
corrida a serializar ali, e a entrega (c) como eu a escrevi mirava um alvo que não existe.

Releia de onde vieram os registros originais: *"E2E rodando em paralelo com a suíte pesada"*,
*"sob a carga da suíte inteira"*. Em todos, havia **duas invocações de pytest ao mesmo tempo**,
disparadas por sessões diferentes — e as duas compartilham `orizon_e2e` e `orizon_test`.

O enunciado honesto passa a ser:

> Uma execução de `pytest -q` é estável. **Duas execuções simultâneas contra o mesmo banco de
> teste não são suportadas — e nada impede que aconteçam.** O conftest dropa e recria schema por
> módulo; dois processos fazendo isso ao mesmo tempo produzem exatamente o deadlock de DDL do
> item 7, e provavelmente os travamentos.

Isso explica o conjunto melhor que "timeout": explica por que sempre passa isolado, por que
nunca é falha de lógica, e por que a assinatura varia (timeout num caso, deadlock noutro,
pendurado no terceiro) — são sintomas diferentes da mesma colisão.

## O que fazer agora, no lugar de (b) e (c)

**(b) morreu com a hipótese.** Não há número a ajustar.

**(c) muda de alvo: em vez de serializar boots dentro de um processo (já são seriais),
impedir ou tornar segura a execução CONCORRENTE.** Um guard, não uma refatoração:

- um **lock** sobre o banco de teste — advisory lock do Postgres (`pg_try_advisory_lock`) tomado
  uma vez por sessão de pytest, ou um lockfile; a segunda invocação **recusa com mensagem clara**
  ("já existe uma execução usando `orizon_e2e` — PID x, iniciada às y") em vez de interleavar DDL;
- ou, se recusar for hostil demais para o fluxo de duas sessões trabalhando junto, **esperar** com
  um limite e então recusar.

Recusar é aceitável e é a escolha que eu prefiro: quem roda a segunda suíte quer resultado
confiável, e hoje recebe silenciosamente um resultado que não é. Mas meça o incômodo antes —
se as duas sessões precisam mesmo rodar junto com frequência, a saída é **banco por invocação**
(sufixo com PID no nome), e aí o guard não é preciso. Diga qual escolheu e por quê.

## E o aceite muda junto

O aceite que escrevi — "três execuções limpas" — **não prova nada**, e é importante dizer isso
em vez de cumprir a formalidade: a Rodada 1 já mostrou que execuções únicas são limpas mesmo sem
conserto nenhum. Três seriam três repetições de um cenário que não exercita a falha.

O aceite certo é **reproduzir de propósito**:

1. Duas invocações de `pytest -q` simultâneas, hoje, contra o mesmo banco — mostrar que colidem
   (deadlock, travamento, ou falha esdrúxula). **Se não colidirem em algumas tentativas, pare e
   me conte**: aí o enunciado desta Rodada 2 também cai, e o problema é outro.
2. A mesma coisa com o guard: a segunda invocação recusa (ou espera) com mensagem legível, e a
   primeira termina limpa.
3. `pytest -q` sozinho segue verde — o guard não pode atrapalhar o caminho normal.

## Passo 2, o que ficou sem resposta

A instrumentação de boot não capturou nada nas execuções completas, funcionando em lotes de 6 e
13 arquivos. Não foi perseguido além do óbvio, e **isso está certo** — com o reenquadramento
acima, contar boots dentro de um processo deixou de importar. Fica registrado como curiosidade
não resolvida, não como dívida.

