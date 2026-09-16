# Decisões de Arquitetura — Orizon Manager

> **Camada 2 · POR QUE ESTÁ ASSIM.** Tem que ser verdade sempre. Decisão revista não se apaga —
> marca-se `[SUPERADA POR ...]` ou `[REVISTA EM ...]`, dizendo o quê e quando. Ver `docs/README.md`.

Registro de decisões técnicas **e de negócio** importantes. Antes de reverter qualquer item, leia
o contexto.

**Auditoria de 2026-09-16:** os nove ADRs originais (todos de 2026-06, todos "Ativo" havia três
meses) foram revisados um a um. Quatro estavam desatualizados a ponto de enganar quem lesse sem
checar o código — o pior caso, ADR-004, descrevia o sistema como "não exposto publicamente" numa
altura em que ele escuta a internet sem firewall na maior parte dos ambientes. Nenhum ADR foi
apagado; os revistos ganharam nota datada abaixo do texto original, preservado.

Nesta mesma auditoria foram acrescentadas as decisões tomadas entre junho e setembro que nunca
tinham virado ADR — técnicas e de negócio. Sem isso, decisões reais (a esteira de quatro estágios,
a janela de reaprovação, a reversão da "decisão 12", as oito decisões de 15/09) continuavam
existindo só em mensagem de commit ou em documento de Camada 4/5, que não tem o compromisso de
"tem que ser verdade sempre" — a mesma falha que produziu os quatro ADRs desatualizados.

---

## ADR-001 — SQLite com SQLAlchemy em vez de MySQL direto
**Data:** 2026-06-07
**Status:** **[SUPERADA POR ADR-010 — Migração para PostgreSQL, 2026-07-15]**

**Decisão:** Usar SQLite + SQLAlchemy para o banco de dados inicial.

**Contexto:** O sistema é usado por uma loja por vez. O volume de acessos simultâneos é baixo. MySQL exigiria configuração adicional no servidor.

**Consequência:** Migração futura para MySQL é simples — trocar a string de conexão. O resto do código não muda.

> **Nota de revisão (2026-09-16):** a "migração futura" não foi para MySQL — foi para PostgreSQL,
> em 2026-07-15, e não foi "só trocar a string de conexão": ver ADR-010. SQLite foi **removido por
> inteiro** do sistema na faxina de 2026-07-23 (Sessão 113) — código de migração raw `sqlite3`,
> `DB_PATH` e o escape `ORIZON_ALLOW_SQLITE` deixaram de existir; `init_db` recusa hoje qualquer
> dialeto que não seja Postgres. `CLAUDE.md`, seção "Áreas sensíveis" → "Banco de dados", é a fonte
> viva deste fato.

---

## ADR-002 — Servidor HTTP nativo Python sem framework
**Data:** 2026-06-07
**Status:** Ativo

**Decisão:** Usar `http.server` nativo do Python em vez de Flask/FastAPI.

**Contexto:** O projeto já existia com essa estrutura. Migrar para um framework quebraria muito código existente.

**Consequência:** Rotas definidas manualmente no `do_GET` e `do_POST` do `main.py`. Ao adicionar novas rotas, seguir o padrão `elif path == "/rota":`.

> **Nota de revisão (2026-09-16):** confirmada válida — continua sendo a arquitetura descrita em
> `CLAUDE.md`. O que mudou desde junho não é esta decisão, é a **organização interna** do código
> em torno dela: alguns domínios (`fiscal/`, `integracoes/`, `auth/`, `mod_fin/`) viraram pacote
> Python, reorganização em andamento desde 2026-07-15 (`CLAUDE.md`, "Layout do código"). Isso não
> contradiz o ADR-002 — ainda é `http.server` sem framework, só que com módulos agrupados por
> domínio em vez de soltos na raiz.

---

## ADR-003 — Frontend SPA sem framework JavaScript
**Data:** 2026-06-07
**Status:** **[REVISTA EM 2026-09-16]**

**Decisão:** Manter o frontend em HTML/CSS/JS puro sem React, Vue ou similar.

**Contexto:** O projeto já existia assim. A adição de um framework quebraria o código existente e aumentaria a complexidade.

**Consequência:** Toda a lógica de UI está em `static/index.html`. O arquivo é grande (~3500 linhas). Ao adicionar funcionalidades, seguir os padrões existentes de navegação (`goPage()`) e modais.

> **Nota de revisão (2026-09-16):** a decisão em si (sem framework JS) continua valendo — nenhum
> documento revisado propõe adotar um. O número "~3500 linhas" está obsoleto há muito: medido hoje,
> `static/index.html` tem **26.582 linhas / ~1,7 MB** (era 26.551 linhas em 15/09, segundo
> `docs/db/TAREFA_SPLIT_FRONTEND.md` — cresce a cada funcionalidade). Desse total, um único bloco
> `<script>` de ~22.000 linhas é JavaScript.
>
> Há um plano escrito para separar esse JavaScript em ~15 arquivos dentro de `static/js/`, por
> domínio (`docs/db/TAREFA_SPLIT_FRONTEND.md`, 2026-09-15), agendado para a "Semana 2"
> (21–27/09/2026) — ainda não executado nesta data. HTML e CSS continuam no arquivo único; só o JS
> sai. A decisão de não usar framework **não é revertida por esse plano** — é sobre organização de
> arquivo, não sobre arquitetura de UI. Ver também "Motor 5.0" em `CLAUDE.md` (reestruturação maior,
> execução adiada até a v1 atual estabilizar) — outra frente, não confundir as duas.
>
> Consequência prática para quem for editar: os testes que travam contagem/faixa de linha absoluta
> do arquivo (família do ACHADO-36) deixam de fazer sentido assim que a extração acontecer — ver
> `docs/db/LISTA_PARALELA.md`, LP-30.

