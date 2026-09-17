# Tarefa — Exposição segura antes do primeiro lead real

> **Camada 4 · TRABALHO EM ANDAMENTO.** Descartável quando o lote fechar.

**Data:** 2026-09-17
**Prazo real:** o chat entra em Homologação em **20/09** recebendo lead de pessoa real. É esse o
gatilho, não 01/10.

**Decisão do Marcelo (17/09):** as lojas-piloto rodam em **Homologação** de 01/10 a 31/10 e migram
para Produção em 01/11. Homologação **continua podendo absorver erro** — o Pontta segue como
sistema oficial e a loja-piloto sabe que está numa versão beta em teste. Integração também será
ativada, mas **sem exposição pública** (decidido em 17/09 — ver a seção própria abaixo). Perda de dado em Homologação, portanto, é incômodo operacional, não catástrofe.

**O que a condição de beta NÃO cobre:** o nome, telefone e a conversa de WhatsApp de um lead são
dados de terceiro. "É beta" explica uma tela quebrada; não explica senha e telefone atravessando a
internet em texto claro. Por isso o TLS não é adiável pelo mesmo argumento que torna a perda de
dado aceitável.

---

## Antes de escrever qualquer coisa: o runbook já existe

**Não escreva procedimento novo.** `docs/db/IMPLANTAR.md`, seção **"Exposição segura de
Integração/Homologação — nginx + TLS + bind interno"** (14/09), já tem os três passos completos,
com os comandos, as provas intermediárias e as armadilhas conhecidas (entre elas o
`client_max_body_size` que o `certbot` não copia para o bloco 443 que ele cria). A seção
**"Backup externo"**, logo abaixo, tem a parte do Backblaze B2.

Esta tarefa **sequencia e completa** aquilo. O que ela acrescenta é o Passo 0 (DNS, que estava
como pré-requisito não resolvido) e o Passo 4 (senhas, que não está em lugar nenhum).

---

## Passo 0 — resolver o nome, que é o que está travando

O runbook assume `integracao.orizonone.com.br` e `homologacao.orizonone.com.br`, **por extenso**,
com a justificativa registrada lá (bater com o vocabulário da esteira, sem abreviação).

**Mas o Marcelo relatou em 17/09 que `homolog.orizonone.com.br` — abreviado — funciona.** E a
Sessão A relatou no mesmo dia que `integracao.orizonone.com.br` não respondeu. Ou seja: o estado
real do DNS não bate com o que o runbook supõe, em nenhum dos dois nomes. Isso precisa ser
medido antes de qualquer `certbot` — o desafio HTTP-01 falha se o nome não apontar para o host.

**Fato novo, 17/09, observado pelo Marcelo no navegador: `https://homolog.orizonone.com.br`
RESPONDE, com TLS válido e a aplicação servida normalmente.** Isso contradiz uma premissa do
runbook de 14/09, que diz "diferente de Produção, este nunca teve os dois [nginx/certbot]". Ou
seja: em Homologação, o Passo 1 já está feito — sob o nome **abreviado**, não o que o runbook
supôs. **Confirme isso na máquina antes de tudo** (nginx ativo, sites habilitados, certificado
emitido e para quais nomes) e trate o runbook como desatualizado nesse ponto, não como verdade.

**O que isso muda, e é o ponto que importa:** TLS existir não fecha a porta direta. Se 8766
continuar aberta em `0.0.0.0` (e tudo indica que sim — os Passos 2 e 3 nunca rodaram), Homologação
está acessível pelos DOIS caminhos, e o caminho em claro continua valendo para quem tiver o IP ou
um link antigo salvo. **O trabalho que falta em Homologação não é instalar TLS — é fechar a outra
porta** (Passos 2 e 3). Integração, essa sim, provavelmente precisa do caminho inteiro.

Medir, do próprio host (`167.88.33.121`) e reportar:

```bash
for n in integracao.orizonone.com.br homologacao.orizonone.com.br homolog.orizonone.com.br orizonone.com.br; do
  printf '%-36s ' "$n"; getent hosts "$n" || echo "(sem resolucao)"
done
ss -ltnp | grep -E ':(80|443|8765|8766)\b'
ufw status verbose
systemctl is-active nginx 2>/dev/null || echo "nginx: ausente/parado"
```

Com o resultado na mão, **reportar ao Marcelo antes de decidir o nome** — se `homolog` já existe e
aponta certo, usar o que existe custa menos que criar outro e é decisão dele, não sua. Se nenhum
apontar, só ele pode criar os registros A.

**Este passo é bloqueador dos demais.** Não instale nginx nem rode `certbot` antes dele.

---

## Passos 1 a 3 — REESCRITOS em 17/09, depois da medição

**O runbook de 14/09 não se aplica a este host.** Medido pela Sessão A em 17/09, e é preciso
registrar de uma vez porque nenhum documento nosso dizia isto:

- `167.88.33.121` roda **EasyPanel** (PaaS sobre Docker Swarm). O **Traefik** do EasyPanel ocupa
  80 e 443 globalmente e termina o TLS.
