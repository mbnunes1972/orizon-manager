# Tarefa — Configurador de Responsabilidades por Etapa (LP-14)

Decidido pelo Marcelo em 15/09/2026 — ver `docs/db/LISTA_PARALELA.md`, destino DECIDIDO/fila da
1.0. Não é urgente: agendado de propósito para depois de 01/10/2026. Escrito pela Sessão B a
partir do pedido original (LP-14: "toda etapa precisa ter um evento que caracterize seu término, e
sempre que terminar deve aparecer um popup informando o término e oferecendo a transferência de
responsabilidade").

## O que está medido — metade do mecanismo já existe

O pedido original (02/09) exigia um levantamento antes de decidir alcance: "quais das 21 etapas já
têm hoje um evento de término identificável e quais terminam por inferência". Medido agora, por
leitura de `main.py`:

**A cadeia de resolução de responsável (`_responsavel_funcionario_etapa`) já cobre quase tudo,
em duas camadas diferentes:**

1. **Override manual por projeto** — `CicloEtapa.responsavel_funcionario_id`. Já existe. **É
   literalmente o "onde houver exceção, aponte uma pessoa específica" que o pedido do Configurador
   quer** — não precisa ser reinventado, só exposto na tela nova.
2. **Papel → pessoa via Mapa de Atribuições** (`_ETAPA_PAPEL`, `mod_escopo.resolver_responsavel`)
   — cobre **9 etapas**: 9, 10 (Medição), 11/11a/11b/11c/11e (Projeto Executivo), 17 (Montagem),
   18 (Assistência). É a MESMA tabela que dispara comissão (`mod_comissao.preparar_comissao_etapa`
   usa o mesmo papel) — mexer nela tem efeito colateral em remuneração, não só em notificação.
3. **Default por FAIXA, hardcoded, não editável** (`_default_responsavel_faixa`) — cobre **13
   etapas** por três faixas fixas: Vendas (1, 2, 3, 4, 7) → Consultor do Briefing; Financeiro (8,
   11d, 21) → função "Gerente Administrativo/Financeiro" (nome de função **literal no código**,
   não referência a registro); Logística (12, 13, 14, 15, 16) → função "Assistente Logístico"
   (mesma fragilidade). Se a loja renomear essas funções em Config, este default quebra em
   silêncio — risco pré-existente, fora do escopo deste pacote, mas vale registrar para quem for
   editar Config depois.
4. **Fallback final** — criador do projeto, se nada acima resolver.

**O que NÃO está coberto por nenhuma camada:** etapas **17a** (Pendências de montagem), **19**
(Vistoria final) e **20** (Aprovação final) — caem direto no fallback (criador do projeto), o que
provavelmente está errado na prática (o criador do projeto raramente é quem faz vistoria ou dá
aprovação final).

**Notificação de conclusão já existe, também espalhada em dois mecanismos:**
- `chat/core.py::mensagem_passagem_fase` — dispara quando a etapa seguinte tem responsável
  resolvível, só de dentro do PATCH genérico de conclusão de etapa (`main.py`, um único call
  site).
- `chat/core.py::mensagem_etapa_concluida` — dispara quando não há transferência (mesmo
  responsável segue), de um call site DIFERENTE em `main.py`.

**O que falta, de verdade:** (a) uma TELA para editar a tabela etapa→papel, hoje só existe como
dicionário Python fixo (`_ETAPA_PAPEL`) — não editável, não visível em Config; (b) as três etapas
sem cobertura (17a, 19, 20); (c) unificar os dois mecanismos de notificação num só, chamado de
QUALQUER caminho que conclua uma etapa — hoje, se uma etapa for concluída por um caminho que não
seja o PATCH genérico, nenhuma notificação dispara (o mesmo padrão de "caminho alternativo não
herda o efeito colateral" já visto no achado da comissão de Montagem); (d) o aviso "na tela"
(popup/toast) que o pedido original menciona — hoje só existe a mensagem de chat, não há um alerta
separado na interface.

## O que fazer

1. **Configurador de Responsabilidades — aba nova no Painel de Config.** Amarra etapa → papel,
   cobrindo TODAS as etapas do ciclo (unificando as 9 hoje em `_ETAPA_PAPEL` e as 13 hoje em
   `_default_responsavel_faixa` num único formato editável — provavelmente uma tabela no banco, não
   mais dicionário fixo em `main.py`), e preenchendo as três hoje sem dono (17a, 19, 20). O papel
   resolve para a pessoa daquela loja via o mesmo Mapa de Atribuições que já existe — **não criar
   um segundo lugar que resolve papel→pessoa**, reusar `mod_escopo.resolver_responsavel`.
2. **Exceção por pessoa específica: reusar `CicloEtapa.responsavel_funcionario_id`**, que já existe
   — não criar um campo novo para a mesma coisa.
3. **Escopo por loja como padrão, com troca dentro de um projeto específico** — o padrão (por
   loja) é o Configurador; a troca pontual (por projeto) é o override que já existe no item 2. O
   Mapa de Atribuições continua sendo a única fonte de "quem é a pessoa por trás do papel" — o
   Configurador não duplica isso, só decide QUAL papel cada etapa usa.
4. **Notificação ao concluir: tela + chat interno, sem WhatsApp por ora.** Unificar
   `mensagem_passagem_fase`/`mensagem_etapa_concluida` para disparar de QUALQUER ponto que conclua
   uma etapa (hoje só dispara do PATCH genérico) — o mesmo princípio de "um setter só, chamado de
   todo caminho" que a Fronteira 6.1 propõe para o resto do Ciclo; se a 6.1 já estiver construída
   quando este pacote for pego, use o mecanismo dela em vez de duplicar. Acrescentar o aviso NA
   TELA (o pedido original pede popup) — hoje só existe mensagem de chat, que pode passar
   despercebida se o usuário não estiver na Conversa.
5. **Editável, com pré-condição de configuração.** Fica estabelecido que o Configurador precisa
   estar preenchido (todas as etapas com papel definido) antes de a loja operar por ele — decidir,
   na implementação, o que acontece enquanto não está: manter o comportamento atual (faixa
   hardcoded) como default até alguém configurar, para não travar loja nenhuma no meio da
   transição.

## Fronteiras — o que este pacote toca, e o que não

**Toca:** a tabela etapa→papel (hoje `_ETAPA_PAPEL` + `_default_responsavel_faixa`, ambos em
`main.py`), a tela nova em Config, e os dois pontos de notificação de conclusão de etapa.

**Não toca:**
- `mod_comissao.preparar_comissao_etapa` — usa o mesmo papel, mas este pacote não muda regra de
  comissão, só onde o papel é definido (de hardcoded para configurável). Testar que comissão
  continua disparando igual depois da migração é aceite explícito abaixo.
- O Mapa de Atribuições em si (`mod_escopo.py`) — continua sendo a única fonte de papel→pessoa.
- WhatsApp/Evolution — fora de escopo por decisão explícita (barulhento, token de terceiro, custo
  por mensagem). Liga depois se a operação pedir, como pacote separado.
- A Fronteira 6.1 (regra única de transição) — este pacote não depende dela para existir, mas se
  ela já estiver pronta quando este for executado, o mecanismo de notificação unificado (item 4)
  deve usar o hook dela em vez de criar um caminho paralelo.

## Aceite

1. Toda etapa do ciclo (as 21, incluindo 17a/19/20) tem um papel resolvível no Configurador — teste
   que itera `mod_ciclo.ETAPAS_PRINCIPAIS`/subfases e confirma que nenhuma cai no fallback
   "criador do projeto" por falta de configuração.
2. `mod_comissao.preparar_comissao_etapa` continua disparando para as 9 etapas que hoje usam
   `_ETAPA_PAPEL`, com o MESMO papel, depois da migração para o Configurador — teste de
   não-regressão explícito, comparando antes/depois para as mesmas etapas.
3. Override por projeto (`CicloEtapa.responsavel_funcionario_id`) continua funcionando exatamente
   como hoje — teste de não-regressão.
4. Concluir uma etapa por QUALQUER caminho (não só o PATCH genérico) dispara notificação — teste
   que cobre pelo menos um caminho hoje não coberto (ex.: conclusão via `_set_etapa_status`
   chamado fora do PATCH genérico).
5. A notificação aparece na tela (não só na Conversa) — critério de UI, a Sessão A decide o
   mecanismo exato (toast, badge, painel).
6. Testável com os usuários de teste que já existem — nenhum usuário/fixture novo criado só para
   este pacote.