---

## ADR-004 — Autenticação por cookie de sessão server-side
**Data:** 2026-06-07
**Status:** **[REVISTA EM 2026-09-16]**

**Decisão:** Usar cookie `omie_session` com token gerado no servidor, em vez de JWT.

**Contexto:** Sistema interno, não exposto publicamente. Simplicidade foi priorizada.

**Consequência:** Sessões ficam na tabela `sessoes` do banco. Expiração em 8 horas. Logout invalida o token no banco.

> **Nota de revisão (2026-09-16) — a mais importante desta auditoria.** Duas coisas mudaram desde
> junho, uma cosmética e uma que invalida a premissa da decisão:
>
> 1. **O cookie mudou de nome.** `omie_session` → `orizon_session`, na faxina de 2026-07-23, junto
>    da remoção da integração Omie (`CLAUDE.md`). O mecanismo (token no servidor, tabela `sessoes`,
>    TTL de 8h) não mudou.
> 2. **A premissa "sistema interno, não exposto publicamente" não é mais verdade.** Hoje: Integração
>    e Homologação (`167.88.33.121`) escutam em `0.0.0.0` com as portas 8765/8766 liberadas no
>    firewall (`DEV_RULES.md`, "Bind"); Produção também está configurada com `ORIZON_HOST=0.0.0.0`
>    (`CLAUDE.md`, "Áreas sensíveis" → "Banco de dados"). O sistema está prestes a receber tráfego
>    real de lojas piloto (`docs/db/IMPLANTAR.md`, "Backup externo — pré-requisito antes de tráfego
>    real de Captação/Chat").
>
>    Existe um plano escrito — mas **não confirmado como executado** nesta data — para colocar
>    Integração/Homologação atrás de nginx + TLS (Let's Encrypt) e voltar o bind para `127.0.0.1`,
>    fechando as portas diretas no firewall: `docs/db/IMPLANTAR.md`, seção "Exposição segura de
>    Integração/Homologação — nginx + TLS + bind interno" (escrito 2026-09-14). Esse plano cobre
>    Integração e Homologação; **não há, nos documentos revisados, um plano equivalente registrado
>    para Produção**, que segundo `CLAUDE.md` já está em `0.0.0.0`.
>
> **Consequência prática:** a autenticação por cookie de sessão server-side continua sendo o
> mecanismo — não está sendo substituída por JWT, e nada aqui é argumento para trocar. Mas ela hoje
> protege um sistema alcançável pela internet, sem TLS nem reverse proxy confirmados na maior parte
> do tempo. A contrapartida de segurança que a decisão original citava ("sistema interno") não
> existe mais, e um ADR desatualizado dizendo o contrário é pior que nenhum ADR — foi exatamente
> este achado, em 15/09, que motivou a reorganização da documentação em camadas (ver `docs/README.md`,
> preâmbulo da Camada 2). **[VALIDAR]** com o Marcelo se a exposição de Produção em `0.0.0.0` é
> deliberada (por trás de outro reverse proxy não documentado aqui) ou é a mesma dívida que
> Integração/Homologação estão fechando.

---

## ADR-005 — Parâmetros internos não afetam valor do cliente
**Data:** 2026-06-08
**Status:** Ativo

**Decisão:** Comissão de arquiteto, fidelidade, viagem e brinde são custos internos da loja. O cliente vê apenas: Valor bruto → Desconto → Valor à vista → Juros financiamento = Total.

**Contexto:** Esses parâmetros reduzem a margem da loja mas não são repassados ao cliente como itens de linha. Opcionalmente podem ser incluídos no valor bruto via gross-up (toggle "Incluir custos adicionais?").

**Consequência:** `_negBaseValues[i].estrutural` = valor bruto original do XML por padrão. Quando "Incluir custos adicionais?" ativo, aplica gross-up: `bruto / (1 - arq%) / (1 - fid%) + viagem + brinde`.

> **Nota de revisão (2026-09-16):** o princípio (parâmetros internos não viram linha visível para
> o cliente) continua valendo — nenhum documento revisado o contradiz. Mas o detalhe de
> implementação citado na Consequência está errado hoje: `_negBaseValues` **nunca é populado**
> (sempre `[]`) — `CLAUDE.md`, "Negociação/motor": *"não confie nele; use o motor/preview
> (`_previewNeg.VBNO`, `neg-subtotal`)"*. O mecanismo evoluiu bastante desde junho — Item Especial,
> `Desc_Efetivo`, `Cust_Via_Recup`/`Bri_Recup`/`Cust_Esp_Recup` — tudo isso resolvido pelo motor de
> negociação (`mod_negociacao.py`) e não mais por cálculo direto no JS. Histórico completo em
> `docs/db/CADERNO_DE_BORDO.md` (F2-32 a F2-39, ACHADO-63 a 66).

---

## ADR-006 — Limite autorizado = desconto específico aprovado
**Data:** 2026-06-08
**Status:** Ativo

**Decisão:** Quando um gerente autoriza 15%, o novo limite para aquela negociação é 15% — não 20% (limite do gerente).

**Contexto:** Evita que uma autorização pontual se torne uma permissão ampla.

**Consequência:** `_limiteAutorizado` recebe o valor do desconto aprovado, não o limite do perfil do autorizador. Persiste durante a negociação, reseta ao trocar de projeto.

> **Nota de revisão (2026-09-16):** confirmada válida — nenhum documento revisado (ACHADOS_CONTABEIS.md,
> CADERNO_DE_BORDO.md, LISTA_PARALELA.md) registra mudança neste comportamento. Não confundir com
> o ADR-015 (janela de reaprovação de 15 minutos): aquele muda **quantas vezes** a senha é pedida
> para `aprovar_financeiro`; este ADR-006 é sobre **qual limite** vale depois de uma autorização de
> desconto. Mecanismos diferentes, sem sobreposição.

---

## ADR-007 — Projetos persistidos em JSON, não no banco
**Data:** Antes de 2026-06-07
**Status:** **[REVISTA EM 2026-09-16]**

**Decisão:** Cada projeto é salvo como `PROJETOS/<nome_safe>/projeto.json`.

**Contexto:** Decisão anterior ao início desta documentação. Permite portabilidade e inspeção manual.

**Consequência:** Projetos não estão no SQLite. Relacionamentos (cliente_id, parceiro_id) são campos dentro do JSON. Busca de projetos é feita lendo os arquivos do sistema de arquivos.

> **Nota de revisão (2026-09-16):** a premissa "projetos não estão no banco" não é mais verdade
> como está escrita. Existe hoje uma tabela `projetos_meta` (classe `Projeto`, `database.py`) com
> metadados de pipeline — status, datas de entrega/início, escopo por criador
> (`criado_por_id`, usado pela regra de "Consultor vê só os projetos que criou" — `CLAUDE.md`,
> "Áreas sensíveis"), cronograma, equipe. Boa parte do que antes só existia no JSON hoje tem tabela
> própria no Postgres: orçamentos (`orcamentos`), vínculos de ambiente (`OrcamentoAmbiente`), fases
> (`parcela_projeto`/`parcela_ambiente`), e mais — parte da modelagem que cresceu junto com a
> migração geral para PostgreSQL (ADR-010, 2026-07-15).
>
> O `projeto.json` **continua existindo** — 9 referências em `main.py` medidas em 2026-09-16 — como
> registro legado/snapshot: `main.py:19824` documenta *"Preenche campos vazios do banco com o que
> foi salvo no projeto.json"* para projeto legado sem registro completo no banco. Ou seja: hoje é um
> estado híbrido, banco como fonte primária para o que já foi modelado, JSON como fallback para o
> resto — não mais "tudo no JSON, nada no banco" como o ADR original descreve.
>
> **Esta é uma auditoria superficial** (não foi mapeada cada leitura/escrita de `projeto.json`) — o
> suficiente para dizer que o ADR original engana quem o lê hoje, não o suficiente para escrever com
> precisão o estado atual. **[VALIDAR]** com o Marcelo se vale abrir uma frente para terminar a
> migração e aposentar `projeto.json` de vez, ou se o hoje híbrido é intencional e deveria virar um
> ADR novo, escrito com mais cuidado do que esta nota permite.

---

## ADR-008 — Um parceiro por projeto
**Data:** 2026-06-08
**Status:** Ativo

**Decisão:** Cada projeto tem no máximo um parceiro vinculado.

**Contexto:** Simplicidade operacional. Casos com múltiplos parceiros são raros e podem ser tratados via observações.

**Consequência:** `projeto.json` tem campo `parceiro_id` (null ou integer). A estrutura permite expandir para N parceiros no futuro sem mudança drástica.

> **Nota de revisão (2026-09-16):** sem evidência de mudança na regra — não existe, em
> `database.py`, nenhuma tabela de vínculo N:N parceiro×projeto (existe `parceiro_lojas`, mas é
> vínculo parceiro×**loja**, outra relação). O comportamento (um parceiro por projeto) parece
> continuar valendo. O que está em transição é **onde** o campo `parceiro_id` mora — ver a revisão
> do ADR-007, acima: se ele ainda vive só no `projeto.json`, esta ADR herda a mesma imprecisão sobre
> armazenamento que aquela.

---

## ADR-009 — Bind 0.0.0.0 no servidor via sed após git pull
**Data:** 2026-06-08
**Status:** **[SUPERADA POR ADR-011 — Deploy por tag, 2026-08-31]**

**Decisão:** O `main.py` no GitHub usa `127.0.0.1`. No servidor, após `git pull`, executa-se `sed -i 's/127.0.0.1/0.0.0.0/g' main.py`.

**Contexto:** Permite que o código local funcione sem expor o servidor de desenvolvimento.

**Consequência:** O `main.py` no servidor sempre diverge do GitHub após o pull. Sempre executar `git checkout main.py` antes do `git pull` no servidor.

**Alternativa considerada:** Variável de ambiente `ORIZON_HOST` — mais elegante, não implementada ainda.

> **Nota de revisão (2026-09-16):** a alternativa citada na própria ADR foi implementada. Hoje
> `main.py` lê `ORIZON_HOST` de variável de ambiente (`DEV_RULES.md`), sem `sed` nenhum, e o deploy
> em todo ambiente é por **tag** — o servidor faz `git checkout <tag>`, nunca `git pull` de `main`
> (ver ADR-011). O procedimento de `sed`/`git checkout main.py` descrito aqui não existe mais em
> nenhum ambiente.

---

## ADR-010 — Migração de SQLite para PostgreSQL
**Data:** 2026-07-15
**Status:** Ativo — supersede o ADR-001

**Decisão:** Trocar SQLite por PostgreSQL como único banco suportado.

**Contexto:** Multi-loja/rede exigia concorrência e integridade referencial real que o SQLite não
sustentava com conforto (FK enforcement, escrita concorrente). A "migração simples de string de
conexão" prevista no ADR-001 nunca foi para MySQL — foi decidida para PostgreSQL, com plano próprio.

**Consequência:** `DATABASE_URL` (com `+psycopg2`) passa a ser obrigatório — sem ele, o app explica
e sai. A suíte de teste roda sempre contra Postgres (`orizon_test`, derivado do `.env`). SQLite foi
removido por inteiro na faxina de 2026-07-23 (Sessão 113): código de migração raw `sqlite3`,
`DB_PATH` e o escape `ORIZON_ALLOW_SQLITE` deixaram de existir; `init_db` recusa qualquer dialeto
que não seja Postgres. Schema versionado por Alembic desde então (ver `docs/db/ESTEIRA.md`,
"Alembic ainda não tem baseline" ficou resolvido — regras R1–R16 em `CLAUDE.md`).

**Fonte:** `docs/superpowers/specs/_geral/2026-07-15-migracao-postgresql.md` (plano/rationale
completo, Camada 5 — não editar, só consultar).

---

## ADR-011 — Deploy por tag, nunca `git pull` de `main`
**Data:** 2026-08-31
**Status:** Ativo — supersede o ADR-009

**Decisão:** Toda implantação sai de uma tag (`v2026.08.31-1`, `-2`, …). O servidor faz `git
checkout <tag>`, nunca `pull`. Rollback é fazer checkout da tag anterior. A tag é criada na
bancada, depois de a suíte passar, e nunca é movida.

**Contexto:** Não havia como responder "o que está rodando em Homologação?" sem entrar no servidor
e olhar o `git log`. Produção chegou a sair da esteira por três dias (`git checkout main` manual em
28/08) sem que ninguém percebesse por uma semana — só descoberto porque a regra ainda não existia.

**Consequência:** O fim de um ciclo de trabalho passa a ser "suíte verde + tag criada", não
"commitado". Ninguém edita código em servidor — servidor recebe checkout e migration; correção
direta em servidor não existe na bancada e some no próximo deploy. Procedimento operacional
detalhado (backup → parar serviço → checkout → migration → subir → smoke) descrito em
`docs/db/IMPLANTAR.md`, "Deploy rotineiro — procedimento padrão" (2026-09-13).

**Fonte:** `docs/db/ESTEIRA.md`.

---

## ADR-012 — A esteira de quatro estágios: Bancada → Integração → Homologação → Produção
**Data:** 2026-08-31
**Status:** Ativo

**Decisão:** Separar **ambiente** de **bancada**, com critério objetivo de saída para cada estágio.
Bancada (onde se escreve código; não é ambiente, ninguém valida nada nela) → Integração (primeiro
alvo de deploy automático, prova que o deploy funciona) → Homologação (o Marcelo clica, com dado
parecido com o real) → Produção (só o que passou pelos três).

**Contexto:** Os três servidores já existiam com migrations encadeadas e `confirmar.sh`, mas nada
impedia pular etapa — a implantação simultânea nos três no marco da Fase 1 expôs isso.

**Consequência:** Bancada→Integração exige `pytest -q` verde + E2E de navegador verde + tag criada;
Integração→Homologação exige migrations no head + `confirmar.sh` 15/0 + smoke; Homologação→Produção
exige percurso do Marcelo aprovado + defeitos conhecidos documentados e aceitos. Nenhum estágio
avança sem o critério do anterior cumprido.

**Fonte:** `docs/db/ESTEIRA.md`.

---

## ADR-013 — Reversão da "decisão 12": contato inbound sem match vira `Lead`, não `Cliente` direto
**Data:** 2026-09-14 (reversão; a "decisão 12" original é anterior, sem data localizada nesta auditoria)
**Status:** Ativo

**Decisão:** `chat/triagem.py::triagem_materializar` passa a criar um registro `Lead` — não mais
`Cliente` — quando um contato comercial chega por canal inbound (WhatsApp, tipicamente) sem
corresponder a um cadastro existente.

**Contexto:** A "decisão 12" original fazia o oposto: contato inbound sem match virava `Cliente`
direto, sem estágio de qualificação. Isso promovia a `Cliente` leads de Google/Instagram/Facebook
que chegavam por WhatsApp antes de qualquer briefing — cadastro inflado com contatos que nunca
viravam projeto. A entidade `Lead` (nova, `PLANO_SEMANA_1.md`) resolve essa demanda represada:
núcleo fixo de campos + `dados_json`/`template` para o que varia por formulário de captação, sem
fila, funil ou atribuição automática — deliberadamente provisória, não o módulo de Captação
definitivo (esse é pós-1.0, ver ADR pendente quando a fronteira 6.7 for construída).

**Consequência:** Um contato vira `Cliente` só ao ser promovido deliberadamente a partir de um
`Lead` — nunca mais automaticamente na triagem. `Lead.cliente_id` registra a conversão, preenchido
só nesse momento, nunca na criação.

**Fonte:** `docs/db/LISTA_PARALELA.md`, LP-29 (FRONTEIRA/6.7); `docs/db/PLANO_SEMANA_1.md`.

---

## ADR-014 — Canal × origem: dois campos que nunca se fundem
**Data:** 2026-09-14
**Status:** Ativo

**Decisão:** `Lead.canal` (DE ONDE o lead veio — google, instagram, facebook, site...) e
`Cliente.origem` (COMO o cliente chegou — porta, arquiteto, indicação, ou `"lead/" + Lead.canal`
quando vem de conversão) são campos **deliberadamente separados**, e nunca se fundem num só.

**Contexto:** Um campo só para as duas perguntas seria mais uma instância da "Causa B" do
`MAPA_MODULOS.md` — um campo carregando dois significados (a mesma família de problema do LP-23,
"campo genérico carregando venda × execução"). Na conversão de Lead para Cliente, `Cliente.origem`
é preenchido automaticamente como `"lead/" + Lead.canal` — nunca digitado à mão.

**Consequência:** Qualquer relatório ou tela que queira "de onde vêm os clientes" precisa decidir
explicitamente se a pergunta é sobre a campanha/plataforma (`canal`) ou sobre a via de entrada
(`origem`) — não existe campo único que responda as duas.

**Fonte:** `database.py`, docstrings de `Cliente.origem` e `Lead.canal` (linhas ~262-270 e
~287-288); `docs/db/PLANO_SEMANA_1.md`.

---

## ADR-015 — Janela de reaprovação de 15 minutos para `aprovar_financeiro`
**Data:** 2026-09-10
**Status:** Ativo — revê decisão anterior de 2026-08-25 (nunca formalizada em ADR)

**Decisão:** A senha para operações de `aprovar_financeiro` é pedida **uma vez** e abre uma janela
de 15 minutos, do lado do **servidor**, atrelada ao token da sessão, durante a qual os passos
seguintes da mesma capacidade não pedem senha de novo. Expiração absoluta (não deslizante),
revogada no logout.

**Contexto:** Em 2026-08-25 havia sido decidido que `aprovar_financeiro` pedisse senha a cada
passo, sem atalho — mesmo para quem já tinha a capacidade, como camada extra de confiança antes de
mexer no razão contábil. Na prática isso significava reautenticar repetidamente numa mesma operação,
incômodo relatado pelo Marcelo em 2026-09-10 (ACHADO-68). A janela preserva o ato deliberado antes
de mexer no razão (a decisão de 25/08 não foi anulada, foi afrouxada) e mata a repetição.

**Consequência:** A janela é **por capacidade**, não por sessão inteira — abrir para
`aprovar_financeiro` não libera nenhuma outra capacidade. Atos irreversíveis (ex.:
`cancelarContrato`) formam uma terceira categoria que **sempre** pede senha, sem atalho e sem
janela, mesmo com a janela de `aprovar_financeiro` aberta na mesma sessão — marcados por
`capacidade: 'sempre_pedir'`, reconhecido por nome, nunca por ser falsy. `LogAcaoGerencial`
continua gravando o autorizador em toda operação dentro da janela — a janela dispensa a digitação,
nunca o registro. `/parametros` e `/descontos` (família `_usuario_autoriza_desconto`, que autoriza
por limiar numérico, não por capacidade booleana) ficam **de fora** de propósito — uma janela
copiada do modelo de `aprovar_financeiro` concederia mais do que foi autorizado (ver
`docs/db/TAREFA_ACHADO68_REAUTENTICACAO.md`, "Lacunas conhecidas").

**Fonte:** `docs/db/TAREFA_ACHADO68_REAUTENTICACAO.md`; ACHADO-68 em `docs/db/ACHADOS_CONTABEIS.md`.

---

## ADR-016 — Sessão emprestada encerra junto com o ato de autorização, qualquer desfecho
**Data:** 2026-09-10 (regra original); 2026-09-11 (extensão ao caminho triste)
**Status:** Ativo

**Decisão:** Quando um gerente digita suas próprias credenciais dentro da sessão de outro usuário
("sessão emprestada") para autorizar uma operação financeira, essa sessão é encerrada de verdade —
token invalidado no servidor — assim que o ato de autorização termina, **qualquer que seja o
desfecho**: conclusão, falha ou cancelamento. Uma regra só, sem ramificação por tipo de erro.

**Contexto:** A versão original (10/09) só previa encerrar na conclusão. A medição de verificação
(11/09) achou que a sessão sobrevivia a uma operação que falhasse **depois** do aprovador digitar a
senha — o código que mata a sessão nunca era alcançado nesse caminho. Se a elevação sobrevive à
falha, o "caminho triste" vira o caminho preferido de quem quiser abusar: provocar um erro de
propósito, o gerente sair, a sessão elevada continuar aberta.

**Consequência:** A sessão emprestada **não ganha** a janela de 15 minutos do ADR-015 — ela morre
junto com a operação, não sobrevive para autorizar uma segunda. O conserto que acompanha esta
decisão: a validação de dados passou a acontecer **antes** de pedir a senha do gerente, não depois
— um campo obrigatório vazio não deveria nunca "queimar" uma autorização já concedida. Dívida
assumida conscientemente: só 3 das 14 rotas afetadas ganharam essa reordenação até o fechamento
(12/09); as outras 11 seguem pedindo a senha antes de validar o resto (`docs/db/ACHADOS_CONTABEIS.md`,
ACHADO-68, § "Dívida assumida conscientemente").

**Fonte:** `docs/db/TAREFA_ACHADO68_VERIFICACAO.md`, "ADENDO — o caminho triste".

---

## ADR-017 — `handler` obrigatório em `_aprovador_financeiro`: falha silenciosa vira falha barulhenta
**Data:** 2026-09-11/12
**Status:** Ativo

**Decisão:** O parâmetro `handler` de `_aprovador_financeiro` deixou de ter valor default —
tornou-se posicional obrigatório.

**Contexto:** Esquecer `handler` num ponto de chamada novo produzia, antes, um mecanismo cego em
silêncio: a função rodava, não enxergava a sessão, e a única consequência era a janela de
reaprovação (ADR-015) não funcionar ali — sem ninguém perceber. É a mesma classe de defeito do
ACHADO-25 (campo obrigatório novo na tela do aditivo passou despercebido com milhares de testes
verdes, e nenhum aditivo pôde ser assinado em produção).

**Consequência:** Esquecer `handler` num ponto novo agora produz `TypeError` na primeira execução,
não um comportamento degradado e silencioso. `/cancelamento` (categoria "atos irreversíveis" do
ADR-015) declara `handler=None` explicitamente — nunca abre, nunca consulta, nunca aproveita uma
janela aberta por outra operação na mesma sessão, por desenho, não por esquecimento de parâmetro.

**Fonte:** `docs/db/TAREFA_ACHADO68_VERIFICACAO.md`, "Ponta 2".

---

## ADR-018 — Mecanismo único de assinatura eletrônica (ClickSign)
**Data:** 2026-09-11 (decisão); implementação concluída em etapas até 2026-09-13
**Status:** Ativo — parcial (ver Consequência)

**Decisão:** Extrair o mecanismo comum de envio/reconciliação/cancelamento de envelope ClickSign
— hoje replicado em três versões paralelas (Contrato, Aprovação do PE, Solicitação de Medição) —
para um módulo único (`mod_assinatura.py`), migrar os três documentos existentes para ele, e só
então trazer o Termo Aditivo como quarto caso.

**Contexto:** O Marcelo pediu inicialmente para o Aditivo "usar o mesmo mecanismo" (espelhando os
três casos existentes, criando uma quarta cópia). Ao ver as duas saídas lado a lado, decidiu fazer
"o mais certo": extrair o mecanismo, migrar os três, testando em sequência — em vez de perpetuar a
triplicação que já existia entre Contrato/Aprovação PE/Solicitação de Medição.

**Consequência:** `assinatura_canal` e os campos de envelope ClickSign passaram a existir também em
`aditivos` (migration `5325ac7badfa`), e o Aditivo ganhou escolha de canal (interno × ClickSign)
que antes não tinha. **Unificação parcial, por decisão explícita:** `registrar_assinatura`
continua sendo passado como parâmetro externo por documento — a unificação não alcançou o "irmão"
que registra quem assinou e avança o status de cada documento, que seguem sendo quatro
implementações independentes (`_registrar_assinatura_contrato`, `_registrar_assinatura_aprovacao_pe`,
`_registrar_assinatura_solicitacao_medicao`, `_registrar_assinatura_aditivo`). Isso é dívida
registrada, não descoberta agora: `docs/db/LISTA_PARALELA.md`, LP-25, fica como FRONTEIRA/6.1 —
"um setter só, consultado de todo caminho", ainda não construído, esperando o desenho da 6.1.

**Fonte:** `docs/db/TAREFA_ACHADO69_ASSINATURA_UNIFICADA.md`; ACHADO-69/70 em
`docs/db/ACHADOS_CONTABEIS.md`.

---

## ADR-019 — A regra dos destinos da fila
**Data:** 2026-09-15
**Status:** Ativo

**Decisão:** Todo item aberto na Lista Paralela recebe exatamente um de seis destinos — **BETA**
(quebra dinheiro ou impede uma loja de operar; conserto individual na semana em que for
encontrado), **FRONTEIRA** (causa estrutural, morre quando a fronteira correspondente for
construída), **HIGIENE** (nome/rótulo/elemento morto, lote único sem decisão de arquitetura),
**DECIDIDO — fila da 1.0** (decisão já tomada, falta só implementar, agendado deliberadamente para
depois de 2026-10-01), **PRODUTO** (decisão do Marcelo ainda pendente), **INFRA** (teste e
infraestrutura, congelados até depois da 1.0). Nada entra na fila sem destino.

**Contexto:** Antes disso, `ACHADOS_CONTABEIS.md` tentava ser fila **e** arquivo histórico ao mesmo
tempo — e parecia infinito por isso. `ACHADOS_CONTABEIS.md` deixou de ser fila (é registro
histórico, Camada 5); a Lista Paralela passou a ser a única fila de itens sem destino resolvido.

**Consequência:** Um item sem destino claro é, por definição, um item mal classificado, não um
item "pendente de triagem" — a classificação acontece no momento em que o item entra. Documentos
como `MAPA_MODULOS.md` (causas estruturais/fronteiras) e `DECISOES_PENDENTES.md` (enquadramento das
decisões PRODUTO) existem como apoio a essa classificação, não como fila paralela.

**Fonte:** `docs/db/LISTA_PARALELA.md`, preâmbulo.

---

## ADR-020 — Data combinada da medição: guardar as duas
**Data:** 2026-09-15 (LP-01)
**Status:** Ativo — DECIDIDO, implementação agendada para depois de 2026-10-01

**Decisão:** A data PREVISTA (dada na venda) e a data COMBINADA (acertada de fato com o cliente, no
momento de Solicitar Medição) coexistem — nenhuma substitui a outra. A combinada é a que entra no
documento que o cliente assina.

**Contexto:** A diferença entre "prometido" e "combinado" é um indicador de operação — mede o
quanto a operação desvia da promessa comercial. Esse indicador só existe se as duas datas forem
guardadas desde o início; guardar só uma descarta a informação de forma irrecuperável.

**Consequência (escopo ainda em aberto, registrado, não decisão nova):** quando o projeto está
desmembrado em fases, cada fase tem sua própria data combinada — não é um campo único no projeto. A
gravação da data combinada precisa atualizar a programação automática que o cronograma padrão já
montou na assinatura do contrato.

**Fonte:** `docs/db/LISTA_PARALELA.md`, LP-01; `docs/db/DECISOES_PENDENTES.md`.

---

## ADR-021 — CPF de quem assina: avisar e exigir confirmação do gerente, não bloquear
**Data:** 2026-09-15 (LP-02)
**Status:** Ativo — implementado no mesmo dia

**Decisão:** Quando o CPF digitado na assinatura (Contrato, Aditivo, Aprovação do PE, Solicitação
de Medição — os quatro documentos internos; o gatilho ClickSign fica de fora, pois a assinatura já
aconteceu fora do sistema) não bater com o CPF cadastrado (do cliente ou do usuário logado), o
sistema **avisa** e **exige confirmação de um gerente** antes de prosseguir. Não bloqueia
automaticamente.

**Contexto:** Bloquear destrataria os dois casos legítimos mais comuns — procuração e cônjuge
assinando em nome do titular — obrigando um fluxo de exceção só para eles. Antes desta decisão, o
sistema só conferia se o CPF digitado era matematicamente válido (ACHADO-28), nunca se era o CPF da
pessoa certa.

**Consequência:** A confirmação da exceção é registrada em `LogAcaoGerencial`
(`acao=confirmar_cpf_divergente`) — login do gerente, quando, para qual assinatura. Sem esse
rastro, "avisar" viraria "ignorar com um clique".

**Fonte:** `docs/db/LISTA_PARALELA.md`, LP-02; `docs/db/DECISOES_PENDENTES.md`.

---

## ADR-022 — Projeto Executivo pós-aprovação não ganha "várias versões"
**Data:** 2026-09-15 (LP-09)
**Status:** Ativo — recusa deliberada

**Decisão:** O Projeto Executivo aprovado não tem versões concorrentes (o modelo "vários
orçamentos, um vence" que já existe na venda). Tem REVISÕES — no fim existe uma versão final
assinada, que é a que se executa.

**Contexto:** Revisão pós-aprovação tem regras próprias que o modelo da venda não precisa
considerar (por exemplo, o que fazer com material já comprado da fábrica). Importar um mecanismo
pensado para outro momento do processo criaria mais problema do que resolveria.

**Consequência:** Quem reabrir esta questão no futuro precisa de um motivo novo — casos reais
concretos, não "seria bom ter as duas opções". A pergunta já foi feita e respondida.

**Fonte:** `docs/db/LISTA_PARALELA.md`, "Fechados"; `docs/db/DECISOES_PENDENTES.md`.

---

## ADR-023 — Lançamentos automáticos mortos removidos, não ligados
**Data:** 2026-09-15 (LP-11)
**Status:** Ativo — implementado no mesmo dia

**Decisão:** Os eventos `execucao_montagem` e `pagamento_fabrica` — prontos no código mas que nunca
disparavam fora de teste — saíram de `mod_contabil.EVENTOS`, em vez de serem consertados e ligados.

**Contexto:** Cada um, se ligado como estava, faria só metade da contabilização certa (moveria
dinheiro sem reconhecer a despesa) — o oposto do que a auditoria contábil pediu. O "Efetivar"
genérico já cobre os dois casos com a contabilização correta (as duas pernas do lançamento).

**Consequência:** Manter caminhos mortos ao lado de um caminho que já funciona era risco sem
benefício — algum dia alguém ligaria um dos dois sem saber que fazia só metade do lançamento certo.
`test_eventos_mortos_removidos_por_decisao` guarda a ausência dos dois em `EVENTOS`.

**Fonte:** `docs/db/LISTA_PARALELA.md`, LP-11.

---

## ADR-024 — Liberação financeira por fase: dois critérios, um por gate
**Data:** 2026-09-15 (LP-12)
**Status:** Ativo — DECIDIDO, implementação agendada para depois de 2026-10-01

**Decisão:** Quando um projeto é dividido em fases, a liberação usa critérios diferentes em cada um
dos dois gates: na aprovação do PE junto ao cliente, o valor de contrato da fase; na aprovação
financeira (AF1/AF2), mantém-se o padrão atual — comparação contra o CFO (Custo de Fábrica/Obra),
sem mudar.

**Contexto:** A divisão em fases reparte o trabalho (o que é aprovado e liberado em cada momento),
mas não deveria mudar o padrão de controle financeiro, que continua baseado nos valores dos
ambientes. Misturar os dois confundiria uma decisão de processo comercial com uma decisão de risco
financeiro.

**Consequência:** As contas de provisão não se desmembram por fase — a contabilidade segue
consolidada por projeto. Só a camada de **acionamento** (quando cada gate libera) passa a operar
por fase.

**Fonte:** `docs/db/LISTA_PARALELA.md`, LP-12; `docs/db/DECISOES_PENDENTES.md`.

---

## ADR-025 — Aviso de etapa concluída, com responsável: aguarda pré-requisito
**Data:** 2026-09-15 (LP-14)
**Status:** Ativo — DECIDIDO, com desenho; implementação agendada para depois de 2026-10-01

**Decisão:** Construir um Configurador de Responsabilidades (aba nova em Config) amarrando
etapa→papel, com exceção por pessoa específica onde precisar, notificando por tela e chat ao
concluir (sem WhatsApp por ora) — mas só depois de levantar quais das 21 etapas já têm um jeito
claro de saber que terminaram.

**Contexto:** Construir a notificação para "toda etapa" sem esse levantamento seria uma promessa
que não dá para cumprir — algumas etapas hoje só terminam "por adivinhação". Uma versão parcial,
só nas etapas com término claro, foi considerada e recusada: viraria dívida disfarçada de entrega,
provavelmente exigindo retrabalho quando o resto ficasse pronto.

**Consequência:** Metade do mecanismo já existe (`_ETAPA_PAPEL`, a mesma tabela que já dispara
comissão) — o pacote de execução completo está em `docs/db/TAREFA_RESPONSAVEIS_POR_ETAPA.md`.

**Fonte:** `docs/db/LISTA_PARALELA.md`, LP-14; `docs/db/DECISOES_PENDENTES.md`.

---

## ADR-026 — Acompanhar produção/entrega por fase fica na fronteira, não é barato
**Data:** 2026-09-15 (LP-18)
**Status:** Ativo — FRONTEIRA, sem prazo

**Decisão:** A divisão de acompanhamento de produção/entrega por fase (em vez de por pedido
inteiro) fica classificada como FRONTEIRA — depende do domínio Estoque existir de verdade — e não
como conserto pontual. O Marcelo havia condicionado essa classificação a uma medição de custo; a
medição, feita em 15/09, confirma que não é barato.

**Contexto (medição, não suposição):** "Fase" já existe como conceito maduro
(`parcela_projeto`/`parcela_ambiente`, em uso desde a Fatia 2). `CicloLogistico` já aceita operar
por fase, mas é uma linha agregada por fase — sem granularidade de item/ambiente dentro dela.
`DocumentoFiscal` não tem `parcela_id` nem ligação a ambiente hoje. A peça cara de verdade é a
Conferência de Volumes item a item — não existe hoje nenhuma tabela de itens/linhas recebidas para
comparar contra a nota fiscal.

**Consequência:** O desenho de tela (trilhas por fase, tabela de fases + painel da etapa corrente)
está fechado, mas a execução não é "de graça" nem "do zero" — fica fora do escopo da Semana 2,
aguardando o domínio Estoque.

**Fonte:** `docs/db/LISTA_PARALELA.md`, LP-18; `docs/db/TAREFA_FASES_E_RECEBIMENTO.md`.

---

## ADR-027 — Aprovação do Projeto Executivo não pede testemunha
**Data:** 2026-09-15 (LP-24)
**Status:** Ativo — confirmação de comportamento já existente, não mudança

**Decisão:** A ausência de testemunha na assinatura da Aprovação do Projeto Executivo é
**deliberada**, não esquecimento de quem programou a funcionalidade.

**Contexto:** O Contrato pede testemunha porque **cria** uma obrigação (compromisso
financeiro/legal entre as partes). A Aprovação do Projeto Executivo é aceite técnico — o cliente
confirma que o projeto está como deveria, sem assumir obrigação nova. Não gerar obrigação é a
diferença que justifica não pedir testemunha ali.

**Consequência:** Nenhuma mudança de código — a ausência, que soava como lacuna quando descoberta
(Passo 0 do ACHADO-69), estava correta desde o início. Registrado como ADR para que a dúvida não
precise ser refeita.

**Fonte:** `docs/db/LISTA_PARALELA.md`, "Fechados"; `docs/db/DECISOES_PENDENTES.md`.
