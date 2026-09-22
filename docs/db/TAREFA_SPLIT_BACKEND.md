# Tarefa — extrair as rotas de `main.py` para os módulos donos

Escrito pela Sessão B, 21/09/2026, companheiro do `TAREFA_SPLIT_FRONTEND.md` (15/09/2026) — mesma
disciplina: **plano, não execução**. Nenhum código escrito aqui, nenhum `pytest` rodado. É o plano
para a Sessão A.

**Isto NÃO é o "empacotamento" que `CLAUDE.md` já descreve em andamento** (fiscal/, integracoes/,
auth/, mod_fin/ virando pacote; falta empacotar comercial). Aquilo transforma um `mod_X.py` da raiz
numa pasta `X/` — **lógica de domínio**, que já mora fora de `main.py`. Esta tarefa é outra: tirar
de dentro de `main.py` o **roteamento e a lógica inline** que ainda vivem lá — a parte que o
empacotamento de lógica nunca tocou. As duas frentes se cruzam (uma rota extraída de `main.py` pode
ir para um pacote já existente), mas são obras diferentes, com riscos diferentes.

---

## 1. Medição de partida

`main.py` tem hoje **20.960 linhas**, em quatro blocos:

| Trecho | Linhas | O que é |
|---|---|---|
| 1–1973 | 1.973 | Setup do módulo + **75 funções/classes de nível 0** definidas antes da classe (ex.: `_AprovadorFinanceiro`, linha 694) |
| 1974–~18499 | **~16.525** | `class Handler(BaseHTTPRequestHandler)` — **o monolito de verdade** |
| ~18500–20854 | ~2.355 | **101 funções de nível 0**, fora da classe, usadas pelos métodos dela (`_recalcular_orcamento`, `_complemento_diferencas`, `_registrar_assinatura_contrato`, etc.) |
| 20855–fim | — | `# == MAIN ==`, bootstrap do servidor |

Dentro da classe `Handler`, nove métodos; os quatro que importam:

| Método | Início | Tamanho aproximado |
|---|---|---|
| `do_GET` | 2022 | ~4.927 linhas |
| `do_POST` | 6949 | **~10.027 linhas — mais da metade da classe inteira** |
| `do_PUT` | 16976 | ~689 linhas |
| `do_PATCH` | 17665 | ~835 linhas |

**Como o roteamento funciona hoje:** não existe tabela de rotas, nem decorator, nem `_match_rota`
central. Cada método é uma sequência de `if path == "/api/...":` (**121** ocorrências literais) e
`re.match(r'^/api/.../([^/]+)/...$', path)` (**244** ocorrências) — cada um seu próprio bloco,
verificado um atrás do outro, do topo do método até achar o que bate. **≈365 pontos de checagem de
rota** no total (proxy, não contagem exata — alguns `re.match` são re-checagens dentro do mesmo
bloco de erro). A lógica de cada rota é majoritariamente **inline** dentro do próprio `if`/bloco do
match — não uma chamada a uma função nomeada que se possa "só mover".

**Não existe comentário-âncora por módulo.** `docs/ARQUITETURA-MODULOS.md` (Convenção 5) previa
"uma seção de rotas por módulo no `main.py`, comentário-âncora" — verificado: isso nunca foi
seguido na prática. Os únicos marcadores de seção genéricos são `# == HANDLERS HTTP ==` (310) e
`# == MAIN ==` (20855). Ancorar por comentário de seção não é opção; **é por nome de rota/função
que este plano ancora**, como pedido.

### O único precedente real de extração de rota

**`auth/auth_routes.py` já fez exatamente este trabalho, uma vez, para Auth.** O padrão:

```python
# no topo de main.py:
from auth.auth_routes import handle_auth_get, handle_auth_post, get_usuario_sessao

# na PRIMEIRA linha de do_GET, antes de qualquer "if path == ...":
if handle_auth_get(self, path): return

# na PRIMEIRA linha de do_POST:
if handle_auth_post(self, path, body): return
```

`handle_auth_get(handler, path) -> bool` mora em `auth/auth_routes.py`, recebe o handler (`self`) e
o `path`, e devolve `True` se tratou a rota. Sem retorno especial de erro — `False` só significa
"não era minha rota, continue procurando". **Este é o único mecanismo já provado em produção para
extrair rota de `main.py` sem tabela de despacho nova.** O resto deste plano usa o mesmo padrão,
generalizado por domínio: `handle_<dominio>_get/post/put/patch(handler, path[, body]) -> bool`,
chamado no topo do método correspondente, na MESMA ordem relativa em que os blocos apareciam antes
(ver Seção 3, "ordem de checagem").

Nenhum outro domínio tem este tratamento hoje. `fiscal/`, `integracoes/`, `chat/` (via os shims
`mod_chat`/`mod_chat_externo`) já são pacotes — mas **só de lógica**: as rotas `/api/comunicacao/*`
continuam sendo `if path == "/api/comunicacao/inbox":` inline dentro de `do_GET`, chamando
`mod_chat`/`mod_chat_externo` só para a lógica de negócio, nunca para o roteamento em si.

