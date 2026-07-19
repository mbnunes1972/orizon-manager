# Motor 5.0 — Reestruturação `app/` (core/modules/integrations/shared) — Design

**Data:** 2026-07-16
**Estado:** decidido, **preparação em andamento** — execução adiada até a v1 estabilizar em produção
**Escopo desta frente:** documentação, inventário de módulos e plano de fatiamento — **sem mexer em
código** enquanto a v1 estiver ativa
**Fora de escopo (por ora):** qualquer migração de arquivo/import real; isso só começa quando a v1
estiver estável em uso e a decisão de iniciar a execução for tomada explicitamente

---

## 1. Contexto

O layout atual do código está no meio de uma reorganização **incremental** (`CLAUDE.md`, seção "Layout
do código"): módulos `.py` soltos na raiz, indo virando pacote por domínio (`fiscal/`, `integracoes/`,
`auth/`, `mod_fin/`), com `test_arquitetura_modulos` garantindo que nada fique órfão. Falta empacotar
`comercial/` (15 arquivos).

Esse plano incremental **continua até o fim** — não é substituído por esta spec. É uma reorganização
mais modesta (agrupar o que já existe por domínio, na raiz do repo).

**Motor 5.0** é uma ambição maior e deliberadamente **posterior**: uma reestruturação completa para uma
arquitetura em camadas —

```
app/
├── core/            # infraestrutura transversal (config, database, auth, tenancy, events)
├── modules/         # domínio de negócio, um pacote por área
│   ├── cadastros/
│   ├── comercial/
│   ├── projetos/
│   ├── operacoes/
│   ├── logistica/
│   ├── montagem/
│   ├── pos_venda/
│   ├── financeiro/      # inclui o motor contábil (partida dobrada) — não separa (§9)
│   ├── folha/
│   ├── fiscal/
│   ├── relatorios/
│   └── documentos/
├── integrations/    # Focus NFe, Omie, bancos, armazenamento
├── shared/          # enums, exceptions, utilities, value objects
└── main.py
```

## 2. Decisão

1. **Sequência confirmada (já debatida antes desta sessão):** primeiro a v1 (arquitetura atual,
   empacotamento incremental) chega a uma versão estável em produção. **Só depois** começa a execução
   real do Motor 5.0.
2. **Mas a preparação começa agora, em frente paralela.** Objetivo: quando a v1 estabilizar, a migração
   para o Motor 5.0 já tem plano, inventário e fatiamento prontos — não começa do zero.
3. **"Mesma cara, motor novo."** O Motor 5.0 não é uma reescrita de produto — é a mesma aplicação
   (mesma UI, mesmo comportamento pro usuário final) rodando sobre uma reestruturação interna. Não se
   confunde com pedidos de feature nova; aqueles continuam entrando na v1 normalmente enquanto ela for a
   versão em produção.
4. **Extremo cuidado, sem prazo fixo.** O texto do Marcelo é explícito: "pode durar um bom tempo no ar"
   — não há pressão de data. A v1 seguirá recebendo alterações solicitadas mesmo depois que o Motor 5.0
   começar a funcionar; o Motor 5.0 não é "big bang", é evolução cuidadosa em paralelo.

## 3. Como esta frente de preparação funciona

- O Marcelo lista a **visão real dos módulos** (o inventário de negócio, não necessariamente 1:1 com os
  arquivos `.py` atuais) e vai debatendo, seção por seção, como cada um mapeia pra estrutura `app/`.
- Toda documentação já sai **pronta para a migração futura** — ou seja, cada decisão registrada aqui já
  assume o layout `app/core/modules/...` como destino, não como esboço a refinar depois.
- Claude lê a documentação existente do projeto em detalhe ao longo dessa frente (specs em
  `docs/superpowers/specs/`, `DEV_LOG.md`, `REQUIREMENTS.md`, os módulos `.py` reais) para identificar o
  que já pode ser **fatiado** desde já — ou seja, que fronteiras de domínio já estão claras o suficiente
  pra virar plano de migração, mesmo sem executar nada ainda.

## 4. O manifesto atual já é uma pista — não estamos começando do zero

