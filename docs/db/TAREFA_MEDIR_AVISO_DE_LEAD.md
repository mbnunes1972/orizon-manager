# Tarefa — Medição: quando um lead entra, quem fica sabendo?

> **Camada 4 · TRABALHO EM ANDAMENTO.** Medição, não conserto.

**Data:** 2026-09-17
**Origem:** a medição do webhook (`TAREFA_MEDIR_WEBHOOK_WHATSAPP.md`) provou que o canal **funciona
e sempre funcionou** — 7 mensagens entregues desde 31/08, a última processada ao vivo durante a
própria medição. O defeito não era técnico: **seis conversas reais ficaram abertas na Inspirium
por dezessete dias sem ninguém ver**, e um lead (Felipe, SJC) esperou resposta humana enquanto a
medição acontecia.

**A pergunta mudou.** Não é mais "o chat funciona". É: **quando um lead entra, quem fica sabendo,
e como?** Um sistema que recebe o lead corretamente e não avisa ninguém é operacionalmente
idêntico a um que não recebe — e a prova disso são os dezessete dias.

**Prazo:** 20/09. Esta é a última medição entre o estado atual e o chat operando de verdade.

**Esta tarefa é SÓ MEDIÇÃO.** Não conserte nada, não crie aviso, não atribua conversa a ninguém.
Meça e reporte; o desenho do aviso é decisão do Marcelo.

---

## Hipótese principal, para a medição ser dirigida

O badge de não-lidas existe: `ocPollBadge` (`static/index.html`) chama `_ocInboxAtualizar` a cada
45 s, e a contagem vem de `chat/core.py::_conta_nao_lidas`, **por participante da conversa**.

Se uma conversa nascida do WhatsApp **não tem participante nenhum**, ela não é "não-lida" para
ninguém — logo não produz badge para ninguém, e some da vista sem nunca ter aparecido. Essa
família de defeito já apareceu uma vez neste mesmo código: em 14/09, um `ConversaParticipante`
ausente fazia `pode_escrever_conversa` recusar sempre.

**Medir, não supor.**

---

## O que medir

### 1. As conversas órfãs

Para as 7 conversas/triagens de entrada existentes em Homologação: **quem são os participantes de
cada uma?** Alguma tem zero? Alguma tem responsável atribuído? Reporte em tabela: conversa, data,
nº de participantes, responsável.

Se as que ninguém viu tiverem zero participantes e a que alguém viu tiver participante, a
hipótese está confirmada e o resto da medição é secundário.

### 2. O caminho da triagem

`TriagemEntrada` com status `pendente` (o caso do Felipe): **algum contador, badge ou lista a
mostra fora da própria tela de Triagem?** Uma busca por `triagem` no que alimenta "Pendências"
(`/api/me/ciclo/pendencias`) não encontrou nada — confirme se é isso mesmo: **triagem pendente não
entra em Pendências**.

Se não entra, então o único lugar onde um lead novo aparece é dentro da tela de Triagem, que
alguém precisa lembrar de abrir. Ou seja: o aviso não existe, existe um lugar para procurar.

### 3. O que "Pendências" realmente mostra

Liste as fontes que alimentam o contador de Pendências do cabeçalho. Não interessa o detalhe de
cada uma — interessa se **alguma delas cobre "chegou mensagem de alguém de fora"**.

### 4. Avisos fora da tela

Existe **qualquer** aviso que alcance a pessoa que não está com o Orizon aberto? E-mail, push,
som, título da aba piscando, mensagem de volta para o WhatsApp de um atendente. Reporte o que
existe e o que não existe. Se a resposta for "nada", diga isso com todas as letras — é a resposta
mais útil possível aqui.

### 5. A quem a conversa deveria chegar

Em Homologação, na loja 1: **existe alguma regra de distribuição?** Segmento, fila, consultor de
plantão, rodízio? A tela de Chat tem "Segmentos" e "Triagem" no menu — meça se estão configurados
na loja 1 ou se estão vazios. Um aviso sem destinatário definido não resolve nada: alguém precisa
ser o dono do lead novo.

---

## O que NÃO fazer

- Não responda o lead do Felipe pelo sistema. Isso é operação do Marcelo, não da sessão.
- Não crie participante, não atribua responsável, não mexa em Segmentos/Triagem.
- Não construa o aviso. Medir primeiro; o desenho vem depois e é decisão de negócio.

---

## Formato do relatório

Os cinco itens, cada um com **o que existe hoje** e **o que não existe**. No fim, uma frase só:
*"hoje, quando um lead entra, quem fica sabendo é ___, por ___"* — ou "ninguém", se for o caso.
É essa frase que decide o que precisa ser construído antes de 20/09.