---

## 2. As fronteiras — o que sai, para onde, e se a casa já existe

Base: Seção 1 do `MAPA_MODULOS.md` (papel × código) e a medição de prefixos de rota desta análise.

**Achado que organiza tudo o resto desta seção:** os domínios do backend se dividem em dois grupos,
por uma razão que o frontend não tinha — **prefixo de URL**.

### Grupo A — prefixo próprio, limpo, no topo (`/api/<dominio>/...`)

Estes podem replicar o padrão `handle_auth_get` quase mecanicamente: um `if path.startswith(...)`
(ou os `if path == .../re.match` de sempre) dentro de uma função nova, chamada uma vez no topo do
método.

| Domínio | Prefixo(s) | Casa já existe? | Onde a rota deveria morar |
|---|---|---|---|
| **Admin** | `/api/admin/*` (98 ocorrências) | **Não** — `modulos.py` nem tem chave `"admin"` (MAPA_MODULOS, Seção 1). É o único domínio rico sem NENHUM arquivo dono hoje. | **Arquivo novo**: `mod_admin.py` na raiz (convenção atual — pacote só quando crescer, ver `CLAUDE.md`) |
| **Cadastro** | `/api/clientes`, `/api/parceiros`, `/api/funcionarios`, `/api/fornecedores`, `/api/terceiros`, `/api/funcoes` — todos literais, nunca aninhados em `/api/projetos/` | **Sim** — `mod_cadastro.py` já existe e já é dono das tabelas | `mod_cadastro.py` ganha `handle_cadastro_get/post/put/patch` |
| **Financeiro (parte global)** | `/api/financeiro/*` (51 ocorrências — o maior grupo de prefixo limpo), `/api/provisoes`, `/api/simulador` (8), `/api/recebiveis` (9), `/api/estrategico` | Parcial — 9 arquivos (`mod_provisoes.py`, `mod_contabil.py`, `mod_recebiveis.py`, `mod_estrategico.py`, `mod_simulador*.py`...), nenhum claramente "dono do roteamento". | **Arquivo novo**: `mod_financeiro_routes.py` — só despacho, delegando a cada `mod_*` já existente (não duplicar lógica que já foi empacotada) |
| **Folha** | `/api/folha` (6), `/api/comissao` | Sim — `mod_folha.py`/`mod_comissao.py` | `mod_folha.py` ganha `handle_folha_get/post` |
| **Expedição** | `/api/expedicao` (5), sempre literal/regex simples (`/api/expedicao/cards/(\d+)`) | Sim — `mod_expedicao.py` | `mod_expedicao.py` ganha `handle_expedicao_get/post` |
| **Assistências** | `/api/assistencias` (5) | Sim — `mod_assistencias.py` | `mod_assistencias.py` ganha `handle_assistencias_get/post` |
| **Chat/Comunicação** | `/api/comunicacao/*` — prefixo limpo, confirmado (inbox, fila, janela, conversas, assuntos, exportar) | Sim — pacote `chat/` já existe (`chat/core.py`, `chat/externo.py`, `chat/triagem.py`) | `chat/chat_routes.py`, seguindo o padrão do próprio `auth/auth_routes.py` (mesmo pacote, arquivo `_routes` irmão) |

### Grupo B — sem prefixo próprio: aninhado sob `/api/projetos/<nome>/...`

**Este é o achado central desta análise, e é grave o bastante para não decidir sozinha (ver Seção
4).** Comercial, Ciclo (núcleo), PE, Aditivo, Medição, Equipe e a emissão de NF-e do Fiscal **não
têm prefixo de URL próprio** — todos vivem sob o mesmo guarda-chuva `/api/projetos/<nome>/...`.
Medido: **157 ocorrências** de `/api/projetos` em `main.py`, contra **zero** de `/api/ciclo`,
`/api/pe/`, `/api/aditivo`, `/api/medicao`, `/api/equipe`, `/api/fiscal` como prefixo próprio.
Exemplos reais, lado a lado:

```
/api/projetos/<nome>/equipe                    → Comercial (mod_equipe.py)
/api/projetos/<nome>/ciclo/15/nfe              → Fiscal (emissão de NF-e)
/api/projetos/<nome>/ciclo/15/emitir-nfe       → Fiscal
/api/projetos/<nome>/pe/comparacao             → Comercial/Produção (PE)
/api/projetos/<nome>/conferencia               → Financeiro (AF)
```

Uma única função `handle_comercial_get(handler, path)` que decidisse "é meu?" checando só
`path.startswith("/api/projetos/")` capturaria TODAS as rotas acima, inclusive as que são de Fiscal
e Financeiro — errado. Extrair estes domínios exige casar pelo **sufixo** (o que vem depois do
`<nome>`), não pelo prefixo — o mesmo `re.match` que já existe hoje, só que hospedado numa função
com nome, não perdido no meio de 10 mil linhas.

