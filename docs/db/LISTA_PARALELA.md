# Lista Paralela — organizada por destino

**Reorganizada em 15/09/2026 (Marcelo, depois de ler o `MAPA_MODULOS.md`).** Substitui o sistema
de "duas filas" desta lista (criada em 31/08) por um sistema de **destino**: todo item aberto
recebe exatamente um dos cinco valores abaixo, e é isso que faz a lista parar de crescer sem
controle — cada destino diz claramente quando e como o item sai daqui.

## Os cinco destinos

- **BETA** — quebra dinheiro ou impede uma loja de operar. Conserto individual, na semana em que
  for encontrado.
- **FRONTEIRA** — tem causa estrutural (`docs/db/MAPA_MODULOS.md`, Seção 5). Não se conserta
  sozinho: morre quando a fronteira correspondente (Seção 6 do mapa) for construída. Todo item
  aqui aponta qual das seis fronteiras o mata.
- **HIGIENE** — nome, rótulo, elemento morto. Lote único, uma passada, sem decisão de arquitetura
  nem de produto envolvida.
- **PRODUTO** — decisão do Marcelo, não defeito. Sai da fila quando ele decidir.
- **INFRA** — teste e infraestrutura. Congelados até depois da 1.0 (produção, 01/10/2026).

**`ACHADOS_CONTABEIS.md` não é mais fila — é registro histórico.** O que está sendo corrigido
agora vive só na cabeça de quem está corrigindo (Sessão A) e no próprio commit; esta lista é a
única fila de itens ainda sem destino resolvido. Ele parecia infinito exatamente por tentar ser as
duas coisas ao mesmo tempo — fila e arquivo.

**Classificação:** baseada na Seção 5 do `MAPA_MODULOS.md` (causas estruturais dos achados
abertos) e, quando a Seção 5 não cobria o item, em leitura direta do texto original de cada LP
abaixo. Toda classificação sem correspondência óbvia numa das seis fronteiras vem com a
justificativa explícita — para o Marcelo corrigir se discordar.

## Resumo — quanto cada destino/fronteira está segurando

| Destino | Itens | Observação |
|---|---|---|
| **BETA** | 0 | Nenhum item aberto aqui hoje quebra dinheiro ou trava loja — o que é urgente já está na fila ativa, não nesta lista. |
| **FRONTEIRA** | 9 | Agrupados por fronteira — ver detalhamento abaixo. |
| ↳ 6.1 (regra única de transição) | 2 | Ainda não construída — Marcelo quer desenhar com calma. |
| ↳ 6.2 (Tela Única de Provisões) | 3 | **Em construção nesta Semana 2** — `docs/db/TAREFA_TELA_UNICA_PROVISOES.md`. |
| ↳ 6.3 (Estoque como domínio) | 1 | Ainda não construída — fora do escopo desta Semana 2. |
| ↳ 6.4 (Montagem como domínio) | 1 | Ainda não construída — fora do escopo desta Semana 2. |
| ↳ 6.7 (Captação como domínio, nova) | 1 | Ainda não construída — pós-1.0; o `Lead` provisório (`PLANO_SEMANA_1.md`) segura a demanda até lá. |
| ↳ 6.8 (extração do JS de index.html, nova) | 1 | Ainda não construída — os ratchets de linha/contagem sobre `static/index.html` precisam ser repensados quando a Semana 2 chegar lá. |
| **HIGIENE** | 3 | Lote único, quando alguém tiver uma tarde livre. |
| **PRODUTO** | 8 | Esperando decisão do Marcelo. |
| **INFRA** | 8 | Congelados até depois de 01/10/2026. |
| **Total aberto** | **28** | 22 da lista original (após fechar LP-17 e mover LP-20 para "Fechados") + 4 candidatos novos do `MAPA_MODULOS.md` + LP-29 (Captação) + LP-30 (ratchets de linha vs. Semana 2). |

---

## BETA

Nenhum item aberto. O que quebra dinheiro ou impede uma loja de operar está sendo corrigido na
hora — o achado da comissão de Montagem (etapa 17 não preparando `preparar_comissao_etapa` pelo
fluxo padrão do PATCH genérico, `docs/db/MAPA_MODULOS.md` § 2.8/Candidato 5) é o exemplo mais
recente: entrou direto na correção da beta desta semana, nunca passou por aqui.

---

## FRONTEIRA

### 6.1 — Função central de transições válidas (regra única) — ainda não construída, 2 itens

Marcelo decidiu deixar o desenho da 6.1 para depois — "é o centro da Semana 2, mas quero decidir
o desenho dela com calma" — então estes dois itens ficam aqui esperando, sem prazo.

**LP-25 · Registro de assinatura por documento — quatro funções irmãs não unificadas.**
*Destino: FRONTEIRA / 6.1 — mesmo princípio de "um setter só, consultado de todo caminho" que a
6.1 pretende formalizar para o Ciclo; não é um bug hoje, os quatro concordam porque nasceram
juntos.*
`_registrar_assinatura_contrato`, `_registrar_assinatura_aprovacao_pe`,
`_registrar_assinatura_solicitacao_medicao` e `_registrar_assinatura_aditivo` (todas em `main.py`)
reimplementam, cada uma, a mesma lógica: registrar quem assinou, checar se `{"loja","cliente"}` já
assinaram, e então avançar o `status` do documento. `mod_assinatura.py` (ACHADO-69) unificou
envio/reconciliação/cancelamento de envelope ClickSign para os 4 tipos de documento, mas
deliberadamente manteve `registrar_assinatura` como parâmetro externo por documento — a
unificação parou um passo antes do "irmão" que originou a própria categoria (ACHADO-26). Nada
impede que uma das quatro ganhe uma regra nova sem as outras três. (Achado do `MAPA_MODULOS.md`,
§ 2.9, 15/09.)

