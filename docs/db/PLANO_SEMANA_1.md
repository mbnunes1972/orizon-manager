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

   **Como conferir — precisão da Sessão A (21/09), melhor que a redação original:** não basta
   procurar `pytest` nas outras sessões. O que consome a máquina é o **Chromium do Playwright
   MCP**, que fica vivo mesmo com a sessão ociosa. Antes da suíte completa:
   `ps -eo pid,etime,rss,args | grep -Ei 'chrom|playwright|claude' | grep -v grep`. Sessão-irmã
   com Chromium vivo conta como ocupada, ainda que ninguém esteja digitando nela.
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