Isto **já está registrado** — não é achado novo desta tarefa, é a Causa E do `MAPA_MODULOS.md`
(Seção 5): *"o manifesto declara `/api/projetos/` inteiro como prefixo de Fiscal... rotas de
Comercial e do Ciclo caem, por eliminação, no prefixo de Fiscal"*. Esta análise confirma que o
mesmo fato que torna `modulo_do_path()` errado para o guard de topologia **também torna a extração
física mais cara** para este grupo — mesma causa, duas consequências. Ver Seção 4 para o que isso
muda na ordem.

| Domínio | Onde mora a lógica hoje | Casa para as rotas |
|---|---|---|
| Comercial (Negociação, Contrato, PE, Aditivo, Medição, Equipe) | 18 arquivos (`mod_negociacao.py`, `mod_contrato.py`, `mod_equipe.py`, `mod_medicao.py`, `mod_assinatura.py`...) | Precisa de UM arquivo de despacho novo (`mod_comercial_routes.py`?) que faça o `re.match` por sufixo e delegue — **decisão de desenho, não mecânica** (ver Seção 4) |
| Ciclo (núcleo) | `mod_ciclo.py` | Mesma ressalva — Ciclo é núcleo, mas suas rotas (`/api/projetos/<nome>/ciclo/*`) estão misturadas com as de domínio no mesmo prefixo |
| Fiscal (emissão por projeto) | pacote `fiscal/` | As rotas de CONFIG (`/api/admin/*/perfil-fiscal*`) já são Grupo A (limpo, sob Admin); só a EMISSÃO por projeto é Grupo B |

### As 101 funções de nível 0 (pós-classe) — vão junto com a rota que as usa

Cada uma dessas funções (`_recalcular_orcamento`, `_complemento_diferencas`,
`_registrar_assinatura_contrato`, `_aditivo_dados_calculo`, `_cliente_dict`, etc.) é candidata a
migrar para o MESMO arquivo que a rota que a chama — não ficam para trás em `main.py`. Algumas são
usadas por mais de um domínio (ex.: `_contrato_assinado`, chamada tanto por Comercial quanto pelos
gates do Ciclo) — para essas, aplicar o mesmo critério do Caso 5 do split de frontend: mora onde
está o dado que ela lê primeiro, e os outros chamadores importam de lá.

---

## 3. A ordem

**A mesma ordem já decidida para o frontend, pelos mesmos motivos — e por um motivo a mais que é
só do backend.**

**Primeiro: Admin.** Prefixo limpo (`/api/admin/*`, zero aninhamento em `/api/projetos/`), zero
toque em dinheiro, zero chave no manifesto hoje (nada a quebrar em `modulo_do_path()`). É o único
domínio do Grupo A que, além de barato, ainda NÃO TEM ARQUIVO — prova o mecanismo (`handle_admin_get/
post/put/patch`, arquivo novo, import no topo de `main.py`) no lugar de menor risco, exatamente como
`admin.js` foi o primeiro do frontend.

**Segundo, ainda dentro do Grupo A: Expedição e Assistências.** Pequenas, prefixo limpo, longe de
dinheiro — mesmo raciocínio do `expedicao.js` no frontend (ainda que aqui não haja um `_expPoll`
para consertar; o achado do Caso 1 do frontend foi um estado JS global, sem equivalente direto no
backend).

**Terceiro: Cadastro, Folha, Chat/Comunicação.** Prefixo limpo, casa já existe nos três, sem
decisão de desenho pendente — mecânico.

**Quarto — aqui a ordem do backend diverge da do frontend, e por uma razão nova:** antes de tocar
QUALQUER domínio do Grupo B (Comercial, Ciclo, Fiscal por projeto), a Causa E (Seção 5 do
`MAPA_MODULOS.md`) precisa de uma decisão — **como despachar por sufixo**, não por prefixo. Ver
Seção 4. Isto não é um domínio da lista, é um pré-requisito de desenho que bloqueia o Grupo
inteiro.

**Por último, e só então: Financeiro (a parte global do Grupo A) e o Grupo B inteiro (Comercial,
Ciclo, Fiscal por projeto).** São as rotas que tocam preço, negociação, provisão, comissão e
emissão fiscal — o dinheiro de verdade, e a parte estruturalmente mais difícil (sufixo, não
prefixo). Mesmo raciocínio do frontend: nesse ponto o mecanismo já foi provado várias vezes em área
barata: o risco que resta é do conteúdo, não do processo.

**A mesma dependência com a Fronteira 6.2, no mesmo sentido.** `TAREFA_SPLIT_FRONTEND.md` já
decidiu: extrair `financeiro.js` ANTES de construir a Tela Única de Provisões (6.2). Vale o mesmo
aqui, pela mesma razão — mexer no roteamento financeiro DEPOIS que 6.2 já tiver mudado o
comportamento das rotas de provisão obrigaria a extração a reconciliar código que mudou de forma no
meio do caminho. **Ordem: extrair as rotas de Financeiro primeiro (mecânico) → só então 6.2 usa o
arquivo novo como base.**

