# Retomar — onde estamos (23/09/2026, madrugada)

> **Camada 4 · TRABALHO EM ANDAMENTO.** Este arquivo é **descartável e datado**. Se a data acima
> estiver velha, ele mente: confie na `LISTA_PARALELA.md` e nos ADRs, não nele.

Escrito ao encerrar uma sessão longa de coordenação (11 a 21/09), para uma sessão nova chegar
inteira sem reler o histórico. **A memória deste projeto é o repositório, não a conversa.**

## O que ler primeiro, nesta ordem

1. `docs/README.md` — as cinco camadas e quais documentos precisam ser verdade.
2. `docs/arquitetura/DECISOES.md` — ADR-028 (cadastro × histórico), **ADR-029** (Triagem é canal,
   Captação é funil), **ADR-030** (PDV e loja ativa do cliente). Os três são desta semana.
3. `docs/db/LISTA_PARALELA.md` — 30 itens abertos, cada um com destino. LP-31, LP-34, LP-35 e
   LP-36 são novos.
4. `CLAUDE.md` e `docs/db/IMPLANTAR.md` — regras de banco e de implantação, com duas regras novas
   de 19–21/09 (commit antes de rodar script; nada de `scp` num ambiente).

## O que aconteceu nesta semana, em uma linha cada

- **O ciclo do lead fechou.** Sete contatos de WhatsApp reais ficaram 17 dias invisíveis porque a
  conversa nascia sem dono (faltava funcionário na função SAC). Hoje existe a **fila da Triagem**,
  com portão para SAC/gerencial/master da loja, ação **Assumir**, e aviso de entrega falhada na
  bolha (`TAREFA_ENTREGA_VISIVEL.md`).
- **A exposição foi fechada:** TLS já existia via EasyPanel/Traefik (o runbook antigo estava
  errado), o bind saiu de `0.0.0.0` para `172.19.0.1`, a rota `dev.orizonone.com.br` foi removida,
  sete contas privilegiadas passaram a exigir troca de senha e `pdm2026` foi desativado.
