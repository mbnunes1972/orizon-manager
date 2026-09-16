# Mapa dos Módulos — papel × código, duplicação estrutural e fronteiras propostas

> **Sessão B (14/09/2026), conforme `PLANO_SEMANA_1.md`.** Documento só de leitura e análise —
> nenhum código foi escrito ou alterado para produzi-lo, nenhum `pytest` foi executado. Toda
> âncora abaixo é por **nome** (função, rota, tabela, id de elemento) — nunca por número de linha
> de `main.py` ou `static/index.html`, porque a Sessão A edita os dois em paralelo a este trabalho.
>
> Fontes cruzadas: `docs/especificacoes/Modulos_Orizon_v12.docx` (o papel, "Módulos v12"),
> `docs/ARQUITETURA-MODULOS.md` (o mapa lógico anterior, 2026-07-06 + adendos), `modulos.py` (o
> manifesto executável — Fase 1, imposto por `tests/test_arquitetura_modulos.py`),
> `docs/processos/FLUXO_38_ETAPAS.md`, `docs/arquitetura/ROTAS.md`/`DECISOES.md`,
> `docs/db/ACHADOS_CONTABEIS.md` (177 achados) e `docs/db/LISTA_PARALELA.md` (24 itens LP).
>
> **Achado central deste levantamento, antes de qualquer seção:** o sistema já tem DOIS mapas de
> módulos que não coincidem exatamente. `Módulos v12` (o papel, negócio) lista 12 nomes: Captação,
> Cadastro, Comercial, Projetos, Fiscal, Estoque, Expedição, Financeiro, Montagem, Assistências,
> Admin, Config. `modulos.py` (o código, Fase 1) lista 8 núcleos + 10 domínios, com nomes e
> fronteiras que **não são um espelho 1:1** do papel — "Projetos" não tem módulo de código próprio
> (foi absorvido por Comercial, de propósito, ver Seção 1); "Admin" e "Config" não existem como
> chave nenhuma do manifesto (são superfícies de UI sobre outros módulos); "Montagem" existe como
> chave, mas seu rótulo interno ainda é `"Operacional"`, o nome de antes da v12 renomear
> "Pós-venda". Isso não é defeito em si — é a distância exata entre o papel e o código que este
> mapa existe para medir.

---

## 1. Módulos: papel × código

Para cada módulo do `Módulos v12`, onde a lógica vive hoje.

### Captação — só papel, zero código
`modulos.py` tem a chave `"captacao"` (domínio, faixa `vendas`) mas `arquivos: []`,
`tabelas: []`, `rotas: []`. No frontend, `_SB_MODULOS.captacao` só declara um ícone
(`target-arrow`) — sem `go` nem `secoes`, o que faz `sbModuloClick()` cair no ramo
`emConstrucao()`. Grep por `captac` em `main.py`/`database.py` não encontra nada relacionado
a captação de lead (os dois hits são "captação de empréstimo", um evento financeiro sem relação
nenhuma). **100% lacuna**, exatamente como `ARQUITETURA-MODULOS.md` já registra.

### Cadastro — código rico, uma lacuna central
- **Backend:** `mod_cadastro.py` + `validacao_doc.py`. Tabelas: `clientes`, `parceiros`,
  `funcionarios`, `fornecedores`, `terceiros`, `funcoes`. Rotas: `/api/clientes`,
  `/api/parceiros`, `/api/funcionarios`, `/api/fornecedores`, `/api/terceiros`, `/api/funcoes`.
- **Frontend:** container `id="page-10"`, com abas roteadas por `cadTab()`/`cadIr()` — Clientes,
  Parceiros, Fornecedores, Terceiros, Funcionários (as duas últimas ainda "em breve" na v12,
  mas já têm rota/tela).
- **Lacuna central (papel v12, item 2):** Catálogo de Produtos/Serviços não existe como tabela —
  produto é implícito no XML Promob e em `orcamento_ambientes` (`cProd[ID]`). `ARQUITETURA-
  MODULOS.md` já nomeia isso como pré-requisito do módulo Estoque.
- **Achado à parte (ver Seção 7 — candidatos):** existe um segundo elemento `id="page-01"`,
  também rotulado internamente perto de "Cadastro", marcado no próprio HTML como
  `<!-- PAGE 01 DUMMY (mantido para não quebrar unlockNav) -->` — container vazio, morto,
  mantido só por dependência de outra função.

### Comercial — o módulo mais rico, e onde "Projetos" (papel) foi parar
- **Backend:** `mod_orcamento_params.py`, `mod_margens.py`, `mod_negociacao.py`,
  `mod_contrato.py`, `mod_marcadores.py`, `mod_documentos.py`/`mod_documentos_import.py`,
  `mod_arvore.py`, `_ler_aymore.py`, pacote `mod_fin`, `mod_pe_comparacao.py`,
  `mod_parcelas.py`, `mod_retido.py`, `mod_medicao.py`, `mod_qualidade_xml.py`,
  `mod_comercial_dash.py`, `mod_equipe.py`, `mod_clicksign.py`, `mod_assinatura.py`.
- **Tabelas:** `projetos_meta`, `briefings`, `pool_ambientes`, `orcamentos`,
  `orcamento_ambientes`, `contratos`, `contratos_assinaturas`, `aditivos`/`aditivos_assinaturas`,
  `aprovacoes_pe`/`aprovacoes_pe_assinaturas`, `integracoes_clicksign`, `arquivo_pe`,
  `parcela_projeto`/`parcela_ambiente`, `sinal_retido`/`retencao_obra`, `medicoes`,
  `solicitacoes_medicao`/`solicitacoes_medicao_assinaturas`, `documento_modelos`/`documento_tipos`.
- **Frontend, espalhado por três páginas:** `page-00` ("Projetos" — lista + fichário do ciclo,
  navegado como **Atalho**, fora do menu de módulos), `page-02` ("Negociação", layout novo) e
  `page-15` ("Comercial" — dashboard, aberto por `comercialDashAbrir()`). Não há uma página só.
- **Desvio deliberado papel↔código:** o item 4 do `Módulos v12` (renomeado "Projetos", ex-
  "Produção/Projetos") **não tem módulo de código próprio**. O comentário do próprio `modulos.py`
  explica: "o antigo módulo 'producao' ... foi retirado da navegação por ser tela-vazia e duplicar
  o nome; seu código é dono aqui [Comercial], pois Medição pertence ao ciclo comercial." Medição
  (`mod_medicao.py`), subfases do PE e o motor de corte paramétrico (ainda inexistente) vivem
  dentro de Comercial. Isso não é achado — é decisão registrada — mas quem for extrair um módulo
  físico "Projetos" no futuro precisa saber que hoje ele **não existe**, nem como pacote nem como
  fronteira de teste.

### Fiscal — pacote isolado, mas com rotas genéricas demais
- **Backend:** pacote `fiscal/` (reorganização 2026-07-15, candidato à extração física Fase 2 por
  ser "o cluster mais isolado"). Tabelas: `emitente`, `perfil_emissao`, `documento_fiscal`.
- **Frontend:** `page-11`.
- **Achado de fronteira (ver Seção 7):** as rotas declaradas para Fiscal em `modulos.py`
  (`/api/projetos/`, `/api/admin/lojas/`, `/api/admin/redes/`) são prefixos **largos demais** —
  cobrem literalmente qualquer rota que comece com `/api/projetos/`, inclusive as que pertencem a
  Comercial (`mod_equipe.py`, por exemplo) e ao Ciclo (núcleo). Ver Seção 7 para o mecanismo exato
  e por que hoje isso está adormecido.

### Estoque — zero código, mas já citado como dependência de outros três
`modulos.py`: `"estoque"` existe como chave (domínio, faixa `expedicao`, `depende_de: ["cadastro",
"comercial"]`), mas `arquivos: []`, `tabelas: []`, `rotas: []` — stub puro, conforme o próprio
`ARQUITETURA-MODULOS.md` registra ("entra só como fronteira; design interno depois, YAGNI").
`expedicao` e `fiscal` já **dependem** dele no manifesto (`depende_de`), mesmo sem ele existir —
é uma dependência declarada para um módulo que ainda não tem chão. Achado da Seção 5: pelo menos
dois itens abertos (LP-15/ACHADO-31 parcial, e parte do LP-18) são sintoma direto dessa ausência.

### Expedição — módulo fino conforme o desenho, mas com uma violação concreta da própria regra
- **Backend:** `mod_expedicao.py`. Tabelas: `ciclo_logistico`, `ciclo_logistico_transicao`.
  Rota: `/api/expedicao`.
- **Frontend:** `page-13`, Kanban.
- `ARQUITETURA-MODULOS.md` já escreve a regra para este módulo, em letras grandes: "**NÃO PODE**
  conter duplicação de dado que já pertence a Produção, Estoque ou Fiscal... nunca é fonte da
  verdade". A Seção 4 encontrou exatamente essa violação, concretamente: a função `_expPoll()`
  (Expedição, frontend) escreve diretamente no estado global `projetoAtivo`, que pertence
  conceitualmente a Comercial e é lido por mais de 350 pontos do arquivo inteiro. Ver Seção 2.

