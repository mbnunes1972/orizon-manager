# Tarefa B — Lead de verdade e o painel do SAC

> **Camada 4 · TRABALHO EM ANDAMENTO.** Descartável quando fechar.
> Aberta em 24/09/2026, depois do fechamento do LP-39 passo 1.
> Irmã da **Tarefa A** (`TAREFA_TRIAGEM_CLIENTE_CONHECIDO.md`, ainda não aberta): A muda o
> FLUXO de quem já é cliente e tem migration; B muda o RÓTULO e a VISIBILIDADE e **não tem
> DDL**. B primeiro, porque é o que incomoda na tela hoje.

## Estado

**B1 (rótulo) + B2 (referral) — FECHADO em 24/09** (`git log --grep="TAREFA-B"`). Portão alvo
(`tests/test_tarefa_b_lead_e_painel_sac.py` + `tests/test_triagem_fila.py` +
`tests/test_chat_externo.py` + `tests/test_triagem_auto.py` + `tests/test_chat_ciclo_eventos.py`
+ `tests/test_chat_wa.py` + `tests/test_lp39_roteamento_loja.py`): verde. Um teste
pré-existente precisou de ajuste — `test_segmento_reconhecido_materializa_com_sac_responsavel`
(`tests/test_triagem_fila.py`) fixava a regra ANTIGA (todo contato sem Cliente virava Lead);
B2 substitui essa regra (Lead é só quem veio de campanha) e o teste passou a fixar a nova.

**B3 (sinalização) + B4 (ordenação) — em andamento.**

## O problema, nas palavras do Marcelo (24/09)

> "Todas as mensagens que chegam pela triagem estão sendo marcadas como lead, ainda que nem
> sempre sejam. (...) O lead pode entrar de uma campanha de impulsionamento, por um clique num
> anúncio do Google ou do Instagram, esses são tipicamente leads."

E, sobre o SAC:

> "O SAC tem que ter sinalização clara. (...) Quero um contador como funciona no WhatsApp real:
> conversa sem resposta, o funcionário vê uma linha no contato."

## O que foi MEDIDO antes de escrever (24/09)

1. `chat/triagem.py::triagem_materializar` monta o título `"Lead — %s"` nos **dois** ramos —
   contato novo e cliente reconhecido. O prefixo é literal, não derivado de nada.
2. O mesmo ramo **procura** o Cliente pelo telefone (`_cliente_por_telefone`), usa só o nome, e
   **não grava `conv.cliente_id`**. A conversa nasce sem âncora, sabendo quem é.
3. Linha de `Lead` só nasce quando o telefone NÃO bate com Cliente. Captação (`main.py:4037`)
   lista `Lead`, então cliente antigo nunca poluiu Captação — o que polui é o TÍTULO.
4. `chat/externo.py::iter_mensagens_whatsapp` extrai `from`, `texto`, `id`, `ref`, `nome` e
   **descarta o resto do payload** — inclusive `messages[].referral`, que é o bloco que a Meta
   manda quando a mensagem veio de um clique em anúncio (Click-to-WhatsApp): id do anúncio,
   `source_type`, `source_id`, `headline`, `body`. Mesma família do `phone_number_id` do LP-39:
   o sinal chega e é jogado fora.
5. `chat/core.py::serializar_conversa` JÁ devolve `nao_lidas` (por usuário, via
   `_conta_nao_lidas`) e JÁ devolve `pendente` (última mensagem com `autor_usuario_id IS NULL`
   = cliente esperando resposta de alguém da loja, independente de quem olha).
6. `static/index.html` JÁ renderiza `nao_lidas` como `.atd-nl` em dois pontos da inbox.
   `pendente` só aparece como **filtro** ("Pendentes" na barra de chips) — não como marca na
   linha.
7. `chat/core.py::_atendimento_meta` JÁ calcula o estado da janela de 24h, com `fechando`
   (< 2h para fechar). A lista NÃO ordena por isso.
8. O contador do canal Triagem (`ocPollBadge`/`_ocFilaAtualizar`, poll de 45s) conta a **fila
   sem dono** — não conta "quantas esperam resposta".

## Regra de negócio (decisão do Marcelo, 24/09)

- **Lead é quem veio de campanha.** `referral` presente no payload → Lead de verdade, com o
  canal vindo do próprio anúncio → entra em Captação.
- **Cliente cadastrado nunca vira Lead.**
- **Desconhecido sem anúncio nasce como ATENDIMENTO do SAC**, não como Lead. O SAC promove a
  Lead quando for o caso (botão — fora desta tarefa, anotar).
- O SAC continua **central**: o segmento indica, o SAC distribui. `SegmentoConfig.
  responsavel_funcionario_id` continua existindo e SEM USO — peça pronta para quando a
  distribuição virar automática. Não ligar nesta tarefa.

### Aviso registrado: anúncio do Google não manda `referral`

