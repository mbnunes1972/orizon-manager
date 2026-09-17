# Tarefa — Exposição segura antes do primeiro lead real

> **Camada 4 · TRABALHO EM ANDAMENTO.** Descartável quando o lote fechar.

**Data:** 2026-09-17
**Prazo real:** o chat entra em Homologação em **20/09** recebendo lead de pessoa real. É esse o
gatilho, não 01/10.

**Decisão do Marcelo (17/09):** as lojas-piloto rodam em **Homologação** de 01/10 a 31/10 e migram
para Produção em 01/11. Homologação **continua podendo absorver erro** — o Pontta segue como
sistema oficial e a loja-piloto sabe que está numa versão beta em teste. Integração também será
ativada. Perda de dado em Homologação, portanto, é incômodo operacional, não catástrofe.

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

## Passos 1 a 3 — nginx, TLS, bind interno, firewall

Seguir `IMPLANTAR.md`, seção citada, **sem reescrever**. Substituir os nomes pelos que o Passo 0
definir — a própria seção já prevê isso ("se os nomes escolhidos forem outros, troque nos comandos
abaixo — é substituição mecânica").

Ordem e provas são as de lá, e a ordem importa: o Passo 3 fecha 8765/8766 no firewall, e fazê-lo
antes do HTTPS provado deixaria os dois ambientes inacessíveis por qualquer caminho.

Fazer **nos dois ambientes**. Integração passa a ser usada de verdade a partir de agora — foi
decisão do Marcelo em 17/09 — então ela precisa estar tão acessível quanto Homologação.

---

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