### Financeiro — o segundo módulo mais rico, com Folha "emprestada" na tela
- **Backend:** `mod_provisoes.py`, `mod_contabil.py` (262 KB, o maior módulo de domínio do
  sistema), `mod_ajustes_fabrica.py`, `mod_indicadores.py`, `mod_recebiveis.py`,
  `mod_estrategico.py`, `mod_simulador.py`/`mod_simulador_autorizacao.py`/`mod_simulador_dados.py`,
  `mod_conciliacao_pe.py`.
- **Rotas:** mais de vinte prefixos declarados (`/api/provisoes`, `/api/financeiro/*`,
  `/api/admin/acordos-fabrica`, `/api/admin/ajustes-fabrica`, `/api/estrategico/indicadores`,
  `/api/simulador`, `/api/recebiveis`, entre outros).
- **Frontend:** `page-12`, com **doze abas** roteadas por `_FIN_SECOES`/`finIrSecao()`: Provisões,
  Plano de Contas, Lançamentos, Fluxo de Caixa, DRE, Balanço, Margem/Projeto, Reconciliação,
  Reconc. Provisões, Fila de Provisões, Contas a Pagar, **Folha de Pagamento**.
- **Desvio papel↔código:** Folha de Pagamento é, no manifesto (`modulos.py`), um **módulo
  próprio** (`"folha"`, com `mod_folha.py`/`mod_comissao.py`/`mod_adiantamento.py`, tabelas e
  rotas dedicadas), não uma sub-parte de Financeiro — mas na sidebar ele é explicitamente
  filtrado da lista de módulos (`m.id !== 'folha'`) e vive só como aba dentro de `page-12`. O
  próprio código comenta o motivo: "Folha = seção do Financeiro". É decisão de apresentação, não
  bug — mas, como o caso de Comercial/Projetos, é uma fronteira que existe no código-backend e
  desaparece na navegação.

