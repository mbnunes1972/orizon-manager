# Rascunho — regra única de transição do Ciclo (Fronteira 6.1)

Escrito pela Sessão B, 15/09/2026, a pedido do Marcelo: **não é uma especificação pronta, são
opções.** A 6.1 é a fronteira de maior retorno da Seção 6 do mapa e a que mexe no motor mais
crítico do sistema (`mod_ciclo.py`) — por isso o desenho fica para o Marcelo e o Claude do
navegador decidirem, não para esta sessão escrever.

**Nota sobre a contagem:** o pedido original falava em "7 itens de FRONTEIRA" — desde então
`LISTA_PARALELA.md` ganhou um oitavo (LP-29, fronteira nova 6.7/Captação, adicionada depois deste
pedido). Uso 8 abaixo, que é a contagem real agora.

---

## O que existe hoje, espalhado

**Seis funções de checagem já vivem em `mod_ciclo.py`, cada uma respondendo uma pergunta
diferente sobre "esta etapa pode mudar de estado?" — e isso é sintoma correto de um problema real,
não desorganização gratuita:**

| Função | Pergunta que responde |
|---|---|
| `pode_avancar(codigo, status_por_codigo, bloqueadores_ativos)` | Pode SAIR de "pendente"? (sequência + bloqueador de transferência) |
| `guarda_conclusao(codigo, tipos_presentes, status_por_codigo, pe_ambientes, aprovacao_pe)` | Pode CONCLUIR esta subfase de PE especificamente? (documento/decisão presente) |
| `guarda_conclusao_operacional(codigo, tem_xml, numeros_txt, relatorio_txt)` | Pode concluir uma etapa operacional (12/13/14)? (XML, números, relatório presentes) |
| `etapa_concluida_agregada(codigo, status_por_codigo)` | Um GRUPO de etapas (ex. "13" cobrindo 13–16) está concluído de verdade, ou só a etapa-cabeça? |
| `reabertura_bloqueada_por_contrato(codigos_a_resetar, contrato_status)` | Reabrir esta etapa desfaria um contrato já assinado? |
| `exige_aprovacao_financeira(codigo)` | Esta etapa é um gate financeiro (8/11d)? |

**Isso já é bom sinal:** as seis respondem perguntas GENUINAMENTE diferentes — não são o mesmo
código copiado seis vezes. `pode_avancar` (sequência) e `guarda_conclusao` (documento presente)
continuariam precisando coexistir em qualquer desenho novo; unificar não significa colapsar as
seis numa função só.

**O problema não está nas seis — está em volta delas, em `main.py`.** A rota
`PATCH /api/projetos/<nome>/ciclo/<codigo>` (o caminho padrão que a UI usa pra concluir qualquer
etapa sem tela dedicada) soma, além das seis funções acima, **mais oito checagens escritas
diretamente no corpo do handler**, sem função nomeada: bloqueio por retenção de obra (17/18),
lacuna de responsável no Mapa de Atribuições (17), data de entrega definida (gate financeiro),
contrato totalmente assinado (gate financeiro), segmentação Mercadoria×Serviço congelada (etapa 8),
subfases do PE pendentes (11d) e — só neste ponto, **duplicado** do endpoint dedicado
`/ciclo/11d/aprovar` — a checagem de conciliação de PE (`_pe_ambientes_pendentes_decisao` +
`mod_conciliacao_pe.fase_completa`). Esta última é o único caso onde o handler já reusa um helper
compartilhado em vez de reimplementar; as outras sete são só código inline.

**E há três formas diferentes de gravar o resultado**, uma vez que a checagem passa: o helper
`_set_etapa_status` (o único que também dispara `mod_comissao.preparar_comissao_etapa` — o achado
que já entrou na correção da beta), o próprio corpo do PATCH genérico (que reimplementa os mesmos
três campos sem chamar o helper), e `_marcar_etapa_cliente` (uma terceira via, pra marcar a mesma
etapa em todos os projetos de um cliente).

**O que isso já produziu, sem exagero — cada linha é um achado ou item real, não hipótese:**
- ACHADO-56 (duas instâncias: 11d/`reprovar` não sincroniza `AprovacaoPE.status`; 11c/
  `guarda_conclusao` nunca consulta a decisão contábil pendente)
