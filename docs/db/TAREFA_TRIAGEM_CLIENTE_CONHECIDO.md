# Tarefa A — quem já é cliente não é tratado como lead

> **Camada 4 · TRABALHO EM ANDAMENTO.** Descartável quando fechar.
> Aberta em 24/09/2026, depois do fechamento da **Tarefa B**
> (`TAREFA_LEAD_E_PAINEL_SAC.md`, commits 070a32b + a25c58e).
> B arrumou o RÓTULO e a VISIBILIDADE sem DDL. A muda o FLUXO e **tem migration**.

## Estado

**Migração + modelo — FECHADO em 24/09** (`git log --grep="TAREFA-A"`). Revisão
`a518e96c1cee` (`Revises: d2544ffcba33`), só a coluna `triagem_entradas.dialogo_json`, sem
backfill. `tests/test_schema_boot_estavel.py` + `tests/test_schema_fk_integridade.py`: verdes
(`init_db()` e `alembic upgrade head` continuam produzindo o mesmo schema).

**Fluxo (itens 2-5) — FECHADO em 25/09** (`git log --grep="TAREFA-A"`). `chat/externo.py`:
`processar_entrada` cria `dialogo_json={"estado": "aguardando_reconhecimento"}` e chama
`enviar_reconhecimento_cliente` (P1) só quando o telefone bate com `Cliente` DA loja resolvida
(LP-39); resto (número desconhecido) segue com `dialogo_json=None`, fluxo de hoje intacto.
`chat/triagem.py`: `registrar_resposta_triagem` passa a checar `dialogo_json` antes do caminho
antigo — se presente, despacha pro novo `_registrar_resposta_dialogo` (P1→P2/P3→menu, conforme o
`estado`). `SEGMENTO_PROJETO_DEFINIDO` (sentinela interno) sinaliza pra `triagem_materializar`
entrar na conversa do PROJETO em vez de abrir grupo novo; "ramo do comercial" (sem consultor, ou
consultor recusado em P3) materializa normal com segmento `comercial` — sem tocar
`SegmentoConfig.responsavel_funcionario_id`, como pedido. Sweep de 2min (`varrer_triagem_vencida`)
já cobria qualquer `dialogo_json` pendente sem mudança — materializa com `SEGMENTO_TRIAGEM`
igual a antes, em qualquer estado do diálogo.

Nove das dez provas (a 10ª é A5) em `tests/test_tarefa_a_triagem_cliente_conhecido.py`. Portão
`-k "triagem or externo or chat or rotear or lead"`: 155 passed (146 pré-existentes + 9 novas,
3 delas ajustadas por usarem `Cliente` real como âncora de loja — passam a receber P1 em vez do
menu direto, mesmo comportamento novo e correto).

**A5 (botão promover a Lead) — FECHADO em 25/09** (`git log --grep="TAREFA-A"`). Sem migration
nova: `Conversa.lead_id`/`Lead` já existiam (PLANO_SEMANA_1.md, 14/09). `chat/core.py`:
`promover_lead(db, conversa, ator_id)` cria o `Lead` a partir do `ConversaParticipanteExterno` da
própria conversa (nome/telefone ou email conforme `meio`), liga `conversa.lead_id`, registra o
evento na timeline — a conversa não se move, nenhuma mensagem muda de lugar. Recusa (`ValueError`)
quando a conversa já é Lead, já é Cliente, é mural/fórum, ou não tem contato externo nenhum.
Endpoint `POST /api/comunicacao/conversas/<id>/promover_lead` (mesma família de
transferir/urgente/concluir — participante da conversa ou gerência). Botão "Promover a Lead" no
action-bar do Orizon Chat (`static/index.html`, `oc-lead-btn`/`ocPromoverLead`), visível só quando
`contato_tipo === 'contato'` (nem Lead nem Cliente). Prova 10 em
`tests/test_tarefa_a5_promover_lead.py` (unidade, incl. as 3 recusas) +
`tests/test_atendimentos_ui.py::test_endpoint_promover_lead` (endpoint + tenancy). Portão
`-k "triagem or externo or chat or rotear or lead or atendimento or achado36"`: 186 passed.

