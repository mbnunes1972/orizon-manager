# Decisões Pendentes — os 8 itens PRODUTO da Lista Paralela

**Escrito em 15/09/2026, a partir de `docs/db/LISTA_PARALELA.md` (destino PRODUTO).** Nenhum destes
oito depende de código — depende só de uma escolha do Marcelo. Cada bloco cabe numa leitura de
minuto; o objetivo é decidir os oito numa sentada só, sem precisar abrir mais nenhum documento.
Decidiu um? Vá em `LISTA_PARALELA.md`, ache o LP correspondente e anote a decisão ali — ele sai do
destino PRODUTO para BETA (se virar conserto desta semana), FRONTEIRA (se depender de uma das seis
fronteiras) ou "Fechados" (se a decisão for "não faz").

---

## LP-01 · Data combinada da medição

**O que é.** Hoje o sistema só guarda a data PREVISTA de medição (a que foi dada na venda, antes
de qualquer contato com o medidor). Quando o cliente e o medidor combinam a data de verdade,
não há onde guardar isso — e essa data deveria entrar no documento que o cliente assina.

**Por que está parado.** Falta escolher se a data combinada SUBSTITUI a prevista, CORRIGE ela, ou
fica do lado como um segundo número.

**Opções:**
- **Substituir.** Mais simples (um campo a menos), mas perde o histórico de quanto a data real
  desviou da prometida na venda.
- **Guardar as duas.** Mostra a diferença entre "prometido" e "combinado" — útil pra medir a
  operação — mas dá mais trabalho de tela e exige decidir o que mostrar pra quem.
- **A combinada recalcula o cronograma do projeto inteiro.** Mais poderoso, mas mais arriscado —
  precisa mapear tudo que hoje lê essa data antes de mudar o comportamento debaixo dela.

**Recomendação:** guardar as duas — é a única opção que não descarta informação, e o custo extra é
só de tela, não de risco.

---

## LP-02 · Conferir se quem assina é quem deveria assinar

**O que é.** Hoje o sistema confere se o CPF digitado na assinatura é um CPF VÁLIDO (o número bate
com a fórmula) — não confere se é o CPF da PESSOA CERTA (o cliente daquele projeto, ou o gerente
daquela loja).

**Por que está parado.** É uma escolha de rigor de processo, não um defeito — falta decidir se vale
travar mais.

**Opções:**
- **Manter como está.** Custo zero, mas alguém pode assinar em nome de outra pessoa sem o sistema
  notar.
- **Bloquear se o CPF não bater com o cadastro.** Mais seguro, mas precisa de um fluxo de exceção
  pra casos legítimos (procuração, familiar assinando por alguém) — senão trava gente que deveria
  poder assinar.

**Recomendação:** nenhuma — depende de saber se isso já causou problema na prática. Vale perguntar
ao time comercial antes de decidir.

---

## LP-09 · Cliente pedindo várias versões do projeto depois de aprovado

**O que é.** Quando o cliente pede mudanças no Projeto Executivo já aprovado — trocar um item,
tirar outro — hoje existe só uma tela de comparação simples. Não há um jeito de mostrar "várias
versões possíveis" e deixar o cliente escolher uma, do jeito que já existe na venda (vários
orçamentos, um vence).

**Por que está parado.** É grande, e o Marcelo já registrou insegurança sobre se o modelo atual
está errado ou só incompleto — não decidiu mudar.

**Opções:**
- **Manter a comparação simples.** Custo zero agora; risco é cliente reclamar de não conseguir
  comparar alternativas de verdade.
- **Trazer o modelo "várias versões" da venda pra cá.** Resolve o pedido, mas é caro — revisão
  pós-aprovação tem regras próprias (o que fazer com material já comprado da fábrica, por exemplo)
  que o modelo da venda não precisa considerar.

**Recomendação:** nenhuma — o próprio Marcelo pediu tempo para revisitar casos reais antes de
decidir. Não force esta decisão sem esses casos em mãos.

---

## LP-11 · Dois lançamentos financeiros automáticos que existem mas nunca ligam

**O que é.** No sistema há dois "gatilhos" prontos — um pra quando a montagem é executada, outro
pra pagamento à fábrica — que nunca disparam de verdade hoje, só em teste. Se alguém os ligasse do
jeito que estão, cada um faria só METADE da contabilização certa (move dinheiro sem reconhecer a
despesa) — o oposto do que a auditoria contábil pediu.

**Por que está parado.** Falta decidir: consertar e ligar os dois, ou remover — parece que já
existe outro mecanismo (o "Efetivar") fazendo a mesma coisa, certo, nos dois casos.

**Opções:**
- **Consertar e ligar.** Precisa de um campo novo ("quanto foi gasto de verdade") que hoje não
  existe no fim da etapa de Montagem — custo médio.
- **Remover os dois.** Custo baixo — é limpeza. Risco de manter: algum dia alguém liga um dos
  dois sem saber que está incompleto, e o erro contábil que a auditoria toda tentou evitar volta.

