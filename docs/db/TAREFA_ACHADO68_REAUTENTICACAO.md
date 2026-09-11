# TAREFA — ACHADO-68: a senha pedida a cada passo, e a sessão emprestada

Achado do Marcelo em 10/09/2026, percorrendo Homologação (`v2026.09.09-beta1`).

> "Nos mecanismos de aprovação é solicitada a senha, porém a cada passo ele pede novamente.
> Depois de iniciada uma sessão de aprovação, ou no caso do login inicial ser de um usuário com
> permissão, o sistema não deve exigir nova senha. (…) O normal será o acesso ser feito pelo
> usuário com permissão, e nesse caso não deveria ter que entrar com senha, dado que o usuário
> tem a permissão."

## O que já está medido — não re-medir

**O atalho existe, e `aprovar_financeiro` foi excluída dele de propósito.**
`static/index.html:24267`, `pedirCredenciaisGerente`:

```js
const cap = (opts.capacidade === undefined) ? 'autorizar' : opts.capacidade;
if (cap && cap !== 'aprovar_financeiro' && _usuarioAtual && _usuarioAtual['pode_' + cap]) {
  return Promise.resolve({ auto: true });
}
```

O comentário logo acima diz de onde veio: *"Achado do usuário (2026-08-25): a folga NÃO vale
pra eventos financeiros — 'deve ocorrer em todos os casos que não envolvam eventos
financeiros'. `aprovar_financeiro` sempre pede a senha de novo, mesmo pra quem já tem a
capacidade — reautenticação como passo extra de confiança antes de mexer no razão contábil,
deliberadamente sem atalho."*

**Ou seja: não é defeito, é uma decisão anterior do próprio Marcelo — que agora ele revisa.**
Isso muda o enunciado: não se está consertando um esquecimento, está-se **substituindo uma
regra por outra**, e o registro tem que dizer isso.