### Montagem — tem tela, não tem dados próprios
No `Módulos v12` é módulo novo, desmembrado do antigo "Pós-venda". No manifesto, a chave
`"montagem"` existe (`depende_de: ["comercial"]`), mas **com `arquivos: []`, `tabelas: []`,
`rotas: []`** — e o rótulo interno (`"rotulo": "Operacional"`) ainda é o nome anterior à
renomeação da v12. Na tela, Montagem não tem página própria: mora dentro de `page-18`
("Operacional"), ao lado de PE e Assistências, comandada por `_SB_MODULOS.montagem` →
`goPage(18)`. A agenda/Gantt de Montagem existe em `main.py` (bloco comentado como "Gantt de
MONTAGEM"), mas o dado que ela lê pertence ao **Ciclo** (`mod_agenda.py`/`mod_cronograma.py`, que
são núcleo, não domínio "montagem") e à Folha (`ComissaoFolha`, cujo campo de base "Σ order_total
dos ambientes" é como o motor de comissão sabe quanto um Montador executou). Ou seja: Montagem
tem comportamento real no sistema, mas **nenhum dado que more literalmente nela** — está
emprestado do Ciclo e da Comercial/Folha. A Seção 5 mostra o achado que nasce exatamente daqui
(LP-23).

### Assistências — código próprio, mas fundido com Montagem na tela
- **Backend:** `mod_assistencias.py`. Tabelas: `assistencia_caso`, `assistencia_executores`,
  `assistencia_anexos`. Rota: `/api/assistencias`.
- **Frontend:** também filtrado da sidebar (`m.id !== 'assistencias'`) e vive como aba dentro de
  `page-18`, junto com Montagem — o próprio código chama isso de "Assistências = ABA do
  Operacional". O papel v12 é explícito: "módulo **distinto** de Montagem: Montagem executa o
  serviço original; Assistências trata problemas/pedidos depois do fato." O código respeita essa
  distinção nos dados (tabelas próprias) mas não na navegação (mesma tela).

### Admin — papel rico, sem módulo de código
Não existe chave `"admin"` em `modulos.py`. As rotas do papel Admin (`/api/admin/usuarios`,
`/api/admin/perfis`/`/api/admin/perfis-matriz`, `/api/admin/redes`, `/api/admin/lojas`,
`/api/admin/contrapartes-financeiras`, `/api/admin/lojas/<id>/config-financeira`, `/api/admin/
lojas/<id>/modulos`, `/api/admin/*/perfil-fiscal*`, `/api/admin/*/integracao-clicksign*`) vivem
soltas em `main.py`, sem serem atribuídas a nenhum módulo do manifesto — as tabelas que elas
tocam (`usuarios`, `sessoes` → **auth**; `redes`, `lojas`, `usuario_lojas` → **tenancy**) já
pertencem a outros módulos núcleo. Frontend: `page-07` tem HTML quase vazio
(`<div id="admin-console">`) — toda a estrutura de telas (Dados da loja / Usuários / Perfis /
Módulos) é montada em runtime por `adminRender()`, então o "tamanho" real de Admin no frontend só
aparece em JavaScript, nunca em marcação. Isso bate com a leitura do próprio `Módulos v12`: Admin
é Núcleo/Plataforma, não domínio — mas por não ter chave no manifesto, fica **invisível** ao
teste de fronteira (`tests/test_arquitetura_modulos.py`) e a qualquer auditoria automática de
"quem é dono desta rota".

### Config — a câmara de compensação do sistema
Também sem chave no manifesto. `page-09` é uma única tela com sete abas (`cfgTab()`) que agregam
config de **cinco módulos de domínio diferentes**: Provisões (Financeiro), Remunerações
(Folha), Cronograma (Ciclo), Agenda (Ciclo), Funções (Cadastro), Documentos (Comercial),
Privacidade (oculta). O papel v12 já avisa que Config é Núcleo, "mesma natureza [de Admin], mas
assunto diferente" — e de fato não há tabela própria de Config; cada aba escreve na tabela do seu
módulo dono. Isso é legítimo como camada de apresentação, mas quem for extrair fisicamente
qualquer um desses cinco domínios (a Fase 2+ do roadmap já cogita o Fiscal primeiro) precisa
lembrar que uma fatia da configuração dele mora fisicamente numa página que se chama "de outro
módulo".

### Resumo tabular

| Módulo (papel v12) | Backend (arquivos) | Tabelas próprias | Rota(s) | Tela própria | Situação |
|---|---|---|---|---|---|
| Captação | nenhum | nenhuma | nenhuma | não (stub genérico) | só papel |
| Cadastro | `mod_cadastro.py`, `validacao_doc.py` | 6 tabelas | 6 prefixos | `page-10` | rico, 1 lacuna (catálogo) |
| Comercial | 18 arquivos | ~20 tabelas | 5 prefixos declarados (subespecificado) | 3 páginas | o mais rico; absorve "Projetos" |
| Fiscal | pacote `fiscal/` | 3 tabelas | 3 prefixos (largos demais) | `page-11` | isolado, mas mal delimitado |
| Estoque | nenhum | nenhuma | nenhuma | não (stub genérico) | só papel, já é dependência de outros |
| Expedição | `mod_expedicao.py` | 2 tabelas | 1 prefixo | `page-13` | fino, mas com violação ativa (`_expPoll`) |
| Financeiro | 9 arquivos | ~14 tabelas | >20 prefixos | `page-12` (12 abas) | o mais rico depois de Comercial |
| Montagem | nenhum | nenhuma | nenhuma | `page-18` (compartilhada) | tela sem dados próprios |
| Assistências | `mod_assistencias.py` | 3 tabelas | 1 prefixo | `page-18` (compartilhada) | dados próprios, tela fundida |
| Admin | nenhum (disperso em `main.py`) | usa auth/tenancy | ~15 prefixos soltos | `page-07` (100% JS) | núcleo sem manifesto |
| Config | nenhum (agrega 5 módulos) | nenhuma própria | usa rotas de outros módulos | `page-09` (7 abas) | câmara de compensação |
| *(Folha, fora da lista v12 original)* | `mod_folha.py`, `mod_comissao.py`, `mod_adiantamento.py` | 3 tabelas | 3 prefixos | aba dentro de `page-12` | módulo real, sem tela própria |

---

## 2. Caminhos dobrados — mesmo estado, mais de um caminho de escrita

A "regra dos irmãos" (ACHADO-26) aplicada ao sistema inteiro.

### 2.1 — `projetoAtivo` escrito por Comercial e por Expedição
O objeto global `projetoAtivo` (frontend) é lido em **mais de 350 pontos** de `static/index.html`
— praticamente toda tela que mostra dado de um projeto depende dele. Ele é reescrito por inteiro
(nunca campo a campo, o que já reduz o risco) em seis funções: `abrirProjeto`, `criarProjeto`,
`uploadXmls`, `removerAmbiente`, `atualizarXml` — todas de Comercial — e **`_expPoll`**, que é
Expedição. Uma função do módulo Expedição sobrescrevendo o estado "projeto ativo" que todo o
resto do sistema lê é a violação concreta da regra que `ARQUITETURA-MODULOS.md` já escreveu para
este módulo ("nunca é fonte da verdade"). Hoje os dois lados buscam o mesmo formato
(`{ok, projeto}` da API), então não há divergência de *valor* observada — mas é o tipo exato de
acoplamento que torna uma mudança local (em Expedição) numa quebra remota (em qualquer tela que
leia `projetoAtivo`), que é a definição do ACHADO-25 aplicada aqui.

### 2.2 — Vereditos de provisão: quatro pontos de montagem para a mesma decisão (LP-13)
Já nomeado no próprio `LISTA_PARALELA.md`: "Hoje há **quatro caminhos** para o mesmo estado —
Financeiro em leitura, modal de Reconciliação do projeto, tabela da Conciliação Final, e a Fila
[de Provisões]." O documento atribui a essa multiplicidade, sozinha, os ACHADO-26, 32, 33 e 41.
O redesenho ("Tela Única de Provisões", desenho já FECHADO com o Marcelo em 05/09, não
implementado) resolveria os quatro pontos de montagem para **um componente, dois pontos de
exibição** — e resolveria o ACHADO-37 "de graça", segundo o próprio texto.

### 2.3 — "Pode fazer X nesta linha?" reimplementado tela a tela (a família B6)
O padrão mais recorrente do levantamento: a UI decide, por conta própria, quais ações mostrar
para um estado, e o backend tem sua **própria** regra sobre quais aceita — sem uma function
compartilhada entre as duas pontas. Ocorrências, na ordem em que apareceram no mesmo dia
(01/09), segundo o próprio texto do ACHADO-41: **ACHADO-32** (Conciliação Final oferecia
"Resolver" com 409 garantido) → **ACHADO-33** (o conserto do 32 quebrou o que funcionava) →
**ACHADO-39** (AF2 oferecia decisão pela grandeza errada) → **ACHADO-41** (Fila oferece veredito
que o sinal do saldo já exclui). O próprio texto nomeia a regra que deveria valer: "nenhuma tela
oferece ação que o servidor recusará por regra conhecida... quando a regra mora no backend, é o
backend que diz quais ações valem". A correção do ACHADO-41
(`mod_contabil.vereditos_validos_para_saldo(saldo)`, consultada tanto por quem recusa quanto por
quem desenha os botões) é o modelo exato do que uma fronteira bem desenhada faz: fecha quatro
achados de uma vez, porque a causa era uma só.

### 2.4 — "Isso já foi decidido?" reimplementado subfase a subfase (ACHADO-56)
`mod_ciclo.guarda_conclusao` decide se a subfase 11c (Revisão de PE) pode fechar consultando
`pe_ambientes` (todo ambiente tem PE carregado?) — mas **nunca** consulta a tabela de decisão
contábil (`ConciliacaoPeFase`/equivalente a `_pe_ambientes_pendentes_decisao`, que a 11d usa para
a mesma pergunta de fundo: "existe ambiente com Δ a cobrar/estornar ainda sem decisão?"). O texto
do próprio achado nomeia o princípio ausente: "todo fechamento de subfase de PE que representa
uma decisão contábil tem que confirmar que a decisão existe, não só que o documento foi
carregado" — e confirma que são **duas instâncias independentes** do mesmo princípio (11c e 11d),
cada uma com sua própria causa, cada uma exigindo seu próprio commit. Ver Seção 3 para a metade
"duas fontes de verdade" do mesmo achado.

### 2.5 — Nove chamadores de `_recalcular_orcamento`, seis engolindo a falha (ACHADO-19)
`_recalcular_orcamento` é a única função que persiste `orc.valor_total` e as 14 colunas-sombra do
motor de negociação — mas é chamada de nove lugares diferentes em `main.py`, e cada um decide por
conta própria o que fazer se ela falhar: três respondem `ok: False` corretamente, seis fazem
*fail-soft* e respondem `ok: True` mesmo com o recálculo não tendo acontecido. Não existe uma
única rota, das nove, onde "o insumo novo" e "o resultado recalculado" andam na mesma transação —
é o mesmo caminho dobrado do padrão 2.3, mas em vez de "quais botões mostrar" é "o que fazer
quando o motor falha".

### 2.6 — Reclassificação de Outros Fornecedores: dois braços que podem desalinhar (ACHADO-06)
`reclassificar_provisao` sempre move o valor **cheio** na perna da provisão, mas espelha o ativo
diferido **capado** ao saldo aberto do ativo de origem no momento da chamada. O comentário do
próprio código já admite: "reclass ANTES da NF-e espelha tudo; DEPOIS da NF-e não move" — dois
braços da mesma operação, sem garantia de que terminam iguais.

### 2.7 — Markup de ajuste × rateio automático (ACHADO-31 parcial / LP-15)
Decidido em 31/08 ("o rateio sugere, o markup manda") mas nunca implementado: hoje
`rescalar_itens_para_total` **sobrescreve** o campo que o usuário digitou sempre que existe
contrato — dois "donos" competindo pelo mesmo campo, e o automático sempre vence, inclusive no
caso normal (que é justamente o defeito original). Fica registrado como caminho dobrado **ativo**
— não é risco teórico, é o comportamento hoje.

### 2.8 — Conclusão de etapa do Ciclo: três implementações, uma delas sem efeito colateral de comissão (verificado)
Existe um único helper que centraliza os efeitos de "concluir uma etapa" — `_set_etapa_status`
(`main.py`): grava `iniciado_em` na primeira saída de "pendente", `status`, e, em status
conclusivo, `concluido_em`/`responsavel_id` **e** dispara `mod_comissao.preparar_comissao_etapa`
(comentário no próprio código: "Fase 4: comissão do papel na conclusão da etapa"). Mas ele não é o
único caminho:
- A rota genérica **`PATCH /api/projetos/<nome>/ciclo/<codigo>`** — a documentada em
  `docs/arquitetura/ROTAS.md` como *o* jeito de avançar etapa, e a única usada pelo fluxo padrão da
  UI para etapas sem tela dedicada — **reimplementa inline** exatamente os mesmos três campos
  (`etapa.status`, `etapa.concluido_em`, `etapa.responsavel_id`) e **não chama `_set_etapa_status`
  nem `mod_comissao.preparar_comissao_etapa`**. Confirmado lendo o handler inteiro: as checagens de
  gate (sequência, bloqueador do chat, operacional 12/13/14, retenção 17/18, aprovação financeira
  8/11d) foram cuidadosamente replicadas com os mesmos helpers do endpoint dedicado — só o efeito
  colateral de comissão ficou de fora.
- **`_marcar_etapa_cliente`** é uma terceira reimplementação (marca a mesma etapa em todos os
  projetos de um cliente), também sem chamar `_set_etapa_status` nem preparar comissão.
- **Efeito concreto, confirmado por leitura (não por teste):** a etapa **17 (Montagem)** — que tem
  papel comissionável via `_ETAPA_PAPEL`/`mod_comissao` — **não aparece em nenhum dos call sites de
  `_set_etapa_status`** (que cobre só 4, 9, 10, 11, 11d, 15, 21). Ela só pode ser concluída pelo
  PATCH genérico. Ou seja: **hoje, concluir Montagem pelo fluxo padrão da UI não prepara a comissão
  do Montador** — o único jeito de disparar `preparar_comissao_etapa` para uma etapa comissionável
  fora de 4/9/10/11/11d/15/21 seria um caminho que não existe na navegação normal. Ver candidato a
  achado na Seção 7.

### 2.9 — Registro de assinatura por documento: quatro funções irmãs não unificadas
`_registrar_assinatura_contrato`, `_registrar_assinatura_aprovacao_pe`,
`_registrar_assinatura_solicitacao_medicao` e `_registrar_assinatura_aditivo` (todas em `main.py`)
reimplementam, cada uma, a mesma lógica: registrar quem assinou, checar se `{"loja","cliente"}` já
assinaram, e então avançar o `status` do documento. `mod_assinatura.py` (ACHADO-69) unificou
**envio/reconciliação/cancelamento** de envelope ClickSign para os 4 tipos de documento, mas
deliberadamente manteve `registrar_assinatura` como parâmetro externo por documento
(`reconciliar_clicksign(..., registrar_assinatura=...)`) — a unificação parou um passo antes do
"irmão" que originou a própria categoria (ACHADO-26). As 4 funções concordam hoje porque foram
escritas em conjunto na mesma leva de trabalho, mas nada impede que uma ganhe uma regra nova sem as
outras três — é a extensão natural do pacote `mod_assinatura.py`, ainda não feita.

---

## 3. Duas fontes de verdade — o mesmo fato, guardado (ou nomeado) em dois lugares

### 3.1 — `CicloEtapa.status` × `AprovacaoPE.status` (a metade "fonte" do ACHADO-56)
`POST /api/projetos/<nome>/ciclo/11d/reprovar` (reprovação da Aprovação Financeira II) escreve
**só** `CicloEtapa.status = "reprovado"` — nunca toca `AprovacaoPE.status`. São duas colunas, em
duas tabelas, contando a mesma história ("isso foi aprovado?"), e uma ação real do sistema
atualiza uma e esquece a outra. É o padrão canônico que `ARQUITETURA-MODULOS.md`/`PLANO_SEMANA_1`
já citam como referência (CicloEtapa × status do documento), com instância nova e confirmada em
13/09.

### 3.2 — O catálogo de etapas do Ciclo, duplicado à mão entre Python e JavaScript
`mod_ciclo.py` é explícito sobre isso no próprio cabeçalho: "a ordem aqui... é a canônica nova; o
`ETAPAS_CICLO` do frontend é alinhado a ela." `ETAPAS_CICLO` (`static/index.html`) é uma cópia
mantida manualmente do que `mod_ciclo.ETAPAS_PRINCIPAIS`/`ETAPA_NOME` já definem no backend — e o
mesmo vale para o rótulo do grupo "Logística e Expedição": existe como `GRUPO_NOME` em
`mod_ciclo.py` e como `_FICHA_GRUPO_NOME` em `static/index.html`, os dois hardcoded
separadamente. **Isso já divergiu uma vez, com registro formal**: o próprio `mod_ciclo.py`
documenta o achado da Vera (26/08) em que "a lista de Projetos e o diálogo de transferência de
responsabilidade usavam `ETAPA_NOME["13"]` cru ('Produção')... divergindo do fichário do projeto
(que mostra 'Logística e Expedição')" — comentário que termina com "manter os dois dicionários em
sincronia se o grupo mudar", ou seja: a duplicação continua sendo responsabilidade manual, não
foi eliminada, só corrigida na instância que apareceu.

### 3.3 — "Está concluído?" tem uma resposta certa e uma resposta rápida errada (`GRUPOS_ESPINHACO`)
O código "13" representa visualmente o grupo inteiro Produção→Entrega no Cliente (13,14,15,16),
mas cada um desses códigos tem sua própria linha `CicloEtapa`, com seu próprio status. A pergunta
"a etapa 13 terminou?" tem duas rotas possíveis: ler `status_por_codigo["13"]` direto (rápida,
errada — dá "concluído" assim que só a Produção terminar) ou chamar
`mod_ciclo.etapa_concluida_agregada("13", ...)` (correta, verifica o grupo inteiro). O comentário
do próprio arquivo alerta explicitamente que "quem varre `ETAPAS_PRINCIPAIS`" pode tomar a rota
errada por engano — é uma duas-fontes-de-verdade **por desenho**, não um bug hoje, mas um convite
a um bug amanhã em qualquer código novo que precise responder essa pergunta.

### 3.4 — Nome da conta contábil × o que o código realmente faz com ela
Uma variante do padrão que não é duplicação de *dado*, é duplicação de *significado*: o nome de
uma conta do plano é uma fonte de verdade sobre "o que isto é", e o comportamento do código é
outra, e elas divergem sem que ninguém tenha decidido isso. Dois casos abertos:
- **ACHADO-17**: `2.1.04.12` se chama "Retenção de Comissão de Vendas", mas o mecanismo de
  retenção parcial/condicional que o nome promete nunca foi implementado — é uma provisão simples.
- **ACHADO-09**: `5.3.01` é debitada por dois mecanismos conceitualmente diferentes (comissão de
  rotina via folha variável, e reconhecimento de retenção provisionada) sem distinção além do
  campo `origem` do lançamento.

### 3.5 — Remuneração do Montador: um campo, dois significados (LP-23)
`Funcao.comissao_json`/a "Base" que a tela de Remuneração mostra serve, ao mesmo tempo, para
"líquido de vendas" (Consultor, o que a tela rotula) e para "volume executado por papel"
(Montador/Medidor/Projetista, o que o motor `mod_comissao.preparar_comissao_etapa` realmente usa
via `base_ambientes`/`order_total`). O próprio comentário de `ComissaoFolha.base` já registra a
ambiguidade ("Σ order_total dos ambientes (ou vendas líq.)"). Não é duplicação de valor — é um
campo genérico demais escondendo dois domínios diferentes (venda × execução), consequência direta
de Montagem não ter dado próprio (ver Seção 1).

### 3.6 — Risco leve, não confirmado: dois catálogos de "faixa" do Ciclo
`mod_ciclo.FAIXA_POR_ETAPA` usa 7 ids de faixa (inclui `gate_financeiro_1`, `gate_financeiro_2`,
`conciliacao_final`); `modulos.FAIXAS` (usado para agrupar o hub) usa só 5 (`vendas`,
`execucao_projeto`, `expedicao`, `montagem`, `financeiro`). Hoje nenhum módulo de domínio no
manifesto declara `faixa` como um dos ids exclusivos do Ciclo, então não há divergência
observável — mas são dois catálogos paralelos, e nada impede que um módulo futuro declare
`faixa: "gate_financeiro_1"` e desapareça silenciosamente do hub (`hub_layout` simplesmente não
teria grupo para ele). Registrado como risco estrutural leve, não como achado.

### 3.7 — Motivos de retenção por obra: lista JS hardcoded × `mod_retido.MOTIVOS_RETENCAO` (verificado)
O array de motivos de retenção usado no frontend (`const motivos = ['Atraso da Obra', 'Aprovação
do Arquiteto', ...]`) é uma cópia manual de `mod_retido.MOTIVOS_RETENCAO` — o próprio comentário no
`static/index.html`, junto ao array, admite isso ("espelho de `mod_retido.MOTIVOS_RETENCAO`
(backend valida)"). É a mesma forma da duplicação já registrada em 3.2 (catálogo de etapas do
Ciclo), mas numa lista de negócio menor e sem o mesmo histórico de divergência documentada — ainda
assim, é uma segunda instância confirmada do padrão "enum vive no Python, é copiado à mão pro JS",
o que sugere que não é um caso isolado, e sim um hábito recorrente de como o time integra front e
back neste projeto.

### 3.8 — `contrato.status` × etapa "7" (Contrato) do Ciclo: escritos por pontos distintos, sem função de sincronização
`Contrato.status` (`rascunho` → `para_assinatura` → `assinado_loja`/`assinado_cliente` →
`assinado`/`vigente`) e a etapa "7" do Ciclo descrevem a mesma jornada de negócio (o contrato foi
fechado?), mas são escritos por funções diferentes sem um helper único que os mantenha casados:
`_registrar_assinatura_contrato` avança `contrato.status` em três pontos (assinado_loja →
assinado_cliente → assinado) sem tocar a etapa; a rota de reabertura de etapa reseta `contrato.
status = "rascunho"` num branch dedicado a essa consequência; e a geração/regeração do contrato
grava `contrato.status = "rascunho"`/`"para_assinatura"` num terceiro ponto. Nenhum dos três chama
os outros nem consulta um estado central — cada um sabe, por conta própria, o que fazer com o outro
lado. Sintoma de que essa disciplina manual já quase falhou: a rota de cancelamento de contrato tem
um comentário defensivo explícito ("etapa 7 do ciclo não deveria estar 'concluido' aqui... mas se
algum caminho futuro deixar isso acontecer, reabre") — um remendo escrito porque alguém já temeu
(ou já viu) a divergência acontecer.

---

## 4. O inventário do frontend

`static/index.html`: **26.335 linhas / 1,69 MB**, HTML+CSS+JS num arquivo só (ADR-003), **1.131
funções JavaScript** no total. Áreas identificadas pelos containers `id="page-*"` e pelos prefixos
de nome de função/variável (não por número de linha — nomes e ids são estáveis, a posição não é).

| Área (id do container) | Módulo de negócio | Tamanho relativo (por nº de funções do prefixo) | Como se chega lá |
|---|---|---|---|
| `page-00` | Comercial (Projetos — atalho) | grande (`proj*`, 17+) | `goPage(0)`, item de menu "Projetos" |
| `page-01` | — (morto) | ínfimo (div vazia) | não navegável de propósito |
| `page-02` | Comercial (Negociação) | grande (`neg*` 16, `tf*` 17, `mp*` 20, `_ay`/`_cc`/`_vp` somados ~15) | `goPage(2)` |
| `page-03` | Comercial (Exportar) | ínfimo (placeholder "em breve") | `goPage(3)` |
| `page-07` | Admin | grande, mas **quase só JS** (`admin*`, 27 funções, HTML quase vazio) | `goPage(7)`, item "Admin" |
| `page-08` | qualquer módulo sem tela | mínimo (template genérico "Em construção") | reusado por todo módulo `_SB_MODULOS` sem `go` |
| `page-09` | Config (7 abas de 5 módulos) | grande (`cfg*`, 26 funções) | `goPage(9)`, item "Config" |
| `page-10` | Cadastro | médio (`cad*`, 14 + `cli*` 26 — mas `cli*` mistura Clientes com outros usos) | `goPage(10)`/`cadIr()` |
| `page-11` | Fiscal | médio | `goPage(11)` |
| `page-12` | Financeiro (12 abas, incl. Folha) | o maior (`recon*` 10, `folha*` 10, mais lançamentos/DRE/balanço/plano de contas) | `goPage(12)`/`finIrSecao()` |
| `page-13` | Expedição | médio (`exp*`, 11) | `goPage(13)` |
| `page-15` | Comercial (dashboard) | pequeno | `comercialDashAbrir()` → `goPage(15)` |
| `page-16` | Ciclo/Agenda da Loja | grande (`_ag*`, 18+) | `goPage(16)`, item "Agenda" |
| `page-18` | Montagem + Assistências + PE ("Operacional") | grande (`_op*` 13, `_pe*`/`pe*` ~40) | `goPage(18)` |
| `page-chat` | Chat (núcleo, Orizon Chat) | **o maior por contagem de função** (`oc*`, 72) | `ocAbrirPagina('atend')` |
| `page-estrategico` | Financeiro (Painel Estratégico) | pequeno-médio | `goPageEstrategico()` |
| `page-orizon` | Núcleo/Tenancy (super_admin) | médio (`orizon*`, 11) | `goPageOrizon()` |
| `page-rede` | Núcleo/Tenancy (admin de rede) | pequeno-médio | `goPageRede()` |

Achados de estrutura, não de negócio:
- **Orizon Chat (`oc*`, 72 funções) é a maior área por contagem de função em todo o arquivo** —
  maior que Financeiro, maior que Negociação. O papel v12 não lista Chat como módulo de domínio
  (é núcleo, "sempre ativo"), mas seu peso no arquivo já é comparável ao dos módulos de negócio
  mais ricos — vale considerar isso ao decidir a ordem de extração de arquivos JS na Semana 2.
- **Admin (`page-07`) não tem estrutura no HTML** — é um único `<div>` preenchido inteiramente
  por `adminRender()`. Qualquer inventário "por linha de marcação" subestima Admin; o peso real
  dele só aparece contando função JS.

### Acoplamento cruzado — a parte mais importante desta seção

- **`projetoAtivo` (Comercial) escrito por `_expPoll` (Expedição)** — já detalhado na Seção 2.1.
  É o caso mais concreto e mais bem evidenciado de função de uma área escrevendo estado que não é
  dela.
- **`_usuarioAtual`** (170 ocorrências) e **`projetoAtivo`** (362 ocorrências) são, juntos, o
  "estado central" que toda área lê — isso é esperado numa SPA sem framework (alguém precisa
  guardar "qual é o contexto atual"), não é por si um achado. O risco não está em quem *lê*: está
  em quem *escreve*. `_usuarioAtual` tem um único ponto de escrita real (login/`/api/auth/me`);
  `projetoAtivo` tem seis, um deles fora do módulo dono (ver acima) — a assimetria entre os dois é
  o sinal de qual dos dois globais precisa de guarda.
- Fora desses dois, a nomenclatura de variável global do arquivo é **bem namespaced por área**
  (prefixos `_neg*`, `_ag*`, `_op*`, `_tf*`, `_cc*`, `_ay*`, `_vp*`, `_cad*`, `_doc*`, `_cfg*`) —
  uma varredura ampla das 358 declarações `let`/`var` de topo não achou um segundo caso do porte
  do `projetoAtivo`/`_expPoll`. Isso é, em si, um dado relevante: o problema de acoplamento do
  frontend não é "está tudo misturado" — é "existem um ou dois pontos centrais de estado
  compartilhado, e nada impede que qualquer área escreva neles".
- **Três variáveis paralelas para o mesmo conceito ("gerente desbloqueou X nesta tela"):**
  `_impostosLiberados`, `_tfTaxaLiberada` e `_descBloqueioRemovido` (área de Negociação), cada uma
  comentada "não persistido: recarregar re-bloqueia". É o mesmo conceito — autorização temporária
  de gerente — representado três vezes em variáveis independentes, em vez de um único estado de
  autorização; risco de uma tela achar que está desbloqueada e outra não, dentro da mesma
  negociação.
- **`nav-07`/`nav-cfg` nascem `style="display:none"` no HTML estático, mas isso NÃO é elemento
  morto — é visibilidade por permissão, decidida em runtime.** ~~O candidato 8 original (`page-09`
  "inalcançável") foi CORRIGIDO em 15/09, depois de o Marcelo confirmar em bancada/Homologação que
  Config abre normalmente com o perfil `pdm2026` (master).~~ O `display:none` do HTML é só o estado
  antes do login resolver; a função que trata a resposta de `/api/auth/me` (`static/index.html`,
  bloco de pós-login) reescreve `nav-07.style.display`/`nav-cfg.style.display` para `''` (visível)
  sempre que o usuário tem a capability `acesso_admin`/`acesso_config` (matriz de Perfis de Usuário,
  `auth/perfis.py`) — e só mantém `none` para quem não tem a capability, ou para `super_admin`/
  `admin_rede` (que chegam em Admin por outro caminho, "Administrar loja"). Não há nenhum
  `goPage(9)` fora do próprio `onclick` do nav-item porque a página não precisa de um segundo
  caminho de entrada — o nav-item É o caminho, só que sua visibilidade não está no HTML, está numa
  função JS que roda depois do login. **Ver nota metodológica no topo da Seção 7** — este era
  exatamente o viés que o Marcelo pediu para caçar nos outros candidatos.

---

## 5. Os achados abertos, classificados por causa estrutural

Levantamento sobre `ACHADOS_CONTABEIS.md` (177 achados numerados, a maioria já resolvida) e
`LISTA_PARALELA.md` (24 itens LP). Abaixo, só o que está **aberto, parcialmente aberto, ou
revertido** — a pergunta que cada grupo responde é: *que fronteira de módulo, se existisse, teria
impedido isto?*

### Causa A — Regra de transição de estado reimplementada na tela (tela oferece o que o servidor recusa)
**Achados:** ACHADO-56 (Revisão de PE fecha "verde" sem o veredito contábil), ACHADO-49
(autoridade do "Remover" da etapa 12 herdou uma regra genérica que não foi pensada para ela),
ACHADO-29 (plano de pagamento do aditivo mostra o contrato inteiro — hipótese de causa é estado
de tela não zerado ao trocar de contexto). *(ACHADO-32/33/39/41 são a mesma família, já
corrigidos — citados aqui como prova de que a fronteira funciona quando aplicada: ver Seção 2.3.)*
**Fronteira que fecharia a classe:** uma função central por domínio ("quais ações/valores são
válidos para este estado", ex.: `vereditos_validos_para_saldo`) consultada tanto por quem desenha
o botão/condição quanto por quem valida a ação no backend — nunca reimplementada na tela. Já
nasceu uma vez (Financeiro/Provisões); ainda não existe para Ciclo/PE nem para Aditivo/Negociação.
**O que já morreu com essa fronteira:** 4 achados no mesmo dia (32, 33, 39, 41), quando aplicada.
**O que ainda não morreu:** ACHADO-56 e ACHADO-49 são a mesma classe, sem a fronteira aplicada
ainda — são os dois candidatos naturais para a próxima rodada desse padrão.

### Causa B — `CicloEtapa`/status de subfase × status do documento/decisão real, duas fontes que ninguém amarra
**Achados:** ACHADO-56 (as duas instâncias: 11d/`reprovar` não toca `AprovacaoPE.status`; 11c/
`guarda_conclusao` nunca consulta a decisão contábil pendente). **Fronteira:** o princípio que o
próprio achado nomeia — "todo fechamento de subfase que representa uma decisão contábil confirma
que a decisão existe" — precisaria virar uma função do Núcleo/Ciclo, com um "hook" que cada
domínio (Financeiro, no caso) registra, em vez de cada subfase reimplementar sua própria checagem.
**O que morreria junto:** as duas instâncias hoje conhecidas (11c e 11d) e, provavelmente, a
próxima subfase que vier a representar uma decisão contábil (ex.: se a Conferência de Volumes da
LP-18 nascer sem essa amarração, repete o padrão pela terceira vez).
**Instância adicional, não numerada como achado ainda, encontrada nesta análise (Seção 3.8):**
`contrato.status` × etapa "7" do Ciclo têm a MESMA forma — nenhuma das duas é derivada da outra, os
dois são escritos por caminhos independentes (`_registrar_assinatura_contrato`, reabertura de
etapa, geração/regeração de contrato), e já existe um remendo defensivo no código por causa disso.
É a mesma causa estrutural do ACHADO-56, numa costura diferente (Contrato/etapa-7 em vez de
Aprovação do PE/etapa-11d) — reforça que Causa B não é um caso isolado, é um padrão que se repete
a cada documento assinável que o Ciclo também rastreia como etapa.

### Causa C — Múltiplos pontos de montagem para o mesmo estado, sem um único setter/leitor
**Achados:** ACHADO-37 (Fila de Provisões empilha todos os projetos), ACHADO-06 (reclassificação
de Outros Fornecedores com dois braços que podem desalinhar), ACHADO-19 (nove chamadores de
`_recalcular_orcamento`, seis engolindo a falha). **Item estrutural correlato, já desenhado mas
não implementado:** LP-13, a Tela Única de Provisões. **Fronteira:** dentro de Financeiro, um
componente único de "provisões do projeto" com dois pontos de *exibição* (ciclo do projeto e
tela dedicada) mas uma implementação; dentro de Comercial, uma transação única para "orçamento
mudou → recalcula", substituindo as nove cópias de tratamento de erro. **O que morre junto:**
ACHADO-37 morre de graça com o LP-13 (o próprio documento afirma isso); ACHADO-06 e ACHADO-19 não
são resolvidos pelo mesmo commit, mas são a mesma *classe* de causa.
**Duas instâncias adicionais, verificadas nesta análise, ainda sem número de achado (Seção 2.8/
2.9):** (1) "concluir uma etapa do Ciclo" tem três implementações (`_set_etapa_status`, o PATCH
genérico de `/ciclo/<codigo>`, `_marcar_etapa_cliente`) e só a primeira dispara
`mod_comissao.preparar_comissao_etapa` — confirmado que a etapa 17 (Montagem), comissionável, só é
concluída pelo caminho que NÃO prepara comissão; (2) as quatro funções `_registrar_assinatura_*`
(contrato/aprovação de PE/solicitação de medição/aditivo) são cópias paralelas da mesma lógica de
"registrar quem assinou e avançar o status", nunca unificadas apesar de `mod_assinatura.py`
(ACHADO-69) já ter unificado o resto do fluxo desses mesmos quatro documentos. Mesma causa,
mesma fronteira que já funcionou uma vez para Provisões: um único setter por conceito, chamado de
todo caminho que produz aquele efeito — não um setter "canônico" que alguns caminhos escolhem
ignorar.

### Causa D — Módulo definido no papel (v12), sem dado próprio no código
**Achados/itens:** LP-23 (remuneração do Montador com rótulo errado — nasce porque Montagem não
tem tabela própria, então o campo genérico da Folha carrega dois significados), parte do LP-15/
ACHADO-31 (falta o markup de ajuste — sintoma indireto de Estoque não existir: não há um registro
de "o que saiu de fábrica" separado do que a NF-e traz), parte do LP-18 (fases/recebimento — a
Conferência de Volumes que a frente descreve é, na prática, uma tela de Estoque que ainda não tem
onde morar). **Fronteira:** dar a Montagem uma tabela mínima própria (ordem de montagem,
referenciando o Mapa de Atribuições por FK) e construir Estoque como domínio real, mesmo que
simples no início — o próprio roadmap de `ARQUITETURA-MODULOS.md` já lista os dois como "fronteira
só (stub)", esperando design. **O que morre junto:** LP-23 inteiro; parte da LP-18 (o recebimento
por fase deixa de ser "onde eu guardo isso?" e vira "que campo desta tabela eu leio?").

### Causa E — Rota/prefixo do manifesto subespecificado (achado novo, encontrado nesta análise)
Não está em nenhum dos dois documentos de achados — é candidato novo (ver Seção 7, item 1): o
manifesto declara `/api/projetos/` inteiro como prefixo de Fiscal, mas rotas de Comercial
(`mod_equipe.py`, por exemplo) e do Ciclo (núcleo) também começam com `/api/projetos/` e não têm
prefixo próprio na lista de nenhum módulo — então `modulo_do_path()`, usado pelo guard real
`_bloqueio_modulo` em seis pontos de despacho de `main.py`, classificaria essas rotas como
"fiscal". **Hoje adormecido** (default "tudo ligado"), mas ativo no instante em que uma loja
desligar Fiscal mantendo Comercial ligado. **Fronteira:** completar as listas de rotas de
Comercial e do Ciclo no manifesto — é o próprio manifesto que precisa da correção, não um módulo
novo.

### Causa F — Conta/campo com nome que não corresponde ao comportamento (higiene, sem causa de fronteira)
**Achados:** ACHADO-04 (`2.1.05` nunca tocada, resíduo), ACHADO-05 (`2.1.04.01` + evento
`pagamento_comissao`, mecanismo morto), ACHADO-08 (parcial — grupo "módulo declarado" segue como
futuro, sem decisão pendente), ACHADO-09 (`5.3.01` usada por dois mecanismos), ACHADO-10
(`_fin_evento_seguro`, código morto), ACHADO-11 (docstring desatualizada), ACHADO-17 (`2.1.04.12`
não faz o que o nome promete). **Resposta honesta à pergunta da seção:** nenhuma fronteira de
módulo teria evitado nenhum destes — são resíduos de decisões de produto que mudaram (Total Flex
trocou de mecanismo, retenção de comissão nunca foi implementada como concebida) sem limpeza
posterior do código/plano de contas. É dívida de *rename*/remoção, não de arquitetura. Valor
prático: são sete achados do mesmo grupo, prontos para uma rodada de limpeza em lote — mas essa
rodada não fecha nada em nenhuma outra causa.

### Causa G — Escape hatches administrativos que furam qualquer fronteira de domínio por desenho
**Achado:** ACHADO-07 (`POST /api/financeiro/lancamentos` e `POST /api/financeiro/eventos`
aceitam conta/evento/valor direto do corpo da requisição, contornando toda regra de negócio das
rotas dedicadas — inclusive o bloqueio do ACHADO-01, se alguém chamar o evento certo manualmente).
**Por que não é achado de fronteira:** nenhuma extração de módulo resolve isto sozinha — é decisão
de superfície de API/permissão. Vale registrar para quem for extrair o Fiscal (Fase 2 do roadmap)
como aviso: qualquer domínio que tenha um endpoint "genérico" de bypass vai carregar o mesmo risco
para fora do monolito.

### Causa H — Validação que devia estar na entrada mora na saída
**Achados:** ACHADO-31 (parcial — falta markup, mas a parte de validação do XML já foi corrigida
movendo a checagem para o upload), ACHADO-20 (recursão infinita em complemento de PE
auto-referente — não alcançável por usuário hoje, mas sem guarda de ciclo). **Fronteira:** dentro
de Fiscal/Comercial, princípio de "falhar cedo na borda" em vez de na emissão/cálculo final — mais
um princípio de camada do que uma fronteira de módulo nova.

### Causa I (fora do escopo de módulo de negócio) — Isolamento de teste/infraestrutura
**Itens:** LP-16, LP-21, LP-22 (o próprio motivo pelo qual esta sessão não pode rodar `pytest` ao
mesmo tempo que a Sessão A). **Resposta explícita:** nenhuma fronteira de módulo de negócio
resolve isto — é isolamento de banco/processo entre execuções de teste (bancos compartilhados,
DDL no boot do E2E, estado vazando entre módulos de teste). Registrado aqui só para não ficar de
fora da contagem total de itens abertos, e para deixar explícito que esta classe **não morre**
com nenhuma das fronteiras propostas na Seção 6.

### Causa J — Especificação escrita e implementada pela metade (o documento afirma que está certo)
**Achado (primeiro exemplo desta causa, 16/09):** parceiro com abrangência `'rede'`
(`_aplicar_abrangencia_parceiro`, `main.py`) — a spec `docs/superpowers/specs/multitenant/
2026-06-21-multitenant-f2-tenancy-design.md:200` registra, desde 21/06, o critério de aceite
"diretor pode 'rede'": `super_admin`/`admin_rede` por política pura, MAIS o diretor (master) da
própria loja — excluindo, por omissão deliberada do texto, gerencial e operador. A implementação
(commit `bcefacf`, mesmo dia da spec) só checou "o ator tem `loja_id`", sem checar nível nenhum —
qualquer perfil de loja (inclusive operador) passava. Achado e corrigido durante a investigação
do vazamento de tenancy em Homologação (ver `LISTA_PARALELA.md`, LP-31, e o registro do Fórum
Orizon em `TAREFA_LOJA_TESTE.md`).
**Por que é pior que as Causas A-I:** nelas, o sintoma é a única fonte — não existe documento
dizendo "isto está certo assim". Aqui existe: a spec registra a regra CORRETA, e essa própria
existência desarma a suspeita de quem lê o código depois ("já tem spec, deve estar implementado
como ela manda"). A lacuna fica invisível justamente pelo documento que deveria ter prevenido.
**Fronteira que fecharia a classe:** não é fronteira de módulo — é hábito de fechamento. Toda spec
com critério de aceite explícito (a seção "Verificação"/"pytest" que várias specs de
`docs/superpowers/specs/` já têm) devia virar um teste NOMEADO pelo próprio critério — aqui,
"diretor pode 'rede', consultor não" — não um teste batizado só pelo caminho feliz ("X pode Y"),
que é exatamente o que produziu a Causa K, logo abaixo (mesmo achado, a outra face). Sem essa
disciplina, ninguém audita depois "o código ainda faz o que a spec de tal data mandou?" uma vez
que a feature já "funciona" na prática.
**O que ainda não sabemos:** este é o único exemplo catalogado até agora — não foi feita (nem foi
pedida) uma varredura das demais specs de `docs/superpowers/specs/` contra o código
correspondente. Fica registrada a classe, para reconhecer o segundo caso quando aparecer, não uma
tarefa de varredura em aberto.

### Causa K — Teste que nomeia e defende o comportamento errado (o teste vira obstáculo do conserto, não garantia dele)
**Achado (mesmo evento da Causa J, a outra face, 16/09):**
`test_consultor_pode_cadastrar_parceiro_de_rede_da_propria_loja`
(`tests/test_parceiro_vinculo_loja.py`) — o PRÓPRIO NOME do teste afirmava, com um consultor
(operador) como sujeito, exatamente o que a spec de 21/06 já proibia. Não documentava uma decisão
tomada; documentava o sintoma do gate frouxo da Causa J, com nome afirmativo e tom de intenção.
Corrigido junto (o teste passou a usar o diretor, e ganhou um irmão negativo provando que o
consultor é recusado).
**Por que importa como padrão, não só como caso:** um teste verde com nome afirmativo ("X pode
Y") convence tanto quanto uma spec escrita — quem for consertar o código por trás dele vê
vermelho ao tentar, e o instinto natural é recuar ("deve haver um motivo, tem teste cobrindo").
Isso inverte a proteção: o teste passa a proteger o DEFEITO, não o comportamento correto.
**A pergunta certa, para quem chegar aqui depois:** quando um teste existente barra um conserto
que a medição (spec, achado, ou decisão registrada) diz que é certo, a primeira pergunta é **se o
teste está certo** — não se o conserto está. Nome afirmativo + sujeito de nível/escopo errado
("consultor pode" quando a regra escrita é "diretor pode") é o sinal mais barato de checar
primeiro, antes de recuar do conserto.
**Fronteira que fecharia a classe:** não é fronteira de módulo — é hábito de revisão, irmão do
hábito que fecharia a Causa J (nomear o teste pelo critério da spec, não pelo caminho que o
código hoje aceita). **Não é pedido varrer os ~2830 testes da suíte atrás de outras instâncias**
(custo alto, nenhum indício concreto de mais casos) — fica só o padrão registrado, para reconhecer
o segundo caso quando ele aparecer.

*(Causas J e K nasceram de um único achado, fora da varredura original de ~52 itens que produziu
a Contagem abaixo — não recontada ali por serem descoberta posterior, 16/09, não parte do
levantamento que gerou aqueles números.)*

### Itens sem causa estrutural (decisão de produto pendente, não achado)
LP-01 (data acordada da medição — falta campo, não é defeito), LP-02 (validar CPF contra cadastro
— política, não bug), LP-09 (alternativas de revisão de PE — funcionalidade nova), LP-12
(desmembramento por fase nas etapas futuras — produto novo), LP-14 (evento de término por etapa —
depende de papéis declarados, ACHADO-46/47), LP-18 (fases/recebimento — frente de produto, uma
tarefa própria já existe), LP-24 (testemunha na assinatura do PE — lacuna ou decisão,
desconhecido). Nenhum destes fecha com fronteira de módulo — fecham com decisão do Marcelo.

### Contagem
De ~52 achados/itens LP examinados linha a linha: **~7 são higiene pura (Causa F)**, sem relação
com fronteira nenhuma; **~7 são decisão de produto pendente**, também sem relação com fronteira;
**3 são infraestrutura de teste (Causa I)**, explicitamente fora do escopo deste mapa; os
**~14 restantes** se agrupam em só **6 causas estruturais** (A a E, H), o que confirma o
diagnóstico do `PLANO_SEMANA_1.md`: a lista não fecha porque poucos padrões produzem muitos
sintomas. As Causas A e B, sozinhas (regra de transição reimplementada na tela; duas fontes de
verdade entre etapa e decisão), já respondem por 4 achados fechados de uma vez (32/33/39/41,
quando a fronteira foi aplicada) e por 2 achados que continuam abertos exatamente por *não* terem
recebido a mesma fronteira ainda (56, 49) — a correlação é direta.

**Nota sobre o que este levantamento encontrou além dos dois documentos:** a leitura de código
cruzada com os achados (Seções 2 e 3) achou pelo menos 4 instâncias novas das Causas B e C que
ainda não têm número de achado — a etapa 17 (Montagem) não preparando comissão pelo fluxo padrão
(2.8), as 4 funções `_registrar_assinatura_*` não unificadas (2.9), `contrato.status`×etapa "7"
sem sincronização (3.8) e os motivos de retenção duplicados à mão (3.7). Nenhuma foi corrigida
aqui — ficam registradas na Seção 7 para o Marcelo decidir se viram achado. O padrão se repete: são
a mesma causa estrutural (B ou C) de achados já existentes, encontradas porque este mapa olhou o
sistema inteiro de uma vez, não um endpoint por vez.

---

## 6. Fronteiras propostas — trade-offs, não decisão

*(Quem decide é o Marcelo — o que segue é o levantamento de opções com o custo de cada uma.)*

### 6.1 — Função central de "transições válidas", por domínio, testável como padrão de arquitetura
**O que seria:** replicar o padrão que já fechou 4 achados (`vereditos_validos_para_saldo`) para
Ciclo/PE (a pergunta "esta subfase pode fechar?") e para Negociação/Aditivo. Idealmente, um teste
de arquitetura no estilo de `tests/test_arquitetura_modulos.py` que verifique — por convenção de
nome ou por um registro explícito — que toda lista de botões condicionais no frontend tem uma
function-espelho no backend com a mesma fonte de regra.
**Prós:** já provado (fechou 4 achados de uma vez); baixo custo por instância.
**Contras:** exige generalizar `guarda_conclusao`/`SUBFASES_PE` para aceitar um "hook" plugável
por domínio (hoje é hardcoded ponto a ponto) — mexe no motor mais crítico do sistema (o Ciclo).
O teste de arquitetura em si (a parte "por convenção de nome") é mais difícil de automatizar do
que o de imports — decidir isso é trabalho de desenho, não de implementação mecânica.

### 6.2 — Implementar a Tela Única de Provisões (LP-13)
**O que seria:** o desenho já fechado com o Marcelo em 05/09 — um componente, dois pontos de
montagem (ciclo do projeto e a Fila), a mesma consulta/endpoint nos dois.
**Prós:** zero decisão de desenho pendente — é a única fronteira desta lista pronta para
implementar direto; fecha ACHADO-37 e reduz o risco estrutural por trás de 26/32/33/41 mesmo já
corrigidos pontualmente.
**Contras:** nenhum registrado — é a mais barata das seis propostas.

### 6.3 — Estoque como domínio real de dados, mesmo que mínimo
**O que seria:** ao menos um registro de "o que saiu da fábrica / o que chegou no depósito",
separado da NF-e e do XML — o pré-requisito que `ARQUITETURA-MODULOS.md` já nomeia para o markup
de ajuste (LP-15) e para a Conferência de Volumes por fase (LP-18).
**Prós:** já é o item 2 do roadmap de extração física ("Fase 2+"); dois itens abertos (LP-15,
parte do LP-18) dependem dele.
**Contras:** é o maior item desta lista — exige decidir a granularidade de rastreio (`cProd[ID]`
peça a peça, per `ARQUITETURA-MODULOS.md`) antes de desenhar qualquer tabela; puxa Fiscal e
Comercial como dependentes (`depende_de` já declarado no manifesto).

### 6.4 — Promover Montagem a domínio com tabela própria
**O que seria:** ao menos uma "ordem de montagem" com FK para o Mapa de Atribuições, em vez de a
lógica de Montagem viver espalhada entre Ciclo (agenda/cronograma) e Folha (base de comissão).
**Prós:** resolve LP-23 na raiz (o campo de remuneração deixa de precisar significar duas coisas).
**Contras:** hoje ninguém sentiu dor operacional suficiente para isso além do LP-23 — extrair
antes da dor certa é o risco de YAGNI que o próprio `ARQUITETURA-MODULOS.md` cita para Estoque e
Pós-venda. É uma proposta de "antecipar", não de "consertar algo quebrado hoje".

### 6.5 — Admin e Config como chaves de primeira classe no manifesto
**O que seria:** dar a Admin e Config uma entrada em `modulos.py` (mesmo que continuem núcleo,
sempre ligados) — hoje ficam invisíveis ao teste de fronteira e a `modulo_do_path()` porque
nenhuma chave os representa.
**Prós:** baixo custo (é classificação, não código novo); resolveria de quebra a Causa E (Seção
5) se as rotas de Admin/Config forem enumeradas no processo.
**Contras:** pode ser visto como redundante — Admin sempre foi entendido como "console sobre
outros módulos", não como um módulo com regras de dependência próprias; classificar mal poderia
criar uma falsa sensação de fronteira onde não há dado nenhum para proteger.

### 6.6 — Completar as listas de rotas de Comercial e do Ciclo no manifesto (Causa E)
**O que seria:** o conserto mais estreito de todos — adicionar `/api/projetos/<nome>/equipe`,
`/api/projetos/<nome>/briefing`, `/api/projetos/<nome>/ciclo/*` etc. às listas de rotas de
`comercial`/`ciclo` no manifesto, para que `modulo_do_path()` pare de atribuí-las a Fiscal por
padrão.
**Prós:** é a única proposta desta lista que é, na prática, uma correção pontual e não uma
decisão de arquitetura — não muda nenhum comportamento visível hoje (a guarda está adormecida por
"tudo ligado" default).
**Contras:** nenhum — mas fica fora de escopo desta sessão (Sessão B não escreve código); fica
registrado para a Sessão A ou para a Semana 2.

---

## 7. Candidatos a achado

*(Não decido se viram achado — só registro o que encontrei durante a análise, para o Marcelo
decidir. Nenhum foi corrigido.)*

> **Nota metodológica (15/09) — correção do candidato 8, e uma auditoria de viés.** O candidato 8
> original dizia que `page-09` (Config) era inalcançável, com base em "o único `goPage(9)` do
> arquivo é o do próprio nav-item, que está `display:none`". Estava **errado**: o Marcelo abriu
> Config em bancada e em Homologação com o perfil `pdm2026` (master). O `display:none` no HTML é só
> o estado ANTES do login resolver — uma função que roda logo depois de `/api/auth/me` responder
> reescreve `nav-07.style.display`/`nav-cfg.style.display` conforme a capability do perfil
> (`acesso_admin`/`acesso_config`, matriz de Perfis de Usuário em `auth/perfis.py`) ou o nível
> (`super_admin`/`admin_rede` usam outro caminho, "Administrar loja"). **A lição, generalizada:**
> `grep` em `static/index.html` só vê o estado ESTÁTICO do HTML — qualquer conclusão do tipo "está
> `display:none`" ou "nada chama esta função/id" pode estar descrevendo o estado pré-login, não o
> estado real para o perfil que importa, porque a visibilidade real é decidida por JavaScript
> rodando depois do login, condicionado a permissão. Reauditei os outros sete candidatos contra
> esse viés especificamente:
> - **Candidato 1** (`modulo_do_path()`/Fiscal) — verificado lendo o CORPO da função
>   `_bloqueio_modulo` no backend (não a ausência de referência no HTML); confirmado que não há
>   allowlist nem exceção — **mantém-se, sem alteração**.
> - **Candidato 2** (`page-01` morto) — confirmado que `nav-01` **não existe** no HTML (a busca por
>   `id="nav-01"` não encontra nada), então `unlockNav(1)` — chamado em 3 pontos do código — é hoje
>   um no-op silencioso (`getElementById` retorna null, o guard `if(el)` absorve). Não há permissão
>   nenhuma escondendo isso: é morto de fato, em qualquer perfil — **mantém-se, sem alteração**.
> - **Candidato 3** (rótulo "Operacional" de Montagem) — **CORRIGIDO E FORTALECIDO abaixo**: eu
>   tinha escrito "não há sintoma visível ainda", o que também era o viés — não verifiquei se o
>   rótulo é consumido por alguma API antes de concluir isso. Ele é.
> - **Candidatos 4, 5, 6, 7** — nenhum depende de "o que está visível no DOM hoje"; são duplicação
>   de dado/lógica entre arquivos-fonte (Python × JS) ou chamadas de função verificadas lendo o
>   corpo de quem chama, não a ausência de chamada. **Mantêm-se, sem alteração.**

1. **`modulo_do_path()` classificaria a maior parte de `/api/projetos/<nome>/*` como "fiscal".**
   `modulos.MODULOS["fiscal"]["rotas"]` inclui o prefixo largo `/api/projetos/`;
   `modulos.MODULOS["comercial"]["rotas"]` e a entrada `"ciclo"` (núcleo, `rotas: []`) não têm
   nenhum prefixo próprio sob `/api/projetos/`. O guard real `_bloqueio_modulo` (chamado em seis
   pontos de despacho de `main.py`) usa `modulo_do_path()` para decidir se uma rota pertence a um
   módulo desligado para a loja. Confirmado por leitura: rotas claramente de Comercial (ex.: as
   que `mod_equipe.py` atende, tipo "grava a seleção de um papel da Equipe do Projeto") e do
   Ciclo (reabertura de etapa, PATCH de status) caem, por eliminação, no prefixo de Fiscal.
   **Hoje adormecido** — o default de topologia é "tudo ligado" para toda loja — mas ativo assim
   que qualquer loja desligar Fiscal mantendo Comercial ligado (a própria `ARQUITETURA-MODULOS.md`
   descreve esse cenário como objetivo: "loja avulsa" com topologia reduzida).

2. **`page-01` é um elemento morto, com o mesmo nome de área ("Cadastro") de `page-10`.**
   Marcado no próprio HTML como `<!-- PAGE 01 DUMMY (mantido para não quebrar unlockNav) -->` —
   não é usado por nenhum `goPage(1)` encontrado, mas o comentário admite uma dependência (função
   `unlockNav`) que ainda espera que o elemento exista. Risco baixo (não afeta comportamento
   visível), mas é confusão de leitura para quem grepar "Cadastro" no arquivo.

3. **O rótulo interno de Montagem no manifesto ainda é `"Operacional"` — e isso JÁ é visível a
   quem configura permissões, corrigido/fortalecido em 15/09.** `modulos.py`:
   `"montagem": {..., "rotulo": "Operacional", ...}`. O papel v12 renomeou explicitamente esse
   módulo para "Montagem" (Pós-venda deixou de ser módulo, virou faixa) — o manifesto não
   acompanhou o rename. Ao contrário do que eu tinha escrito antes ("não há sintoma visível
   ainda"), há sim: `mod_perfis_opcoes()` (`main.py`) monta `dominios_com_rotulo()` (que lê
   `rotulo` direto do manifesto) e devolve isso como `modulos_opcoes` na resposta de
   `GET /api/admin/perfis` — consumida pela tela **Admin › Perfis de Usuário** (a matriz onde se
   escolhe quais domínios cada perfil pode acessar). Ou seja: hoje, um admin configurando permissões
   de um perfil vê um checkbox rotulado **"Operacional"**, não "Montagem", nessa tela. Sintoma real,
   não hipotético — quem tem acesso a Admin › Perfis (que agora sabemos ser mais gente do que eu
   presumi — ver nota metodológica acima) já vê essa divergência.

4. **`ETAPAS_CICLO`/`_FICHA_GRUPO_NOME` (frontend) continuam sendo cópias manuais de
   `mod_ciclo.ETAPA_NOME`/`ETAPAS_PRINCIPAIS`/`GRUPO_NOME` (backend), sem mecanismo que force
   sincronia.** Já divergiram uma vez (achado da Vera, 26/08, documentado no próprio
   `mod_ciclo.py`). Não é uma correção de código pequena (geraria uma rota nova de "o backend
   expõe o catálogo, o frontend deixa de ter o seu"), por isso fica como candidato, não como
   conserto sugerido.

5. **Concluir a etapa 17 (Montagem) pelo fluxo padrão da UI não prepara a comissão do Montador —
   confirmado por leitura completa do handler, não é hipótese.** `PATCH /api/projetos/<nome>/
   ciclo/<codigo>` (a rota documentada em `docs/arquitetura/ROTAS.md` como o jeito de avançar
   etapa, e a única disponível para a 17, que não tem endpoint dedicado) reimplementa `etapa.
   status`/`concluido_em`/`responsavel_id` inline e nunca chama `_set_etapa_status` — a única
   função que, nessas mesmas condições, também dispara `mod_comissao.preparar_comissao_etapa`.
   Nenhum dos call sites confirmados de `_set_etapa_status` cobre a etapa "17". Ver Seção 2.8 para
   a leitura completa do handler que sustenta esta afirmação. Impacto potencial: se confirmado por
   quem conhece o fluxo real de pagamento, é o tipo de achado silencioso — sem erro, sem 400, sem
   log — que só aparece quando um Montador reclama que não recebeu.

6. **`contrato.status` e a etapa "7" do Ciclo são escritos por três funções independentes, sem
   sincronização — com um remendo defensivo já escrito por causa disso.** Ver Seção 3.8. Diferente
   do ACHADO-56 (que já tem número), esta instância ainda não foi registrada nos dois documentos de
   achados.

7. **A lista de motivos de retenção por obra é uma cópia manual, no frontend, de
   `mod_retido.MOTIVOS_RETENCAO`.** Ver Seção 3.7. Risco baixo isoladamente, mas é a segunda
   instância confirmada (depois de `ETAPAS_CICLO`/`ETAPA_NOME`, que já divergiu uma vez) do mesmo
   hábito — vale considerar se merece um princípio geral ("todo enum de negócio nasce só no
   backend, o frontend busca via API") em vez de tratar cada ocorrência isoladamente.

8. ~~**`page-09` (Config) não parece alcançável por nenhum caminho de navegação hoje.**~~
   **CORRIGIDO em 15/09 — não é achado, era leitura incompleta.** O candidato original concluiu
   isso de "só existe um `goPage(9)` no arquivo, e é o `onclick` do nav-item oculto por
   `display:none`" — sem checar que a visibilidade daquele `display:none` é reescrita em runtime
   por permissão (ver nota metodológica logo acima). Confirmado pelo Marcelo: Config abre
   normalmente com o perfil `pdm2026` (master), em bancada e em Homologação. A visibilidade real
   depende da capability `acesso_config` do perfil do usuário — não é "sempre oculto", é "oculto
   só para quem não tem a capability, mais super_admin/admin_rede (que usam outro caminho)". Este
   item some da lista de candidatos.

---

## Referências consultadas
`docs/db/PLANO_SEMANA_1.md` · `docs/especificacoes/Modulos_Orizon_v12.docx` ·
`docs/ARQUITETURA-MODULOS.md` · `modulos.py` · `tests/test_arquitetura_modulos.py` ·
`tests/test_modulos.py` · `docs/processos/FLUXO_38_ETAPAS.md` · `docs/arquitetura/ROTAS.md` ·
`docs/arquitetura/DECISOES.md` · `mod_ciclo.py` · `mod_assinatura.py` ·
`docs/db/ACHADOS_CONTABEIS.md` · `docs/db/LISTA_PARALELA.md` · `static/index.html` · `main.py`.