**Recomendação:** remover — o "Efetivar" genérico já cobre os dois casos com o lançamento certo.
Manter caminhos mortos ao lado de um caminho que já funciona é risco sem benefício.

---

## LP-12 · Aprovar e liberar financeiramente por FASE, não só o projeto inteiro

**O que é.** Quando um projeto é dividido em fases (parte entregue antes, parte depois), hoje a
aprovação financeira trata o projeto inteiro como um bloco — mesmo que só uma fase esteja pronta
pra avançar. **Já está decidido** que a contabilidade em si não se divide por fase (fica
consolidada por projeto) — só falta decidir a REGRA de liberação.

**Por que está parado.** Falta escolher com base em que número calcular "quanto dessa fase libera":
o valor do contrato daquela fase, o custo financeiro dela, ou o número de ambientes.

**Opções:**
- **Por valor de contrato da fase.** Fácil de explicar ao cliente; pode não bater com o esforço
  real de produção daquela fase.
- **Por custo financeiro (CFO) da fase.** Mais fiel ao risco financeiro real; mais difícil de
  explicar e auditar.
- **Por número de ambientes da fase.** Simples de calcular; distorce quando os ambientes têm
  valores muito diferentes entre si.

**Recomendação:** nenhuma — depende do critério que o time financeiro já usa informalmente hoje
para decidir isso na prática. Vale perguntar antes de formalizar.

---

## LP-14 · Avisar quando uma etapa termina e oferecer passar adiante

**O que é.** Hoje, quando uma etapa do processo termina, ninguém é avisado automaticamente — quem
está de olho percebe sozinho, ou não percebe. O pedido: toda etapa, ao terminar, deveria avisar e
já oferecer "passar a responsabilidade para o próximo".

**Por que está parado.** Antes de construir isso para TODAS as etapas, alguém precisa levantar
quais das 21 etapas já têm um jeito claro de saber que terminaram, e quais só terminam "por
adivinhação" (o status mudou, alguém clicou em algo) — sem esse levantamento, "toda etapa" é uma
promessa que não dá pra cumprir. Também depende de outro trabalho (papéis/responsáveis definidos
por etapa) que ainda não está pronto.

**Opções:**
- **Esperar o pré-requisito e fazer o levantamento primeiro.** Mais lento, mas é o único jeito de
  entregar "toda etapa" de verdade.
- **Fazer uma versão parcial já, só nas etapas com término claro hoje.** Mais rápido, mas não
  cumpre o pedido original — vira dívida disfarçada de entrega, e provavelmente precisa ser refeito
  quando o resto ficar pronto.

**Recomendação:** esperar o pré-requisito — a versão parcial provavelmente seria retrabalho.

---

## LP-18 · Acompanhar produção e entrega por FASE, não por pedido inteiro

**O que é.** Quando um projeto é dividido em fases, hoje o sistema só sabe dizer "a etapa terminou"
ou não — não "a Fase 1 terminou, a Fase 2 não". Isso afeta conferir o que chegou no depósito contra
a nota fiscal, e emitir a nota certa por fase. É uma frente grande, com desenho próprio já escrito
(`docs/db/TAREFA_FASES_E_RECEBIMENTO.md`).

**Por que está parado.** É grande demais para um ciclo de estabilização, e o desenho ainda precisa
virar plano de execução.

**Opções:**
- **Fazer a frente inteira como desenhada.** Cobre carregamento, recebimento e emissão de nota, os
  três por fase — custo alto, mas resolve o problema de vez.
- **Fazer só a parte mais dolorida primeiro** (por exemplo, só o recebimento por fase) e adiar o
  resto. Custo menor agora, mas fragmenta o trabalho — risco de inconsistência entre a parte feita
  e a que ainda trata tudo como bloco único.

**Recomendação:** nenhuma — depende de qual dor incomoda mais a operação hoje: não conseguir
separar fases na produção, ou não conseguir separar na hora de receber e faturar. Essa resposta só
vem de quem está no chão da operação agora.

---

## LP-24 · Aprovação do Projeto Executivo não pede testemunha na assinatura

**O que é.** Quando o Contrato é assinado, o sistema pede testemunhas. Quando a Aprovação do
Projeto Executivo (uma etapa depois) é assinada, não pede. Ninguém sabe hoje se isso foi decisão
consciente (não faz sentido pedir testemunha ali) ou esquecimento de quem programou na época.

**Por que está parado.** Não dá pra "consertar" sem saber qual das duas é — adicionar testemunha
por precaução resolve o sintoma errado se a ausência já era proposital.

**Opções:**
- **Perguntar a quem pediu a funcionalidade originalmente** se foi intencional. Custo mínimo,
  resposta direta.
- **Observar se isso já incomodou alguém em produção** (evidência indireta, mais lenta).
- **Adicionar testemunha de qualquer jeito, por precaução.** Custo técnico baixo, mas é apostar —
  se a ausência era proposital, isso cria uma trava nova sem necessidade.

**Recomendação:** a primeira — perguntar é a forma mais barata e definitiva de tirar a dúvida.
Adicionar sem confirmar (a terceira opção) é a única que pode criar um problema novo em vez de
resolver o antigo.
