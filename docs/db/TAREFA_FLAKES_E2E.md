# TAREFA — Flakes de E2E de navegador: a rodada de medição (13/09/2026)

Pedido do Marcelo, depois de fechar o ACHADO-69: os onze arquivos de E2E de navegador
registrados como flakes **não explicados** na RODADA3 (`docs/db/TAREFA_ESTABILIDADE_RODADA3.md`)
ganham rodada própria. **Tarefa de medir, não de consertar** — nenhuma asserção muda, nenhum
teste sai do `pytest -q`, nada de código de negócio/tela/Produção/tag/deploy, nada commitado.

Bancos `orizon_test`/`orizon_e2e` recriados do zero antes de começar (drop+create, autorizado e
executado pelo Marcelo — sudo não aceitava autenticação não-interativa neste ambiente).

---

## O que já estava medido antes desta rodada (RODADA3, não re-medir)

- **Achado 1**: o conjunto de testes que falha muda entre execuções — duas rodadas completas no
  mesmo código tiveram falhas quase sem sobreposição.
- **Achado 2, fechado**: o método `'signal'` do `pytest-timeout` corrompe o laço de despacho
  greenlet do Playwright quando o alarme cai dentro dele — corrigido forçando `method='thread'`
  para testes com fixture `page`/`context`/`browser` (`tests/conftest.py`). Eliminou a categoria
  "teste de 5 minutos" inteira (zero `+++ Timeout +++` em 3 execuções overnight de 12→13/09).
  **O que sobrou depois disso é o objeto desta rodada**: falhas normais (não travamentos) só em
  E2E de navegador, onze arquivos, nenhum determinístico (inclusive o que antes parecia ser).
- **Hipótese derrubada (13/09, antes desta tarefa)**: os tempos fixos de espera do Playwright
  (`#neg-subtotal`) não perdem margem sob carga da suíte — isolado 783,0ms, sob carga 780,9 a
  784,8ms. Mesmo número. Não é timing.
- **Achado 3 (RODADA3)**: recriar os bancos consertou parte das falhas anteriores (achado18,
  achado35), não a família de E2E.
- **Hipótese em aberto, com evidência forte mas não provada (RODADA3, Passo 1 nunca executado)**:
  colisão de schema entre módulos num banco único — o `_reset_schema_pg` (`orizon_test`) e o
  `_e2e_bootstrap.py` (`orizon_e2e`) já tentam se defender disso (`pg_terminate_backend` antes do
  `DROP SCHEMA`), mas ninguém mediu se essa defesa é suficiente. Esta rodada tenta olhar para essa
  hipótese de um ângulo diferente (medição passiva de `pg_stat_activity`, ver seção própria abaixo)
  sem repetir o Passo 1 exatamente como escrito lá (que instrumentaria `_reset_schema_pg` e
  `_e2e_bootstrap.py` diretamente — não fiz isso aqui para não me aproximar de "consertar" antes
  de terminar de medir; ficou como sugestão de próximo passo se esta rodada não bastar).

## Fatos estruturais confirmados nesta rodada (antes de rodar qualquer suíte)

1. **Sem plugin de ordenação.** `pip list` não mostra `pytest-randomly`, `pytest-order` nem
   `pytest-xdist`. `pytest --collect-only` produziu a MESMA ordem em duas execuções
   independentes (diff vazio). **A ordem de coleta é determinística** — segue a ordem de
   descoberta de arquivo (alfabética) e depois a ordem de definição dentro do arquivo.
2. **Sem paralelismo.** Sem `pytest-xdist`, a suíte roda inteira num processo só, sequencial.
   Descarta contenção entre workers como causa.
3. **Correção do próprio inventário, no meio desta rodada**: a população de testes com navegador
   NÃO é só os arquivos nomeados `test_e2e_browser_*.py`. `grep -l "def servidor_e2e" tests/*.py`
   devolve **31 arquivos** — inclui `test_aceite_achado36/38/40/_c6.py`,
   `test_aceite_b6_fila_tooltips.py`, `test_achado43/49/53/54/57/59_*.py`,
   `test_achado_c4_reaprovar_af_silenciosa.py` e `test_f2_43_avista_concorda_apos_preview.py` —
   nenhum com "e2e_browser" no nome, todos com fixture `page`/`browser` e `[chromium]` na
   parametrização. Isso importa porque um dos 15 testes que falharam nesta rodada
   (`test_f2_43_avista_concorda_apos_preview.py`) é exatamente um desses "fora do nome" — contar
   só pelo nome do arquivo teria deixado ele de fora da população certa. **Todos os 31 são
   estruturalmente ISOLADOS do resto da suíte**: nenhum usa `app_db`/`seed` de
   `tests/conftest.py` num teste com navegador — a única exceção parcial é `test_aceite_achado38.py`,
   que tem UM teste HTTP comum (`app_db`/`seed`) e UM teste de navegador (`servidor_e2e`) no MESMO
   arquivo (mesmo módulo) — acoplamento que existe, mas não apareceu entre as 15 falhas desta
   rodada, então fica registrado como estrutura, não como causa medida.
   Cada arquivo declara sua PRÓPRIA fixture `servidor_e2e` (`scope="module"`), que roda
   `tests/_e2e_bootstrap.py` como subprocesso (mata outras conexões do banco, `DROP SCHEMA
   CASCADE`, `CREATE SCHEMA`, `init_db()`, semeia `Usuario(login="e2e_master")` +
   `Cliente(nome="Cliente E2E")`) e sobe `main.py` como subprocesso próprio numa porta livre.