Só o anúncio da Meta (Facebook/Instagram) com destino WhatsApp produz `referral`. Anúncio do
Google que leva a um link `wa.me` chega como mensagem comum. O reconhecimento, se for desejado,
passa por padronizar o TEXTO pré-preenchido do link por campanha — decisão de campanha, não de
código. Não implementar adivinhação por heurística de texto aqui.

## O conserto

### B1 — parar de rotular tudo como "Lead"

1. `triagem_materializar`: título passa a ser o **nome do contato**, sem prefixo.
2. Quando o Cliente foi reconhecido, gravar `conv.cliente_id = cli.id` (a informação já está na
   mão e está sendo descartada).
3. O selo da linha é DERIVADO, não escrito no título: `lead_id` preenchido → "Lead";
   `cliente_id` preenchido → "Cliente"; nenhum dos dois → "Contato". Derivar em
   `serializar_conversa`, campo novo no JSON (sem coluna).

### B2 — `referral`: o lead de campanha

4. `iter_mensagens_whatsapp` passa a extrair `referral` do `msg` e devolvê-lo no dicionário
   normalizado (chave `referral`, `None` quando ausente).
5. O webhook repassa a `processar_entrada`, que repassa adiante.
6. **Sem DDL**: quando há `referral` e o telefone não bate com Cliente, o `Lead` nasce **na
   hora da entrada**, não na materialização — o clique no anúncio JÁ É o evento de lead.
   `canal` = origem do anúncio; o bloco `referral` inteiro vai em `Lead.dados_json` com
   `template='whatsapp_referral'`.
7. `triagem_materializar` passa a PROCURAR Lead existente por (telefone, loja) antes de criar —
   liga `conv.lead_id` ao que já existe. Isso também deduplica lead repetido, que hoje nasce
   novo a cada primeira mensagem.
8. Sem `referral` e telefone desconhecido: **não cria Lead**. Conversa nasce como atendimento,
   selo "Contato".

### B3 — sinalização do SAC

9. A linha do item da inbox passa a mostrar a marca de **aguardando resposta** quando
   `pendente` é verdadeiro (hoje o dado existe e só filtra). Marca visual na linha, no mesmo
   lugar onde já vive `.atd-nl`.
10. O contador do canal **Triagem** passa a somar dois números distintos, não um só: contato
    sem dono (o de hoje) **+** conversas `pendente` da loja. Apresentação: um número; o
    critério fica documentado no código.
11. **Antes de mexer em `.atd-nl`, MEDIR em campo** se o contador de não-lidas já aparece como
    o Marcelo espera. Ele é por usuário e some quando quem olha já leu — pode estar correto e
    parecer ausente. Não reconstruir o que já funciona.
12. `ocAtualizarBadges` é o consumidor da partição única de Comunicação
    (`_ocEhInterno`/`_ocEhAtendimento`/`_ocEhMural`, TAREFA_TRIAGEM_E_CONTADOR.md Item 2). Se
    esta tarefa precisar de um predicado novo, ele nasce AO LADO desses três, nunca uma
    quarta cópia divergente.

### B4 — ordenar pelo que expira

13. Na lista de Atendimentos, conversa `pendente` ordena por **janela restante** (menor
    primeiro), não por data da última mensagem. `_atendimento_meta` já entrega o estado.
14. Escalonamento (subir ao topo / mudar de cor / notificar gerencial abaixo de X horas) é
    decisão do Marcelo e **não entra aqui** — anotar como pergunta aberta no fim do documento.

## Prova

- mensagem com `referral` de telefone desconhecido → nasce `Lead` com `canal` do anúncio e
  `dados_json` com o bloco; a conversa materializada tem `lead_id` apontando pra ELE (não um
  segundo Lead);
- mensagem SEM `referral` de telefone desconhecido → **nenhum** `Lead`; conversa com
  `lead_id` nulo e `cliente_id` nulo;
- mensagem de telefone que é Cliente → `cliente_id` gravado, `lead_id` nulo, título sem
  "Lead —";
- segunda mensagem do MESMO telefone de anúncio → não cria Lead novo;
- `serializar_conversa` devolve o selo derivado certo nos três casos;
- conversa cuja última mensagem é externa → `pendente` verdadeiro e a marca aparece no item;
- ordenação: duas conversas pendentes, a de janela menor vem primeiro.

## Regras deste lote

1. **Sem DDL.** Se aparecer um caso que exija coluna, PARAR e reportar — provavelmente é da
   Tarefa A.
2. Não abrir achado novo — anotar e reportar.
3. Testes alvo verdes por commit; suíte completa ao fim.
4. `TAREFA-B` na mensagem do commit.
5. Não ligar `SegmentoConfig.responsavel_funcionario_id`.

## Perguntas abertas (para o Marcelo, não decidir sozinho)

- Escalonamento por janela: o que acontece quando falta pouco para fechar as 24h?
- O botão "promover a Lead" do SAC: onde vive e quem pode?
