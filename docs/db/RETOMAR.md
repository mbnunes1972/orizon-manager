# Retomar — onde estamos (22/09/2026)

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

## Em curso, ainda não entregue

- `docs/db/TAREFA_TRIAGEM_E_CONTADOR.md` — **FECHADA em 22/09** (`9aa79b4` e `33a9bcb`, suíte
  completa 2.884 verdes). A triagem agora reformula a pergunta uma vez e depois entrega à fila com
  o texto preservado; o contador do Chat Interno passou a somar pelo mesmo predicado que a lista
  usa. Ver o cabeçalho da própria tarefa pelo que foi decidido e pelo que divergiu do plano.
- `docs/db/TAREFA_SPLIT_BACKEND.md` — plano pronto (Sessão B, `f60cf3b`). O Grupo A pode começar
  por Admin a qualquer momento; o Grupo B está **travado numa decisão do Marcelo**: as ~9 rotas
  sob `/ciclo/` que, pelo código, são de Financeiro ou Comercial(PE) seguem o comportamento
  (Opção A) ou o prefixo da URL (Opção B). A pergunta é de modelo de negócio — se desligar o
  módulo Financeiro numa loja tem que bloquear `ciclo/21/conciliar` de verdade ou não.
- `docs/db/RASCUNHO_PORTAO_E2E.md` — rascunho para debate sobre o portão da suíte; ainda não foi
  discutido com o Claude Code.

## Aberto e sem dono escrito em lugar nenhum

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