**O backend já aceita requisição sem credenciais.** `main.py:416`,
`_usuario_autoriza_desconto(db, login, senha, desconto_pct, sessao=None)` — quando `login` e
`senha` vêm vazios, ele resolve pela sessão (*"mesmo padrão sessão-primeiro de
`_usuario_com_capacidade`"*). A exclusão é só do lado da tela.

**São 29 chamadas de `pedirCredenciaisGerente` em `static/index.html`** — não 32; esse número
veio de um `grep -c` que também contava 2 comentários (~11298, ~15482) e a própria definição da
função (~24267). Regra dos irmãos (ACHADO-26): enumere as 29 e diga quais são `aprovar_financeiro`
antes de mexer em qualquer uma. Enumeração feita (Claude Code, 10/09): 19 são `aprovar_financeiro`;
9 usam outra capacidade e já têm atalho hoje (inalterado); 1 — `cancelarContrato`, achado
incidental fora do enunciado original — usava `capacidade: null`, que por ser falsy também nunca
tinha atalho, só que por acidente de tipo, não por declaração de intenção (ver DECIDIDO abaixo).

**Existe rastro de quem autorizou** — os 15 pontos de `_aprovador_financeiro` gravam em
`LogAcaoGerencial.autorizador_id` (correção 11/09: o doc original citava `LogAutorizacao` — erro
meu; aquele modelo é da família do LIMITE DE DESCONTO, `desconto_solicit`/`desconto_limite`,
usado por `_usuario_autoriza_desconto`, não por `_aprovador_financeiro`) — e existe `Sessao` com
token e `expira_em`. Nada disso pode se perder.

## DECIDIDO (Marcelo, 10/09) — três categorias, não duas

Reenquadramento depois da enumeração: não é "aprovar_financeiro vs. o resto", são **três**
categorias de `pedirCredenciaisGerente`, cada uma com sua própria regra — e nenhuma vira as
outras por acidente.

1. **`aprovar_financeiro` (as 19).** Janela de reaprovação, 15 min — regras 1 e 2 abaixo.
2. **Demais capacidades (as 9: `autorizar`, `registrar_medicao`, `aprovar_medicao_reprovada`,
   `executar_pe`, `revisar_pe`).** Atalho de hoje, **inalterado** — quem já tem a capacidade
   nunca digita senha, sem janela nenhuma envolvida (não precisa: já é imediato).
3. **Atos irreversíveis.** SEMPRE pedem senha — sem janela e sem atalho, mesmo pra quem tem a
   capacidade. `cancelarContrato` é o primeiro membro (achado incidental na enumeração, não
   estava no enunciado original).

   Duas exigências sobre esta categoria:
   - **Declarada, não acidental.** Hoje `cancelarContrato` "sempre pede" só porque
     `capacidade: null` é falsy no `if (cap && ...)` — efeito colateral de tipo, não intenção
     escrita. Trocar por um marcador explícito, `capacidade: 'sempre_pedir'`, e o dispatcher de
     `pedirCredenciaisGerente` tem que reconhecer esse valor por nome (não por ser falsy) —
     assim uma refatoração futura do `if` não absorve este caso por acaso.
   - **Justificativa no código, não só aqui.** Comentário no ponto de checagem: ato terminal e
     irreversível não tem problema de repetição a resolver (é raro, por definição), e uma janela
     aberta por outra intenção (ex.: uma sessão de aprovação financeira em andamento) não pode
     virar permissão de passagem para cancelar contrato.

**A janela é POR CAPACIDADE, não por sessão inteira.** Abrir a janela de `aprovar_financeiro`
não libera nada além de `aprovar_financeiro` — nem as 9 da categoria 2 (que não precisam, já
têm atalho próprio) nem a categoria 3 (que nunca tem atalho, de propósito). Se no futuro outra
capacidade ganhar janela própria, é uma janela SEPARADA, com sua própria expiração.

### 1. Janela de reaprovação, no lugar de "toda vez"

A senha é pedida **uma vez** e abre uma **janela** (proposta: 15 minutos) durante a qual os
passos seguintes de `aprovar_financeiro` **não pedem de novo**. Modelo do `sudo`.

Preserva o que a decisão de 25/08 queria — um ato deliberado antes de mexer no razão — e mata
o incômodo real, que é reautenticar a cada passo de uma mesma operação.

**Tensão a resolver com o Marcelo antes de codar, se o implementador achar que importa:** o
texto dele diz *"não deveria ter que entrar com senha, dado que o usuário tem a permissão"* —
zero senha. A opção escolhida (janela) pede **uma**. Foi escolhida sabendo das duas
alternativas, então vale como está; mas se ao implementar ficar evidente que a primeira senha
também incomoda, pergunte em vez de decidir sozinho.

**A janela é do SERVIDOR, não da tela.** Guardar isso só em JavaScript recria exatamente o
achado de 2026-08-10 registrado no docstring de `_usuario_autoriza_desconto`: *"a autorização
gerencial da tela era só decoração de UI, sem trava real no servidor"*. A janela tem que ser
um estado do lado do servidor, atrelado ao **token da sessão**, com expiração **absoluta**
(não deslizante), e revogada no logout.

**O rastro não afrouxa.** Cada operação feita dentro da janela continua gravando
`LogAcaoGerencial` com o autorizador (correção 11/09: não `LogAutorizacao` — ver nota acima) —
a janela dispensa a digitação, não o registro de quem autorizou o quê.

### 2. Sessão emprestada encerra ao concluir

Quando quem está logado **não** tem a capacidade e um gerente digita as credenciais dele:

- **antes**, avisar: *"Você está autorizando com as suas credenciais numa sessão de outro
  usuário. Ao concluir a operação, esta sessão será encerrada."*
- **ao concluir a operação**, encerrar a sessão de verdade: invalidar o token, levar para a
  tela de login com uma mensagem que explique por quê.

A janela do item 1 **não se aplica** neste caso — sessão emprestada não ganha janela, porque
ela termina junto com a operação.

Razão: hoje, a autorização de um gerente dentro da sessão de um operador não deixa nada além
do log; a sessão continua aberta, do mesmo jeito, com o operador de volta ao teclado. Encerrar
é o que impede que um ato pontual de autorização vire acesso continuado.

## Fronteiras

- **Não mudar o que exige autorização.** Limites de desconto, `desconto_max`, quem pode o quê
  — nada disso entra. O que muda é **quantas vezes se digita a senha**, não quem pode fazer o quê.
- **Não enfraquecer a trava do servidor.** `_usuario_autoriza_desconto` e irmãs continuam
  decidindo no backend. Se a janela existir só no frontend, o pacote está errado.
- **`LogAcaoGerencial` continua completo** — uma operação dentro da janela grava igual.
- Não tocar em Produção, tag ou deploy.

## Aceite

1. Enumeração das 29 chamadas, com as três categorias marcadas.
2. Usuário **com** a capacidade: digita a senha na primeira ação financeira e **não** digita nas
   seguintes dentro da janela. Passada a janela, pede de novo.
3. A janela **expira por tempo absoluto** e **morre no logout** — teste que prova os dois.
4. A janela **não vale** entre sessões nem entre usuários: token de outra sessão não a herda.
5. Usuário **sem** a capacidade: vê o aviso antes; ao concluir, a sessão é invalidada de fato
   (o token não serve mais para nenhuma requisição) e a tela leva ao login explicando.
6. `LogAcaoGerencial` grava o autorizador em todas as operações dos casos 2 e 5.
7. A janela é **por capacidade**: abrir para `aprovar_financeiro` não libera as 9 da categoria 2
   (que continuam com o atalho de hoje, sem depender de janela) nem `cancelarContrato`
   (categoria 3 — sempre pede, mesmo com a janela de `aprovar_financeiro` aberta na mesma sessão).
8. `capacidade: 'sempre_pedir'` é reconhecida por NOME no dispatcher, não por ser falsy —
   `cancelarContrato` migrado de `capacidade: null` para o marcador explícito.
9. Suíte verde. `tests/test_stepup_e2e.py` já existe — ele fala deste mecanismo; ou continua
   valendo, ou muda com justificativa escrita.

## Lacunas conhecidas (fora desta rodada, decisão de Marcelo 11/09)

**`/parametros` e `/descontos` (família `_usuario_autoriza_desconto`) ficam de fora.** Das 19
chamadas de `aprovar_financeiro`, duas — `salvarParametrosAuto` e `_peComplModalSalvarDescontos`
— na verdade não passam por `_aprovador_financeiro`: o backend delas usa
`_usuario_autoriza_desconto`, que autoriza por **limiar NUMÉRICO** (`limite_desconto >=
desconto_pct`), não por capacidade booleana. Uma janela copiada do modelo de `aprovar_financeiro`
concederia MAIS do que foi autorizado: alguém autoriza 12% agora e a janela liberaria, sem nova
senha, qualquer desconto até o teto da PESSOA (ex. 50%) pelos 15 minutos seguintes — o valor
autorizado e o valor coberto pela janela deixariam de ser a mesma coisa. Uma janela correta para
essa família teria que ficar PRESA ao valor efetivamente autorizado (ex.: "esta janela cobre até
12%, não mais"), o que é desenho novo — não reuso do mecanismo de `aprovar_financeiro`. **Isto é
lacuna conhecida, registrada com o motivo — não esquecimento.** Fica pra uma rodada própria, se
e quando o incômodo de repetição nessas duas telas for medido como real.

**Achado incidental, medido por leitura (não consertado nesta rodada):**
`salvarParametrosAuto` É um auto-save por edição, confirmado no código — `agendarParametros()`
(qualquer edição de campo no modal de parâmetros) chama `agendarSalvarParametros()`, que agenda
`salvarParametrosAuto` via `setTimeout(..., 500)` (`static/index.html:~11235-11253`). Se o
composto comissão/fidelidade estourar o limite NO MEIO da edição (ex.: enquanto o usuário ajusta
o percentual e passa, mesmo que momentaneamente, por um valor acima do teto), o modal de senha
dispara 500ms depois — por EDIÇÃO, não por um clique de "salvar" deliberado. O próprio código já
carrega uma correção parcial da mesma classe (ACHADO-53, comentário ~11241-11245: dois portões,
`_mpPopulando`/`_mpModoLeitura`, pra não salvar ao só abrir o modal ou em modo leitura) — mas
esses portões cobrem "não salvar quando não deveria", não "não pedir senha no meio de uma edição
ainda em andamento". **É primo do ACHADO-53, defeito PRÓPRIO da tela de parâmetros — nenhuma
janela resolve isso** (a janela reduziria a REPETIÇÃO de um pedido que, pela causa, não deveria
estar dependendo do timing da digitação pra disparar). Fica como achado registrado, sem
conserto nesta rodada.

## `_aprovador_financeiro` em `/cancelamento` — confirmado categoria 3

`cancelarContrato`/`/api/orcamentos/<id>/cancelamento` REUSA `_aprovador_financeiro` só para
validar a credencial (login/senha + `perfis.pode(nivel, "autorizar")`) — não é uma 4ª família,
é o mesmo validador emprestado por conveniência. Ele **não pode ganhar janela por tabela**: o
call site não passa `handler=self` (comentário explícito no código apontando pra isto), então
`_aprovador_financeiro` nunca recebe token ali — nunca abre, nunca consulta, nunca aproveita uma
janela de `aprovar_financeiro` já aberta na mesma sessão por outra operação. Continua "sempre
pede", como a categoria 3 exige, mesmo reusando a função das outras 14 chamadas.

Registrar como **ACHADO-68** em `docs/db/ACHADOS_CONTABEIS.md`, dizendo que substitui a decisão
de 25/08 (que fica registrada como revista, não como erro).