- `homolog.orizonone.com.br` já funciona de ponta a ponta desde 31/07: DNS → Traefik (certificado
  Let's Encrypt válido, expira 29/10/2026) → container `orizon-proxy_whatsapp-proxy`
  (`nginx:alpine`) → aplicação na 8766.
- O **nginx bare-metal do host está `failed` desde 30/07** (conflito de porta com o Traefik), e
  `/etc/nginx/sites-enabled/orizon-homolog` é artefato morto daquela primeira tentativa. `certbot
  certificates` no host devolve "No certificates found".
- **`ufw` está `inactive`** — não faltam regras, não há firewall.
- O mesmo host serve **`archdecorpoints-dev`** (web/api/batch/mysql/minio/phpmyadmin), que é
  **outro projeto do próprio Marcelo**, não de terceiro.
- Não existe DNS para `integracao.*` nem `homologacao.*`. A raiz `orizonone.com.br` aponta para
  `179.197.77.9`, que é **Produção, outro host**.

**Consequência:** `apt install nginx` + `certbot --nginx` + bind em 80/443 **não é o caminho neste
host** e não deve ser tentado. Quem expõe aqui é o EasyPanel.

### Passo 1 — não fazer nada

Homologação já tem TLS e roteamento corretos. Não refazer o que funciona.

### Integração não vai para a internet — DECIDIDO pelo Marcelo em 17/09

Integração é degrau de teste da esteira, usado **só pelo Marcelo** e pelas sessões de
desenvolvimento. Ninguém de loja entra lá, hoje nem em outubro. Publicar um domínio, um
certificado e uma rota para ela acrescenta superfície de ataque sem acrescentar uso.

O acesso que ela precisa já existe e é mais seguro: **túnel SSH**
(`ssh -L 8765:127.0.0.1:8765 root@167.88.33.121`, depois abrir `http://127.0.0.1:8765` no
navegador local). Não precisa de DNS, nem de certificado, nem de rota no Traefik — e, com o Passo
2 aplicado, a porta some da internet sem ficar inacessível para quem trabalha nela.

Se mais tarde alguém além do Marcelo precisar entrar em Integração, aí sim se cria a rota pelo
EasyPanel, do mesmo jeito que `homolog` já é servido. Não é caminho fechado, é caminho adiado — e
sai do caminho crítico de 20/09.

**Consequência para este lote:** nenhum registro DNS novo, nenhum certificado novo, nenhuma rota
nova no Traefik. O que sobra para Integração é o Passo 2 (bind interno), igual ao de Homologação,
e o acesso passa a ser por túnel.

### Passo 2 — bind interno: MEDIDO em 17/09, desenho decidido

**O que a medição achou** (Sessão A, 17/09): o container `orizon-proxy_whatsapp-proxy` roda em
**bridge**, não em rede de host (IPs próprios em duas overlays do Swarm). O `proxy_pass` real,
lido de dentro do container vivo (`/etc/nginx/conf.d/default.conf`):

```
server_name dev.orizonone.com.br;      →  proxy_pass http://172.19.0.1:8765;   (Integração)
server_name homolog.orizonone.com.br;  →  proxy_pass http://172.19.0.1:8766;   (Homologação)
```

`172.19.0.1` é o **`docker_gwbridge` deste host** (interface real, 172.19.0.0/16, gateway do
Swarm), confirmado por `ip addr`. O container nunca fala com a aplicação por `127.0.0.1`.

**Portanto o ramo previsto se confirmou: `ORIZON_HOST=127.0.0.1` derrubaria
`homolog.orizonone.com.br`.** Nada foi aplicado.

**Desenho decidido: bind em `172.19.0.1`, não em `127.0.0.1`.** A aplicação passa a escutar só na
interface que o proxy realmente usa. Sai de `0.0.0.0` — deixa de existir para a internet — e o
`homolog` continua no ar.

**O que isso NÃO resolve, dito com todas as letras:** `172.19.0.1` é alcançável por **qualquer
container deste host**, inclusive os do `archdecorpoints-dev`. Não é isolamento, é redução de
superfície: some a internet inteira, permanece o próprio host. É aceitável agora e deixa de ser
necessário quando o Orizon virar app do EasyPanel de verdade — que é a resposta de longo prazo,
fora do prazo de 20/09.

**Fragilidade a cobrir antes de aplicar:** um bind em endereço de interface falha se a interface
não existir no momento em que o serviço sobe. Conferir nas units de `orizon-a`/`orizon-b`:
ordenação em relação ao Docker (`After=docker.service`) e política de `Restart`. Sem isso, um
reboot em que o Docker suba depois deixa os dois ambientes fora do ar até alguém perceber.

**Ordem de aplicação, e ela importa:** Integração (8765) **primeiro** — é o ambiente sem usuário,
onde um erro não custa nada. Prova o mecanismo ali, e só então Homologação (8766). Depois de cada
um: teste local, teste do domínio público, e — de outra máquina — confirmar que
`http://167.88.33.121:<porta>` **não** responde mais. Reversão é trocar o env de volta e
reiniciar; deixe o valor antigo anotado antes de mexer.

**O túnel de Integração muda de alvo:** `ssh -L 8765:172.19.0.1:8765 root@167.88.33.121`.

### Passo 2b — a rota latente de Integração (achado de 17/09, prioridade alta)

A mesma medição encontrou que **`dev.orizonone.com.br` já resolve para este host** e que o
container **já tem o server block** roteando esse nome para a 8765. Ou seja: é possível que
Integração esteja **exposta à internet hoje**, com TLS do Traefik, com as mesmas senhas fracas —
exatamente o que a decisão de 17/09 disse que não deveria existir.

**Medir primeiro, antes de qualquer outra coisa deste lote:** `dev.orizonone.com.br` responde de
fora? Serve a aplicação de Integração? Reportar.

Se responder, **remover a rota** (o server block e, se houver, a rota correspondente no Traefik) —
é a decisão já tomada, não precisa ser retomada. Se não responder, registrar que o server block
existe mas está inerte, e remover mesmo assim, para não virar exposição por acidente no próximo
reload do container.

### Passo 3 — `ufw` sai deste lote

Dois motivos, e o segundo é técnico e decisivo:

1. O host não tem firewall nenhum hoje, e ele serve outro projeto do Marcelo. Ligar `ufw` do zero
   aqui é mudança de superfície do **host inteiro**, não "fechar uma porta do Orizon" — não cabe
   num lote cujo objetivo é proteger o Orizon antes de 20/09.
2. **`ufw` não filtra porta publicada por Docker.** O Docker insere as próprias regras na cadeia
   `DOCKER`, que passa ao largo do `INPUT` onde o `ufw` atua. Ou seja: ligar `ufw` não fecharia
   nada do EasyPanel/archdecorpoints (inclusive o que estiver publicado lá), e fecharia só os
   serviços de systemd — `orizon-a`, `orizon-b` e **o SSH**, com risco de trancar o acesso se a
   regra do SSH falhar. Muito trabalho e muito risco para um efeito que o Passo 2 já alcança
   melhor. *(Verificar antes de agir: é o comportamento padrão do Docker, mas confirme neste host.)*

**Portanto: o Passo 2, bem medido, é o que fecha a exposição do Orizon.** O firewall do host vira
item próprio — ver abaixo.

### Item novo — higiene do host (fora deste lote, com dono e prazo próprios)

Um host sem firewall servindo `phpmyadmin`, `mysql` e `minio` publicados merece uma passada
própria, independente do Orizon. **Medir e reportar** (só leitura): quais portas o Docker publica
em `0.0.0.0` hoje. Não mexer. O resultado vira decisão do Marcelo sobre o host, não sobre o Orizon.

## Passo 4 — senhas (não está no runbook)

Hoje há 21+ contas com a senha `orizon123` e `senha_provisoria=0`, ou seja: senha conhecida, sem
troca obrigatória no primeiro acesso. Enquanto era só teste, tudo bem. A partir do momento em que
gente de loja-piloto entra, não.

Duas partes, e a segunda importa mais que a primeira:

1. **As contas que já existem** e que pessoas reais vão usar passam a `senha_provisoria=1`, para
   forçar a troca no primeiro acesso. As contas puramente de teste (Loja Teste, seeds) podem ficar
   como estão — são descartáveis e ninguém de fora as usa. Diga quais você mudou e por quê.
2. **As contas que ainda vão ser criadas.** Medir e reportar: quando um usuário é criado hoje —
   pela tela de Admin e pelos scripts de seed —, `senha_provisoria` nasce em 1 ou em 0? Se nasce
   em 0, cada loja-piloto implantada em outubro repete o problema, e o conserto é na origem, não
   uma varredura que alguém precisa lembrar de repetir cinco vezes. **Reporte antes de consertar**
   — se for mudança de comportamento, é decisão do Marcelo.

Aproveitar a mesma passada: **apagar `pdm2026` de Integração e Homologação** (decisão do Marcelo,
17/09 — fica só no localhost). Conferir antes se ele é dono de registro (projeto, log, conversa);
se for, reportar em vez de forçar — chave estrangeira quebrada em banco com dado real é pior que
uma conta a mais.

---

## Passo 5 — backup externo

`IMPLANTAR.md`, seção "Backup externo". O script `scripts/backup_externo.sh` já existe; falta a
configuração do bucket, que precisa de credencial do Backblaze B2 — **só o Marcelo tem**. Peça
quando chegar aqui.

Motivo, que já está registrado lá e vale repetir: a partir do chat, o banco local é o único lugar
onde vive a conversa de WhatsApp de um lead. Backup morando na mesma máquina que o banco não é
backup.

---

## Regras deste lote

1. **Passo 0 é bloqueador.** Reporte o resultado e espere a decisão do nome.
2. Ordem estrita nos Passos 1–3. Cada prova intermediária do runbook é pré-condição da seguinte,
   não formalidade.
3. **Não abrir achado novo** — reportar ao Marcelo e seguir.
4. Nenhuma alteração de código de aplicação neste lote. É infraestrutura e dado operacional.
5. Se algo no runbook de 14/09 não bater com o estado real do host, **pare e reporte**. O runbook
   foi escrito sem executar; divergência entre ele e a máquina é informação, não obstáculo a
   contornar por conta própria.