`tests/test_aceite_achado36.py` recalibrado (2ª vez nesta tarefa): 3 hunks puros no
`static/index.html` (botão no cabeçalho, +4; toggle de visibilidade em `_ocSetHeaderExtras`, +5;
`ocPromoverLead`, +19) — a faixa financeiro (+4, só o 1º hunk é anterior) e a 1ª sub-faixa do
ciclo (`abrirProjeto`, +4, mesmo motivo) deslocam pouco; as 5 sub-faixas seguintes do ciclo, que
vêm DEPOIS dos 3 hunks, deslocam +28 (4+5+19). Contagem total de `showToast(..., true)` sobe de
147 pra 149 (os 2 sites novos de `ocPromoverLead`).

## O problema

Hoje toda entrada externa sem conversa casada recebe o MESMO tratamento: o menu de 7 segmentos,
independentemente de quem mandou. Cliente com contrato assinado, no meio de uma obra, recebe do
robô um "responda com o NÚMERO do assunto" como se a loja não o reconhecesse — e a conversa
nasce solta, sem ligação com o projeto dele.

B já fez a parte barata: o título deixou de dizer "Lead", `conv.cliente_id` passou a ser
gravado, e Lead virou coisa de campanha. O que sobrou é o fluxo.

## A regra (decisão do Marcelo, 24/09)

Número **desconhecido**: como hoje — menu de segmentos, e Lead só se vier de campanha (B).

Número de **Cliente cadastrado**: não recebe o menu. Recebe reconhecimento:

1. **P1** — "É sobre o seu projeto em andamento, ou outro assunto?"
2. Resposta **projeto**:
   - **1 projeto ativo** → a mensagem cai na conversa DAQUELE projeto;
   - **2+ projetos ativos** → **P2**: o robô lista e o cliente escolhe;
   - **0 projeto ativo** → é "outro assunto" por definição → segue o ramo 3.
3. Resposta **outro assunto** → menu de segmentos normal (o de hoje). **Não** vira Lead:
   já é Cliente.
4. Com o projeto definido, **P3** — confirmação do responsável:
   - projeto TEM consultor → "seu consultor é Fulano, certo?" → **sim**: segue com ele;
     **não**: ramo do comercial (abaixo);
   - projeto SEM consultor → ramo do comercial.
5. **Sem resposta em 2 min** (a varredura de hoje): materializa com segmento `triagem`,
   SAC distribui. Vale em qualquer estado do diálogo.

### O "ramo do comercial", reconciliado com o SAC central

O Marcelo disse duas coisas em ordem: primeiro "transfere ao comercial", depois "não vejo
problema em centralizar no SAC — ele redistribui, a triagem indica o segmento e o SAC faz a
primeira fase humana". A segunda é posterior e mais ampla, então **manda**:

> "ramo do comercial" = materializa com **segmento `comercial`** e responsável **SAC**, como
> qualquer outra saída de triagem. Ninguém é atribuído direto ao comercial.

`SegmentoConfig.responsavel_funcionario_id` continua existindo e **sem uso** — não ligar aqui.
Se o Marcelo corrigir esta reconciliação, o conserto é de uma linha; está isolado de propósito.

### O que o robô nomeia, e o que não nomeia

Nomear pessoa ao cliente só em **P3** (a confirmação do consultor), que foi o que ele pediu. No
encaminhamento ao comercial o robô **não** nomeia ninguém: o responsável pode mudar antes de
alguém responder, e prometer nome errado é pior que não prometer.

## Por que isto exige DDL (e o que exatamente)

Hoje o estado do diálogo é DERIVADO por contagem: `ja_reformulou` conta linhas de
`EnvioExterno.triagem_id` (TAREFA_TRIAGEM_E_CONTADOR.md, Item 1). Contagem só funciona quando a
sequência é única. Aqui a sequência **ramifica** (P1 → P2 ou P3 ou menu), então contar não diz
QUAL pergunta foi feita. Derivar isso de novo seria adivinhação — a família de defeito que este
projeto persegue.

