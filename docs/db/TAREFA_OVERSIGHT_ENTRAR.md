# Tarefa — o gerente entra na conversa, não só assiste

> **Camada 4 · TRABALHO EM ANDAMENTO.** Descartável quando fechar.
> Aberta em 26/09/2026, a partir de uso real em Homologação logo após o deploy da
> `v2026.09.25-beta3`.

## O que aconteceu em campo

O Marcelo entrou como **Felipe** (master da Dalmóbile SJC) e abriu, pelo **Oversight**, a
conversa externa dele mesmo — a que estava com a Gabriela como responsável. Viu tudo e não pôde
responder: o cabeçalho dizia "(somente leitura)" e não havia compositor.

> "O Felipe visualiza a mensagem pelo oversight, mas não consegue tentar responder. A mensagem
> ficou presa com a Gabriela. Mas de toda forma, o gerente deve ter o acesso e poder entrar na
> comunicação." — Marcelo, 26/09

## Isto NÃO é defeito de permissão. É uma decisão antiga.

Medido em 26/09: `static/index.html:13357` — a lista de Oversight chama
`ocAbrirConversaPorId(c.id, _titAtd, false, ...)`, com `podePostar = false` **fixo**. Em
qualquer outro caminho o mesmo parâmetro vai `true` (só o mural tem regra própria). Ou seja: o
Oversight foi construído para AUDITAR — o gerente vê a loja inteira, inclusive o que não é
dele, e por isso não posta por acidente numa conversa que só estava conferindo.

A regra do Marcelo é mais ampla que essa proteção, mas não a contradiz: ele quer poder **entrar**,
não quer postar sem querer. As duas coisas cabem juntas se entrar for um ATO EXPLÍCITO.

## O conserto

1. Botão **"Entrar na conversa"** no cabeçalho do thread, visível **somente** quando:
   - a conversa foi aberta pelo Oversight (o caminho que hoje passa `podePostar=false`), E
   - quem olha é master ou gerencial da loja da conversa (mesmo gate de `pode_trabalhar_fila`,
     ADR-029 — nível bruto ou Função SAC, nunca capacidade configurável), E
   - a pessoa ainda não é participante.
2. O clique:
   - adiciona quem clicou como participante — **carteira aditiva**, ninguém é removido;
   - **NÃO** troca o responsável. Quem era responsável continua sendo. Trocar é o Transferir,
     que já existe e tem trilha própria;
   - grava evento na linha do tempo ("Fulano entrou na conversa"), no mesmo padrão de
     `responsavel_transf`;
   - libera o compositor sem recarregar a tela.
3. Reuso, não duplicação: a adição de participante já existe dentro de
   `chat/core.py::transferir_responsavel` (participante + evento). Extraia o trecho ou chame a
   parte comum — **não** escreva um terceiro lugar que cria `ConversaParticipante`.
4. O Oversight continua abrindo em leitura. O botão é a única porta, e ela é deliberada.

## Medição pedida junto (não consertar antes de reportar)

No mesmo print, o cabeçalho mostrava **"Responsável: SAC"**, enquanto a linha do tempo dizia
"Atendimento transferido para Gabriela por Gabriela". A Gabriela foi **desativada** em 25/09,
pelo lote de usuários. Meça e reporte, sem corrigir:

- o que o backend devolve em `responsavel` para essa conversa hoje;
- se existe algum fallback que troca o responsável quando o titular fica inativo, ou se é a
  tela que exibe outra coisa;
- se o responsável gravado continua sendo o usuário inativo, o que acontece com a fila e com a
  contagem de pendentes dessa conversa.

Isto pode ser correto, pode ser cosmético, ou pode ser um responsável fantasma. Conclusão sobre
caminho de código só entra em documento depois de executada.

### Medido em 26/09/2026 — são DUAS coisas, uma cosmética e uma real

**1. O texto "Responsável: SAC" é cosmético — artefato do caminho de Oversight, não uma
reatribuição de verdade.** `ocAbrirTodas` (`static/index.html:13352`) só entra no ramo de
Oversight quando o viewer NÃO participa da conversa (`_ocInbox` não a contém) — Felipe não é
participante desta, então cai em `listar_todas_conversas` (`chat/core.py:1103`), que **não
serializa `responsavel` de propósito** (o próprio comentário da função já lista o que ela espelha
do serializer pessoal — `urgente`/`status`/`pendente` — e `responsavel` não está na lista).
`_ocSetHeaderExtras` (`static/index.html:18860`) então cai no fallback já existente desde
05/08 ("sem responsável explícito, quem trata é o SAC até a transferência"):
`(c && c.responsavel && c.responsavel.nome) || 'SAC'` — `c.responsavel` vem `undefined` (não
`null`), o fallback dispara, e a tela mostra "SAC" **mesmo quando o backend tem um responsável
de verdade**. Confirmado pelo próprio comentário deixado no `ocAbrirTodas`: "listar_todas_
conversas não serializa responsavel/urgente/status — some/neutro". Quem abrisse esta mesma
conversa pelo caminho normal (`serializar_conversa`, `chat/core.py:1799`) veria o nome real — essa
função lê `Usuario` por PK sem filtrar `ativo`, então mostraria "Gabriela", não "SAC".

**2. O responsável gravado no banco quase certamente CONTINUA sendo a Gabriela — e isso É um
responsável fantasma de verdade, com consequência real na fila.** Não existe, em lugar nenhum do
código (`chat/core.py`, `main.py`, `database.py`), nenhum mecanismo que limpe ou reatribua
`Conversa.responsavel_usuario_id` quando o `Usuario` titular é desativado — a única escrita nesse
campo é `transferir_responsavel`/criação de grupo/projeto. A consequência, seguindo os dois
lugares que decidem visibilidade:
- `listar_conversas_sem_dono` (a fila "sem dono" que o SAC/gerência trabalha, `chat/core.py:1931`)
  só inclui conversa com `responsavel_usuario_id IS NULL` **e** sem participante ativo — esta
  conversa tem os dois (responsável gravado + Gabriela como participante, `transferir_
  responsavel` sempre adiciona o destino como participante), então ela NUNCA cai nessa fila,
  mesmo com o titular inativo.
