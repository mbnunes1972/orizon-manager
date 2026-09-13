# TAREFA — Estabilidade da suíte, Rodada 3: a colisão entre módulos

Medido em 12/09/2026, na bancada, depois de uma execução que girou **doze horas** a 98,9% de CPU.

As Rodadas 1 e 2 derrubaram duas hipóteses (o teto de 5s do cliente HTTP; a serialização dos boots
de E2E) e entregaram o `--timeout` global. Esta rodada tem **três achados provados** e um alvo.

> **Nada aqui é regra de negócio, dinheiro ou tela.** É infraestrutura de teste. Pode andar sozinha.

---

## Achado 1 — o conjunto de falhas MUDA entre execuções

Duas execuções completas da suíte no mesmo dia, na mesma máquina, com o código idêntico:

| execução | resultado | arquivos que falharam |
|---|---|---|
| 1 (bancos antigos) | 20 failed, 3 errors, 2753 passed | achado28, achado35, achado18, + 8 E2E |
| 2 (bancos recriados do zero) | 14 failed, 2 errors, 2760 passed | achado02_03, achado12, achado24, achado16, + 5 E2E |

**Quase nenhuma sobreposição.** E `tests/test_aceite_achado28.py`, que falhou 4 vezes na primeira,
passa **6 de 6 rodando sozinho, duas vezes seguidas**.

Consequência que precisa ser dita: o **"2773 passed, 0 failed" de 11/09 não provou a suíte** — foi
uma combinação que deu certo. Hoje a suíte não é um portão confiável, e a `ESTEIRA.md` depende dela
para cortar tag.

## Achado 2 — o `--timeout` protege o teste e NÃO protege o teardown

A entrega (a) da Rodada 1 funcionou: o log mostra `+++ Timeout +++` e o `F` registrado. Mas o
processo então girou doze horas. `py-spy dump` no processo travado:

```
Thread (active+gil): "MainThread"
    _sync (playwright/_impl/_sync_base.py:113)
    stop (playwright/sync_api/_generated.py:17463)
    on_will_close_browser_context (pytest_playwright/pytest_playwright.py:695)
    _teardown_yield_fixture (_pytest/fixtures.py:1014)
```

O alarme interrompeu o teste no meio de uma conversa com o Chromium. O `context.stop()` do
**teardown** entrou no laço `_sync` esperando uma resposta que nunca veio — espera ativa, por isso
98,9% de CPU e não zero, como no travamento de 09/09.

O cronômetro do `pytest-timeout` já disparou; o teardown corre **sem proteção nenhuma**. Um teste
que estoura leva a suíte inteira junto.

## Achado 3 — recriar os bancos consertou parte, e só parte

`drop database` + `create database` em `orizon_test` e `orizon_e2e` levou `achado18` e `achado35` de
erro a verde. **Não** consertou o resto. A hipótese "é só sujeira residual" está parcialmente
derrubada: havia sujeira, e há outra coisa por baixo.

---

## O alvo: escopo de MÓDULO num banco ÚNICO

`tests/conftest.py`:

```
62:  def _reset_schema_pg(engine)          # derruba e recria o schema
86:  @pytest.fixture(scope="module") app_db()
145: @pytest.fixture(scope="module") seed(app_db)
343: @pytest.fixture(scope="module") servidor(app_db, seed, projetos_dir)
```

O schema é derrubado e recriado **a cada módulo**, dentro de **um único banco**. E cada módulo sobe
o **próprio servidor HTTP em subprocesso**, também por módulo.

Na virada de um módulo para o outro, o `_reset_schema_pg` do módulo seguinte roda DDL enquanto o
servidor do módulo anterior pode ainda estar vivo, com conexões abertas e transações em curso.

**Isso explica os quatro sintomas de uma vez:** o `DeadlockDetected` em DDL (09/09), as conexões
`idle in transaction` encontradas hoje, o `SSL connection has been closed unexpectedly` no boot do
E2E, e o conjunto de falhas que dança conforme o tempo de morte de cada subprocesso.

**Não é vazamento entre testes do mesmo arquivo — é colisão entre módulos no mesmo banco.**

> Isto é hipótese com evidência forte, não fato provado. O Passo 1 abaixo é o que a converte.

---

## Passo 1 — provar antes de consertar

