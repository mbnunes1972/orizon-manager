# Tarefa — A fila de leads: configuração do SAC + tela de contatos sem dono

> **Camada 4 · TRABALHO EM ANDAMENTO.** Descartável quando fechar.

**Data:** 2026-09-17
**Origem:** `TAREFA_MEDIR_AVISO_DE_LEAD.md`. A medição concluiu: *"hoje, quando um lead entra, quem
fica sabendo é ninguém"* — 7 contatos de WhatsApp reais desde 31/08, nenhum visível em nenhuma
tela, nem para o super_admin.
**Prazo:** o chat precisa operar em **20/09**.

**Decisões do Marcelo (17/09), já tomadas — não retomar:**
- A função **SAC** será criada na Inspirium e ancorará a distribuição.
- A coluna esquerda do Chat passa a ter **três canais**: Atendimentos, Chat Interno e **Triagem**.
- O bloco "Configurações do Chat" **colapsa num botão** que abre as opções.
- O item de configuração hoje chamado "Triagem" passa a se chamar **"OrizonBot"** — é onde se
  configura a pergunta automática e o comportamento do robô.

---

## Parte 1 — Configuração do SAC (HOJE, sem código)

Faz o fluxo funcionar para **todo lead novo**, sem tocar em uma linha de código.
`chat/triagem.py::triagem_materializar` só atribui participante e responsável quando existe um
funcionário com função **"SAC"** e conta de login na loja (`_sac_usuario_id`). A Inspirium não tem
essa função — por isso o caminho "sem SAC" (conversa nua, zero participantes) roda sempre.

1. ~~Criar a função **SAC** na loja 1~~ — **já existe; passo feito.** Correção da Sessão A,
   17/09: `funcoes.id=12`, nome `SAC`, ativo, criada em **16/07/2026**. A medição do item 5 de
   `TAREFA_MEDIR_AVISO_DE_LEAD.md` relatou "0 registros" porque a consulta juntava
   `funcionarios → funcoes` — respondeu "quem OCUPA a função", não "a função EXISTE". A conclusão
   de fundo continua de pé (`_sac_usuario_id` não resolve para ninguém); muda a causa: não é "a
   função não existe", é **"a função existe e ninguém a ocupa"**.

   *Efeito colateral bom:* a mesma consulta produziu o "a Inspirium tem 8 funções" que fez duvidar
   do clone (a Loja Teste, clonada dela, mostra 15). A dúvida **cai** — eram 8 funções *ocupadas*,
   não 8 existentes. O clone não está sob suspeita.
2. **Criar um usuário novo** para ocupar a função (decisão do Marcelo, 17/09 — por enquanto é
   conta de teste; a pessoa real entra depois). Sugestão de nome/login: **"SAC Inspirium"** /
   `sac.inspirium` — confirme que o login não colide antes. Nível: o **mínimo** que permita
   receber e assumir conversa; **meça qual é** e reporte, não escolha por conforto.
3. **Crie-o pela tela de Admin**, não por script — assim a criação serve de verificação ao vivo do
   conserto de hoje (`senha_provisoria` nascendo em 1). Confirme depois que o registro nasceu com
   a flag ligada. Se nascer em 0, o conserto de hoje não pegou e isso é achado — reporte.
4. **Provar**, sem inventar mensagem: confirme que `_sac_usuario_id` passa a resolver para essa
   conta. Só o próximo lead real fecha a prova de ponta a ponta — **não force um POST no webhook
   público** para testar (injetaria conversa falsa num banco que em outubro é de loja-piloto).

### 1b — Adotar as sete conversas órfãs

O conserto acima **não alcança o que já existe**. As 6 conversas materializadas (ids 2, 3, 4, 19,
21, 22) e a do Felipe continuam com zero participantes para sempre. Depois da Parte 2 elas vão
aparecer sozinhas na nova tela (o recorte inclui conversa sem dono) — então **não faça adoção
manual no banco**. Só confirme, quando a tela existir, que as sete aparecem nela.

---

## Parte 2 — A tela da fila

### 2a — O recorte, que é a decisão mais importante desta tarefa

A lista **não pode ser só `TriagemEntrada` com status pendente.** Se for, o lead aparece por alguns
minutos e **some** assim que materializa em conversa — cai no mesmo buraco de hoje, só mais tarde.
Foi exatamente o que aconteceu com o contato do Felipe em 17/09: ele saiu da triagem e virou uma
conversa invisível quando alguém abriu o inbox.

**O recorte é "contato de fora sem dono"**, e cobre os dois estados:

1. `TriagemEntrada` com status `pendente` — ainda não virou conversa.
2. `Conversa` de origem externa **sem participante interno e sem `responsavel_usuario_id`** — já
   materializou e ninguém assumiu.

Com esse recorte, as sete órfãs de agosto/setembro aparecem no primeiro carregamento, sem
migração nem adoção manual.

### 2b — A fila precisa de saída

Uma fila que não esvazia vira outra lista que ninguém olha. Cada item precisa de uma ação
**Assumir**: adiciona o usuário atual como participante e como responsável, materializando a
triagem antes, se ainda for o caso. Depois disso o item sai da fila e passa a viver no inbox
normal de quem assumiu — que é onde o badge de não-lidas já funciona.

### 2c — Navegação

- Coluna esquerda, bloco de cima: **Atendimentos**, **Chat Interno**, **Triagem** (o novo).
- Bloco "Configurações do Chat": colapsa num botão **Configurações** que abre Segmentos,
  **OrizonBot**, Modelos de Mensagem, Números Conectados, Consumo / Custos.
- **"Triagem" não pode existir duas vezes.** O item de configuração vira **OrizonBot**; o canal
  novo fica com o nome Triagem. Dois itens com o mesmo nome, um sendo lista e outro configuração,
  é a ambiguidade que produziu o problema de hoje — o Marcelo clicou no nome certo e achou a tela
  errada.
- O canal Triagem leva **contador** quando há item na fila. Sem contador, continua dependendo de
  alguém lembrar de olhar.

---

## Sobre o tamanho disto — leia antes de estimar

O Marcelo descreveu a Parte 2 como "quase só um detalhe de interface". **Não é**, e é melhor dizer
agora do que descobrir na véspera:

- **Nenhum endpoint de `main.py` lê `TriagemEntrada` hoje** — medido em 17/09; só `chat/triagem.py`
  e `chat/externo.py` a tocam, e só escrevendo. A rota de leitura não existe, precisa nascer.
- A consulta de "conversa sem dono" também não existe — o inbox de hoje lista por participante, que
  é justamente o que essas conversas não têm.
- A ação **Assumir** é escrita, com tenancy: só quem é da loja da conversa pode assumir. Vale a
  regra dos irmãos — enumere todo lugar que cria participante antes de acrescentar mais um.
- A reorganização da navegação mexe em `static/index.html`, que tem catracas de contagem de linha.

**Se der conflito de prazo, a Parte 1 sozinha já faz o chat operar** para lead novo. A Parte 2 é o
que resolve o passado e o que torna o fluxo legível. Reporte ao Marcelo se achar que não fecha até
20/09 — atrasar com aviso é decisão dele; atrasar em silêncio, não.

---

## Regras deste lote

1. Não faça `POST` de teste no webhook público. Não responda o lead do Felipe pelo sistema — isso é
   operação do Marcelo.
2. Não abra achado novo: reporte e siga.
3. Suíte verde antes da tag, como sempre. Deploy por tag, Integração antes de Homologação.
4. Se alguma medição sua contradisser este documento, **pare e reporte**. Ele foi escrito a partir
   da medição de 17/09, não de execução.