4. **O que os 31 compartilham, de fato**: só o banco físico `orizon_e2e` — cada arquivo o
   redesenha inteiro (schema dropado e recriado) na sua própria vez, e essa recriação mata
   qualquer conexão de terceiro do mesmo role antes de dropar. `PROJETOS_DIR` no disco também é
   compartilhado, mas só `E2E_Cozinha_Playwright*` é limpo pelo bootstrap (hardcoded) — os outros
   arquivos deixam diretório próprio para trás a cada rodada; é lixo que cresce (sufixo `_N` só
   sobe), não uma fonte de falha (o banco é recriado do zero, então nunca há registro apontando
   pra um diretório de rodada anterior).
5. **Nem todo arquivo da população de 31 falhou nestas 8 rodadas** — arquivos como
   `test_e2e_browser_conciliacao_final.py`, `_conciliacao_ui.py`, `_f2_33_...py`, `_f2_39_...py`,
   `_f2_40_fatia3_...py` e `_paineis_identificam_projeto.py`, e TODOS os 12 arquivos "fora do
   nome" listados no item 3 exceto o `f2_43`, ficaram limpos nas 8 rodadas — mesmo intercalados na
   ordem de coleta com arquivos que falharam. Isso pesa contra uma explicação "toda fronteira
   entre módulos de E2E tem a mesma chance de falhar" — se fosse só isso, a distribuição de falhas
   deveria ser mais uniforme entre vizinhos de coleta, não concentrada nalguns arquivos específicos
   (ver a tabela de frequência abaixo).

---

## Rodadas completas (frequência)

Oito rodadas (o máximo que coube — cada uma leva 10 a 19 minutos; ver `/tmp/.../flakes_rodada/
run_N.log` para o log bruto de cada uma, fora do repositório, session-local, não commitado).

| rodada | duração | passed | failed | xfailed | arquivos distintos com falha |
|---|---|---|---|---|---|
| 1 | 10m28s | 2799 | 0 | 4 | 0 |
| 2 | 12m02s | 2799 | 0 | 4 | 0 |
| 3 | 18m43s | 2793 | 6 | 4 | 6 |
| 4 | 18m49s | 2793 | 6 | 4 | 6 |
| 5 | 19m07s | 2790 | 9 | 4 | 8 |
| 6 | 18m51s | 2793 | 6 | 4 | 6 |
| 7 | 18m35s | 2797 | 2 | 4 | 2 |
| 8 | 18m57s | 2793 | 6 | 4 | 6 |

**Achado 1 da RODADA3 confirmado de novo, com números novos**: duas rodadas (1 e 2) saíram
**totalmente verdes** — zero falha, todos os 2799 testes — e as outras seis tiveram entre 2 e 9
falhas, sempre só em testes de navegador (nunca backend). O total de falhas nas 8 rodadas foi
**41 ocorrências, em 15 testes distintos de 9 arquivos distintos**. `+++ Timeout +++`: zero nas
8 (`grep -c` confirmado em cada log) — o conserto da RODADA3(b) continua de pé, nada regrediu.

Nota sobre duração: as duas rodadas limpas (1, 2) também foram as mais RÁPIDAS (10-12min); as
seis com falha levaram 18-19min — falha em teste de navegador custa tempo (retries do
Playwright, timeouts de 10s por seletor) mesmo sem travar o processo inteiro.

