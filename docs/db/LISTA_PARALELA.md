# Lista Paralela — organizada por destino

**Reorganizada em 15/09/2026 (Marcelo, depois de ler o `MAPA_MODULOS.md`).** Substitui o sistema
de "duas filas" desta lista (criada em 31/08) por um sistema de **destino**: todo item aberto
recebe exatamente um dos cinco valores abaixo, e é isso que faz a lista parar de crescer sem
controle — cada destino diz claramente quando e como o item sai daqui.

## Os seis destinos

- **BETA** — quebra dinheiro ou impede uma loja de operar. Conserto individual, na semana em que
  for encontrado.
- **FRONTEIRA** — tem causa estrutural (`docs/db/MAPA_MODULOS.md`, Seção 5). Não se conserta
  sozinho: morre quando a fronteira correspondente (Seção 6 do mapa) for construída. Todo item
  aqui aponta qual fronteira o mata.
- **HIGIENE** — nome, rótulo, elemento morto. Lote único, uma passada, sem decisão de arquitetura
  nem de produto envolvida.
- **DECIDIDO — fila da 1.0** — a decisão JÁ foi tomada; falta só implementar, e isso está agendado
  para depois de 01/10/2026 de propósito (não cabe num ciclo de estabilização). Diferente de
  PRODUTO (decisão pendente): aqui não há mais nada para o Marcelo decidir, só trabalho para
  alguém fazer quando a janela abrir.
- **PRODUTO** — decisão do Marcelo ainda pendente, não defeito. Sai da fila quando ele decidir.
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
| **BETA** | 3 | LP-31 (clone herda `rede_id`), LP-32 (identificação da loja no cabeçalho) e LP-33 (faixa sem teto no configurador) — os três de 16/09. LP-02 implementado em 15/09 — ver o item, abaixo, mantido como registro. |
| **FRONTEIRA** | 10 | Agrupados por fronteira — ver detalhamento abaixo. |
| ↳ 6.1 (regra única de transição) | 2 | Ainda não construída — Marcelo quer desenhar com calma. |
| ↳ 6.2 (Tela Única de Provisões) | 3 | **Em construção nesta Semana 2** — `docs/db/TAREFA_TELA_UNICA_PROVISOES.md`. |
| ↳ 6.3 (Estoque como domínio) | 2 | LP-15 + LP-18 (decidido em 15/09, medição confirmou que não é barato). Ainda não construída — fora do escopo desta Semana 2. |
| ↳ 6.4 (Montagem como domínio) | 1 | Ainda não construída — fora do escopo desta Semana 2. |
| ↳ 6.7 (Captação como domínio, nova) | 1 | Ainda não construída — pós-1.0; o `Lead` provisório (`PLANO_SEMANA_1.md`) segura a demanda até lá. |
| ↳ 6.8 (extração do JS de index.html, nova) | 1 | Ainda não construída — os ratchets de linha/contagem sobre `static/index.html` precisam ser repensados quando a Semana 2 chegar lá. |
| **HIGIENE** | 4 | LP-34, novo (16/09) — clone copia funções de teste da loja-fonte. LP-11 implementado em 15/09 — sai da contagem, fica como registro. Lote único, quando alguém tiver uma tarde livre. |
| **DECIDIDO — fila da 1.0** | 3 | Decisão fechada em 15/09; falta só implementar, agendado para depois de 01/10. |
| **PRODUTO** | 0 | Os oito itens que estavam aqui foram todos decididos em 15/09 — ver "Decisões de 15/09" abaixo. |
| **INFRA** | 8 | Congelados até depois de 01/10/2026. |
| **Total aberto** | **28** | 26 da rodada anterior, menos LP-02 e LP-11 (implementados em 15/09 — saem da contagem de aberto, ficam como registro no lugar), mais LP-31, LP-32, LP-33 e LP-34 (todos de 16/09 — LP-31 do vazamento de tenancy medido em Homologação; os outros três do Aceite 6 da Loja Teste). |

---

## BETA

**LP-02 · CPF de quem assina — decidido em 15/09: AVISAR, NÃO BLOQUEAR. IMPLEMENTADO em 15/09.**
*Destino: BETA — decisão fechada, implementada no mesmo dia.*

