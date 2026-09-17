# Tarefa — Lote do Aceite 6 da Loja Teste + tag e deploy

> **Camada 4 · TRABALHO EM ANDAMENTO.** Documento de execução, descartável quando o lote fechar.
> Ver `docs/README.md` para as cinco camadas.

**Data:** 2026-09-17
**Origem:** Aceite 6 da Loja Teste, feito pelo Marcelo em Homologação em 16/09.
**Destino do lote:** desbloquear a tag e subir para Integração e Homologação tudo que está em
`main` desde `v2026.09.13-beta2` (Consertos 1, 2 e 3 desta semana).

## Regras deste lote

1. Vale tudo que está em `CLAUDE.md` — R1 a R16 em especial. Nenhum DDL fora de migração.
2. **Ancorar por nome**, nunca por número de linha. `static/index.html` tem 1.68 MB e as linhas
   andam a cada rodada.
3. **Não abrir achado novo.** Se encontrar algo, **reportar ao Marcelo** e seguir. Quem escreve
   em `docs/db/LISTA_PARALELA.md` é a Sessão B.
4. A suíte tem que ficar verde antes da tag — é a regra da `ESTEIRA.md`. Hoje ela tem 1 vermelho,
   que é a Tarefa 1 abaixo.
5. Deploy **por tag**, nunca `git pull`. `docs/db/IMPLANTAR.md` tem o roteiro e a lição de 13/09
   (`git status --short` vazio antes do checkout; conferir `git describe --tags` contra o alvo).

---

## Tarefa 1 — Destravar a suíte: a catraca de `showToast`

**Arquivo:** `tests/test_aceite_achado36.py`
**Teste:** `test_contagem_total_de_showtoast_de_erro_no_sistema`

Ele afirma `total == 143` sobre `static/index.html`. Os consertos desta semana (Fatia do
`Val_Liq_Portao`, tenancy do parceiro, unicidade de cliente por rede) acrescentaram sites de
toast, então a contagem subiu e o teste ficou vermelho.

**Não é defeito de comportamento — é catraca de contagem**, o mesmo padrão do LP-30. O conserto é:

1. Recontar com a mesma regex do teste (`showToast\([^;]*,\s*true\)`, que atravessa quebra de
   linha — `grep` linha a linha dá número diferente e errado).
2. Atualizar o número **e o docstring**, seguindo o padrão que já está lá: cada incremento
   histórico é justificado com data, origem e se é conversão ou site novo. Diga quais chamadas
   novas entraram e de qual conserto vieram. Sem isso o próximo que ver o teste vermelho não
   saberá se subiu por motivo legítimo.
3. Os outros dois testes do arquivo (`..._no_modulo_financeiro`, `..._na_faixa_do_ciclo`) devem
   continuar verdes — se algum ficar vermelho, aí **é** comportamento e o conserto é outro:
   reporte ao Marcelo antes de mexer.

**Aviso:** `FAIXAS_CICLO`, no mesmo arquivo, é uma lista de intervalos de linha absolutos. Se a
Tarefa 2 ou 3 deslocar linhas de `static/index.html`, esses intervalos precisam ser remedidos
**função por função** (o arquivo já registra que isso foi feito assim em 08/09), nunca chutados.

---

## Tarefa 2 — LP-32: o selo da loja no cabeçalho

**Achado do Marcelo (16/09):** "O nome da loja ficou muito pequeno e mal posicionado."

**Onde:** `static/index.html` — CSS `.tf-loja-nome` / `.tf-marca-loja`, marcação
`<span id="tf-loja-nome">` dentro de `.tf-marca`, preenchida pela função que escreve em
`tf-loja-nome`. Ao lado dela vive `#seletor-loja-wrap`, o seletor de loja de quem tem acesso a
mais de uma.

**O problema medido:** `.tf-loja-nome` está em `font-size:9.5px` com `color:var(--sidebar-text)`,
enquanto o wordmark ao lado está em 19px e cor de destaque. O nome da loja tem metade do tamanho
da marca e menos contraste — lê-se como legenda do logo, não como informação de contexto.

**Por que importa agora, e não é cosmético:** hoje existe uma loja de verdade. A partir de 01/10
serão cinco lojas-piloto, e quem atende mais de uma precisa saber em qual está **antes** de
aprovar um desconto ou assinar um contrato. O custo do erro é um ato gerencial praticado na loja
errada.