**Observação do Marcelo, depois de ver esta tabela — falhas e duração sobem JUNTAS e
MONOTONICAMENTE (0→0→6→6→9, 628s→722s→1123s...), o que aponta para acúmulo de estado nos bancos
entre execuções, não aleatoriedade pura.** Essa hipótese é DIFERENTE da que a Isolação (seção
abaixo) testa — a Isolação reseta só o SCHEMA (`DROP SCHEMA`/`CREATE SCHEMA`, o que
`_e2e_bootstrap.py` já fazia entre uma rodada e outra dentro do MESMO banco de longa duração);
a hipótese do Marcelo é sobre o BANCO em si (bloat de catálogo, sequências, o que só um `DROP
DATABASE`/`CREATE DATABASE` de verdade limparia). Ver `## Experimento 2` abaixo — quatro rodadas
adicionais, banco recriado do zero (`DROP DATABASE` + `CREATE DATABASE`, sem sudo, `orizon` tem
`CREATEDB`) antes de cada uma.

### Tabela de frequência por teste

| arquivo | teste | rodadas em que falhou | de 8 |
|---|---|---|---|
| `test_e2e_browser_remover_ciclo.py` | `test_remover_nfe_fabrica_em_erro_funciona_no_clique_real` | 3,4,5,6,8 | **5** |
| `test_e2e_browser_f2_40_fatia2_modal_complemento.py` | `test_f2_42_c4_salvar_volta_pra_11e_e_c5_botao_pagamento_nao_desaparece` | 3,4,6,7,8 | **5** |
| `test_f2_43_avista_concorda_apos_preview.py` | `test_avista_concorda_com_neg_avista_apos_preview_mesmo_envenenada` | 4,5,6 | 3 |
| `test_e2e_browser_f2_38_zero_aceito.py` | `test_digitar_zero_zera_o_item_especial` | 4,5,8 | 3 |
| `test_e2e_browser_f2_37_linha_item_especial.py` | `test_linha_item_especial_aparece_some_e_nao_duplica_o_total` | 5,6,8 | 3 |
| `test_e2e_browser_ciclo_overlay.py` | `test_ciclo_aberto_esconde_a_negociacao_por_baixo` | 3,4,7 | 3 |
| `test_e2e_browser_negociacao_layout.py` | `test_plano_15_parcelas_nao_colapsa_card_de_ambientes` | 3,5 | 2 |
| `test_e2e_browser_f2_40_fatia1_botao_11e.py` | `test_botao_negociar_complemento_vive_no_card_de_aprovacao_no_11e` | 4,5 | 2 |
| `test_e2e_browser_achado65_item_especial.py` | `test_item_especial_botao_soma_no_bruto_e_no_total_e_campo_do_modal_vira_leitura` | 3,5 | 2 |
| `test_e2e_browser_achado64_total_contrato.py` | `test_digitar_total_do_contrato_visivel_muda_o_desconto` | 3,8 | 2 |
| `test_e2e_browser_termo_aditivo_clicksign.py` | `test_termo_aditivo_11e_oferece_as_duas_opcoes_de_canal` | 8 | 1 |
| `test_e2e_browser_remover_ciclo.py` | `test_remover_etapa12_funciona_no_clique_real` | 5 | 1 |
| `test_e2e_browser_f2_41_apoio_dev.py` | `test_apoio_dev_escondido_por_padrao_e_visivel_com_data_apoio_on` | 6 | 1 |
| `test_e2e_browser_f2_40_fatia2_modal_complemento.py` | `test_modal_complemento_desc_pct_totais_e_travamento_por_pagamento` | 5 | 1 |
| `test_e2e_browser_f2_38_zero_aceito.py` | `test_apagar_o_campo_e_salvar_tambem_zera_o_item_especial` | 6 | 1 |

**Nenhum teste caiu em 6 de 8 ou mais** — os dois piores (remover_ciclo/nfe_fabrica e
f2_40_fatia2/c4_salvar) empatam em 5 de 8 (62,5%). Isso já responde uma pergunta que o pedido
desta tarefa fez em aberto: "um teste que cai em 1 de 8 é um problema diferente de um que cai em
6 de 8" — aqui não existe nenhum de 6/8; a distribuição vai de 1/8 a 5/8, sem um caso dominante
isolado. É uma família de flakes com intensidades DIFERENTES, não um flake principal com ruído
ao redor.

---

## Isolamento

Os 15 testes da tabela, cada um rodado sozinho 10× (`python3 -m pytest -q <nodeid>`, sem tocar
mais nada). Cada invocação passa pelo MESMO `servidor_e2e`/`_e2e_bootstrap.py` de sempre — schema
dropado e recriado a cada uma — mas dentro do banco de longa duração (não recriado a nível de
`CREATE DATABASE` entre uma rodada de isolamento e a próxima; isso só entrou no Experimento 2,
pedido depois de ver este resultado).