`modulos.py` (usado por `test_arquitetura_modulos`) já classifica o sistema em **núcleo** (sempre ligado)
e **domínios desligáveis por loja**. Isso já é uma forma de modularidade em produção hoje — o Motor 5.0
não inventa o conceito de módulo, ele formaliza em código (pastas, fronteiras de import) o que já existe
como manifesto de configuração:

- **Núcleo:** `auth`, `tenancy` (`mod_tenancy.py`), `escopo` (`mod_escopo.py`), `auditoria` (sem arquivo
  próprio — só tabelas de log), `ciclo` (`mod_ciclo.py`, `mod_cronograma.py`), `integracoes` (pacote),
  `plataforma` (`database.py`, `storage.py`).
- **Domínios desligáveis (ordem de UI):** `captacao` (**stub vazio** — zero arquivo/tabela/rota, só
  reservado), `cadastro`, `comercial` (16 arquivos), `fiscal`, `estoque` (stub vazio), `expedicao`,
  `montagem` (stub vazio), `assistencias`, `financeiro`, `folha`.

**Achado que responde direto sua dúvida sobre "mercado":** `captacao` já existe como domínio reservado,
sem nenhum código — é o único slot (além de `estoque`/`montagem`) já pensado e ainda vazio. Não precisa
inventar uma gaveta nova pra "mapear relacionamento com o mercado"; a gaveta já existe no manifesto atual,
só nunca foi usada. Proposta: `app/modules/captacao/` recebe essa responsabilidade quando a fonte de dado
for definida (ver §7).

## 5. Projeto como eixo central — o que isso exige da arquitetura nova

`Projeto` (`database.py`, tabela `projetos_meta`) tem **`nome_safe` (string) como chave primária**, não
um `id` numérico. E — achado importante — **nenhuma das ~17 tabelas que dependem de Projeto usa
`ForeignKey` de verdade**: todas amarram por texto solto (`projeto_nome`/`projeto_id`, colunas
`Text`/`String` sem constraint), incluindo `Briefing`, `PoolAmbiente`, `CicloEtapa`, orçamentos,
contratos, medições, parcelas, folha/comissão. O banco não impede hoje um "projeto fantasma" (referência
a um `nome_safe` que não existe mais).

O ciclo (`mod_ciclo.ETAPAS_PRINCIPAIS`, 19 etapas ativas — 1 Cadastro do Cliente → 21 Conciliação Final,
etapas 5/6 removidas) é a espinha dorsal que você descreve — mas hoje ele **dispara os outros módulos de
forma imperativa**: é o handler HTTP de `PATCH /ciclo` em `main.py` que, ao mudar o status de uma etapa,
chama diretamente funções de `mod_contrato`, `mod_contabil`, `mod_medicao` etc. `main.py` termina sabendo
demais sobre o interior de cada módulo.

**Duas decisões de arquitetura que o Motor 5.0 precisa tomar, exatamente por causa dessa centralidade:**

1. ✅ **DECIDIDO (2026-07-16): Projeto ganha PK numérica real + FK de verdade em todas as tabelas
   dependentes.** Hoje funciona porque `nome_safe` é único e estável, mas as ~17 tabelas que amarram por
   texto solto (§5, acima) passam a referenciar `Projeto.id` via `ForeignKey` de verdade no Motor 5.0.
   `nome_safe` continua existindo (é usado como slug/identificador legível — URLs, nomes de pasta em
   `PROJETOS_DIR`), mas deixa de ser a chave que sustenta os relacionamentos do banco. **Implicação pra
   o plano de migração:** essa mudança precisa vir acompanhada de um script de backfill (gerar `id`
   pros projetos existentes e reapontar as ~17 FKs) — não é só trocar o tipo da coluna.
2. ✅ **DECIDIDO (2026-07-16): o disparo do ciclo vira evento explícito.** Em vez de `main.py` chamar
   módulo por módulo, uma etapa concluída publica um evento (`app/core/events`) — ex. `ContratoAssinado`,
   `NFeAutorizada`, `MedicaoConcluida` — e cada módulo interessado assina o que precisa. **Porquê
   (Marcelo, 2026-07-16):** do jeito de hoje, o disparo é deficiente — fica **preso dentro do dispatch
   imperativo de `main.py`**, invisível pra qualquer coisa que não seja aquele handler específico.
   Publicar como evento explícito torna a transição de etapa um **dado público do sistema**: qualquer
   consumidor novo (ex. a secretária IA — já citada em `mod_equipe.py` — ou um futuro serviço de
   notificação/auditoria) pode assinar `ContratoAssinado`/`MedicaoConcluida`/etc. sem precisar que
   `main.py` saiba que esse consumidor existe. **Implicação pro plano:** o catálogo de eventos (que
   evento existe, quem publica, quem assina) vira uma peça central do design — não é só refatoração
   interna, é a interface que habilita features futuras (secretária IA incluída) a reagir ao ciclo sem
   acoplamento direto.