- `listar_inbox` (`chat/core.py:1861`, de onde vem `_ocInbox` e a contagem de pendentes de
  `ocAtualizarBadges`, `static/index.html:18766`) é por `ConversaParticipante`, não por
  `responsavel_usuario_id` — como só a Gabriela (desativada, não consegue logar) é participante,
  a conversa não entra no inbox de mais ninguém e **não conta em nenhum badge de pendentes de
  ninguém**.

**Conclusão:** a conversa fica presa — grava um responsável real (Gabriela) que não pode mais
agir, não aparece na fila de "sem dono" (porque tecnicamente tem dono), e não conta pendente pra
ninguém (porque só o dono inativo é participante). Só o Oversight a alcança — auditoria manual,
não fila de trabalho. É exatamente o cenário que motivou o pedido do Marcelo: o gerente PRECISA
poder entrar, porque não há outro caminho pra essa conversa sair do limbo. Não é achado novo desta
tarefa (é consequência do desenho existente de responsável + participante, não um defeito
introduzido por LI-3/LI-8/LI-4/LI-4b) — registrado aqui como medição, não como item a consertar
neste lote (o conserto deste lote é o botão "Entrar", que já resolve o sintoma prático: dá a
qualquer master/gerencial da loja um jeito de assumir participação e destravar a conversa).

## Prova

- master da loja abre pelo Oversight uma conversa da qual não participa → vê o botão, não vê
  compositor;
- clica → vira participante, compositor aparece, evento na linha do tempo, **responsável
  inalterado**;
- operador comum abre a mesma conversa (sem Oversight, sem ser participante) → não vê o botão;
- quem JÁ é participante não vê o botão (não duplica participação);
- o mural continua sem compositor para quem não pode postar (regra própria, intocada).

## Estado — FECHADO em 26/09/2026

**Medição (item 1)** — ver "Medido em 26/09/2026" acima, dentro da seção "Medição pedida junto".
Resumo: "Responsável: SAC" é cosmético (gap de serialização do Oversight, `listar_todas_
conversas` não expõe `responsavel`); o responsável GRAVADO continua sendo o usuário desativado
(nada limpa `responsavel_usuario_id` na desativação) — isso É um responsável fantasma real, que
some tanto da fila "sem dono" (`listar_conversas_sem_dono`, que exige responsável NULO) quanto da
contagem de pendentes de qualquer um (`listar_inbox`/`ocAtualizarBadges` são por
`ConversaParticipante`, e só o titular inativo participa). Não é achado novo desta tarefa —
consequência do desenho existente; o próprio botão "Entrar" é o que destrava esse limbo na
prática.

**Conserto (itens 2-3)** — implementado num commit só:
- `chat/core.py`: `_participar` extraída de `transferir_responsavel` (única escrita de
  `ConversaParticipante` por este caminho); `entrar_na_conversa` (nova) a reusa com
  `origem="manual"`, registra evento `entrou_conversa` na timeline, NÃO toca
  `responsavel_usuario_id`. `listar_todas_conversas` ganhou `pode_entrar` por item — gate
  `pode_trabalhar_fila` (nível bruto master/gerencial OU Função SAC, ADR-029) **e** ainda não
  ser participante.
- `main.py`: `/api/comunicacao/conversas/<id>/entrar`, mesma família de
  transferir/urgente/concluir/promover_lead — com gate PRÓPRIO (`pode_trabalhar_fila`), mais
  estrito que o "participante ou `ver_todas_conversas`" comum ao resto da família.
- `static/index.html`: botão "Entrar na conversa" no cabeçalho (`oc-header-right`, visível
  independente de `podePostar` — o resto do compositor some quando `podePostar=false`, o botão
  não pode estar lá dentro); visibilidade = `c.pode_entrar` (só vem preenchido no item do
  Oversight, então o botão nunca aparece fora dele, sem precisar de um estado "abriu por
  oversight" à parte); clique libera o compositor sem recarregar a tela.

**Provas (item 3)** — `tests/test_oversight_entrar.py`, 11 testes: as 5 do documento (master vê
o botão / clique adiciona sem trocar responsável / operador comum não vê / quem já participa não
vê / mural fica de fora) + gate por Função SAC + recusa de reentrada + regressão de
`transferir_responsavel` + endpoint com tenancy e gate próprio.

**Portão:** `-k "chat or oversight or atendimento or transferir or participante or li4b or
contrato"` — 337 passed, 0 failed.

**Suíte completa (procedimento do PLANO_SEMANA_1.md — nohup setsid + timeout tail -f --pid, log
lido antes de apagar):** `python3 -m pytest -q` — **2941 passed, 3 xfailed, 0 failed em 671,49s
(11m11)**. Os 3 `xfailed` são os mesmos pré-existentes de sempre (ACHADO-19), não consequência
desta tarefa.

## Regras deste lote

1. Sem DDL.
2. Não abrir achado novo — anotar e reportar.
3. Testes alvo verdes por commit; suíte completa ao fim, pelo procedimento do
   `PLANO_SEMANA_1.md` (destacada com `nohup setsid`, acompanhada com
   `timeout N tail -f --pid=<pid>`; o log só se apaga depois do número lido, reportado e
   escrito no documento).
4. `OVERSIGHT-ENTRAR` na mensagem dos commits.