| # | teste | falhas / 10 |
|---|---|---|
| 1 | `test_e2e_browser_achado64_total_contrato.py::test_digitar_total_do_contrato_visivel_muda_o_desconto` | 3 |
| 2 | `test_e2e_browser_achado65_item_especial.py::test_item_especial_botao_soma_no_bruto_e_no_total_e_campo_do_modal_vira_leitura` | 1 |
| 3 | `test_e2e_browser_ciclo_overlay.py::test_ciclo_aberto_esconde_a_negociacao_por_baixo` | 3 |
| 4 | `test_e2e_browser_f2_37_linha_item_especial.py::test_linha_item_especial_aparece_some_e_nao_duplica_o_total` | 4 |
| 5 | `test_e2e_browser_f2_38_zero_aceito.py::test_apagar_o_campo_e_salvar_tambem_zera_o_item_especial` | 3 |
| 6 | `test_e2e_browser_f2_38_zero_aceito.py::test_digitar_zero_zera_o_item_especial` | 5 |
| 7 | `test_e2e_browser_f2_40_fatia1_botao_11e.py::test_botao_negociar_complemento_vive_no_card_de_aprovacao_no_11e` | 2 |
| 8 | `test_e2e_browser_f2_40_fatia2_modal_complemento.py::test_f2_42_c4_salvar_volta_pra_11e_e_c5_botao_pagamento_nao_desaparece` | 5 |
| 9 | `test_e2e_browser_f2_40_fatia2_modal_complemento.py::test_modal_complemento_desc_pct_totais_e_travamento_por_pagamento` | 2 |
| 10 | `test_e2e_browser_f2_41_apoio_dev.py::test_apoio_dev_escondido_por_padrao_e_visivel_com_data_apoio_on` | 2 |
| 11 | `test_e2e_browser_negociacao_layout.py::test_plano_15_parcelas_nao_colapsa_card_de_ambientes` | 5 |
| 12 | `test_e2e_browser_remover_ciclo.py::test_remover_etapa12_funciona_no_clique_real` | 4 |
| 13 | `test_e2e_browser_remover_ciclo.py::test_remover_nfe_fabrica_em_erro_funciona_no_clique_real` | 3 |
| 14 | `test_e2e_browser_termo_aditivo_clicksign.py::test_termo_aditivo_11e_oferece_as_duas_opcoes_de_canal` | 2 |
| **15** | `test_f2_43_avista_concorda_apos_preview.py::test_avista_concorda_com_neg_avista_apos_preview_mesmo_envenenada` | **10** |