## 6. "Comercial" hoje é 5 responsabilidades diferentes num arquivo só — proposta de fatiamento

Os 16 arquivos hoje classificados `comercial` cobrem coisas bem distintas:

| Responsabilidade real | Arquivos atuais | Destino proposto no Motor 5.0 |
|---|---|---|
| Motor de negociação/preço (cálculo puro) | `mod_orcamento_params.py`, `mod_margens.py`, `mod_negociacao.py`, `mod_pe_comparacao.py`, `mod_parcelas.py`, `mod_fin/` | `app/modules/comercial/` (núcleo operacional: funil, orçamento, negociação — a definição "clássica" de Comercial) |
| Geração de documento (contrato/proposta) | `mod_contrato.py`, `mod_marcadores.py`, `mod_documentos.py`, `mod_documentos_import.py` | `app/modules/documentos/` (já era um módulo à parte na sua lista original — faz sentido próprio: versionamento, templates, PDF) |
| Medição/qualidade de dado técnico | `mod_medicao.py`, `mod_qualidade_xml.py` | `app/modules/projetos/` (são validações de etapas do PRÓPRIO ciclo do projeto — 9/10 Medição — não são "vender", são "executar o que foi vendido") |
| Equipe do projeto (roster de responsáveis) | `mod_equipe.py` | `app/modules/projetos/` (cross-cutting por natureza — mistura papel comercial/montagem/SAC; mora melhor perto do dono do ciclo) |
| Indicadores/KPI/gráficos | `mod_comercial_dash.py` | **ver §7 — é aqui que mora a ambiguidade que você levantou** |
| Utilitário solto | `_ler_aymore.py` | avaliar se ainda é usado; candidato a `shared/utilities` ou aposentadoria |

## 7. Comercial × Relatórios × Captação — a ambiguidade que você levantou, resolvida

✅ **DECIDIDO (2026-07-16) — Marcelo aprovou a proposta abaixo sem ajustes.**

Você descreveu "Comercial" com duas responsabilidades bem diferentes: **(a)** extrair indicadores/KPI/
relatórios/gráficos de gestão, e **(b)** mapear relacionamento com o mercado. E sua lista original já
tinha um módulo `relatorios` separado. Isso é uma tensão real, não um detalhe — proposta:

- **`app/modules/comercial/`** = a operação em si (funil, orçamento, negociação, propostas) — o que já
  existe hoje, menos documentos/medição/dashboard que saem pra outro lugar (§6).
- **`app/modules/relatorios/`** = a camada de leitura/BI **cross-domínio**: recebe `mod_comercial_dash.py`
  (funil, carteira, volume, ticket médio) e o que hoje é `mod_contabil.dashboard_financeiro` (dashboard
  financeiro embutido no próprio módulo financeiro). Regra do ChatGPT que vale adotar: **relatório não
  escreve dado de negócio**, só lê e consolida — hoje já é assim de fato (`dashboard_comercial` é view
  derivada, não persiste nada), só falta a fronteira de pasta refletir isso.