- **Redefinição de senha existe** (`scripts/redefinir_senha.py`, e pela tela do gestor).
- **A Inspirium foi limpa** (`scripts/limpar_loja.py`, 1.688 linhas) e restou um master ativo.
- **O nome da Gabriela foi corrigido** em 18–19/09: `Usuario.nome` = "Gabriela" (era "Gabriela
  Adm/Fin"). Ela é a única conta ativa da Inspirium, então esse nome assina toda mensagem que sai
  para cliente. O alvo certo era mesmo o `Usuario` — ela **não tem `Funcionario` vinculado**.
- **As lojas-piloto existem:** Salinas (16) e Casa Shopping (17) clonadas, Caraguatatuba (4)
  completada como PDV, Recreio (3) entrou na rede. Cada uma com master e **SAC**.

## O dia 22/09, em uma linha cada

- **A frente do chat fechou.** `docs/db/LISTA_IMEDIATA.md` nasceu com 8 itens; LI-1 (guarda do
  ACHADO-20), LI-5 (motivos de retenção) e LI-6 (rótulo Montagem) estão FECHADOS, LI-2 nasceu
  cortado. **Portão do bloco verde: 2.893 passed, 3 xfailed, 0 failed em 10m56.**
- **Sobram LI-3, LI-4, LI-7 e LI-8.** O LI-3 (inverter o default de `senha_provisoria`) é o único
  com DDL e é o primeiro a fazer com a cabeça descansada. O LI-4 precisa do aceite visual do
  Marcelo; o LI-7 precisa de alguém operando Homologação.
- **Nada foi empurrado para a Meta ainda.** `origin/main` estava em `dd45049` na noite de 22/09 —
  confira antes de concluir qualquer coisa sobre o que Homologação está rodando.
- **LP-39 nasceu e é o item mais importante em aberto.** Ver abaixo.
- **Três desenhos meus foram derrubados pela execução no mesmo dia** (guarda em código morto, erro
  morrendo no meio do caminho, o falso "prova" do prefixo `Lead —`). A regra que fica: **conclusão
  sobre caminho de código só entra em documento depois de executada; leitura vira hipótese
  nomeada, nunca evidência.**

## Em curso, ainda não entregue

- **`LP-39` (`LISTA_PARALELA.md`, BETA) — WhatsApp multi-loja. É a frente com prazo de outubro.**
  Medido: o roteamento de entrada não filtra por loja e o transporte de WhatsApp é único por
  instalação (env `ORIZON_WA_TOKEN`/`ORIZON_WA_PHONE_ID`), então hoje **toda loja envia pelo
  número da Inspirium**. A regra do Marcelo (23/09) é o desenho-alvo: quem recebeu decide a loja.
  Conserto em 5 peças, uma só com DDL. **Caminho-ponte para outubro confirmado:** o portfólio da
  Inspirium já é verificado e o usuário de sistema `orizon-whatsapp` alcança as WABAs dele — dá
  para cada piloto ter seu número sem Tech Provider e sem papelada. Falta o inventário
  `loja → phone_number_id` (aba "Phone numbers" de cada WABA).
- `docs/db/TAREFA_TRIAGEM_E_CONTADOR.md` — **FECHADA em 22/09** (`9aa79b4` e `33a9bcb`, suíte
  completa 2.884 verdes). A triagem agora reformula a pergunta uma vez e depois entrega à fila com
  o texto preservado; o contador do Chat Interno passou a somar pelo mesmo predicado que a lista
  usa. Ver o cabeçalho da própria tarefa pelo que foi decidido e pelo que divergiu do plano.
- `docs/db/TAREFA_SPLIT_BACKEND.md` — plano pronto (Sessão B, `f60cf3b`). O Grupo A pode começar
  por Admin a qualquer momento; o Grupo B está **travado numa decisão do Marcelo**: as ~9 rotas
  sob `/ciclo/` que, pelo código, são de Financeiro ou Comercial(PE) seguem o comportamento
  (Opção A) ou o prefixo da URL (Opção B). **DECIDIDO em 22/09: Opção B** (`03ffe56`) — hoje
  desligar módulo some da tela, não bloqueia a operação. O Grupo B não tem mais pergunta aberta;
  segue atrás da 6.6 do manifesto e da ordem da Seção 3.
- `docs/db/RASCUNHO_PORTAO_E2E.md` — rascunho para debate sobre o portão da suíte; ainda não foi
  discutido com o Claude Code.

## Aberto e sem dono escrito em lugar nenhum

- **Governança da conta Meta (visto em 23/09, não é código).** A WABA da **Dalmóbile é
  propriedade do portfólio da Inspirium** — negócios distintos com ativos misturados, o oposto da
  decisão do Marcelo de que a conta é da loja. E o portfólio tem **um único administrador**:
  perder essa conta é perder o WhatsApp de todas as lojas de uma vez. Adicionar um segundo
  administrador leva dois minutos.
- **Orizon como Tech Provider** — não é hoje: os apps pertencem a portfólios de clientes
  (Inspirium, Dalmobile SJC, Verano Atelier) e a Orizon não tem portfólio próprio. É o caminho do
  destino do LP-39, com relógio da Meta (verificação + revisão de app), e por isso vale abrir em
  paralelo ao código, não depois dele.

- **Backup externo.** O Marcelo foi decidir o fornecedor em 21/09. É o item mais urgente:
  Homologação tem lead real desde 18/09 e o backup ainda mora na mesma máquina do banco.
- **Testar a tarja vermelha de entrega falhada** com um contato de janela fechada. O código está
  no ar desde 18/09 e ninguém viu funcionando.
- **CNPJ e razão social de Salinas e Casa Shopping** — nasceram sem identidade fiscal, de
  propósito. É passo obrigatório antes de 01/11.
- **Não conectar um segundo número de WhatsApp** até existir roteamento por `phone_number_id`
  (`TAREFA_LOJAS_PILOTO.md`). Hoje o roteamento só funciona porque há um número só.

## Coisas que esta semana ensinou e que valem para a próxima

- **A medição responde a pergunta que foi feita, não a que se quis fazer.** Três casos: "a loja 1
  tem 8 funções" (eram 8 *ocupadas*), "nginx nunca existiu neste host" (runbook escrito sem
  executar), "a fila não bloqueia mais" (não é o mesmo que "mostra os itens").
- **Falha silenciosa é o defeito mais caro.** Os 17 dias, o `except Exception: pass` da ponte, o
  envio recusado que parecia enviado — todos da mesma família (ADR-017).
- **Quando um conserto existir em dois lugares, extraia um só.** Foi assim com `mod_assinatura`,
  `_rede_da_loja`, o gate da fila — e é o que a tarefa do contador pede.