**Implementado:** `_cpf_diverge_do_cadastro`/`_confirmar_excecao_cpf_ou_pedir` (main.py), rodando
nos quatro endpoints internos de assinatura (Contrato, Aditivo, Aprovação do PE, Solicitação de
Medição) — o gatilho ClickSign fica de fora de propósito (a assinatura já aconteceu fora, sem
sessão viva pra perguntar nada). `parte='cliente'` compara contra `Cliente.cpf`; `parte='loja'`
compara contra o `Usuario.cpf` de quem está logado assinando. Nova capacidade
`confirmar_excecao_cpf` (auth/perfis.py, concedida a master/gerencial, configurável por loja como
qualquer outra) reusa o mecanismo genérico já existente na tela (`pedirCredenciaisGerente`) — sem
componente novo de UI. Confirmação vira `LogAcaoGerencial` (`acao=confirmar_cpf_divergente`).
Testes: `tests/test_lp02_cpf_divergente.py` (7 casos, os quatro documentos) +
`tests/test_aceite_achado28.py` (6, sem regressão).

**A regra, para quem ler isto sem contexto:** hoje o sistema confere só se o CPF digitado na
assinatura é um CPF matematicamente válido — não se é o CPF da pessoa certa (o cliente daquele
projeto, ou o gerente da loja). A partir de 15/09: quando o CPF digitado não bater com o do
cliente cadastrado, a tela **avisa** e **exige confirmação do gerente** antes de deixar prosseguir.
Não é bloqueio automático.

**Por que não bloquear:** bloquear destrataria os dois casos legítimos mais comuns — procuração e
cônjuge assinando em nome do titular — obrigando um fluxo de exceção só para eles. Avisar +
confirmação do gerente resolve o problema real (alguém assinando sem que ninguém perceba) sem
travar quem tem motivo legítimo para divergir.

**O que a implementação precisa garantir** (para o registro ficar completo, não só o aviso):
o sistema **grava quem autorizou a exceção** — login do gerente, quando, e para qual assinatura.
Sem esse rastro, "avisar" vira "ignorar com um clique" e a regra perde o sentido.

**Histórico:** o ACHADO-28 (validação de dígito) já está no beta2; isto é a camada de conferência
contra o cadastro que ficou pendente dele, decidida agora.

---

**LP-31 · `clonar_loja.py` herda `rede_id` da loja de origem em silêncio — implantação real
precisa que seja parâmetro explícito. Registrado em 16/09, achado durante a medição do
vazamento de tenancy (Homologação, item abaixo). NÃO CORRIGIDO — só registrado, por pedido do
Marcelo.**
*Destino: BETA — as cinco lojas-piloto entram em outubro, e este mecanismo é exatamente o que
vai ser reusado (ou uma variante dele) pra colocá-las de pé.*

**O que foi medido:** `scripts/clonar_loja.py` já tem um argumento `--rede-id` explícito
(`default=None`) e `mod_implantacao_loja.criar_loja_base` o usa corretamente — mas
`aplicar_config_loja` (`mod_implantacao_loja.py:304-308`) reaplica por cima, sem condição
nenhuma, TODOS os campos de `_LOJA_CONFIG` (linha 65-68) do artefato exportado da loja de
ORIGEM — e `rede_id` está nessa lista, junto com `config_financeira_json`, telefone, endereço.
Resultado: o `--rede-id` do CLI é sobrescrito e vira letra morta assim que `--aplicar` roda; a
loja nova SEMPRE herda a rede da loja de origem, mesmo se alguém passar `--rede-id` diferente ou
nenhum. Foi assim que a Loja Teste (`id=15`) nasceu com `rede_id=1`, igual à Inspirium — nesse
caso, correto e documentado (`TAREFA_LOJA_TESTE.md` já listava `rede_id` como campo que "copia",
decisão de 11/09, para o propósito de TESTE). Mas pertencer à mesma rede não é só um rótulo —
implica compartilhar Fórum Orizon e Parceiros de abrangência `rede` com todo mundo daquela rede
(medido no mesmo achado, ver `TAREFA_LOJA_TESTE.md` para o detalhe). Para uma loja-piloto REAL
(Inspirium e Dalmóbile são negócios diferentes), herdar isso da loja usada como origem/template
de configuração é um erro de isolamento, não um detalhe.