- ACHADO-49 (a checagem de "pode remover" da etapa 12 herdou uma regra genérica não pensada pra
  ela — mesma família, checagem inline sem dono claro)
- LP-25 (quatro funções `_registrar_assinatura_*` irmãs, cada uma seu próprio "isto já foi
  assinado?")
- LP-26 (`contrato.status`×etapa "7", escritos por três pontos sem sincronização)
- o achado da comissão de Montagem (etapa 17 concluída pelo PATCH genérico não preparava comissão
  — já corrigido na beta desta semana, citado aqui só como prova viva do padrão)

Cinco sintomas, uma causa: **não existe um ÚNICO lugar que decida "esta etapa pode mudar de
estado, e o que precisa acontecer quando ela muda" — existe um lugar que decide a sequência (bem
feito, `pode_avancar`), e depois sete a oito checagens de domínio penduradas ad hoc no handler que
usa esse resultado.**

---

## Três desenhos possíveis

### Desenho A — Registro central de checagens por etapa ("hook" por domínio)

Cada etapa declara, numa estrutura central em `mod_ciclo.py`
(ex. `CHECAGENS_POR_ETAPA = {"8": [...], "11d": [...], "17": [...]}`), uma lista de funções de
checagem. Um único ponto de entrada — `mod_ciclo.pode_concluir(codigo, contexto)` — itera essa
lista e para na primeira que recusar. O PATCH genérico E os endpoints dedicados (11d/aprovar,
PE/concluir) passam a chamar só esse ponto de entrada. Cada módulo de domínio (Financeiro,
Comercial) **registra** sua própria checagem no Ciclo, em vez de o Ciclo importar lógica de
domínio — respeita a regra "núcleo não importa domínio" do `ARQUITETURA-MODULOS.md`.

**Custo:** médio-alto. Exige desenhar o "contexto" que cada checagem recebe — hoje as checagens
inline usam `db`, `loja`, `projeto`, `usuario`, corpo do request, tudo misturado. Se o contexto for
genérico demais (passar o request inteiro), o hook vira uma cópia do handler e nada foi resolvido;
se for específico demais, cada checagem nova exige mexer na assinatura do ponto de entrada.

**O que quebra no caminho:** é a mudança mais arriscada das três — o PATCH genérico e os
endpoints dedicados de 11d/PE passam a depender de um mecanismo novo; um erro no registro (uma
etapa que devia ter checagem e não tem, ou vice-versa) fica silencioso até alguém testar aquela
etapa específica. Pede suíte de teste por etapa ANTES da migração, não depois.

**Quantos dos 8 FRONTEIRA fecha:** fecha LP-26 de forma direta (o hook da etapa "7" passaria a
consultar `contrato.status` como parte da checagem central). Não fecha LP-25 diretamente — LP-25 é
sobre unificar quem REGISTRA uma assinatura, não sobre quem decide se uma etapa pode fechar; um
desenho A bem feito FACILITA um "irmão" pro LP-25 (mesma ideia de registro central, aplicada a
"registrar evento", não "checar transição"), mas não o resolve sozinho. As fronteiras 6.2, 6.3,
6.4, 6.7 não são tocadas — são de outra causa (dado que falta, não regra de transição).

---

### Desenho B — Função pura por gate, sem mecanismo de registro (generalizar o padrão que já funcionou)

Não cria infraestrutura nova. Para cada gate conhecido hoje (8, 11d, 11a–e, 12–14, 17–18,
reabertura), extrai uma função pura em `mod_ciclo.py` que recebe só dados primitivos (nunca
objetos ORM) e devolve `(pode, motivo)` — exatamente o padrão que **já existe e já funciona** para
a checagem 11d de conciliação de PE, hoje chamada dos dois lugares (`/ciclo/11d/aprovar` e o PATCH
genérico) via `mod_conciliacao_pe.fase_completa`. A diferença para hoje é disciplina aplicada às
outras sete checagens que ainda estão inline, não um mecanismo novo.

**Custo:** mais baixo que o Desenho A — não precisa desenhar um sistema de registro, só extrair
função por função, uma de cada vez, incrementalmente. Pode ser feito em paralelo por etapa, sem
travar a Semana 2 inteira num único PR.

