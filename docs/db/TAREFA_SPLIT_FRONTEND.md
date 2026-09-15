# Tarefa — separar o JavaScript de `static/index.html`

Escrito pela Sessão B, 15/09/2026, para a Semana 2 (21–27/09). Refatoração mecânica: **o
comportamento tem que sair idêntico**. Nenhum código escrito aqui, nenhum `pytest` rodado — este é
o plano de execução para a Sessão A.

**Medição de partida:** `static/index.html` tem hoje **26.551 linhas**. Linhas 1–4231 são
HTML/CSS/markup de página (inalterado por este plano). Um **único bloco `<script>`**, linha 4232
até 26261 — **22.029 linhas de JavaScript, um arquivo só** — é o que sai. Linhas 26262–26551 são
markup de fechamento, também inalteradas. Escopo é só JS: CSS continua onde está (ADR-003 fala dos
três juntos, mas separar CSS é outra frente, não pedida aqui).

---

## 1. As fronteiras de arquivo

A base é a Seção 4 do `MAPA_MODULOS.md` (inventário por `page-*`/prefixo) cruzada com a Seção 1
(papel × código). Proposta: **15 arquivos em `static/js/`**, um `<script src>` por arquivo, na
ordem que a Seção 2 (abaixo) descreve.

| Arquivo | Conteúdo | Espelha o módulo? |
|---|---|---|
| `core.js` | Sessão (`_usuarioAtual`), `projetoAtivo` — **declaração e o único setter permitido**, `goPage`, `sbNavRender`, popups/toasts do design system (`avisoPopup`, `confirmarPopup`, `showToast`, `_popupOverlay`), bootstrap pós-login (inclui a visibilidade de `nav-07`/`nav-cfg`), `_alinharLojaAoProjeto` | **Não espelha módulo nenhum — é Núcleo/Plataforma transversal**, do jeito que o backend já trata Auth/Tenancy. Todo outro arquivo depende deste; ele não depende de nenhum. |
| `admin.js` | `page-07`, `admin*` (27 funções), `adminRender()` | Sim — Admin |
| `config.js` | `page-09`, só o **shell de abas** (`cfgTab()` e navegação) | **Parcial — ver Caso 5 abaixo.** As funções de cada aba migram para o arquivo do domínio que elas realmente escrevem; `config.js` fica fino. |
| `cadastro.js` | `page-10`, `cad*`/`cli*`, `cadEntCarregar` (Fornecedores/Terceiros/Funcionários), + `cfgFuncao*`/`cfgRemuneracaoSalvar` (vêm de Config, ver Caso 5) | Sim — Cadastro |
| `fiscal.js` | `page-11` | Sim — Fiscal |
| `financeiro.js` | `page-12` (exceto aba Folha), `page-estrategico`, + `cfgPrivacidade*` (vêm de Config) | Sim — Financeiro |
| `folha.js` | aba Folha de `page-12` (`folha*`), + `cfgComissaoRender`/`cfgAdiantamentoSalvar` (vêm de Config) | Sim — Folha é módulo próprio no manifesto (`mod_folha.py`/`mod_comissao.py`), mesmo sem tela própria hoje. |
| `comercial.js` | `page-00`, `page-02`, `page-03`, `page-15`, e os `pe*`/`_pe*` de `page-18` (Projeto Executivo — modulos.py já declara PE/medição como Comercial) | Sim — Comercial, o mais rico |
| `expedicao.js` | `page-13`, `exp*` — **`_expPoll` sai daqui reescrito para chamar `core.setProjetoAtivo(...)`, nunca escrever a variável direto** | Sim — Expedição, com o conserto do Caso 1 embutido na mudança de arquivo |
| `montagem.js` | fatia de `page-18` referente a Montagem | Sim — Montagem tem chave própria no manifesto |
| `assistencias.js` | fatia de `page-18`, `assist*` | Sim — Assistências |
| `operacional-shell.js` | o que resta de `page-18` depois de tirar PE/Montagem/Assistências: só a troca de aba (`_op*` de navegação) | **Não espelha módulo — é plumbing de UI compartilhado por três domínios que hoje moram na mesma tela física.** |
| `ciclo.js` | Agenda da Loja (`page-16`, `_ag*`), `_cicloTransferResponder`/`_cicloTransferConfirmar`, `toggleSalvarEtapa`, `reabrirEtapaCascata` | **Não espelha limpo — ver Caso "Ciclo" abaixo.** É o núcleo Ciclo, mas hoje não tem UMA área própria — fica onde a UI do fichário do projeto está incrustada. |
| `chat.js` | `page-chat`, `oc*` (72 funções — a maior área) | Sim — Chat (núcleo, transversal), grande o bastante pra justificar arquivo próprio mesmo não sendo módulo de domínio |
| `plataforma.js` | `page-orizon`, `page-rede` | Sim — Tenancy/Rede (núcleo), telas de super_admin/admin_rede |

