# Tarefa — A entrega que falha em silêncio (LP-36, conserto)

> **Camada 4 · TRABALHO EM ANDAMENTO.** Descartável quando fechar.

**Data:** 2026-09-18
**Origem:** a medição do LP-36, feita por você em 18/09. Ela achou mais do que a hipótese previa, e
por isso o item sobe de "medir" para "consertar".

**Por que na frente da fila:** Homologação já recebe lead real. Hoje, quem responde um lead cuja
janela fechou vê a mensagem na tela como qualquer outra, segue o dia achando que atendeu, e o
cliente nunca recebeu nada. Não é risco de outubro — está acontecendo agora, e a partir de 01/10
acontece em cinco lojas.

**A decisão de negócio já está tomada (Marcelo, 18/09, LP-36):** quando a janela fecha, **a loja
resolve por outro canal** — tem o telefone e liga. O template de reengajamento é a meta, não o
pré-requisito. **Essa decisão só funciona se a pessoa souber que precisa agir.** É isso que esta
tarefa entrega: não o reenvio, a **ciência**.

**Precedente da casa — mesmo princípio, lugar novo:** ADR-017, "falha silenciosa vira falha
barulhenta", escrito para o `handler` obrigatório do aprovador financeiro. O princípio está
registrado desde 10–11/09; só não tinha chegado ao único ponto do sistema que fala com o mundo lá
fora.

---

## O que a medição achou (não repetir, é ponto de partida)

**O banco sabe.** `envios_externos.status` fica `"falhou"` com a mensagem real da Meta, via
`chat/externo.py::_erro_meta` — inclusive o código **131047**, janela de 24 h fechada, já tratado e
com teste (`tests/test_orizon_chat_meta.py`).

**A tela não.** `chat/core.py::serializar_mensagem` não tem campo de entrega, e os três call sites
de `espelhar_para_externos` em `main.py` (linhas ~9339, ~9742, ~9833 — **ancore por nome, não por
número**) envolvem a chamada em `try/except Exception:` e respondem `{"ok": true}` sempre.
Entregue, recusada ou nem tentada, a bolha fica idêntica.

**O aviso de janela existe e está no corredor, não na porta.**
`chat/externo.py::janela_da_conversa` calcula certo e alimenta um badge real — "Janela aberta",
"Janela fecha em Xh", fechada — mas **só na lista de Atendimentos**. O composer (`ocEnviar`,
`static/index.html`) nunca consulta.

---

## Conserto 1 — a informação para de ser jogada fora

**Leia antes de mexer: o `try/except` NÃO deve virar exceção.** O comentário no código está certo —
*"ponte WhatsApp é best-effort — nunca quebra o anexo"*. A mensagem interna **tem** que persistir
mesmo quando a ponte falha; quem chegar depois precisa ver o que foi escrito. O defeito não é
engolir a exceção, é **perder a informação**. Como no ADR-017, o conserto não é fazer estourar —
é fazer aparecer.

O que muda:

1. `serializar_mensagem` passa a carregar o **estado de entrega** da mensagem (entregue /
   falhou / não se aplica), e, quando falhou, o motivo que já está guardado.
2. Os três call sites param de responder `{"ok": true}` indiscriminadamente: a resposta diz que a
   mensagem foi salva **e** qual foi o destino da ponte. Sem trocar o código HTTP — salvar deu
   certo; o que mudou é a resposta contar a outra metade.
3. A bolha no chat mostra a falha, com o motivo da Meta legível (não o código cru). O caso
   "janela fechada" merece texto próprio, porque é o mais comum e tem ação clara: falar por outro
   canal.

**Regra dos irmãos:** são **três** call sites de `espelhar_para_externos` hoje. Enumere-os, trate
os três, e **escreva o número na tarefa e no código**, para o quarto se denunciar quando aparecer —
mesma prática do ADR-028 com os caminhos que criam `Cliente`.

---

## Conserto 2 — o aviso muda de lugar

O estado da janela passa a aparecer **no composer**, onde a pessoa está prestes a digitar. Reuse
`janela_da_conversa`, que já está correto — **não escreva um segundo cálculo**.

Comportamento: janela fechada, a pessoa vê antes de escrever, com dizer o que fazer (ligar, usar
outro canal). Janela fechando, o aviso de tempo restante aparece ali também, não só na lista.

Não implemente envio por template — está fora desta tarefa, depende de aprovação na Meta e é
decisão do Marcelo para depois de 01/10.

---

## Testes que precisam existir

- Envio recusado pela Meta → mensagem **persiste** internamente **e** a serialização diz que
  falhou, com motivo. (Cobre os dois lados do best-effort.)
- Código 131047 especificamente → estado "janela fechada", com o texto próprio.
- Envio bem-sucedido → nada muda no que já funcionava (sem regressão de bolha normal).
- `janela_da_conversa` fechada → o composer avisa; aberta → não avisa.
- Os três call sites cobertos, não só o mais fácil.

---

## Regras deste lote

1. **Não abrir achado novo** — reportar ao Marcelo e seguir.
2. **Enquanto a suíte completa roda, a Sessão B fica parada** (`PLANO_SEMANA_1.md`, regra 2b,
   acrescentada em 18/09). A contenção é de CPU, não de memória — não adianta liberar RAM.
3. Suíte verde antes da tag; Integração antes de Homologação; `git status --short` vazio antes do
   checkout; smoke em `172.19.0.1`, não em `127.0.0.1` (`IMPLANTAR.md`, nota de 18/09).
4. Se alguma medição sua contradisser este documento, **pare e reporte** — ele foi escrito a partir
   do seu relatório, não de execução própria.
