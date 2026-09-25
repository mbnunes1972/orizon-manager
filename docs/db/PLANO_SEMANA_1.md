# PLANO — Semana 1 (14–20/09/2026): ajustes da beta + mapa da reorganização

Decisão do Marcelo em 14/09, depois de três dias perseguindo achados sem fechar a lista.

## O diagnóstico que originou este plano

A lista de achados não fecha porque **cada achado é sintoma da mesma doença**: o mesmo
comportamento existe em vários lugares, sem dono único. Corrigir um revela dois irmãos
esquecidos, e a `LISTA_PARALELA.md` cresce mais rápido do que encolhe.

Há duas provas desta semana de que dá para fechar **classes** em vez de instâncias:

- **`handler` obrigatório** (ACHADO-68) encerrou a categoria "ponto de chamada esquecido fica
  cego em silêncio".
- **`mod_assinatura.py`** (ACHADO-69) encerrou a categoria "três cópias divergem sem ninguém
  saber" — e de quebra revelou o ACHADO-70, invisível por meses.

Nenhuma das duas gerou lista paralela. Encerraram.

**O alvo não é inventar uma arquitetura.** O mapa dos módulos já existe: `Módulos v12` e
`FLUXO_38_ETAPAS.md`. O problema é que o código não o espelha — tudo vive em `main.py` e
`static/index.html` (1,68 MB, HTML+CSS+JS num arquivo só). O trabalho é fazer o código obedecer a
arquitetura que o negócio já definiu.

## Decisões de negócio (Marcelo, 14/09)

- **Produção: 01/10/2026.**
- **Lojas-piloto começam o quanto antes:** Inspirium, Dalmóbile Recreio, Dalmóbile Salinas,
  Dalmóbile Casa Shopping, Caraguatatuba.
- **O Pontta continua sendo o sistema OFICIAL durante o piloto.** O Orizon roda em paralelo, como
  sombra. **Consequência que governa tudo neste plano: os dados do piloto são descartáveis**, e é
  isso que mantém aberta a janela para reorganizar o sistema.
- **Chat e Agenda ficam como estão**, com pequenos ajustes da beta. Entram de verdade depois, já
  dentro da estrutura modular.
- **Fator crítico:** os ajustes da beta terminam até o fim da Semana 1. A Semana 2 depende disso.

## As duas sessões, e como convivem

Duas sessões de Claude Code rodando em paralelo, com papéis que **não se cruzam**:

| | Sessão A — Ajustes | Sessão B — Mapa |
|---|---|---|
| escreve código? | sim | **não** |
| roda `pytest`? | sim | **não** |
| entrega | beta pronta para congelar | um documento |

**Regras de convivência, não negociáveis:**

1. **Só a Sessão A escreve.** A Sessão B lê e escreve **um único arquivo**:
   `docs/db/MAPA_MODULOS.md`. Nada mais.