**LP-26 · `contrato.status` × etapa "7" (Contrato) do Ciclo — escritos por pontos distintos, sem
função de sincronização.**
*Destino: FRONTEIRA / 6.1 — mesma causa estrutural do ACHADO-56 (Causa B do mapa: `CicloEtapa`
duplicando fato com o status de um documento), instância nova ainda sem número de achado.*
`Contrato.status` e a etapa "7" do Ciclo descrevem a mesma jornada de negócio (o contrato foi
fechado?), mas são escritos por três funções independentes sem um helper único que os mantenha
casados: `_registrar_assinatura_contrato` avança `contrato.status` sem tocar a etapa; a rota de
reabertura de etapa reseta `contrato.status = "rascunho"` num branch dedicado; e a
geração/regeração do contrato grava `contrato.status` num terceiro ponto. Já existe um remendo
defensivo no código por causa disso (comentário na rota de cancelamento: "etapa 7 do ciclo não
deveria estar 'concluido' aqui... mas se algum caminho futuro deixar isso acontecer, reabre") — o
tipo de remendo que só se escreve depois de temer (ou já ter visto) a divergência acontecer.
(Achado do `MAPA_MODULOS.md`, § 3.8, 15/09.)

---

### 6.2 — Tela Única de Provisões — desenho FECHADO, em construção nesta Semana 2, 3 itens

Ver `docs/db/TAREFA_TELA_UNICA_PROVISOES.md` para o pacote de execução. Os três itens abaixo
morrem juntos quando a tela nova substituir a antiga — não porque alguém vá corrigi-los um a um,
mas porque a tela em que vivem deixa de existir no formato atual.

**LP-13 · Tela única de Provisões por projeto.**
*Destino: FRONTEIRA / 6.2 — o item que deu origem à própria fronteira; desenho fechado, sem
decisão pendente, pronto para execução.*
Hoje há quatro caminhos para o mesmo estado — Financeiro em leitura, modal de Reconciliação do
projeto, tabela da Conciliação Final, e a Fila. Essa multiplicidade produziu, sozinha, o
ACHADO-26, 32, 33 e 41. O alvo: uma tela por projeto onde tudo acontece — ver, efetivar, revisar,
resolver, dar veredito — e link para ela onde hoje há modal ou tabela editável. O botão "Resolver"
volta e leva até lá, com a rubrica em foco. Resolve o ACHADO-37 (a fila empilhando todos os
projetos) de graça.
*Adiado (histórico):* era redesenho, não conserto, e mexeria justamente na tela que tinha acabado
de ser estabilizada. Desenho completo na Parte A do `TAREFA_CONCILIACAO_UI.md`. (Marcelo, 01/09, e
reafirmado em 02/09.)

**Desenho FECHADO com o Marcelo em 05/09** (histórico — o pacote de execução em
`TAREFA_TELA_UNICA_PROVISOES.md` é a versão acionável disto):
- uma tela só, a **Fila**, morando no módulo **Financeiro**, filtrável por projeto e por conta,
  agrupada por projeto com as contas abrindo ao selecionar, no design que hoje é usado na tela do
  ciclo.
- a tela de provisões DO CICLO permanece — mas apontando para o MESMO endpoint, a MESMA consulta e
  o MESMO box de veredito. Um componente, dois pontos de montagem. O risco não é ter duas telas, é
  ter duas implementações: foi assim que nasceram os ACHADOS 32, 33, 39 e 41, quatro vezes no
  mesmo mês.
- o contador ("N provisões em aberto") sai da MESMA consulta da lista, escopos diferentes só pelo
  filtro — número divergente entre as duas telas é defeito por construção.
- o veredito deixa de ser texto e vira botão **"Resolver"**, que NÃO navega: abre o box na própria
  linha, valha ela no ciclo ou na Fila.
- as opções do box vêm do SERVIDOR (`vereditos_validos_para_saldo`), nunca fixas na tela — fixar
  quatro opções reintroduz o ACHADO-41 com roupa nova.
- **"Vai Chegar" NÃO é veredito, é ADIAMENTO** (decidido com o Marcelo): Absorver, Receber e
  Encerrar fecham a conta; Adiar mantém a linha viva, com data prevista, marcada como aguardando
  na fila.
- o valor da despesa vem PRÉ-PREENCHIDO com o saldo disponível da provisão e continua editável —
  mesma regra da LP-15, "sugere, não manda".
(Marcelo, 05/09, percurso do `v2026.09.05-beta1`.)

**LP-10 · Botões cobrar / manter / absorver / estornar em colunas.**
*Destino: FRONTEIRA / 6.2 — mesma tela que a 6.2 reconstrói do zero; o desalinhamento desaparece
junto, não precisa de conserto isolado.*
Hoje ficam desalinhados na tela de conciliação de PE. Ergonomia pura.
*Adiado (histórico):* não muda número nem trava fluxo. (Marcelo, 31/08.)

**LP-19 · Valor estourando a coluna na tabela de decisão (família do C6).**
*Destino: FRONTEIRA / 6.2 — mesma tela e mesmo motivo do LP-10; morre junto quando a 6.2 for
construída.*
Achado do percurso do Marcelo em Homologação (05/09): "R$ -64.043,46" quebra em duas linhas na
coluna de valor da tabela de decisão (mesma classe do C6 — `docs/db/TAREFA_PERCURSO_0209.md`, o
modal de comparação de CFO/venda que tinha o mesmo problema nas caixas de KPI: coluna estreita pro
tamanho da fonte com um valor negativo/longo). Ergonomia pura, mesma família da LP-10 (botões
desalinhados na mesma tela).
*Adiado (histórico):* não muda número nem trava fluxo. (Marcelo, 05/09.)

---

### 6.3 — Estoque como domínio real — ainda não construída, 1 item

Fora do escopo desta Semana 2 (Marcelo: "as outras duas ficam para depois da 1.0").

**LP-15 · Markup de ajuste — a metade não implementada do ACHADO-31.**
*Destino: FRONTEIRA / 6.3 — a Seção 5 do mapa (Causa D) liga a lacuna a Estoque não existir como
domínio: falta um registro de "o que saiu de fábrica" separado do que a NF-e traz. Nota honesta:
o conserto estreito (parar de sobrescrever, pré-preencher em vez disso) é tecnicamente
independente de Estoque existir — mas o escopo completo do item (a distinção "ramo com NF-e de
origem" × "ramo Estoque", fixada em 04/09) só fecha de verdade com o domínio Estoque no lugar,
porque é ele que define o que "o que saiu de fábrica" quer dizer no ramo sem NF-e.*
Decidido em 31/08 e nunca escrito: "o rateio sugere, o markup manda" — o rateio pelo `Val_Cont`
deveria deixar de sobrescrever e passar a PRÉ-PREENCHER o campo, que o usuário ajusta, e a emissão
usaria o que está no campo. Medido em 03/09: não existe `markup_ajuste` em lugar nenhum do
código, e `rescalar_itens_para_total` continua sobrescrevendo o valor digitado sempre que há
contrato — ou seja, o número que o usuário digita é descartado justamente no caso normal, que é o
defeito original.
*Por que importa:* quando parte do projeto é produzida localmente, a NF-e da fábrica não cobre
tudo, e forçar a face da saída à parcela Mercadoria rateada produz um número que não corresponde
ao que saiu.
*Adiado (histórico):* apareceu ao fechar o item 2 do bloco fiscal (03/09) e não é item de nenhum
bloco — é decisão tomada, sem implementação e sem dono. A consequência aceita (a face da nota
deixar de bater com a receita de mercadoria escriturada) já está registrada no próprio ACHADO-31.

**Fronteira definida em 04/09** (percurso do Marcelo, ver LP-18): o Markup de Ajuste é um
multiplicador sobre os valores DE FÁBRICA, para ajustar ao preço de venda — logo ele só existe no
ramo "com NF-e de origem". No ramo "Estoque" não há valor de fábrica para multiplicar: o usuário
digita o PREÇO DE VENDA direto, e nenhum multiplicador se aplica. Isso não resolve a LP-15 —
delimita onde ela vale, e impede o erro de leitura oposto (registrado porque foi cometido nesta
conversa: ler o Estoque como o destino do markup, quando é o contrário).

---

### 6.4 — Montagem como domínio com tabela própria — ainda não construída, 1 item

Fora do escopo desta Semana 2.

**LP-23 · Montador é pago por volume MONTADO, e a tela só sabe falar de venda.**
*Destino: FRONTEIRA / 6.4 — Causa D do mapa: nasce porque Montagem não tem tabela própria, então
o campo genérico da Folha carrega dois significados (venda × execução). Promover Montagem a
domínio resolve isto na raiz.*
Achado do Marcelo em 10/09, configurando a Remuneração das funções em Homologação: o modal
"Remuneração — Montador" oferece "Usa comissão de vendas por metas", "Comissão por meta?" e um
seletor **Base: Líquido de Vendas**. Para o Montador nada disso descreve o que ele recebe — a
remuneração variável dele é por **volume montado**, não por venda.

**O motor já faz a conta certa.** `mod_comissao.preparar_comissao_etapa` dispara na conclusão da
etapa **17 (Montagem)** com papel `montagem` (`PAPEL_POR_ETAPA`), e a base é **Σ `order_total` dos
ambientes atribuídos àquele montador no Mapa de Atribuições** (`base_ambientes`; atribuição de
projeto inteiro = todos os ambientes). Isso É volume montado. O item nasce em `comissao_folha` com
`origem='papel'`, e a Folha soma. O próprio comentário de `ComissaoFolha.base` já registra a
ambiguidade: *"Σ order_total dos ambientes (ou vendas líq.)"* — dois significados, um campo, e a
tela só nomeia um deles.

**O que falta é a TELA, não o cálculo.** O `%` que o motor aplica sai de `_pct_funcao(funcao, base)`
→ `mod_folha._resolver_pct_funcao` → `funcao.comissao_json`. Ou seja: o MESMO campo que a tela
rotula "comissão de vendas" é o que parametriza a comissão de papel do montador. Consequências
medidas:

- o rótulo **mente** sobre o que o número faz (base é volume montado, não líquido de vendas);
- o seletor "Base: Líquido de Vendas" oferece uma opção que não se aplica à função escolhida —
  família do "a tela oferece o que o servidor não faz" (ACHADOS 32/33/39/41/49/50);
- `preparar_comissao_etapa` pula quem tem `pct <= 0` ("função do executor sem comissão → sem
  item"). Com o campo em 0, o montador **não gera item nenhum**, em silêncio, e nada na tela diz
  por quê.

**O desenho que falta**, para a rodada que pegar isto:
1. a tela distinguir as **três naturezas de base** que já existem no motor — venda líquida
   (Consultor, faixas da LOJA), volume executado por papel (Montador/Medidor/Projetista,
   `order_total` dos ambientes do Mapa), e base digitada na Folha (demais funções) — e mostrar só
   a que vale para a função;
2. faixas **por volume montado** (m², ou faixa de `order_total`), no lugar de faixas por venda,
   para quem é remunerado por papel;
3. dizer na tela que 0% significa "não gera comissão", em vez de silêncio.

*Não implementado.* Ligar isto sem (1) é o que produz o achado ao contrário: número certo com
rótulo errado, que é pior que número errado — ninguém confere o que parece coerente.
*Adiado (histórico):* achado ao preparar dado de teste da Folha, não é item de bloco nenhum.

---

### 6.7 — Captação como domínio real (módulo definitivo, pós-1.0) — ainda não construída, 1 item

Não corresponde a nenhuma das seis fronteiras do `MAPA_MODULOS.md` § 6 — é uma fronteira nova,
sem número lá ainda, aberta pela entidade `Lead` (14/09/2026, `PLANO_SEMANA_1.md`). Registrado
aqui, e não em PRODUTO, porque não é uma decisão pendente: já foi decidido que o cadastro atual é
provisório, o que falta é o trabalho de construir o módulo de verdade.

**LP-29 · Captação precisa nascer como módulo de verdade depois da 1.0; o cadastro de lead atual
é provisório e deliberado.**
*Destino: FRONTEIRA / 6.7 (nova) — o `Lead` (tabela própria, `database.py`) resolve uma demanda
comercial parada — hoje um contato comercial só virava registro no sistema quando já era
promovido a `Cliente`, sem estágio de qualificação antes disso — mas nasceu deliberadamente
simples: núcleo fixo de campos + `dados_json`/`template` para o que varia por formulário de
captação, sem fila, sem funil, sem atribuição automática, sem os relatórios que uma Captação de
verdade exigiria.* Consumidor real (14/09/2026, commit separado do nascimento do `Lead`):
`chat/triagem.py::triagem_materializar` passou a criar `Lead` em vez de `Cliente` para contato
inbound sem match — reversão deliberada da "decisão 12" original (contato inbound sem match virava
`Cliente` direto, sem estágio de qualificação; motivo: leads de Google/Instagram/Facebook chegam
por WhatsApp e a triagem os promovia a Cliente antes de qualquer briefing). Este é o primeiro
consumidor real do módulo provisório, e um segundo lugar que a Captação definitiva precisará
revisitar.

---

### 6.8 — Extração do JS de `static/index.html` (Semana 2) — ainda não construída, 1 item

Não corresponde a nenhuma das seis fronteiras do `MAPA_MODULOS.md` § 6 (mesma situação da 6.7,
acima) — mas o próprio mapa já cita a extração de JS como plano real da Semana 2 (§ 4, linha sobre
"ordem de extração de arquivos JS"), não uma ideia solta.

**LP-30 · Testes que travam contagem/faixa de LINHA ABSOLUTA de `static/index.html` quebram por
inteiro quando o JS sair do arquivo — não é um ratchet a reajustar, é um ratchet que perde o
sentido.**
*Destino: FRONTEIRA / 6.8 (nova) — a causa é estrutural: `static/index.html` hoje é HTML+CSS+JS
num arquivo só (ADR-003, 26.551 linhas), então "linha 14754 até 16799" e "conte quantos
`showToast(..., true)` tem no arquivo" são proxies válidos SÓ enquanto o arquivo continuar
monolítico.* Achado ao consertar `tests/test_aceite_achado36.py` (14/09/2026, PLANO_SEMANA_1.md):
inserir a entidade `Lead` deslocou `FAIXA_INICIO`/`FAIXA_FIM` (constantes hardcoded, "linha X até
linha Y") em +99 linhas, quebrando os dois testes de aceite do ACHADO-36 sem NENHUMA mudança na
lógica que eles supostamente guardam — o teste mediu a inserção de código, não uma regressão real.
Ajustei o range desta vez (medindo o deslocamento por âncora, não de cabeça) porque ainda faz
sentido hoje; **na Semana 2, quando o JS for extraído para arquivo(s) próprio(s), esse tipo de
teste para de fazer sentido NENHUM** — não existirá mais "a linha 14754 do index.html" pra
apontar, e mesmo se existisse, um arquivo cada vez mais vazio não é mais o universo que o teste
pretendia cobrir ("nenhum `showToast(erro)` sobra no módulo financeiro"). *O que precisa acontecer
na Semana 2, não antes:* re-desenhar esses testes para apontarem para o(s) arquivo(s) JS que
herdarem o código financeiro/provisões (por nome de arquivo ou de função, não por número de linha)
— repensar, não só reajustar mais uma vez. Registrado agora, achado incidental durante o conserto
de uma regressão, não investigado a fundo (fora do escopo desta rodada).

---

## HIGIENE

Lote único, sem decisão de arquitetura nem de produto — quando alguém tiver uma tarde livre entre
ciclos.

**LP-03 · Varredura de `logging.warning`/`print` em caminho de dinheiro.**
*Destino: HIGIENE — chamada de julgamento explícita: não é literalmente "nome/rótulo/elemento
morto", mas tem a mesma forma (varredura de baixo risco imediato, passada única, sem decisão
pendente). Diferente das outras duas HIGIENE desta lista, este item é um MÉTODO — uma varredura —
não um defeito único; o resultado dela pode gerar itens novos com destino BETA ou FRONTEIRA, que
aí sim entram na fila certa.*
Quatro achados desta auditoria nasceram de alguém prever a falha e seguir com um aviso no log:
ACHADO-18, 19, 23, 24. Cada aviso desses é um lugar onde alguém viu o problema e não teve tempo.
*Adiado (histórico):* é varredura ampla, melhor feita de uma vez com a fila vazia.

**LP-27 · Motivos de retenção por obra — lista JS hardcoded × `mod_retido.MOTIVOS_RETENCAO`.**
*Destino: HIGIENE — cópia manual de um enum de negócio entre backend e frontend, sem lógica nem
decisão envolvida; é rename/consolidação, não arquitetura.*
O array de motivos de retenção usado no frontend (`const motivos = ['Atraso da Obra', 'Aprovação
do Arquiteto', ...]`) é uma cópia manual de `mod_retido.MOTIVOS_RETENCAO` — o próprio comentário no
`static/index.html`, junto ao array, admite isso ("espelho de `mod_retido.MOTIVOS_RETENCAO`
(backend valida)"). É a mesma forma da duplicação já registrada entre `ETAPAS_CICLO`/`ETAPA_NOME`
(que já divergiu uma vez, achado da Vera em 26/08) — uma segunda instância confirmada do mesmo
hábito. (Achado do `MAPA_MODULOS.md`, § 3.7, 15/09.)

**LP-28 · Rótulo interno de Montagem no manifesto ainda é `"Operacional"`.**
*Destino: HIGIENE — rename simples num dicionário Python; nenhuma decisão de produto nem de
arquitetura envolvida.*
`modulos.py`: `"montagem": {..., "rotulo": "Operacional", ...}`. O papel v12 renomeou
explicitamente esse módulo para "Montagem" (Pós-venda deixou de ser módulo, virou faixa) — o
manifesto não acompanhou o rename. **Não é só um detalhe interno:** `mod_perfis_opcoes()`
(`main.py`) lê `rotulo` direto do manifesto e devolve isso em `GET /api/admin/perfis` — consumida
pela tela **Admin › Perfis de Usuário**, a matriz onde se escolhe quais domínios cada perfil pode
acessar. Um admin configurando permissões hoje vê um checkbox rotulado "Operacional", não
"Montagem". (Achado do `MAPA_MODULOS.md`, § Candidato 3, corrigido/fortalecido em 15/09.)

---

## PRODUTO

Esperando decisão do Marcelo. Nenhum destes é defeito.

**LP-01 · Data acordada da medição.**
*Destino: PRODUTO — precisa de decisão de desenho (substitui/corrige/complementa a previsão) antes
de virar coluna/migration/tela.*
`SolicitacaoMedicao` não tem campo de data; a única data é `Contrato.previsao_medicao`, que é
previsão dada no fechamento da venda. O modal de "Solicitar Medição" deve capturar a **data
acordada**, e ela entra no documento que o cliente assina. Decidir se substitui, corrige ou
complementa a previsão — guardar as duas dá variância previsto × acordado.
*Adiado:* é coluna nova, migration, tela e decisão de desenho — não cabe num ciclo de
estabilização. (Marcelo, 31/08, clicando em Homologação.)
*Pedido de novo em 02/09*, com dois requisitos que o item ainda não tinha: **uma data por fase**
quando o projeto está desmembrado (liga no LP-12), e o registro **alterando a programação
automática** que o cronograma padrão montou na assinatura — não é campo, é entrada que substitui
previsão do sistema. Medir onde essa programação vive e quem mais a lê antes de escrever nela.
Dois pedidos independentes do mesmo usuário: o adiamento estava certo, a necessidade está
confirmada.

**LP-02 · CPF do signatário conferido contra o cadastro.**
*Destino: PRODUTO — política de negócio, não bug.*
O ACHADO-28 entra no beta2 só com validação de dígito. Conferir se o CPF **bate com a pessoa** que
deveria assinar (o cliente do projeto, o gerente da loja) é guarda diferente e mais forte.
*Adiado:* é política de negócio, decisão do Marcelo, e não travar o beta esperando por ela.

**LP-09 · Alternativas de revisão de PE.**
*Destino: PRODUTO — funcionalidade nova, Marcelo registrou insegurança sobre a escolha atual sem
decidir mudá-la.*
Hoje existe só painel de comparação. O cliente às vezes faz várias alternativas — inclusão,
remoção, mudança de item — e aquilo vira uma negociação nova. O paralelo natural é o que já existe
na venda: vários orçamentos, um vence.
*Adiado:* funcionalidade grande, e o Marcelo registrou insegurança sobre a escolha atual sem ter
decidido mudá-la. Não confundir com o ACHADO-21, que trata de revisão depois da assinatura e é
defeito, não ausência.

**LP-11 · `execucao_montagem`/`pagamento_fabrica` — ligar ou remover (ACHADO-33, item 7 de
`TAREFA_CONCILIACAO_UI.md`).**
*Destino: PRODUTO — decisão explícita pendente: ligar (com a perna de despesa corrigida) ou
remover.*
Medido em 01/09, sem mexer: os dois estão em `EVENTOS` e só são disparados por teste. Se ligados
hoje, do jeito que estão definidos, cada um faria **um lançamento só** — provisão
(2.1.04.02/2.1.04.06) × Caixa/Bancos (1.1.01), sem a perna de despesa formal que
`efetivar_provisao` já faz (`reconhecer_despesa_efetivacao`, débito na despesa × crédito no ativo
diferido). Ligar assim, sem essa perna, moveria dinheiro da provisão pro caixa sem NUNCA reconhecer
a despesa real na DRE — o oposto do que a auditoria inteira defendeu. Gatilho natural, se ligados:
`execucao_montagem` na conclusão da etapa "17" (Montagem) — hoje sem NENHUM campo de valor nesse
ponto, precisaria de um novo, tipo o "informe o valor efetivamente gasto" do Efetivar;
`pagamento_fabrica` não tem gatilho natural nenhum na aplicação — o pagamento a fornecedor que
existe (`/api/financeiro/pagar-fornecedor`, evento `pagamento_fornecedor`, DIFERENTE deste) baixa a
conta genérica 2.1.01 (Fornecedores a Pagar), não a provisão 2.1.04.06 diretamente. Como o item 6
(ACHADO-33) restaurou o Efetivar genérico pra Montagem e pra Fábrica — que já faz as duas pernas
certas, com `forma_pagamento` à escolha (direto ou a_prazo) — os dois eventos mortos podem já ser
puramente redundantes com o mecanismo genérico.
*Adiado:* decisão do Marcelo — ligar (com a perna de despesa corrigida) ou remover da tabela
`EVENTOS` os dois.

**LP-12 · Desmembramento em fases nas etapas futuras.**
*Destino: PRODUTO — é produto, não defeito; toca todas as etapas pós-venda; falta decidir a
proporcionalidade.*
O desmembramento abre dois braços na venda e para por ali: as etapas seguintes continuam tratando
o projeto como um só. A aprovação financeira passa a ser por fase, e as liberações também, com
valor **proporcional à fase**.
*Delimitação já dada pelo Marcelo, e é ela que torna o item viável:* **as contas de provisão NÃO
se desmembram** — a contabilidade continua consolidada por projeto. O que ganha fase é a camada de
acionamento. Sem migration de plano de contas, sem rateio contábil.
*Falta decidir:* proporcional a quê — valor de contrato da fase, CFO da fase, ou número de
ambientes.
*Adiado:* é produto, não defeito; toca todas as etapas pós-venda. (Marcelo, 02/09, percurso do
`v2026.09.02-beta1`.)

**LP-14 · Evento de término por etapa, com oferta de transferência.**
*Destino: PRODUTO — depende do ACHADO-46/47 (papéis declarados) antes de existir.*
Pedido do Marcelo (02/09): *toda etapa precisa ter um evento que caracterize seu término, e sempre
que terminar deve aparecer um popup informando o término e oferecendo a transferência de
responsabilidade.* Hoje a transferência é um ato avulso, procurado pelo usuário quando ele lembra
— foi tentando fazê-la fora de hora que o ACHADO-46 apareceu.
*O que o item exige antes de existir:* um levantamento de quais das 21 etapas têm hoje um evento
de término identificável e quais terminam por inferência (status mudou, alguém clicou). Sem esse
mapa, "toda etapa" não tem alcance definido.
*Adiado:* é fluxo novo em todas as etapas do ciclo, não conserto. Depende do ACHADO-46/47 estarem
prontos — sem papéis declarados, a oferta de transferência não teria a quem oferecer. (Marcelo,
02/09, testando o Ciclo.)

**LP-18 · Fases independentes, recebimento na Logística e entrada fiscal.**
*Destino: PRODUTO — frente grande com tarefa própria (`TAREFA_FASES_E_RECEBIMENTO.md`); não morre
sozinha quando uma fronteira for construída, precisa do próprio ciclo de desenho. Correlação: a
parte de "Conferência de Volumes" toca a mesma lacuna estrutural da 6.3 (Estoque) — quem pegar
esta frente se beneficia de olhar a 6.3 primeiro, mas a 6.3 sozinha não resolve isto.*
Levantada pelo Marcelo percorrendo o `v2026.09.04-beta1` em Homologação, junto com o ACHADO-49.
Não é achado: nada disso está errado — nada disso existe. É ausência, e o desenho está em
`docs/db/TAREFA_FASES_E_RECEBIMENTO.md`.
**Por que aqui e não na fila ativa**, contra a regra 2 do sistema antigo desta lista: a regra
mandava o *correlacionado* para a fila ativa, e esta frente não era correlacionada ao bloco fiscal
— é outro assunto, que só encosta nele no fim. E é grande o bastante para engolir o que resta do
bloco fiscal se for misturada. O ACHADO-49, que nasceu no mesmo percurso, esse **era**
correlacionado (defeito do F2-15) e foi para a fila ativa como F2-20 — os dois caminhos, lado a
lado, no mesmo dia.
**O que a frente cobre** (uma linha cada; o desenho fica na TAREFA):
- carregar e implantar pedidos POR FASE, cada fase concluindo sozinha — hoje um arquivo só dá a
  etapa inteira por concluída
- indicador no painel do ciclo quando uma fase seguiu e a outra ficou para trás — caso real: a
  obra exigiu tocar a Fase 2 e a Fase 1 ficou sem finalizar
- Logística e Expedição: o recebimento não tem ação de concluir; precisa de carga de NF-e e de
  pedidos em relação N:N, conferência de volumes (os da nota × os efetivamente recebidos), campo
  de observações, tudo persistido; a Visão Geral deixa de listar número de pedido e passa a ser
  resumo da fase
- emissão da NF-e POR FASE, perguntando NF-e de Origem (lista das carregadas no recebimento) ou
  "Estoque" (preço de venda digitado, sem markup — ver a fronteira na LP-15)
- os botões de carregar e de emitir precisam morar DENTRO da tabela de fases, associados a cada
  fase — hoje ficam soltos na etapa inteira, sem dizer a qual fase pertencem; e as notas se
  associam aos AMBIENTES do projeto, não à etapa como um todo (achado do Marcelo, 04/09, percurso
  do `v2026.09.04-beta1` — mesmo dia do ACHADO-49/50/51, classificado por ele mesmo como LP, não
  achado de bloco fiscal)
- a carga das NF-e da fábrica deve ocorrer na subfase de RECEBIMENTO — confirmado pelo Marcelo no
  percurso de 05/09 (`v2026.09.05-beta1`); é literalmente o item 2 de
  `TAREFA_FASES_E_RECEBIMENTO.md` ("item 2, recebimento — cria o dado que o item 3 consome"), não
  um ponto novo — registrado aqui pra não depender de só estar na TAREFA
**Consequência imediata na fila ativa (histórico):** o item 5 do bloco fiscal (NF-e H/P) ficou
suspenso até esta frente ter decisão — `ROTEIRO.md`, F2-21.

**LP-24 · Aprovação do PE não tem testemunha na assinatura — lacuna ou decisão? Desconhecido.**
*Destino: PRODUTO — a própria natureza do item é "decidir se é lacuna ou decisão", não há como
classificar diferente até isso ser resolvido.*
Achado no Passo 0 (inventário) de `docs/db/TAREFA_ACHADO69_ASSINATURA_UNIFICADA.md`, comparando os
três documentos com escolha de canal ClickSign. O Contrato suporta testemunha 1/2 na assinatura
(`_enviar_contrato_para_clicksign`, e colunas próprias no modelo). A Solicitação de medição não
suporta — e isso é decisão registrada, de 17/08/2026 (comentário no código de
`SolicitacaoMedicaoAssinatura`). A Aprovação do PE também não suporta
(`_enviar_aprovacao_pe_para_clicksign` não recebe o parâmetro `testemunhas`), mas não há decisão
nenhuma registrada para essa ausência — pode ser lacuna (nunca foi pedida) ou pode ter sido uma
escolha implícita de quem escreveu o código na época.
**Fora do escopo do ACHADO-69** por decisão de Marcelo (13/09): desconhecido não se resolve
unificando por cima — unificar teria que ESCOLHER um comportamento pra Aprovação do PE sem saber
se existe um motivo pro atual. Fica registrado aqui até alguém confirmar (perguntando a quem pediu
a funcionalidade originalmente, ou observando se a falta de testemunha em Aprovação do PE já
incomodou alguém em produção) se é lacuna a fechar ou decisão a documentar.

---

## INFRA

Congelados até depois de 01/10/2026 (produção). Teste e infraestrutura de desenvolvimento — nenhum
destes afeta uma loja operando hoje.

**LP-04 · Varredura das fixtures que montam estado direto no banco.**
*Destino: INFRA.*
O passo 9 revelou vários testes com `valor_total` zero por acidente, porque construíam o vínculo
de ambiente no banco sem passar pelo recálculo do caminho HTTP. Todo teste assim prova menos do
que promete.
*Adiado:* não afeta produção, e mexer em fixture no meio de um ciclo mascara regressão.

**LP-05 · E2E dos demais fluxos terminais.**
*Destino: INFRA.*
A recomendação do F2-2 era dois ou três; existe um (Conciliação Final). Candidatos: emissão de
NF-e, e o ciclo do aditivo ponta a ponta.
*Adiado:* o primeiro precisa rodar algumas semanas antes de sabermos se o padrão se sustenta.

**LP-06 · PostgreSQL 16 na bancada.**
*Destino: INFRA.*
Hoje PG18 contra PG16 dos servidores. Já custou uma armadilha documentada (`SET
transaction_timeout` no dump). Ver `ESTEIRA.md`.
*Adiado:* mexer no banco da bancada no meio de um ciclo para a suíte por um tempo indeterminado.

**LP-07 · Acesso remoto à bancada por rede privada.**
*Destino: INFRA.*
Tailscale ou WireGuard, sem abrir porta. Objetivo do Marcelo: liberdade de trabalhar de qualquer
lugar sem expor a máquina que tem repositório, chaves e histórico.
*Adiado:* é infraestrutura, não bloqueia nada hoje.

**LP-08 · Servidor de desenvolvimento remoto.**
*Destino: INFRA.*
A `ESTEIRA.md` já comporta: entra como estágio 1 e a bancada volta a ser só oficina.
*Adiado:* o Marcelo registrou como intenção, sem prazo.

**LP-16 · `test_aceite_achado12.py::test_projeto_com_aditivo_termina_com_2106_zerado` — dívida de
isolamento, não de código.**
*Destino: INFRA — nomeado explicitamente pelo Marcelo.*
Achado ao fechar o F2-17 (bloco fiscal itens 3/4, 03/09): numa rodada de `pytest -q` completo o
teste falhou; rodado sozinho, passa; rodado de novo na suíte inteira (mesmo código, sem nenhuma
mudança), passa também. Ou seja, existe uma combinação de ordem/estado compartilhado entre este
teste e algum outro que só se manifesta às vezes — a mesma classe de problema que o ESTEIRA.md já
nomeia ("resolva o isolamento, não o teste"), e que fecha o CI num dia e quebra no outro sem
ninguém ter mexido em nada.
*O que falta antes de consertar:* identificar QUAL outro teste deixa estado que este lê — não dá
pra reproduzir por comando único ainda (a falha não é determinística por posição fixa na suíte, só
ocorreu uma vez em várias rodadas). Precisa de um `pytest-randomly`/bisect de ordem, ou de
instrumentar o que exatamente o teste lê que poderia vir sujo (a conta 2.1.06, pelo nome do
teste).
*Adiado:* não é item de bloco nenhum, achado incidental durante o fechamento de outra frente —
registrado aqui pra não se perder, não investigado a fundo ainda.

**Atualização (F2-29 Fatia D, 06/09):** fechadas 3 sessões vazadas neste teste (`app_db.
get_session()` inline, nunca fechadas — só sobrevivem até o `engine.dispose()` do teardown do
MÓDULO, `tests/conftest.py`, não até o fim do teste) — higiene, feita por segurança, mas NÃO
confirmada como a causa raiz do flake. Descartadas duas hipóteses concretas: (a) vazamento de
conexão acumulando entre módulos — não acontece, `app_db` dropa/recria o schema E dispõe a engine
por módulo (roda sequencial, sem xdist, nas invocações desta sessão); (b) cache de
`auth/perfis.py` (`_REG_BY_SLUG`) ficando stale entre módulos — não acontece pra quem usa a
fixture `seed` (chama `perfis.recarregar()` no próprio setup), e este teste usa `seed`. Ainda
falta o que o próprio achado original pedia: bisect real (`pytest-randomly` ou instrumentar
exatamente o que a conta 2.1.06 lê que poderia vir sujo) — não feito, seguem em aberto.

**Atualização (F2-30 Fatia 4, 06/09) — reclassificado: NÃO é resíduo de vizinho.** Reexaminado com
a mesma lente que o F2-29 Fatia D usou pra achar o `test_contrato_real_geracao_e_assinatura`
(procurar o vizinho que suja, não aceitar "não reproduziu de novo" como prova de aleatoriedade).
Achado estrutural que o texto original não tinha: `test_projeto_com_aditivo_termina_com_2106_
zerado` é o **PRIMEIRO teste definido no próprio arquivo** — não existe vizinho do MESMO módulo
rodando antes dele que possa deixar resíduo (o segundo teste do arquivo, que rodaria depois, já
usa `qual="l2"` de propósito, projeto diferente). E resíduo de OUTRO arquivo já está
estruturalmente descartado (hipótese (a) acima — `app_db` dropa/recria o schema e dispõe a engine
por módulo). Ou seja: não há vizinho de módulo nenhum capaz de sujar este teste, nem do mesmo
arquivo nem de outro — a classe "resíduo de vizinho" (que fechou o F2-29 Fatia D) não se aplica
aqui, mesmo achado sendo o MESMO padrão de evidência (passa sozinho, passa na maioria das rodadas
da suíte, falhou uma vez).
*Bisect real feito, sem reproduzir:* 2 rodadas completas da suíte (sem E2E) com `pytest-randomly`
(`-p randomly`, ordem embaralhada de verdade, não só rodar de novo na mesma ordem) — nenhuma
reproduziu a falha deste teste. Combinado com as rodadas anteriores (fixas), são várias tentativas
sem reprodução — mas, por definição, isso não prova aleatoriedade (é exatamente a inferência que
já enganou uma vez); é só o resultado de um bisect que não pegou o caso ainda.
*Hipótese nova, não confirmada:* achado incidental durante esta mesma fatia — `tests/
test_bateria_ciclo.py` (LP-21) mostra o MESMO padrão (falha às vezes, mesmo sozinho no próprio
arquivo, sem vizinho fixo) numa área de código completamente diferente (ramo financeira/retenção,
não aditivo/2.1.06). Duas classes de teste com o mesmo comportamento ("falha não determinística,
sem vizinho que explique") em código não relacionado sugere uma causa mais estrutural do que
resíduo de teste — por exemplo, uma condição de corrida real ou sensibilidade a hora de parede
(classe ACHADO-48) em código de PRODUÇÃO compartilhado, não nos testes. Não investigado a fundo
(exigiria instrumentação de timing, fora do escopo desta fatia).
*Recomendação para quem pegar depois:* não tratar como "resíduo de vizinho" (já descartado); focar
em timing/concorrência real, talvez cruzando com o mesmo esforço de investigação da LP-21.

**LP-21 · `test_bateria_ciclo.py` — cenários "financeira" deixam `1.1.02` aberto, não
determinístico mesmo isolado no próprio arquivo.**
*Destino: INFRA — nomeado explicitamente pelo Marcelo.*
Achado ao rodar a camada (d) do F2-30 (06/09): a suíte completa (sem E2E) voltou com contagens de
falha DIFERENTES em três rodadas seguidas (35, depois 59, depois 48 — inclusive numa rodada com as
mudanças do F2-30 inteiramente stashed, ou seja, em `main` sem nenhuma mudança minha), provando
que a instabilidade é pré-existente e não causada pelo F2-30 (mesmo raciocínio de A/B já usado pra
separar F2-27 do F2-25 no F2-28). Investigando a fundo mais um caso específico:
`tests/test_bateria_ciclo.py` sozinho (23 cenários, nenhum outro arquivo no meio) já falha por
conta própria — `financeira_sem_custo_com_aditivo` e `financeira_com_custo_com_aditivo` (às vezes
também `financeira_sem_custo_sem_aditivo`) deixam `1.1.02 Contas a Receber` aberto no fechamento
(`_conferir_invariantes`, linha 228) com o MESMO valor que deveria ter ido pra `4.4.05 Ajuste de
Retenção Financeira` na conferência do ramo financeira — mas rodados SOZINHOS (só os 2-3 nodeids
dos cenários financeira), sempre passam. Diferente da classe LP-16 (falha por ORDEM fixa, sempre a
mesma): aqui o Nº de falhas mudou entre duas rodadas do MESMO arquivo, sem nenhuma mudança de
código no meio — não é resíduo de um vizinho fixo, cheira a condição de corrida ou dependência de
estado que dois cenários "financeira" compartilham entre si de forma não determinística.
*O que falta antes de consertar:* isolar COM QUAL outro cenário "financeira" a corrida acontece
(rodar só os cenários financeira entre si, em subconjuntos, repetidas vezes, até achar o par
mínimo que reproduz de forma estável) — não investigado a fundo aqui, achado incidental durante o
fechamento do F2-30, fora do escopo das 4 fatias. Registrado com evidência concreta (nunca só
"rodei de novo e sumiu") pra não repetir a inferência que o LP-16 já cometeu uma vez.
*Adiado:* não é item de bloco nenhum; achado ao verificar que o F2-30 não regrediu nada, não que o
F2-30 tenha causado isto.

**LP-22 · Os E2E de navegador dividem um banco só, e o boot faz DDL.**
*Destino: INFRA — nomeado explicitamente pelo Marcelo; é o próprio motivo pelo qual a Sessão B não
pode rodar `pytest` ao mesmo tempo que a Sessão A.*
Achado em 10/09, ao rodar a bateria de regressão do F2-43: o servidor E2E morreu no boot com
`DeadlockDetected` em `_migrar_colunas_pg()`, no `ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS
senha_provisoria`. Dois processos travados um no outro fazendo DDL no MESMO `orizon_e2e`.
A causa é estrutural, não acidental: **cada módulo de E2E de navegador sobe o próprio servidor**
(padrão da casa — fixture `servidor_e2e` por arquivo, porta própria), e todo boot passa por
`init_db()` → `_migrar_colunas_pg()`, que a R1 congelou mas que continua rodando DDL a cada
partida. Dois boots próximos no mesmo banco = deadlock.
**É primo dos cinco flakes já listados (LP-16, LP-21 e os três irmãos), mas de espécie diferente:**
aqueles FALHAM por timeout de socket de 5s; este falha por lock de DDL, e a mensagem não se parece
nada com as outras. A causa comum é a mesma — E2E compartilhando um banco só, sem serialização.
Com o sexto caso registrado em 09/09 (`test_e2e_browser_negociacao_layout.py`, travado no upload
do XML sob carga), a família chega a sete ocorrências.
**Pior que falhar: travar.** Em 09/09 uma bateria de E2E ficou **12 horas pendurada** — pytest
vivo, Chromium vivo, `main.py` vivo, CPU zerada, segurando o lock do `orizon_e2e` e bloqueando
qualquer execução seguinte. Só apareceu porque alguém foi olhar o `ps`. O E2E de navegador não tem
timeout nenhum.
*Mitigação proposta (implementada, ver abaixo):* `--timeout` global no `pytest.ini`
(pytest-timeout), pra que o pior caso vire uma falha legível em vez de um bloqueio silencioso. Não
resolve a causa — resolve a descoberta.

**Atualização 10/09 (Claude Code) — entrega (a) feita, medição dos Passos 1/2 em
`docs/db/TAREFA_ESTABILIDADE_SUITE.md`:**

**(a) feito.** `pytest.ini` ganhou `timeout = 300` (pytest-timeout, instalado); provado com um
`time.sleep(600)` descartável virando falha legível com `--timeout=3` (não esperei os 300s de
verdade pra provar o mecanismo — o override por linha de comando É a interface pretendida) e com
um teste rápido confirmando que o teto de 300s do ini não afeta teste normal. Isso cobre o pior
caso do item acima (o travamento de 12h) — não a causa.

**Passo 1 (o timeout de 5s do HttpClient) — hipótese DERRUBADA.** Instrumentei
`urllib.request.urlopen` (temporário, `ORIZON_MEDIR_SUITE=1` em `tests/conftest.py`, revertido
depois de medir) e rodei `pytest -q` completo duas vezes (2750 passed, 4 xfailed, ~590s cada,
nenhuma das sete ocorrências apareceu nas duas rodadas). Das 2767 chamadas reais do `HttpClient`
(`timeout=5`): p50 = 0,005s, p95 ≈ 0,06s, **máximo 1,08–1,18s**. Nenhuma chegou perto do teto de
5s. **O timeout de 5s não é a causa comum** — não ajustei o número; a hipótese cai, como o item 4
do aceite pede.

**Passo 2 (a corrida de boot) — medição inconclusiva, registro honesto.** A mesma instrumentação,
aplicada a `subprocess.Popen` e ao `urlopen(timeout=1)` dos loops de boot dos ~30 arquivos que
definem `servidor_e2e` (o padrão citado acima), **não capturou nenhuma chamada real dessas** nas
duas rodadas completas — 0 `popen_start`, 0 `urlopen` sem `/login` — apesar de os boots claramente
terem acontecido (a suíte passou). Verifiquei em escala menor (6 e depois 13 arquivos de E2E de
navegador só) e a MESMA instrumentação capturou certinho (12 e 26 subprocessos, pareados). Não
achei a causa da diferença em escala grande — cheguei a descartar dupla-importação de
`tests.conftest` (ninguém importa assim) e reassinatura direta de `subprocess.Popen` em qualquer
teste (nenhuma ocorrência) — mas não persegui além disso; é um artefato da FERRAMENTA de medição,
não do sistema medido, e não vale gastar mais rodadas de 10 minutos nele sem uma pista melhor.
Dado estrutural que SEI por leitura, não por instrumentação: são exatamente **30 arquivos**, cada
um com `servidor_e2e` `scope="module"` — sem `pytest-xdist` instalado e sem nenhum plugin de
reordenação, `pytest -q` roda os 30 boots em SÉRIE, um processo por vez. Isso não prova ausência de
corrida (o deadlock do item 7 é evidência de que ela existe às vezes), mas sugere que ela não nasce
do agendamento do próprio pytest numa rodada serial única — os candidatos que sobram são (i) duas
invocações de pytest rodando ao mesmo tempo (dois terminais, dois jobs de CI) ou (ii) uma corrida
fina no fechamento da conexão Postgres do processo anterior, abaixo do que dá pra ver por fora do
processo com timestamps de `urlopen`/`Popen` no lado do cliente. Provar (ii) provavelmente exige
instrumentar DENTRO do próprio `main.py`/`_migrar_colunas_pg()` (logar timestamp de início/fim da
DDL num arquivo), não por fora.

**Não avancei para (b)/(c)** — só a entrega (a) e a medição, como pedido.

**Atualização 11/09 (Claude Code) — aceite 1 da Rodada 2: reproduzido, e pior do que a hipótese
previa.** Duas invocações de `pytest -q` completas, disparadas ao mesmo tempo contra os mesmos
bancos (`orizon_test`/`orizon_e2e`), do zero. Resultado: paredes de `E`/`F` desde os primeiros 10%
da suíte em AMBAS — não "alguns flakes a mais", é colisão sistemática. O `--timeout` global
(entrega (a)) disparou várias vezes (confirmado no log — dump de stack de `pytest-timeout`), o que
já muda o quadro da Rodada 1: não é um travamento único e silencioso, é uma sequência de MUITOS
testes cada um pagando até 300s de timeout contra um banco corrompido pela concorrência — some numa
suíte de ~2755 testes, isso soma horas de verdade (as duas rodadas ainda estavam vivas **mais de
24h depois**, achadas por acidente enquanto eu media outra coisa — mesmo padrão do achado
original, "só apareceu porque alguém foi olhar o `ps`"). Não consegui um stack trace limpo da
causa exata (sem `py-spy` com root neste ambiente; `pg_stat_activity` não mostrava lock-wait no
instante em que investiguei — o processo parecia "rodando", não travado num lock específico, o que
sugere thrashing/degradação, não necessariamente um deadlock de DDL puro toda vez). Encerrei os
dois processos (e os Chromiums órfãos deles) pra liberar o banco — não valia mais continuar a
reprodução, o resultado já estava inequívoco. **Confirma o enunciado da Rodada 2**: duas invocações
simultâneas não são seguras, e o guard (item (c) da Rodada 2) é o próximo passo — ainda não
implementado. **É o motivo direto pelo qual esta lista (Sessão B) nunca roda `pytest` enquanto a
Sessão A trabalha — a regra não é cautela genérica, é este achado.**

**Atualização 13/09 (Claude Code) — RODADA3 (b) fechou o travamento de 12h (Achado 2,
`docs/db/TAREFA_ESTABILIDADE_RODADA3.md`: corrupção de laço greenlet/asyncio quando o sinal do
pytest-timeout interrompe o Playwright — método trocado pra `'thread'`), mas o que sobrou depois é
maior do que parecia.** Uma execução completa (13/09, durante o Passo 0/1 do ACHADO-69) falhou em
**10 arquivos de E2E de navegador diferentes**, nenhum backend — total de coleta idêntico ao de
uma execução limpa no mesmo dia (2780), então não é diferença de coleta, é intermitência de
verdade. Nenhum arquivo se repete entre esta lista e a de execuções anteriores do mesmo dia (nem
`test_remover_ciclo.py` falhou no mesmo teste das vezes anteriores — falhou num teste DIFERENTE do
arquivo). **Registro deliberadamente sem causa:** não escrevo aqui "provavelmente carga" nem
"provavelmente timing" — foi cogitado e MEDIDO que não é isso (ver RODADA3, hipótese dos tempos de
espera do Playwright derrubada com `#neg-subtotal` idêntico isolado e em suíte, 783ms vs.
780-785ms). Não sabemos a causa, e escrever um palpite aqui teria o efeito de fazer alguém no
futuro parar de procurar.

**Decisão de Marcelo (13/09): rodada própria, depois que o ACHADO-69 fechar — não agora, pra não
misturar duas investigações.** Isto NÃO é bloqueio para o ACHADO-69: o portão de aceite de cada
migração do Passo 2 é a suíte específica de ClickSign (hoje 64 testes) mais a contagem total de
coleta — não a suíte E2E inteira, que não distingue "quebrei algo" de "é o flake de sempre".

**Atualização 14/09 (Claude Code) — a "rodada própria" prometida acima aconteceu**
(`docs/db/TAREFA_FLAKES_E2E.md`, 8 rodadas completas + isolamento de cada um dos 15 testes que
falham): 41 falhas/15 testes/9 arquivos, TODOS os 15 também falham isolados (1/10 a 10/10) — a
contaminação cruzada pura já foi descartada como causa ÚNICA por essa mesma medição. O ponto de
falha mais comum, por contagem bruta nos 47 logs isolados, é `#np-cli-dropdown` (27 ocorrências,
à frente do `#neg-subtotal` que a RODADA3 investigou, 20 ocorrências) — família DIFERENTE da
corrupção de boot/DDL que este LP-22 rastreia, mas do mesmo gênero (E2E de navegador, timeout de
10s). **Esse sub-caso está resolvido agora** (item 1 da fila de beta, PLANO_SEMANA_1.md): causa
nomeada — os 11 arquivos afetados esperavam o `<div>` do dropdown correndo contra um debounce de
300ms IMPLÍCITO no `npBuscarCliente()`, sem esperar a resposta de rede de verdade; corrigido
trocando por `page.expect_response(...)` antes do fill, nos 11 arquivos (ver
`TAREFA_FLAKES_E2E.md` pela medição completa e o commit desta correção pelo diff). **A família de
47 falhas isoladas encolhe para os 20 do `#neg-subtotal`** (já investigado pela RODADA3, sem causa
raiz encontrada — sobrevivências dos tempos de espera do Playwright, hipótese de timing já
derrubada) **mais o que sobrar do restante** (`#np-cli-dropdown` era o mais comum, mas não o
único ponto de falha dos 15 testes — a tabela completa está em `TAREFA_FLAKES_E2E.md`). Não
resolve o LP-22 em si (boot/DDL é mecanismo diferente) — é o primeiro corte real dentro da família
mais ampla de flakes de E2E que este item vem acumulando desde 09/09.

---

## Fechados — não são adiamento, e por isso não estão na lista acima

- **Aditivo criado manualmente entre a assinatura e o PE.** DECIDIDO em 31/08: **não entra**. O
  aditivo continua nascendo só do PE. Motivo e consequências em `DESENVOLVIMENTOS.md`. Reabre-se
  com número se o caso real aparecer com frequência.
- **ACHADO-15.** Aposentado em 31/08: a divergência de meio de ciclo é o modelo, não defeito.
- **LP-17 · Dois testes que ainda comparavam `datetime.utcnow()` com competência já migrada pro
  ACHADO-48 · RESOLVIDO 04/09, `b7bb834`.** Varredura ampla feita depois (F2-29 Fatia D, 06/09):
  dos ~40 usos de `datetime.utcnow()` em `tests/*.py` (19 arquivos), 0 compartilham o padrão desta
  LP — todos usam margens de DIAS (imunes a um desvio de fuso de 3h) ou comparam `utcnow()` contra
  `utcnow()` do próprio código de produção sendo testado. Fechado — nada a consertar. (Movido para
  "Fechados" em 15/09 — estava listado como item numerado, mas já resolvido desde 04/09.)
- **LP-20 · Rótulos do veredito (Absorver/Receber/Encerrar/Adiar).** DECIDIDO em 05/09, depois de
  `docs/db/MODELO_CONTABIL.md` fechar o modelo (F2-26): o que travava o mapeamento era não saber
  se "Receber" precisava de um lançamento de receita novo — agora sabe-se que sim, e o modelo já
  diz onde. Absorver (gastou mais que o provisionado) → Despesa de Conciliação, competência da
  conciliação; Receber (gastou menos) → Receita de Conciliação, mesma competência; Encerrar (bateu
  exato) → fecha sem tocar o resultado; Adiar → mantém a rubrica aberta, com data prevista. Detalhe
  e o porquê de "Receber" não ser receita de venda em `MODELO_CONTABIL.md`, seção "As contas de
  Conciliação" e "Pendências". Não implementado ainda — isso é desenho, a implementação é a frente
  própria que o modelo já descreve ("Onde isto entra no plano"). **Nota (15/09): esta implementação
  é parte do pacote da fronteira 6.2 — ver `docs/db/TAREFA_TELA_UNICA_PROVISOES.md`.**
