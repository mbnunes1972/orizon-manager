# TAREFA — ACHADO-68: as duas pontas soltas

O ACHADO-68 foi implementado e commitado (`bac1e0b` e seguintes), com a suíte em 272 verdes.
Este pacote **não pede código novo primeiro** — pede duas provas. Só há conserto se alguma falhar.

A razão de existir: o relatório de fechamento afirmou coisas que a suíte não demonstrou. Isso não
é má-fé, é o ponto cego normal de quem acabou de escrever o mecanismo. As duas pontas abaixo são
exatamente onde o ACHADO-68 se parece com o achado de 2026-08-10 registrado no docstring de
`_usuario_autoriza_desconto`: *"a autorização gerencial da tela era só decoração de UI, sem trava
real no servidor"*.

---

## Ponta 1 — a sessão emprestada morre no SERVIDOR, não só na tela

**O que foi afirmado:** ao concluir a operação numa sessão emprestada, o usuário é levado ao
login com uma mensagem.

**O que isso prova:** que o frontend navegou. Nada mais.

**O que falta provar:** que o **token** daquela sessão deixou de valer para qualquer requisição.

### A prova

Um teste de integração, não de navegador — navegador testa a tela, e a tela não é o que está em
dúvida:

1. Autentique um usuário **sem** `aprovar_financeiro` (um `operador`; em Homologação,
   `cantunes`). Guarde o token da sessão — chame de `T`.
2. Confirme que `T` funciona: uma requisição autenticada qualquer devolve 200.
3. Dispare a operação financeira que exige autorização, com as credenciais de um usuário **com**
   a capacidade (um `gerencial`, `rvieira`), dentro da sessão `T`. Deixe a operação **concluir**.
4. Repita **a mesma requisição do passo 2**, com o mesmo `T`.

**Aceite:** o passo 4 devolve **401** (ou o que o sistema use para sessão inválida). Devolver 200
reprova, e reprovar aqui significa que a invalidação existe só no frontend.

**Cubra também o caminho triste:** a operação que **falha** ou é **cancelada** no meio. A sessão
emprestada deve morrer do mesmo jeito? Essa é uma decisão, não uma dedução — meça o que o código
faz hoje, escreva qual é o comportamento atual, e **pergunte ao Marcelo** se for diferente de
"morre sempre". Não decida sozinho: uma sessão que sobrevive ao cancelamento é uma porta aberta;
uma que morre no meio de um erro pode deixar o operador preso fora do sistema.

### Enquanto estiver aqui

Confira que `LogAcaoGerencial` gravou o autorizador (`rvieira`) e não o dono da sessão
(`cantunes`). A janela dispensa a digitação, nunca o registro de quem autorizou o quê.

---

## Ponta 2 — os 15 pontos, e o 16º que ainda não existe

**O que foi afirmado:** todos os pontos que chamam `_aprovador_financeiro` passam `handler=self`.

**O que isso prova:** nada, até alguém listar os pontos.

### A prova

1. Enumere **todas** as chamadas de `_aprovador_financeiro` em `main.py` (e onde mais houver).
   Diga quantas são, e para cada uma: passa `handler`? Se não passa, o que acontece — a função
   cai num caminho silencioso ou levanta erro?
2. Se alguma não passa, esse é o defeito real e o conserto é ela.

> **Regra dos irmãos (ACHADO-26):** antes de proteger uma operação, enumere todo endpoint capaz de
> produzir a mesma mudança de estado. Aqui a regra se aplica à assinatura da função, não à rota:
> um parâmetro que *pode* faltar é um irmão esquecido esperando para acontecer.

### O conserto que vale mesmo com as 15 corretas

Tornar `handler` **obrigatório** — parâmetro posicional sem default. Hoje, esquecer `handler` num
ponto novo produz um mecanismo **cego em silêncio**: a função roda, não enxerga a sessão, e a
única consequência é que a janela não funciona e ninguém percebe. Obrigatório, o mesmo esquecimento
vira `TypeError` na primeira execução.

**Aceite:** `handler` obrigatório; a suíte verde depois da mudança; e um teste que prove que a
chamada sem `handler` falha em vez de degradar.

Isto **não é refatoração cosmética** — é transformar uma falha silenciosa em falha barulhenta, que
é a mesma lição do ACHADO-25 (campo obrigatório novo na tela do aditivo passou despercebido com
2466 testes verdes e nenhum aditivo pôde ser assinado em produção).

---

## Fronteiras

- **Não mudar quem pode o quê.** Limites de desconto, `desconto_max`, capacidades: nada entra.
- **Não mexer na duração da janela** (15 min) nem no comportamento de quem **tem** a capacidade —
  isso já foi decidido e entregue.