### Onde o espelho não funciona, e por quê

- **Folha, Montagem, Assistências** têm chave própria no manifesto backend, mas **não têm tela
  própria** — vivem como aba/fatia dentro de Financeiro e de "Operacional" (`page-18`). O espelho
  funciona no CONTEÚDO (cada arquivo recebe só as funções do seu domínio) mas não na ARQUITETURA DE
  NAVEGAÇÃO (o usuário continua clicando numa aba dentro de outra tela) — isso é decisão de produto
  já registrada (`ARQUITETURA-MODULOS.md`), não algo que este split deveria mudar.
- **Config não é dono de dado nenhum** (achado da Seção 1 do mapa) — é uma tela que agrega cinco
  domínios. Um arquivo `config.js` que só contém o shell de abas, com cada função de gravação
  morando no arquivo do domínio dono, é o único jeito de o split não criar um arquivo que faz
  imports cruzados de todo mundo. Ver Caso 5.
- **Ciclo é núcleo sem área própria no frontend.** O backend tem `mod_ciclo.py` bem definido; o
  frontend NUNCA teve uma "tela do Ciclo" — o fichário de etapas vive incrustado dentro da tela do
  projeto (Comercial). Um arquivo `ciclo.js` isolado é a melhor aproximação, mas ele vai conter só
  as funções mais genéricas (transferência, reabertura); funções específicas de uma etapa
  continuam fisicamente no arquivo do domínio que renderiza aquela etapa (ex.: a ClickSign da
  Aprovação do PE fica em `comercial.js`, não em `ciclo.js`, porque é ali que a tela mora).
- **`page-08` (template "Em construção") e `page-01` (morto, LP do mapa) não geram arquivo
  próprio** — o primeiro é usado por referência (função genérica de template, cabe em `core.js`); o
  segundo não migra para lugar nenhum — ver Seção 6 (não conserte, mas também não precisa
  transportar código morto para um arquivo novo só para preservá-lo).

---

## 2. A ordem

**Primeiro: `admin.js`.** É a área menos acoplada do arquivo — zero funções que leem ou escrevem
`projetoAtivo`, não toca negociação nem cálculo de nenhum tipo, sua tela inteira já é gerada por
uma função própria (`adminRender()`), e o pior caso de erro na extração é a tela de administração
de conta ficar temporariamente quebrada — nunca um preço errado ou um contrato mal gerado. É o
lugar certo para provar o MECANISMO (script tags na ordem certa, `core.js` carregando primeiro,
convenção de nomes de arquivo) sem risco de negócio.

**Segundo: `expedicao.js`.** Pequena (11 funções) e ainda longe de dinheiro (Kanban de logística,
não cálculo financeiro) — mas com o benefício extra de **forçar o conserto do Caso 1** (`_expPoll`
escrevendo `projetoAtivo` direto) logo cedo, enquanto o time ainda está com atenção total no
mecanismo. Adiar essa área para depois arrisca carregar a mesma violação para dentro de um arquivo
maior e mais tarde, quando a atenção já tiver se diluído.

**Terceiro: `plataforma.js` (Orizon/Rede) e `fiscal.js`.** Ambas telas de uso raro/especializado
(super_admin, ou só Fiscal) — baixo tráfego real, baixo custo de um erro passar despercebido por
pouco tempo. Fiscal, além disso, já é o piloto de extração ESCOLHIDO pelo backend
(`ARQUITETURA-MODULOS.md`, Fase 2) por ser "o cluster mais isolado" — fazer o mesmo no frontend
segue o mesmo precedente e usa a mesma justificativa.