**Objetivo:** o nome da loja ativa passa a ser um **selo de contexto com peso próprio** — legível
num relance, visualmente separado da marca (não colado como subtítulo dela), e coerente com quem
também enxerga o seletor de loja ao lado.

**Restrições:**
- Nada de regressão de layout: a faixa de topo já passou por três rodadas de ajuste (ver os
  comentários datados de 2026-08-24 no CSS, que explicam por que marca e loja voltaram para a
  **mesma linha** e por que `overflow` foi removido dali). Leia esses comentários antes de mexer —
  eles registram o que já foi tentado e revertido.
- Tem que funcionar nos dois temas (Claro e Escuro) e continuar cortando com reticências em nome
  longo (`text-overflow:ellipsis`, `max-width`) — "Dalmóbile Casa Shopping" precisa caber.
- Usar token de cor de `orizon-tokens.css`. O hook de design falha em cor literal.

O desenho fino é seu. Se ficar em dúvida entre duas soluções, mande as duas ao Marcelo com
descrição curta — ele decide de olho, é decisão de negócio dele.

---

## Tarefa 3 — LP-33: a faixa sem teto e o rótulo que mente

Dois consertos no mesmo assunto. **Leia a regra dos irmãos (ACHADO-26) antes de começar: são
QUATRO pontos, não um.**

### 3a — O configurador aceita salvar sem faixa aberta

**Medido em 16/09:** `mod_provisoes.resolver_comissao_venda` usa `for/else` — venda acima de todas
as faixas não dá `break`, e o `else` aplica `faixas[-1]["pct"]`. **Não há buraco de comissão**: a
configuração atual (topo "venda até 300.000 = 6%") paga 6% numa venda de 400.000. O dinheiro está
certo hoje.

O defeito é de **verdade declarada**: a tela promete um teto que o motor não aplica. Quem
configura acredita ter limitado; quem vende recebe como se não houvesse limite. O default do
próprio sistema já tem a forma certa — `mod_provisoes.py`,
`"faixas_comissao": [{"venda_ate": None, "pct": 0.0}]`. É a UI que deixa quebrá-la.

**Conserto decidido pelo Marcelo (16/09):** a **última linha do configurador é sempre presente,
exige percentual e não permite editar o valor de venda** — ela é, por construção, a faixa sem
teto. Não dá para remover nem deixar em branco o percentual.

**E a garantia não pode viver só na tela:** `mod_provisoes.validar` ganha a regra correspondente
(última faixa com `venda_ate` nulo). Hoje ela só exige "ao menos uma faixa" e "cada faixa tem
pct" — uma configuração quebrada passa direto pela API.

### 3b — O rótulo "até" promete inclusão que o código não cumpre

A comparação é `val_liq_mes < ate`, estritamente menor: uma venda de **exatamente** R$ 100.000 não
entra na faixa rotulada "venda até 100.000", cai na seguinte.

**Decisão do Marcelo (16/09): o código está certo, muda o rótulo.** Nas palavras dele — *"as
vendas são 'abaixo de'; o valor colocado é a meta da faixa, atingiu, sobe de faixa."* O número
digitado é o alvo a **atingir**, e atingi-lo promove.

**Conserto:** a coluna passa de "Venda até (R$)" para **"Vendas abaixo de (R$)"**, com texto de
apoio dizendo que atingir o valor leva à faixa seguinte; a última linha (fixa, sem valor editável)
identifica-se como "acima da última meta". **Nenhuma mudança em `resolver_comissao_venda`.**

### 3c — Onde o conserto tem que valer (dois modelos de comissão, um defeito compartilhado)

**Leia isto antes de mexer, porque a primeira leitura deste código engana.** Não existem dois
configuradores da mesma coisa. Existe **um** configurador de remuneração por função,
`cfgRemuneracaoEditar` (`static/index.html`) — genérico, o mesmo para toda função — e dentro dele
o administrador escolhe o modelo:

- **Chave "Usa comissão de vendas por metas (motor da loja...)" LIGADA** → a função não configura
  faixa nenhuma própria; o modal só oferece o botão que abre `abrirModalComissao`, o **motor da
  loja** (`modal-comissao`: meta mensal + faixas + limitador de desconto por margem). Esse motor é
  **um só, por loja** — toda função que liga a chave aponta para o mesmo objeto, não para uma
  cópia. Resolvido por `mod_provisoes.resolver_comissao_venda`.