---

## 4. O que quebra se sair na ordem errada — as armadilhas medidas, não hipotéticas

Duas já mataram em produção; a terceira é o achado novo desta análise.

### Armadilha 1 — `__file__` dentro de pacote aponta para o pacote, não para a raiz

**Já aconteceu, documentado em `CLAUDE.md` e travado por `tests/test_caminhos_de_pacote.py`.**
Quando `auth_routes.py` virou `auth/auth_routes.py` (2026-07-15), `_LOGIN_HTML =
join(dirname(__file__), "static", "login.html")` passou a apontar para `auth/static/login.html` —
inexistente. `except FileNotFoundError` devolveu 404 **em silêncio**: a página de entrada sumiu
sem erro nenhum no log, e a suíte inteira (1181 testes, na época) continuou verde. O usuário achou
antes da suíte. **Regra para qualquer arquivo novo desta tarefa que precise de caminho de disco
(estático, config, chave):** dois `dirname()` a partir de dentro de um pacote, um só a partir de um
`.py` solto na raiz — e o teste `test_caminhos_de_pacote.py` é o lugar certo para acrescentar o
caso novo, não confiar em revisão visual.

### Armadilha 2 — import de pacote com shim precisa ser síncrono, no carregamento do módulo

**Também já aconteceu, em produção**, com `mod_chat`/`mod_chat_externo` — o comentário no topo de
`main.py` (linhas 35-45) documenta: os dois são shims que fazem `sys.modules[__name__] = _core`
para redirecionar o nome antigo para o pacote novo. Importados no CARREGAMENTO do módulo (antes do
`ThreadingHTTPServer` subir), porque em todo outro lugar o import é preguiçoso (dentro do handler
da requisição) — se duas threads de requisição disparassem a PRIMEIRA importação ao mesmo tempo
(ex.: logo após um deploy), a thread perdedora do lock de import podia capturar a referência ANTIGA
(o shim vazio, antes da substituição) e ficar sem os atributos. Aconteceu de verdade:
`AttributeError: module 'mod_chat_externo' has no attribute 'varrer_triagem_vencida'`. **Regra:**
qualquer arquivo novo desta tarefa que use o padrão shim (`sys.modules[__name__] = ...`) precisa do
import síncrono no topo de `main.py`, nunca só dentro do handler — os domínios do Grupo A que forem
arquivo NOVO simples (Admin, Financeiro-routes) não precisam de shim nenhum (é import direto de
função, como `auth_routes.py` já faz) — esta armadilha só se aplica a quem reusar o padrão de
substituição de módulo do `chat/`.

### Armadilha 3 — o guarda-chuva `/api/projetos/<nome>/...` (achado desta análise, não decidido aqui)

Detalhado na Seção 2, Grupo B. Consequência para a ORDEM: extrair Comercial/Ciclo/Fiscal-por-
projeto antes de resolver como despachar por sufixo produz um de dois erros — (a) uma função nova
que também captura por engano rotas de outro domínio que só por acaso ainda não foi extraído
(silencioso: a rota "errada" continua funcionando, porque cai no mesmo arquivo, até o dia em que
outro domínio tentar reivindicar a mesma rota e um dos dois perder silenciosamente), ou (b) uma
função tão específica por rota que não generaliza nada — o split vira 40 `if` isolados em vez de
10.000 linhas isoladas, sem reduzir a complexidade real. **Isto é decisão de desenho, não mecânica
— reportado ao Marcelo, não decidido por esta sessão** (ver rodapé). A Seção 6.6 do `MAPA_MODULOS.md`
já propõe o conserto mais estreito do sintoma relacionado (completar as listas de rota do manifesto)
— resolver aquilo primeiro pode ser o mesmo trabalho que desenha o despacho por sufixo que esta
extração precisa, ou pode ser insuficiente; não sei ainda, por isso está registrado como pergunta,
não como plano.

### Armadilha 4 — ordem de checagem dentro do método

Os `if`/`elif`+`re.match` de hoje são checados em sequência, do topo do método até o primeiro que
bater. Ao extrair um domínio, a função `handle_<dominio>_get(handler, path)` precisa ser chamada na
MESMA posição relativa em que o primeiro bloco daquele domínio aparecia — nunca "no fim, por
garantia". Hoje isso é seguro porque cada literal/regex é específico o bastante para não colidir
com outro; mas um domínio extraído cedo demais, chamado ANTES de uma rota mais específica de outro
domínio que ainda não foi extraída, pode capturar por engano um caminho que hoje só bate depois de
outras checagens já terem falhado. Nenhuma colisão concreta foi encontrada nesta análise — é um
risco estrutural do mecanismo, não um caso medido — mas é o tipo de coisa que só aparece testando.

---

## 5. Catracas de contagem de linha — a resposta é diferente da do frontend

