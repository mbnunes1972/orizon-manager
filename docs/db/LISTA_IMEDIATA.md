# Lista Imediata — as lacunas que a conferência de 22/09 deixou abertas

> **Camada 4 · TRABALHO EM ANDAMENTO.** Descartável quando fechar. Lista FECHADA: **8 itens**,
> numerados LI-1 a LI-8 — **7 ativos**, porque o LI-2 nasceu cortado (já estava feito, ver a
> tabela). Item novo não entra aqui — vai para a `LISTA_PARALELA.md` com destino.

**Data:** 22/09/2026. **Alvo:** fechar até 23/09.
**Origem:** a conferência da `LISTA_PARALELA.md` contra o código (commit `2d72c2e`) e a medição do
ACHADO-20 pedida pelo Marcelo em 22/09.

## Estado — a única fonte de verdade sobre o que já fechou

**Quem fecha um item edita ESTA tabela no mesmo commit do conserto.** É o que permite qualquer
sessão nova (ou qualquer terminal que perdeu contexto) pegar a lista de onde parou sem perguntar a
ninguém: o repositório é a memória, a conversa não é.

| item | o que é | estado | commit |
|---|---|---|---|
| LI-1 | ACHADO-20 — guarda no endpoint do contrato + guarda de ciclo | **FECHADO** | `git log --grep="LI-1"` |
| LI-2 | LP-33b — validação de servidor no lado da FUNÇÃO | **CORTADO (já estava feito desde 17/09)** | — |
| LI-3 | LP-35 — inverter o default de `senha_provisoria` (DDL) | **FECHADO** | `git log --grep="LI-3"` |
| LI-4 | LP-32 — selo da loja no cabeçalho | ABERTO | — |
| LI-5 | LP-27 — motivos de retenção servidos pelo backend | **FECHADO** | `git log --grep="LI-5"` |
| LI-6 | LP-28 — rótulo "Operacional" → Montagem | **FECHADO** | `git log --grep="LI-6"` |
| LI-7 | LP-36 — verificar a tarja em campo (não é código) | ABERTO | — |
| LI-8 | Lote Causa F — sete achados de higiene contábil | ABERTO | — |

**Portão do bloco 1 (LI-1, LI-5, LI-6) — PASSOU, 22/09 23h:** suíte completa **2.893 passed,
3 xfailed, 0 failed em 10m56**. Nenhum vermelho, nem os 3 do `#neg-subtotal` (flake LP-22) — zero
numa rodada não prova nada, a taxa registrada é de 1/10 a 10/10; é só o que aconteceu desta vez.
Os 3 `xfailed` são pré-existentes (achados do ACHADO-19 ainda pendentes), não são consequência do
bloco. Comparação útil: a rodada da manhã deu 2.884 passed em 13m20 com 3 vermelhos.

Estados válidos: `ABERTO`, `EM CURSO (<terminal>)`, `FECHADO`, `CORTADO (<motivo>)`.

**Correção de 22/09 — a coluna não guarda hash, e o motivo é bom.** A regra original mandava
escrever `FECHADO (<hash>)` no MESMO commit do conserto, o que é impossível: o hash só existe
depois que o commit existe, e cada `git commit --amend` para corrigi-lo muda o próprio hash de
novo. Medido no LI-1: duas rodadas de convergência (`b6cd6da` → `b7c252c`) e a tabela acabou
apontando para `b7c252c`, que **não é o commit do conserto** — o commit real é uma geração
adiante. E o detalhe que torna isso pior do que não ter hash: `b7c252c` ainda RESOLVE (o amend
órfã o commit, não o apaga — ele vive no reflog até o gc), então `git show b7c252c` funciona e
exibe com toda a confiança uma versão que não está na `main`. Hash órfão não parece errado,
parece verdade. **O vínculo é o número do LI na mensagem do commit**, que é estável e
não depende de ordem: `git log --grep="LI-1"` acha o conserto, e é isso que a coluna registra.
Quando os oito saírem de ABERTO, esta lista é apagada e o que sobrar volta para a
`LISTA_PARALELA.md` com destino.

---