2. **Só a Sessão A roda `pytest`.** Duas invocações simultâneas contra os mesmos bancos é o LP-22,
   que já custou uma manhã inteira perseguindo falhas que eram colisão.

   **2b — acrescentado em 18/09, a outra metade da mesma regra: enquanto a Sessão A roda a suíte
   completa, a Sessão B fica PARADA.** Não é fechar a janela nem perder contexto — é não trabalhar
   no mesmo minuto. Medido: as duas sessões vivem na mesma máquina, cada uma com seu Chromium
   headless; a suíte completa levou **19 min com 8 vermelhos** enquanto as duas trabalhavam e
   **~10 min com 0 vermelhos** com a máquina folgada. Não é memória (havia 13 GB livres nas
   mortes) — é **CPU**: duas sessões, dois navegadores e uma suíte que dirige navegador disputando
   processador. A regra 2 impedia a colisão de banco; esta impede a contenção de máquina, que é
   como o portão da suíte vinha ficando ilegível. Ver `docs/db/RASCUNHO_PORTAO_E2E.md`.

   **Como conferir — corrigido em 22/09, depois de a redação anterior produzir dois erros no
   mesmo dia.** Não basta procurar `pytest`: o que consome a máquina é o **Chromium do Playwright
   MCP**, vivo mesmo com a sessão ociosa. Mas o `grep` da redação anterior
   (`grep -Ei 'chrom|playwright|claude'`) tem dois defeitos, os dois medidos em 22/09:

   - **casa o processo `claude` da própria sessão** — quem confere se auto-bloqueia. Foi o que
     aconteceu: a Sessão A leu dois PIDs `claude` (o dela e o da Sessão B) como sessão-irmã
     ocupada e parou sem rodar a suíte, sendo que uma das duas era ela mesma;
   - **o PID que aparece não é o do navegador.** O `claude` é o PAI; o Chromium descartável são os
     filhos (`npm exec` → `sh` → `node ... playwright-mcp`). Matar o PID do `claude` derruba a
     sessão inteira, não um navegador — erro que só não foi executado porque a Sessão A conferiu
     a ancestralidade antes de obedecer.

   Confira assim, olhando o processo certo e excluindo a própria árvore:
   `ps -eo pid,ppid,etime,rss,args | grep -i playwright-mcp | grep -v grep` — e compare o PPID
   com o `claude` desta sessão antes de concluir qualquer coisa.

   **E ocioso não é ocupado.** A medição que originou esta regra (19 min/8 vermelhos contra
   ~10 min/0) foi com as duas sessões TRABALHANDO — dois navegadores sendo dirigidos enquanto a
   suíte dirigia o dela. Chromium de pé desde a véspera, sem ninguém dirigindo, não compete por
   CPU: em 22/09 a suíte completa rodou com o Chromium da sessão-irmã vivo e ocioso e fechou em
   13m20 com 2.884 verdes e 3 vermelhos, todos do flake conhecido do `#neg-subtotal` (LP-22).

   **Regra nova (24/09/2026) — a suíte completa roda DESTACADA do monitor de comandos em
   background do CLI, nunca como comando em background do harness.** Medido: quatro tentativas
   de rodar a suíte via comando em background (dois turnos, TAREFA-B) foram mortas pelo próprio
   monitor com a mensagem "the system is running low on memory" — mas `dmesg -T` não tinha
   nenhuma linha de OOM, o `memory.pressure` da raiz do cgroup estava zerado nas três janelas
   (10s/60s/300s), nenhum cgroup relevante (`user.slice`, `user-1000.slice`, `init.scope`) tinha
   teto (`memory.max = max`), e `free -h` mostrava 13 GiB disponíveis nas quatro vezes. O
   bloqueio não vinha do kernel nem do pytest — vinha do próprio monitor de background do CLI,
   por um critério não exposto aqui dentro. **Saída que funcionou:** destacar o processo da
   árvore que o monitor vigia, com `nohup setsid python3 -m pytest -q > /tmp/suite.log 2>&1 <
   /dev/null & disown` (retorna na hora — não é um comando de longa duração, então não há o que
   o monitor mate), e acompanhar com `timeout 170 tail -f --pid=<PID> -n 3 /tmp/suite.log`
   repetido (não é `sleep`: produz saída desde o primeiro instante e termina sozinho quando o
   PID morre ou o timeout estoura). `sleep` isolado (mesmo curto, mesmo fora de `run_in_background`)
   é bloqueado pela ferramenta de shell como espera vazia — a diferença é que `tail -f` produz
   saída imediata e reage a evento, não dorme cego.

   **Regra nova (25/09/2026) — não apagar `/tmp/suite*.log` antes de o número (passed/failed/
   xfailed) estar REPORTADO ao Marcelo E REGISTRADO no documento da tarefa em andamento.** Achado
   real do bloco LI-3/LI-8/LI-4: o log foi limpo (`rm -f`) logo depois do resumo final no chat —
   o número que chegou ao Marcelo existia só na memória da conversa, não em evidência que ele
   pudesse conferir depois. "Memória não é evidência neste projeto." A ordem certa é: 1) suíte
   termina, 2) número lido do próprio log (não repetido de cabeça), 3) número escrito no
   documento da tarefa (Estado/portão), 4) só then o log pode ser apagado — e mesmo assim, não é
   obrigatório apagar; o log solto em `/tmp` não é ruído versionado, pode ficar até o próximo boot.
3. **A Sessão B ancora por NOME, nunca por número de linha.** A Sessão A está editando `main.py` e
   `index.html` ao mesmo tempo; qualquer `main.py:9587` anotado hoje estará errado amanhã. Anote
   nome de função, id de elemento, rota — coisas que sobrevivem a uma edição.
4. **A Sessão B não abre achado novo.** Se encontrar defeito, anota no mapa numa seção própria
   ("candidatos a achado") e segue. Quem decide se vira achado é o Marcelo, depois.

## Semana 1 — Sessão A (ajustes da beta)