**Não existe, hoje, nenhum teste que trave contagem/faixa de LINHA de `main.py` como
`test_aceite_achado36.py` trava `static/index.html`.** Verificado: nenhum arquivo em `tests/` lê o
conteúdo-fonte de `main.py` e fatia por número de linha para asserção (`open("main.py")` só aparece
para SUBIR o servidor via `subprocess.Popen`, nunca para ler/fatiar texto). `test_arquitetura_
modulos.py` — o teste de fronteira real do backend — trabalha por **AST e nome de módulo**
(`modulos.MODULOS[nome]["arquivos"]`), nunca por linha; já é imune a este split por desenho.

**O que existe, em vez de catraca, é uma dívida de comentário diferente:** dezenas de arquivos de
teste citam `main.py:NNNN` ou `main.py ~NNNN` em docstring/comentário, como referência de onde uma
rota vive (`test_aceite_achado18.py:33` → "main.py:12278"; `test_contrato_modelo_versionado_e2e.py`
→ "main.py ~6070"/"~7476"; `test_f2_41_sombra_complemento.py:4` → "main.py:2666-2677"; e outros em
`test_aceite_achado19_20.py`, `test_aceite_achado24.py`, `test_aceite_conciliacao_ui_item1.py`,
`test_achado65_item_especial.py`, `test_bateria_ciclo.py`, `test_complemento_pe_e2e.py`). **Nenhuma
delas é executável — são prosa, não asserção.** Não vão ficar vermelhas: vão ficar **erradas em
silêncio**, apontando para uma linha que depois da extração pertence a outro arquivo, ou que nem
existe mais em `main.py`. É dívida de documentação, não achado de teste — mas é exatamente o tipo
de coisa que, se não for corrigida no mesmo commit que move o código (Seção 6, regra do split
frontend), vira confiança falsa para a próxima pessoa que ler o comentário e for procurar no lugar
errado.

**Não é pedido varrer e corrigir todas agora** (mesmo princípio do LP-30/6.8, ainda não é hora) —
fica registrado aqui para quem fizer a extração real: ao mover uma rota, `grep -rn "main\.py.*<a
faixa de linha antiga>" tests/` no mesmo commit, e trocar a referência pelo arquivo/rota novos (ou
apagar o número, já que o nome da rota já identifica o lugar).

---

## 6. Como provar que nada mudou

Mesma disciplina do split de frontend, adaptada ao mecanismo real daqui:

1. **Diff de comportamento por rota, não de linha.** Como não há bloco único de `<script>` para
   comparar por concatenação, a prova equivalente é: para cada rota extraída, o corpo do
   `if`/`re.match` movido tem que ser **idêntico byte a byte** ao original, só trocando `self` por
   `handler` (a mesma adaptação que `auth_routes.py` já fez) e o `return` do método por `return
   True` no fim do bloco que trata. Qualquer diferença além dessa é erro de transcrição.
2. **Contagem de pontos de rota, antes e depois.** Esta análise mediu ≈365 pontos de checagem
   (121 literais + 244 regex) somados nos quatro métodos — a mesma contagem, somada sobre `main.py`
   residual + todos os `handle_*` novos, tem que bater.
3. **`test_arquitetura_modulos.py` e `test_caminhos_de_pacote.py` primeiro, sempre.** São os dois
   ratchets que já existem e já cobrem exatamente os dois erros que já aconteceram nesta família de
   mudança (fronteira de import; caminho de disco dentro de pacote). Rodar estes dois antes de
   qualquer coisa mais cara.
4. **`pytest -q` completo como smoke, nunca como prova central — e nunca pela Sessão B.** Regra do
   próprio papel desta sessão: quem roda a suíte é a Sessão A; esta sessão não roda `pytest` em
   hipótese nenhuma (LP-22, colisão medida, não cautela genérica).
5. **A suíte de E2E de navegador é a guarda de comportamento real** — com as mesmas ressalvas já
   registradas para o frontend (LP-16, LP-21, LP-22: histórico de flakiness medido; um E2E
   vermelho durante a extração não é prova automática de regressão, mas também um E2E verde sozinho
   não é suficiente, dado o histórico).

**Ordem por domínio extraído:** 1 → 2 → 3 → suíte E2E daquele domínio → só então a suíte completa.

---

## 7. O que NÃO fazer junto

**A mesma regra do split de frontend, palavra por palavra:** todo defeito encontrado durante a
extração vira registro — nunca conserto no mesmo commit. Um split que também conserta deixa de ser
"comportamento idêntico", e a Seção 6 inteira perde o sentido.

**Onde registrar, e por quem:** achado de análise (leitura de código, sem decisão de destino ainda)
vai para a Seção 7 do `MAPA_MODULOS.md`, "Candidatos a achado" — não vira linha na Lista Paralela
por conta própria desta sessão. Só ganha número/destino na Lista Paralela quando tiver a forma que
os demais itens já têm (classificação por causa estrutural ou decisão explícita) — e quem decide
isso, quando envolve escolha, é o Marcelo, não esta sessão.

