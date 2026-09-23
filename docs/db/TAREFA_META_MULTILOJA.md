# Tarefa — Conta Meta multi-loja: WABA por loja e a Orizon como Tech Provider

> **Camada 4 · TRABALHO EM ANDAMENTO.** Descartável quando fechar.
> **Aberta em 23/09/2026**, a pedido do Marcelo. Companheira do **LP-39** (`LISTA_PARALELA.md`),
> que trata do lado do CÓDIGO. Esta trata do lado da CONTA META — que é onde está o prazo.

## Mapa mental da Meta — as seis camadas, para parar de se perder

A confusão não é sua: a Meta empilha seis coisas que se parecem e usa nomes repetidos em todas.
Da mais externa para a mais interna:

1. **Sua conta pessoal do Facebook** — é só a chave que abre as portas. Não é empresa, não é ativo.
2. **Portfólio empresarial** (ex-Business Manager) — o cofre de UMA empresa. **É ele que se
   verifica**, e é por isso que ele precisa ter a razão social exata. Uma pessoa pode ter vários.
3. **Ativos dentro do cofre** — Páginas, Instagram, contas de anúncios, **Apps** e **WABAs**.
   Ativo pertence ao portfólio, não a você.
4. **WABA** (conta do WhatsApp Business) — uma caixa que guarda números. Não envia nada sozinha.
   **Não pode mudar de portfólio**, nunca.
5. **Número** (`phone_number_id`) — o que de fato envia e recebe. Tem nome próprio
   (`verified_name`), aprovado em separado, e é esse nome que o cliente lê.
6. **App + usuário de sistema** — o software que fala com a API, e dentro dele a identidade que
   gera o token. Precisa estar **atribuído** a cada WABA que vai usar.

**As três armadilhas que fazem tudo parecer confuso:**

- **Nome se repete em três camadas.** O portfólio tem um nome, a WABA tem outro, e o número tem um
  terceiro — e só o terceiro o cliente vê. No nosso caso os três eram diferentes entre si.
- **A tela mistura pessoa e empresa.** "Editar informações" na lista de Pessoas edita VOCÊ, não a
  empresa; o nome do portfólio fica em outro lugar (Informações da empresa).
- **Quase nada se move depois.** WABA não troca de portfólio, verificação não se transfere. Por
  isso vale gastar cinco minutos conferindo um nome antes, em vez de duas semanas depois.

## O fato que decide o desenho (pesquisado na documentação da Meta, 23/09)

**Uma WABA NÃO pode mudar de portfólio empresarial.** A documentação é explícita: *"You cannot
migrate a WABA from one business to another."* Ou seja, a WABA `Dalmobile SJC` que hoje é
**propriedade do portfólio da Inspirium** não tem botão de "transferir". O que existe são dois
caminhos, e só dois:

1. **Compartilhar** a WABA com outro portfólio (até dois parceiros, o parceiro precisa ser
   verificado). Isso dá ACESSO, não propriedade — não resolve a mistura de ativos entre negócios
   distintos, só permite operar.
2. **Migrar o NÚMERO** para uma WABA nova, criada no portfólio certo. É o caminho real, e é uma
   operação com requisitos duros (abaixo). A WABA velha fica onde está, vazia.

### Requisitos da migração de número entre WABAs (documentados)

- número registrado na WABA de origem, com **nome de exibição aprovado** e nenhuma troca de nome
  pendente;
- **verificação em duas etapas DESLIGADA** na origem;
- **origem** com verificação de negócio aprovada; **destino** com verificação de negócio aprovada,
  revisão da WABA aprovada e **forma de pagamento configurada**;
- para Cloud API, o destino precisa de **um app inscrito nos webhooks** antes da migração;
- confirmação de posse por **código SMS ou voz no número** — alguém precisa ter o aparelho/linha;
- migra-se **um número por vez**; não há operação em lote.

**O que sobrevive à migração:** nome de exibição, qualidade do número, limites de mensagem, status
de conta oficial e os templates aprovados de alta qualidade (duplicados e auto-aprovados).
**O que não sobrevive:** templates de baixa qualidade, rejeitados ou pendentes; e a qualidade dos
templates zera por 24h. **Cobrança:** antes da migração é da origem, depois é do destino.