**A regra, para quem pegar isto:** `rede_id` do destino tem que ser decisão deliberada de quem
chama o clone/implantação — nunca herança do artefato de configuração. Mesmo padrão já usado
para `cnpj`/`razao_social` (`_EMITENTE_IDENTIDADE`, gated por `permitir_identidade`) — `rede_id`
precisa do mesmo tipo de gate explícito em `aplicar_config_loja`, em vez de viver dentro de
`_LOJA_CONFIG` sem condição. Não implementado — decisão de desenho ainda não tomada (o comentário
do código já registra `rede_id` ombro a ombro com "config financeira, contato, endereço", e não
é disso que se trata).

**LP-32 · Identificação da loja no cabeçalho é pequena demais para quem opera duas lojas.**
*Destino: BETA — ajuste de layout, sem decisão de arquitetura; precisa estar pronto antes das
cinco lojas-piloto.*
Hoje o nome da loja ativa aparece como texto miúdo ao lado do logo "OrizonOne" (verificado em
Homologação, 16/09, Loja Teste). Enquanto existe uma loja só, é cosmético. Com cinco lojas-piloto
simultâneas vira **segurança operacional**: quem atende mais de uma unidade precisa saber em qual
está *antes* de aprovar um desconto ou assinar um contrato — o custo do erro é um ato gerencial
praticado na loja errada. Tratar como selo de contexto com peso próprio, não como legenda do logo.
(Achado do Marcelo no Aceite 6 da Loja Teste, 16/09.)

**LP-33 · Configurador de faixas de comissão aceita salvar sem faixa "sem teto" — a tela diz uma
coisa, o motor faz outra.**
*Destino: BETA — toda loja nova passa por esse configurador na implantação; sem conserto, o
defeito se reproduz cinco vezes nas lojas-piloto.*

**Medido (16/09, bancada):** `mod_provisoes.resolver_comissao_venda` usa `for/else` — se a venda
ultrapassa todas as faixas, nenhum `break` acontece e o `else` aplica `faixas[-1]["pct"]`. Ou
seja, **não há buraco de comissão**: a configuração atual (topo em "venda até 300.000 = 6%") paga
6% também numa venda de 400.000. O dinheiro está certo hoje.

**O defeito é de verdade declarada.** A tela afirma "venda até R$ 300.000" e o motor trata essa
faixa como aberta. Quem configura acredita ter posto um teto; quem vende recebe como se não
houvesse. O próprio default do sistema já tem a forma certa — `mod_provisoes.py`,
`"faixas_comissao": [{"venda_ate": None, "pct": 0.0}]` — é a UI que deixa quebrá-la.

**Conserto decidido pelo Marcelo (16/09):** a última linha do configurador passa a ser **sempre
presente, exige percentual e não permite editar o valor de venda** — ela é, por construção, a
faixa sem teto. `mod_provisoes.validar` ganha a regra correspondente (última faixa com
`venda_ate` nulo), para a garantia não depender só da tela.

**Segundo detalhe do mesmo trecho — decidido em 16/09: muda o RÓTULO, não o código.** A comparação
é `val_liq_mes < ate`, estritamente menor: uma venda de exatamente R$ 100.000 **não** entra na
faixa rotulada "venda até 100.000", cai na seguinte. O Marcelo confirmou que o comportamento do
código é o correto — *"as vendas são 'abaixo de'; o valor colocado é a meta da faixa, atingiu,
sobe de faixa"*. Ou seja, o número digitado é o alvo a **atingir**, e atingi-lo promove. O que
mente é a palavra "até". Conserto: a coluna passa a se chamar **"Vendas abaixo de (R$)"**, com
texto de apoio dizendo que atingir o valor leva à faixa seguinte, e a última linha (fixa, sem
valor editável) se identifica como "acima da última meta". Nenhuma mudança em
`resolver_comissao_venda`.