**Coisas que esta própria análise já encontrou, que vão aparecer de novo na frente de quem fizer a
extração, e que NÃO devem ser consertadas ali:**
- a Causa E (guarda-chuva `/api/projetos/`) — é a Armadilha 3 acima; resolver isso é PRÉ-REQUISITO
  de desenho do Grupo B, não um conserto a fazer durante a extração dele;
- qualquer `main.py:NNNN` desatualizado nos comentários de teste (Seção 5) — corrigir só o que a
  própria extração tocar, não sair caçando os demais fora de escopo;
- qualquer função das 101 pós-classe que, ao ser lida de perto para decidir o arquivo de destino,
  revelar comportamento estranho — mesmo critério do split de frontend: se consertar exige mudar o
  QUE o código faz, é achado, registra e segue; se é só mudar ONDE mora, é split, continua.

---

## O que este plano NÃO decide, e por que fica com o Marcelo

1. **Como despachar o Grupo B por sufixo** (Armadilha 3) — é desenho novo, não mecânica; bloqueia a
   extração de Comercial, Ciclo e Fiscal-por-projeto até existir uma resposta.
2. **Se a Seção 6.6 do `MAPA_MODULOS.md`** (completar as listas de rota do manifesto, hoje um
   conserto pequeno e adormecido) deveria acontecer ANTES desta extração, como parte da mesma
   decisão, ou continuar separada.
3. **O nome/local exato dos arquivos novos** (`mod_admin.py`? um pacote `admin/` direto? `mod_
   financeiro_routes.py`, ou um nome que já esteja reservado em outro lugar?) — esta análise propõe
   o caminho de menor atrito (arquivo solto, convenção atual da raiz), mas é decisão de quem vai
   executar, com o Marcelo por perto se o nome importar para outra coisa.

Nada disto impede começar pelo Grupo A (Admin primeiro) — só impede avançar para o Grupo B sem essa
conversa.

---

## Respostas do Marcelo (21/09/2026)

**Sobre o item 1 (como despachar o Grupo B por sufixo):** não se decide, se mede. Listar as 157
rotas de `/api/projetos/<nome>/...` e verificar se o sufixo particiona limpo entre Comercial, Ciclo
e Fiscal. Se particionar, a tabela de despacho se escreve sozinha a partir da medição; se houver
ambiguidade real, aí sim existe decisão de desenho a tomar. **Medição feita em 21/09/2026 — não
particiona limpo. Ver subseção abaixo.**

### Medição do item 1 — resultado (21/09/2026)

Das 157 ocorrências de `/api/projetos` em `main.py` (104 são pontos de despacho reais; o resto é
comentário/prosa), a maior parte segue limpa:

| Domínio | Sufixos | Contagem aprox. |
|---|---|---|
| **Comercial** | `equipe`, `pe/*` (exceto os de PE-sob-`/ciclo/`, ver abaixo), `parcelas*`, `retencoes`/`retido/*`, `briefing`, `parametros`, `aprovacao-pe*`, `aditivo*`, `contrato` (GET/POST/PUT — exceto `concluir-financeiro`), `medicao*`, `parceiro`, `editar`, `consultores`, `status` | ~62 |
| **Ciclo (núcleo genuíno)** | `ciclo` (bare), `ciclo/<codigo>` PATCH genérico, `ciclo/<codigo>/reabrir`/`/data-prevista`/`/responsavel`/`/pos-conclusao`/`/transferencia/aceitar`, `cronograma` | ~15 |
| **Fiscal** | `ciclo/15/nfe`, `/nfe-fabrica`, `/emitir-nfe`, `/emitir-nfse`, `/nfe/consultar`, `/nfe/cancelar` | 7 |

**O achado: o prefixo `/ciclo/` não é homogêneo — mistura Ciclo-núcleo com rotas de outro domínio,
sem nenhuma marca sintática de sufixo que distinga as duas.** Casos concretos, confirmados lendo o
código (não só o nome da rota):