**Por que esta lista existe:** a lista paralela é organizada por *destino* e não por *data* — é
boa para não crescer sem controle, e ruim para responder "o que eu fecho amanhã". Esta lista tem
número fixo e um critério de pronto por item. Quando os oito fecharem, ela é apagada.

---

## LI-1 · ACHADO-20 — a recursão infinita tem porta de entrada pelo endpoint de contrato

**MEDIDO em 22/09, e o achado original subestimava.** O texto de 30/08 diz *"não alcançável hoje
pelo endpoint real de criação de complemento, que sempre cria um `Orcamento` novo e separado"* —
verdade, e irrelevante: **não é por ali que o estado auto-referente entra.** É pelo endpoint do
contrato.

**O caminho, lido no código:**

- `POST /api/projetos/<nome>/contrato` (`main.py`) recebe `orcamento_id` do corpo da requisição.
- A única validação do orçamento é `_montar_dados_projeto_para_contrato`, que confere se ele
  existe e se `orcamento.projeto_id == nome_safe`. **Não há nenhuma checagem de
  `complemento_pe`.** Depois disso, `Contrato(projeto_nome=..., orcamento_id=orcamento_id)` nasce
  apontando para o que veio no corpo.
- Com `Contrato.orcamento_id` apontando para um orçamento `complemento_pe=1`, `_pe_fator_contexto`
  devolve esse orçamento como `orc_ct`; `_complemento_diferencas` chama
  `_negociacao_breakdown(orc_ct, ...)`; `_negociacao_breakdown` vê `complemento_pe=1` e chama
  `_complemento_diferencas` de volta. **Não existe guarda de ciclo em nenhum dos dois lados.**

**Não é hipótese de laboratório:** orçamento com `complemento_pe=1` é rotina (todo aditivo e toda
renegociação de PE cria um), e a própria docstring de `_pe_fator_contexto` já registra que
recomputar o aditivo ao vivo *"criaria recursão infinita a cada aditivo assinado (não só no caso
auto-referente do ACHADO-20)"* — ou seja, o risco já era conhecido e foi contornado lendo o
snapshot, não fechado.

**O que NÃO foi medido, e é a única incógnita que sobra:** se a tela oferece esse caminho, ou se
hoje ele só é alcançável por quem chama a rota direto. Isso muda a urgência, não o conserto.

### Remedição de 22/09 (Terminal A) — o conserto de duas guardas estava errado

**A guarda "fundo do poço" que este item mandava pôr em `_complemento_diferencas` é CÓDIGO MORTO
para o caso que interessa.** O laço não passa por ela: `_pe_fator_contexto` (`main.py`) chama
`d_ct = _negociacao_breakdown(orc_ct, db)` **incondicionalmente, antes de retornar**. No estado
auto-referente é ali que o ciclo fecha — `_negociacao_breakdown` → `_complemento_diferencas` →
`_pe_fator_contexto` → a mesma chamada — e `_complemento_diferencas` nunca chega a receber o
`orc_ct` para conferir. Medido rodando
`test_negociacao_breakdown_excecoes.py::test_complemento_pe_no_proprio_orcamento_do_contrato_recursao_infinita`
COM as duas guardas no código: continua passando, ou seja, o `RecursionError` continua
acontecendo. (Esse teste **fixa o defeito** hoje — como o teste do silêncio da triagem fixava o
silêncio. Ele tem que virar quando o conserto entrar.)

