# Lista Imediata — as lacunas que a conferência de 22/09 deixou abertas

> **Camada 4 · TRABALHO EM ANDAMENTO.** Descartável quando fechar. Lista FECHADA: **8 itens**,
> numerados LI-1 a LI-8. Item novo não entra aqui — vai para a `LISTA_PARALELA.md` com destino.

**Data:** 22/09/2026. **Alvo:** fechar até 23/09.
**Origem:** a conferência da `LISTA_PARALELA.md` contra o código (commit `2d72c2e`) e a medição do
ACHADO-20 pedida pelo Marcelo em 22/09.

## Estado — a única fonte de verdade sobre o que já fechou

**Quem fecha um item edita ESTA tabela no mesmo commit do conserto.** É o que permite qualquer
sessão nova (ou qualquer terminal que perdeu contexto) pegar a lista de onde parou sem perguntar a
ninguém: o repositório é a memória, a conversa não é.

| item | o que é | estado | commit |
|---|---|---|---|
| LI-1 | ACHADO-20 — guarda no endpoint do contrato + guarda de ciclo | ABERTO | — |
| LI-2 | LP-33b — validação de servidor no lado da FUNÇÃO | ABERTO | — |
| LI-3 | LP-35 — inverter o default de `senha_provisoria` (DDL) | ABERTO | — |
| LI-4 | LP-32 — selo da loja no cabeçalho | ABERTO | — |
| LI-5 | LP-27 — motivos de retenção servidos pelo backend | ABERTO | — |
| LI-6 | LP-28 — rótulo "Operacional" → Montagem | ABERTO | — |
| LI-7 | LP-36 — verificar a tarja em campo (não é código) | ABERTO | — |
| LI-8 | Lote Causa F — sete achados de higiene contábil | ABERTO | — |

Estados válidos: `ABERTO`, `EM CURSO (<terminal>)`, `FECHADO (<hash>)`, `CORTADO (<motivo>)`.
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

**Conserto (duas guardas, não uma):**
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

## LI-2 · LP-33b — o lado da FUNÇÃO grava faixa de comissão sem validação de servidor

A metade que sobrou do LP-33. O configurador da função já força a última faixa sem teto **na
tela** (`_rmFaixas`, `static/index.html`), e o motor da loja já tem `mod_provisoes.validar` — mas
`mod_cadastro` grava `comissao.faixas` conferindo só o tipo dos números, sem exigir a forma
(última faixa com `venda_ate` nulo). Enquanto for assim, a garantia daquele lado depende da tela,
e a tela não é garantia.

**Conserto:** validação no servidor, espelhando a regra de `mod_provisoes.validar`, no ponto em
que `mod_cadastro` grava. Os dois modelos continuam separados de propósito (decisão de 17/09) —
o que se compartilha é a forma da faixa, não o resolvedor.
**Prova:** teste que tenta gravar faixas com a última fechada e espera recusa.
**Tamanho:** pequeno.

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