| Linha (main.py) | Rota | Sufixo sugere | Domínio real (pelo código) |
|---|---|---|---|
| 8558 | `ciclo/11d/aprovar` | Ciclo | **Financeiro** — comentário "Gate financeiro", AF2 |
| 8652 | `ciclo/11d/reprovar` | Ciclo | **Financeiro** — mesma AF2 |
| 11191 | `ciclo/21/conciliar` | Ciclo | **Financeiro** — `mod_contabil`, comentário "Gate financeiro", Conciliação Final |
| 15161 | `contrato/concluir-financeiro` | Comercial | **Financeiro** — importa `mod_contabil`, exige `_aprovador_financeiro` |
| 6510 | `ciclo/pe` | Ciclo | **Comercial (PE)** — "documentos + revisões + status das subfases" de PE |
| 16283 | `ciclo/<codigo>/revisao` | Ciclo | **Comercial (PE)** — revisão + reabertura em cascata da subfase de PE |
| 16365 | `ciclo/<codigo>/concluir` | Ciclo | **Comercial (PE)** — comentário "fecha a subfase de PE" |
| 16004 | `ciclo/<codigo>/documento` (upload) | Ciclo | **Comercial (PE)** |
| 6548, 16115 | `ciclo/documento/<id>`, `ciclo/<codigo>/documentos/<id>/remover` | Ciclo | **ambíguo de fato** — endpoint genérico; o documento pode ser de Contrato/PE/Aditivo/Medição, só se sabe em runtime |
| 6580, 16056 | `ciclo/<codigo>/pedido-xml` | Ciclo | zona cinzenta Ciclo↔Expedição (usa `mod_ciclo.tipo_doc_operacional`, mas Expedição já tem prefixo próprio `/api/expedicao`, não usado aqui) |
| 14285 | `ciclo/desfazer_aprovacao` | Ciclo | **Comercial (Negociação)** — "volta ao orçamento" |

Fora do prefixo `/ciclo/`, mais quatro rotas sem dono único nos três domínios nomeados:
- **2195 `auditoria-contabil`** → Financeiro (`mod_contabil`).
- **5084, 8874 `contatos-comunicacao`(`/confirmar`)** → Chat/Comunicação (`mod_chat`) — domínio que
  já tem prefixo próprio (`/api/comunicacao/*`) em outro lugar, reaparecendo aqui embutido.
- **3172 `entrega-resumo`** → lê `CicloLogistico` (Expedição) **e** `Projeto.data_entrega`
  (Comercial/Ciclo) na mesma resposta — sem dono único.
- **5869, 14756 `atribuicoes`** (Mapa de Atribuições) → cross-cutting, não claramente Comercial nem
  Ciclo.

**Conclusão: existe decisão de desenho real, não só trabalho mecânico — exatamente o segundo ramo
que a orientação do Marcelo previu.** Um despachante ingênuo por sufixo (`ciclo/*` → Ciclo) captura
por engano pelo menos 9 rotas que pertencem, pelo código que executam, a Financeiro ou a
Comercial(PE). A 6.6 do manifesto não resolve isso sozinha classificando por prefixo — precisa, no
mínimo, de uma decisão sobre se essas rotas entram na lista de Financeiro/Comercial (fiéis ao que o
código faz) ou ficam em Ciclo (fiéis ao prefixo da URL, por simplicidade de guarda de módulo — a
guarda hoje é "tudo ligado" por padrão, então o custo de errar aqui é sobre uma loja hipotética que
desligue só Financeiro ou só Comercial mantendo Ciclo ligado). **Decisão pendente do Marcelo — não
resolvida por esta medição**, que só troca a pergunta original ("existe ambiguidade?") por uma mais
concreta ("o que fazer com estas ~11 rotas nomeadas?").

### As duas opções para as ~11 rotas ambíguas (proposta, não decisão)

**Opção A — despachar por comportamento.** `handle_financeiro_get/post` reivindica `ciclo/11d/
aprovar`, `ciclo/11d/reprovar`, `ciclo/21/conciliar` e `contrato/concluir-financeiro`;
`handle_comercial_get/post` reivindica `ciclo/pe`, `ciclo/<codigo>/revisao`, `ciclo/<codigo>/
concluir`, `ciclo/<codigo>/documento`, `ciclo/desfazer_aprovacao`. `handle_ciclo_get/post` só pega o
que sobrar do prefixo, checado por último (Armadilha 4 da Seção 4 — ordem de checagem importa: as
exceções específicas têm que ser checadas ANTES do `handle_ciclo` genérico, ou o genérico as
captura primeiro).
- **Prós:** a guarda de módulo (`_bloqueio_modulo`/`modulo_do_path`, Causa E) fica correta de
  verdade — desligar Financeiro numa loja bloqueia `ciclo/21/conciliar` de fato, não só de nome.
  Fiel ao que `MAPA_MODULOS.md` § 1 já diz sobre onde cada lógica mora.
- **Contras:** `handle_ciclo_get/post` deixa de ser "tudo que começa com `/ciclo/`" — vira uma
  lista de exclusões que precisa ser mantida manualmente conforme rotas novas nascerem sob esse
  prefixo (o mesmo risco de manutenção manual que a Causa E já descreve para o manifesto hoje).
  As 3 rotas "ambíguas de fato" (`ciclo/documento/<id>` etc., que só sabem o domínio em runtime)
  não se resolvem nem aqui — precisam de uma checagem própria (ler o documento, decidir o domínio)
  dentro do handler, não só no despacho.

**Opção B — despachar por prefixo de URL.** `handle_ciclo_get/post` reivindica TUDO sob `/ciclo/*`,
sem exceção — mecânico, replica o padrão de `auth_routes.py` sem lista de exclusão nenhuma. A
lógica de Financeiro/Comercial(PE) continua chamada de dentro do handler de Ciclo (como já é hoje),
só que agora hospedada num arquivo/pacote com nome "Ciclo".
- **Prós:** zero lista de exceção pra manter; a extração fica tão simples quanto Admin/Cadastro/
  Financeiro-global — sem decisão de desenho nenhuma, só mecânica.
