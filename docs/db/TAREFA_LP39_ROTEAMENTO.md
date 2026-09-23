# Tarefa — LP-39, passo 1: quem recebeu decide a loja

> **Camada 4 · TRABALHO EM ANDAMENTO.** Descartável quando fechar.
> Aberta em 23/09/2026. Executa a primeira fatia do **LP-39** (`LISTA_PARALELA.md`), que é a
> única BETA com evidência de campo repetida — três vezes em dois dias.

## Por que agora, e não em outubro

Medido em campo três vezes: 22/09 (lead caiu na Loja Teste), 23/09 00h37 (mesma conversa) e
23/09 15h42 (mensagem nova entrou na conversa 31 da loja 15, sem passar pela triagem). **Enquanto
isto não fechar, qualquer teste de triagem, de janela de 24h ou da tarja de entrega falhada está
sendo feito contra um roteamento que entrega no lugar errado** — mede-se o sistema errado e
conclui-se errado, que é o defeito mais caro que este projeto conhece.

## O passo 1 não precisa de DDL, nem da Meta, nem do `phone_number_id`

A regra do Marcelo (22/09) é: **quem recebeu a mensagem decide a loja**; depois o telefone
cadastrado dentro dela; depois a triagem daquela loja; e conversa existente só vale dentro da
mesma loja. Hoje `_loja_da_entrada` (`chat/externo.py`) faz quase o contrário:

1. cliente cadastrado → a loja DELE;
2. `NumeroConectado` único na instalação → a loja do número;
3. primeira loja por id.

**Enquanto existir um único `numero_conectado`, o degrau 2 JÁ É "quem recebeu"** — ele só está
abaixo do cliente. Inverter a ordem entrega a regra do Marcelo hoje, sem coluna nova e sem
depender do payload da Meta. Quando o `phone_number_id` entrar (passo 2), ele generaliza o mesmo
degrau para N números; a ordem não muda mais.

## O conserto

1. **`_loja_da_entrada`** — ordem nova: (a) dono do número que recebeu — hoje, o
   `NumeroConectado` único; (b) cliente cadastrado; (c) primeira loja. Manter o comportamento
   atual como fallback explícito quando não houver número conectado nenhum.
2. **`_rotear_com_candidatos`** — passa a receber a loja e a **filtrar as candidatas por ela**.
   Sem isso, o passo 1 não resolve nada: a conversa antiga de outra loja continuaria vencendo
   antes de qualquer decisão de loja.
3. **`processar_entrada`** — resolve a loja ANTES de rotear e repassa ao roteamento. É a inversão
   de ordem que dá nome a esta tarefa.
4. **Os outros dois chamadores do roteamento** (`chat/core.py::iniciar_conversa_externa` e o
   segundo ponto em `chat/externo.py`) continuam funcionando: o primeiro já compara
   `conv.loja_id != loja_id` depois de rotear e cria conversa nova quando diverge — com o filtro,
   essa comparação vira redundância inofensiva. Conferir o segundo antes de mexer.

## O que muda de comportamento, dito antes de acontecer

Com um número só na instalação, **toda entrada externa passa a cair na loja dona desse número**
(hoje, a loja 1). Conversas que hoje vivem na Loja Teste param de receber mensagem nova — elas não
somem, apenas deixam de ser o destino. Em Homologação isso é o efeito desejado. **Antes de subir
para Produção, confirmar que o `numero_conectado` de lá aponta para a loja certa** — se apontar
para a loja errada, a inversão manda tudo para a loja errada com mais convicção do que hoje.

## Prova

- entrada de um telefone que é Cliente da loja B, chegando pelo número da loja A → **vai para a
  loja A** (é o caso do Marcelo, medido três vezes);
- entrada de telefone com conversa existente na loja B, chegando pelo número da loja A → **nasce
  triagem na loja A**, a conversa da loja B não captura;
- entrada de telefone com conversa existente na MESMA loja → continua caindo nela (não se cria
  conversa duplicada);
- sem `numero_conectado` nenhum → comportamento de hoje, intacto.

## Regras deste lote

1. Não abrir achado novo — anotar e reportar.
2. Testes alvo verdes por commit; suíte completa ao fim.
3. `LP-39` na mensagem do commit.
4. Passo 2 (coluna `phone_number_id`, extração do payload, saída por loja) é outra tarefa e tem
   DDL — não entra aqui.