**Quarto: `assistencias.js` e `montagem.js`.** Times/telas menores, ainda não mexem em preço.

**Quinto: `cadastro.js` e `ciclo.js`.** Cadastro é referenciado por todo mundo mas não FAZ cálculo
— o risco de quebrar é "alguém não encontra o cliente", não "o valor saiu errado". Ciclo (a parte
genérica) precisa vir depois de Comercial/Financeiro já terem lugar certo pra receber as funções
específicas de etapa que hoje estão misturadas no meio do bloco de Negociação/PE — fazer Ciclo
cedo demais deixaria função órfã esperando um arquivo que ainda não existe.

**Sexto: `chat.js`.** Núcleo, mas é a MAIOR área por contagem de função (72) — o risco aqui não é
de negócio, é de VOLUME: mais chance de esquecer uma função no meio da extração. Vale ir depois de
o mecanismo já estar rodado várias vezes nas áreas menores.

**Sétimo: `config.js` + o remanejamento das funções `cfg*`.** Só depois que `cadastro.js`,
`folha.js` e `financeiro.js` já existirem — porque o Caso 5 (abaixo) manda cada função `cfg*` para
o arquivo do domínio dono, e esses arquivos precisam já estar lá para recebê-las.

**Por último, e só então: `comercial.js`, `folha.js`, `financeiro.js` (e `operacional-shell.js`,
que depende de Comercial/Montagem/Assistências já existirem).** São as áreas que tocam preço,
negociação, provisão e comissão — o dinheiro de verdade. Nesse ponto o mecanismo já foi provado
sete vezes; o risco que resta é só o tamanho e a criticidade do conteúdo, não mais o processo de
extração em si.

**Dependência com a Fronteira 6.2 (Tela Única de Provisões), que está sendo construída na MESMA
Semana 2:** decidir explicitamente a ordem relativa entre "extrair `financeiro.js`" e "construir a
Tela Única" antes de começar os dois. Recomendação: extrair `financeiro.js` PRIMEIRO (mecânico,
zero mudança de comportamento) e só então implementar a 6.2 diretamente dentro do arquivo novo —
fazer o contrário (6.2 primeiro, extração depois) arrisca a extração ter que reconciliar código
que mudou de forma no meio do caminho.

---

## 3. O problema real — acoplamento cruzado, caso a caso

A Seção 4 do mapa achou um punhado de casos concretos. Para cada um, a disposição:

### Caso 1 — `projetoAtivo` escrito por `_expPoll` (Expedição)
**O que fazer:** `core.js` ganha um único setter, `core.setProjetoAtivo(dados)` — a única forma de
escrever a variável depois do split. `_expPoll`, ao mover para `expedicao.js`, passa a chamar esse
setter em vez de atribuir direto. **Não precisa de decisão do Marcelo** — é a aplicação mecânica da
regra que o próprio `ARQUITETURA-MODULOS.md` já escreveu para Expedição ("nunca é fonte da
verdade"). Vira o primeiro teste de arquitetura do frontend (ver Seção 5).

### Caso 2 — `_usuarioAtual`/`projetoAtivo` como estado central lido por todo mundo
**O que fazer:** ficam declarados em `core.js`, lidos livremente por qualquer arquivo (isso é
esperado — sessão e projeto ativo são conceito transversal de verdade, não um vazamento). **Não
precisa de decisão** — é o comportamento correto, só formalizado num arquivo com nome.

### Caso 3 — três variáveis paralelas de "gerente desbloqueou X" (`_impostosLiberados`,
`_tfTaxaLiberada`, `_descBloqueioRemovido`)
**O que fazer:** as três ficam dentro de `comercial.js` — são intra-área (todas em Negociação),
não criam dependência entre arquivos. **Não bloqueiam o split.** Consolidar as três num estado só
é melhoria de código, não requisito de arquitetura — fica fora deste pacote (ver Seção 6: se
alguém notar isso durante o split, vira linha na Lista Paralela, não conserto no meio da mudança).