> **Risco operacional, dito claramente:** migrar o número VIVO da Inspirium é a operação mais
> arriscada desta tarefa — exige desligar a verificação em duas etapas, confirmar por SMS e troca
> a conta que paga. **Não se faz isso na véspera nem durante a entrada das lojas-piloto.**

## Tech Provider — o que é preciso, e por que é o gargalo

Hoje a Orizon **não é** Tech Provider e **não tem portfólio próprio**: os apps pertencem a
portfólios de clientes (Inspirium, Dalmobile SJC, Verano Atelier). O caminho, na ordem:

1. **Criar o portfólio empresarial do fornecedor.** *Decisão do Marcelo (23/09): a entidade é a
   **Jkaercher**, CNPJ existente, que **futuramente será renomeada para "Orizon Soluções"**,
   detentora do OrizonOne.* Consequências práticas, nesta ordem:
   - **o portfólio nasce com o nome que está no Cartão CNPJ HOJE** — "Jkaercher", exato. A
     verificação confere contra o documento de hoje, não contra o nome futuro; usar "Orizon
     Soluções" antes da alteração societária é recusa garantida e mais 14 dias úteis;
   - **a renomeação futura não recria nada.** App, status de Tech Provider e tokens pertencem ao
     PORTFÓLIO, e o portfólio continua o mesmo objeto depois de trocar de nome. Não se perde
     onboarding nem revisão de app;
   - **mudança de dados legais tende a disparar nova verificação** — é o comportamento esperado
     quando razão social muda, mas não confirmei na documentação; conferir quando a alteração
     societária sair, e não contar com o contrário;
   - **e-mail do portfólio: `dev@orizonone.com.br`** (decisão de 23/09) — do domínio, não Gmail,
     que é o que a verificação espera. Precisa ser caixa monitorada: é por ali que a Meta avisa
     recusa, pedido de documento e status;
   - **o cliente final não vê esse nome em momento nenhum.** O que aparece no WhatsApp é o
     `verified_name` do NÚMERO, que é por loja. Ou seja, o nome do fornecedor ser "Jkaercher" por
     alguns meses não tem efeito nenhum sobre a marca que o cliente da loja enxerga;
2. **Verificação de negócio da Orizon** — documentos, e o prazo é da Meta. **É o item mais longo
   e o único que não se acelera de dentro.** Começa hoje ou atrasa tudo. **Prazo pesquisado em
   23/09: a verificação clássica (pelo próprio portfólio, na Central de Segurança) leva até
   14 dias ÚTEIS** — ou seja, perto de três semanas de calendário. A via rápida de parceiro
   (Partner-led, ~48h) está **suspensa desde 01/09/2026**, então não há atalho. Isso confirma, com
   número, que as lojas-piloto de outubro têm de entrar pela ponte, não por este caminho;
3. criar o **app sob o portfólio da Orizon**, adicionar o produto WhatsApp;
4. no painel do app: **Casos de uso → Personalizar → Onboarding de Tech Provider**, completar as
   etapas (verificação, ícone/política de privacidade/categoria);
5. **Revisão do app** com vídeo demonstrando envio de mensagem e criação de template, pedindo
   **acesso avançado** a `whatsapp_business_messaging` e `whatsapp_business_management`;
6. só então o **Embedded Signup** funciona: cada loja entra com o portfólio DELA, mantém a posse
   dos ativos, e a Orizon recebe um **business token por cliente**.

## Inventário da Fase 0 — primeira medição real (23/09)

Feita pelo token do sistema, no servidor de Homologação. Três achados, e o segundo é grave.

**1. O token não enxerga o portfólio, e agora sabemos por quê.** `debug_token` do
`ORIZON_WA_TOKEN`: é `SYSTEM_USER` do app **OrizonChat Inspirium** (1036246669392700), escopos
`whatsapp_business_management`, `whatsapp_business_messaging`, `public_profile` — **não tem
`business_management`**, que é o exigido pela aresta `owned_whatsapp_business_accounts`. Daí o 403.
Os `granular_scopes` vêm **sem `target_ids`**, ou seja, o token não está limitado a uma WABA
específica; ele só não pode ENUMERAR o portfólio. Consequência prática: o resto do inventário sai
clicando (aba "Phone numbers" de cada WABA), ou concedendo `business_management` ao usuário de
sistema — o que é uma permissão bem mais larga e não vale a pena só para listar.