**O que quebra no caminho:** risco menor de regressão (funções puras são fáceis de testar
isoladas), mas **nada impede a próxima checagem nova de nascer inline de novo** — é convenção, não
arquitetura imposta. Diferente do Desenho A, não há como escrever um teste de arquitetura (`ast`,
no estilo de `test_arquitetura_modulos.py`) que reprove uma checagem inline nova — só revisão de
código.

**Quantos dos 8 FRONTEIRA fecha:** fecha LP-26 igual ao Desenho A (a checagem "contrato assinado
== etapa 7 concluída" vira uma função pura chamada dos três pontos de escrita). Mesmo raciocínio
do Desenho A para LP-25 e para as outras quatro fronteiras: não tocadas.

---

### Desenho C — Fonte única de STATUS, sem mexer no motor de "pode avançar" (a fronteira mínima)

Não ataca as checagens de transição (Causa A do mapa: "regra reimplementada na tela") — ataca só a
metade "duas fontes de verdade" (Causa B): para cada par conhecido (`CicloEtapa` × documento
correlato — Contrato/etapa 7, AprovacaoPE/etapa 11d), cria uma função `status_efetivo(projeto,
codigo)` que deriva o status SEMPRE a partir do documento, nunca de `CicloEtapa.status` isolado, e
faz toda escrita passar por ela em vez de gravar os dois campos separadamente em cada rota.

**Custo:** o mais baixo dos três — não toca `pode_avancar`/`guarda_conclusao`/as oito checagens
inline, só a sincronização de status entre Ciclo e documento.

**O que quebra no caminho:** risco muito baixo — é essencialmente trocar "escrever dois campos" por
"recalcular um deles a partir do outro". Mas é a fronteira que **fecha menos**: ACHADO-49 (regra de
remoção herdada errada) e a classe inteira "tela oferece o que o servidor recusa" (Causa A) ficam
sem fronteira nenhuma — continuam nascendo achado por achado, um de cada vez.

**Quantos dos 8 FRONTEIRA fecha:** fecha LP-26 (é literalmente o problema que este desenho ataca).
Não fecha LP-25 (mesmo motivo dos outros dois — causa diferente). As outras quatro: não tocadas,
mesmo raciocínio.

---

## Resumo — nenhum dos três fecha os 8 sozinho, e é esperado

| Desenho | Custo | Risco no caminho | LP-25 | LP-26 | 6.2/6.3/6.4/6.7 |
|---|---|---|---|---|---|
| A — registro central de checagens | médio-alto | maior (mecanismo novo) | facilita, não fecha | fecha | não tocadas (causa diferente) |
| B — função pura por gate, sem registro | médio | menor (extração incremental) | não fecha | fecha | não tocadas |
| C — só sincronizar status (Causa B só) | baixo | mínimo | não fecha | fecha | não tocadas |

**Por que nenhum fecha as quatro fronteiras restantes:** 6.2 (Provisões) já tem o padrão
funcionando por conta própria (`vereditos_validos_para_saldo`) — não depende da 6.1, é o exemplo
que a 6.1 deveria imitar. 6.3 (Estoque), 6.4 (Montagem) e 6.7 (Captação) são sobre **dado que não
existe**, não sobre regra de transição mal colocada — nenhum desenho de "regra única de fechar
etapa" cria uma tabela de Estoque ou um módulo de Captação.

**O retorno real da 6.1 não é "quantos itens desta lista fecha hoje" — é quantos NÃO vão precisar
entrar na lista amanhã.** Causa A e Causa B, juntas, já produziram cinco achados/itens reais em
menos de três semanas (ACHADO-56 ×2, ACHADO-49, LP-25, LP-26), fora o que já foi corrigido na
correção da beta. Uma fronteira que fecha essa CLASSE, não essas duas instâncias, é o que evita a
sexta e a sétima ocorrência — que, sem a 6.1, vão continuar aparecendo uma a uma, cada vez com seu
próprio número de achado.

**Pergunta em aberto para a decisão, não respondida aqui de propósito:** os três desenhos não são
mutuamente exclusivos em sequência — dá pra começar pelo C (barato, fecha LP-26, zero risco),
medir se as próximas divergências de status continuam aparecendo, e só então decidir entre A e B
para atacar a Causa A. Se essa sequência faz sentido pro Marcelo e pro Claude do navegador, ou se
vale ir direto para A/B, é exatamente a decisão que este rascunho existe para provocar.