### Caso 4 — visibilidade de `nav-07`/`nav-cfg` decidida no bootstrap pós-login
**O que fazer:** a função de bootstrap fica em `core.js` — ela legitimamente precisa tocar
elementos de nav de MÚLTIPLAS áreas (é o "app shell" decidindo o que aparece, papel que cabe ao
núcleo). **Não é o mesmo problema do Caso 1** — ali uma função de DOMÍNIO escrevia estado de OUTRO
domínio; aqui é o NÚCLEO orquestrando visibilidade, que é seu papel. Não precisa de decisão.

### Caso 5 — `cfg*` (Config) grava em Cadastro, Admin/Tenancy, Comercial e Financeiro
**O que fazer, função por função:**
- `cfgFuncaoNova`/`cfgFuncaoSalvar`/`cfgFuncaoToggle`/`cfgFuncoesRender`/`cfgRemuneracaoSalvar` →
  `cadastro.js` (gravam em `/api/funcoes`, rota de Cadastro).
- `cfgAdiantamentoSalvar`/`cfgComissaoRender` → `folha.js` (Folha de Pagamento).
- `cfgAgendaRender`/`cfgAgendaSalvar`/`cfgCronogramaRender`/`cfgCronogramaSalvar` → `ciclo.js`
  (Cronograma e Agenda são backend do Ciclo, `mod_cronograma.py`/`mod_agenda.py`).
- `cfgDocumentosRender` → `comercial.js` (`/api/documentos`, `mod_documentos.py`).
- `cfgPrivacidadeAprovar`/`cfgPrivacidadeRender`/`cfgPrivacidadeRevogar` → `financeiro.js`
  (`/api/simulador/autorizacao`).
- `config.js` fica só com `cfgTab()` — o dispatcher de abas — chamando as funções que agora moram
  em outros arquivos (funcionam normalmente, porque sem módulos ES tudo está no mesmo escopo global
  depois de carregado).
**Não precisa de decisão do Marcelo** — é reclassificação por dono de dado, o mesmo critério que o
próprio manifesto backend já usa. **Mas precisa vir depois** dos arquivos de destino existirem (ver
Seção 2).

### Caso "Ciclo" — funções de etapa espalhadas sem área própria
Já coberto na Seção 1 ("onde o espelho não funciona"). **Não precisa de decisão** — é constatação,
não escolha: o que for genérico (transferência, reabertura, agenda) vai para `ciclo.js`; o que for
específico de uma etapa fica no arquivo da tela que a renderiza.

### Caso `_alinharLojaAoProjeto` — chamada por Comercial e por Chat
**Correção ao próprio levantamento:** um relato anterior descrevia isto como "duplicado" — **não
é.** Conferido agora: `_alinharLojaAoProjeto` é uma função ÚNICA (definida uma vez, perto do topo
do bloco de script, antes de qualquer código específico de `page-*` — já vive, na prática, na
região que vai virar `core.js`), chamada de dois lugares (`abrirProjeto`, em Comercial, e do envio
de mensagem, em Chat). Não há duas implementações — é uma guarda de tenancy já corretamente
compartilhada.
**O que fazer:** só mover essa função, como está, para `core.js` — nenhuma mudança de
comportamento, só de arquivo. **Não precisa de decisão do Marcelo.**

**Resumo do que precisa do Marcelo:** **nada, nesta seção.** Todos os sete casos têm disposição
mecânica clara a partir do que já está documentado (manifesto backend, ARQUITETURA-MODULOS.md, ou
constatação direta de qual API cada função chama). Isso é, em si, um dado bom: o acoplamento do
frontend é resolvível com regra, não com julgamento de produto.

---

## 4. Os testes que contam linha — o que eles queriam medir, e como medir depois

**Achado, único arquivo:** `tests/test_aceite_achado36.py` — três testes, dois deles são ratchet de
linha:
- `test_nenhum_showtoast_de_erro_sobra_no_modulo_financeiro` — usa `FAIXA_INICIO, FAIXA_FIM =
  14754, 16799` (faixa contígua) para extrair "o texto do módulo financeiro" e conferir que nenhum
  `showToast(msg, true)` sobrou nele (o achado original, ACHADO-36: erro deveria usar o popup do
  design system, não o overlay manuscrito).