*Nota (Marcelo, 16/09):* a **meta mensal não participa** do cálculo de faixa — é indicador, para
premiação e estatística de cumprimento no futuro. As faixas não precisam ter relação com ela, e o
fato de o topo (300.000) ser menor que a meta (500.000) não é, por si, inconsistência.


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

### 6.3 — Estoque como domínio real — ainda não construída, 2 itens

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

**LP-18 · Fases independentes, recebimento na Logística e entrada fiscal — decidido em 15/09: o
desenho de tela fechou, a medição de custo confirma que fica na 6.3.**
*Destino: FRONTEIRA / 6.3 — o Marcelo condicionou explicitamente ("a menos que a medição mostre
que é barato"); a medição abaixo mostra que não é.*

**O desenho de tela, fechado:** a divisão em fases abre trilhas que seguem aparecendo ao longo das
etapas, cada uma com etiqueta indicando em que etapa está. No topo, uma tabela das fases com seus
ambientes e sua etapa corrente; ao selecionar uma linha, abre abaixo o painel da etapa corrente
daquela fase.

**A medição pedida, feita em 15/09 — lendo `database.py`, não estimando de memória:**
- **"Fase" já existe como conceito maduro, não é preciso inventar.** `ParcelaProjeto` (tabela
  `parcela_projeto`) já é "grupo de ambientes que percorre o ciclo de forma independente", em uso
  desde a Fatia 2 (aprovação, retenção, cronograma). `ParcelaAmbiente` (`parcela_ambiente`) já é a
  associação N:N fase↔ambiente, com o valor de contrato do ambiente já rateado e gravado
  (`valor_ambiente`). **Não é preciso desenhar "fase = conjunto de ambientes" do zero — já existe e
  já roda em produção.**
- **`CicloLogistico` (Expedição/recebimento) já tem `parcela_id`** — a tabela já aceita operar por
  fase (`NULL` = projeto inteiro, modo legado). Mas hoje é **uma linha agregada por fase** (um
  status, uma data, uma NF-e) — não tem granularidade de item/ambiente dentro da fase. Sem isso,
  não dá para "conferir volumes" (o que a nota diz × o que chegou item a item).
- **`DocumentoFiscal` (a NF-e) NÃO tem `parcela_id` nem ligação a ambiente** — hoje é só por
  projeto inteiro. Emitir nota por fase exige adicionar essa referência, do mesmo jeito que
  `CicloLogistico` e `ConciliacaoPeFase` já fazem (há precedente direto: `ConciliacaoPeFase` já
  liga `parcela_id` + `pool_ambiente_id` juntos, para a decisão de conciliação da AF2 — a mesma
  forma que a Conferência de Volumes precisaria, só que para outro propósito).
- **Conclusão da medição:** nem "de graça", nem "do zero". A CAMADA de fase já existe e é madura;
  ligar `DocumentoFiscal` a ela é trabalho incremental (mesmo padrão já usado duas vezes no
  sistema); a parte cara de verdade é a Conferência de Volumes item a item — não existe hoje
  **nenhuma tabela** de itens/linhas recebidas para comparar contra a nota, nem em
  `CicloLogistico` nem em `DocumentoFiscal`. É essa peça, não a estrutura de fase, que sustenta a
  classificação como FRONTEIRA em vez de conserto pontual.

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

**LP-11 · Dois lançamentos financeiros automáticos que nunca ligam — decidido em 15/09: REMOVER.
REMOVIDO em 15/09.**
*Destino: HIGIENE — é limpeza de código morto, não decisão de arquitetura nem de produto.*

**Implementado:** `execucao_montagem` e `pagamento_fabrica` saíram de `mod_contabil.EVENTOS`.
Os três chamadores que só existiam em teste (`test_eventos.py`, `test_fase_b2_eventos.py`,
`test_contabil_ajustes_excepcionais.py`) passaram a usar `efetivar_provisao(...,
forma_pagamento="direto")` — o mesmo débito/crédito que os eventos mortos tinham
(`2.1.04.02`/`2.1.04.06` × `1.1.01`), agora pelo caminho que já lança as duas pernas certas.
`test_eventos_mortos_removidos_por_decisao` (já existia, mesmo padrão do ACHADO-04/05) ganhou os
dois novos `assert ... not in mc.EVENTOS`. Suíte contábil/folha/provisão (80+41 testes) sem
regressão.

**A regra:** os eventos `execucao_montagem` e `pagamento_fabrica` saem da tabela `EVENTOS`. O
"Efetivar" genérico (restaurado pelo item 6 do ACHADO-33) já cobre os dois casos com a
contabilização CORRETA (as duas pernas — despesa e caixa — não só uma). Manter os dois eventos
mortos ao lado de um caminho que já funciona é risco sem benefício: algum dia alguém liga um dos
dois sem saber que fazem só metade do lançamento certo, e o erro contábil que toda a auditoria
tentou evitar volta pela porta dos fundos.
*Decisão anterior (01/09, medição):* os dois só disparavam em teste, cada um faria um lançamento
incompleto se ligado como estava — a decisão de 15/09 fecha o que ficou em aberto ali.

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

**LP-34 · O clone de loja copia também o lixo da loja-fonte.**
*Destino: HIGIENE — não é defeito de código; é passo de procedimento de implantação mais uma
limpeza pontual na loja-template.*
A Loja Teste nasceu com a função **"Teste Novo"** (resumo vazio), que existe na Inspirium por ter
sido criada em algum teste antigo. O clone foi fiel — o problema está na fonte. Como a Inspirium é
a loja-template das cinco implantações-piloto, cada função de teste que sobrar lá nasce cinco
vezes. Dois passos: (1) limpar as funções de teste da Inspirium antes da primeira implantação
real; (2) acrescentar "conferir funções da loja-fonte" ao roteiro de implantação
(`docs/db/TAREFA_LOJA_TESTE.md`). (Achado do Marcelo no Aceite 6, 16/09.)


---

## PRODUTO

**Nenhum item aberto.** Os oito itens que estavam aqui (LP-01, 02, 09, 11, 12, 14, 18, 24) foram
todos decididos pelo Marcelo em 15/09 — ver `docs/db/DECISOES_PENDENTES.md` para o histórico da
folha de decisão que levou a cada uma. Nenhum voltou pra PRODUTO: LP-02 → BETA; LP-11 → HIGIENE;
LP-01, LP-12, LP-14 → DECIDIDO/fila da 1.0 (abaixo); LP-18 → FRONTEIRA/6.3; LP-09 e LP-24 → recusa
decidida, foram para "Fechados".

---

## DECIDIDO — fila da 1.0

Decisão já tomada em 15/09; falta só implementar, de propósito depois de 01/10/2026 — não cabe num
ciclo de estabilização, e ninguém precisa decidir mais nada aqui, só agendar.

**LP-01 · Data combinada da medição — decidido em 15/09: GUARDAR AS DUAS.**
*Destino: DECIDIDO/fila da 1.0.*

**A regra:** a data PREVISTA (dada na venda) e a data COMBINADA (acertada de fato com o cliente,
no momento de Solicitar Medição) coexistem — nenhuma substitui a outra. A combinada é a que entra
no documento que o cliente assina.

**Por quê:** a diferença entre "prometido" (previsto na venda) e "combinado" (a data real
acertada) é um indicador de operação — mede o quanto a operação desvia da promessa comercial — e
esse indicador só existe se as duas datas forem guardadas desde o início. Guardar só uma das duas
descarta essa informação de forma irrecuperável (não dá pra reconstruir depois).

**O que ainda falta resolver na implementação** (não é decisão nova, é escopo já registrado):
quando o projeto está desmembrado em fases, cada fase tem sua própria data combinada — não é um
campo único no projeto. E a data combinada, ao ser gravada, precisa **atualizar a programação
automática** que o cronograma padrão já montou na assinatura do contrato — não é só um campo
solto; é uma entrada que substitui uma previsão que o sistema já calculou sozinho. Medir onde essa
programação vive e quem mais a lê antes de escrever nela é o primeiro passo de quem pegar isto.

---

**LP-12 · Liberação financeira por fase — decidido em 15/09: DOIS CRITÉRIOS, um por gate.**
*Destino: DECIDIDO/fila da 1.0.*

**A regra:** a liberação por fase usa critérios DIFERENTES em cada um dos dois gates — não um
critério único para os dois:
- **Na aprovação do PE junto ao cliente:** valor de contrato da fase.
- **Na aprovação financeira (AF1/AF2):** mantém o padrão atual — comparação contra o CFO (Custo
  Fábrica/Obra), sem mudar.

**Por quê:** a divisão em fases reparte o TRABALHO (o que é aprovado e liberado em cada momento),
mas não muda o padrão de CONTROLE financeiro, que continua baseado nos valores dos ambientes —
mudar o critério do gate financeiro só porque o projeto virou multi-fase misturaria uma decisão de
processo comercial (como apresentar a fase ao cliente) com uma decisão de risco financeiro (como o
Financeiro decide liberar dinheiro), que são perguntas diferentes.

**O que já estava decidido antes, e continua valendo:** as contas de provisão NÃO se desmembram
por fase — a contabilidade segue consolidada por projeto. Só a camada de acionamento (quando cada
gate libera) passa a operar por fase.

---

**LP-14 · Aviso de etapa concluída, com responsável — decidido em 15/09, com desenho.**
*Destino: DECIDIDO/fila da 1.0 — pacote de execução em
`docs/db/TAREFA_RESPONSAVEIS_POR_ETAPA.md`.*

Decisão fechada: um Configurador de Responsabilidades (aba nova em Config), amarrando etapa→papel,
com exceção por pessoa específica onde precisar, notificando por tela e chat ao concluir (sem
WhatsApp por ora). O pacote completo — incluindo a medição de que metade do mecanismo já existe
(`_ETAPA_PAPEL`, a mesma tabela que já dispara comissão) — está no arquivo dedicado, porque o
desenho tem peças demais para caber numa entrada desta lista.

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

- **Fórum Orizon mostra o nome da loja de quem postou, cross-loja dentro da mesma rede.**
  CONFIRMADO COMO DESENHO, não defeito — 16/09, investigação do vazamento de tenancy em
  Homologação (`pdm2026` enxergando a Loja Teste). `chat/core.py::criar_debate`/`listar_debates`
  resolvem `rede_id` pela loja ATIVA do ator (`mod_chat._rede_da_loja`), não pelo `rede_id` do
  usuário — por isso qualquer usuário de qualquer loja de uma rede vê o Fórum Orizon inteiro,
  `loja_nome` incluído, nos dois sentidos. Documentado no próprio código (`chat/core.py`,
  docstring de `criar_debate`) e em `docs/db/TAREFA_LOJA_TESTE.md`. Não reabrir sem motivo novo.
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
- **LP-09 · Várias versões do Projeto Executivo — RECUSADO, decidido em 15/09.** Não é esquecimento
  nem falta de tempo: é recusa deliberada. **A regra:** o Projeto Executivo aprovado não tem
  versões concorrentes. Tem REVISÕES — e no fim existe uma versão final assinada, que é a que se
  executa. O modelo "vários orçamentos, um vence" que já existe na venda não é trazido para cá.
  **Por quê:** revisão pós-aprovação tem regras próprias que o modelo da venda não precisa
  considerar (o que fazer com material já comprado da fábrica, por exemplo) — importar um
  mecanismo pensado para outro momento do processo criaria mais problema do que resolveria. Quem
  reabrir isto no futuro precisa de um motivo novo, não só "seria bom ter as duas opções" — a
  pergunta já foi feita e respondida.
- **LP-24 · Testemunha na Aprovação do Projeto Executivo — NÃO PRECISA, decidido em 15/09.** Não é
  esquecimento de quem programou a funcionalidade em 2026: é recusa deliberada, agora confirmada.
  **A regra:** o Contrato pede testemunha porque CRIA uma obrigação (compromisso financeiro/legal
  entre as partes). A Aprovação do Projeto Executivo é ACEITE TÉCNICO — o cliente confirma que o
  projeto está como deveria estar, não assume uma obrigação nova. Não gerar obrigação é a diferença
  que justifica não pedir testemunha ali. A ausência, que soava como lacuna quando descoberta
  (Passo 0 do ACHADO-69), estava correta desde o início.
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