- **Chave DESLIGADA** → aparece o bloco simples: base (Líquido de Vendas / Custo Fábrica) e ou um
  % fixo, ou "comissão por meta" com faixas próprias daquela função (`_rmFaixas`, `_rmAddFaixa`,
  `_rmRenderFaixas`). Resolvido por `mod_folha._resolver_pct_funcao`.

Os dois modelos são **diferentes de propósito** e a diferença é decisão de negócio do Marcelo,
confirmada em 17/09: o motor da loja tem meta e redutor por margem, o modelo por função não tem.
**Não unifique os dois configuradores.** O histórico ajuda a entender por quê: o comentário de
2026-08-08 no código ("achado da Vera") registra que antes só a função de nome exato "Consultor de
Vendas" alcançava o motor da loja, e que a chave existe justamente para qualquer função poder
optar. Portanto o recorte real não é "consultor × os outros", é "quem usa o motor da loja × quem
tem comissão própria" — e isso é configuração, não código.

**O que É compartilhado, e por isso o conserto vale nos dois lados:** a forma do dado (`venda_ate`
+ `pct`, última aberta) e os dois defeitos em cima dela.

| | Motor da loja | Comissão própria da função |
|---|---|---|
| Configurador | `cvAdicionarFaixa` (`modal-comissao`) | `_rmAddFaixa` / `_rmRenderFaixas` |
| Resolvedor | `mod_provisoes.resolver_comissao_venda` | `mod_folha._resolver_pct_funcao` |
| Comparação estrita `<` | sim | sim |
| Escape para `faixas[-1]` | sim | sim |
| Validação no servidor | `mod_provisoes.validar` | **nenhuma** — `mod_cadastro` grava `comissao.faixas` sem conferir |

Ou seja: 3a e 3b valem para os dois configuradores e para os dois resolvedores, e o lado da função
precisa **ganhar** a validação que hoje não tem. Se ao medir você achar razão para algum dos dois
lados ficar de fora, **reporte ao Marcelo** em vez de decidir sozinho.

### 3d — Testes

Casos que precisam existir depois disto:
- Venda **acima** de todas as faixas → percentual da última (prova que o comportamento atual não
  regrediu).
- Venda **exatamente igual** a um `venda_ate` → faixa seguinte (prova a semântica "abaixo de",
  agora deliberada e não acidental).
- `validar` **recusa** configuração cuja última faixa tem `venda_ate` preenchido.
- O mesmo trio para o lado não-consultor (`_resolver_pct_funcao`), se 3c se confirmar.

---

## Tarefa 4 — Tag e deploy

Só depois das três anteriores, com a suíte inteira verde.

1. Suíte completa verde (0 vermelho; xfail conhecido pode ficar).
2. Cortar a tag seguindo `docs/db/ESTEIRA.md`. A anterior é `v2026.09.13-beta2`.
3. Subir em **Integração** (`orizon-a`, porta 8765, `/root/orizon-manager`), conferir, e só então
   **Homologação** (`orizon-b`, porta 8766, `/root/orizon-homolog`).
4. Em cada uma: `git status --short` vazio ANTES do checkout, `git describe --tags` conferido
   contra o alvo DEPOIS, `bash docs/db/confirmar.sh`, e `sleep` antes do primeiro `curl` (o
   serviço demora a subir; `curl` retornando `000` é boot, não falha).

**Cuidado que já custou caro (13/09):** arquivo não rastreado (`??`) que também existe no commit
alvo faz o `git checkout <tag>` **abortar**. O resto do bloco então roda contra o código velho e o
`confirmar.sh` reporta tudo OK sobre o schema errado. Por isso o `git status --short` vazio é
pré-condição, não formalidade.

---

## O que entra nesta tag (para a mensagem de tag)

- Conserto 1 — `Val_Liq_Portao`: os portões de autorização passam a ler o líquido sem
  viagem/brinde/custo especial; a perda real continua no `Val_Liq` verdadeiro (ADR-005).
- Conserto 2 — tenancy do parceiro: `master` entra na condição de `_aplicar_abrangencia_parceiro`,
  como a especificação de 21/06 já dizia.
- Conserto 3 — unicidade de cliente por rede: cadastro compartilhado dentro da rede, histórico
  comercial isolado sempre (ADR-028).
- Este lote — LP-32 e LP-33.