- `test_nenhum_showtoast_de_erro_sobra_na_faixa_do_ciclo` — usa `FAIXAS_CICLO`, uma lista de **seis
  faixas descontínuas** (cada uma é uma função específica: `abrirProjeto`, transferência de etapa,
  ClickSign de PE, `peConciliacaoReprovar`, toggle/reabertura de etapa, ClickSign de Medição) —
  mesma checagem, escopo mais espalhado.
- `test_contagem_total_de_showtoast_de_erro_no_sistema` — conta o total no ARQUIVO INTEIRO (hoje
  143) — não usa faixa, é o único dos três que já sobrevive ao split sem mudança nenhuma.

**O que eles mediam de verdade:** não "estas linhas", e sim **"estas funções, agrupadas por
módulo, não usam mais o overlay manuscrito"**. A faixa de linha era só o jeito disponível de dizer
"o módulo financeiro" e "estas seis funções do ciclo" antes de existir separação física — **reajustar
o número (como já foi feito uma vez, em 14/09, quando a entidade `Lead` deslocou tudo em +99
linhas) é medir a INSERÇÃO de código, não a regressão que o teste deveria guardar.** É exatamente o
que o LP-30 (`LISTA_PARALELA.md`) já registrou.

**Como medir a mesma coisa depois do split:**
1. `test_nenhum_showtoast_de_erro_sobra_no_modulo_financeiro` passa a ler o **arquivo inteiro**
   `static/js/financeiro.js` (e `static/js/folha.js`, se a aba Folha entrar na varredura original —
   conferir se as 36 conversões do B2 tocaram funções de Folha antes de decidir) — sem faixa
   nenhuma, porque agora o arquivo INTEIRO é o módulo. É uma melhoria, não só uma correção: hoje,
   uma função financeira nova fora da faixa hardcoded escapa do teste; depois do split, é
   impossível escapar, porque não existe "fora do arquivo".
2. `test_nenhum_showtoast_de_erro_sobra_na_faixa_do_ciclo` troca linha por **nome de função**: uma
   função utilitária pequena (`_corpo_da_funcao(nome_funcao, texto_do_arquivo)`, achando o texto
   entre `function nome_funcao(` e o fechamento correspondente) substitui `FAIXAS_CICLO`. A lista
   de seis nomes continua a mesma; só a forma de localizar o texto muda de número para nome — e o
   teste precisa saber em QUAL arquivo procurar cada função (a maioria fica em `comercial.js`,
   conferir se alguma das seis foi para `ciclo.js` na extração real).
3. `test_contagem_total_de_showtoast_de_erro_no_sistema` passa a somar a contagem em **todos os
   arquivos de `static/js/*.js`** em vez de um `open()` só — muda de "abra este arquivo" para "some
   sobre esta pasta", conceitualmente mais simples do que hoje.
**Quem faz esse ajuste é a Sessão A, no mesmo PR que move o código** — não é trabalho novo separado,
é parte do próprio split (mover código sem atualizar o teste que aponta pra ele não é split
completo).

---

## 5. Como provar que nada mudou

Refatoração mecânica pede prova de que o comportamento é idêntico, não só "os testes passam". Em
ordem de força:

1. **Diff de conteúdo, não de comportamento — a prova mais barata e mais forte.** Antes de rodar
   qualquer teste: concatenar os arquivos novos, na ordem em que o HTML vai carregá-los via
   `<script src>`, e comparar o resultado contra o bloco `<script>` original (linha 4232–26261),
   ignorando só as linhas que o próprio split precisa adicionar (as chamadas a
   `core.setProjetoAtivo` no lugar da atribuição direta, os dois lugares que passam a chamar
   `_alinharLojaAoProjeto` de `core.js`). Qualquer diferença além dessas duas mudanças esperadas é
   erro de transcrição — bug do split, não do sistema. Isso prova "nada mudou" sem precisar de
   navegador nenhum.
