# Tarefa — Medição: por que nenhuma mensagem do WhatsApp chega ao Orizon

> **Camada 4 · TRABALHO EM ANDAMENTO.** Medição, não conserto. Descartável quando fechar.

**Data:** 2026-09-17
**Sintoma relatado pelo Marcelo:** o app está **configurado no Meta**, e **nenhuma mensagem chegou
ao Orizon** em Homologação. Nunca.
**Prazo:** o chat precisa receber lead real em **20/09**. Esta medição é o caminho crítico.

**Esta tarefa é SÓ MEDIÇÃO. Não configure token, não mude env, não reinicie serviço, não altere o
proxy.** Meça, reporte, espere. Metade das respostas está no painel do Meta, que só o Marcelo vê —
consertar de um lado sem saber o outro é chute.

---

## O mecanismo, para a medição ser dirigida e não uma varredura

Duas rotas em `main.py`, ambas **não autenticadas** (quem chama é a Meta), as duas em
`/webhooks/whatsapp`:

**`GET /webhooks/whatsapp`** — o handshake de verificação da Meta. Compara
`hub.verify_token` com a variável de ambiente **`ORIZON_WA_VERIFY_TOKEN`** e devolve o
`hub.challenge`. **Sem a variável, responde 403** — e a Meta não consegue nem validar o webhook.

**`POST /webhooks/whatsapp`** — a entrega das mensagens. Três portões, nesta ordem:

1. **`ORIZON_WA_TOKEN` vazia → responde `200 {"ok": true}` e não faz nada.** É o modo "dormiente",
   deliberado. **Atenção: este é o candidato número um.** Do lado da Meta, a entrega parece um
   sucesso — 200 OK, sem erro, sem reentrega — e do lado do Orizon não acontece nada. Casa
   exatamente com "configurado no Meta e nunca chegou nada", e é o tipo de falha que não aparece
   em log de erro nenhum, porque não há erro.
2. **`ORIZON_WA_APP_SECRET`**, se preenchida, exige HMAC `X-Hub-Signature-256` conferindo com o
   corpo. Divergência → **403**. Aqui a Meta veria erro de entrega e reentregaria.
3. Passando os dois, parseia o payload e roteia por `processar_entrada` / `processar_entrada_usuario`,
   com log `webhook whatsapp: <id> → <status>`.

---

## Parte A — o que só o Marcelo consegue ver (painel do Meta)

Peça a ele, e não tente adivinhar por fora:

1. A **Callback URL** exata cadastrada no app — o host e o caminho, copiados literalmente.
2. O **Verify token** cadastrado (o valor, ou ao menos se existe).
3. Se o campo **`messages`** está **subscrito** no webhook. Webhook verificado mas sem esse campo
   assinado não entrega mensagem nenhuma, e é um erro comum de configuração.
4. O **log de entregas/erros** do webhook no painel: aparece tentativa? Com qual código de
   resposta? Se aparecem 200, o problema é deste lado (portão 1). Se aparecem 403, é o portão 2 ou
   o handshake. Se **não aparece tentativa nenhuma**, o problema é o número/assinatura, não nós.

---

## Parte B — o que medir no servidor (Homologação, `orizon-b`, 8766)

Tudo leitura. **Não imprima o valor dos segredos** — diga apenas se a variável existe e se está
vazia.

1. **As três variáveis em `/root/orizon-B.env`**: `ORIZON_WA_VERIFY_TOKEN`, `ORIZON_WA_TOKEN`,
   `ORIZON_WA_APP_SECRET` — cada uma **existe? está vazia?**. Confira também se o processo vivo
   realmente as enxerga (a unit pode não carregar o env file que você leu).
2. **O handshake responde?** `GET /webhooks/whatsapp?hub.verify_token=errado&hub.challenge=abc` na
   interface local — 403 esperado. Serve para provar que a rota existe e responde; não distingue
   "sem token" de "token errado", que é o item 1 que resolve.
3. **A rota é alcançável de fora, pelo domínio?**
   `https://homolog.orizonone.com.br/webhooks/whatsapp` — a requisição atravessa Traefik → o
   container de proxy → a aplicação? Basta o código de resposta; um 403 aqui é **boa notícia**
   (chegou até a aplicação).
4. **Algum dia chegou alguma coisa?** Procure no banco e nos logs por qualquer rastro de entrada:
   registros de conversa/mensagem com origem WhatsApp, `id_externo` preenchido (o `wamid`), e a
   linha de log `webhook whatsapp:`. Reporte **a data do mais recente**, se houver algum.
5. **Nós quebramos hoje?** Compare a data do item 4 com as mudanças de hoje (bind
   `0.0.0.0` → `172.19.0.1`, remoção do bloco `dev`, `default_server` 444). Se havia entrada antes
   e parou hoje, a causa é nossa e é reversível na hora. Se nunca houve nada, as mudanças de hoje
   são inocentes — mas veja o item 6.
6. **A hipótese do Host, que precisa ser descartada explicitamente.** Antes de hoje o container
   tinha dois `server{}`: `dev.orizonone.com.br` **primeiro** e `homolog` depois. No nginx, um Host
   não reconhecido cai no **primeiro** bloco — ou seja, **se a Callback URL da Meta apontasse para
   qualquer outro nome, a entrega estava indo para INTEGRAÇÃO, não para Homologação**, o que
   explicaria sozinho "nunca chegou nada" sem nenhum defeito de código. E, depois da mudança de
   hoje, passaria a bater no `default_server` 444. Cruze a Callback URL da Parte A com os
   `server_name` do container e diga se essa hipótese se sustenta ou cai.

---

## Parte C — o que NÃO fazer nesta rodada

- Não preencha nenhuma das três variáveis. São segredos do Marcelo e a decisão de ligar o webhook
  é dele.
- Não faça `POST` de teste no endpoint público com payload inventado — injetaria conversa falsa num
  banco que a partir de outubro é de loja-piloto.
- Não mexa no proxy nem reverta nada de hoje antes de reportar. Se o item 5 mostrar que foi nossa
  mudança, a reversão está documentada em `TAREFA_EXPOSICAO_SEGURA.md` e leva minutos.

---

## Formato do relatório

Uma tabela com os seis pontos da Parte B (medido / não medido / resultado), a conclusão sobre a
hipótese do item 6, e **qual dos três portões está fechado** — ou, se nenhum estiver, o que a Parte
A precisa responder para fechar o diagnóstico. Sem palpite: se faltar dado do painel do Meta, diga
que falta.