**2. O número vivo tem TRÊS nomes, e nenhum bate com o outro.** A consulta direta devolveu:

| o quê | valor |
|---|---|
| WABA | `1351550097174694` — **"Dalmobile SJC"** |
| `phone_number_id` | **`1240173699181323`** |
| número exibível | **+55 12 99602-1234** |
| **nome que o cliente vê** (`verified_name`) | **"Orizon One"** |
| qualidade | GREEN |
| `code_verification_status` | **EXPIRED** |
| plataforma | CLOUD_API |

Ou seja: o número que o nosso banco atribui à **Inspirium** (`numero_conectado.loja_id = 1`) mora,
na Meta, dentro da WABA chamada **"Dalmobile SJC"**, e aparece para o cliente final como
**"Orizon One"**. Três nomes para a mesma coisa, nenhum deles o da loja que atende.

**Por que isso é grave para outubro, e não é cosmético:** `verified_name` é o nome que o cliente
lê no WhatsApp. Hoje, qualquer cliente de qualquer loja vê "Orizon One" — o nome do fornecedor do
software, não da loja com quem ele acha que está falando. Com cinco pilotos de duas redes
diferentes, isso deixa de ser detalhe e vira problema de marca e de confiança. **E o nome de
exibição é POR NÚMERO e passa por aprovação da Meta** — então cada loja-piloto com número próprio
precisa do nome dela aprovado, o que é mais um item com relógio da Meta (bem mais curto que a
verificação de negócio, mas não instantâneo).

**3. `code_verification_status = EXPIRED`.** O número opera normalmente (qualidade GREEN, mensagens
fluindo), então isso não é incêndio. Mas é um dos pontos que a migração de número checa, e por isso
entra na lista de conferência ANTES de qualquer migração — não depois.

**O que já dá para o código (LP-39):** o primeiro par real do mapa é
`phone_number_id = 1240173699181323` → hoje servindo a loja 1 (Inspirium) no nosso banco, ainda
que a WABA se chame Dalmobile SJC. Falta o resto do inventário, que sai clicando.

## Mudança de estado — 23/09, o Marcelo apagou as WABAs "Orizon"

Sobraram **duas** no portfólio da Inspirium: **Dalmobile SJC** (`1351550097174694`, com o número
vivo) e **Test WhatsApp Business Account** (a sandbox criada pela Meta). As quatro que se chamavam
"Orizon One"/"OrizonOne"/"Orizon Soluções" foram apagadas.

**Custo real disso, medido contra o que importa:** baixo. O que leva dias e não se recria é a
**verificação do portfólio**, e ela é do portfólio — continua intacta. WABA nova sob um portfólio
já verificado se cria em poucos cliques (`Contas do WhatsApp → Adicionar`). E as apagadas teriam
que ser renomeadas de qualquer jeito, porque nenhuma tinha nome de loja. A perda é de alguns
cliques, não de calendário.

**A única coisa que precisa de conferência:** se alguma daquelas WABAs tinha número registrado, o
número foi liberado junto e precisaria ser registrado de novo. O número vivo está na Dalmobile
SJC, que não foi tocada. **CONFERIDO em 23/09, logo depois das remoções:** o
`phone_number_id 1240173699181323` responde `status: CONNECTED`, `quality_rating: GREEN`,
`+55 12 99602-1234`. Nada foi perdido.

**Lição de processo, que vale mais que o episódio:** o inventário das seis WABAs nunca foi feito —
a listagem por API deu 403 e a coleta manual ficou pendente. Apagou-se sem saber o que havia
dentro. Para os próximos passos desta tarefa, a regra é a mesma que o projeto já aplica em código:
**medir antes de mexer**, inclusive na conta Meta.

## Mapa dos portfólios (visto em 23/09)

Existem **quatro** portfólios empresariais na conta do Marcelo, e **nenhum é da Orizon**:

| portfólio | id | observação |
|---|---|---|
| **Inspirium Moveis Planejados** | `37632910929655762` | é onde vivem a WABA com o número vivo e o app `OrizonChat Inspirium`; **verificado** |
| **Dalmobile SJC** | `448387691450653` | vazio |
| **dalmobilesjc** | — | **duplicata** do anterior, em minúsculas; vazio |
| Verano Atelier | — | vazio |

Dois pontos que isto acrescenta: (a) a Orizon precisa de portfólio novo, confirmado — não há o que
reaproveitar; (b) há **duas** entradas de Dalmóbile SJC, mesma doença dos nomes duplicados das
WABAs. **Não mexer nelas agora** — limpeza de portfólio sem inventário foi exatamente o que gerou
o susto das WABAs; entra na fila depois que o Tech Provider estiver de pé.

## Fase 0 — estado final (23/09)

**O inventário está completo**, e por um caminho que não era o planejado: com as remoções, o
portfólio da Inspirium ficou com **duas** WABAs, e não há mais o que inventariar.

| WABA | ID | conteúdo |
|---|---|---|
| **Dalmobile SJC** | `1351550097174694` · `account_review_status: APPROVED` | `phone_number_id` **`1240173699181323`** · +55 12 99602-1234 · `status: CONNECTED` · `quality: GREEN` |
| Test WhatsApp Business Account | (sandbox da Meta) | — |

**Susto de 23/09, medido e descartado:** houve a suspeita de ter apagado a WABA que funcionava. A
consulta direta devolveu a WABA viva e APROVADA e o número CONNECTED/GREEN. Bate com o
comportamento documentado: **WABA com número registrado não se apaga** — a própria Meta barra. As
que saíram eram as vazias.

**Estado do nome de exibição, a pendência que sobra:** `verified_name: "Orizon One"` com
`name_status: **DECLINED**` — o nome em vigor foi recusado pela Meta e mesmo assim é o que o
cliente lê no WhatsApp (conferido no celular). Há um `new_name_status: PENDING_REVIEW`, ainda sem
confirmação de qual nome está na fila. **Consequência além da marca:** um pré-requisito da
migração de número entre WABAs é nome aprovado e nenhuma troca pendente — então aprovar o nome da
loja é o que destrava o caminho do "destino" mais adiante.

**Segundo administrador:** convite enviado em 23/09, aguardando aceite. A Fase 0 fecha quando ele
aparecer como "Acesso total" na lista de Pessoas.

**Mapa para o código (LP-39), primeira linha real:**
`loja 1 (Inspirium Móveis Planejados / "Dalmóbile SJC")` → WABA `1351550097174694` →
`phone_number_id 1240173699181323`.

## A ordem que eu recomendo, e o porquê

**Fase 0 — hoje, risco zero, não depende da Meta:**
- **segundo administrador** no portfólio da Inspirium (hoje há só um; perder essa conta é perder o
  WhatsApp de todas as lojas);
- **inventário** `WABA → números → phone_number_id` (aba "Phone numbers" de cada WABA). É insumo
  do código do LP-39 nos DOIS cenários;
- **não tocar** no número vivo da Inspirium.

**Fase 1 — hoje, porque é o relógio mais longo:** criar o portfólio da Orizon e **abrir a
verificação de negócio**. Nada mais depende de decisão nenhuma.

**Fase 2 — quando a Orizon estiver verificada:** app sob o portfólio da Orizon, onboarding de Tech
Provider, revisão do app.

**Fase 3 — por loja, conforme entram:** portfólio da loja (CNPJ dela) → verificação → Embedded
Signup → número. Para loja com número já existente em outra WABA, aí sim a migração de número,
em janela combinada.

### O caminho mais simples que FUNCIONA (pesquisado em 23/09, com a restrição que ele tem)

O Marcelo pediu o mais simples, e a resposta honesta é: existe um caminho mais simples que o
Embedded Signup, ele satisfaz a regra "o número é da loja", e **não exige verificação por loja**.
Mas tem dois portões, e nenhum dos dois se pula.

**Como funciona:** a loja cria o portfólio dela, a WABA dela e registra o número dela; depois
**compartilha a WABA com a Orizon como PARCEIRO** (Meta Business Suite, "Atribuir parceiro", até
dois parceiros por WABA). A Orizon opera com um app e um usuário de sistema só, atendendo todas as
lojas. Sem Embedded Signup, sem token por cliente para gerenciar.