- **`app/modules/captacao/`** = a peça que ainda não tem fonte de dado definida (seu "mapear
  relacionamento com o mercado"). Fica reservado, com o mesmo status de hoje (stub) até você decidir a
  fonte — só que agora com um lugar claro no Motor 5.0 em vez de ficar solto dentro de Comercial. Quando
  a fonte aparecer (você mencionou uma possível relação com "captação" — o que já bate com o nome do
  domínio reservado), os KPIs de mercado alimentam `relatorios` a partir daqui, sem misturar com o
  funil/orçamento operacional do Comercial.

## 8. Estrutura interna padrão por módulo

Cada módulo em `app/modules/<dominio>/` segue o mesmo layout interno (adotado da sua conversa com o
ChatGPT — faz sentido incorporar, é o pedaço que a spec original ainda não detalhava):

```
<dominio>/
├── models/       # entidades/tabelas do domínio
├── services/      # regras de negócio, orquestração
├── repositories/   # acesso a dado (consultas/persistência)
├── api/           # rotas HTTP expostas por esse domínio
├── schemas/        # validação/serialização de entrada e saída
└── tests/
```

**Regra de fronteira entre módulos:** um módulo não importa `repositories`/`models` de outro domínio
diretamente — só a `services`/API pública dele, ou reage a um evento publicado em `core/events`. Ex.:
Comercial não deveria escrever direto em tabela do Financeiro; chama
`financeiro.registrar_venda(projeto_id, valor)` ou reage a um evento que o Financeiro publica.

## 9. Inventário completo — mapeamento módulo atual → `app/modules/*`

| Domínio (`app/modules/`) | Conteúdo atual (arquivos/tabelas) | Situação |
|---|---|---|
| `cadastros` | `validacao_doc.py`, `mod_cadastro.py`; `clientes/parceiros/funcionarios/fornecedores/terceiros/funcoes` | fronteira clara hoje |
| `comercial` | Ver §6 — motor de negociação/preço, sem documentos/medição/dashboard | fatiamento necessário |
| `projetos` | `Projeto`/`projetos_meta` + `mod_equipe.py` + `mod_medicao.py`/`mod_qualidade_xml.py` (vindos de §6) | **eixo central** — decisão de FK/eventos (§5) precisa vir antes de mexer aqui |
| `operacoes` | hoje é o próprio `mod_ciclo.py`/`mod_cronograma.py` (núcleo) — avaliar se vira módulo de domínio ou continua núcleo | a decidir |
| `logistica` | `mod_expedicao.py`; `ciclo_logistico`, `ciclo_logistico_transicao` (hoje nomeado "expedicao") | fronteira clara, só renomear |
| `montagem` | **stub vazio hoje** — planejado, não implementado | nasce do zero no Motor 5.0 ou antes, na v1 |
| `pos_venda` | `mod_assistencias.py`; `assistencia_caso` (hoje nomeado "assistencias") | fronteira clara, só renomear |
| `financeiro` | `mod_provisoes.py`, `mod_contabil.py` (motor contábil, inclui o que seria "contábil" — ver decisão abaixo) | ✅ decidido: fica um módulo só (financeiro+contábil), sem separar |
| `folha` | `mod_folha.py`, `mod_comissao.py`, `mod_adiantamento.py` | ✅ decidido: módulo próprio, NÃO entra em `financeiro` — já é domínio desligável independente hoje (`modulos.py`), usuário diferente (RH), e é a frente ativa agora (Remunerações) |
| `fiscal` | pacote `fiscal/` já empacotado na v1 | pronto, só mover de lugar |
| `relatorios` | **não existe hoje como domínio** — nasce de `mod_comercial_dash.py` + `dashboard_financeiro` (§7) | módulo novo, cross-domínio |
| `documentos` | `mod_contrato.py`, `mod_marcadores.py`, `mod_documentos.py`, `mod_documentos_import.py` (vindos de §6) | fronteira clara depois do fatiamento |
| `captacao` | **stub vazio hoje**, reservado no manifesto atual | nasce quando a fonte de dado de mercado for definida (§7) |
| `estoque` | **stub vazio hoje** | fora do escopo desta rodada |
| `integrations/` | pacote `integracoes/` já empacotado (Focus NFe, Omie) | pronto, só mover de lugar |
| `core/` | `auth/`, `mod_tenancy.py`, `mod_escopo.py`, `database.py`, `storage.py`, `mod_ciclo.py`? | `mod_ciclo` é candidato a `core/events` em vez de módulo de domínio — ver §5 |

## 10. Riscos já identificados (carregados da experiência da reorganização incremental atual)

- **Caminho relativo a `__file__` dentro de pacote aponta pra pasta do pacote, não a raiz** — já mordeu
  o projeto uma vez (sumiu a página de entrada em silêncio, 404). Numa reestruturação do tamanho do Motor
  5.0, esse risco se multiplica por cada módulo movido. `test_caminhos_de_pacote.py` é o ratchet disso
  hoje; o Motor 5.0 vai precisar de um equivalente mais abrangente.
- **Import de fora vs. entre irmãos** — o padrão já estabelecido (`from fiscal import mod_nfe` de fora,
  `from . import mapa_fiscal` entre irmãos) deve se manter como convenção no `app/` também, por
  consistência.
- **Coordenação com outras sessões de desenvolvimento ativas.** Esta frente é só documentação enquanto a
  v1 está em produção sendo alterada por outras sessões — evita qualquer risco de colisão de arquivo/git
  enquanto a decisão de "começar a execução de verdade" não for tomada explicitamente.

## 11. Sequência de concepção proposta

Ordem pensada pra resolver primeiro o que é genuinamente incerto, deixando pra depois o que já é
confirmação rápida de fronteira clara:

1. ✅ **Fechado (2026-07-16) — §5 (Projeto: FK real + eventos explícitos).** As duas decisões da
   fundação estão tomadas: PK numérica + FK real nas ~17 tabelas dependentes, e o ciclo passa a publicar
   eventos explícitos em `app/core/events` (motivado por tornar a transição de etapa um dado público do
   sistema, habilitando consumidores como a secretária IA sem acoplamento direto a `main.py`).
2. ✅ **Fechado (2026-07-16) — §6-7 (Comercial × Relatórios × Captação).** Aprovado sem ajustes: Comercial
   fica só a operação (funil/orçamento/negociação); `relatorios` (novo) absorve o dashboard/KPI hoje em
   `mod_comercial_dash.py` + `dashboard_financeiro`; `captacao` fica reservado pro dado de mercado ainda
   sem fonte definida.
3. ✅ **Fechado (2026-07-16) — módulos de fronteira já clara (§9).** Confirmado sem ajustes: `fiscal` e
   `integracoes` seguem como já empacotados na v1, só mudam de lugar; `cadastro`→`cadastros`,
   `expedicao`→`logistica`, `assistencias`→`pos_venda` — renomeações aprovadas.
4. ✅ **Fechado (2026-07-16) — destino de `folha`/`contabil` (§9).** `folha` vira módulo próprio (já é
   domínio desligável independente hoje, usuário diferente, frente ativa agora); `contabil` NÃO separa
   de `financeiro` (motor de partida dobrada é uma peça só hoje, separar seria fronteira artificial).
5. **PRÓXIMO — Tratar os stubs vazios** (`captacao` além do já decidido em §7, `estoque`, `montagem`) —
   são território livre, sem legado pra encaixar, ficam pra quando a v1 for implementá-los de verdade
   (dentro ou fora do Motor 5.0, a decidir na hora).
6. **Fechar a estrutura interna padrão (§8)** e o catálogo de eventos que `core/events` vai carregar —
   última peça, depende de 1-2 já estarem fechados.

## 12. Próximos passos

1. Marcelo revisa este documento (especialmente §5 e §7, as duas decisões reais em aberto) e aprova ou
   ajusta seção por seção, na ordem do §10.
2. Claude aprofunda cada seção aprovada com mais detalhe conforme necessário (ex.: desenhar o catálogo de
   eventos, ou o plano de migração de PK do Projeto).
3. Quando a v1 estiver estável em produção **e** o inventário/plano estiver completo, uma nova spec
   ("Motor 5.0 — Execução") é aberta para começar a migração de fato.

## 13. Catálogo de eventos do ciclo — extraído da história (RASCUNHO, pendente de validação)

Marcelo narrou o fluxo real de um projeto de planejados, do lead até o encerramento, com atenção a três
coisas: quando cada evento acontece, que documento oficializa a transição de responsabilidade, e onde o
arquiteto precisa ser informado (ou decidir). Esta seção organiza essa história em eventos candidatos a
`core/events`. **Nada aqui está decidido ainda** — é a matéria-prima organizada pra vocês debaterem.

### 13.1 Tabela de eventos

| # | Evento candidato | Etapa do ciclo hoje | Documento / transição de responsabilidade | Arquiteto |
|---|---|---|---|---|
| 1 | `LeadCaptado` (canal: showroom, Instagram, indicação de arquiteto) | **nenhuma — hoje é o domínio `captacao`, stub vazio** | nenhum hoje | pode ser a origem (arquiteto manda o projeto direto) |
| 2 | `EspecificacaoInicialColetada` (desejo estético/funcional) | 3 Briefing | Briefing | — |
| 3 | `VisitaShowroomRealizada` | sem etapa própria hoje | **lacuna:** nada registra o que foi efetivamente mostrado/prometido no showroom — é a raiz do "descasamento de expectativa" citado | — |
| 4 | `PropostaTecnicaElaborada` (segue desejo do cliente OU especificação do arquiteto) | pré-4 | — | especifica ou é seguido |
| 5 | `ProjetoApresentadoAoCliente` (Promob) | 4 Orçamento | — | — |
| 6 | `AjusteSolicitadoPeloCliente` — **quando diverge da especificação do arquiteto** | 4 Orçamento | **lacuna:** hoje nada avisa o arquiteto quando o cliente altera o que ele especificou | **deveria ser avisado — às vezes decide** |
| 7 | `NegociacaoConcluida` (preço fechado) | 4 Orçamento | Orçamento | — |
| 8 | `ContratoAssinado` | 7 Contrato | Contrato | — a partir daqui, prazo é o desafio central |
| 9 | `MedicaoSolicitada` / `MedicaoRealizada` | 9/10 | Termo de Medição | — |
| 10 | `ResponsabilidadeElementosNaoPrevistosAssumida` — obra inacabada, cliente assume posição/dimensão de elementos ainda ausentes | **já existe como cláusula contratual (2.3.2 do modelo real), mas não como evento rastreado** | Termo específico (já previsto no contrato — falta virar registro no sistema) | pode precisar opinar se afeta o projeto dele |
| 11 | `ProjetoExecutivoIniciado` → revisões → `ProjetoExecutivoAprovado` | 11 (11a-e) | Projeto Executivo — **deveria "congelar" a especificação (opinião do Marcelo: deveria ser 1 documento só)** | **compatibilidade depende da participação dele — muitas vezes ausente** |
| 12 | `IncompatibilidadeDetectada` (interface com outros elementos da obra) | dentro de 11 | — | **crítico — decisão de compatibilidade é dele, por natureza** |
| 13 | `RevisaoPEAtrasouFila` — revisão sucessiva de 1 projeto atrasa OUTROS projetos | dentro de 11 | — | — (é um problema de fila/recurso compartilhado, não só deste projeto) |
| 14 | `PedidoImplantado` + `ListaComplementarGerada` (compras/substituições) | 12 | — | — |
| 15 | `AprovacaoFinanceiraIIConcluida` (2ª aprovação, na implantação) | 11d (já existe) | — | — |
| 16 | `ProducaoIniciada` → `ExpedidoPelaFabrica` → `TransportadoAteDeposito` → `EntregueAoCliente` | 13 → 14 → 16 | Nota Fiscal (15, já existe) | — |
| 17 | `MontagemIniciada` (segue plano de montagem + cronograma por ambiente) | 17 | Plano de Montagem — **opinião do Marcelo: deveria vir do mesmo documento único do Projeto Executivo** | — |
| 18 | `FrenteMultiplaAberta` (sinal de caos — indefinição de projeto ou peça faltante/avariada abrindo várias frentes ao mesmo tempo) | dentro de 17 | — | pode ser causa raiz (indefinição de projeto) |
| 19 | `VistoriaAmbienteConcluida` — **por ambiente, não só global** | **hoje 19 é só "Vistoria final" (nível projeto) — a história pede granularidade por ambiente** | — | — |
| 20 | `VistoriaFinalConcluida` + `AssistenciasDeMontagemLevantadas` + `AjustesFinaisFeitos` | 18/19 | — | — |
| 21 | `ProjetoEncerrado` | 20/21 | Aprovação final / Conciliação | — |

### 13.2 Três coisas que a história revelou e que o desenho original não previa

1. **`captacao` não é só um domínio de KPI de mercado — é literalmente o primeiro evento do sistema.**
   O lead entra por canal (showroom, Instagram, indicação de arquiteto) antes de qualquer coisa hoje
   modelada (`Briefing` já é o segundo passo). Isso reforça a decisão do §7, mas com um detalhe novo:
   `captacao` pode precisar nascer **antes** de `relatorios` no roadmap de implementação, já que é fonte
   de dado pros outros dois, não só consumidor.
2. **"Arquiteto informado vs. arquiteto decide" precisa ser um atributo explícito, não implícito.** A
   história mostra que a autoridade do arquiteto muda por momento (ajuste de especificação por orçamento:
   avisar; compatibilidade técnica: decide) e por projeto (às vezes o arquiteto nem existe no projeto).
   Proposta: um campo tipo `Projeto.arquiteto_autoridade` (`nenhum` | `informado` | `decide`), consultado
   pelo `core/events` antes de decidir se um evento vira notificação passiva ou um bloqueio esperando
   resposta.
3. **Vistoria deveria ser granular por ambiente, não só um evento de projeto inteiro no fim.** Hoje a
   etapa 19 é um único "Vistoria final". A história pede `VistoriaAmbienteConcluida` por ambiente,
   agregando pra uma vistoria final — isso é uma mudança de modelagem, não só de nome.

### 13.3 Mecanismo de confirmação/aprovação — proposta

Pedido do Marcelo: cada evento que envolve uma pessoa (cliente, arquiteto, equipe interna) precisa de uma
forma de **oficializar confirmação/aprovação**, possivelmente via app. Proposta: generalizar um padrão que
**já existe parcialmente no sistema hoje**, em vez de inventar do zero —

- **Já existe hoje:** assinatura de contrato (`_contrato_assinado`/`_contrato_totalmente_assinado`),
  reautenticação por senha pra ações gerenciais (ex. editar data prevista), e a cláusula contratual de
  "confirmação por mensagem eletrônica com mecanismo de confirmação de recebimento" (item 1.5.1 do
  contrato real).
- **Proposta:** um primitivo único, `ConfirmacaoEvento(evento_id, pessoa_id, papel, meio, confirmado_em)`,
  reusado por todo `core/events` que precisa de confirmação humana — não um mecanismo por evento. `meio`
  registra COMO foi confirmado (link de app, assinatura, reautenticação) — mantém rastreabilidade uniforme
  em vez de cada evento inventar seu próprio jeito de confirmar, e monta a base pra um app/portal do
  cliente e do arquiteto (hoje eles só recebem PDF/mensagem, sem canal de confirmação estruturado).
- ✅ **DECIDIDO (2026-07-16): WhatsApp como canal inicial de confirmação, condicionado a ser monitorável
  pelo sistema.** Não é WhatsApp "solto" (número pessoal, sem rastro) — a exigência de ser monitorável é
  o que torna a confirmação um dado do sistema, e não só uma conversa perdida num aplicativo de terceiro.
  Detalhamento das implicações concretas dessa decisão: §14. Debate mais amplo sobre por que a
  arquitetura de processos chegou nesse formato: §15.

## 14. Ações concretas de sistema — canal de confirmação via WhatsApp

Esta seção traduz a decisão do §13.3 em requisitos de sistema objetivos — o que precisa existir pra
"WhatsApp monitorável" ser real, não só uma frase.

1. **WhatsApp Business API, não WhatsApp pessoal.** É a única forma de ter webhook de status (enviado/
   entregue/lido) e envio programático — número pessoal de atendente não dá rastreabilidade nenhuma.
2. **Todo evento que exige confirmação gera um link único e de uso único** (token, com expiração),
   enviado por WhatsApp pro destinatário certo (cliente, arquiteto, ou membro da equipe interna).
3. **`ConfirmacaoEvento` (§13.3) grava o ciclo de vida completo da mensagem**, não só a confirmação final:
   `enviado_em`, `entregue_em` (webhook de entrega do WhatsApp), `lido_em` (webhook de leitura, quando
   disponível), `confirmado_em` (clique no link/resposta), e o `id` da mensagem/conversa no WhatsApp pra
   auditoria.
4. **Cadastro precisa de número de WhatsApp validado por pessoa** — cliente, arquiteto e membros da
   equipe interna relevantes (hoje o cadastro de cliente já tem telefone; falta o de arquiteto, que hoje
   não é nem uma entidade própria no sistema — é texto solto em briefing/projeto).
5. **Opt-in/consentimento do destinatário** pra receber mensagem automatizada (LGPD) — registrado uma vez
   no cadastro, não por evento.
6. **Escalonamento por falta de resposta.** Se um evento crítico (ex. compatibilidade que depende do
   arquiteto) não é confirmado em um prazo configurável, o sistema precisa alertar alguém internamente
   (gestor do projeto) em vez de ficar esperando em silêncio — hoje esse silêncio é exatamente o que gera
   atraso não percebido a tempo.
7. **Fallback pra quem não usa/não responde WhatsApp fica fora de escopo por ora** — a decisão foi
   "WhatsApp como solução inicial"; se um canal alternativo (e-mail, portal) for necessário, é extensão
   futura do mesmo primitivo `ConfirmacaoEvento` (o campo `meio` já foi desenhado pra isso, §13.3), não
   uma reformulação.

## 15. O debate de arquitetura de processos — por que chegamos nesse formato

Esta seção registra o raciocínio por trás das decisões de §5 e §13, não as decisões em si — serve pra
quem ler esta spec depois entender o **porquê**, não só o quê.

**A tensão central do negócio, segundo a história do Marcelo:** móveis planejados é um processo longo
(captação → medição → projeto executivo → produção → montagem → vistoria) que atravessa **responsabilidade
de pessoas diferentes** (consultor, projetista, arquiteto, cliente, fábrica, montador) sobre uma realidade
física que muda no meio do caminho (obra inacabada na medição, revisões no projeto executivo, peça
avariada na montagem). O sistema de hoje trata isso como um fluxo de **status de etapa** (`CicloEtapa`,
19 etapas) — suficiente pra saber "onde o projeto está", mas insuficiente pra responder "quem prometeu o
quê, pra quem, e isso foi confirmado?".

**Por que evento explícito em vez de só status de etapa:** status responde "o que é verdade agora";
evento responde "o que aconteceu, quando, e quem confirmou". A história deixou claro que o negócio precisa
das duas coisas — ex.: saber que a etapa está em "Medição" não captura que o cliente **assumiu
responsabilidade formal** por elementos ainda não construídos (item 10 do catálogo, §13.1), que é
justamente o tipo de fato que evita disputa depois.

**Por que um primitivo de confirmação genérico (`ConfirmacaoEvento`) em vez de um mecanismo por evento:**
o sistema já tem 3 formas diferentes de "confirmar algo" (assinatura de contrato, reautenticação de senha,
cláusula de confirmação por e-mail) — cada uma nasceu resolvendo um problema pontual, sem um padrão comum.
Generalizar agora, na concepção do Motor 5.0, evita que o WhatsApp vire a 4ª forma isolada de confirmar
algo; em vez disso, vira a implementação inicial de um padrão único que qualquer evento futuro reusa.

**Por que "arquiteto informado vs. decide" precisa ser dado, não código:** a autoridade do arquiteto não
é uma regra fixa do sistema — muda por projeto (às vezes ele nem existe) e por tipo de decisão (avisar
sobre orçamento vs. decidir compatibilidade técnica). Modelar isso como regra de código forçaria uma
generalização falsa; modelar como atributo consultado em tempo de execução (`Projeto.arquiteto_autoridade`)
deixa a variação real do negócio onde ela pertence — no dado, não na lógica.

**Por que WhatsApp e não portal, nesta primeira fase:** a história mostra que cliente e arquiteto hoje só
recebem PDF/mensagem, sem canal de confirmação estruturado nenhum — o gap não é "falta um portal
sofisticado", é "falta qualquer rastro de confirmação". WhatsApp monitorável fecha esse gap com o menor
custo de adoção possível (ninguém precisa aprender um app novo); um portal dedicado é uma evolução
natural depois que o padrão `ConfirmacaoEvento` já estiver provado em produção, não um pré-requisito.

**O que isso não resolve (e não deveria, ainda):** o catálogo de eventos (§13.1) tem itens que são
lacunas de PROCESSO, não de sistema — ex. "revisão de um projeto atrasa outros projetos na fila" (item 13)
é um problema de capacidade/alocação de equipe, não algo que um evento de confirmação resolve. Esta spec
registra a lacuna; resolvê-la é decisão de gestão operacional, fora do escopo de arquitetura de software.