**Uma coluna, em migração** (R1 respeitado — R1 proíbe DDL FORA de migração, não a migração):

    triagem_entradas.dialogo_json  TEXT NULL

Forma documentada no modelo (mesmo espírito de `Lead.dados_json`):

    {"estado": "aguardando_reconhecimento" | "aguardando_projeto" |
               "aguardando_consultor" | "aguardando_segmento",
     "projeto": "<nome_safe>"        # preenchido ao sair de P2 (ou direto, com 1 projeto)
     "consultor_funcionario_id": <int>}

`NULL` = entrada anterior a esta tarefa, ou fluxo de desconhecido: comportamento de hoje,
intacto. **Nenhum backfill** — a ausência já significa a coisa certa.

## O conserto

1. **Migração** com a coluna acima. Nada mais nela.
2. `processar_entrada`: quando o telefone bate com Cliente da loja resolvida, em vez de
   `enviar_pergunta_triagem` manda **P1** e grava `estado=aguardando_reconhecimento`.
3. O hook de resposta JÁ existe e não precisa ser inventado: `processar_entrada` acha a
   `TriagemEntrada` pendente por (meio, remetente, status) e chama
   `registrar_resposta_triagem`. Essa função passa a **ler `dialogo_json` e interpretar
   conforme o estado** — reconhecimento, escolha de projeto, confirmação de consultor, ou
   segmento (o de hoje).
4. Resposta não reconhecida em qualquer estado: **mesma regra de hoje** — reformula UMA vez
   (`ja_reformulou` continua valendo, agora por estado), depois deixa vencer pela varredura.
5. `triagem_materializar` ganha o ramo "projeto definido": em vez de criar grupo novo, entrega
   na conversa do projeto (`get_or_create_conversa_projeto`) e não cria Lead nenhum.
6. **A5 (decidido em 24/09, veio da pergunta aberta da Tarefa B)**: botão **promover a Lead**,
   na tela do usuário SAC. Cria o `Lead` a partir de uma conversa de contato desconhecido que
   não veio de campanha, liga `conv.lead_id` e mantém a conversa onde está.

## Prova

- Cliente com 1 projeto ativo responde "projeto" → mensagem cai na conversa DAQUELE projeto,
  nenhum grupo novo, nenhum Lead;
- Cliente com 2 projetos ativos → P2 é enviada e a escolha entrega no projeto escolhido;
- Cliente com 0 projeto ativo responde "projeto" → cai no ramo 3 (menu), sem erro e sem loop;
- Cliente responde "outro assunto" → menu de segmentos, materializa com o segmento escolhido,
  `lead_id` nulo e `cliente_id` gravado;
- projeto sem consultor → materializa com segmento `comercial` e responsável SAC;
- cliente responde "não" em P3 → mesmo destino do caso anterior;
- silêncio em qualquer estado → a varredura de 2 min materializa com segmento `triagem`;
- número DESCONHECIDO → nada muda: menu de hoje, `dialogo_json` nulo;
- reentrega do mesmo `wamid` em qualquer estado → no-op (idempotência de hoje preservada);
- botão promover a Lead: conversa de contato vira Lead, `conv.lead_id` ligado, conversa não se
  move.

## Regras deste lote

1. A migração é UMA e só adiciona a coluna. Qualquer outra necessidade de DDL: PARAR e reportar.
2. Não abrir achado novo — anotar e reportar.
3. Testes alvo verdes por commit; suíte completa ao fim, rodada pelo procedimento novo do
   `PLANO_SEMANA_1.md` (destacada com `nohup setsid`, acompanhada com
   `timeout N tail -f --pid=<pid>`).
4. `TAREFA-A` na mensagem dos commits.
5. Não ligar `SegmentoConfig.responsavel_funcionario_id`.

## Pergunta aberta (do Marcelo, ainda sem resposta — não entra aqui)

- Escalonamento da janela de 24h: o que acontece quando falta pouco para fechar? (sobe ao topo,
  muda de cor, notifica gerencial?) Hoje não acontece nada; a Tarefa B só passou a ORDENAR por
  janela restante.