Instrumente `_reset_schema_pg` para, **antes** de qualquer DDL, consultar `pg_stat_activity` e
registrar quantas outras conexões existem naquele banco, de quais PIDs, e em que `state`.

Rode a suíte completa uma vez com isso ligado.

**Se em alguma virada de módulo houver conexão de terceiro aberta, a hipótese está provada** e o
conserto é o Passo 2. **Se nunca houver, a hipótese cai** — diga isso, e o alvo passa a ser outro.
Hipótese derrubada com medição vale mais que conserto sem causa; já derrubamos quatro hoje.

## Passo 2 — as entregas, nesta ordem

**(a) Falha barulhenta no `_reset_schema_pg`.** Antes do DDL, se existir qualquer outra conexão
naquele banco, **erre com mensagem clara** dizendo quem está conectado — em vez de rodar DDL e
corromper em silêncio. É a mesma lição do `handler` obrigatório do ACHADO-68: transformar uma falha
silenciosa em falha ruidosa. **Faça esta primeiro**: mesmo que o resto demore, ela troca "20 testes
falham aleatoriamente" por "a suíte para e diz por quê".

**(b) Teardown do navegador com prazo próprio.** Envolva o fechamento do contexto/página do
Playwright num limite de tempo independente do `pytest-timeout`, de modo que o `_sync` não possa
girar para sempre depois de um teste estourado. Um teste que falha pode custar aquele teste — nunca
a suíte inteira, nunca uma noite.

**(c) Isolar o banco por módulo.** Duas saídas; escolha **com a medição do Passo 1**, não por gosto:
um banco por módulo (isolamento total, custo de criação), ou garantir o **encerramento síncrono** do
servidor do módulo anterior — esperar o processo morrer e confirmar zero conexões — antes que o
próximo `_reset_schema_pg` toque em DDL. A segunda é menos invasiva; diga qual escolheu e por quê.

**(d) Recriação dos bancos como passo documentado.** Depois de qualquer `kill -9` numa execução, os
bancos de teste ficam num estado que produz falhas parecidas com regressão — perdemos meia manhã
hoje quase acusando código nosso por isso. Registre o procedimento onde quem for rodar a suíte vá
ler (`ESTEIRA.md` ou `CADERNO_DE_BORDO.md`), com os nomes certos e o aviso de que `orizon` e
`orizon_baseline_teste` **não entram** na limpeza.

---

## Fronteiras — não negociáveis

- **Nenhum teste sai do `pytest -q`.** `skip`, mover para fora da coleta, ou pôr atrás de flag é
  **recusado**. A `ESTEIRA.md`: *"um teste que só roda quando alguém lembra de invocá-lo é da mesma
  família do `logging.warning` que ninguém lê."*
- **Nenhuma asserção muda.** Se algum teste precisar mudar o que afirma para ficar estável, pare e
  relate — isso não é instabilidade, é outra coisa.
- **`_migrar_colunas_pg` está congelado (R1).** `tests/test_schema_boot_estavel.py` compara o schema
  de `alembic upgrade head` com o de `init_db()` — tem que continuar verde.
- **Todo teste que abre banco continua afirmando o nome do banco antes de qualquer coisa.** Um
  `DATABASE_URL` esquecido já fez o E2E escrever registro órfão no banco de dev (31/08).
- Não tocar em código de negócio, Produção, tag ou deploy.

## Aceite

1. Relato do Passo 1 — com os números, inclusive se derrubar a hipótese.
2. `python3 -m pytest -q` **três vezes seguidas**, do zero, **com o mesmo resultado nas três**.
   Verde nas três é o alvo; mas *o mesmo conjunto* nas três já provaria determinismo, que é o que
   está faltando. Uma execução verde não prova nada aqui.
3. Travamento provocado de propósito no teardown (um teste descartável que estoura o timeout dentro
   de uma ação do Playwright) vira falha legível em vez de pendurar. Prova (b).
4. `_reset_schema_pg` com conexão de terceiro aberta erra com mensagem clara. Prova (a).
5. Os E2E de navegador uma vez a mais, um por vez, verdes.

## Registro