- **Contras:** a guarda de módulo continua errada pelo MESMO motivo da Causa E — só que agora o
  "prefixo largo demais" migra de Fiscal (hoje) para Ciclo (depois da extração), sem consertar o
  problema que motivou medir isto. `ciclo/11d/aprovar`/`reprovar`/`21/conciliar` ficariam
  fisicamente dentro do módulo/pacote "Ciclo", o que text-searches futuras por "onde mora a lógica
  financeira" não vão esperar encontrar.

Nenhuma das duas resolve os 3 casos "ambíguos de fato" (documento genérico, `entrega-resumo`,
`atribuicoes`) — esses continuam precisando de uma checagem em runtime independente de qual opção
for escolhida para o resto.

**Sobre o item 2 (se a 6.6 do `MAPA_MODULOS.md` deveria vir antes):** sim, na ordem 6.6 → extração
do Grupo B. Completar as listas de rota do manifesto (Comercial/Ciclo em `modulos.py`) entrega a
tabela de despacho do Grupo B como subproduto — é o mesmo trabalho visto de dois ângulos; fazer na
ordem inversa resolveria a mesma coisa duas vezes.

**Sobre o item 3 (nome/local dos arquivos novos):** nomes seguem o precedente já provado em
produção — `<dominio>/<dominio>_routes.py`, com a assinatura `handle_<dominio>_get/post(handler,
path) -> bool` de `auth/auth_routes.py`. Para domínios que ainda são arquivo solto na raiz (Admin,
Financeiro-routes), o mesmo padrão de nome sem o pacote: `mod_<dominio>_routes.py` (ou, no caso de
Admin, o arquivo novo já previsto, `mod_admin.py`, ganha `handle_admin_get/post/put/patch` direto —
sem sufixo `_routes` quando o arquivo inteiro já é só roteamento).

## Decisão do Marcelo (22/09/2026) — Opção B, por enquanto

**Escolhida a Opção B: despachar por prefixo de URL.** `handle_ciclo_get/post` reivindica tudo sob
`/ciclo/*`, sem lista de exceção. O critério foi de modelo de negócio, não de código: **hoje,
desligar o módulo Financeiro numa loja significa "some da tela", não "bloqueia a operação"**.

**O que isso compra, dito explicitamente para não virar surpresa depois.** A guarda de módulo
(`_bloqueio_modulo` + `modulo_do_path`) bloqueia de verdade no backend, por prefixo do manifesto —
não é enfeite. Com a Opção B, as rotas financeiras que moram sob `/ciclo/` ficam classificadas como
Ciclo, então **uma loja com Financeiro desligado e Ciclo ligado continua aprovando o gate 11d e
conciliando na etapa 21**, pela tela do Ciclo. Isso é coerente com a decisão: o módulo Financeiro
que ela não assina são as telas próprias dele (DRE, contas, provisões), não o gate operacional que
vive dentro do ciclo. O que NÃO se pode fazer é vender "Financeiro desligado" como se fosse uma
fronteira que impede a loja de tocar em dinheiro — hoje não é, e esta decisão mantém assim.

**Consequência para a 6.6 do `MAPA_MODULOS.md`:** a classificação fica trivial — `/ciclo/*` inteiro
entra na lista de rota de Ciclo, sem exceção a manter à mão. A ordem 6.6 → extração do Grupo B
continua valendo.

**O que destrava:** o Grupo B deixa de estar bloqueado por decisão de desenho. Continua atrás da
6.6 e da ordem da Seção 3 (Grupo A primeiro, Financeiro e Grupo B por último), mas não há mais
pergunta em aberto para o Marcelo.

**"Por enquanto" é literal, e o custo de mudar de ideia é conhecido:** o dia em que existir loja
assinando sem Financeiro e a guarda precisar valer como fronteira comercial de verdade, a virada
para a Opção A é mover ~9 rotas nomeadas de arquivo e checá-las antes do genérico — trabalho
delimitado, na casa de um lote, não uma reescrita. As 3 rotas ambíguas de fato (`ciclo/documento/
<id>`, `entrega-resumo`, `atribuicoes`) continuam precisando de checagem em runtime em qualquer
cenário; a Opção B não as resolve, só não piora.

---

**Item à parte, fora dos três do rodapé:** os comentários `main.py:NNNN` da Seção 5, espalhados em
16 arquivos de teste, viraram item próprio — `LP-37` (`docs/db/LISTA_PARALELA.md`, destino HIGIENE)
— em vez de ficarem só como prosa nesta seção. Continuam com a mesma regra: corrigir só o que a
própria extração tocar, no mesmo commit que move a rota; não é varredura para fazer isolada agora.