O comentário de `_pe_fator_contexto` que este item citava ("recomputar ao vivo aqui criaria
recursão infinita a cada aditivo assinado") fala do laço de `Aditivo` logo abaixo, que por isso lê
o snapshot congelado — **não** da chamada de cima. Eu li o comentário e não o código.

**Desenho decidido em 22/09 (decisão técnica, não de produto):**

1. **Uma guarda só no fundo, e no lugar certo:** dentro de `_pe_fator_contexto`, imediatamente
   antes de `d_ct = _negociacao_breakdown(orc_ct, db)` — é a ÚNICA aresta do ciclo. As duas
   guardas em `_complemento_diferencas`/`_complemento_diferencas_fase` **saem**: depois desta,
   elas são inalcançáveis, e guarda inalcançável sem teste é ruído que engana o próximo leitor.
2. **O sinal é EXCEÇÃO nomeada, não sentinela.** `_pe_fator_contexto` tem **cinco** chamadores
   (`main.py` 3013, 8468, 18808, 18997, 19057). Reaproveitar `orc_ct is None` faria o caso
   auto-referente responder *"Projeto sem contrato para comparar."* — e o projeto TEM contrato;
   é afirmação falsa na tela, a família do ADR-004 e do "Venda até". Sentinela nova exige que os
   cinco lembrem de conferir, e quem esquecer produz número errado em silêncio. Exceção nomeada
   falha alto e não tem como ser ignorada por engano.
3. **Cada chamador converte a exceção em erro nomeado do usuário** — os dois de complemento para
   o contrato `(None, erro)` que já usam; os outros três para 409 com a mesma mensagem. Nenhum
   deles pode deixar a exceção cair num `except Exception` largo e virar 500 mudo: isso
   reintroduziria a falha silenciosa por outro caminho.
4. A guarda do endpoint do contrato (a porta) continua como estava — ela impede o estado; esta
   impede o laço para o estado que já existir no banco.

### Segunda remedição de 22/09 (Terminal A) — o erro morria no meio do caminho

Com os itens 1–4 acima implementados, o ciclo fecha (não há mais `RecursionError`), **mas
`_negociacao_breakdown` chamada DIRETO devolve um breakdown de complemento zerado, calada.**
Medido, não deduzido. A causa: `_negociacao_breakdown` não é um dos cinco chamadores de
`_pe_fator_contexto` — ela chama `_complemento_diferencas`, que (pelo item 3) convertia a exceção
em `(None, erro)`, e então descarta esse retorno: `for l in (linhas_c or [])` transforma o `None`
em lista vazia e o texto do erro nunca é lido. Trocamos `RecursionError` por número errado em
silêncio, que é pior.

**O erro de desenho foi meu, e é de LUGAR:** o item 3 mandou converter a exceção em
`_complemento_diferencas`/`_complemento_diferencas_fase`, que são funções INTERMEDIÁRIAS. Converter
no meio do caminho é o que permite alguém acima descartar o resultado sem perceber.

**Regra, que substitui o item 3:** *a exceção nomeada só se captura em FRONTEIRA HTTP.* Nenhuma
função intermediária a captura — nem as duas de complemento, nem `_negociacao_breakdown`. Ela sobe
até o handler que responde ao usuário, e ali vira 409 com mensagem nomeada. Duas consequências
diretas:

- as capturas dentro de `_complemento_diferencas` e `_complemento_diferencas_fase` **saem**;
- os dois endpoints que chamam essas funções (`main.py` 6064 e 8848) ganham a captura que elas
  perderam, e `_aditivo_dados_calculo` apenas deixa passar, porque quem o chama é endpoint.

**E o `except Exception` largo é o inimigo desta regra.** Onde houver um no caminho — o
`[F2-41-SOMBRA]` dentro de `_complemento_diferencas`, e o que o Terminal A já achou acima do
handler de 18146 — a captura específica da exceção nomeada vem ANTES, re-levantando. Um
`except Exception` que engole esta exceção recria a falha silenciosa por outra porta.

**O que continua valendo do desenho anterior:** guarda na porta (endpoint do contrato), guarda
única no fundo (`_pe_fator_contexto`, antes da chamada que fecha o ciclo), exceção nomeada em vez
de sentinela, e nenhuma guarda inalcançável.

**Conserto (na redação original, mantida como registro — a guarda 2 abaixo foi movida pelo item
1 da primeira remedição, e o item 3 foi substituído pela regra da segunda):**
1. no endpoint do contrato — recusar `orcamento_id` de orçamento `complemento_pe=1`, com erro
   nomeado. É a porta;
2. em `_complemento_diferencas` e `_complemento_diferencas_fase` — se o orçamento do contrato for
   ele próprio um complemento, recusar com erro nomeado em vez de recorrer. É o fundo do poço,
   e protege contra correção manual no banco, migração e importação, que foi o motivo original de
   registrar o achado.

**Prova:** teste que cria o estado auto-referente direto no banco e espera erro nomeado (não
`RecursionError`, não 500 mudo), mais teste do endpoint recusando o `orcamento_id` de complemento.
**Tamanho:** pequeno. **Risco:** baixo — as duas guardas são recusas, não mudam caminho feliz.

---

## LI-2 · CORTADO — a validação do lado da FUNÇÃO já existe desde 17/09

**Não fazer nada aqui.** Este item nasceu de um erro meu de conferência, corrigido no mesmo dia, e
fica registrado porque o erro é instrutivo.

A regra está em `mod_provisoes.validar_faixas_comissao` e é chamada pelos dois lados: pelo motor
da loja (via `validar_config_financeira`) e pelo lado da FUNÇÃO no endpoint `/api/funcoes`
(`main.py`, logo antes de `apl()`), desde 17/09 — com `tests/test_lp33_faixas_sem_teto.py`
cobrindo os dois. **Como o erro aconteceu:** olhei `mod_cadastro.funcao_aplicar`, não achei
validação ali, e concluí ausência. A guarda mora um nível acima, no endpoint que chama `apl()`.
Ausência não se conclui de um ponto do caminho — se conclui percorrendo o caminho.

---

## LI-3 · LP-35 — inverter o default de `senha_provisoria`

`database.py` declara `senha_provisoria` com `default=0, server_default="0"`. Esquecer o parâmetro
produz conta insegura — já aconteceu uma vez, na tela de Admin. Invertendo para 1, esquecer passa
a produzir conta segura e quem quer 0 (os dois seeds de teste) passa explícito.

**Cuidados que o próprio item já registra, e que fazem dele o maior desta lista:** é DDL, exige
migração (R1); `default` do Python e `server_default` mudam **juntos** ou criam duas verdades
divergentes (ORM ≠ SQL cru); e é coluna lida por milhares de testes, então pede varredura dos
pontos de criação de `Usuario` e dos seeds, não pressa.
**Prova:** migração + `tests/test_gabarito_migration_x_seed.py` verde + teste de que criar
`Usuario` sem passar o campo produz `senha_provisoria=1`.
**Tamanho:** médio — é o item que eu tiraria do dia se o dia apertar, porque é o único com DDL.

---

## LI-4 · LP-32 — o selo da loja no cabeçalho

Medido em 22/09: a pílula `.tf-marca-loja` / `#tf-loja-nome` é de **23/08** (`2209cd7`), anterior
ao seu achado de 16/09 — ou seja, é exatamente a que você olhou e achou pequena demais. 13px,
semibold, colada no wordmark.

Com cinco lojas-piloto simultâneas isso deixa de ser cosmético: quem opera duas unidades precisa
saber em qual está **antes** de aprovar desconto ou assinar contrato.
**Conserto:** tratar como selo de contexto com peso próprio, não como legenda do logo.
**Prova:** captura em 1280 e em 1600, claro e escuro — e o seu aceite visual, que é o único
critério que vale aqui.
**Tamanho:** pequeno. **Dependência:** precisa de você para fechar.

---

## LI-5 · LP-27 — motivos de retenção duplicados entre tela e servidor

`mod_retido.MOTIVOS_RETENCAO` é a lista canônica e o backend valida contra ela
(`main.py`, 400 quando o motivo não está na lista). O `static/index.html` mantém um **espelho
hardcoded** com os mesmos sete valores, rotulado no próprio código como "espelho de
mod_retido.MOTIVOS_RETENCAO". Dois lugares com a mesma lista é a mesma doença do contador do Chat
Interno, só que ainda não divergiu.
**Conserto:** a tela passa a receber a lista do servidor. Uma fonte, dois consumidores.
**Prova:** teste que muda a lista no backend e vê a tela refletir (ou, no mínimo, que o endpoint
serve a lista e o JS não tem mais literal).
**Tamanho:** pequeno.

---

## LI-6 · LP-28 — o manifesto chama Montagem de "Operacional"

`modulos.py`: `"montagem": {..., "rotulo": "Operacional", ...}`. Nome interno que não corresponde
ao domínio, e o rótulo aparece na UI de módulos.
**Conserto:** trocar o rótulo; conferir quem lê `rotulo` antes (sidebar, tela de módulos, testes).
**Prova:** suíte verde — há teste de manifesto.
**Tamanho:** trivial. É o item para fechar primeiro e tirar da frente.

---

## LI-7 · LP-36 — VERIFICAR a tarja vermelha em campo

Não é código: os dois consertos existem desde 18/09 (`c070b46`). O que falta é alguém ver
funcionar com um contato real de janela fechada. `RETOMAR.md` já registra isto como item sem dono
desde 18/09 — quatro dias.
**Prova:** um contato em Homologação com mais de 24 h desde a última mensagem dele; tentar
responder por texto livre; a tarja tem que aparecer, e o aviso de janela tem que estar no composer
ANTES da tentativa.
**Tamanho:** minutos. **Dependência:** precisa de você ou de quem opera Homologação.

---

## LI-8 · Lote Causa F — sete achados de higiene contábil, numa passada só

ACHADO-04, 05, 08, 09, 10, 11 e 17. O `MAPA_MODULOS.md` já classificou os sete na Causa F e é
explícito: nenhuma fronteira de módulo teria evitado nenhum deles — são resíduos de decisões de
produto que mudaram (conta nunca tocada, evento morto, `_fin_evento_seguro` que é código morto,
docstring desatualizada, conta cujo nome não descreve o que o código faz).

**Regra deste item:** é UM lote, uma passada, sem decisão de arquitetura nem de produto. Cada
achado que exigir decisão sai do lote e vira item da `LISTA_PARALELA.md` — não se decide dentro
de um lote de higiene.
**Prova:** suíte verde + os sete achados marcados no `ACHADOS_CONTABEIS.md` com o commit.
**Tamanho:** médio pelo volume, baixo por item. **É o segundo candidato a sair do dia**, atrás
do LI-3.

---

## O que NÃO entra nesta lista, e por quê

- **Os 10 itens de FRONTEIRA** — morrem quando a fronteira for construída, por definição. A 6.2
  está em execução nesta Semana 2 (`TAREFA_TELA_UNICA_PROVISOES.md`) e leva junto LP-13, LP-10,
  LP-19 e a metade aberta do ACHADO-40. Não se fecha por esforço de um dia.
- **Os 8 itens de INFRA** — congelados por decisão sua até depois de 01/10.
- **LP-03, LP-34, LP-37** (higiene) — LP-37 tem regra própria (corrigir só o que a extração de
  rota tocar, no mesmo commit); LP-34 precisa estar pronto antes de clonar as lojas-piloto, que é
  outubro, não amanhã; LP-03 é varredura, e varredura sem tempo vira amostra.
- **ACHADO-01, 06, 07, 19, 29, 31, 37, 41, 49, 50, 56, 67** — todos com destino escrito
  (defeitos conhecidos do beta1, percurso de homologação, lista paralela ou fronteira). Nenhum
  órfão: o único que estava sem destino era o ACHADO-40, amarrado à 6.2 em 22/09.

## Ordem sugerida

LI-6 (trivial, tira da frente) → LI-1 (é o único com modo de falha feio) → LI-2 → LI-5 → LI-4
(precisa do seu aceite) → LI-7 (precisa de você, pode ir em paralelo a qualquer momento) →
LI-3 → LI-8.

**Se o dia não comportar oito:** cortar LI-8 primeiro, LI-3 depois. Os seis restantes cabem.

## Regras deste lote

1. **Não abrir achado novo.** Encontrou defeito? Anota e reporta ao Marcelo — não conserta.
2. Um commit por item, com o número do LI na mensagem, e a tabela de Estado atualizada no MESMO
   commit. **Portão por BLOCO, não por item:** a suíte completa leva ~13 min (medido em 22/09),
   então cada item fecha com os testes ALVO dele verdes, e a suíte completa roda uma vez ao fim de
   cada bloco de itens. Nada vai para tag sem suíte completa verde.
3. LI-3 é o único com DDL — migração no mesmo commit do modelo (R1), sem exceção.
4. Antes da suíte completa, a checagem da regra 2b do `PLANO_SEMANA_1.md` **na redação corrigida
   de 22/09** (olhar `playwright-mcp` pelo PPID, excluindo a própria árvore — não o processo
   `claude`, e Chromium ocioso não conta como ocupado).