2. **Contagem de função, antes e depois.** O mapa mediu **1.131 funções `function`/`async
   function`** no arquivo hoje — a mesma contagem, somada sobre todos os arquivos novos, tem que
   bater (menos as que viraram uma só, como `_alinharLojaAoProjeto` — contar essa dedução
   explicitamente, não deixar a diferença "sobrar" sem explicação).
3. **A suíte de E2E de navegador é a guarda PRINCIPAL — com as ressalvas já registradas, não
   ignoradas.** `LISTA_PARALELA.md` já documenta que essa suíte tem histórico de flakiness real e
   medido (LP-16, LP-21, LP-22: falhas não-determinísticas, banco compartilhado, deadlock de DDL,
   um caso de trava de 12 horas) — um E2E vermelho durante o split **não é automaticamente prova de
   regressão**. Antes de assumir que o split quebrou algo: (a) rodar de novo isolado (mesma lógica
   que já resolveu falsos positivos nas rodadas anteriores); (b) checar se a falha bate com um dos
   padrões já catalogados nas três LP de infraestrutura; só depois disso investigar como regressão
   real do split. E o inverso vale também: **um E2E verde não é suficiente sozinho** — dado o
   histórico de intermitência, rodar a suíte completa **mais de uma vez** por área extraída dá mais
   confiança do que uma passada só.
4. **Suíte de backend (`pytest`) como smoke test, não como prova central.** Uma extração de JS
   correta não deveria mudar nada no backend — rodar a suíte inteira uma vez por área extraída é
   só para pegar o caso (improvável, mas barato de checar) de algum teste Python que, por acidente,
   dependa de conteúdo do HTML (ex.: um teste que faz `grep` em `static/index.html`, como os do
   Caso 4).
**Ordem recomendada por área extraída:** 1 → 2 → suíte E2E específica daquela área → só then a
suíte completa. Não pular o passo 1: é o único dos quatro que dá certeza absoluta, os outros três
dão confiança.

---

## 6. O que NÃO fazer junto

**A regra:** durante o split, todo defeito encontrado vira uma linha nova em
`docs/db/LISTA_PARALELA.md` — nunca um conserto no mesmo commit/PR do split. Um split que também
conserta é um split que não se pode revisar como "comportamento idêntico" — a Seção 5 inteira deste
plano deixa de valer no momento em que uma linha muda por outro motivo além de mudar de arquivo.

**Coisas que este próprio levantamento já encontrou, que vão estar bem na frente de quem fizer o
split, e que NÃO devem ser consertadas ali:**
- as três variáveis paralelas de desbloqueio (Caso 3) — juntá-las numa só é melhoria real, mas é
  outro commit;
- a lista de motivos de retenção hardcoded em JS (`LP-27`, já na Lista Paralela) — vai aparecer de
  novo quando `comercial.js`/o arquivo que herdar a tela de retenção for extraído; não é para
  buscar `mod_retido.MOTIVOS_RETENCAO` via API nesse momento;
- `page-01`, o elemento morto — não precisa ser "limpo" nem "preservado com cuidado" no arquivo
  novo; se sobrar código morto claramente identificável, documentar onde foi parar (para não
  reaparecer como "achado novo" depois) e seguir;
- qualquer `showToast(..., true)` que os testes do ACHADO-36 ainda pegarem fora das faixas
  medidas — se aparecer um NOVO fora das áreas já cobertas, registrar na Lista Paralela, não
  corrigir ali;
- qualquer outra função que, ao ser lida de perto para decidir em qual arquivo ela entra, revelar
  um bug (é o tipo de coisa que aparece exatamente quando alguém lê código com atenção pela
  primeira vez em meses). O critério é simples: **se consertar exige mudar o QUE o código faz, é
  achado — vai para a lista. Se é só mudar ONDE o código mora, é split — continua.**

**Por que a regra existe, para quem for revisar:** um split que vira "enquanto eu tava ali, também
resolvi..." é como uma refatoração mecânica de 22 mil linhas vira uma semana de caça a defeitos sem
ninguém decidir isso — e é exatamente o padrão que fez a lista de achados original (antes da
reorganização por destino) crescer mais rápido do que fechava.