**Achado central desta seção: NENHUM dos 15 testes é limpo quando rodado sozinho.** Isso muda a
pergunta que a tarefa pediu para responder ("se passar 10 de 10 sozinho e cair na suíte, a causa
é de contexto"): não é o caso aqui — todos os 15 falham também isolados, em taxas que vão de
1/10 a **10/10**. A causa NÃO é (só) contaminação entre módulos da suíte — pelo menos parte dela
é intrínseca ao teste/app, reproduzível sem suíte nenhuma ao redor.

**O caso 15 é o mais importante e o mais contraintuitivo: falha 10 de 10 isolado, mas só 3 de 8
na suíte completa (rodadas 4, 5, 6 — passou nas outras cinco).** Isto é o OPOSTO do padrão que
contaminação entre testes prevê (que seria: mais confiável isolado, menos confiável na suíte). Um
teste que FALHA MAIS quando está sozinho do que quando embutido numa suíte de 40 minutos sugere
que **alguma coisa no contexto da suíte longa ajuda esse teste a passar** — não o contrário. Não
investiguei o que seria essa coisa (fronteira: medir, não consertar) — fica como o achado mais
específico e mais estranho desta rodada.

**O ponto de falha mais comum, contado nos 47 logs de falha isolada, não é o `#neg-subtotal` que
a RODADA3 já tinha medido — é um ANTERIOR:**

| seletor onde travou | ocorrências |
|---|---|
| `#np-cli-dropdown div` (dropdown de autocomplete do cliente, na criação do projeto) | **27** |
| `#neg-subtotal:has-text('140.000,00')` | 10 |
| `#neg-subtotal:has-text('100.000,00')` | 10 |

`#np-cli-dropdown` é preenchido por `npBuscarCliente()` (`static/index.html`): `oninput` (evento
que `page.fill()` do Playwright dispara corretamente) → debounce de **300ms** → `fetch('/api/
clientes?q=...')` → renderiza a lista. Contra um timeout de 10000ms, 300ms + uma chamada HTTP
deveria sobrar folga enorme — **medido, não explicado**: não investiguei POR QUE esse round-trip
ocasionalmente estoura 10s (seria consertar, não medir); fica registrado como o ponto de entrada
mais provável para quem pegar a causa raiz, na frente do `#neg-subtotal` que a RODADA3 já tinha
olhado.

**Atualização — 14/09/2026 (PLANO_SEMANA_1.md, item 1 da fila de beta): causa confirmada e
corrigida.** Medi a latência do backend direto (`GET /api/clientes?q=Cliente`, curl autenticado,
processo `main.py` novo em porta descartável): 4-10ms, incluindo a PRIMEIRA requisição (fria) —
descarta backend lento. Rodei os testes afetados isolados, várias vezes, máquina ociosa, banco
recriado — reproduzi a falha (ex.: `test_e2e_browser_ciclo_overlay.py`, 1/8). **Veredicto: defeito
de teste, não de produto.** A causa não é o backend estourar 10s — é o padrão dos 11 arquivos
afetados (`page.fill("#novo-proj-cli", ...)` seguido direto de
`page.wait_for_selector("#np-cli-dropdown div")`) correr contra o debounce de 300ms como uma
corrida IMPLÍCITA: `page.fill()` volta assim que o evento `oninput` dispara, MAS o fetch só
começa 300ms depois (dentro do `setTimeout` de `npBuscarCliente`) — o teste está torcendo pra
essa janela nunca coincidir com uma pausa do event loop do Chromium sob carga, em vez de esperar
o sinal de verdade. **Conserto:** os 11 arquivos passam a envolver o `page.fill()` num
`page.expect_response(lambda r: "/api/clientes" in r.url and "q=" in r.url)` — espera a RESPOSTA
da rede antes de seguir pro dropdown, não mais um cronômetro implícito. 10/10 rodadas limpas em
`test_e2e_browser_ciclo_overlay.py` depois do conserto (vs. 1 falha em 8 antes). A família de 47
falhas isoladas encolhe: os 27 do `#np-cli-dropdown` saem com causa nomeada e resolvida: sobram os
20 do `#neg-subtotal` (já investigado pela RODADA3) mais o que outras rodadas ainda encontrarem —
ver o LP correspondente em `LISTA_PARALELA.md` § INFRA. Achado colateral, NÃO relacionado a este
flake (o backend local é rápido demais pra exercitar este caminho): `npBuscarCliente()` tem
`catch(e){}` vazio — um erro de rede de verdade (produção, contra um backend lento ou fora do ar)
falharia em silêncio, sem aviso nenhum ao usuário. Genuíno, mas separado; não registrado como
achado de produto aqui porque não é o que causa ESTE flake.

---

## Ordem — pares predecessor/sucessor

Ordem determinística confirmada (seção de fatos estruturais) — o predecessor de cada um dos 15,
lido direto de `pytest --collect-only`:

| teste | predecessor imediato na coleta |
|---|---|
| `achado64_total_contrato::test_digitar_total...` | `achado62_recusa_reducao::test_percurso_3000_4000_2000...` |
| `achado65_item_especial::test_item_especial_botao...` | `achado64_total_contrato::test_digitar_total...` |
| `ciclo_overlay::test_ciclo_aberto_esconde...` | `achado65_item_especial::test_item_especial_botao...` |
| `f2_37_linha_item_especial::test_linha_item...` | `f2_33_caixa_limite_desconto::test_limite_de_desconto...` |
| `f2_38_zero_aceito::test_digitar_zero...` | `f2_37_linha_item_especial::test_linha_item...` |
| `f2_38_zero_aceito::test_apagar_o_campo...` | `f2_38_zero_aceito::test_digitar_zero...` (mesmo arquivo) |
| `f2_40_fatia1::test_botao_negociar...` | `f2_39_af_mascara_e_item_especial::test_mascara_financeira...` |
| `f2_40_fatia2::test_modal_complemento_desc_pct...` | `f2_40_fatia1::test_botao_negociar...` |
| `f2_40_fatia2::test_f2_42_c4_salvar...` | `f2_40_fatia2::test_modal_complemento_desc_pct...` (mesmo arquivo) |
| `f2_41_apoio_dev::test_apoio_dev_escondido...` | `f2_40_fatia3_af_oculta::test_af1_af2_somem...` |
| `negociacao_layout::test_plano_15_parcelas...` | `f2_41_apoio_dev::test_apoio_dev_escondido...` |
| `remover_ciclo::test_remover_etapa12...` | `paineis_identificam_projeto::test_provisoes_af_identifica...` |
| `remover_ciclo::test_remover_nfe_fabrica...` | `remover_ciclo::test_remover_etapa12...` (mesmo arquivo) |
| `termo_aditivo_clicksign::test_termo_aditivo_11e...` | `remover_ciclo::test_remover_nfe_fabrica...` |
| `f2_43_avista_concorda::test_avista_concorda...` | `termo_aditivo_clicksign::test_termo_aditivo_11e...` |

**Achado que muda o peso deste experimento**: como a seção de Isolamento provou que os 15 já
falham sozinhos (nenhum em 0/10), um par "predecessor+teste" que reproduzir a falha não prova
"é o predecessor" — o teste já falhava sem ele. Um par só seria evidência útil onde o teste
isolado tem taxa BAIXA e o par sobe muito essa taxa. Não rodei a bateria de pares (seria mais
uma bateria de ~150 execuções, e o Experimento 2 do Marcelo tomou a prioridade de tempo depois
da tabela de frequência) — registrado como **não medido nesta rodada**, não como negativo. Se
alguém retomar: os candidatos mais informativos são os de taxa isolada baixa — `achado65` (1/10),
e os de 2/10 (`f2_40_fatia1`, `f2_40_fatia2/desc_pct`, `f2_41_apoio_dev`,
`termo_aditivo_clicksign`) — um salto desses para perto de 8-10/10 quando pareados com o
predecessor real seria o sinal que valeria a pena perseguir.

Uma observação estrutural que a própria tabela já entrega, sem rodar nada: **cinco dos quinze
predecessores são o OUTRO teste que falha, do MESMO arquivo** (`f2_38`, `f2_40_fatia2`,
`remover_ciclo` aparecem como seu próprio predecessor). Isso é esperado (arquivos com mais de um
teste falho têm os dois um do lado do outro na coleta) e não distingue "efeito do vizinho" de
"o arquivo inteiro é frágil" — mais um motivo para não superinterpretar um "par reproduziu" sem
comparar contra a taxa isolada de cada um sozinho.

---

## `pg_stat_activity` — observação passiva durante as 8 rodadas

Um watcher externo (fora dos testes, só leitura) amostrou `pg_stat_activity` em `orizon_test` e
`orizon_e2e` a cada ~1s durante as 8 rodadas do Experimento 1, sem instrumentar nenhum código do
projeto. Não é o Passo 1 da RODADA3 (que instrumentaria `_reset_schema_pg`/`_e2e_bootstrap.py`
diretamente e travaria a granularidade no exato momento do DDL) — é uma amostragem de fora, mais
grosseira, pensada para não exigir nenhuma mudança de código enquanto essa rodada é só de medição.
16.015 amostras coletadas; `orizon_e2e` concentrou 61% delas (9.327) contra 39% de `orizon_test`
(5.971) — consistente com os testes de navegador dominando o tempo de execução da suíte.

**Achado corroborante para a hipótese do Marcelo (registrado ANTES de ele formulá-la —
coletado durante o Experimento 1, analisado depois):** a fração de amostras capturadas em
`idle in transaction` sobe de forma monotônica ao longo das 8 rodadas, na MESMA direção que
falhas e duração:

| rodada | amostras | `idle in transaction` | % |
|---|---|---|---|
| 1 | 1025 | 211 | 20,6% |
| 2 | 1461 | 300 | 20,5% |
| 3 | 2140 | 525 | 24,5% |
| 4 | 2163 | 528 | 24,4% |
| 5 | 2158 | 528 | 24,5% |
| 6 | 2168 | 565 | 26,1% |
| 7 | 2071 | 545 | 26,3% |
| 8 | 2111 | 561 | 26,6% |

Sobe de 20,5% para 26,6% — não é grande, mas é **consistentemente crescente, nunca cai**, nas 8
rodadas. Isso é uma amostragem de PONTOS no tempo (não mede duração de transação individual
diretamente) — o número sobe tanto porque cada transação individual pode estar demorando mais
(consistente com "banco mais pesado, consultas mais lentas") quanto porque há mais transações
concorrentes por segundo (mais retries de Playwright acontecendo). As duas explicações apontam
pra a mesma direção da hipótese do Marcelo (o banco de longa duração fica mais pesado com o
tempo) — **corroborante, não prova**: não isola qual das duas é a causa dominante, e essas 8
rodadas rodaram TODAS contra os mesmos dois bancos criados uma única vez antes da rodada 1 (nunca
recriados entre rodadas) — exatamente o cenário que o Experimento 2 agora testa de propósito.

Também observado, sem conseguir ligar a uma falha específica: picos pontuais de até 10 conexões
simultâneas em `orizon_e2e` e cadeias de até ~30 amostras consecutivas (~30s) de UM MESMO pid em
`idle in transaction` em `orizon_test` — nenhuma delas correlacionada, neste nível de granularidade
de 1s sem nodeid por teste, a um `FAILED` específico dos logs. Ficam registradas como textura do
ambiente, não como causa localizada.

---

## Experimento 2 (pedido do Marcelo, 13-14/09) — o banco recriado do zero é a causa?

Hipótese: falhas e duração do Experimento 1 sobem juntas e monotonicamente (rodadas 1-2 limpas e
rápidas, 3-8 com falha e mais lentas) porque o banco de teste **não volta ao estado inicial**
entre rodadas — `_reset_schema_pg`/`_e2e_bootstrap.py` fazem `DROP SCHEMA`/`CREATE SCHEMA`, não
`DROP DATABASE`/`CREATE DATABASE`, e algo no nível do BANCO (não do schema) acumula. Casa com
13/09: recriar os bancos (`DROP DATABASE`+`CREATE DATABASE`) consertou `test_aceite_achado18` e
`test_aceite_achado35` de uma vez.

**Desenho do experimento**: quatro rodadas completas (`pytest -q`), cada uma precedida por
`DROP DATABASE`/`CREATE DATABASE` de `orizon_test` E `orizon_e2e` (o papel `orizon` ganhou
`CREATEDB` — confirmado, `SELECT rolcreatedb FROM pg_roles` devolve `t` — então isso roda sem
sudo, diferente da recriação do início desta tarefa).

| rodada | banco recriado? | duração | resultado |
|---|---|---|---|
| 1 | sim | 622,5s | **limpa** — 2799 passed, 0 failed, 4 xfailed |
| 2 | sim | ~1min até travar | **`+++ Timeout +++`** — `test_e2e_browser_f2_40_fatia2_modal_complemento.py::test_modal_complemento_desc_pct_totais_e_travamento_por_pagamento` travou dentro de um `wait_for_selector` do Playwright, estourou os 300s do `pytest-timeout` (método `thread`), o processo terminou sozinho via `os._exit` (o comportamento CORRETO desenhado na RODADA3(b) — nunca mais 12h penduradas). `pytest -q` abortou cedo, log truncado, sem sumário final |
| 3 | sim | 620,8s | **limpa** — 2799 passed, 0 failed, 4 xfailed |
| 4 | sim | 622,9s | **limpa** — 2799 passed, 0 failed, 4 xfailed |

**Leitura, e ela não é nem "confirmada" nem "derrubada" — é as duas coisas, em pontas
diferentes da hipótese:**

**A favor da hipótese (duração):** as três rodadas que completaram ficaram todas em 620-623s —
**achatado, sem crescimento nenhum**, contra o 628s→1137s do Experimento 1 (banco nunca recriado
entre rodadas). Isso é o resultado mais limpo desta tarefa inteira a favor de "o banco de longa
duração fica mais pesado com o tempo, e isso é visível no relógio": recriar o banco a cada rodada
manteve a duração plana nas três vezes em que a suíte chegou ao fim.

**Contra a hipótese, ou pelo menos incompleta (o travamento da rodada 2):** um `+++ Timeout +++`
de verdade — a categoria que a RODADA3(b) tinha ELIMINADO (zero ocorrências em 3 execuções
overnight de 12→13/09 E nas 8 rodadas do Experimento 1) — apareceu logo na SEGUNDA rodada com
banco **recém-criado**, tão limpo quanto um banco pode estar. Se a causa fosse só acúmulo de
estado no banco de longa duração, um banco criado há menos de um minuto não deveria produzir o
sintoma mais severo já visto nesta investigação inteira. **Isso não derruba a hipótese da
duração** (as três rodadas limpas continuam achatadas) — mas prova que existe pelo menos uma
segunda causa, capaz de travar um teste por 300s inteiros, que recriar o banco não elimina.

**O que isto muda na pergunta original**: a hipótese do Marcelo explica bem a parte "por que as
rodadas 3-8 do Experimento 1 foram mais LENTAS" — três rodadas limpas consecutivas com duração
idêntica é evidência forte. Não explica (nem tenta explicar) as FALHAS suaves de seletor (10s,
a maioria desta tarefa) nem o travamento de 300s da rodada 2 — ambas apareceram com bancos tanto
velhos (Experimento 1) quanto novos em folha (Experimento 2, rodada 2). São, no mínimo, DUAS
famílias de sintoma que compartilham a mesma superfície (testes de navegador, seletor
`wait_for_selector`) mas não necessariamente a mesma causa.

---

## Conclusão

**Não existe reprodução controlada de UMA causa única — existem pelo menos duas famílias de
sintoma medidas, distintas, e uma terceira hipótese confirmada só em parte.** Isto é resultado,
não fracasso: doze rodadas completas de suíte (8 + 4), 150 execuções isoladas e uma amostragem
contínua de `pg_stat_activity` depois, a família de flakes de E2E de navegador tem contorno mais
claro do que tinha ontem, mas não tem UMA causa raiz só.

**O que ficou medido, com confiança:**

1. **A categoria "trava a suíte inteira" (RODADA3(b)) continua consertada, com uma exceção
   pontual.** Zero `+++ Timeout +++` nas 8 rodadas do Experimento 1; UM apareceu no Experimento 2
   (rodada 2, banco recém-criado) — mas terminou o processo sozinho em segundos, como desenhado,
   nunca pendurou. O conserto de 12/09 continua fazendo o que foi feito para fazer.
2. **As falhas "normais" (seletor de 10s) são intrínsecas ao teste/app, não só de contexto de
   suíte.** Os 15 testes que falharam nas 8 rodadas do Experimento 1 falharam TODOS também
   sozinhos (0/15 limpos em isolamento), em taxas de 1/10 a 10/10. Contaminação entre módulos
   pode ser um fator agravante, mas não é a única explicação nem a explicação principal — se
   fosse só isso, isolar deveria ter zerado a taxa de falha, e não zerou em nenhum dos 15 casos.
3. **O ponto de falha isolado mais comum é o dropdown de busca de cliente
   (`#np-cli-dropdown`, 27 de 47 falhas), não o `#neg-subtotal` que a RODADA3 tinha medido.**
   `npBuscarCliente()`: debounce de 300ms + uma chamada `/api/clientes?q=...`. Contra um timeout
   de 10s, a folga deveria ser grande — medido que não é suficiente algumas vezes, não medido
   por quê.
4. **A duração da suíte cresce quando o banco de teste não é recriado entre rodadas, e some
   quando é.** Experimento 1 (banco fixo): 628s→1137s, crescendo. Experimento 2 (banco recriado
   a cada rodada): 620-623s nas três que completaram, achatado. Esta é a medição mais limpa desta
   tarefa inteira, e é OPERACIONALIZÁVEL: o conserto desenhado pelo Marcelo (a suíte recriar os
   dois bancos numa fixture de sessão, no início de cada `pytest -q`) tem evidência de sobra a
   favor da parte de DURAÇÃO — **não implementado, por instrução explícita; só medido.**
5. **Essa mesma recriação não protege contra o travamento de 300s** — apareceu com banco
   novo em folha, no Experimento 2. O acúmulo de estado no banco (Achado 4) e o que trava
   testes por 300s inteiros (Achado 1/RODADA3) parecem ser causas DIFERENTES compartilhando a
   mesma superfície de sintoma.
6. **Um achado sem explicação, mais estranho que os outros**: um teste
   (`test_f2_43_avista_concorda_apos_preview.py`) falha 10 de 10 vezes sozinho e só 3 de 8 vezes
   dentro da suíte completa — o oposto do padrão que contaminação prevê. Não investigado por que.
7. **Sem plugin de ordenação — a ordem de execução é determinística.** Isso tornou possível
   mapear o predecessor de cada teste, mas como nenhum dos 15 é limpo isolado, um par que
   "reproduzir" a falha não distingue predecessor de fragilidade própria — bateria de pares não
   rodada, registrada como não medida (não como negativa).

**O que muda para a próxima pessoa que pegar isto:**

- A RODADA3 (Passo 1, instrumentar `_reset_schema_pg`/`_e2e_bootstrap.py` para logar
  `pg_stat_activity` no exato momento do DDL) continua não feita — esta tarefa mediu de fora
  (amostragem passiva de 1s), não de dentro. Achado 4 acima já dá motivo concreto pra fazer o
  Passo 1 de verdade, mirado na hipótese "acúmulo no banco", que agora tem números a favor.
- O travamento de 300s do Experimento 2 merece olhar de novo com atenção — é raro (1 em 12
  rodadas completas), mas é a categoria mais cara (custa a rodada inteira) e apareceu justamente
  onde a hipótese principal previa que não devia.
- `#np-cli-dropdown`/`npBuscarCliente()` é, por contagem bruta, o ponto de entrada mais
  produtivo para investigar a seguir — mais failures batem ali do que em qualquer outro seletor,
  incluindo o que a RODADA3 já tinha olhado.

**Nada foi consertado.** Nenhuma asserção mudou, nenhum teste saiu do `pytest -q`, nada de
código de negócio/tela tocado. Os bancos `orizon_test`/`orizon_e2e` ficaram, ao final desta
tarefa, recém-recriados (última recriação do Experimento 2, antes da rodada 4).