- **`_migrar_colunas_pg` está congelado (R1).** Se a Ponta 1 precisar de campo novo em `Sessao`,
  vai em migration, com `docs/db/schema.sql` e `docs/db/ERD.mmd` regerados no mesmo commit (R4).
- **Nenhum teste sai do `pytest -q`.** Se algum precisar de isolamento, resolva o isolamento.
- Não tocar em Produção, tag ou deploy.

## Aceite consolidado

1. Teste de integração da Ponta 1, com o 401 provado. Se hoje devolve 200, o conserto vem junto
   e o teste passa a provar o 401.
2. Comportamento da sessão emprestada em operação cancelada/com erro: **medido e escrito**.
   Mudança de comportamento só com o Marcelo decidindo.
3. `LogAcaoGerencial` com o autorizador correto nos dois casos.
4. Enumeração das chamadas de `_aprovador_financeiro`, com o número real (não um `grep -c`, que já
   nos enganou uma vez contando comentários e a própria definição da função).
5. `handler` obrigatório, com teste que prova a falha barulhenta.
6. `python3 -m pytest -q` verde — completo, não bateria focada. Ele não roda inteiro desde o
   ACHADO-68, e a ESTEIRA exige antes de cortar tag.

Ao fechar, atualizar a entrada **ACHADO-68** em `docs/db/ACHADOS_CONTABEIS.md` dizendo o que as
duas provas acharam — inclusive se acharam que estava tudo certo. Verificação que confirma vale
registro igual a verificação que reprova.

---

# ADENDO — o caminho triste, DECIDIDO (Marcelo, 11/09)

As duas pontas passaram na medição de 11/09 (relatório na entrada ACHADO-68 de
`docs/db/ACHADOS_CONTABEIS.md`): o 401 é real, `LogAcaoGerencial` grava
`autorizador_id`/`solicitante_id` corretos, as 15 chamadas foram enumeradas, e `handler` virou
obrigatório com `/cancelamento` declarando `handler=None` explícito.

Restou a pergunta que a medição levantou e não decidiu: **hoje a sessão emprestada sobrevive a uma
operação que falha depois do aprovador** — o código que mata a sessão nunca é alcançado.

## A decisão

**A sessão emprestada termina quando o ato de autorização termina, qualquer que seja o desfecho:**
conclusão, falha ou cancelamento. Uma regra só, sem ramificação por tipo de erro.

**Razão.** A sessão emprestada não é perigosa por estar aberta; é perigosa porque foi **elevada uma
vez** com a senha de outra pessoa, e o operador volta ao teclado. Se a elevação sobrevive à falha,
o caminho triste vira o caminho **preferido** por quem quiser abusar: provoca um erro de propósito,
o gerente sai, e a sessão elevada fica. Uma regra que trata o sucesso com mais rigor que a falha
está invertida.

## O conserto que vem junto — e sem o qual a decisão dói

**A validação acontece ANTES de pedir a senha do gerente, não depois.**

O caso que motivou a dúvida — campo obrigatório vazio — não deveria nunca chegar a queimar uma
autorização. Validando primeiro e autorizando por último, o "erro besta" deixa de existir: a senha
só é pedida quando a operação está pronta para ser executada. Sobra o erro genuíno (banco fora,
falha de integração), raro, e no qual encerrar a sessão é o comportamento certo mesmo.

Sobre "trancar o operador fora do sistema": ele não fica trancado — entra de novo com o login dele.
O que ele perde é o formulário preenchido, o que é mais um argumento para validar antes.

## A conferir antes de considerar fechado

**A sessão emprestada realmente não ganha a janela de 15 minutos?** O pacote de 10/09 diz que não
deveria — *"sessão emprestada não ganha janela, porque ela termina junto com a operação"*. Se na
implementação ela ganhar, isso é **defeito independente desta decisão e mais urgente que ela**:
seriam 15 minutos de elevação nas mãos de quem não tem a capacidade. Meça antes de mexer no resto.

## Aceite do adendo

1. Teste que prova a morte da sessão emprestada numa operação que **falha** depois do aprovador —
   o mesmo 401 da Ponta 1, por outro caminho.
2. Teste equivalente para **cancelamento**.
3. Ao menos uma operação financeira com autorização reordenada: validação completa **antes** do
   pedido de credenciais. Teste que prova que entrada inválida é recusada **sem** pedir senha.
4. Medição escrita de se a sessão emprestada ganha ou não a janela de 15 min.
5. `python3 -m pytest -q` completo, verde.