`docs/db/LISTA_PARALELA.md`: atualizar **LP-16**, **LP-21** e **LP-22** dizendo qual era a causa
comum — ou que não havia uma. O LP-22 deixa de ser "os E2E compartilham um banco e o boot faz DDL" e
passa a ser **"a suíte inteira compartilha um banco e o schema é recriado por módulo, sem barreira
entre o servidor de um módulo e o DDL do seguinte"**.

Abrir entrada para os sete flakes conhecidos, acrescentando o oitavo medido hoje:
`test_e2e_browser_f2_40_fatia2_modal_complemento` — falhou em `Page.fill("#ct-previsao-medicao")`
numa execução isolada e passou na seguinte, também isolada.

---

## (b) — fechado (12/09): a causa não era falta de prazo, era o MÉTODO do prazo

**Causa-raiz, medida, não suposta.** `_sync()` do Playwright Python (`_impl/_sync_base.py`) não usa
uma thread de fundo — usa `greenlet`, troca de pilha **cooperativa numa única thread do SO**
(`faulthandler.dump_traceback(all_threads=True)`, provocado de propósito, mostrou UMA thread só no
processo inteiro). O método `'signal'` do pytest-timeout (default aqui) levanta uma exceção via
`SIGALRM` num ponto **arbitrário** do bytecode em execução. Quando esse ponto cai dentro do laço
`while not task.done(): self._dispatcher_fiber.switch()`, a interrupção corrompe o laço de
despacho asyncio/greenlet: `task.done()` nunca mais fica `True`, e a única thread do processo entra
num laço ocupado (~99% CPU) **sem esperar nada externo**. Prova de que não é espera por recurso
externo: matar o processo do navegador, e depois a árvore inteira de descendentes (navegador +
driver Node.js), não mudou o stack travado em nada, nas duas vezes — descartando por medição a
hipótese inicial de "prazo próprio via watchdog que mata o navegador". Um watchdog externo não
conserta uma corrupção que é inteiramente interna ao laço de eventos do próprio Python.

**Por isso "prazo próprio" não é um relógio adicional — é trocar o MÉTODO.** `tests/conftest.py`
agora força `method='thread'` (via `_get_item_settings`, não por marcador — um teste com
`@pytest.mark.timeout(N)` próprio ganha dois marcadores "timeout" no item, e `get_closest_marker`
só lê um) para todo item que usa fixture `page`/`context`/`browser`. O método `'thread'` nunca
injeta exceção no código em execução — só observa de fora, numa thread de verdade, e chama
`os._exit()` se o prazo estourar — não tem como corromper o que nunca tenta interromper.

**Escopo revisto pelo Marcelo (12/09):** a frase original ("nunca a suíte inteira, nunca uma
noite") juntava dois pesos muito diferentes na mesma decisão. Perder a noite era inaceitável;
perder a execução custa segundos até rodar de novo — só a segunda metade era requisito real. Um
supervisor externo que reinicia o pytest pulando o teste travado foi considerado e **recusado**:
pularia teste da suíte sem ninguém decidir (a mesma coisa que a fronteira "nenhum teste sai do
`pytest -q`" já proíbe), e construir tolerância para um defeito ainda não diagnosticado é a ordem
errada. Ficam dois requisitos, não três: nome do teste legível no que for impresso antes de sair
(`tests/conftest.py` embrulha `timeout_timer` só pra imprimir `FAILED <nodeid>` antes do
`os._exit` do original), e o processo termina sozinho — nunca mais "fica pra alguém matar".

**Prova por travamento provocado (item 3 do aceite):** teste descartável (`page.wait_for_timeout
(600_000)` com `@pytest.mark.timeout(3)`), rodado 3 vezes seguidas: `FAILED <nodeid>` visível,
processo termina sozinho em ~5,3-5,4s (exit code 1) nas três — nunca mais os 12h/45min medidos
antes. Apagado depois de confirmado, mesmo papel do `time.sleep(600)` da Rodada 1.

**Pergunta que fica aberta, e importa mais que este item:** por que um teste passa de 300s? Um
teste de 5 minutos não é lento — é outra coisa, e é candidato a ser a MESMA causa que aparece como
flake desde o LP-16. Com o nome do teste agora sempre visível no relatório, a próxima ocorrência
dá pra isolar e medir isoladamente — se isso se resolver, a ideia do supervisor (recusada acima)
nunca precisa voltar à mesa.