**Os dois portões, ambos UMA vez só — não por loja:**

1. **A Jkaercher precisa estar business-verified.** A documentação é explícita: só se compartilha
   WABA com parceiro verificado. Até 14 dias úteis, e é o que já está começando.
2. **O app da Orizon precisa de ACESSO AVANÇADO a `whatsapp_business_management`.** A
   documentação diz, com todas as letras, que sem isso o parceiro toma erro ao operar a WABA
   compartilhada. E acesso avançado **é revisão de app** — o mesmo passo do onboarding de Tech
   Provider, com vídeo demonstrando envio de mensagem e criação de template.

**O que isso elimina de verdade:** a verificação de negócio **por loja**. Portfólio novo não
verificado já registra **até 2 números** (o teto sobe para 20 com verificação), e uma loja precisa
de um. A loja fica num tier de mensagens menor, o que para uma loja de móveis planejados não
aperta. Ou seja: **cada loja entra em minutos** — portfólio, WABA, número, compartilhar com a
Orizon — desde que os dois portões acima já tenham sido vencidos.

**Resposta à pergunta "simples + Meta existe?":** não existe simples de verdade, mas existe
*simples o suficiente*: **dois portões uma vez, e depois minutos por loja**. O que não existe é
caminho nenhum que dispense a revisão de app, porque é ela que autoriza a Orizon a operar WABA de
terceiro.

### Tensão a resolver antes de outubro (decisão do Marcelo, 23/09: "os WhatsApp serão de cada loja")

A regra do destino está clara: **o número é da loja, não da Orizon**. Só que a ponte coloca os
números das pilotos sob o portfólio da **Inspirium** — que é justamente a mistura de ativos entre
CNPJs que esta tarefa existe para desfazer. As duas saídas, com o custo de cada uma:

- **Ponte agora, migração depois.** A piloto entra em outubro com número sob o portfólio da
  Inspirium e, quando o Tech Provider estiver de pé, o número migra para o portfólio da loja.
  Custo: **uma migração por número**, cada uma exigindo 2FA desligada, verificação por SMS/voz na
  linha, e perda dos templates que não forem de alta qualidade. Nada disso é caro isoladamente; o
  problema é fazer cinco vezes com loja já operando.
- **Portfólio próprio da loja desde o dia um.** Zero migração, mas **cada loja precisa da própria
  verificação de negócio — até 14 dias úteis, por loja**, e isso corre em paralelo ao da Jkaercher.
  Para as pilotos de outubro, só é viável se começar agora.

**O corte que provavelmente resolve:** piloto que **compartilha o CNPJ da Inspirium** (caso do PDV
de Caraguatatuba, pelo nome) pode usar a ponte sem mistura nenhuma — é a mesma empresa. Piloto com
**CNPJ próprio** (Dalmóbile Salinas, Casa Shopping, Recreio, se forem entidades distintas) deveria
abrir a verificação do portfólio dela **agora**, porque 14 dias úteis a partir de hoje cai no meio
de outubro. **Falta o Marcelo dizer quais pilotos são CNPJ próprio e quais são filial/PDV da
Inspirium** — é a informação que decide, e não está em lugar nenhum do repositório.

**E a ponte continua válida:** as lojas-piloto de outubro NÃO precisam esperar nada disso. Com o
portfólio da Inspirium já verificado e o `orizon-whatsapp` alcançando as WABAs dele, cada piloto
pode ter seu número agora, e o código do LP-39 é o mesmo nos dois cenários — muda só onde a
credencial mora. **Tech Provider é o destino; a ponte é o que entrega outubro.**

## O que NÃO fazer

1. Não migrar o número vivo da Inspirium antes de as lojas-piloto estarem estáveis.
2. Não desligar a verificação em duas etapas "para testar" — ela só cai no momento da migração,
   com a janela combinada.
3. Não criar o app da Orizon dentro do portfólio da Inspirium "por enquanto": é o erro que já
   existe hoje e que esta tarefa desfaz.
4. Não prometer a nenhuma loja número próprio com nome dela antes do inventário da Fase 0.