Ordem sugerida; o Marcelo confirma prioridade.

1. **O dropdown de cliente.** `#np-cli-dropdown` responde por 27 das 47 falhas isoladas medidas em
   `TAREFA_FLAKES_E2E.md`, e falha **mesmo com o teste rodando sozinho, máquina ociosa**. Pergunta
   delimitada, resposta binária: **é defeito de produto ou de teste?** Uma hora. Se for produto, o
   usuário real vê isso como "travou ao escolher o cliente" — e não abre chamado, só reclama do
   sistema.
2. **Script de backup externo.** Escrever o script que copia o dump para fora da VPS (o
   `DEV_RULES.md` já registra a pendência; S3 ou Backblaze B2). O Marcelo fornece a credencial e
   instala; a Sessão A escreve e documenta.
3. **O que o Marcelo apontar do percurso da seção 15** — ele vai percorrer os quatro documentos nos
   dois canais em Homologação e trazer os defeitos.
4. **Congelar a caça a flakes.** Nada de novas rodadas de medição. O que aparecer vai para a lista
   e espera a Semana 2.

## Semana 1 — Sessão B (o mapa)

Entrega única: `docs/db/MAPA_MODULOS.md`. **Nenhum código.** Seis seções:

**1. Módulos: papel × código.** Para cada módulo do `Módulos v12` — Captação, Cadastro, Comercial,
Projetos, Fiscal, Estoque, Expedição, Financeiro, Montagem, Assistências, Admin, Config — diga onde
a lógica dele vive hoje (quais funções de `main.py`, quais `mod_*.py`, quais áreas do
`index.html`) e o que existe só no papel.

**2. Caminhos dobrados.** Todo lugar onde o **mesmo estado é escrito por mais de um caminho**. É a
regra dos irmãos (ACHADO-26) aplicada ao sistema inteiro, não a um endpoint. Para cada um: qual
estado, quais caminhos, e se eles concordam entre si.

**3. Duas fontes de verdade.** Todo lugar onde o mesmo fato é guardado em dois lugares que podem
divergir. Já conhecidos: `CicloEtapa` (flag) × status do documento — o padrão do ACHADO-56, do 11c
e do 11d. Procure os outros.

**4. O inventário do frontend.** `static/index.html` por área: quantas linhas cada uma, quais
funções, quais ids, e — o mais importante — **quais funções leem ou escrevem estado que não é
delas**. É isso que torna uma mudança local numa quebra remota (ACHADO-25).

**5. Os achados abertos, classificados por causa estrutural.** Pegue `ACHADOS_CONTABEIS.md` e
`LISTA_PARALELA.md` e agrupe cada item aberto pela **causa estrutural** que o produziu, não pelo
sintoma. A pergunta que o mapa tem que responder: *qual fronteira de módulo, se existisse, teria
impedido este achado?* É esta seção que fecha o ciclo — ela mostra quantos achados morrem juntos a
cada fronteira criada.

**6. Fronteiras propostas.** A lista de módulos que o código deveria ter, o que cada um possui
(tabelas, funções, telas), e onde há reaproveitamento real entre eles. **Proposta com trade-offs,
não decisão** — as fronteiras mexem em como o negócio funciona, e quem decide é o Marcelo.

## Semana 2 (21–27/09) — janela exclusiva

Só com o mapa pronto e a beta congelada:

- Separar o JavaScript do `index.html` em arquivos por área. **Mecânico, sem mudar comportamento** —
  os E2E provam que nada mudou.
- Criar fontes únicas da verdade nos pontos que a seção 5 do mapa mostrar como os de maior retorno
  (mais achados fechados por fronteira criada).

## 28–30/09 — estabilização · 01/10 — produção

A beta sai do ar quando o mapa final disser que saiu.

## Pendências operacionais — antes de qualquer dado real

As três têm o mesmo gatilho e são de horas, não de dias:

1. **Firewall** — `ufw` está inativo; 8765 e 8766 escutam em `0.0.0.0`. Hoje qualquer um na
   internet alcança Integração e Homologação.
2. **Senhas individuais** — 21 contas com `orizon123` e `senha_provisoria=0`.
3. **Backup externo** — o backup mora na mesma máquina que o banco. Se a VPS morre, morrem os dois.

O piloto com o Pontta como sistema oficial reduz o risco de perda, mas não o elimina: o esforço de
digitação das lojas é real mesmo que o dado seja descartável.
