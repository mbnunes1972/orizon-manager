# DEV_LOG.md — Diário de Desenvolvimento
## Orizon Manager | Dalmóbile

---

## RESUMO ATUAL
> Atualizado em: 2026-07-04 (sessão 44 — **manutenção de ambiente + política do MCP**. Renomeação do diretório pai `estudo_de_ia → desenvolvimento` (o repo já vinha renomeado `Omie_V3 → Orizon Manager`, commit `c8eb350`); corrigidos os mounts do `.mcp.json` para `E:/2026/desenvolvimento/...` e reconectado o servidor MCP `orizon` (validado com `cobertura`/`ingerir`). **Decisão de processo:** o grafo MCP é **camada de consulta**, não substitui o DEV_LOG nem o git — DEV_LOG segue como fonte narrativa versionada; adicionado o passo de **re-ingestão** ao ritual de fechar frente (docs `CLAUDE.md`/`DEV_RULES.md`). Push da `main` para o `origin` **funciona** (feito nesta sessão) — a antiga pendência de push foi removida. Suíte permanece **395 passed** (sem mudança de código de app). Antes: sessão 43 — padronização da tela de Negociação + "Valor Total do Contrato" editável (cálculo reverso); sessão 42 — lote de ajustes de teste em produção (395 passed))

### [ESTADO] O que está funcionando
- App rodando em `http://167.88.33.121:8765` (servidor DEV) e `http://127.0.0.1:8765` (local)
- Sistema de autenticação completo: login, logout, sessões via cookie
- **12 perfis (`perfis.py`, fonte única):** 10 operacionais — Diretor (50%), Gerente de Vendas (20%), Consultor (10%), Gerente Administrativo/Financeiro, Assistente Logístico, Conferente, Supervisor de Montagem, Assistente Administrativo, Projetista Executivo, Medidor — + 2 **administrativos de tenancy** (F2): `super_admin` e `admin_rede` (gerenciam estrutura, sem capacidade operacional). Permissões centralizadas: `desconto_max`, `ver_parametros`, `autorizar`, `gerir_usuarios`, `aprovar_financeiro`, `registrar_medicao`, `aprovar_medicao_reprovada` + tenancy (`gerir_redes`/`gerir_lojas`/`editar_dados_loja`). Perfil técnico `admin` **aposentado** (via `perfis_v2_2026`). Detalhes em `docs/USUARIOS.md`.
- **Usuários-exemplo (`seed.py`, 1 por perfil):** `pdm2026` (Diretor), `lds2026` (Ger. Vendas), `mds2026` (Consultor), `gaf2026` (Ger. Adm/Fin), `med2026` (Medidor) + demais — **senhas de exemplo, trocar antes de produção**.
- **Painel Admin → Usuários:** CRUD (criar/editar perfil/telefone/ativar-desativar/resetar senha), acesso para Diretor ou Gerente Adm/Financeiro; `nav-07` gateado por `pode_gerir_usuarios`.
- Módulo Clientes completo com ViaCEP, máscaras, CRUD, unicidade
- **Auto-sync Omie:** ao criar cliente, tenta registrar no Omie em background thread; grava `omie_sync_status` (`ok`/`pendente`/`erro`) + `omie_sync_erro` na tabela `clientes`
- Módulo Parceiros completo com tipos, comissão padrão, CRUD
- **Área administrativa (page-07) — console de 3 níveis (F2):** Plataforma (redes + lojas avulsas + admins de rede) → Rede (lojas + diretores) → Loja (dados da loja editáveis incl. testemunhas/CPF · usuários da loja · parceiros), com breadcrumb + drill-down e aterrissagem por perfil. Mantém a fila de sync Omie (clientes pendente/erro, botão "Tentar").
- Projeto vinculado a cliente obrigatório
- **Lista de projetos redesenhada:** tabela com Status | Data | Projeto | Cliente | Último Orçamento
  - Duplo clique ou botão "Abrir →" entra no projeto
  - Filtro de texto simultâneo por nome do projeto, nome do cliente e CPF
  - Filtro multi-seleção de status (OR lógico)
  - Dropdown inline para alterar status direto na lista
- **Pipeline de status por projeto:** `quente` / `morno` / `frio` / `convertido` / `perdido`
  - `convertido` setado automaticamente ao aprovar orçamento (via `bloquear_projeto`)
  - `perdido` grava `perdido_em` automaticamente
  - Botão de status na page-02 (cabeçalho da negociação)
- EP-07 completo: upload, pool, orçamentos, cálculos, desconto individual, limites
- Toggle "Incluir custos adicionais" corrigido: `_incluirCustos` como fonte de verdade global
- **Total Flex (US-14) completo:** `mod_fin/total_flex.py` — juros compostos por dias reais
- **Último orçamento ativo** persistido por projeto em localStorage; ao abrir projeto vai direto para o orçamento que estava ativo na última visita
- **Módulo Ciclo (EP-10):** aba "Ciclo" na page-02 com 20 etapas em 2 colunas; etapas 1-5 auto-completas para projetos com negociação ativa
- **Módulo Contrato (EP-10):** `mod_contrato.py` gera o `.docx` a partir do template por marcadores `modelo_contrato_mapeado.docx` (`_substituir_marcadores` + `_preencher_grade`) → PDF via LibreOffice; **número do contrato** `INS-AAAA-MM-DD-SEQ` no cabeçalho + data; grade de parcelas valor+data (sem ordinal, traços nos vazios); `[TOTAL_CONTRATO]`; 2º signatário = cliente; **empresa/CNPJ, código do número e testemunhas vêm da loja (F3)**, com snapshot por contrato; hash SHA-256 de assinatura
- **Contrato editável protegido:** `.docx` sai somente-leitura com regiões editáveis só nos valores (`permStart/permEnd` + `documentProtection`); botão "Editar contrato" (gate gerencial auditado) abre no Word/LibreOffice e regera o PDF a cada salvamento (watcher `contrato_editar.py`)
- **Status contrato:** `rascunho` → `para_assinatura` → `assinado`; badges CSS dedicados
- **Aprovar Orçamento reformulado:** modal exibe dados do cliente, CPF/endereço de instalação obrigatórios se vazios, condições de pagamento pré-carregadas; salva `valor_negociado` e `forma_pagamento` no orçamento antes de gerar contrato
- **Pós-aprovação:** ao aprovar (etapa 6), a negociação inteira fica **somente-leitura** (`aplicarBloqueioNegociacao`, cobre `#sb-params` + `#page-02`, exceto o `#ciclo-panel`); botões na tela de negociação: **"✍ Assinar Contrato"** + **"✎ Rever Orçamento"** (senha gerencial → `POST /ciclo/desfazer_aprovacao`, libera a edição)
- **Negociação — formas de pagamento por modalidade:** seletores de forma da entrada/parcelas (cartão/aymoré/VP/TF/à vista); modalidade **À Vista** com entrada (valor+data+forma) e liquidação automática; calendário nativo clicável em todos os campos de data; formas levadas ao contrato (`[FORMA_ENTRADA]`, `[TIPO]`)
- **Assinatura do contrato:** bloco de assinaturas normalizado (nome numa linha, CPF/CNPJ embaixo, mesma fonte) via `scripts/organizar_assinaturas.py`/`normalizar_assinaturas.py`
- **UX:** diálogos nativos substituídos por popups estilizados (`confirmarPopup`/`avisoPopup`/`pedirCredenciaisGerente`); `index.html` servido com `Cache-Control: no-cache`
- **Ciclo — gating de sub-etapas:** sub-etapas (`11a`–`11e`, `17a`) desbloqueiam junto com a etapa-mãe (`mod_ciclo.etapa_pai`)
- **Aprovação financeira (etapas 8 e 11d):** exige login+senha de quem tem `aprovar_financeiro` (Diretor ou Ger. Adm/Fin; gerente de vendas não); auditado em `log_acoes_gerenciais`
- **Workflow de Medição (etapas 9 e 10):** etapa 9 = upload da solicitação + senha do medidor; etapa 10 "Medição" = parecer (Aprovado/Reprovado/Parcial+ambientes) + planta promob; **Reprovado em 2 passos** (medidor registra → fica em andamento; Gerente Vendas/Adm-Fin/Diretor anexa doc do cliente + senha → libera). Modelo `Medicao`; arquivos em `PROJETOS/<nome>/medicao/`; guard impede fechar 9/10 pelo toggle genérico
- **Auto-load projetos** ao iniciar app (`DOMContentLoaded → projCarregar()`)
- **LibreOffice gracioso:** `LibreOfficeIndisponivel` salva `.docx` e avança status sem travar o fluxo
- **Parâmetros de negociação — dois escopos (sessões 16 + 20):** os **estruturais** (incluir custos, comissão do arquiteto, fidelidade, custo viagem, brinde, carga tributária) valem para o **projeto inteiro** (`projetos_meta.parametros_json`, compartilhados por todos os orçamentos); **desconto** (global em `orcamentos.margens` + por ambiente em `orcamento_ambientes.desconto_individual_pct`) e **pagamento** são **por orçamento**. Migrações automáticas (`projeto.json`→orçamento e estruturais→projeto)
- **Snapshot completo da negociação (`orcamentos.negociacao_json`):** modalidade, formas, nº de parcelas, entrada e **datas manuais do Total Flex** salvas e reproduzidas ao reabrir; **salvamento garantido ao aprovar** (aprovação bloqueada se falhar; total 0 não sobrescreve) (sessão 17)
- **Trava total pós-assinatura:** a partir da 1ª assinatura, UI esconde Salvar/Parâmetros/Ambientes/Novo Orçamento/Rever (mantém "Assinar Contrato" só enquanto falta a 2ª parte) e backend recusa **403** as mutações (`_contrato_assinado`); na 2ª assinatura, status terminal **"🔒 Fechado"** (sessão 19)
- **Contrato alinhado ao template reestruturado:** `[NOME_EMPRESA]`/`[CNPJ_EMPRESA]` (valores reais), CPFs separados (cliente + 2 testemunhas), cabeçalho robusto a marcadores fragmentados em runs (inclui text-boxes com nº/data) (sessão 18)

### [EP-07] Estado atual do versionamento de orçamentos

**Backend — 100% funcionando:**
- Tabelas: `pool_ambientes`, `orcamentos`, `orcamento_ambientes`
- Criar projeto → Orçamento 1 criado automaticamente ✓
- Upload XML → apenas sistema pool (EP-07); `/ambientes/adicionar` somente para modo legado ✓
- Arquivo salvo no disco SOMENTE após `db.commit()` bem-sucedido (4 endpoints) ✓
- Detecção de duplicata (Sobrescrever / Nova versão) ✓
- Painel pool com status `incluido: true/false` ✓
- Adicionar/remover ambiente com recálculo ✓
- Criar novo orçamento ✓ | Renomear: `PUT /projetos/<nome>/orcamentos/<oid>` ✓
- Cards de projeto: `n_ambientes`/`n_selecionados` lidos do pool via `_enriquecer_projetos_com_pool()` ✓

**Interface — 100% funcionando:**
- Barra de orçamentos com abas, troca de aba, renomear inline ✓
- Painel "Ambientes ▾" com checkbox incluído/disponível ✓
- Upload XML: nenhum arquivo salvo em disco antes da confirmação do usuário ✓
- Tecla Esc fecha qualquer modal ativo sem salvar ✓

**Cálculo de negociação EP-07 — 100% funcionando:**
- Parâmetros (margens, desconto, custos, impostos): compartilhados por projeto ✓
- Base de cálculo: sempre os ambientes do orçamento ativo ✓
- Sequência: `bruto` (gross-up) → `avista` (−desc_global% −desc_individual%) → `final` (÷(1−fin%))
- `neg-subtotal` = bruto gross-up | `neg-avista` = à vista | `neg-total` = com financiamento ✓
- **Desconto individual por ambiente** (EP-07): coluna "Desc.%" editável na tabela ✓
  - Chave em `_descIndividual`: `'ep07_'+pa.id` (não colide com legado por nome de arquivo)
- Modal de parâmetros EP-07: painel de apoio considera desconto individual por ambiente ✓
- Discriminação por ambiente EP-07: usa `_orcAmbientesAtivos` + desconto efetivo combinado ✓
- Cartão/VP: gross-up via `_acrescimoFin` na tabela ✓
- Aymoré/TF: `_ep07DistribuirFinanciado(totalCliente, totalAvista)` ✓
- Painéis de pagamento atualizam ao trocar aba ou alterar parâmetros ✓
- **Limite de desconto total: 35%** sobre bruto original dos XMLs ✓
  - Bloqueia save de parâmetros; reverte desconto individual em tempo real

### [PENDENTE]
- **Sub-projeto 3 — Versionamento de documentos:** novos documentos criam versão; nunca sobrescrevem nem permitem apagar versões anteriores (último item do pedido das sessões 17–19)
- **Plataforma multi-tenant (programa de 4 fases):** o "configurador de lojas" virou um programa `Plataforma → Rede → Loja` com isolamento total. **F1 (fundação de dados) CONCLUÍDA na sessão 21** (tabelas `redes`/`lojas`/`parceiro_lojas`, colunas de tenant, migração `tenancy_v1_2026` + loja seed). **Pendentes:** F2 (perfis `super_admin`/`admin_rede` + CRUD de redes/lojas + UX de abrangência de parceiro); F3 (`mod_contrato.py` puxa dados da loja em vez das constantes `_NOME_EMPRESA`/`_CNPJ_EMPRESA`/`_TESTEMUNHAS` com CPF placeholder + numeração por loja); F4 (isolamento — escopo por loja/rede em todas as queries). Spec/plano em `docs/superpowers/`.
- Módulo Clientes e Parceiros vinculados a orçamentos (planejado)
- **Trocar as senhas de exemplo do `seed.py`** (10 usuários) antes de produção — pelo Painel Admin → Usuários (perfil técnico `admin` foi aposentado)
- Refinar espaçamento visual do bloco de assinaturas no PDF (validado por estrutura, não por render — LibreOffice ausente no dev local)
- **LibreOffice no VPS:** verificar disponibilidade; app funciona sem ele (fallback .docx), mas PDF é o ideal
- **Deploy:** projetos já totalmente assinados em produção podem ficar sem o status "fechado" (o backfill foi feito só no DEV DB) — reassinar não é necessário; setar via banco se quiser consistência
- (Resolvido na sessão 17) `salvarOrcamento()` agora persiste o snapshot completo da negociação

### [DECIDIDO]
- Pool de ambientes permanente por projeto (XMLs nunca deletados)
- Upload EP-07: somente `/pool` (sem `/ambientes/adicionar`) — arquivo salvo após commit
- Pergunta Sobrescrever/Nova versão = apenas quando usuário quer ATUALIZAR o arquivo XML
- Múltiplos orçamentos paralelos, todos editáveis
- Desconto total máximo: 35% de (bruto_original − líquido) / bruto_original
- Banco: SQLite + SQLAlchemy
- Servidor DEV: `167.88.33.121:8765`
- GitHub: `https://github.com/mbnunes1972/orizon-manager`
- Auto-sync Omie ao criar cliente: background thread (não bloqueia HTTP); falha silenciosa → fila no painel admin
- Status "convertido" nunca via dropdown — apenas automático ao aprovar orçamento
- Último orçamento ativo por projeto: localStorage (não backend) — suficiente para uso em loja fixa
- `projetos_meta` (banco): metadados de pipeline; `PROJETOS/*/projeto.json` ainda é a fonte de dados do projeto

### [CONTEXTO] Arquivos e variáveis chave
**Arquivos principais:**
- `main.py` — servidor HTTP, todas as rotas; `_enriquecer_projetos_com_pool()` e `_enriquecer_projetos_com_status()` enriquecem listagens; `do_PATCH` para status; `_tentar_sync_omie()` para sync Omie
- `database.py` — SQLAlchemy: `Usuario`, `Sessao`, `LogAutorizacao`, `LogAcaoGerencial`, `Cliente`, `Parceiro`, `PoolAmbiente`, `Orcamento`, `OrcamentoAmbiente`, **`Projeto`** (projetos_meta), `CicloEtapa`, `Contrato`, `ContratoAssinatura`, **`Medicao`**; migrações de dados em `_run_migracoes` (guard `_tabela_existe`); `Usuario.limite_desconto`/`pode_ver_parametros` delegam a `perfis.py`
- `perfis.py` — **fonte única dos 10 perfis e permissões** (`PERFIS`, `pode/desconto_max/rotulo/existe/slugs`)
- `mod_usuarios.py` — validadores puros do CRUD de usuários
- `mod_ciclo.py` — gating do ciclo (`pode_avancar`, `etapa_pai`, `etapa_anterior`), `ETAPA_NOME` (10 = "Medição"), `ETAPAS_APROVACAO_FINANCEIRA` (8, 11d), `exige_aprovacao_financeira`
- `mod_medicao.py` — `PARECERES` + `validar_parecer`
- `mod_omie.py` — `_listar_projetos()` retorna `cliente_cpf`; `bloquear_projeto()` seta status "convertido"; `_projeto_path()`
- `static/index.html` — frontend SPA completo
- `PROJETOS/*/projeto.json` — dados persistidos de cada projeto (legado; EP-07 usa banco); `PROJETOS/<nome>/medicao/` guarda os arquivos da medição

**Perfis e capacidades (sub-projeto 2/3/4):** ver tabela em `docs/USUARIOS.md`. Capacidades: `autorizar` (desconto: diretor+ger.vendas), `gerir_usuarios` (diretor+adm/fin), `aprovar_financeiro` (diretor+adm/fin), `registrar_medicao` (medidor+diretor), `aprovar_medicao_reprovada` (vendas+adm/fin+diretor).

**Tabelas/rotas novas (sub-projetos 2–4):**
- `medicoes` (1 por projeto); migração de dados `perfis_v2_2026` (gerente→gerente_vendas, admin→diretor)
- `GET/POST/PATCH /api/admin/usuarios` (gate `gerir_usuarios`)
- `POST /api/projetos/<nome>/medicao/{solicitacao,parecer,decisao-reprovado}` + `GET .../medicao` + `GET .../medicao/arquivo/<tipo>`
- `PATCH /ciclo/<codigo>`: gate financeiro (8/11d) e guard de medição (9/10)

**Tabelas novas (sessão 6):**
- `projetos_meta` — `nome_safe` PK, `status`, `status_at`, `perdido_em`
- Campos novos em `clientes` — `omie_sync_status`, `omie_sync_erro`, `omie_sync_at`

**Rotas novas (sessão 6):**
- `GET /api/admin/omie-sync` — lista clientes com sync pendente/erro (role admin)
- `POST /api/admin/omie-sync/<id>/retry` — reprocessa sync de um cliente (role admin)
- `PATCH /api/projetos/<nome>/status` — altera status do projeto (quente/morno/frio/perdido)

**Tabelas novas (sessão 7):**
- `ciclo_etapas` — `projeto`, `numero`, `status`, `concluido_em`, `concluido_por`
- `contratos` — `projeto`, `orcamento_id`, `status`, `arquivo_path`, `arquivo_tipo`, `gerado_em`
- `contrato_assinaturas` — `contrato_id`, `tipo` (cliente/empresa), `hash`, `assinado_em`, `assinado_por`
- Campo novo em `orcamentos` — `valor_negociado`, `forma_pagamento`

**Rotas novas (sessão 7):**
- `GET /api/projetos/<nome>/ciclo` — retorna 20 etapas (auto-cria 1-5 se negociação presente)
- `PATCH /api/projetos/<nome>/ciclo_etapas` — marca etapa como concluída/pendente
- `POST /api/projetos/<nome>/contrato` — gera contrato (PDF ou .docx fallback)
- `PATCH /api/projetos/<nome>/contrato` — atualiza status do contrato
- `POST /api/projetos/<nome>/contrato/assinar` — registra assinatura com hash SHA-256
- `GET /api/projetos/<nome>/contrato` — retorna metadados do contrato (inclui `arquivo_tipo`)
- `GET /api/projetos/<nome>/contrato/pdf` — serve o arquivo (PDF ou .docx com Content-Type correto)
- `PATCH /api/orcamentos/<id>/valor` — salva `valor_negociado` e `forma_pagamento`
- `POST /api/projetos/<nome>/ciclo/desfazer_aprovacao` — valida gerente e reseta etapas 6+7

**Arquivos novos (sessão 7):**
- `mod_contrato.py` — geração de contrato via docxtpl + LibreOffice; `LibreOfficeIndisponivel`
- `config/contrato_template.docx` — template com 13 variáveis Jinja2
- `scripts/configurar_template_contrato.py` — insere variáveis no .docx base

**Variáveis JS chave EP-07:**
- `_orcamentos` — lista de orçamentos do projeto ativo
- `_orcamentoAtivoId` — ID do orçamento sendo visualizado (persistido em `localStorage['lastOrc_<nome_safe>']`)
- `_orcAmbientesAtivos` — ambientes do orçamento ativo (null = modo legado)
- `_descIndividual` — `{ chave: pct }` desconto individual; EP-07 usa `'ep07_'+pa.id`
- `_margemAtual` — desconto total % atualizado por `mpAtualizarApoio()`; base do limite 35%
- `_LIMITE_DESC_TOTAL` — constante `35`
- `_projListaBase` — cache da lista de projetos carregada
- `_projetoStatusAtual` — status do projeto ativo na page-02
- `carregarOrcamentos()` — busca GET /projetos/<nome>/orcamentos; seleciona por localStorage → updated_at → ordem
- `ativarOrcamento(id)` — troca aba, grava em localStorage, chama GET /orcamentos/<id>/ambientes
- `abrirPainelPool()` — abre modal com GET /projetos/<nome>/pool?orcamento_id=<oid>
- `uploadXmls()` — em modo EP-07 usa exclusivamente POST /projetos/<nome>/pool

---

## HISTÓRICO

### Sessão 2026-06-23 (sessão 26 — Motor de Negociação em MODO SOMBRA — Task 8: golden-master)
**Processo:** Task 8 (última) do plano de refatoração do motor de negociação (`feat/motor-negociacao-sombra`). Golden-master: fotografia dos valores HOJE × NOVO para baseline de validação.

**Motor e trava:**
- **`mod_negociacao`** em **MODO SOMBRA**: motor de negociação calcula os derivados (`vavo`, `val_liq`, `markup`, `val_cont`, `desc_tot_pct`) e os grava nas colunas sombra — sem alterar `valor_total`/`valor_liquido` (legado intacto).
- **`mod_qualidade_xml`** — trava de qualidade em modo sombra: bloqueia upload de XML com itens sem acréscimo/markup abaixo do limiar, com mecanismo de override gerencial (Tasks 2/4/5).
- Colunas aditivas (Tasks 3/6): `vbvo`, `cfo`, `vbno`, `vavo`, `cust_ad`, `val_liq`, `desc_tot_pct`, `markup`, `cust_fin`, `val_cont`, `prov_imp` — adicionadas via `_migrar_colunas()`, sem remover nada.
- **Tag de rollback:** `pre-refator-negociacao` — restaura estado anterior a qualquer mudança destrutiva.

**Golden-master:**
- Script: `scripts/snapshot_negociacao.py` — lê todos os `Orcamento` e grava `tests/golden/negociacao_baseline.json` com `{id, projeto, ordem, hoje:{valor_total, valor_liquido}, novo:{vavo, val_liq, markup, val_cont, desc_tot_pct}}`.
- Baseline gerado: **20 orçamentos** — campos `novo` zerados (motor sombra ainda não rodou o `save` de validação nos dados reais; será re-gerado após o primeiro save na interface).
- Arquivo commitado em `tests/golden/negociacao_baseline.json` para servir de referência na fase de validação.

**O que fica fora desta fase (após validação na interface):**
- **Fase B (cutover):** contrato/UI passam a usar os valores novos; integração plena `Cust_Fin` via `mod_fin.calcular(...)`; mover params duplicados de `orcamentos.margens` para o projeto.
- **Fase C (limpeza):** aposentar `orcamentos.valor_liquido`/bloco `margens`; remover `custo_financeiro_pct` duplicado de `mod_margens`.
- Comportamento atual (legado) permanece intacto durante toda a Fase A.

**Arquivos criados/modificados nesta sessão:**
- `scripts/snapshot_negociacao.py` (novo)
- `tests/golden/negociacao_baseline.json` (novo — baseline de 20 orçamentos)
- `DEV_LOG.md` (esta entrada)

---

### Sessão 2026-06-21 (sessão 24 — F4: isolamento operacional) — **fecha o multi-tenant**
**Processo:** pipeline superpowers (brainstorm → spec → plano → subagentes com revisão de **segurança** + qualidade por task → verificação). Spec/plano em `docs/superpowers/specs/2026-06-21-multitenant-f4-isolamento-design.md` e `docs/superpowers/plans/2026-06-21-multitenant-f4-isolamento.md`. Branch `feat/multitenant-f4-isolamento` (16 commits).

**Origem:** 4ª e última fase. F1 (schema) → F2 (UI/API de tenancy, escopo só nas telas admin) → F3 (contrato puxa da loja) → **F4 aplica escopo por loja em TODAS as queries operacionais**, que eram globais.

**Decisões do brainstorm:** (1) cada loja vê só o seu; super_admin/admin_rede **sem acesso operacional**; (2) **tudo numa fase** (carimbo na criação + filtro nas listagens + checagem de dono anti-IDOR); (3) registro de outra loja por id/link → **404** (não vaza existência).

**Entregue:**
- **`mod_tenancy.escopo_operacional(ator)` (puro):** `(loja_id, None)` p/ usuário de loja; `(None, motivo)` p/ perfil administrativo → rota traduz em **403**.
- **Helpers em `main.py` (testáveis por stub):** `_obj_da_loja(db, Model, pk, loja_id)` e `_projeto_da_loja(db, nome_safe, loja_id)` (delega no primeiro) → objeto se for da loja, senão `None` (→ 404); `_filtrar_projetos_por_loja` (lista de projetos vem do storage → cruza com `projetos_meta.loja_id`); `_parceiro_visivel_loja` (abrangência loja/rede).
- **~30 endpoints escopados** (clientes, projetos, orçamentos, contratos, pool, medição, ciclo, parceiros): guard 401+403 + checagem de dono (`_obj_da_loja`/`_projeto_da_loja`) **antes** de qualquer query que revele estado; **criação carimba** `loja_id` (cliente/projeto/orçamento; contrato já vinha da F3).
- **`database.py`:** `_backfill_loja_operacional` (idempotente, NULL→loja 1) chamado no `_migrar_dados`; `upsert_projeto_status` passa a carimbar `loja_seed_id` ao criar projeto.
- **Contrato/editar (gate gerencial):** escopo via `autorizador.loja_id` (não a sessão).

**Segurança — IDORs achados e corrigidos na revisão por subagentes** (todos fechados na branch): `POST /clientes/<id>/briefing` (escrita cross-loja) + vazamento de cliente na colisão de CPF; ordem do `POST /parametros` (loja antes do estado); `GET /projetos/<nome>/briefing` (sem auth); **`PUT /orcamentos/<id>/descontos` e `PATCH /orcamentos/<id>/valor` (sem auth nenhuma)**; "Orçamento 1" auto-criado com `loja_id` NULL (quebra funcional); `_origem` (cópia de margens) cross-loja; **`POST /projetos/<nome>/ambientes/...` (sem auth)** e `POST /projetos/<nome>/briefing` (sem checagem de sessão).

**Verificação:** pytest **201** verde (novos em `tests/test_isolamento_f4.py`: `escopo_operacional`, `_obj_da_loja`/`_projeto_da_loja` com stub, backfill idempotente). Cada task passou por revisão de **segurança** + qualidade (subagentes). **Pendente:** smoke com **2 lojas** no ambiente do usuário — checklist + mapa de triagem em `docs/processos/SMOKE_F4_ISOLAMENTO.md`. Com uma única loja (hoje), o comportamento visível é idêntico ao de antes.

**Achado pré-existente (fora da F4, decisão do usuário):** `contrato_editar.py:validar_gerencial` usa nomes de perfil antigos (`"gerente"`/`"admin"`) → hoje só `diretor` edita contrato. Política a definir.

### Sessão 2026-06-21 (sessão 23 — F3: contrato puxa da loja)
**Processo:** pipeline superpowers (brainstorm → spec → plano → subagentes com revisão em duas etapas por task → verificação). Spec/plano em `docs/superpowers/specs/2026-06-21-multitenant-f3-contrato-loja-design.md` e `docs/superpowers/plans/2026-06-21-multitenant-f3-contrato-loja.md`. Branch `feat/multitenant-f3-contrato-loja`.

**Origem:** 3ª das 4 fases do multi-tenant. A F2 (sessão 22) tornou os dados da loja editáveis (incl. testemunhas/CPF); a F3 faz o contrato **consumir** esses dados em vez das constantes hard-coded. Não toca isolamento operacional (F4).

**Decisões do brainstorm:** (1) **snapshot** dos dados da loja no contrato; (2) loja incompleta → **avisar mas deixar gerar** (não bloqueia, ao contrário do cadastro do cliente); (3) **remover as constantes** — loja vira fonte única (sem fallback); (4) **refoto a cada geração**, congela na assinatura (pela trava pós-assinatura existente). Telefone/email/endereço da loja viraram **obrigatórios no cadastro** (validação).

**Entregue:**
- **`mod_contrato.py` (puro):** removidas as constantes `_NOME_EMPRESA`/`_CNPJ_EMPRESA`/`_CODIGO_LOJA`/`_TELEFONE_LOJA`/`_EMAIL_LOJA`/`_TESTEMUNHAS`. `construir_contexto(cliente, usuario, forma, loja=None)` injeta a loja no `ctx`; `_montar_mapping` lê empresa/testemunhas de `ctx["loja"]`; `gerar_num_contrato(existing, loja_codigo, …)` com código **obrigatório**. Novo validador puro `validar_loja_para_contrato` (campos obrigatórios; CPF placeholder sem dígito conta como faltando; `complemento` opcional).
- **`database.py`:** coluna `contratos.loja_snapshot_json` (TEXT, nullable) no model + `_migrar_colunas` (idempotente).
- **`main.py`:** helper `_loja_dict_para_contrato(db, loja_id)`; nos **2 pontos de geração** (aprovação + regeração) resolve a loja do consultor (`_ator_dict`), valida → responde `precisa_confirmar_loja`/`campos_loja_faltando` (HTTP 400) quando incompleta e sem `confirmar_loja_incompleta`, grava `loja_snapshot_json`, fixa `contrato.loja_id` na 1ª geração e passa a loja para `construir_contexto`/`gerar_num_contrato`.
- **Frontend (`static/index.html`):** **ambos** os fluxos que geram/regeneram o contrato tratam `precisa_confirmar_loja` com diálogo "Gerar assim? / Cancelar" e re-chamam com a flag — `gerarContrato()` (aprovação, reaproveitando o signatário já coletado) e `salvarAdendo()` (PATCH de regeração; achado na revisão final e corrigido).

**Verificação:** pytest **195** verde (novos: `tests/test_contrato_loja.py` — validador da loja, helper `_loja_dict_para_contrato` com db stub, migração da coluna idempotente; + `tests/test_contrato.py` atualizado para a loja como fonte). Cada task passou por revisão de **spec** + **qualidade** (subagentes). **Pendente:** smoke de API/Playwright no ambiente do usuário (loja seed com CPF de testemunha placeholder → deve disparar o diálogo "Gerar assim?"); preencher os CPFs reais em "Dados da loja" e revalidar. **Checklist de verificação + mapa de triagem (sintoma→local) + inspeção do snapshot em `docs/processos/SMOKE_F3_CONTRATO_LOJA.md`** (para acelerar o diagnóstico se algum bug surgir).

**Edge conhecido (registrado p/ revisão final):** loja **sem código** + geração confirmada → `num_contrato` sai com prefixo vazio (`-AAAA-…`); ocorre só se a loja não tiver código (validação avisa). Mantido o comportamento leniente por coerência com a Decisão 2.

### Sessão 2026-06-21 (sessão 22 — F2: perfis e CRUD de tenancy)
**Processo:** pipeline superpowers (brainstorm → spec → plano → subagentes com revisão em duas etapas por task → verificação → merge). Spec/plano em `docs/superpowers/specs/2026-06-21-multitenant-f2-tenancy-design.md` e `docs/superpowers/plans/2026-06-21-multitenant-f2-tenancy.md`.

**Origem:** 2ª das 4 fases do programa multi-tenant. A F1 (sessão 21) criou o schema; a F2 **expõe a tenancy na UI/API**, sem tocar nenhuma query operacional (isolamento real é a F4).

**Entregue:**
- **Perfis novos (`perfis.py`) — puramente administrativos (operacional 0/False):** `super_admin` ("Administrador da Plataforma", escopo tudo) e `admin_rede` ("Administrador de Rede", escopo sua rede). Capacidades `gerir_redes` (só super_admin), `gerir_lojas` (super_admin+admin_rede), `editar_dados_loja` (+ **Diretor**, só a própria loja). Sessão (`auth._usuario_dict`) passa a expor `loja_id`/`rede_id` + flags `pode_gerir_redes`/`pode_gerir_lojas`/`pode_editar_dados_loja`.
- **`mod_tenancy.py` (novo, puro/testável):** validadores (`validar_rede`, `validar_loja` código 3-letras único, `validar_abrangencia_parceiro`) + política de escopo/atribuição (`pode_ver_rede`, `pode_ver_loja`, `pode_editar_dados_loja`, `atribuir_tenant_usuario`, `_eh_super_admin`/`_eh_admin_rede`). As rotas em `main.py` ficam finas: validam, chamam as funções puras, aplicam `WHERE` por tenant e serializam.
- **Bootstrap:** migração de dados `tenancy_v2_2026` (idempotente, `schema_migrations`) cria o super_admin `sad2026` quando nenhum existe; `seed.py` também o cria via ORM. Hashing de senha unificado em `database._hash_senha`.
- **Endpoints (`main.py`, todos sob `/api/admin/`, com gate + escopo):** `redes` (GET/POST/PATCH, gate `gerir_redes`); `lojas` (GET/POST/PATCH, escopo por rede/loja, `?rede_id=avulsas|N`, edição dos **dados da loja** incl. testemunhas/CPF — destrava a F3); `usuarios` estendido (atribuição de `loja_id`/`rede_id` conforme quem cria + escopo na listagem); parceiros com **abrangência** `'loja'`(M:N em `parceiro_lojas`, comissão por loja) / `'rede'` — **Diretor cria ambos** (rede = a da própria loja).
- **Frontend (`static/index.html`):** page-07 virou **console de 3 níveis** (Plataforma → Rede → Loja) com breadcrumb + drill-down; aterrissagem por perfil; aba "Dados da loja" (form que faz PATCH) e "Usuários da loja" (CRUD de sempre, preservado); UX de abrangência no modal de parceiro (com pré-preenchimento ao editar, p/ não resetar 'rede'→'loja').

**Verificação:** pytest **186** verde (19 novos: perfis, validadores, escopo/atribuição, bootstrap+idempotência). **Smoke de API ao vivo (servidor real, super_admin+diretor):** 19 checagens — atribuição de tenant, escopo do diretor (lista/cria só na própria loja; 403 em `/api/admin/redes`), abrangência loja+rede, cadastro legado intacto, e **parceiro órfão não persiste** quando a abrangência falha (create atômico via `flush`). **Smoke de runtime do frontend via jsdom** (DOM real + backend ao vivo): 16 checagens, **0 erros de JS** — super_admin aterrissa no Nível 1, diretor no Nível 3 (form da loja preenchido + lista de usuários), modal de abrangência e edit-prefill OK. **Pendente:** Playwright em Chromium não rodou (faltam libs de sistema `libnspr4`/`libnss3` no WSL, sem sudo) — coberto funcionalmente pelo jsdom; rodar o pass visual no ambiente do usuário.

**Fixes em revisão (achados e corrigidos durante o ciclo):** import local `urlparse` sombreava o do módulo e quebrava **todo** o `do_GET` (corrigido p/ `parse_qs` só); guard `.isdigit()` no `?rede_id=` (evita 500 por `int()` em input livre); marcador da migração `tenancy_v2` movido p/ dentro do guard de colunas (não marcar aplicada sem agir); **create de parceiro atômico** (`flush`+commit único) p/ não deixar órfão; prefetch das lojas no escopo de usuários (evita N+1); diretor pode parceiro de abrangência rede da própria loja.

### Sessão 2026-06-20 (sessão 21 — F1: fundação da plataforma multi-tenant)
**Processo:** pipeline superpowers (brainstorm → spec → plano → subagentes com revisão em duas etapas por task → verificação → merge). Spec/plano em `docs/superpowers/specs/2026-06-20-multitenant-f1-fundacao-design.md` e `docs/superpowers/plans/2026-06-20-multitenant-f1-fundacao.md`.

**Origem:** o pedido "configurador de lojas" (tirar nome/CNPJ/testemunhas das constantes de `mod_contrato.py`) foi explorado e revelou a intenção de uma **plataforma multi-tenant com isolamento total** — `Plataforma → Rede → Loja`, com lojas independentes (avulsas) e escalável para muitas redes/lojas; cada loja tem seus usuários. Decomposto em **4 fases**, cada uma com seu ciclo: **F1 fundação de dados** (esta) · F2 perfis + CRUD de redes/lojas · F3 contrato puxa da loja · F4 isolamento (escopo por loja em todas as queries).

**F1 — puramente aditiva (zero mudança de comportamento):**
- **Models novos (`database.py`):** `Rede` (`redes`), `Loja` (`lojas`, com `rede_id` nullable = avulsa, `codigo` 3-letras UNIQUE p/ numeração do contrato, endereço, 2 testemunhas), `ParceiroLoja` (`parceiro_lojas` — vínculo M:N parceiro×loja com `comissao_padrao_pct` por loja).
- **Modelo de parceiros M:N:** parceiro pertence a uma **rede** (ou loja avulsa); `abrangencia` `'loja'`|`'rede'`; mesma pessoa pode ser parceira de 2 lojas (1 cadastro, N vínculos); parceiro "global da rede" via `abrangencia='rede'`. Fronteira de isolamento = rede/loja-avulsa.
- **Colunas de tenant:** `loja_id` em `usuarios`/`clientes`/`projetos_meta`/`orcamentos`/`contratos`; `rede_id` em `usuarios`; `rede_id`+`abrangencia` em `parceiros`. Tabelas-filhas (briefings/medicoes/pool/etc.) herdam pelo pai — não recebem `loja_id`.
- **Migração:** colunas via `_migrar_colunas` (DBs existentes); dados via `_run_migracoes` → `tenancy_v1_2026` (idempotente, em `schema_migrations`): cria a **loja seed** a partir das constantes do contrato (INSPIRIUM, `codigo=INS`; CPFs de testemunha ainda placeholder → corrigir na F2) e faz backfill de `loja_id` em todos os registros + um vínculo `parceiro_lojas` por parceiro.
- **`seed.py`:** `criar_usuarios_seed(db, usuarios, loja_id)` (puro/testável) vincula os 10 usuários-exemplo à loja seed; helper `loja_seed_id(db)`.

**Verificação:** pytest **167** verde (10 novos: schema, colunas, migração+idempotência+não-sobrescreve-abrangência, seed). Smoke do `init_db()` completo sobre uma **cópia do `orizon.db` real**: loja seed criada e **0 registros com `loja_id` NULL** (11 usuários, 6 clientes, 14 projetos, 20 orçamentos, 13 contratos). Sem mudança de UI/rotas/contrato (confirmado por revisão de spec em cada task) — regressão por construção. **Pendente:** regressão Playwright ao vivo não rodada (evitar mutar o DEV DB antes do merge; F1 não tem superfície de UI).

**Fixes em revisão:** guard `_tabela_existe("parceiro_lojas")` na migração (robustez a DBs parciais); restaurado o contador "já existia(m)" no resumo do `seed.py`.

**Infra de desenvolvimento (mesmo dia):** configurado **acesso remoto pelo celular** (Termius/SSH) para tocar/testar as próximas fases com sessão persistente — **Tailscale** (PC `legion-marcelo` = `100.95.134.72`) + **OpenSSH do Windows** (user `mbn19`, porta 22) + **WSL2 Ubuntu** + **tmux**. Fluxo: `ssh mbn19@100.95.134.72` → `wsl` → `tmux attach`. Detalhes na memória `trabalho-mobile-termius`. **Próximo passo de produto:** F2 (perfis `super_admin`/`admin_rede` + CRUD de redes/lojas + UX de abrangência de parceiro).

### Sessão 2026-06-20 (sessão 20 — parâmetros estruturais por projeto)
**Processo:** pipeline superpowers (brainstorm → spec → plano → subagentes com revisão em duas etapas por task → verificação API real + Playwright → merge). Spec/plano em `docs/superpowers/`. Refina a sessão 16 (que deixara TODAS as margens por orçamento).

**Correção pedida:** os parâmetros **estruturais** da negociação valem para o projeto inteiro — mexeu num orçamento, vale para todos. Só desconto e pagamento são por orçamento.

**Modelo:**
- **Por projeto** → **`projetos_meta.parametros_json`** (JSON, 10 chaves): `incluir_custos`, `comissao_arq_pct`/`ativa`, `fidelidade_pct`/`ativa`, `fora_da_sede`/`custo_viagem`, `brinde`/`brinde_ativo`, `carga_trib`.
- **Por orçamento** → `orcamentos.margens` (só `desconto_pct` + `custo_financeiro_pct` derivado), `orcamento_ambientes.desconto_individual_pct`, e `orcamentos.negociacao_json` (pagamento).

**Backend:** `PARAMETROS_DEFAULT` + `merge_parametros` (em `mod_orcamento_params.py`); `GET`/`POST /api/projetos/<nome>/parametros` (com gate bloqueio/assinatura); `GET /orcamentos/<id>/ambientes` passou a devolver `parametros` do projeto; `POST /api/orcamentos/<id>/margens` grava **só** `desconto_pct` (ignora estruturais); migração idempotente `migrar_parametros_para_projeto` (copia estruturais de um orçamento → projeto) no startup. `merge_margens` deixou de ser usado em `main.py`.

**Frontend:** ao ativar orçamento, `projetoAtivo.margens` é montado como `parâmetros do projeto + desconto do orçamento` (`Object.assign`); o modal de parâmetros salva estruturais no projeto e desconto no orçamento.

**Verificação:** pytest **155** verde (coluna, módulo puro, migração). API real: **11/11** — salvar parâmetros reflete em todos os orçamentos; desconto isolado por orçamento; estruturais não vazam para o orçamento. Playwright: estruturais compartilhados / desconto isolado entre 2 orçamentos, 0 erros de console.

**Fix de follow-up (mesmo dia):** os parâmetros estruturais sumiam ao reabrir o modal. Causa: `salvarDescontoAutomatico` fazia `projetoAtivo.margens = d.margens` e o endpoint `/margens` (pós-refactor) devolve só `desconto_pct` — apagando os estruturais da memória; e o save do modal não atualizava `projetoAtivo.margens` com os estruturais recém-salvos. Correção: `salvarDescontoAutomatico` passa a atualizar **só** `desconto_pct` (preserva os estruturais); o save do modal atualiza `projetoAtivo.margens` com os `parametros` salvos. Verificado por Playwright (reabrir modal e blur do desconto preservam os estruturais).

**Correção pontual (mesmo dia):** painel de **Cartão** ganhou o campo **"Data da entrada"** (`cc-entrada-data`) na linha de Entrada/Bandeira; o `_planoPagamento.entrada_data` do cartão (antes `''` fixo) passa a lê-lo, refletindo no contrato `[DATA_ENTRADA]`; incluído no snapshot (`negociacao_json`) para persistir por orçamento. Verificado por Playwright.

**Correção pontual (mesmo dia):** **"Data da entrada" em todas as modalidades com entrada** — adicionado também a **Aymoré** (`ay-entrada-data`), **Venda Programada** (`vp-entrada-data`) e **Total Flex** (`tf-entrada-data`); antes essas usavam a *Data do Contrato* como data de entrada. Cada `_planoPagamento.entrada_data` lê o campo novo com fallback para a data do contrato; pré-preenchido com hoje ao abrir o painel; incluído no `negociacao_json`. (Cartão e À vista já tinham.) Tudo reflete no contrato (valor/data/forma da entrada + grade do resíduo). Verificado por Playwright (3/3 modalidades).

**Correção pontual (mesmo dia):** **contrato do cartão** — a grade passa a mostrar **cada parcela na sua posição com o valor e SEM data** (antes despejava o `texto_cartao` na 1ª célula); o campo `[NUM_PARCELAS]` mostra o **número de parcelas** quando parcelado e **"à vista"** quando 1x. Frontend: `_planoPagamento.parcelas` do cartão passa a conter as N parcelas (`{valor, data:''}`). Backend: `_preencher_grade` (ramo cartão) e `_parse_pagamento` (display "à vista"/número; datas vazias do cartão). Verificado: geração de contrato 12x (valores sem data, "12") e 1x ("à vista") + Playwright. pytest **157**.

### Sessão 2026-06-19 (sessão 19 — trava total pós-assinatura + status "Fechado")
**Processo:** pipeline superpowers (brainstorm → spec → plano → subagentes com revisão em duas etapas por task → verificação API real + Playwright → merge). Segundo de 3 sub-projetos. Spec/plano em `docs/superpowers/`.

**Comportamento:** a partir da **1ª assinatura** do contrato (qualquer parte), a negociação/projeto fica **congelada**: o frontend esconde Salvar/Parâmetros/Ambientes/Novo Ambiente/Novo Orçamento e o "Rever Orçamento" (mantém **"Assinar Contrato"** para a 2ª parte); o backend **recusa (403)** as mutações. Quando **ambas** as partes assinam, o projeto recebe o status terminal **"🔒 Fechado"** (automático, não editável — como "convertido").

**Backend (`main.py`):**
- **`_contrato_assinado(nome_safe, db)`** — fonte única (status assinado_loja/cliente/assinado/vigente OU `len(assinaturas)>0`). Exposto em `GET /api/projetos/<nome>/ciclo` como `contrato_assinado`.
- **Guard 403** em: novo orçamento, pool (+ sobrescrever/nova_versão/criar_forçado), adicionar/remover/renomear ambiente, renomear orçamento, PATCH valor, margens, descontos, PATCH status. (Guard de assinatura colocado **antes** do briefing no novo orçamento p/ 403 consistente.)
- **Status "fechado"** setado por `upsert_projeto_status` na 2ª assinatura — **após** o `db.commit()` (corrige bug de lock do SQLite que silenciava o update). Projetos já assinados antigos: backfill manual no DEV DB.

**Frontend (`static/index.html`):**
- `_contratoAssinado` vindo do GET ciclo; `atualizarBotoesAprovacao` esconde a edição quando assinado (caminho não-assinado intacto). Status "🔒 Fechado": label/badge/CSS/filtro + dropdown travado (espelha "convertido", nunca setável manualmente).

**Verificação:** pytest **145** verde (helper `_contrato_assinado` + 4 testes). API real: 403 confirmado em valor/margens/descontos/status/novo-orçamento quando assinado; **status vira "fechado"** ao assinar as 2 partes (sem erro de lock no log). Playwright: botões de edição escondidos, "Assinar Contrato" presente, 0 erros de console.

**Fix de follow-up (mesmo dia):** botão "Assinar Contrato" persistia após a 2ª assinatura. Causa: o ramo assinado de `atualizarBotoesAprovacao` sempre recriava o botão. Correção: novo helper `_contrato_totalmente_assinado` + flag `contrato_totalmente_assinado` no GET ciclo; o botão "Assinar Contrato" só aparece na assinatura **parcial** e some quando ambas as partes assinam; "Rever Orçamento" some em qualquer assinatura (já era o caso — o relato de "Rever ainda aparecia" era **cache** do `index.html` antigo). Verificado por Playwright (parcial: rever ausente/assinar presente; total: ambos ausentes). pytest 149.

**Pendente:** sub-projeto 3 (versionamento de documentos). Configurador de lojas (do sub-projeto do contrato).

### Sessão 2026-06-19 (sessão 18 — alinhar contrato ao template reestruturado)
**Processo:** pipeline superpowers (intercalado durante o sub-projeto 2, a pedido do usuário). Spec/plano em `docs/superpowers/`. Disparado por uma edição do `modelo_contrato_mapeado.docx` no Word (reestruturação do bloco de assinatura), que quebrou 6 testes de contrato.

**Diagnóstico (corrigido após ler o motor):** o motor do corpo (`_subst_paragrafo`) já opera no texto concatenado do parágrafo → já é robusto a marcadores fragmentados em runs. As 6 falhas eram **(a) mapeamentos faltando** e **(b) 2 testes presos à estrutura antiga** ("CPF/CNPJ:" inline).

**Mudanças:**
- **`mod_contrato.py`:** constantes `_NOME_EMPRESA`/`_CNPJ_EMPRESA` com os **valores reais já presentes no template** (`INSPIRIUM MOVEIS PLANEJADOS E DECORACAO LTDA`, CNPJ `19.152.134/0001-56`; TODO: configurador de lojas). `_montar_mapping` ganhou `NOME_EMPRESA`, `CNPJ_EMPRESA`, `CPF_CLIENTE`, `CPF_TESTEMUNHA_1`, `CPF_TESTEMUNHA_2`.
- **Cabeçalho robusto:** o ramo de headers de `_substituir_marcadores` passou a reusar `_subst_paragrafo` (robusto a runs) em parágrafos, tabelas **e text-boxes** do cabeçalho — descobriu-se que `[Num_Contrato]`/`[Data_contrato]` vivem em **caixas de texto** (`wps:txbx`), não em parágrafos comuns.
- **Testes:** 2 atualizados ao novo bloco (nome e CPF em marcadores separados); +3 testes novos (mapping, cabeçalho fragmentado).
- **Template:** o `.docx` reestruturado foi versionado.

**Verificação:** pytest **141** verde. Geração com dados reais (via `preencher_contrato`): zero marcador remanescente; empresa+CNPJ, cliente+CPF, testemunhas e número/data no cabeçalho corretos.

**Pendente:** **configurador de lojas** (origem real de nome/CNPJ/testemunhas/telefone) — projeto futuro; por ora os valores são constantes. Retomar o **sub-projeto 2** (trava pós-assinatura) — a Task 1 dele já está commitada em `feat/trava-pos-assinatura`.

### Sessão 2026-06-19 (sessão 17 — snapshot completo da negociação por orçamento)
**Processo:** pipeline superpowers (brainstorm → spec → plano → subagentes com revisão em duas etapas por task → revisão holística → verificação API real + Playwright → merge). Primeiro de 3 sub-projetos decompostos de um pedido maior (1) snapshot da negociação · 2) trava total pós-assinatura · 3) versionamento de documentos). Spec/plano em `docs/superpowers/`.

**Bug relatado:** ao salvar/aprovar, a última negociação de forma de pagamento/parcelamento se perdia. Causa: o plano calculado era salvo em `forma_pagamento`, mas ao reabrir nada restaurava a modalidade, formas, nº de parcelas, entrada e — no Total Flex — as **datas preenchidas manualmente** (limitação anotada na sessão 10).

**Backend:**
- **`orcamentos.negociacao_json`** (coluna JSON nova): snapshot das **entradas** da negociação (separado do `forma_pagamento`, que segue sendo o plano calculado p/ o contrato).
- `PATCH /orcamentos/<id>/valor` grava `negociacao_json` (campo opcional; omitir não apaga); `GET /orcamentos/<id>/ambientes` devolve `negociacao` (parseado).

**Frontend (`static/index.html`):**
- **`_capturarNegociacao()`** (mapa de campos por modalidade) captura modalidade, formas, nº de parcelas, entrada, e as listas de datas/valores manuais (TF: `tf_datas`+`tf_valores`; VP: `vp_datas`). A **taxa TF** (campo mascarado/gated por gerente) é intencionalmente fora do snapshot.
- **`_restaurarNegociacao()`** reinjeta as entradas após `carregarModalidades()` (ordem: modalidade → parcelas → campos → datas/valores → recálculo) e reproduz o plano com as datas salvas.
- **Garantia ao aprovar:** `salvarValorNegociado()` retorna `{ok,erro}`; `aprovarOrcamento`/`salvarOrcamento`/`abrirAprovacaoComDados` **abortam** se o salvamento falhar; salvamento com total 0 é bloqueado (evita sobrescrever valor bom com 0).
- **Race condition do Total Flex** corrigida: `atualizarTF()` ganhou contador de geração `_tfGen` (descarta respostas `inicializar`/`recalcular` obsoletas em voo, ex.: a disparada por `tfMostrarPainel`) — sem ele, a resposta tardia sobrescrevia as datas restauradas.

**Verificação:** pytest **139** verde (coluna + round-trip). API real (login `pdm2026`): **7/7** — grava/lê snapshot, `tf_datas` preservadas, PATCH parcial não apaga o snapshot. Playwright: **datas manuais do Total Flex reproduzidas** ao reabrir (`_tfDatas`/`_tfValores` corretos), 0 erros de console. Dados de demo restaurados depois.

**Pendente (próximos sub-projetos):** trava total pós-assinatura (esconder salvar/criar orçamento, inserir ambientes, alterar parâmetros após contrato assinado); versionamento de documentos (novos criam versão, sem sobrescrever/apagar). Follow-up menor: simetria já aplicada nos guards de geração do TF.

### Sessão 2026-06-19 (sessão 16 — parâmetros de negociação por orçamento no banco)
**Processo:** pipeline superpowers (brainstorm → spec → plano → subagentes com revisão em duas etapas por task → revisão holística final → verificação por API real + Playwright → merge). Spec/plano em `docs/superpowers/`.

**Motivação (lacunas pegas em auditoria de persistência):** (1) o **desconto individual por ambiente** vivia só no `localStorage` (sumia ao trocar de máquina/navegador); (2) as **margens** (desconto global, custos, comissões, impostos) ficavam em `projeto.json` **compartilhadas pelo projeto todo**, impedindo orçamentos paralelos com parâmetros distintos. Regra registrada: todo documento/dado do projeto deve ser persistido (banco/disco), nunca só no navegador.

**Backend:**
- **`orcamento_ambientes.desconto_individual_pct`** (Float, default 0) — desconto por ambiente agora é por-orçamento, no banco. Migração de coluna idempotente em `_migrar_colunas`.
- **`orcamentos.margens`** (coluna TEXT que já existia) passa a ser a **fonte oficial** das margens, **por orçamento** (12 chaves).
- **`mod_orcamento_params.py`** (novo, puro): `MARGENS_DEFAULT`, `merge_margens(atual, req)` (merge + coerção de tipos; bool a partir de string; rejeita NaN), `sanear_descontos(pares, ids_validos)` (faixa 0..100, filtra ids fora do orçamento).
- **`POST /api/orcamentos/<id>/margens`** e **`PUT /api/orcamentos/<id>/descontos`** (lote) — ambos com gate `_projeto_esta_bloqueado` (pós-aprovação) e `ValueError→400`.
- **`GET /orcamentos/<id>/ambientes`** agora devolve `margens` do orçamento + `desconto_individual_pct` por ambiente.
- **Novo orçamento copia margens** do orçamento de origem (`origem_id`).
- **Migração `migrar_margens_para_orcamentos`** (startup, após `init_db`, em try/except): copia margens do `projeto.json` para orçamentos sem margens; idempotente (só preenche vazias).
- **Aposentada** a rota `POST /projetos/<nome>/margens` (gravava no `projeto.json`).

**Frontend (`static/index.html`):** ao ativar/trocar de orçamento, margens e descontos por ambiente são carregados **do servidor** (servidor é a fonte de verdade); salvamento via os endpoints por-orçamento; criar orçamento envia `origem_id`; guarda contra salvar margens sem orçamento ativo. Corrigido bug de ordem (o `carregarMargensSalvas` zerava `_descIndividual` recém-carregado) — agora roda antes da repopulação.

**Verificação:** pytest **137** verde (novos: coluna, módulo puro, migração). API real (login `pdm2026`): **16/16** asserts — save+read-back de margens, desconto por ambiente, validação 400, cópia por `origem_id`, **isolamento** entre orçamentos. Playwright: 0 erros de console/página. Dados de teste no DEV DB limpos depois.

**Limitação anotada:** comissão de múltiplos parceiros (hoje só `comissao_arq_pct`) e armazenamento dedicado de "projeto executivo" ficaram para sub-projeto futuro.

### Sessão 2026-06-19 (sessão 15 — fix do bloqueio + atualização de documentação)
- **Bug pego em uso:** no parecer da medição só dava para selecionar "Aprovado". Causa: o `#ciclo-panel` vive dentro de `#page-02`, e o bloqueio pós-aprovação (`aplicarBloqueioNegociacao`) desabilitava todos os `select`/`input` de `#page-02` — incluindo o select de parecer e os uploads da medição. **Correção:** o bloqueio passa a isentar `#ciclo-panel` (fluxo pós-aprovação precisa ficar interativo); a negociação continua travando. Verificado por Playwright. Commit `87679e3`.
- **Documentação atualizada:** DEV_LOG ([ESTADO]/[PENDENTE]/[CONTEXTO] revisados para os 10 perfis, painel de usuários, aprovação financeira, medição e correções de negociação) e `docs/USUARIOS.md` já refletindo os perfis/capacidades.
- **Deploy:** sub-projetos 1–4 + correções empurrados ao GitHub; produção atualizada via runbook (deps já instaladas, `ORIZON_HOST=0.0.0.0`, banco recriado/seedado com os 10 perfis, `no-cache` ativo).

### Sessão 2026-06-18 (sessão 14 — sub-projeto 4: workflow de medição)
Quarto e último sub-projeto da decomposição (fecha os itens 6 e 7).
- **Capacidades** (`perfis.py`): `registrar_medicao` (Medidor + Diretor) e `aprovar_medicao_reprovada` (Gerente de Vendas + Gerente Adm/Fin + Diretor).
- **Modelo `Medicao`** (1 por projeto): arquivos de solicitação/planta/doc-cliente + parecer + ambientes + responsáveis/datas. **`mod_medicao.validar_parecer`** (parcial exige ambientes).
- **Etapa 9 "Solicitação de medição":** upload do arquivo + confirmação por login+senha do Medidor (ou Diretor).
- **Etapa 10 renomeada "Medição":** registro do parecer (Aprovado/Reprovado/Parcial+ambientes) + planta promob, autenticado pelo medidor/diretor. Aprovado/Parcial concluem; **Reprovado em 2 passos** — fica `em_andamento` e só conclui com upload do documento do cliente + senha de Gerente de Vendas/Adm-Fin/Diretor (gravado quem autorizou).
- **Backend:** parser multipart **binário** (`_parse_multipart_arquivos`), helper `_usuario_com_capacidade`, endpoints `/medicao/{solicitacao,parecer,decisao-reprovado,arquivo/<tipo>}`, **guard** no `PATCH /ciclo/9|10` (só fecham pelo fluxo de medição), auditoria em `log_acoes_gerenciais`.
- **Frontend:** cards dedicados das etapas 9 e 10 (upload + popup de credenciais + parecer + campo de ambientes no parcial + 2º passo do reprovado).
- **Verificação:** pytest **125** verde; API real (multipart) confirmou todos os caminhos — etapa 9 (consultor 403, medidor 200), parcial sem ambientes (erro), aprovado (200), guard (400), reprovado 2 passos (medidor não libera 403; vendas libera 200), auditoria registrada. Spec/plano em `docs/superpowers/`.
- **Decomposição concluída:** os 4 sub-projetos (correções do ciclo, perfis+painel, aprovação financeira, medição) estão mesclados na `main`.

### Sessão 2026-06-18 (sessão 13 — sub-projeto 3: aprovação financeira gerencial)
Terceiro de 4 sub-projetos (usa a fundação de perfis do sub-projeto 2).
- **Capacidade `aprovar_financeiro`** em `perfis.py` (Diretor + Gerente Adm/Financeiro; gerente de vendas **não**).
- **`mod_ciclo.ETAPAS_APROVACAO_FINANCEIRA = {8, 11d}`** + `exige_aprovacao_financeira()`.
- **Gate no `PATCH /ciclo/<codigo>`:** concluir as etapas 8 ("Aprovação financeira I") e 11d ("Aprovação financeira II") exige `login`+`senha` de quem tem `aprovar_financeiro` (helper `_aprovador_financeiro`); senão **403**. Registra o aprovador como responsável da etapa e audita em `log_acoes_gerenciais` (ação `aprovar_financeiro`).
- **Frontend:** `concluirAprovacaoFinanceira(codigo)` abre o popup `pedirCredenciaisGerente`; a sub-etapa 11d passou a usar o card de aprovação financeira (igual à 8).
- **Verificação:** pytest **118** verde; API real confirmou — etapa 8 e 11d: gerente de vendas/consultor → 403, senha errada → 403, Gerente Adm/Fin e Diretor → 200, auditoria registrada. Spec/plano em `docs/superpowers/`.

### Sessão 2026-06-18 (sessão 12 — sub-projeto 2: perfis + painel admin de usuários)
Segundo de 4 sub-projetos (fundação reusada pelos sub-projetos 3 e 4).
- **`perfis.py` (fonte única):** 10 perfis oficiais (diretor, gerente_vendas, consultor, gerente_adm_fin, assistente_logistico, conferente, supervisor_montagem, assistente_administrativo, projetista_executivo, medidor) com matriz de permissões (desconto_max, ver_parametros, autorizar, gerir_usuarios). `database.py` (`limite_desconto`/`pode_ver_parametros`), `auth.py` e `main.py` passam a consultar `perfis`.
- **Migração `perfis_v2_2026`:** renomeia `gerente`→`gerente_vendas` e `admin`→`diretor` (idempotente, com guard `_tabela_existe`). Perfil técnico `admin` aposentado.
- **CRUD de usuários no painel admin:** `GET/POST/PATCH /api/admin/usuarios` (gate `gerir_usuarios` = Diretor + Gerente Adm/Fin); validadores puros em `mod_usuarios.py`; seção "Usuários" na page-07 (lista viva, criar, editar perfil/telefone, ativar/desativar, resetar senha). Usuários são desativados, não excluídos.
- **`/api/auth/me`** expõe `rotulo` e `pode_gerir_usuarios`; frontend usa `limite_desconto` do `/me` (removido o hardcode `_LIMITES_NIVEL`); `nav-07` gateado por `pode_gerir_usuarios`.
- **`seed.py`:** um usuário-exemplo por perfil (10); saída ASCII-safe. **`docs/USUARIOS.md`** documenta os perfis.
- **Bug pego na verificação:** variável local `perfis` em `do_POST` (rota `/api/gerente/verificar`) sombreava o módulo → `UnboundLocalError` nos gates novos; renomeada para `_perfis_cfg`.
- **Verificação:** pytest **116** verde; CRUD/gate confirmados via API real (criar/duplicado/perfil-inválido/editar/desativar; consultor 403; adm-fin 200). Spec/plano em `docs/superpowers/`.

### Sessão 2026-06-18 (sessão 11 — sub-projeto 1: correções do ciclo)
Primeiro de 4 sub-projetos decompostos de uma leva de pedidos (perfis, aprovação financeira, medição virão a seguir).
- **Gating de sub-etapas (genérico):** sub-etapas (`11a`–`11e` do PE, `17a` da Montagem e quaisquer `Nx`) estavam desbloqueando antes da etapa-mãe. Agora herdam o gating da mãe e desbloqueiam **junto** com ela. Backend: `mod_ciclo.etapa_pai()` + `pode_avancar()` recursivo na mãe. Frontend: `_etapaBloqueada()` recursa na mãe. (Substituído o teste antigo `test_pode_avancar_subetapa_sempre_livre`.)
- **Botão "Assinar Contrato":** o botão pós-aprovação na tela de negociação passou de "🔒 Orçamento aprovado – assinar contrato" para **"✍ Assinar Contrato"**, com estilo idêntico ao "Rever Orçamento" (`btn btn-ghost`, contorno âmbar).
- **Verificação:** pytest **103** verde; Playwright confirmou sub-etapas 🔒 antes da etapa-mãe e liberando juntas, e o botão renomeado/estilizado. Spec/plano em `docs/superpowers/`.

### Sessão 2026-06-18 (sessão 10b — UX: popups estilizados, assinatura do cliente, botão voltar)
**Processo:** pipeline superpowers (clarificação → branch → subagentes com revisão a nível de controlador → verificação Playwright/dados reais → revisão final → merge local).

- **Diálogos nativos → popups estilizados:** removidos todos os `confirm`/`alert`/`prompt` (que apareciam como "127.0.0.1:8765 diz"). Novos helpers em `static/index.html`: `confirmarPopup` (sim/não), `avisoPopup` (aviso) e `pedirCredenciaisGerente` (login+senha estilizado). Refatorados: signatário do contrato em `gerarContrato` (popup Sim/Não), reabrir etapa (`abrirModalReabrir` — antes `confirm`+2 `prompt` → popup de credenciais), remover ambiente e o aviso de abrir o editor.
- **Assinatura do cliente no contrato:** o nome saía com fonte/negrito diferente das demais. Causa: parágrafo em estilo `Normal` com `\n` inicial; `_subst_paragrafo` herdava o run vazio. Correção: `_subst_paragrafo` ignora run inicial vazio ao escolher a base de formatação; `scripts/normalizar_assinaturas.py` (idempotente) padroniza as 4 linhas de assinatura (empresa/cliente/2 testemunhas) em estilo `Heading 2`, limpa overrides de fonte e remove o `\n` extra — fonte/negrito/alinhamento iguais. 2 testes novos.
- **Botão "Voltar"** também ao final da lista de etapas do ciclo (`renderCiclo`).
- **Verificação:** Playwright (servidor real) sem erros de console/página; popups abrem e resolvem; 2 botões "Voltar" no ciclo. Suíte: **101 testes** passando.

### Sessão 2026-06-18 (sessão 10 — negociação: bloqueio, Rever Orçamento, À Vista, formas)
**Processo:** pipeline superpowers (brainstorm → spec → plano → subagentes com revisão a nível de controlador → verificação Playwright com dados reais → merge). Spec/plano em `docs/superpowers/`.

**Backend (`mod_contrato.py`):**
- `_forma_label` + `_FORMA_LABELS`: converte códigos de forma (pix/ted/boleto/cheque/dinheiro/cartao_credito) em rótulos pt-BR; idempotente.
- `_parse_pagamento`: `entrada_tipo` via rótulo; novo `forma_parcela` (rótulo da 1ª parcela; "Cartão de Crédito" quando cartão).
- `_montar_mapping`: novo marcador `TIPO` (forma das parcelas) + mapeia `NOME_TESTEMUNHA_1`/`NOME_TESTEMUNHA_2`/`NOME_TESTEMUNHA2` (alinha ao template real; corrigiu 3 testes vermelhos pré-existentes).
- `scripts/inserir_marcador_tipo.py` (idempotente): insere `[NUM_PARCELAS] / [TIPO]` no `modelo_contrato_mapeado.docx`.

**Frontend (`static/index.html`):**
- **Bloqueio pós-aprovação:** `aplicarBloqueioNegociacao(travar)` deixa toda a negociação somente-leitura ao concluir a etapa 6 — cobre `#sb-params` (sidebar: desconto, modalidade, parcelas, formas, taxa TF) **e** `#page-02` (tabela, painéis, datas, total). Chamada em `atualizarBotoesAprovacao()`.
- **Rever Orçamento:** substitui "Voltar ao Orçamento" (removido do card 7 do Ciclo); dois botões na action-row da negociação pós-aprovação (`✎ Rever Orçamento` + assinar contrato); senha gerencial → `POST /ciclo/desfazer_aprovacao` → destrava e reexibe Salvar/Aprovar.
- **À Vista:** `painel-avista` com entrada (valor+data+forma) e liquidação (valor automático = total−entrada, somente-leitura; data+forma); alimenta `_planoPagamento` como entrada + 1 parcela (liquidação).
- **Calendário:** `showPicker()` em qualquer clique de `input[type=date]` (delegado em `document`) + CSS do ícone; cobre campos dinâmicos.
- **Formas por modalidade:** seletores `neg-forma-entrada`/`neg-forma-parcela` (`atualizarFormasPagamento`): cartão→entrada Pix/TED/Boleto + parcelas "Cartão de Crédito" fixo; aymoré→parcelas "Boleto" fixo; VP/TF→parcelas Boleto/Cheque; à vista→Pix/TED/Boleto/Cheque/Dinheiro. Estado `_formaEntrada`/`_formaParcela` nos 4 `_planoPagamento`.
- **Aprovação:** modal pré-seleciona formas a partir de `_planoPagamento` (mapeia ted→transferencia; +Dinheiro); `salvarValorNegociado` persiste o plano JSON em `forma_pagamento` (usado pelo backend como fallback do `pagamento_json`).

**Verificação (Playwright, servidor real, login `pdm2026`):** zero erros de console/página; regras de forma por modalidade; à vista com clamp de saldo; bloqueio trava modalidade+datas e destrava ao Rever; dois botões pós-aprovação. Suíte: **99 testes** passando.

**Limitação anotada:** restaurar `_formaEntrada`/`_formaParcela` a partir do `forma_pagamento` salvo ao reabrir orçamento não-aprovado ficou fora de escopo (o recálculo regenera `_planoPagamento`).

### Sessão 2026-06-18 (sessão 9 — contrato: marcadores, pagamento, número, edição protegida)
**Bug-raiz corrigido (F1):** `_capturarPagamento` (frontend) raspava as colunas da tabela de pagamento por índice e saía com **data e valor trocados**, além de incluir Assinatura/Entrada/Total como parcelas (o valor bruto caía na "13ª parcela"). Causa descoberta inspecionando o `pagamento_json` real do `Contrato` 6. Os testes anteriores passaram porque usavam um JSON **fabricado** — lição: verificar com dados reais.

**F1 — Pagamento correto + grade + template por marcadores:**
- Frontend expõe `window._planoPagamento` (estruturado: só parcelas reais com `valor` numérico + `data`, `total_cliente`, `texto_cartao`); `_capturarPagamento` retorna esse global (sem raspar DOM) — robusto aos 4 painéis (aymoré/cartão/vp/tf).
- `modelo_contrato_mapeado.docx` (todo em marcadores `[MARCADOR]`) **promovido a template oficial**; `modelo_contrato_final.docx` aposentado. Geração reescrita: `_substituir_marcadores` (corpo/tabelas/cabeçalho) + `_preencher_grade` (posicional). Removidos `_set_cell`/`_set_para`/`_relabel_cpf_cnpj` (agora é tudo do template).
- Grade: valor+data por parcela **sem ordinal**, **traços** nos slots vazios (linhas preservadas); cartão no 1º campo (`12x R$ ...`); novo `[TOTAL_CONTRATO]`.
- `_parse_pagamento` reescrito para a estrutura real (`valores` em dinheiro, `valor_contrato`, `texto_cartao`).
- Verificado end-to-end com **dados reais** via navegador (Playwright) + `/calcular_aymore`.

**Número do contrato:** `gerar_num_contrato` → `LOJA-AAAA-MM-DD-SEQ` (`INS`, sequência contínua por loja), coluna `contratos.num_contrato` (migração idempotente), gerado uma vez/estável, no cabeçalho com a data abaixo. Ajuste de layout: número e data realinhados à direita (saíam fora da página A4).

**F2 — Contrato editável protegido + edição pontual gerencial:**
- `preencher_contrato(..., protegido=True)`: valores envoltos em `permStart/permEnd` (editáveis) + `documentProtection edit=readOnly` (texto fixo e cabeçalho travados) — `_proteger_editaveis`.
- `_converter_pdf(docx_path)` extraído (converte sem regenerar o docx).
- `POST /api/projetos/<nome>/contrato/editar`: gate gerencial (gerente/diretor/admin, auditado `editar_contrato`), abre o `.docx` no Word/LibreOffice e inicia watcher (`contrato_editar.py`: mtime + lock + debounce + timeout) que regera o PDF a cada salvamento.
- Botão "✎ Editar contrato" + modal gerencial no frontend.

**Processo:** ambos (F1, F2) pelo pipeline superpowers (spec → plano → subagentes com revisão em duas etapas → verificação com dados reais → merge). Suíte: **93 testes** passando.

**Banco:** coluna `contratos.num_contrato` (VARCHAR(30), via `_migrar_colunas`).

---

### Sessão 2026-06-17 (sessão 8 — redesenho do ciclo de vida, sub-projetos A–E)
**Spec e implementação:**
- **A) Etapas — ordem + gating:** códigos renumerados ("2"=Criação do projeto, "3"=Briefing); gating sequencial (PATCH /ciclo rejeita 400 se etapa anterior não concluída; UI mostra 🔒); sub-etapas livres; reabertura em cascata por gerente via POST /api/projetos/<nome>/ciclo/<codigo>/reabrir (auditada em `log_acoes_gerenciais`, bloqueia se contrato assinado); criar projeto marca etapas 1 e 2 (Briefing 3 pendente); módulo `mod_ciclo.py`
- **B) Cadastro completo na aprovação:** criar cliente exige nome+email+telefone (CPF opcional); modal de aprovação não edita mais cliente; `validar_cliente_para_contrato` bloqueia contrato sem cadastro completo (HTTP 400 + `campos_faltando` → popup "Cadastro Incompleto")
- **C) Aprovação — semântica + botão:** "Aprovar Orçamento" conclui Revisão (5) e Aprovação (6) juntas; etapa 5 sem toggle manual; `desfazer_aprovacao` reseta 5/6/7; botão pós-aprovação "Orçamento aprovado – assinar contrato" leva ao card de assinatura
- **D) Briefing obrigatório por-projeto:** briefing agora por-projeto (coluna `briefings.projeto_nome`); endpoints GET/POST /api/projetos/<nome>/briefing; etapa 3 marcada só no projeto; criar projeto → briefing obrigatório → negociação; backend bloqueia orçamentos/pool sem briefing completo do projeto (400)
- **E) Contrato — signatário/testemunhas/formatação + enforcement:** 2º signatário = cliente (não consultor); INSPIRIUM intacta; testemunhas provisórias (Jaime Perinazzo/Felipe Guizalberte); CPF→CPF/CNPJ; tags de nomenclatura (rótulo cinza ~7pt) nos campos editáveis; gate de ambiente (POST /contrato 400 sem ambientes); `signatario_override` (modal "é o cliente cadastrado?"); bug-fixes: popup troca de modal, bloqueio de aprovação sem ambiente
- **Banco novo:** tabela `log_acoes_gerenciais`; coluna `briefings.projeto_nome`; tabela `schema_migrations`

---

### Sessão 2026-06-15 (sessão 7 — ciclo completo 20 etapas + módulo contrato + aprovar orçamento)
**Commits:** `3861470` → `b5d2ad3` (13:39 → 21:19)

**Spec e planejamento:**
- `docs/`: spec ciclo completo com 20 etapas, contrato, NFe cliente (2 iterações com correção de etapa 6 e endereço de instalação)
- Plano de implementação do módulo de contrato (7 tasks, TDD)

**Backend — módulo ciclo + contrato:**
- Models: `CicloEtapa`, `Contrato`, `ContratoAssinatura` (SQLAlchemy)
- `mod_contrato.py`: geração de docx via `docxtpl` + conversão para PDF via LibreOffice; fallback `LibreOfficeIndisponivel` salva `.docx` e avança status sem travar; hash SHA-256 de assinatura
- `config/contrato_template.docx`: template com 13 variáveis Jinja2 (cliente, valores, parcelas, endereços)
- `scripts/configurar_template_contrato.py`: popula automaticamente as variáveis no .docx base
- `main.py`: `_montar_dados()` inclui `valor_liquido`; 9 novas rotas (ciclo, contrato, orcamento valor)
- Auto-criação de etapas 1-5 como concluídas no `GET /ciclo` para projetos com negociação ativa

**Interface — aba Ciclo (page-02):**
- Nova aba "Ciclo" na barra superior da page-02
- 20 etapas em 2 colunas (esq: 1-10, dir: 11-20); toggle clique para concluir/reabrir
- Card 7 (Contrato): botão gerar, preview, download PDF/docx, botão assinar, campo senha gerente
- Card 16 (Adendo): UI placeholder para futuro
- Após gerar contrato: abre aba Ciclo no card 7 automaticamente
- Botões "Salvar Parâmetros" e "Aprovar Orçamento" ocultos quando etapa 6 concluída
- `carregarCicloSilencioso()`: carrega `_cicloData` ao abrir projeto sem exibir o painel

**Interface — Aprovar Orçamento reformulado:**
- `salvarValorNegociado()`: persiste valor negociado e forma de pagamento antes de abrir modal
- Modal de aprovação: dados do cliente, CPF e endereço de instalação destacados se vazios, condições de pagamento pré-carregadas da negociação ativa
- Status renomeados: `gerado` → `para_assinatura`, `vigente` → `assinado`
- Badges CSS para `para_assinatura`, `rascunho`, `assinado`
- Botão Omie removido da action-row (migrado para etapa 12 do Ciclo)
- Campo entrada com máscara moeda `R$ X.XXX,XX` em tempo real; `parseMoeda()` para leitura
- `mascaraMoedaInput()` reescrita: cursor estável, formato centavos-first correto

**"Voltar ao Orçamento" (desfazer aprovação):**
- `abrirModalVoltarOrcamento()`: modal com login/senha de gerente
- `POST /ciclo/desfazer_aprovacao`: valida gerente, reseta etapas 6 e 7; disponível somente antes de contrato assinado

**Bugs corrigidos:**
- Auto-load projetos ao abrir app (`DOMContentLoaded → projCarregar()`)
- LibreOffice indisponível: exceção `LibreOfficeIndisponivel` específica — salva .docx e avança sem crash
- Etapa 6 não era mais hardcoded como concluída — marcada corretamente ao gerar contrato
- Card 7: exibe botão baixar .docx + aviso dourado quando LibreOffice não disponível
- `GET /contrato/pdf` serve .docx com `Content-Type` e `Content-Disposition` corretos; retorna `arquivo_tipo`
- `usuario.id` → `usuario['id']` no PATCH ciclo (fix KeyError)
- `PROJETOS_DIR` absoluto no helper contrato (fix path relativo)
- Botão dourado `Etapas do Projeto` e template do usuário corrigidos

---

### Sessão 2026-06-15 (sessão 6 — admin + omie sync + lista projetos + pipeline)
**Commits:** `0bcc154` → `44863eb`

**Funcionalidades adicionadas:**

**EP-08 — Sincronização Omie e Painel Admin:**
- **Role Admin:** novo nível `admin` no banco — acesso total a vendas + painel exclusivo (page-07). Limite de desconto 50%. Usuário de teste: `admin2026`/`admin123`
- **Auto-sync cliente → Omie:** `POST /api/clientes` tenta `criar_cliente()` em background thread após salvar localmente. Grava `omie_sync_status` (`ok`/`pendente`/`erro`) + `omie_sync_erro` na tabela `clientes`. Pendente = sem CPF ou sem credenciais Omie; Erro = falha da API
- **Painel Admin (page-07):** lista clientes com sync pendente/erro com botão "Tentar" por entrada. Acessível apenas para role `admin`. Nav item `⚙ Admin` aparece na sidebar somente para admin
- **PATCH `/api/projetos/<nome>/status`:** muda status do projeto (quente/morno/frio/perdido). Rejeita "convertido" via API
- **Convertido automático:** `bloquear_projeto()` seta status `convertido` em `projetos_meta` ao aprovar

**EP-09 — Lista de Projetos e Pipeline de Vendas:**
- **Lista redesenhada:** tabela com colunas Status | Data | Projeto | Cliente | Último Orçamento. Substitui cards anteriores
- **Filtro de texto:** busca simultânea em nome do projeto, nome do cliente e CPF do cliente (client-side)
- **Filtro multi-select de status:** dropdown com checkboxes por status (OR lógico); botão mostra contagem ativa
- **Status pipeline:** `quente` / `morno` / `frio` / `convertido` / `perdido`. Tabela `projetos_meta` no banco
  - `perdido` grava `perdido_em` automaticamente
  - Dropdown inline na lista para alterar status
  - Botão de status no cabeçalho da page-02 (negociação)
- **UX lista:** duplo clique ou botão "Abrir →" entra no projeto; `goPage(n)` corrigido para navegar mesmo sem nav item na sidebar
- **Último orçamento ativo:** `ativarOrcamento(id)` grava em `localStorage['lastOrc_<nome_safe>']`; `carregarOrcamentos()` restaura ao reabrir projeto

**Bugs corrigidos:**
- `goPage(2)` bloqueava com `if(!navEl) return` após remoção de `nav-02` — corrigido para `if(navEl && navEl.classList.contains('locked')) return`
- Badge de status `—` (sem status) não era clicável — corrigido para abrir dropdown
- `orcamento_ativo_id` no `projeto.json` sempre apontava para Orçamento 1 — descartado em favor de localStorage + `updated_at`
- Subquery `func.max(updated_at)` indeterminística com empate — substituída por `.order_by(updated_at.desc(), id.desc()).first()`
- Clientes com `omie_sync_status IS NULL` invisíveis no painel admin — corrigido com `or_(in_(), is_(None))`
- Missing `return` após "Cliente não encontrado" no retry endpoint

**Sidebar e navegação:**
- Removidos: `nav-new-amb` (Novo Ambiente), `nav-02` (Negociação), `nav-03` (Exportar)
- Adicionado: `nav-07` Admin (oculto por padrão, visível apenas para role admin)
- Barra de orçamentos: `Ambientes` | `Novo Ambiente` | `Novo Orçamento` (3 botões)
- `unlockNav(2)` e `unlockNav(3)` mantidos por compatibilidade (null-safe)

---

### Sessão 2026-06-12 (sessão 5 — bugs EP-07 + desconto individual + limites + UX)
**Commits:** `5ccb96d`, `019eb6b`, `b6e8d3f`, `74a4710`, `5349427`, `f1a0c30`

**Bugs corrigidos:**
- **BUG-EP07-03:** `uploadXmls` em modo EP-07 não chama mais `/ambientes/adicionar`. Arquivo salvo no disco somente após `db.commit()` bem-sucedido (endpoints: pool/novo, sobrescrever, nova_versao, criar_forcado)
- **Cards 0 ambientes:** `_enriquecer_projetos_com_pool()` em `main.py` sobrescreve `n_ambientes`/`n_selecionados` com contagem real do banco para projetos EP-07
- **Painel de apoio modal EP-07:** `mpAtualizarApoio` agora faz loop per-ambiente e aplica `_descIndividual` antes de somar
- **Discriminação por ambiente EP-07:** `atualizarDiscriminacao` usava `projetoAtivo.ambientes` (vazio); corrigido para usar `_orcAmbientesAtivos` com desconto efetivo combinado

**Funcionalidades adicionadas:**
- **Desconto individual por ambiente (EP-07):** coluna "Desc.%" com input editável na tabela de negociação. Fórmula: `avista = bruto × (1−desc_global%) × (1−desc_individual%)`
- **Limite de 35% no desconto total:** `_margemAtual` atualizado por `mpAtualizarApoio`; bloqueia save de parâmetros; reverte desconto individual via `_onDescIndBlur`
- **Esc fecha modal ativo:** listener global percorre modais do z-index mais alto ao mais baixo e chama a função de cancelar do primeiro visível (15 modais cobertos)

---

### Sessão 2026-06-10 (sessão 4 — EP-07 completo)
**Commit:** `79cec86` — feat: EP-07 versionamento de orcamentos completo (passos 1-12)

**Realizado:**
- EP-07 Versionamento de Orçamentos completo — todos os 12 passos implementados sem bugs
- Passos 1-8: backend (tabelas, rotas, pool, orçamentos, recálculo)
- Passos 9-12: interface (barra de orçamentos, painel Ambientes, novo orçamento, renomear)
- Modal de parâmetros corrigido para calcular sobre ambientes do orçamento ativo
- Upload de XML vincula automaticamente ao orçamento ativo quando ambiente já existe no pool
- Servidor DEV atualizado: `167.88.33.121:8765` rodando com screen

**Documento criado:**
- `docs/modulos/financeiro/FUTURO_CALCULO_FINANCEIRO.md`

**Pendente:**
- Bug toggle "incluir custos adicionais" (da sessão 2) — ainda em aberto
- Total Flex (US-14) — planejado para v0.2.0
- Módulo Clientes e Parceiros vinculados a orçamentos — planejado

### Sessão 2026-06-09 (sessão 3 — documentação)
- BACKLOG.md com 26 histórias (EP-01 a EP-07)
- 7 SPEC.md de módulos
- VERSIONAMENTO.md com spec completo do EP-07

### Sessão 2026-06-09 (sessão 2)
- Módulo Clientes completo
- Projeto vinculado a cliente obrigatório

### Sessão 2026-06-07/08 (sessão 1)
- Sistema de autenticação completo
- Módulo Parceiros
- Toggle custos adicionais

## Sessão 27 — Cutover do motor de negociação (Fase B)

A tela de negociação e o modal passam a usar o motor `mod_negociacao` (não mais o cálculo
legado do frontend):
- **Preview endpoint** `POST /api/orcamentos/<id>/negociacao-preview` (puro, sem gravar):
  display ao vivo da cadeia do motor; helper compartilhado `_negociacao_breakdown`.
- **Persistência autoritativa**: `_recalcular_orcamento` grava `valor_total = Val_Cont` e
  `valor_liquido = Val_Liq` no save de margens e no PATCH; o frontend deixa de enviá-los e o
  PATCH não os aceita mais. O contrato reflete automaticamente (lê `valor_total`/`valor_liquido`).
- **UI**: `negPreview()`/`_aplicarPreviewNaTela()` sobrepõem bruto negociado / à vista / comissão
  arquiteto / fidelidade / líquido / %desc total e o `neg-avista` (que alimenta o pagamento via
  `mod_fin`); limite de 35% sobre o `%Desc_Tot` do motor. `mod_fin` reusado como está.
- **Segurança**: golden-master `scripts/snapshot_cutover.py` (baseline) + `scripts/diff_cutover.py`
  (old×new); rollback na tag `pre-refator-negociacao`.
- **Pós-cutover**: `scripts/reset_para_teste.py` (DESTRUTIVO — cancela contratos, volta o ciclo à
  fase de orçamento, recalcula tudo) para testar o fluxo inteiro + transições de fase. Backup antes.
- **Fase C** (limpeza do legado: `margens` duplicado, `custo_financeiro_pct` do `mod_margens`)
  fica para depois.

## Sessão 28 — Bloqueio dos campos de impostos

Base tributária e provisão de impostos passam a ficar **ocultas (🔒)** por padrão na tela; o
sistema continua calculando, mas só revela mediante senha de **Diretor ou Gerente
Administrativo-Financeiro** (capacidade `aprovar_financeiro`).
- **Backend:** `POST /api/auth/liberar_impostos` (auth_routes.py) — valida usuário+senha e
  `perfis.pode(nivel, "aprovar_financeiro")`; 401 (credencial inválida) × 403 (sem capacidade).
- **Frontend:** `_atualizarImpostos` cacheia em `_impostosValores` e delega a `_renderImpostosLock`
  (único exibidor): valor real se `_impostosLiberados`, senão cadeado clicável. Modal
  `modal-liberar-impostos`. Valor liberado é clicável para re-bloquear. Estado **não persistido**
  (recarregar re-bloqueia — escopo de sessão/timer é tratamento futuro).
- **Cobertura:** os IDs `-r-base-trib`/`-r-impostos` são compartilhados pelos 4 painéis de
  pagamento → a tela do projeto fechado fica coberta automaticamente.
- **Honesto:** é bloqueio de **apresentação** (valores calculados no cliente), não sigilo
  criptográfico.

## Sessão 29 — Fase 2: distribuição brinde/viagem + fonte única da tela + persistência do pagamento

Branch `feat/fase2-autosave-negociacao`. Continuação da faxina single-source.

- **Auto-save incremental da negociação:** "trava" o orçamento ao sair (troca in-app via
  `ativarOrcamento` com `await salvarValorNegociado()`; `beforeunload` com `keepalive`). O front
  não persiste estado — o backend é a fonte.
- **Brinde/viagem distribuídos pelo POOL do projeto** (`mod_negociacao`): brinde **igual** por
  ambiente (`bri/n_total_proj`), viagem **proporcional** ao valor (`cust_via × vbva/vbvo_proj`).
  Um orçamento subconjunto (3 de 7) recupera a sua fração. `_negociacao_breakdown` calcula
  `n_total_proj`/`vbvo_proj` do pool e passa ao motor (preview e `_recalcular_orcamento`).
  Fallback ao comportamento atual quando os args são `None` (âncora LELEU inalterada).
- **Tela de negociação — fonte única (Opção B):** o motor é a única fonte de todos os números da
  tabela por ambiente.
  - **Desconto por ambiente robusto:** `renderTabelaNeg` lê de `pa.desconto_individual_pct`
    (`_descIndividual` só como override de edição) → aparece já na 1ª entrada, sem timing.
  - **Duas colunas por ambiente:** **À vista** (`VAVA`) e **Com financiamento**
    (`VAVA × Val_Cont/VAVO`), ambas escritas por `_aplicarPreviewNaTela`; total à vista (`VAVO`) +
    total de contrato (`Val_Cont`) no rodapé. `_ep07DistribuirFinanciado` aposentado (no-op).
  - **Total único (fim da corrida):** só `_aplicarPreviewNaTela` escreve `neg-total`/
    `neg-total-final` = `Val_Cont`. O fluxo de pagamento parou de escrevê-los; ao trocar a
    modalidade, **auto-salva** `forma_pagamento` (`agendarSalvarPagamento`, debounced) → o motor
    recalcula `Val_Cont` → `negPreview` reexibe. **Guard de assinatura** (dentro do timer) quebra
    o loop preview↔pagamento (só salva se o plano mudou).
- **Persistência do plano de pagamento (3 bugs corrigidos):**
  - **Aymoré:** passou a salvar a **data da 1ª parcela** (`ay-data-primeira` faltava em
    `_NEG_CAMPOS_POR_MODALIDADE`).
  - **Auto-save na carga:** `_carregandoOrcamento` suprime o auto-save do pagamento durante a
    carga do orçamento (defesa contra salvar o estado default antes do restore).
  - **Causa-raiz "perde o parcelamento no hard refresh" (mantinha a modalidade):** confirmada por
    log de console — `carregarMargensSalvas` é re-disparado na **navegação p/ a página 2**
    (e em add-ambiente/save-params) **sem `_negociacaoPendente`**; `carregarModalidades →
    onPagamentoChange(default)` **zerava `neg-parcelas`** (volta a 1) e um auto-save salvava
    `n_parcelas=1`, sobrescrevendo o plano. Só o orçamento ativo (o único recarregado) era afetado.
    **Fix single-point:** se há orçamento ativo e nenhuma restauração pendente, `carregarMargensSalvas`
    **captura a negociação atual da tela e a re-restaura** após o reset — cobre os 3 re-triggers.
- **Pendente (Fase 2, futuro):** seletor de ambientes para brinde/viagem; faxina de schema
  (`custo_financeiro_pct`, `margens` duplicado, `valor_liquido` legado); duplicidade de
  armazenamento `total_cliente` × `Val_Cont`. 301 testes verdes.

## Sessão 30 — Faxina de legado de margem + glossário de nomenclatura

Branch `faxina/schema-fase2`. Objetivo (do usuário): **nomenclatura bem definida** + um
**mecanismo para sempre falarmos a mesma língua**, eliminando legado sem trazer falhas.

- **`NOMENCLATURA.md` (raiz)** — glossário **canônico** das siglas fechadas (VBVA/VBNA/VAVA,
  VBVO/VBNO/VAVO, Com_Arq/Pro_Fid/Cust_Via/Bri/Cust_Ad/Val_Liq/Desc_Tot/Markup/Cust_Fin/Val_Cont/
  Prov_Imp), contexto do pool (`n_total_proj`/`vbvo_proj`), onde cada parâmetro fica salvo, a
  nomenclatura **removida** (não reusar) e o **mecanismo**: o motor `mod_negociacao` é a fonte única;
  todo número vem dele.
- **Discriminação por ambiente removida** (decisão do usuário — tinha falhas, não é necessária; no
  futuro refazer pelo motor). Saíram: HTML do painel, `toggleDiscriminacao`/`atualizarDiscriminacao`/
  `lerMargensModal`. `agendarDiscriminacao` → **`agendarParametros`** (só apoio + auto-save).
- **Legado de margem removido:** `mod_margens.calcular_margens` + endpoint `POST /calcular_margens`
  + `ratearViagem` + o path legado Fase 01 de `executarCalculo` (só o EP-07 sobrou) + `test_margens.py`
  + `custo_financeiro_pct` dos defaults de params. **Mantido `mod_margens._normalizar_faixas`/`_pmt`**
  (vivos, servem o endpoint de faixas).
- **Motor** ganhou (aditivo, TDD) o waterfall por ambiente (`Com_Arq/Pro_Fid/Cust_Via/Bri/Val_Liq`,
  Σ por ambiente = agregados) — disponível para uso futuro pelo motor.
- **Vestígios Fase 01 em caminhos mortos** (`lerMargensNegociacao`, `_negBaseValues`, branch legado de
  `renderTabelaNeg`) ficam sinalizados para uma passada futura (entrelaçados com funções vivas).
- **Não-feito (irreversível):** drop da coluna `Orcamento.margens` — exige backup do `orizon.db` +
  aprovação. **295 testes verdes** (caíram 7 do `test_margens` removido).
- **Fix (race do desconto por ambiente):** o desconto só era salvo no blur (`_persistirDescontosOrc`,
  fire-and-forget) e corria com a troca de orçamento (o `_orcamentoAtivoId` mudava antes do commit) →
  desconto não ficava guardado / aparecia stale (intermitente). **Fix:** `ativarOrcamento` aguarda
  `_persistirDescontosOrc` antes de trocar; `_onDescIndBlur` captura o orçamento do blur e aborta se
  trocou durante o `await`. (Race pré-existente, não da faxina.)

## Sessão 31 — Drop da coluna `Orcamento.margens` (fecha a faxina de schema)

Branch `faxina/drop-orcamento-margens`. Usuário autorizou (base é teste; backup feito:
`omie.db.bak-2026-06-24-pre-drop-margens`). A coluna era **duplicação legada** — o motor lê
`Projeto.parametros_json` + `Orcamento.desconto_pct`.

- **Código para de usar `orc.margens`:** `GET /ambientes` e `POST /margens` passam a devolver
  `desconto_pct` (coluna canônica) em vez de um objeto `margens`; criação de orçamento copia
  `desconto_pct` da origem; frontend lê `d.desconto_pct` (não `d.margens.desconto_pct`).
- **Schema:** coluna `margens` removida do modelo `Orcamento`; funções de migração obsoletas
  (`migrar_margens_para_orcamentos`, `migrar_parametros_para_projeto`) e seus call-sites/testes
  removidos; `test_legado_intacto` passa a exigir que `margens` **não** exista.
- **Migração idempotente** `_drop_coluna_margens_orcamentos` (startup, sqlite≥3.35) dropa a coluna
  em DBs existentes; DBs novos já nascem sem ela. **Aplicada ao `orizon.db`** (dados preservados:
  21 orçamentos / 13 contratos). **291 testes verdes** (caíram os 4 testes das migrações obsoletas).
- **Desconto por ambiente — alinhado ao padrão dos campos que funcionam:** era o único campo que
  salvava **só no blur** (`_persistirDescontosOrc`, frágil). Agora:
  - **auto-save debounced no `oninput`** (`agendarSalvarDescontos`, 500ms — espelho do
    `agendarSalvarParametros`); o **`beforeunload`** também persiste (keepalive); a troca de orçamento
    (`ativarOrcamento`) aguarda o save; o limite continua no blur.
  - **Causa-raiz do "input volta ao valor antigo, mas a conta fica certa":** `_persistirDescontosOrc`
    gravava no banco mas **não atualizava `_orcAmbientesAtivos` em memória**; quando `_descIndividual`
    era zerado (`carregarMargensSalvas`) e `renderTabelaNeg` rodava, o input lia o
    `pa.desconto_individual_pct` antigo (o motor lia do banco → conta certa). **Fix:** o save
    sincroniza `pa.desconto_individual_pct` em memória com o valor digitado.

## Sessão 32 — Três frentes: super-admin/árvore, acesso multi-loja, e config financeira/provisões

Três workstreams iniciados hoje (2026-06-24). As duas primeiras com código pronto (TDD +
revisão final opus), **aguardando validação no browser** antes do merge; a terceira em spec.

### Frente A — Super-admin: aterrissagem por papel + árvore estrutural (slice #1+#2)
Branch `feat/super-admin-arvore` (de `main`). super_admin/admin_rede passam a **aterrissar no
Painel Admin** (não em Projetos); menu operacional escondido só p/ super_admin; **árvore** estende
o drill até `Rede › Loja › Projeto › Etapas do ciclo` (estrutural, **sem PII** — PII fica p/ painel
LGPD futuro). Módulo puro novo `mod_arvore.py` + 2 rotas GET finas. Revisão final opus PRONTO P/
MERGE; fix I1 (teste e2e cross-rede 403). **Bugfix pré-existente:** botões "Entrar" rede/loja
quebravam com nome com espaço (onclick aspas duplas + JSON.stringify) → aspas simples + `_attrJson`.
- **Arquivos:** `mod_arvore.py` (novo); `tests/test_arvore.py`, `tests/test_arvore_e2e.py` (novos);
  `main.py` (rotas `GET /api/admin/lojas/<id>/projetos` e `/api/admin/projetos/<nome>/etapas`);
  `static/index.html` (aterrissagem `_aterrissarPorPapel`, nível 4 da árvore, fix dos botões Entrar).
- **Docs:** `docs/superpowers/specs/2026-06-24-super-admin-aterrissagem-arvore-design.md`;
  `docs/superpowers/plans/2026-06-24-super-admin-aterrissagem-arvore.md`.

### Frente B — Acesso multi-loja (loja ativa por requisição)
Branch `feat/multi-loja` (empilhada sobre `feat/super-admin-arvore`). Um usuário acessa N lojas e
opera numa **loja ativa** por vez, escolhida via header `X-Loja-Ativa` (lido só em `_ator_dict`;
`escopo_operacional` é o funil — ~51 call sites inalterados). Tabela M:N `usuario_lojas` +
backfill; `usuarios.loja_id` mantido como loja default. `resolver_loja_ativa` fail-closed (header
não-membro → 403). `/api/auth/me` expõe `lojas` + `loja_ativa_id`. Criação/edição de usuário aceita
`loja_ids`. Contrato usa a loja ativa. Frontend: interceptor de `window.fetch` + seletor + modal
multi-loja. Revisão final opus PRONTO P/ MERGE; fixes: `do_PUT` lê o header (contexto obsoleto),
edição não dropa memberships fora do escopo do ator de loja, coerção de `loja_ids`.
- **Arquivos:** `database.py` (`UsuarioLoja` + backfill + `membership_loja_ids`); `mod_tenancy.py`
  (`resolver_loja_ativa`, `escopo_operacional`, `lojas_do_novo_usuario`); `main.py` (`_ator_dict` +
  header nos 4 dispatch, rotas de usuário, contrato); `auth_routes.py` (`/api/auth/me`);
  `static/index.html` (interceptor + seletor + modal); `tests/test_multi_loja.py`,
  `tests/test_multi_loja_e2e.py` (novos); `tests/test_isolamento_f4.py` (3 dicts unit ajustados).
- **Docs:** `docs/superpowers/specs/2026-06-24-acesso-multi-loja-design.md`;
  `docs/superpowers/plans/2026-06-24-acesso-multi-loja.md`.

### Frente C — Config financeira da loja / provisões / margem real / comissões (EM SPEC)
Retomada da especificação do painel financeiro com todas as provisões. Consolidada a **tabela
canônica do motor** (config por loja + variáveis de projeto/orçamento/ambiente + fórmulas das
provisões). Decisões fechadas: imposto único (`Prov_Imp`, sem dedup `Imp_Orc`); `%Car_Trib` migra do
modal p/ config da loja (0 até a 1ª versão); margem via `Cust_Var` (inclui `CFO` + `Out_Forn`) e
`Marg_Cont = (Val_Liq − Cust_Var)/Val_Liq`; comissões com base `Val_Liq` (frete local/assist/insumos
sobre `VAVO`; frete fábrica sobre `CFO`). **Comissão de vendas** = rotina por consultor (2
configuradores num modal, regra no backend): faixas por `Val_Liq` mensal acumulado + limitador de
desconto (toggle) que reduz o **%** da venda específica por `%Desc_Orc`. **Faseamento:** v1 = config
`%` simples + margem real (faixas/limitador entram como config); fase 2 = acumulador mensal por
consultor + fechamento de ciclo (provisório→definitivo); fase 3 = custo financeiro absorvido em
`Cust_Var`; futuro = condições de pagamento por loja + divisão de `Com_Adm` por função.
- **Doc/referência (novo):** `docs/modulos/financeiro/PROVISOES_E_VARIAVEIS.md` (tabela + rotina de
  comissão + faseamento).
- **Material âncora:** `FUTURO_CALCULO_FINANCEIRO.md`, `NOMENCLATURA.md`,
  `docs/modulos/financeiro/SPEC.md`, `docs/superpowers/specs/2026-06-15-ciclo-completo-projeto-design.md`
  (§Provisões financeiras), `docs/superpowers/specs/2026-06-22-mecanismo-negociacao-design.md`.
- **Spec/plano:** ainda **não escritos** (próximo passo do brainstorm).

## Sessão 33 — Testes (config financeira) + ajustes de leitura/contrato

Dia de validação manual no browser da Frente C. Achados e mudanças:
- **Modo somente-leitura em projeto fechado** (commit `3183789`): `btn-params` deixa de ser
  escondido com contrato assinado; o modal de Parâmetros abre travado (inputs disabled/readonly,
  Salvar oculto, badge "🔒 somente leitura") e expõe a margem real sob o cadeado de impostos.
- **Fix de visualização de contrato** (commit `4c8076c`): `contrato.pdf_path` de contratos antigos
  foi salvo como caminho ABSOLUTO do Windows (`E:/.../orizon-manager/...`) — não resolve em WSL/Linux
  (case-sensitive) e o contrato não abria mesmo com o PDF presente. `_resolver_pdf_contrato` cai
  para `CONTRATOS_DIR/<basename>`. Aplicado nas rotas `GET /contrato/pdf` e `GET /contrato`.

### ⚠️ PROBLEMAS REGISTRADOS PARA TRATAR (teste e2e do usuário, em breve)
1. **Contrato defasado vs negociação:** num projeto com vários orçamentos, o contrato foi gerado
   de um orçamento (ex.: Cartão) enquanto a negociação exibida está em outro (ex.: Aymoré). O PDF
   é snapshot do momento da geração e não acompanha mudanças posteriores. **A tratar:** vincular
   claramente o contrato ao orçamento de origem e/ou alertar/regenerar quando o pagamento mudar
   após a geração (guard de staleness). Validar no teste e2e do início ao fim.
2. **super_admin não acessa negociação operacional nem `aprovar_financeiro`** — a margem real só
   é visível para diretor/gerente adm-fin (correto por design; registrado p/ alinhamento de UX).
3. **Dados de teste inconsistentes** (Projeto_2 sem etapa 6; contratos antigos): preferir um teste
   e2e limpo (criar projeto pela UI do início ao fim) a remendar seed.

### DEFERIDOS da Frente C (follow-ups, não bloqueiam):
- Edição de `Out_Forn` (sem rota PATCH ainda); wiring de `parametros_default_loja` na criação do
  projeto (carga_trib da loja ainda não flui ao Prov_Imp); acumulador mensal da comissão (Fase 2).

## Sessão 34 — Close-out da Frente C (autônomo)

Trabalho autônomo (usuário ausente) fechando os follow-ups da Frente C. Tudo na branch
`feat/config-financeira-provisoes` (empilhada). Suíte: **357 passed**.
- **P2 — wiring `parametros_default_loja`** (`3d13947`): `_negociacao_breakdown` carrega a config da
  loja uma vez no topo; projeto sem `parametros_json` herda os defaults de negociação da loja
  (a `carga_trib` da loja passa a fluir ao `Prov_Imp`/margem). Projetos com params próprios: intactos.
- **P1 — edição de `Out_Forn`** (`4911c8d`, `92a2222`, `059c7c5`): rota `PUT /api/orcamentos/<id>/out-forn`
  (espelha `/descontos`, escopo + IDOR), campo editável no painel de apoio do modal de Parâmetros
  (travado em modo read-only), recálculo da margem na hora. Fix de revisão: clamp `out_forn>=0` +
  validação de corpo (400) + testes de IDOR/clamp.
- **P3 — guard de contrato desatualizado** (`1382ad9`, `66f4fcc`): `mod_contrato.contrato_desatualizado`
  compara o snapshot `pagamento_json` com a `forma_pagamento` atual do orçamento de origem (tipo +
  total); `GET /contrato` devolve `desatualizado`; banner de aviso na etapa Contrato. Resolve o
  achado da Sessão 33 (contrato Cartão × negociação Aymoré).

## Sessão 35 — Provisões versionadas + faxina de branches

- **Frente "Provisões versionadas + aprovação financeira"** implementada (SDD, 6 tasks TDD,
  suíte 369, review final READY TO MERGE) e **mergeada na `main`**: tabela `provisao_registro`
  (venda/rev1/rev2), `mod_provisoes.itens_provisao`/`cust_var_marg_cont`, "Venda" congelada na
  geração do contrato, rotas `GET/POST /api/orcamentos/<id>/provisoes` (Concorda/Revisa com senha
  `aprovar_financeiro`, 409/IDOR/clamp), e o botão "Provisões" na etapa de Aprovação Financeira
  (tabelas Venda|Rev1|Rev2|Atual). Spec/plan em `docs/superpowers/{specs,plans}/2026-06-27-*`.
- **Faxina de branches:** apagadas as 5 da Frente C (já mergeadas) + `feat/multitenant-f2-tenancy`
  (mergeada) + `master`. A `master` continha um commit "v2.0.0" (Total Flex / Venda Programada /
  Cartão X) — **conferido**: a `main` já tem esses arquivos (venda_programada/cartao_x idênticos,
  total_flex mais novo), v2.0.0 superado → descartado sem perda.

### Isolamento multi-tenant de pool/medição/ciclo — F4 conferido e DISPENSADO
O worktree `worktree-agent-a3876ec2c1cd36c64` tem o commit `1aa8231` "feat(isolamento): escopo de
pool/medicao/ciclo (F4)" (2026-06-21), que adicionava guard de loja (`escopo_operacional` +
`_projeto_da_loja → 404` + 401/403) a pool/medição/ciclo. **Verificado rota a rota: a `main` JÁ tem
esse guard em todas** — `/ciclo`, `/ciclo/desfazer_aprovacao`, `/medicao`, `/medicao/arquivo`,
`/medicao/solicitacao`, `/medicao/parecer`, `/pool`, `/pool/criar_forcado` (a main tem 31 pontos com
`_projeto_da_loja`, implementados nas frentes multi-loja/árvore posteriores). F4 é **redundante** —
não reaproveitar (aplicá-lo só geraria conflito nas mesmas rotas já reescritas). Worktree mantido
como está (gerenciado pelo ambiente).

## Sessão 36 — E2E do início ao fim + faxina de artefatos de contrato

Suíte: **371 passed**. Tudo na `main`.

### E2E do início ao fim (`tests/test_fluxo_completo_e2e.py`)
Servidor HTTP real + login real (harness do conftest), dois fluxos:
- **`test_fluxo_completo_inicio_ao_fim`** — login → negociação (motor + margem real: VBVO/CFO/Val_Liq/
  Cust_Var/Marg_Cont) → `Out_Forn` reflete no Cust_Var → ciclo carrega → "Venda" registrada (hook) →
  **Provisões**: Venda → Rev 1 (Concorda = cópia) → Rev 2 (Revisa = edita Out_Forn, margem recalcula
  da base congelada) → **consistência** (negociação muda após a Venda → `desatualizado=true`) →
  **IDOR** (diretor de outra loja → 404).
- **`test_contrato_real_geracao_e_assinatura`** — **geração REAL** do contrato via
  `POST /api/projetos/<n>/contrato` (gera o `.docx` por python-docx) → `para_assinatura` (+ aviso de
  LibreOffice ausente, degradação graciosa) → hook real grava a Venda → arquivo servível
  (`GET /contrato/pdf` 200) → **assinatura loja + cliente** → `assinado`, etapa 7 concluída,
  projeto `fechado`. Hermético: fixture `contratos_dir` isola `CONTRATOS_DIR` num temp.

**Limite de ambiente (não do produto):** sem LibreOffice (`soffice`) o contrato sai `.docx` em vez de
PDF — único passo dependente de `soffice`. O PDF real valida-se no ambiente do usuário (com LibreOffice).
Upload de XML coberto por `test_qualidade_upload_e2e`; ambiente montado no banco (PoolAmbiente).

### Faxina — artefatos de teste de contrato
`test_contrato.py` gerava `.docx` de ids mágicos (`contrato_99/8888/9999.docx`) direto na pasta
`CONTRATOS/` do repo (não isolava `CONTRATOS_DIR`). Adicionada fixture `autouse` que redireciona
`CONTRATOS_DIR` para um temp; artefatos antigos (untracked) removidos. Confirmado: rodando a suíte
completa, nenhum `.docx` novo é escrito no repo. Contratos reais (`contrato_1..15`) preservados.

## Sessão 37 — Etapa Orçamento como hub + Imprimir Orçamento (proposta)

Frente desenhada (brainstorm→spec→plano) e implementada (SDD, 5 tasks TDD, suíte 378, review final
READY TO MERGE) e **mergeada na `main`**. É o 1º documento do banco de documentos da loja (#8).
Spec/plan em `docs/superpowers/{specs,plans}/2026-06-28-*`.

- **Renomear** etapa 4 "Primeiro orçamento" → **"Orçamento"** (`mod_ciclo.ETAPA_NOME` + frontend).
- **🖨 Imprimir Orçamento** na negociação (junto de Salvar/Aprovar).
- Card da etapa **Orçamento**: lista os orçamentos (Abrir → negociação; Imprimir → proposta).
  Card da etapa **Aprovação**: orçamento aprovado (`contrato.orcamento_id`) com Abrir/Imprimir.
- **Proposta** (`mod_proposta.py`, reusa `_substituir_marcadores`/`_montar_mapping`/`construir_contexto`
  de `mod_contrato`) a partir do template **global** `modelo_proposta.docx` (base 1ª pág do contrato,
  sem cláusulas). Rota `GET /api/orcamentos/<id>/proposta/pdf` — **sob demanda, sem salvar**
  (gera em `tempfile.mkdtemp`, serve inline, remove o temp), escopo por loja + IDOR 404 + 401.
  Sem LibreOffice → entrega `.docx` (degradação graciosa). `_converter_pdf` ganhou `outdir`
  (default `CONTRATOS_DIR` — contrato inalterado).

### Defers (não bloqueiam; do review final)
- Genericizar o corpo do 500 da rota (`str(e)` pode ecoar caminho interno — padrão do codebase).
- Remover o `import mod_proposta as _mprop` redundante na rota.
- Conferência visual no browser (botão Imprimir, lista de orçamentos, orçamento aprovado, abrir inline).

### Banco de documentos #8 — pendente
A lista "etapa → documento" NÃO foi encontrada (busca em todos os transcripts + docs). Fonte provável:
`1_FLUXO_DE_PROCESSOS.docx` (não está no repo, só com o usuário). Próximo passo do #8: obter essa lista.

## Sessão 38 — Lista de ambientes com valor no contrato (branch `feat/ambientes-valor-contrato`)

Frente desenhada (brainstorm→spec→plano) e implementada por SDD (5 tasks TDD, suíte **385**),
**na branch `feat/ambientes-valor-contrato`** (empilhada sobre a `main`). Spec/plano em
`docs/superpowers/{specs,plans}/2026-07-01-ambientes-valor-contrato*`. **Ainda não mergeada** —
aguarda revisão final de branch + conferência visual do usuário.

- **Capa do contrato** ganha a seção **"4. Ambientes"** (a "Forma de Pagamento" passa a **"5"**),
  uma linha por ambiente do orçamento com o **valor com financiamento** + linha **Total** = `TOTAL_CONTRATO`.
- **Valor por ambiente** = `Val_Cont_Amb = VAVA × (Val_Cont / VAVO)` — rateio do custo financeiro
  proporcional ao VAVA (mesma conta que a tela de negociação já mostra na coluna "Com financiamento",
  `static/index.html:5677`). Reconciliação de centavos no **último** ambiente (Σ = `Val_Cont` ao centavo).
  Função pura `mod_contrato.ambientes_valor_contrato`.
- **`mod_contrato._preencher_ambientes`** monta a tabela em código e a insere **antes** da grade de
  parcelas (via `addprevious`); ambas as colunas justificadas à esquerda; células de valor entram nas
  regiões editáveis do contrato protegido (a linha Total, não).
- **Robustez:** `_preencher_grade` deixou de usar índice fixo (`doc.tables[3]`) e passou a localizar a
  grade **por conteúdo** (`_localizar_tabela`, cabeçalho "forma de pagamento"), imune ao deslocamento.
- **Fiação:** helper `_ambientes_valor_para_contrato` (reusa `_negociacao_breakdown`; mapeia
  `pool_ambiente_id → nome_exibicao`) injeta `_ambientes` no ctx nas **duas** rotas de geração —
  `POST` (criação) e `PATCH` (edição/regeneração). E2E real cobre as duas (guard RED→GREEN da PATCH).

### Escopo / próxima frente
- **Só o contrato** nesta frente. **Recriar o `modelo_proposta.docx`** para espelhar a 1ª página do
  contrato (incluindo esta tabela de ambientes) é a **frente seguinte** (spec própria).

### Notas / follow-ups (não bloqueiam)
- A rota **PATCH** de contrato **não degrada graciosamente** sem LibreOffice (devolve 500, ao contrário
  da POST que entrega o `.docx` com aviso) — **pré-existente**, candidato a follow-up. O `.docx` é
  gerado mesmo assim; o E2E verifica a seção no arquivo (aceita status 200|500).
- Minors (para a revisão final): assertions do E2E checam headers, não valores; `_ambientes_valor_para_contrato`
  usa fallback nome vazio para id sem match (sem log); alinhamento do título "4. Ambientes" não setado explícito.

## Sessão 39 — Contrato em HTML/Markdown → PDF (WeasyPrint); aposenta o Word (branch `feat/contrato-html-pdf`)

Reescrita do gerador de contrato: sai o template `.docx` + LibreOffice, entra **HTML (capa) +
Markdown (cláusulas) → PDF via WeasyPrint**. Motivação: a numeração automática de listas do Word era
frágil (números/alinhamento quebravam de forma imprevisível). Spec/plano em
`docs/superpowers/{specs,plans}/2026-07-02-contrato-html-pdf*`. Executado por SDD (12 tasks TDD),
**na branch `feat/contrato-html-pdf`** (empilhada sobre a `main`). Suíte **376 passed / 0 failed**.

- **Motor** (`mod_contrato.py`): `gerar_pdf_contrato(id, ctx)` monta a **capa em HTML**
  (`_html_capa` — linhas dinâmicas de ambientes/parcelas), converte `contrato.md`→HTML
  (`_html_corpo`), embrulha no shell, substitui `[MARCADORES]` (`_substituir_marcadores_html`) e
  renderiza com **WeasyPrint**. Assets versionados em `contrato_template/`
  (`contrato.md`, `contrato.css`, `contrato.html`, `logo_dalmobile.png`).
- **Cláusulas — números literais (Opção A):** o `contrato.md` tem os números como texto
  (`1.1.`, `a)`); o CSS cuida do recuo por nível + *hanging*. Decisão-chave: **exatidão jurídica >
  numeração automática**. O `_html_corpo` processa **linha a linha** (Markdown só inline) para NÃO
  acionar a lista ordenada do Markdown (`1.` viraria `<ol><li>` com número dobrado).
- **Migração do texto:** `scripts/extrair_clausulas_docx.py` — como a numeração do `.docx` é
  automática (não está em `p.text`), a fonte é o **export em TXT do LibreOffice** (achata a numeração
  em texto literal). Limpeza de tabs, quebras de linha soltas, alínea `d)`, campos de preenchimento
  do 2.3.4.1. **Revisão jurídica final do `contrato.md` recomendada** (pendência: 3.6 ausente na origem,
  mantida).
- **Capa:** cabeçalho corrido (logo Dalmóbile + subtítulo da rede + número/data à direita), linha do
  consultor, seções 1–5 (ambientes 2/linha + traços; grade de parcelas só com linhas usadas). Quebra
  de página → cláusulas na página seguinte; rodapé "Página X de Y".
- **Corte limpo:** removidos do CONTRATO o caminho `.docx` (`preencher_contrato`, `_preencher_*`,
  `_set_cell_text`, `_localizar_tabela`, `_proteger_editaveis`, `_MODELO`), a rota `/contrato/editar`
  e o botão no frontend. **Assinatura inalterada** (hash em DB). Os helpers docx/LibreOffice
  (`_substituir_marcadores`, `_subst_paragrafo`, `_converter_pdf`, `LibreOfficeIndisponivel`) **ficam**
  — `mod_proposta.py` (Proposta, ainda docx) os usa.
- **Deps:** `weasyprint` + `markdown` (apt no servidor; pip no dev). LibreOffice permanece **só para a
  proposta**.

### Escopo / próxima frente
- **Só o contrato.** Migrar a **proposta** (`modelo_proposta.docx`) para o mesmo motor é a frente
  seguinte (reaproveita `_html_capa`/CSS). `contrato_editar.py` ficou órfão (candidato a limpeza).
- **Pendências:** fonte de config do `[REDE_IDENTIFICADOR]` (hoje fallback = cidade da loja);
  revisão jurídica final do `contrato.md`.

## Sessão 40 — Merge do contrato HTML/PDF na `main` + refinamentos de formatação (2026-07-02)

Fecha a frente da Sessão 39: a branch `feat/contrato-html-pdf` foi **mergeada na `main`** (fast-forward).
O merge estava bloqueado por um *lock* do Word sobre `modelo_contrato_mapeado.docx` (git não conseguia
escrever o arquivo); com o Word fechado, foi limpo. Suíte na `main` mergeada: **379 passed / 0 failed**.
Branch `feat/contrato-html-pdf` **removida** após o merge.

**Refinamentos de capa/corpo após o usuário revisar o PDF real** (commit `6b1085f` —
`contrato.md` + `contrato.css` + `mod_contrato.py`):
- **Preâmbulo** num único parágrafo justificado (não mais fragmentado em ~4 quebras).
- **Assinaturas:** rótulo com o nome ao lado (`Contratada:`/`Contratante:`/`Testemunha 1:`/`2:`);
  espaço entre a linha de assinatura e o nome; espaço antes da data (`.data-fecho`) e antes do
  fecho "E assim, por estarem…" (`.fecho`).
- **Cláusulas em recuo de BLOCO** por nível (`text-indent: 0` + `padding-left` 0.6/1.2/1.8cm): a 2ª
  linha alinha com a numeração (antes o *hanging* deslocava à direita).
- **Capa:** removida a barra sobrando ao lado do nº de parcelas em "5. Forma de Pagamento"; logo
  recortada (tira faixa branca à esquerda) p/ alinhar "Dalmóbile" com o subtítulo da rede.

**Pendências (mantidas):** fonte de config do `[REDE_IDENTIFICADOR]` (hoje = cidade da loja);
revisão jurídica final do `contrato.md` (cláusula 3.6 ausente na origem, mantida).

## Sessão 41 — Cadastro de parceiro por usuário de loja (branch `fix/parceiro-vinculo-loja-automatico`)

Bug pego em teste de produção: **consultor/gerente não conseguiam cadastrar parceiro**. O form
montava a lista de lojas via `/api/admin/lojas` (restrito a `gerir_lojas`/`editar_dados_loja`), então
usuários de loja recebiam lista vazia e a validação *"Selecione ao menos uma loja"* barrava tudo.

- **Backend** (`main.py`): `_aplicar_abrangencia_parceiro` vincula automaticamente à **loja ATIVA do
  ator** quando `abrangencia='loja'` e nenhuma loja é enviada; `POST /api/parceiros` **sempre** aplica
  abrangência (default `loja`) → parceiro nunca nasce órfão/invisível.
- **`/api/auth/me`** (`auth_routes.py`): passa a informar `rede_id`/`rede_nome` de cada loja, para o
  front decidir se oferece a abrangência de rede.
- **Frontend** (`static/index.html`, `parCarregarOpcoesTenant`): usuário com loja operacional vê o
  vínculo automático à sua loja e a opção **"Toda a rede — <nome>"** apenas se a loja pertence a uma
  rede; admin multi-loja (super_admin/admin_rede) mantém o seletor de lojas/redes.
- **Permissão inalterada:** qualquer usuário logado da loja pode cadastrar parceiro (decisão do
  usuário) — só fica restrito à própria loja/rede.
- **Testes:** `tests/test_parceiro_vinculo_loja.py` (5 E2E com consultor); seed ganhou um `consultor`
  e o `rede_id`. Suíte **384 passed**. Mergeada na `main` (ff, `d9e6f6e`); branch removida.

## Sessão 42 — Lote de ajustes de teste em produção (branch `fix/contrato-ui-ajustes`)

Rodada grande de ajustes durante teste em produção (13 commits, suíte **395 passed**), mergeada na
`main`. Principais:

- **Etapa Contrato (UI):** remove borda verde do badge "para_assinatura", remove o botão grande de PDF
  (mantém o pequeno), botão **Revisar** pede senha gerencial e devolve o contrato à fase de Orçamento
  (reabre etapa 4), "Editar Adendo" → botão "Inserir"; remove o botão "Avançar — Aprovação Financeira".
- **Contrato (conteúdo):** adendo vai ao **final, após as assinaturas, em itálico** (sem página isolada);
  cache-busting no link do PDF.
- **Negociação/parâmetros:** toggle "incluir custos" nasce **true**; com **parceiro**, comissão do
  arquiteto (% do parceiro; senão default da loja) e **fidelidade** entram ativas; endpoints de
  parâmetros herdam os defaults da loja; **valores salvos são respeitados** (semente do parceiro só
  inicial). Fidelidade entra sempre que há parceiro.
- **Ciclo:** eliminadas as etapas **5 (Revisão)** e **6 (Aprovação do orçamento)** — vai de Orçamento (4)
  direto para Contrato (7). Etapa **2 (Criação do Projeto)** ganha o **parceiro (arquiteto)** com
  inserir/alterar/remover, travado só quando **ambas** as partes assinam. Etapa **1 (Cadastro)** segue
  editável após a assinatura; **fix** do telefone defasado (GET do projeto enriquece o cliente com dados
  vivos).
- **Escopo por projetista:** Consultor vê só os projetos que **criou** (+ legados sem criador); gerente
  de vendas e acima veem todos. Nova coluna `projetos_meta.criado_por_id` (+ migração). Escopo aplicado
  na listagem e na abertura; hardening IDOR dos demais endpoints por-projeto fica como follow-up.
- **Provisões:** "Instalação Local" → **"Insumos Locais"**; **CFO** como 1ª linha; **fix** da Margem de
  Contribuição (era exibida ÷100 no modal); bloco informativo de **custos adicionais** (arq/fidelidade/
  viagem/brinde + total) e **custo financeiro**, sempre visível (já descontados do Val. Líquido, não
  somam no Cust_Var).

Testes novos: `test_parceiro_vinculo_loja`(já), `test_escopo_projetista`, `test_projeto_parceiro`,
mais casos em `test_ciclo`/`test_orcamento_params`/`test_provisoes`. **Pendências:** revisão da opção B
das provisões (custos adicionais editáveis recalculando margem) se o usuário quiser; IDOR completo do
escopo por projetista.

## Sessão 43 — Padronização da tela de Negociação + fix desconto por ambiente (main)

Rodada de UI da negociação (5 commits direto na `main`, após o merge da Sessão 42) + 1 correção.
Frontend-only (`static/index.html`), verificação manual. Spec:
`docs/superpowers/specs/2026-07-03-negociacao-ui-uniforme-design.md`.

- **Faixa superior:** Valor Bruto → Desconto → Valor à Vista → **Valor Total do Contrato** (célula
  nova à direita; nas modalidades com financiamento = total parcelado; no À Vista = Valor à Vista).
- **Formulário uniforme (uma linha):** Data do Contrato, Entrada, Data da Entrada + campo específico
  (Aymoré: Carência; Cartão: Bandeira; Total Flex: Prazo; Venda Programada: só os 3). Campos
  calculados/informativos ocultos (1ª parcela, prazo limite).
- **Faixa central** (Contrato a Vista/Parcelado) e **cards de resumo** (`cards-3x2`: Loja Recebe,
  Cliente Paga, Valor/Parcela, Custo Financeiro, Taxa de Retenção, Liquidação…) **removidos de todas
  as modalidades** (ids preservados ocultos; avisos de prazo VP/TF permanecem).
- **Provisão de Impostos:** linha fina uniforme com **cadeado liberável por senha** (mecanismo
  `_renderImpostosLock` intacto; mesmos ids `{p}-r-base-trib`/`-r-impostos`).
- **Fix — desconto por ambiente acima do limite:** revertia o campo mas mantinha o desconto aplicado
  (o motor computava antes da checagem de limite e não re-rodava). Agora re-roda `negPreview()` e
  re-persiste após reverter.
- **"Valor Total do Contrato" editável (cálculo reverso — contraproposta do cliente):** digitar o valor
  de contrato calcula o desconto global e aplica. O campo é o **valor de contrato** (com custo
  financeiro): `financiado = max(0, valor − entrada)`; `valorAvista = entrada + financiado × (1 −
  taxaRet)`; `discPct = (1 − valorAvista/bruto) × 100`. Retenção e entrada capturadas por modalidade
  (globais `_negTaxaRetencaoPct`/`_negEntradaValor`; VP/TF/À-Vista sem retenção; entrada é à vista, sem
  custo financeiro). Bruto robusto via `negValorBrutoAtual` (motor/EP07). Acima do limite do perfil,
  popup "Desconto excede o limite do perfil de usuário, deseja realizar autorização gerencial?" → modal
  gerencial. **Causa raiz do 1º bug:** `_negBaseValues` nunca é populado. Trecho feito com apoio do
  **Fable 5**. Spec (seção 6) atualizado.

## Sessão 44 — Manutenção de ambiente + política do MCP `orizon` (main)

Sessão de infraestrutura/processo (sem mudança de código de app; suíte segue **395 passed**).

- **Renomeação do diretório pai** `E:/2026/estudo_de_ia → E:/2026/desenvolvimento` (feita pelo usuário).
  O repo já vinha renomeado `Omie_V3 → Orizon Manager` (commit `c8eb350`, sessão anterior).
- **`.mcp.json`:** corrigidos os dois mounts do container efêmero do MCP para
  `E:/2026/desenvolvimento/mcp-orizon` e `.../orizon-manager`; arquivo adicionado ao git (`c014884`,
  já pushado). Verificado que **nenhum código Python** tinha o path antigo hardcoded (só entradas
  obsoletas de allowlist em `.claude/`, que são ruído ignorado). MCP reconectado via `/mcp` e validado
  com `cobertura` + `ingerir` (`fonte:"all"` → 893 nós de código, 31 requisitos, 60 banco, 42 decisões).
- **[DECIDIDO] Papel do MCP vs DEV_LOG:** o grafo Neo4j (`../mcp-orizon`) é **camada de consulta**
  estrutural (cobertura, impacto, rastreabilidade), **derivada do código e local (fora do git)** →
  fica obsoleta sem re-ingestão. **Não substitui** o DEV_LOG (fonte narrativa versionada) nem o **git**
  (único controle de versão). Ritual de fechar frente ganhou o passo de **re-ingestão** após o push.
  Codificado em `CLAUDE.md` (passo 6 + seção "MCP `orizon`") e `DEV_RULES.md` (checklist + seção
  dedicada).
- **Push da `main`:** funciona nesta máquina (Git Credential Manager do usuário) — feito nesta sessão.
  A antiga seção "🔼 PENDÊNCIA: PUSH" (que assumia ambiente sem credenciais) foi **removida**.
- **Repositório GitHub renomeado** `omie_v3 → orizon-manager` (via API `PATCH /repos`, HTTP 200, com a
  credencial do GCM) e **remote local atualizado** (`git remote set-url origin
  https://github.com/mbnunes1972/orizon-manager.git`); `fetch` validado, `main` sincronizada com
  `origin` (0 à frente). GitHub redireciona o nome antigo por um tempo, então nada quebra.
- **Deploy completo no VPS de produção (167.88.33.121) — feito e validado.** O servidor estava em
  código de 24/06 (commit `895e5f6`, sessão ~31), diretório `/root/omie_v3`, banco `omie.db`, remote
  antigo. Executado o runbook de migração+deploy via SSH (chave ed25519 instalada nesta sessão →
  login sem senha): **backup** do banco (`orizon.db.bak-...`), parada do app, rename `omie_v3 →
  orizon-manager` e `omie.db → orizon.db` (dados preservados: 11 usuários/2 clientes/3 projetos/6
  orçamentos/1 loja), `git reset --hard origin/main` até `ca05a61`, **weasyprint instalado via apt
  (61.1)**, restart no screen `orizon-manager` com `ORIZON_HOST=0.0.0.0`. **Auto-migração** de schema
  rodou limpa na subida (`usuario_lojas_backfill_2026`). Validado: porta 8765 em `0.0.0.0`, `/login`
  **HTTP 200** externo. **[CONTEXTO] Ajuste no runbook:** o screen de produção chamava-se `omie` (não
  `omie_v3`) e o env var antigo era `OMIE_HOST` — o runbook do `DEV_RULES.md` assume nomes que já não
  batiam; hoje está tudo padronizado (`orizon-manager`/`ORIZON_HOST`).
- **[PENDENTE-BAIXA] weasyprint 61.1 no VPS vs 69 no dev local:** conferir um contrato PDF real gerado
  em produção (possíveis diferenças de CSS entre versões). App não depende dela para subir (import lazy).
- **[PENDENTE-BAIXA/segurança] `authorized_keys` do root no VPS** tem chaves de terceiros
  (`igorferreiradaniel99@hotmail.com`, `idaniel@Mac.bbrouter`) + uma linha corrompida da 1ª tentativa de
  instalação — revisar/limpar quem tem acesso root ao servidor.

## Sessão 45 — Subfases do Projeto Executivo (etapa 11) — branch `feat/pe-subfases`

Frente desenhada via brainstorming (spec `docs/superpowers/specs/2026-07-04-projeto-executivo-subfases-design.md`)
e implementada por **subagentes** (plano `docs/superpowers/plans/2026-07-04-projeto-executivo-subfases.md`),
task a task com review de spec + qualidade. **Ainda em branch — não mergeada na `main`.**

- **[ESTADO]** Subfases 11a/11b/11c/11e enriquecidas: upload de documentos **append-only** (nunca
  sobrescreve → registro evolutivo), botões de transição nomeados ("Encaminhar para PE", "Projeto
  Alinhado", "Concluído", "Concluir Projeto Executivo"), e **revisão** (11b/11c) com **reabertura em
  cascata** + relatório complementar obrigatório. Concluir 11e conclui a etapa-mãe 11. Medição (etapa
  10) permanece **inviolável** (o PE só lê/linka).
- **[DECIDIDO] Dados (abordagem B):** 2 tabelas novas `ciclo_documentos` + `ciclo_revisoes` (chaveadas
  por projeto+etapa_codigo); status/datas continuam no `CicloEtapa`. Arquivos em
  `PROJETOS/<nome>/ciclo/<etapa>/<uuid>_...`. Documentos append-only; commit-antes-do-disco (padrão EP-07).
- **[DECIDIDO] Capabilities (`perfis.py`):** `executar_pe` (Projetista Executivo, Conferente, Gerente
  Vendas, Gerente Adm/Fin, Diretor) e `revisar_pe` (Gerente Vendas, Adm/Fin, Diretor). A revisão exige
  capability própria porque o `autorizar` do "reabrir em cascata" existente exclui o Adm/Financeiro.
- **[CONTEXTO] Endpoints (`main.py`):** `POST …/ciclo/<codigo>/documento` (multipart), `…/concluir`
  (JSON), `…/revisao` (multipart, cascata); `GET …/ciclo/pe` e `GET …/ciclo/documento/<id>` (download
  via `storage_ler_binario`). Frontend em `static/index.html` (painéis por subfase, progresso N/4,
  handlers com `pedirCredenciaisGerente`). Correção lateral: `esc()` passou a escapar aspas (XSS de
  atributo) — endurece usos pré-existentes.
- **[ESTADO] Testes:** lógica pura em `tests/test_ciclo.py`; e2e HTTP em `tests/test_ciclo_pe_e2e.py`
  (upload append-only, guardas de conclusão, 11e conclui 11, revisão reabre em cascata, permissões,
  download, medição intocada). Suíte **~412 passed** (1 falha pré-existente do weasyprint no local).
- **[PENDENTE]** Verificação **manual no navegador** do frontend (Tasks 8/9 não têm teste JS): botões
  por perfil, upload/conclusão/revisão, indicador de progresso. Merge na `main` + push + re-ingestão
  do grafo após a conferência.

## Sessão 46 — Etapas operacionais 12/13/14 (Implantação · Produção · Entrega) — branch `feat/etapas-operacionais`

Frente desenhada via brainstorming (spec `docs/superpowers/specs/2026-07-05-etapas-operacionais-implantacao-producao-entrega-design.md`)
e implementada por **subagentes** (plano `docs/superpowers/plans/2026-07-05-etapas-operacionais-implantacao-producao-entrega.md`),
task a task com review de spec + qualidade. **Mergeada na `main`** (fast-forward de 9 commits) após
verificação manual no navegador ("Funcionou"); branch `feat/etapas-operacionais` **deletada**; push +
re-ingestão do grafo (código 945 nós) feitos.

- **[ESTADO]** Etapas principais **12/13/14** ganharam painéis dedicados (deixam o card genérico):
  - **12 Implantação do pedido:** upload **append-only** de XMLs ("Carregar Pedidos") + "Encaminhar
    Pedidos à Fábrica" (fecha; exige ≥1 XML). Integração real com a fábrica = **futuro** (o botão só
    fecha por ora).
  - **13 Produção:** "Inserir/Salvar Números dos Pedidos" (lista, texto — os números **vêm da
    fábrica** como resultado da implantação) + "Produção Concluída" (fecha; exige números).
  - **14 Entrega no depósito:** "Salvar Relatório de Entrega" (texto livre de **faltas e avarias**) +
    "Concluir Relatório de Entrega" (fecha; exige relatório não-vazio). Removido o `toggleavel` da 14.
- **[DECIDIDO] Arquitetura C:** **sem tabela nova, sem capability nova, PE intocado.** XMLs reusam
  `CicloDocumento` (tipo `implantacao_pedido_xml`); números/relatório em `CicloEtapa.observacoes` das
  etapas 13/14. Conclusão e salvar-texto reusam o `PATCH /ciclo/<codigo>` existente. **Cycle-gated**
  (qualquer usuário que já pode avançar o ciclo — ao contrário do PE, que exige `executar_pe`).
- **[CONTEXTO] Endpoints (`main.py`):** `POST/GET …/ciclo/<codigo>/pedido-xml` (upload/listagem da 12,
  append-only, cycle-gated) + **guarda operacional** no `PATCH /ciclo` (`mod_ciclo.guarda_conclusao_operacional`)
  que barra a conclusão de 12/13/14 sem XML/números/relatório. Guarda pura em `mod_ciclo`
  (`ETAPAS_OPERACIONAIS`, `tipo_doc_operacional`, `guarda_conclusao_operacional` — falha explícita em
  `exige` desconhecido). Frontend: `_renderCardImplantacao/Producao/Entrega` + handlers com `_patchEtapa`
  DRY; `esc()` em todo conteúdo dinâmico.
- **[ESTADO] Testes:** lógica pura em `tests/test_ciclo.py`; e2e HTTP em `tests/test_ciclo_operacional_e2e.py`
  (upload append-only/listagem, guardas de conclusão de 12/13/14, gating sequencial preservado,
  cycle-gated com consultor, PE intocado). Suíte **431 passed**. Reviews de spec+qualidade por
  subagente em cada task (fixes aplicados: footgun do `exige`, DRY do `encaminhar`, upload não falseia
  sucesso).
- **[PENDENTE]** Verificação **manual no navegador** (Task 4 sem teste JS; `node` indisponível no
  ambiente): botões/gating por etapa, upload/download de XML, salvar/concluir números e relatório,
  reabrir (gerente). Depois: merge na `main` + push + re-ingestão do grafo.

## Sessão 47 — Integração NF-e (Fábrica→Loja): guinada Omie→Focus NFe + Fases 1-2 (branch `feat/nfe`)

**Guinada de arquitetura:** o motor fiscal deixou de ser o **Omie** e passou a ser a **Focus NFe** (API
REST direta, Plano Solo). Decisão-chave descoberta na doc: **a Focus NÃO calcula imposto** — nós
fornecemos CST/CSOSN/CFOP/alíquotas por item. O que o Omie fazia sozinho vira nosso (Fase 3). O
parser/precificação (Fase 1) é engine-agnostic e não muda. Roadmap em 5 fases + cross-cutting
(Rede→Loja→config fiscal, perfil de emissão, NFS-e adiada). Specs/planos em `docs/superpowers/`.

- **[ESTADO] Fase 1 (parser+precificação):** só **spec** (`mod_nfe.py` a implementar). Evidência: 5 NF-es
  reais da fábrica em `E:/2026/desenvolvimento/nfe-dalmobile` (**fora do git**; 149 linhas→95 distintos,
  `cProd=BASE[ID]`, consolida duplicados, IPI 100%, `infAdProd` "COR L A" **não-confiável**). Fixtures
  serão anonimizados. **Fábrica é CRT3-com-IPI; a LOJA emissora é Simples** (CSOSN).
- **[IMPLEMENTADO] Fase 2 (contrato + transporte), suíte 457:** `emissor_fiscal.py` (ABC `EmissorFiscal`
  + DTOs `ResultadoEmissao`/`StatusNota` + normalizador `resultado_de_focus`), `focus_config.py`
  (`base_url_de` homolog/prod + loader `focus_config.json` gitignored), `focus_client.py` (`FocusClient`:
  `enviar_nfe` POST `/v2/nfe?ref`, `consultar_nfe` GET, `cancelar_nfe` DELETE com justificativa 15-255,
  `baixar`, `aguardar_processamento` polling determinístico; retry/backoff 5xx/429/conexão espelhando
  `omie_post`; `FocusError`; tolera corpo JSON não-dict). Testes com `requests`/`time.sleep` mockados —
  **zero rede**. Endpoints/auth (Basic token, senha vazia) confirmados na doc da Focus. Concreto
  `EmissorFocusNfe` + payload/impostos = **Fase 3**.
- **[IMPLEMENTADO] Fase 1 (`mod_nfe.py`, branch `feat/nfe-fase1`):** parser+precificação puros —
  `parse_nfe` (namespace-aware; localiza `infNFe` sob `nfeProc` ou `NFe` puro; vIPI ausente→0; dest
  CNPJ/CPF), `split_cprod` (padrão/sob-medida), `parse_infadprod` (tolerante, dims só se 2 últimos tokens
  inteiros), `consolidar` (soma duplicados por cProd completo), `precificar` (custo=(vProd+vIPI)/qCom,
  markup %), `preview` (pipeline+totais) e **CLI de eyeball** (`python3 mod_nfe.py <xml> [markup]`).
  Testes (`tests/test_nfe.py`) com **fixtures anonimizados**. CLI conferido nos XMLs reais (NFe-170942 →
  linhas=21 distintos=12). **[Atenção Fase 3]** `custo_total`/`venda_total` somam valores unitários **já
  arredondados** → pode divergir do total fiscal por centavos (reconciliar se comparar com a NF-e).
- **[PENDENTE]** (1) **Token da Focus** (contratação em andamento) → smoke de transporte em homologação:
  `FocusClient(token, base_url_de("homologacao")).consultar_nfe("ref-inexistente")` deve dar `FocusError`
  **404** (não 401). (2) **Perfil fiscal Simples do CNPJ 19.152.134/0001-56** (contador:
  CST/CSOSN/CFOP/alíquotas) — insumo central da **Fase 3**; lucro real/presumido depois. (3) **Fase 3**
  (mapa fiscal loja→payload + `EmissorFocusNfe`) e depois Fases 4-5.
- **[IMPLEMENTADO] Painel de Configuração Fiscal · Sub-frente I (backend), branch `feat/perfil-fiscal`,
  suíte 493:** reformulação da "Fase 3" — antes do mapa fiscal, um **`PerfilFiscal` por CNPJ/loja** que
  alimenta o mapa com dado real (ou placeholder). Entregue: `fiscal_cripto.py` (**Fernet isolado**, chave
  fora do banco via `ORIZON_FISCAL_KEY`→keyfile gitignored, `cryptography` já instalada), `mod_fiscal.py`
  (`perfil_padrao_teste`/`validar_config`/`pode_ativar_producao`/`focus_client_para_loja`), modelo
  `PerfilFiscal` (tabela 1:1 com Loja, auto-criada), e **endpoints** GET + PUT config/segredos/ambiente
  gated por `editar_dados_loja`+tenancy. **Segurança:** tokens Focus só **cifrados** no banco, **nunca**
  no GET/log; **certificado A1 NÃO fica conosco** (vai pro painel da Focus — guardamos só validade+CNPJ);
  **produção bloqueada com placeholder pendente**. **[DECIDIDO] Perfil-padrão de teste** (Simples, CFOP
  5102/6102, CNAE placeholder, ISS 5%, homologação) desbloqueia o desenvolvimento sem o contador; campos
  de teste marcados em `placeholders`. **[PENDENTE Sub-frente II]** o painel deve também exigir token de
  produção antes de permitir trocar para produção (guarda hoje é só por placeholder).
- **[PENDENTE integração NF-e]** (1) **Token da Focus** → smoke em homologação. (2) **Valores fiscais reais
  do contador** (CST/CSOSN/CFOP/alíquotas) — entram como **dado** no PerfilFiscal, sem mudar código.
  (3) **Sub-frente II** (painel no frontend) e **Fase 3b** (mapa fiscal + `EmissorFocusNfe`), depois Fases 4-5.
- **[IMPLEMENTADO] Fase 3b (mapa fiscal, branch `feat/nfe-mapa-fiscal`, suíte 507):** `mapa_fiscal.py`
  (`montar_nota` modelos→nota neutra: emitente Loja+perfil, destinatário Cliente PF/PJ, regime→código,
  CST Simples; `montar_payload` nota→payload Focus: CFOP dentro/fora por UF, CSOSN do perfil, ICMS origem
  0, PIS/COFINS 49, `valor_bruto`, `consumidor_final` condicional PJ=0/PF=1) e `emissor_focus.py`
  (`EmissorFocusNfe(EmissorFiscal)` fecha o contrato da Fase 2 com o `FocusClient` injetado; emitir/
  consultar/cancelar → `resultado_de_focus`). **Testes offline** (client fake, sem emissão real).
  **[Fase 4]** PIS/COFINS CST "49" + CSOSN são Simples-only (marcado `# TODO Fase 4`) — ramificar por
  regime com o contador.
- **[IMPLEMENTADO] Painel Fiscal · Sub-frente II (frontend, direto na `main`):** aba **Fiscal** no admin da
  loja (`adminRenderLoja`) consumindo os endpoints da Sub-frente I — 7 seções (identificação, regime, NF-e,
  NFS-e só-dado, certificado ref, credenciais Focus, perfil de emissão), **badges + checkbox de confirmação**
  por campo placeholder, **credenciais Focus write-only** (nunca ecoadas), **troca de ambiente** com confirm
  + dupla guarda (produção exige token de produção + zero placeholder). Espelha o padrão da aba Financeiro.
  Checagem estrutural OK; **backend 507 verde**. **[PENDENTE] verificação manual no navegador** (do usuário).
  **[GAP]** `cert_validade`/`cert_cnpj` read-only (o PUT config da Sub-frente I não os inclui — ajuste
  pequeno depois). *(Usuário autorizou seguir direto sem os gates de review; revisão depois.)*
- **[CONTEXTO] Fechamento:** Fases 1, 2, **Painel Fiscal Sub-frentes I e II** e **Fase 3b** todas na `main`
  (pushadas e re-ingeridas). **A retomar:** Fases 4-5 (dependem do token da Focus + valores do contador).

## Sessão 48 — NF-e Fase 5: emissão na etapa 15 (orquestração + painel) — branch `feat/nfe-etapa15`

Última peça de código da integração NF-e. Liga o pipeline (Fases 1-4) à **etapa 15 do ciclo**, por projeto,
com painel dedicado. Subagent-driven (implementer + revisão spec + revisão qualidade por tarefa); spec/plano
em `docs/superpowers/{specs,plans}/2026-07-06-nfe-fase5-etapa15-emissao*`. **Suíte 522→531** (12 e2e novos).

- **Decisões (brainstorming):** a **NF-e da fábrica entra na própria etapa 15** (upload append-only — a etapa
  12 segue sendo os *pedidos enviados à fábrica*); **markup por emissão** (campo no painel, default 30);
  **emissão restrita a `editar_dados_loja`** (≠ etapas 12-14 cycle-gated); **1:1** (uma NF-e da loja por XML
  da fábrica); etapa **conclui automático** em `emitida` ao autorizar.
- **Backend:** coluna `NfeEmissao.fabrica_doc_id` (+ migração idempotente em `_migrar_colunas`); `nfe_emissao.emitir`
  ganhou `fabrica_doc_id=` e **carimba o nome SEFAZ do destinatário em homologação** (centralizado — beneficia
  também o `emitir-teste` da Fase 4). 5 endpoints `/api/projetos/<nome>/ciclo/15/…` (gated `editar_dados_loja`
  + escopo): `nfe-fabrica` (upload), `GET nfe` (estado), `emitir-nfe` (`ref` estável `NFE-<projeto>-<doc_id>`
  → idempotente), `nfe/consultar`, `nfe/cancelar` (**cancelar reverte a etapa 15** para não-conclusiva).
- **Frontend:** painel `_renderCardEmissaoNfe` na etapa 15 (roteado como 12/13/14) — carregar NF-e da fábrica,
  markup por linha, emitir, status/chave, **baixar XML/DANFE**, consultar/cancelar; botões UX-gated por
  `_NFE_NIVEIS_EMITE = {diretor, super_admin, admin_rede}` (casa com `perfis.py`; backend é a trava real).
- **Testes:** `tests/test_nfe_etapa15_e2e.py` (emissor mockado via `monkeypatch` de `nfe_emissao._emissor_para`
  — zero rede): upload+estado, 403/401/404/400 (sem arquivo, outra loja, sem perfil), emitir autoriza+conclui+
  idempotência, homologação carimba nome SEFAZ (test no `test_nfe_emissao.py`), produção **não** carimba,
  rejeitada **não** conclui, consultar/cancelar + reversão da etapa.
- **Pendente:** **smoke real em homologação** (só depois do certificado A1 na Focus, 2026-07-07) e **verificação
  manual do painel** (etapa 15 + Painel Fiscal II). Merge da branch pendente da conferência do usuário.
- **[obs. de review, não bloqueia]** cancelar já reverte a etapa; `markup_pct` inválido → custo (comentado,
  só homologação); justificativa de cancelamento validada 15-255 no painel (backend também).

## Sessão 49 — Fiscal: Plano de Faturamento multi-CNPJ (Emitente 1ª classe) — branch `feat/fiscal-emitente-multicnpj`

Correção **estrutural na base** fiscal: desacopla "quem vende" de "quem emite", antes de Comercial/Estoque
reforçarem a premissa. Motivada por auditoria (a emissão assumia 1 venda = 1 CNPJ = 1 documento, quem vende
emite). Subagent-driven, TDD, suíte **532 → 545**. Spec/plano: `docs/superpowers/{specs,plans}/2026-07-06-fiscal-plano-faturamento-multicnpj*`.

- **`Emitente`** (1ª classe): 1 CNPJ + config fiscal + tokens + **endereço próprio** — absorve `PerfilFiscal`.
  `Loja.emitente_id` / `Rede.emitente_central_id`. Migração idempotente `perfil_fiscal → emitente` (preserva
  o **token do smoke** da INSPIRIUM) — com fix crítico: o **rename de tabela roda ANTES do `create_all`**
  (`_migrar_pre_schema`), senão o upgrade perderia os dados de `nfe_emissao`.
- **`PerfilEmissao`** (owner loja|rede, tipo_doc, emitente) + `mod_fiscal.resolver_emitente` (override loja →
  default rede → self) / `resolver_plano` / `focus_client_para_emitente`.
- **`NfeEmissao → DocumentoFiscal`** (+`tipo_documento`, +`emitente_id` distinto de `loja_id`).
- **Emissão de produto re-plataformada:** `montar_nota(emitente,…)`, `emitir(…, emitente_id)`,
  `consultar`/`cancelar` resolvem por `reg.emitente_id`; endpoints resolvem `resolver_emitente(loja,"produto")`.
  **Contratos de API trocados:** `focus_client_para_loja` → `focus_client_para_emitente`; `_emissor_para(emitente_id)`.
  **Multi-CNPJ provado:** teste emite o produto sob o CNPJ da **central da rede** (≠ loja vendedora).
- **NFS-e** segue slot modelado (`emitir_nfse_servico` NotImplemented — US-32).

> ### ✅ GAP config divergente — FECHADO (US-36, 2026-07-06)
> ~~O Painel Fiscal escrevia `PerfilFiscal` mas a emissão lê `Emitente`.~~ **RESOLVIDO** (branch
> `feat/fiscal-painel-emitente`, suíte 561): o **Painel Fiscal agora opera o `Emitente` da loja**
> (`loja.emitente_id`, cria se faltar) com **endereço + CSOSN contribuinte** editáveis; o modelo
> `PerfilFiscal` + `focus_client_para_loja` foram **removidos** (tabela `perfil_fiscal` mantida como legado).
> Editar o painel volta a afetar a emissão. ~~Falta só a US-37.~~ **✅ US-37 IMPLEMENTADA** (branch
> `feat/fiscal-perfil-emissao-ui`, suíte 578): **painel Fiscal da rede** (Emitente central) + **Perfil de
> Emissão em 2 níveis** (default da rede + override da loja: produto/serviço → self|central, via selects).
> A configuração multi-CNPJ agora é 100% pela tela. Resta a **NFS-e de serviço** (US-38/US-32).

- **Pendente:** merge desta branch; migração do painel de config → Emitente (EP-11); NFS-e (US-32). O smoke
  real (cert A1) pode rodar nesta branch (usa o `Emitente`) ou na `main` atual (usa `PerfilFiscal`) — **decidir
  em qual trilho** antes de rodar (recomendado: mergear esta branch e rodar no trilho novo).

## Sessão 50 — Validação de CPF/CNPJ nos cadastros (rejeita número falso) — branch `feat/validacao-cpf-cnpj`

Nenhum cadastro validava o **dígito verificador** — números falsos (o placeholder `012.021.345-01`, `123.123.123-00`)
entravam e só quebravam na SEFAZ (o smoke da NF-e revelou "CPF inválido"). Agora se **rejeita CPF/CNPJ falso** na
origem, em **todos os cadastros**. Documento **segue opcional** (cliente/parceiro): valida-se **só se informado**;
vazio é OK (obrigatório mesmo só na geração do contrato, já existente). Subagent-driven, TDD, suíte **613 → 624**.
Spec/plano: `docs/superpowers/{specs,plans}/2026-07-06-validacao-cpf-cnpj*`.

- **`validacao_doc.py`** (novo, puro, offline — só DV, não consulta a Receita): `valida_cpf`/`valida_cnpj` (módulo 11,
  rejeita repetidos), `doc_valido` (11→CPF, 14→CNPJ), `erro_doc(valor, rótulo, tipo)` → mensagem se informado e
  inválido, `None` se vazio/válido. Aceita com/sem pontuação.
- **Backend autoritativo (400):** validação antes de persistir em **Cliente** (`cpf`/`cnpj`), **Parceiro** (`cpf_cnpj`,
  auto por tamanho), **Usuário** (`cpf`), **Rede** (`cnpj`), **Loja** (`cnpj`) — nos create **e** edit (no edit, só se
  o campo veio no payload). Unicidade de CPF do cliente preservada (roda depois da validação).
- **Frontend inline (UX) no modal de cliente:** `_docValidoCPF`/`_docValidoCNPJ` (espelham o util); aviso `cli-aviso-cnpj`
  (novo) + `cli-aviso-cpf` (agora também DV, antes só duplicata); `cliFormatarCNPJ` (máscara); `cliSalvar` **bloqueia**
  doc falso antes de enviar. Demais cadastros mostram o erro do backend.
- **Não retroativo:** placeholders já gravados só somem via edição. Testes existentes que criavam cadastro via endpoint
  com CPF placeholder inválido foram trocados por **docs válidos** preservando a intenção (ex.: teste de colisão de CPF
  ainda testa 409, agora com CPF válido). CPFs de teste válidos: `111.444.777-35`, `390.533.447-05`; CNPJ `11.222.333/0001-81`.
- **Pendente:** merge desta branch na `main` + re-ingerir MCP.

## ⏸️ ESTADO ATUAL (2026-07-07) — retomar aqui

> **🚀 Deploy no VPS (2026-07-09, mais recente = `3d60a43`):** servidor online `http://167.88.33.121:8765` — **Módulo
> Financeiro completo (#1–#6) + wiring do faturamento + atualização v2→v5 (5 fronts)**. Migrações idempotentes rodaram
> no start (colunas `lancamento.ref/motivo/ia_sugestao`; backfill das 3 provisões no 1º acesso ao Plano de Contas por
> owner). **Banco preservado**, HTTP 302 local / **200 externo**, sem erros. _(Antes → `7ff3cf0`: Financeiro #1–#6 +
> tabelas conta/lancamento/periodo_contabil criadas no start; e `f36b72b`: modularização + design.)_ **Banco PRESERVADO desta vez** (a pedido): NÃO houve
> `rm orizon.db`/seed — as **migrações idempotentes rodaram no start** e adicionaram as colunas novas
> (`Loja.modulos_ativos`, `Usuario.tema` → confirmado presente). Dados de teste do VPS mantidos. **Contexto:** o VPS
> é ambiente **de dev/teste aberto a pessoas remotas**, ainda **não** há produção operacional; dados são falsos.
> **Emitente configurado no VPS (2026-07-08):** o Emitente INSPIRIUM (CNPJ 19.152.134/0001-56, homologação, IM/IBGE/
> cód-serviço/ISS/CSOSN/endereço = espelho do local) foi replicado e `lojas.id=1.emitente_id=1` apontado → `prontidao`
> **pronta p/ produto e serviço** e `resolver_emitente` OK (igual ao localhost). **Segredo tratado com cuidado:** o
> token Focus **homologação** foi decifrado no local, enviado **pelo canal SSH** (nunca no transcript) e **re-cifrado
> com a chave própria do VPS** — a `config/fiscal.key` **local (chave-mestra) NÃO** foi exportada; o VPS gerou a sua
> (perm 600). Temporários (`tok_tmp`) apagados. Token de **produção** segue indefinido. Senhas são acessíveis de fora.
> **Nota:** este commit de doc (o próprio banner)
> fica 1 à frente do VPS — doc-only, não exige re-deploy. **Runbook via arquivo** (`bash /root/deploy_once.sh`, deixado
> no VPS): evita o self-kill do `pkill -f main.py` (o argv inline conteria `main.py`); ver `DEV_RULES.md`.
> _(Deploy anterior: 2026-07-07, `ca05a61`→`ce209ad`, com banco recriado limpo.)_

**Módulo Fiscal / NF-e completo e na `main`** (suíte **650**, tudo mergeado+pushado; auditoria fiscal 100% endereçada):
Fase 5 (etapa 15) · **multi-CNPJ** (Emitente 1ª classe, DocumentoFiscal) · **destinatário 3 tipos**
(contribuinte/isento/não-contribuinte) · **painel de config → Emitente** (US-36) · **UI do Perfil de Emissão**
(US-37: painel Fiscal da rede + política produto/serviço → self|central em 2 níveis) · **NFS-e de serviço**
(US-38: emite montagem via `/v2/nfse`, valor manual, no painel da etapa 15 — **faturamento produto+serviço
completo**). Tudo **mergeado na `main`** (US-36/37/38).
**🎉 SMOKE REAL AUTORIZADO** — NF-e de **produto** da INSPIRIUM emitida pela SEFAZ.
**🎉 SMOKE NFS-e AUTORIZADO (2026-07-07)** — a INSPIRIUM emitiu NFS-e **autorizada** por São José dos Campos
(homologação): nº 1, cód. verificação `LWWCfsDUg`, XML + DANFSE gerados (`homol-notajoseense.sjc.sp.gov.br`).
O smoke foi na camada do emissor com **ref único** (RPS rejeitado é morto → emite-se novo) e **sem gravar
DocumentoFiscal**. Sequência de correções descoberta (cada uma destravou o próximo motivo de rejeição):
> 1. **E70** (Inscrição Municipal ausente) → **DADO**: preenchido no Emitente (IM `322176`, cód. serviço
>    `14.13.03`, município IBGE `3549904`, CNAE `4330404`, ISS 5%). ✅
> 2. **E188** (Simples Nacional conflita com Regime Especial de Tributação) → **CÓDIGO**: o payload NFS-e
>    precisa enviar, no topo, `optante_simples_nacional` (derivado de `emitente.regime_tributario=='simples'`),
>    `regime_especial_tributacao="6"` (ME/EPP do Simples) e `natureza_operacao="1"`. **Hoje `montar_payload_nfse`
>    NÃO envia** → o endpoint real ainda cairia aqui.
> 3. **L999** ("Tomador Não Identificado para a atividade") → **CÓDIGO**: o tomador precisa de
>    `endereco.codigo_municipio` (IBGE). Isolado: o `codigo_municipio` **sozinho** resolve (CEP inválido é
>    tolerado). **Hoje `montar_payload_nfse` NÃO envia** o IBGE do tomador — e o **Cliente não tem `municipio_ibge`**
>    (só cidade/UF): falta origem do dado (resolver por cidade/UF ou novo campo).
>
> ### ✅ US-39 — payload NFS-e completo — IMPLEMENTADO (2026-07-07, branch `feat/nfse-payload-us39`, suíte 632)
> `mapa_fiscal.montar_payload_nfse` agora envia, no topo, `optante_simples_nacional` (derivado de
> `emitente.regime_tributario=='simples'`), `regime_especial_tributacao="6"` (ME/EPP do Simples; só quando optante)
> e `natureza_operacao="1"`; e `codigo_municipio` (IBGE) no `tomador.endereco`. Novo campo `Cliente.municipio_ibge`
> (migração idempotente), capturado via **ViaCEP** no modal (o ViaCEP devolve `ibge`) + **backfill best-effort**
> por CEP na emissão (`_ibge_por_cep`, offline-safe) para clientes antigos. **Smoke pelo caminho real de código →
> NFS-e AUTORIZADA** por SJC. RET=6/natureza=1 são defaults documentados (MEI seria 5; refinar quando o Emitente
> distinguir). **Pendente:** merge + re-ingerir MCP.

Pendências fiscais: re-smoke via **endpoint da etapa 15** (server+login, com um projeto de serviço) — o caminho de
código já foi provado · refinamentos (CSOSN por operação; não-contribuinte PJ; RET MEI=5) · **dados reais** (CPFs/CEPs
válidos dos clientes; muitos hoje são placeholder → sem IBGE resolvível) · verificação manual dos painéis.

**Validação de CPF/CNPJ (Sessão 50, na `main`, suíte 624):** todos os cadastros
(Cliente/Parceiro/Usuário/Rede/Loja) **rejeitam número falso** (dígito verificador) no backend + inline no
modal de cliente; documento segue **opcional** (valida só se informado). Mergeado + MCP re-ingerido.

**Avaliação + Auditoria fiscal (2026-07-07):** docs em `docs/avaliacao/` — revisão por frente (02-07/07),
mapa de testes para leigo (22 testes de tela) e **auditoria adversarial do módulo fiscal** (14 achados).
Veredito: isolamento multi-tenant e segredos sólidos; riscos em chave local, beco-sem-saída da NFS-e e
hardcodes fiscais. **🔴 Altos corrigidos** (branch `feat/fiscal-altos-auditoria`, suíte 641): **A1**
(.gitignore da chave Fernet), **US-42** (`prontidao_emitente`: barra produto fora do Simples / UF vazia e NFS-e
sem IM/IBGE/cód-serviço/alíquota — A2/A3/A5), **US-41** (NFS-e rejeitada re-emite com ref por tentativa — A4).
**🟠 Médios corrigidos** (branch `feat/fiscal-medios-auditoria`, suíte 648): **A6** (config da rede exige
`pode_editar_dados_rede`), **A7** (justificativa NFS-e 15-255 no backend), **A9** (atomicidade: autorização
persiste antes de baixar XML/DANFE — `consultar` rebaixa), **A10** (RET MEI=5/ME-EPP=6), **A11** (backfill IBGE
alinha cidade/UF). A8 mitigado.
**🟡 Baixos corrigidos** (branch `feat/fiscal-baixos-auditoria`, suíte 650): **A12** (unicidade do PerfilEmissao —
constraint + índice + dedup), **A13** (2º clique concorrente → idempotente, não 500), **A14** (NFS-e autorizada
conclui a etapa 15). **✅ Auditoria fiscal 100% endereçada.** Ver `docs/avaliacao/2026-07-07-auditoria-fiscal.md`.

**Modularização — Fase 1 (fundação) implementada (2026-07-07, branch `feat/modularizacao-fase1`, suíte 670):** o
mapa lógico de `docs/ARQUITETURA-MODULOS.md` virou **executável e imposto**, sem mover código. **`modulos.py`**
(manifesto: camada/arquivos/tabelas/rotas/depende_de/desligável por módulo); **`tests/test_arquitetura_modulos.py`**
impõe a fronteira via `ast` (Núcleo não importa domínio; domínio só o que declara; tudo classificado) — **nasceu
verde** (acoplamento real já respeita a arquitetura) e foi **provado não-vacuoso** (4 mutações A/B/C/D falham como
esperado); **`mod_ciclo.faixa_da_etapa`** (titularidade do ciclo explícita); **`Loja.modulos_ativos` +
`mod_tenancy.modulo_ativo`** + endpoints `/api/admin/lojas/<id>/modulos` + guard no dispatch (piloto no fiscal
etapa 15) — liga/desliga domínio por loja, **default tudo-ligado** (zero mudança de comportamento). Subagent-driven,
6 tasks, cada uma revisada (spec+qualidade). Plano: `docs/superpowers/plans/2026-07-07-modularizacao-fase1.md`.

**Modularização — Painel + Menu reativo (2026-07-08, branch `feat/painel-modulos`, suíte 676):** deu **cara
visível** à Fase 1. `modulos.py` ganhou rótulos/ordem + `topologia_valida` (fecho de dependência); `GET
/api/admin/lojas/<id>/modulos` devolve os domínios com rótulo/ativo/deps e o `POST` rejeita topologia quebrada
(ex.: Comercial sem Cadastro → 400); `/api/auth/me` expõe `modulos_ativos` da loja do usuário; **painel "Módulos"**
no Admin da loja (checkboxes liga/desliga, aviso de dependência) + **menu reativo** (esconde Clientes/Parceiros se
Cadastro off; esconde abas Fiscal/Financeiro conforme o módulo na loja administrada). Default **tudo-ligado** em
todos os caminhos (revisado: nunca esconde por ausência/erro de rede). Frontend sem teste JS → verificado por
balanço + revisão. **Nota honesta:** domínios sem tela (Comercial/Produção/Estoque/Pós-venda/Expedição) têm toggle
mas reagem só no backend. Plano: `docs/superpowers/plans/2026-07-08-painel-modulos-menu-reativo.md`.

**Modularização — Hub de módulos (aterrissagem) + Credenciais no Admin (2026-07-08, branch `feat/hub-modulos`,
suíte 680):** a aterrissagem do usuário operacional deixou de abrir na lista de Projetos e virou um **hub de
módulos** — cards agrupados por **faixa de titularidade do ciclo** (Vendas · Execução do Projeto · Logística/
Expedição *(Fiscal aqui)* · Pós-venda/Montagem · Financeiro transversal), consistente com `mod_ciclo.FAIXA_POR_ETAPA`.
`modulos.py` ganhou `faixa` por domínio + `hub_layout()`; `/api/auth/me` inclui `usuario["hub"]`. Só **Comercial→
Projetos** e **Cadastro→Clientes** navegam; o resto é card **"em breve"** (honesto). **Credenciais** saiu do menu
lateral e virou **"Credenciais e Tokens" dentro do Admin (Plataforma)**, **só super_admin** — a seção **não é
renderizada** (não é cadeado) para os demais; **Diretor deixou de ver**. Subagent-driven, 5 tasks, revisão
frontend combinada aprovada (sintaxe + invisibilidade real + refs limpas). Plano:
`docs/superpowers/plans/2026-07-08-hub-modulos-credenciais.md`.

**Navegação Orizon v1 — Cadastro em abas + sidebar (2026-07-08, branch `feat/nav-cadastro-sidebar`, suíte 680):**
aplicadas as ações imediatas dos docs de spec oficial (`docs/design/navegacao-orizon-v1.md` + `padrao-design-orizon-v2.md`).
**Clientes e Parceiros saíram da sidebar** e viraram **abas do módulo Cadastro** (`page-10`: Clientes/Fornecedores/
Parceiros/Funcionários/Terceiros — 3 stubs "em breve"); o conteúdo foi **movido preservando os IDs internos**
(`cli-*`/`par-*`), então renders/modais seguem intactos; `goPage` ajustado para `n≥10` (senão `page-010`). **Sidebar
em 3 seções:** Módulos (topo→Hub) · **Atalhos** (Projetos, divisor, máx. 2) · Admin (último). **Faixa do hub
confirmada autoritativa** (5 grupos, Fiscal na Logística) — versão simplificada do design v2 superada. Specs
versionadas em `docs/design/`; **backlog de migração de design** (tema claro/escuro, tinta laranja legada, fonte
única, tokenizar status) em `docs/design/backlog-migracao-design.md` — **paralelo, não bloqueia**. Subagent-driven,
3 tasks, revisão frontend combinada aprovada (`node --check` OK). Plano:
`docs/superpowers/plans/2026-07-08-navegacao-cadastro-abas-sidebar.md`.

**Aba Parceiros na página Projetos + rename "Financeiro"→"Provisões" (2026-07-08, suíte 681):**
(a) a página Projetos ganhou uma **3ª aba "Parceiros"** (ao lado de Projetos|Clientes) — lista os parceiros da loja e,
para cada um, os **projetos relacionados** (via `parceiro_id` de cada projeto; nomes clicáveis → `abrirProjeto`). Backend:
a lista `/projetos` passou a expor **`parceiro_nome`** (enricher `_enriquecer_projetos_com_parceiro`, resolve do
`parceiro_id`). Rota real da lista é **`/projetos`** (não `/api/projetos`). Branch `feat/aba-parceiros`, subagent-driven.
(b) a sub-aba **"Financeiro" do Admin da loja** foi renomeada para **"Provisões"** (edita %s de provisão/custo-padrão =
domínio Financeiro; evita confusão com o módulo Financeiro do hub). Gate por `financeiro` mantido (correto); destino
final = dentro do módulo Financeiro quando tiver tela (registrado no `ARQUITETURA-MODULOS.md` §6).

**Alinhamento front-end — passo 1: escopo do Admin (2026-07-08, branch `feat/escopo-admin`, suíte 681):** correção
estrutural derivada dos docs de spec (`docs/design/`). O **Admin é Núcleo** (administra conta/loja, não domínios).
As abas **Projetos, Fiscal e Provisões saíram do Admin** (não tinham respaldo em doc — escolha fora do alinhamento);
**Admin da loja = Dados · Usuários · Módulos**; **Credenciais e Tokens** fica na Plataforma (super_admin). Para não
orfanar a config, os cards **Fiscal** (Emitente/NF-e) e **Financeiro** (Provisões/custos) do **Hub deixaram de ser
"em breve"** e abrem esses painéis (pages 11/12), reaproveitando `adminFiscalCarregar`/`adminFinanceiroCarregar` para
a loja do próprio usuário, gateados por `pode_editar_dados_loja` **dentro do módulo** (evita o erro de fronteira da
Expedição). Frontend puro (`node --check` OK), backend intocado. **Próximos passos do alinhamento:** (2) migração
visual (doc 3 §5, itens 1–7 — tema claro/escuro petróleo/dourado, aposentar tinta laranja legada, etc.); (3)
templates de diagramação (doc 4 Parte 1) conforme as telas forem tocadas. `Modulos_Orizon.docx` ainda não está no repo.
**Pendente:** passos 2 e 3 do alinhamento · **Fase 2** (extração física piloto = Fiscal) e domínios novos.

**Alinhamento front-end — passo 2, itens 1-2: paleta claro/escuro + fim da tinta laranja (2026-07-08, branch
`feat/design-paleta`, suíte 681):** migração visual mais transversal, feita primeiro. **Item 1** — o `:root` do
`static/index.html` deixou o dark-terminal verde-menta e passou aos **tokens claro/escuro do
`Padrao_Design_Orizon_v2.docx`** (accent **petróleo** `#4FA89E` escuro / `#1F4B4B` claro; **dourado** como accent
secundário de marca). Tema **dual**: padrão = escuro; `:root[data-theme="light"]` já definido, aguardando o toggle
(item 7). Estratégia de **aliases** — os nomes antigos (`--card→--surface-2`, `--ok→--accent`, `--dalm-gold→--gold`,
`--border2→--border-strong`, `--section→--info`, `--sb-bg→--surface`) apontam para os novos, então as ~250 referências
`var(--…)` herdam a paleta **sem editar cada linha**. A auditoria de tokens pegou dois **indefinidos pré-existentes**
usados por inputs de modais: `--fg` (herdava o texto, ok) e `--input` (caía no fallback `#0d1a0d` **verde** → destoaria
da superfície petróleo) — resolvidos com `--fg:var(--text)` e `--input:var(--surface)`. **Item 2** — as **8 ocorrências**
da tinta laranja legada `rgba(232,97,26,…)` (hover/ativo do menu, hover de card/linha/drop-zone, card destacado) foram
trocadas por `var(--accent-tint)` (fundos) / `var(--accent)` (borda) → grep = 0. Frontend puro (backend intocado, suíte
681); **sem teste visual → conferência no navegador (Ctrl+F5) fica com o usuário**. Cores hardcoded remanescentes
(status `#f05a50`… e cartões teal/amber/coral) **persistem de propósito** (itens 4/futuro). Plano:
`docs/superpowers/plans/2026-07-08-migracao-design-itens-1-2.md`; checklist derivado (fonte = `.docx`):
`docs/design/backlog-migracao-design.md` (itens 1-2 = ✅). **Pendente do passo 2:** itens 3 (unificar `login.html`),
4 (tokenizar status), 5 (`btn-primary` sem `.btn`), 6 (tipografia única + mono só em números), 7 (toggle persistido).

**Alinhamento front-end — passo 2, item 3: unificar `login.html` (2026-07-08, branch `feat/design-login`, suíte 681):**
o `login.html` tinha `:root` próprio verde-menta (`--bg #0d160d`, `--card #111d11`, `--accent #9FE1CB`, `--input-bg
#0a120a`) + hardcodes (`#0d160d` no botão/spinner, `rgba(224,92,92,…)` no erro). Como é **página standalone**
(servida antes do app → **não** herda o `<style>` do `index.html`), os tokens do **tema escuro do app** foram
**replicados inline** (`--bg #171B1C`, `--card #20262A`, `--border #2C3335`, `--accent #4FA89E` petróleo, `--text
#EDEFEE`, `--muted #8C979A`, `--err #E2876C`, `--input-bg #1D2224`) e os hardcodes trocados por `var(--…)`. Só CSS
mudou (JS intocado, confirmado por diff); backend intocado (suíte 681). **Fonte Epilogue mantida** (troca p/ Inter =
item 6). **Achado sinalizado (fora de escopo):** a logo do login ainda diz **"Promob → Omie"** (Omie foi aposentado;
produto é Orizon Manager) — correção de copy aguardando decisão do usuário. **Pendente do passo 2:** itens 4-7.

**Alinhamento front-end — passo 2, item 4: tokenizar cores de status (2026-07-08, branch `feat/design-status`, suíte
681):** os hexes hardcoded dos badges de status (`#f05a50` quente, `#d4a017` morno, `#c8a84b` fechado) foram trocados
por `var(--st-*)` nos **6 badges** (`.proj-status-badge.quente/morno/frio/convertido/fechado/perdido`) **e** no **JS do
botão** (`negAtualizarStatusBtn`, ternário de cor). Também normalizados `frio`/`convertido`/`perdido`, que liam dos
aliases antigos (`--section`/`--ok`/`--muted`), para o token semântico `--st-*` (mesmo valor hoje, mas single-source e
segue o tema claro/escuro — os `--st-*` já existiam no `:root` desde o item 1). Fundos rgba dos badges (padrão uniforme)
e o `#c8a84b` **decorativo** (separador "→"/rótulo do valor do contrato ~L829/831 = dourado, não status) ficam fora do
item — este último é hardcode de **marca** (deveria virar `var(--dalm-gold)`), sinalizado p/ limpeza futura. Só
frontend (backend intocado, suíte 681); diff = troca de valores (ternário intacto). **Pendente do passo 2:** itens 5
(`btn-primary` sem `.btn`), 6 (tipografia única + mono só em números), 7 (toggle persistido).

**Alinhamento front-end — passo 2, item 5: `btn-primary` sem `.btn` (2026-07-08, branch `feat/design-btn`, suíte
681):** `.btn` dá a base (padding/fonte/display) e `.btn-primary/-ghost/-danger` só trocam cor → quem tiver só o
modificador perde padding/fonte. Varredura (estáticos + dinâmicos: aspas simples, template literals, `classList`)
achou **um** infrator: o botão **"+ Novo Cliente"** (`cli-busca-home`), corrigido `class="btn-primary"` →
`class="btn btn-primary"`. Todos os demais já tinham a base (incl. o ternário `btn btn-sm ${ativo?'btn-primary':
'btn-ghost'}`). Uma linha de HTML; backend intocado (suíte 681). **Pendente do passo 2:** itens 6 (tipografia única +
mono só em números), 7 (toggle persistido).

**Alinhamento front-end — passo 2, item 6: tipografia única Inter + mono só em números (2026-07-08, branch
`feat/design-tipografia`, suíte 681):** o estado estava **invertido** vs. a spec — o `body` (`index.html:46`) usava
**`IBM Plex Mono` como default** (corpo/inputs/labels/tabelas herdavam mono) e a **Epilogue** era aplicada
explicitamente ao display (títulos/nav/botões, 65×). Migração (subagent-driven, 2 tasks + docs): fontes **tokenizadas**
no `:root` (`--font-sans:'Inter',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif` e
`--font-mono:'IBM Plex Mono',ui-monospace,…`); **`body` virou `var(--font-sans)`**; as **65** `font-family:'Epilogue',
sans-serif` → `var(--font-sans)` (pesos/tamanhos intocados → hierarquia preservada); as **40** declarações mono de
valor/`<td>` → `var(--font-mono)`. Link do Google Fonts trocou **Epilogue→Inter** (mantém IBM Plex Mono 400/500 e
carrega Inter 400/500/600/700/900). **`login.html`** (standalone, não herda o `:root`): `@import` e as 3
`font-family` → **Inter** (stack literal). **"mono só em números" por construção:** auditoria confirmou que todo mono
explícito era numérico (13 campos `mp-a-*` + 9 `<td>` alinhadas à direita + demais spans de valor; **zero** em texto),
então virar o default para sans + preservar o mono explícito satisfaz a regra sem demoções. Contagens pós-migração:
Epilogue 0 (ambos arquivos), `var(--font-sans)` 66 (65+body), `var(--font-mono)` 40, `'IBM Plex Mono'` restante 1 (o
token). Só frontend (backend intocado, suíte 681); **sem teste visual → conferência no navegador com o usuário**.
**Achado de copy (re)sinalizado:** "Promob → Omie" está no **`<title>` do `index.html:6`** *e* na logo do `login.html`
(Omie aposentado; produto = Orizon Manager) — correção aguardando decisão. **Passo 2 quase completo — resta só o
item 7** (toggle de tema claro/escuro persistido por usuário).

**Alinhamento front-end — passo 2, item 7: toggle de tema persistido por usuário (2026-07-08, branch
`feat/design-toggle-tema`, suíte 687):** último item do passo 2 — e o único que **mexe em Python**. **Backend:** coluna
`Usuario.tema` (`'claro'|'escuro'`, default escuro, migração idempotente em `_migrar_colunas`); `tema` no
`auth._usuario_dict` (serializador único → chega ao front por login **e** `/api/auth/me`); função testável
`auth.set_tema(id, tema)`; **`POST /api/auth/preferencias`** (auth-scoped, valida 'claro'/'escuro'). **Frontend
(index.html):** `aplicarTema()` seta/remove `data-theme="light"` no `<html>` (a paleta clara já vinha do item 1),
aplicado no **boot** (após `_usuarioAtual = d.usuario`) e por um **toggle na sidebar** (rodapé, sol/lua); `alternarTema()`
inverte + grava via fetch. Persistência **por usuário no backend** (coluna), **não** localStorage/SO → acompanha o
usuário em qualquer máquina; custo aceito = "flash" curto de escuro antes do `/me` p/ quem usa claro. **Testes (suíte
681→687):** 3 unit (coluna/dict-default/`set_tema` válido-inválido-inexistente) + 3 HTTP end-to-end (endpoint
200+persistência, 400 inválido, 401 sem auth). Subagent-driven (backend TDD + frontend), revisado. **Mudança em Python
→ servidor precisa de restart** para valer localmente. **✅ PASSO 2 (migração visual) 100% CONCLUÍDO — itens 1 a 7.**
**Follow-ups de higiene (fora dos itens, aguardando decisão):** copy "Promob → Omie" (`<title>` do index + logo do
login); `#c8a84b` decorativo (~L829/831); e **hardcodes verdes** descobertos nesta frente — avatar `color:#0d160d`
(~L510) e `#modal-perfil` (`#111d11`/`#1e2e1e`, ~L527) — resíduos que o item 1 (aliases só no `:root`) não cobriu.
**Próximo do alinhamento = passo 3** (templates de diagramação, doc 4 Parte 1, conforme as telas forem tocadas).

**Passo 3 (diagramação) — 1ºs ajustes do hub + tema claro (2026-07-08, branch `feat/design-hub-ajustes`, suíte 687):**
guiado por observação do usuário sobre o hub no tema claro. **(1) Contraste** — `--muted` do **tema claro** escurecido
`#8A8880`→`#6B6860`: contraste vs. fundo subiu de **3.55/3.31:1 → 5.56/5.19:1** (passa WCAG **AA** 4.5:1; antes falhava,
sobretudo sobre `--surface`). Só o bloco `:root[data-theme="light"]` (dark intocado). **(2) "Abrir →" em `--accent`** —
nova regra `.hub-card:not(.soon) .hub-card-tag{color:var(--accent)}`: os cards ativos passam a mostrar "Abrir →" em
petróleo, distinto de "Em breve" (`--muted`, que competia visualmente). **(3) Distribuição do grid** — `.hub-cards`
passou de `minmax(200px,1fr)` (esticava) para **card fixo `280px` + `max-width:1280px`**: grupos com 1–2 cards (ex.
Financeiro) não espalham em telas largas; card quebra linha. Frontend puro (suíte 687). **Achado sobre a sidebar
(ponto reportado como "labels arroxeados"):** varredura exaustiva confirmou que **`.sb-nav-title` já usa `var(--muted)`**
e **não há nenhuma cor arroxeada hardcoded** no arquivo — não é resíduo não-migrado. O tom lavanda percebido é o próprio
`--muted` **escuro** `#8C979A` (cinza-frio) sob **contraste simultâneo** com o petróleo. Como já é o token correto, **não
houve mudança** (evitar no-op); se o tom ainda incomodar, opções = hard-refresh (cache) ou ajustar o token `--muted`
escuro levemente mais quente (afeta todo texto muted) — decisão do usuário.

**Passo 3 (diagramação) — sidebar/abas + projeto no cabeçalho (2026-07-08, branch `feat/design-sidebar-tabs`, suíte
687):** 3 ajustes estéticos guiados pelo usuário. **(a) Realce ativo mais leve** — `.nav-item.active` deixou de usar
`background:var(--accent-tint)` (o "botão" que no escuro puxava pro verde-petróleo e no claro era o único item com
fundo, destoando): agora é só `color:var(--text)` + `font-weight:700` + borda-esquerda fina `--accent`. Vale p/ todo
item ativo. **(b) Abas Projetos/Clientes/Parceiros sem dourado** — `.home-tab` usava `--dalm-gold`/`-light` (amarelo
que destoava): inativo → `--muted`, ativo → `--text` + sublinhado `--accent`, hover → `--text`; a borda do `#home-tabs`
dourada virou `--border`. O seletor passou a cobrir **`.ativo` E `.active`** → as abas do **Cadastro (page-10)**, que
não tinham realce ativo (usavam `.active`, sem regra), agora também destacam. **(c) Nome do projeto saiu da sidebar**
— removido o widget "Projeto ativo" do topo (a sidebar fica só navegação/acesso) e o **nome+cliente** foram para o
**cabeçalho da page-02 (Negociação)**, acima do título (novos `#proj-ctx-nome`/`#proj-ctx-cli`; o JS de `abrirProjeto`
e de criação de projeto passou a escrever neles — antes só a sidebar exibia o nome; o `.proj-header-nome` do CSS era
morto). Frontend puro (suíte 687; um e2e de NF-e piscou flaky e passou no re-run). **Pendências de higiene seguem**
(Promob→Omie, `#c8a84b`, hardcodes verdes do avatar/modal-perfil, e o `--muted` escuro se o tom ainda incomodar).

**Módulo Financeiro — sub-projeto #1: Plano de Contas (2026-07-09, branch `feat/financeiro-plano-contas`, suíte
687→699):** início da **camada contábil nova** (a spec `Especificacao_Financeiro_Orizon_v2.docx` é greenfield sobre o
financeiro atual, que era só provisões/custos). O módulo vai em **6 sub-projetos** (Plano de Contas → Livro de
Lançamentos → Motor evento→lançamento → DRE societário → DRE por projeto → Auditoria/Reconciliação); este é o #1.
**Entregue:** modelo **`Conta`** (árvore por `pai_id`, `owner_tipo/owner_id`, `codigo`, `grupo` 1–5, `tipo`
sintética/analítica, `natureza`, `ativa`); **`mod_contabil.py`** com `PLANO_PADRAO` (**99 contas**: grupos 1–5 +
subgrupos + 78 analíticas nível 3 do Pontta — tudo do `.docx` §2/§2.1), `resolver_owner` (loja→rede; loja avulsa =
própria), `seed_plano` idempotente (seed-on-first-access), `listar_contas` (árvore) e **CRUD** (`criar_conta` torna o
pai sintético; `editar_conta` nome+ordem; `remover_conta` = **apaga folha sem lançamento / inativa o resto** — regra
"inativar-não-apagar"; `_tem_lancamentos` é stub `False` até o #2); **API** `/api/financeiro/contas` (GET árvore /
POST criar / PUT editar / **POST /remover** — o dispatch não tem `do_DELETE`) com gate do módulo financeiro +
capability (`aprovar_financeiro` OU `editar_dados_loja`) e barra **cross-owner**; **UI** = aba **Plano de Contas** na
page-12 (árvore add/renomear/inativar), ao lado de **Provisões**. **Tenancy por owner** (rede compartilha; loja avulsa
tem a sua) — espelha o Emitente. Manifesto `modulos.py` atualizado (financeiro += `mod_contabil.py`/`conta`/rota) →
`test_arquitetura_modulos` verde. **Executado inline** (a infra de subagente deu 529), TDD, 8+4 testes novos.
**Cortes conscientes:** "mover conta" (reparent) fica p/ o #2; sinal de dedução na DRE = #4. **Restart do servidor**
para valer localmente. Spec/plano: `docs/superpowers/specs|plans/2026-07-09-plano-de-contas*`; **fonte de verdade do
plano de contas = o `.docx`**. **Próximo:** #2 Livro de Lançamentos (introduz `projeto_id` e ativa `_tem_lancamentos`).

**Módulo Financeiro — sub-projeto #2: Livro de Lançamentos (2026-07-09, branch `feat/financeiro-lancamentos`, suíte
699→707):** modelo **`Lancamento`** (partida dobrada: `conta_debito_id`/`conta_credito_id`, `valor`, `data` de
competência, **`projeto_id`** = nome_safe da dimensão gerencial, `origem`, `historico`) + motor em `mod_contabil`:
`lancar` (valida valor>0, contas distintas, **ambas analíticas ativas do mesmo owner**), `saldo_conta` (na natureza:
devedora D−C / credora C−D), `razao` (extrato com saldo corrido), `listar_lancamentos`; e **`_tem_lancamentos` agora é
real** → conta com lançamento **não apaga, inativa** (fecha a regra do #1). API: `POST /api/financeiro/lancamentos`,
`GET /api/financeiro/lancamentos?projeto=&ini=&fim=`, `GET /api/financeiro/contas/<id>/razao`. UI: **aba Lançamentos**
na page-12 (form débito/crédito/valor/projeto/histórico + lista). Manifesto += `lancamento`/rota. TDD (5 unit + 3 HTTP);
**app_db é module-scoped** → cada teste do livro usa contas distintas (isolamento). **Corte:** o motor evento→lançamento
que **popula** o livro é o #3; entrada manual existe via UI/API. **Próximo:** #3 (as 5 regras evento→lançamento).

**Módulo Financeiro — sub-projeto #3: Motor evento→lançamento (2026-07-09, branch `feat/financeiro-eventos`, suíte
707→714):** as **5 regras do `.docx` §5** viraram `mod_contabil.EVENTOS` + `registrar_evento(...)`: `fechamento_venda`
(D 5.6.01 Constituição de Provisão / C 2.1.04.03 Provisão de Garantia — segue o pareamento 5.6↔2.1.x do próprio plano),
`faturamento` (D 1.1.02 Contas a Receber / C 4.1.01 Receita), `recebimento` (D 1.1.01 Caixa / C 1.1.02),
`pagamento_comissao` (D 2.1.04.01 / C 1.1.01), `execucao_assistencia` (D 2.1.04.03 / C 1.1.01). Contas resolvidas por
**código** (estável: rename não muda código; reparent adiado); o evento gera lançamento com `origem=tipo` + `projeto_id`.
API: `POST /api/financeiro/eventos {tipo,valor,projeto_id,data?}`. TDD (5 unit + 2 HTTP). **Follow-up consciente:** o
**wiring nos fluxos vivos** (fechar contrato → `fechamento_venda`; NF-e emitida → `faturamento`; recebimento/comissão/
assistência) **não** foi feito — toca contrato/emissão e exige idempotência; o motor+endpoint estão prontos p/ plugar.
**Próximo:** #4 DRE societário (relatório do livro por competência).

**Módulo Financeiro — sub-projeto #4: DRE societário (2026-07-09, branch `feat/financeiro-dre`, suíte 714→718):**
`mod_contabil.dre(owner, ini, fim)` monta a DRE do `.docx` §3 a partir do livro por **competência**: Receita Bruta
(4.1+4.2) − Deduções (4.3) = Receita Líquida − CMV/CSP (5.1+5.2) = Lucro Bruto − Comerciais (5.3) − Administrativas
(5.4) − Constituição de Provisões (5.6) = EBITDA − Depreciação = EBIT ± Resultado Financeiro (5.5) = Resultado antes
de impostos − Impostos = Lucro Líquido. **Resolvido o corte de sinal do #1**: `_mov(prefixo, sentido)` computa cada
linha no sentido natural (receita = C−D; deduções/despesas = D−C, sempre positivas) e a estrutura aplica o sinal —
então **dedução reduz** a receita corretamente, independentemente da `natureza` cadastrada. Depreciação e Impostos = 0
(sem conta dedicada; Simples/DAS já em Deduções) — anotado p/ refinar com contador. API: `GET /api/financeiro/dre?
ini=&fim=`. UI: **aba DRE** na page-12 (demonstrativo formatado, subtotais destacados). TDD (3 unit + 1 HTTP; owner
distinto por teste pelo escopo de módulo). **Próximo:** #5 DRE por projeto (margem de contribuição via `projeto_id`).

**Módulo Financeiro — sub-projeto #5: DRE por projeto / margem de contribuição (2026-07-09, branch
`feat/financeiro-dre-projeto`, suíte 718→721):** `margem_projeto(owner, projeto_id, ...)` (do `.docx` §4) = receita
(4.1+4.2) − custo direto produto (5.1) − custo direto serviço (5.2) − comercial/comissão (5.3) − provisão de garantia
(5.6), tudo **filtrado por `projeto_id`** (a dimensão gerencial do #2). `_totais_conta`/`_mov` ganharam o filtro de
projeto (a DRE societária segue sem projeto = total). `projetos_com_lancamento` + `margem_todos_projetos` (ordenada por
margem desc). **NÃO aloca custo fixo** — isso é o rateio do #6 (a soma das margens ≠ Lucro Líquido, como o `.docx`
alerta). API: `GET /api/financeiro/projetos-dre?ini=&fim=`. UI: **aba Margem/Projeto** (tabela receita/custos/margem por
projeto). TDD (2 unit + 1 HTTP). **Próximo:** #6 Auditoria/Reconciliação (rateio de custo fixo → margem plena +
divergência residual).

**Módulo Financeiro — sub-projeto #6: Auditoria/Reconciliação (2026-07-09, branch `feat/financeiro-reconciliacao`,
suíte 721→726):** modelo **`PeriodoContabil`** (snapshot: inicio/fim/status/metodologia/resultado_societario/
soma_margem_plena/divergencia_residual/dados_json) + `mod_contabil.reconciliar(owner, ini, fim, metodologia)` (do
`.docx` §6): rateia a **despesa fixa do período (grupo 5.4)** aos projetos por uma **base de vigência** —
`proporcional_receita` | `proporcional_custo_direto` | `linear_por_projeto` — gerando **margem plena** (full cost) =
margem de contribuição − rateio; e a **divergência residual** = resultado societário (DRE) − soma das margens plenas
(estrutural: itens não alocados a projeto + provisões não realizadas; tende a um piso, não a zero). `fechar_periodo`
persiste o snapshot; `listar_periodos`. API: `POST /api/financeiro/reconciliar` (preview), `POST /api/financeiro/
periodos` (fecha), `GET /api/financeiro/periodos`. UI: **aba Reconciliação** (base de rateio + tabela margem→rateio→
margem plena + soma/societário/divergência + fechar período). TDD (3 unit + 2 HTTP). **✅ MÓDULO FINANCEIRO COMPLETO —
sub-projetos 1 a 6** (Plano de Contas · Livro de Lançamentos · Motor evento→lançamento · DRE societário · DRE por
projeto · Auditoria/Reconciliação). **Follow-ups conscientes** (registrados ao longo): wiring dos eventos nos fluxos
vivos (contrato/NF-e), "mover conta" (reparent), Depreciação/Impostos com conta dedicada, e refino contábil/tributário
com contador antes de produção (aviso do `.docx`). Suíte 687→726 (+39 testes). **Fonte de verdade = o `.docx`.**

**Módulo Financeiro — wiring do motor de eventos nos fluxos vivos (2026-07-09, branch `feat/financeiro-wiring`,
suíte 726→730):** o motor evento→lançamento (#3) passou a ser **disparado automaticamente** pela emissão fiscal.
`Lancamento` ganhou coluna **`ref`** (idempotência; migração idempotente p/ DBs existentes) e `registrar_evento(ref=)`
ficou **idempotente** (mesmo `ref` não duplica; `lancamento_por_ref`). Helper `_fin_evento_seguro(loja_id, tipo, valor,
projeto_id, ref)` no `main.py` (SHELL): **sessão própria + fail-soft** (contabilidade NUNCA aborta a emissão; try/except
que só loga), resolve owner da loja, respeita o **gate do módulo financeiro**. Wirado o evento **`faturamento`** na
**NF-e de produto autorizada** (D Contas a Receber / C Receita, valor = venda do preview, `ref=fat:NFE-<proj>-<doc>`) e
na **NFS-e de serviço autorizada** (valor do serviço, `ref=fat:NFSE-<proj>-<n>`). **Arquitetura:** o wiring vai no
`main.py` (SHELL) porque `nfe_emissao` é domínio **fiscal** e não pode importar `mod_contabil` (financeiro) — fronteira.
Prova **end-to-end**: teste que emite NF-e produto (emissor fake) e confirma o lançamento de `faturamento` com o `ref`
esperado. TDD (3 unit + 1 e2e). **Follow-ups conscientes (ainda não wirados — sem gatilho/valor claro no app):**
`fechamento_venda` (na criação do contrato — falta definir o valor da provisão de garantia), `recebimento`,
`pagamento_comissao`, `execucao_assistencia` (não há fluxos de pagamento/pós-venda ainda) — entram por lançamento
manual / API de eventos por ora. Suíte **687→730** no módulo Financeiro inteiro.

**Módulo Financeiro — atualização v2→v5 (`Especificacao_Financeiro_Orizon_v5.docx` agora é a FONTE DE VERDADE).**
Front 4 — **três provisões distintas (v5 §5/§6, branch `feat/fin-v5-provisoes`, suíte 730):** o seed ganhou
`2.1.04.05 Provisão de Assistência Técnica` (e `2.1.04.03` "Garantia Técnica"→"Garantia"), e `5.6` passou a ter 3
filhos de constituição (`5.6.01` Garantia, `5.6.02` Montagem, `5.6.03` Assistência). **`seed_plano` virou backfill
idempotente** — planos já existentes (ex.: local/VPS) ganham as contas novas no próximo acesso, sem recriar. Os
**EVENTOS** foram reestruturados em 3 provisões **independentes**: abre `fechamento_venda_{montagem,assistencia,
garantia}` (D 5.6.x / C 2.1.04.x) e reverte `execucao_{montagem,assistencia,reparo_garantia}` (D 2.1.04.x / C Caixa) —
partida dobrada de duas pontas, sem conta de "Reserva" no Ativo (§6.1). `margem_projeto` (§5) agora subtrai
produto(5.1) + as 3 provisões(5.6.x) + comissão(5.3); **Garantia entra pelo valor bruto** (repasse à fábrica é
controle à parte, §6.2). Códigos **estáveis** (rename não muda código) → não quebra lançamentos existentes. UI
Margem/Projeto atualizada. Testes de evento/DRE/margem migrados. **Follow-up:** o **painel de provisões DA VENDA**
(as 3 linhas por venda desde o fechamento) e o **wiring `fechamento_venda_*` na criação do contrato** exigem a fonte
dos valores (negociação) — próximo passo da integração.
Front 2 — **Balanço Patrimonial (v5 §4, branch `feat/fin-v5-balanco`, suíte 730→732):** `balanco(owner, data_corte)`
= saldo **acumulado** (do início até a data) dos grupos 1/2/3; o **resultado do exercício** (Receitas−Despesas
acumuladas) entra no PL → **fecha por partida dobrada** (`Ativo = Passivo + PL`, flag `confere`). Diferente do DRE (é
posição num instante, não fluxo). API `GET /api/financeiro/balanco?data=`; **aba Balanço** na page-12. TDD (2 unit).

> **⚠ Incidente (2026-07-06) — servidor obsoleto:** durante a conferência manual, o painel Fiscal "não
> persistia" — causa: o `main.py` na 8765 era um processo de **ontem** (pré US-36/37/38; rotas novas davam
> 404). **Fix:** matar os `main.py` presos e subir fresco (`pythoncore-3.14-64\python.exe main.py`). **SOP:
> toda mudança em Python exige reiniciar o servidor** (o `main.py` é lido só no start; o `index.html` é lido
> do disco a cada request).

### 🧾 Módulo Fiscal / Integração NF-e (Fábrica→Loja via Focus NFe) — mapa e continuação (Sessão 47)

**Objetivo:** a fábrica entrega direto ao cliente; a loja emite **sua** NF-e (com markup) via **Focus NFe**
(a Focus **não** calcula imposto — nós montamos o bloco fiscal). Pipeline em código, ponta a ponta (offline):
`mod_nfe.preview` → `mapa_fiscal` → `EmissorFocusNfe` → `focus_client`, com `PerfilFiscal` alimentando o mapa.

| Fase / peça | O quê | Estado |
|---|---|---|
| **Fase 1** | `mod_nfe.py` — parser XML fábrica + consolidação + markup (`preview`) + CLI | ✅ na `main`, testado |
| **Fase 2** | `emissor_fiscal.py` (contrato `EmissorFiscal`/DTOs) + `focus_client.py` + `focus_config.py` | ✅ na `main`, testado |
| **Painel Fiscal I** | `PerfilFiscal` (tabela) + `fiscal_cripto` (Fernet) + `mod_fiscal` + endpoints GET/PUT (config/segredos/ambiente) | ✅ na `main`, testado |
| **Painel Fiscal II** | Aba **Fiscal** no admin da loja (frontend) — 7 seções, badges de placeholder, segredos write-only, troca de ambiente | ✅ na `main` — **⚠️ verificação manual no navegador PENDENTE** |
| **Fase 3b** | `mapa_fiscal.py` (nota→payload Focus) + `emissor_focus.py` (`EmissorFocusNfe`) | ✅ na `main`, testado (offline) |
| **Fase 4** | `NfeEmissao` (rastreio por `ref`) + `nfe_emissao.py` (`emitir`/`consultar`/`cancelar`: emite→polling→baixa XML/DANFE→guarda; idempotente; **recusa produção**) + endpoint `POST …/nfe/emitir-teste` | ✅ na `main`, testado (offline) — **⚠️ smoke real em homologação PENDENTE do token** |
| **Fase 5** | Orquestração por projeto na **etapa 15**: upload da NF-e da fábrica → `preview(markup)` → `montar_nota` → `nfe_emissao.emitir` (`ref` estável `NFE-<projeto>-<doc_id>`, idempotente, conclui a etapa em `emitida`) + consultar/cancelar (cancelar **reverte** a etapa) + **painel da etapa 15**. Coluna `NfeEmissao.fabrica_doc_id`; regra do nome SEFAZ do destinatário em homologação centralizada no `nfe_emissao.emitir` | ✅ branch `feat/nfe-etapa15`, e2e (emissor mockado) — **⚠️ smoke real + verificação manual do painel PENDENTES** |

**Smoke em homologação (2026-07-06):** **token validado** ✅ (autentica; consulta de `ref` inexistente →
404 "Nota fiscal não encontrada"). **Emissão real testada** com um XML real da fábrica (NFe-170942,
markup 30% → 12 produtos, custo 730,89/venda 950,16): o **payload foi aceito estruturalmente** (a Focus
NÃO rejeitou campo nenhum → `preview→mapa_fiscal→payload→transporte` validado ponta a ponta) e parou num
erro **de negócio**: **"Empresa ainda não habilitada para emissão de NFe, por favor contate o suporte
técnico."** → o pipeline está correto; falta o **cadastro/habilitação do CNPJ 19.152.134/0001-56 na
Focus** (empresa + certificado A1 + liberação pelo suporte). Nada de código muda até lá.

**🎉 SMOKE REAL AUTORIZADO (2026-07-06) — NF-e emitida em homologação, ponta a ponta.**
Após o merge multi-CNPJ + o certificado A1 na Focus, o smoke rodou pelo **trilho novo (Emitente)** e
**autorizou**: `status=AUTORIZADO`, `sefaz="Autorizado o uso da NF-e"`, chave
`NFe35260719152134000156550010000000011051879962` (CNPJ INSPIRIUM na chave → emitiu sob o self-emitente),
XML+DANFE baixados (`DocumentoFiscal` xml_doc/danfe_doc). Toda a integração (Fases 1-5 + multi-CNPJ) validada
contra a SEFAZ real. O smoke descobriu e destravou:
- **2 bugs de código (corrigidos + testados, commit `b443c0a`):** `modalidade_frete` obrigatório (estava
  ausente → "Modalidade frete não pode ser vazio"); **CPF/CNPJ/CEP só com dígitos** no payload (`_so_digitos`
  no `montar_nota` — SEFAZ rejeitava "CPF inválido" com pontuação).
- **2 achados de DADO (não código):** (a) **CSOSN 101 → 102** — venda a consumidor final (não contribuinte)
  exige CSOSN **102** (sem crédito); ajustado no `Emitente` da INSPIRIUM. *(Ideal: CSOSN por tipo de
  destinatário contribuinte×não-contribuinte — refinamento fiscal, contador; registrar.)* (b) o cliente 2
  (Marcelo) tem **CPF placeholder inválido** (`012.021.345-01`) — para emissão real precisa do CPF real (o
  smoke usou um CPF de teste válido).
- **✅ Refinamento do destinatário IMPLEMENTADO** (branch `feat/fiscal-destinatario-contribuinte`, suíte 562):
  Cliente ganha **tipo (Contribuinte/Isento/Não contribuinte)** + CNPJ + IE; cadastro com seletor condicional;
  contrato exige CPF ou CNPJ conforme o tipo (IE não bloqueia); **IE pedida na emissão e persistida no Cliente**;
  `mapa_fiscal` ramifica **indicador IE (1/2/9)**, envio de IE, **CSOSN** (default no código 101/102 + override no
  Emitente `csosn_contribuinte`) e `consumidor_final`. Resolve o achado (a) acima. *(Pendente: CSOSN por operação
  ST/devolução; não-contribuinte PJ — fora do escopo.)*
- **Emitente da INSPIRIUM completo** no `orizon.db`: endereço (Av. Barão do Rio Branco, 736, São José dos
  Campos/SP, CEP 12242-800), IE 645636985117, IBGE 3549904, CSOSN 102, token homolog. *(bairro do emitente
  ficou vazio e a SEFAZ aceitou — usa o cadastro da empresa; preencher por higiene.)*

**Smoke PREPARADO (2026-07-06) — runbook em `docs/RUNBOOK-smoke-nfe.md`** (dados locais em `orizon.db`,
gitignored — não vão pro repo):
- **`config/fiscal.key`** criada (chave Fernet estável; gitignored) — token salvo hoje decripta amanhã.
- **`PerfilFiscal` da loja 1 (INSPIRIUM, 19.152.134/0001-56)** provisionado: `ambiente_ativo=homologacao`,
  perfil-padrão (Simples, CSOSN 101, CFOP 5102/6102, ISS 5%, placeholders → **produção bloqueada**).
  **Token de homologação salvo (encriptado)** e **revalidado** via `focus_client_para_loja` (404 em `ref`
  inexistente = autentica).
- **Projeto-alvo do smoke: `Projeto_Teste_Neg`** (loja 1, cliente **Marcelo Buonocore Nunes** com CPF; ciclo
  concluído até a etapa 14 → **etapa 15 destravada**). **Dry-run offline OK** (perfil INSPIRIUM + cliente 2 +
  `NFe-170942.xml` → preview 12 itens/custo 730,89/venda 950,16 → `montar_nota` → `montar_payload` sem erro).
- **⚠️ GAP de dado (só o usuário tem):** a **loja INSPIRIUM está sem endereço** (Loja: logradouro/cidade/UF/CEP)
  e **sem IE** (perfil). `montar_nota` monta o emitente a partir daí → sem a **UF do emitente** o CFOP sai 6102
  (interestadual) e a Focus pode rejeitar campos do emitente quando habilitada. **Preencher** o endereço (painel
  de dados da loja) + IE/município IBGE (aba Fiscal) antes/durante o smoke. (Oferecido preencher se o usuário
  passar os valores.)

**Insumos do usuário (gatilham as próximas fases, não bloqueiam o que já existe):**
- **Habilitar o CNPJ na Focus** — cadastrar a empresa 19.152.134/0001-56, enviar o **certificado A1** e
  pedir liberação para emissão de NF-e (suporte Focus). É o bloqueio atual do smoke real. **Token já OK
  (homologação, autentica); confirmado que a empresa segue "não habilitada" pois o certificado A1 ainda
  NÃO foi enviado — o usuário fará isso amanhã (2026-07-07). Depois disso, rodar o smoke novamente.**
- **Valores fiscais reais do contador** (CST/CSOSN/CFOP/alíquotas) do CNPJ **19.152.134/0001-56 (Simples)** —
  entram como **dado** no `PerfilFiscal` (perfil-padrão de teste já destrava o desenvolvimento).
- **Nota homologação:** o destinatário vai com o nome SEFAZ "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO -
  SEM VALOR FISCAL" — **✅ implementado (Fase 5)**: `nfe_emissao.emitir` carimba automático quando
  `ambiente_ativo == "homologacao"`.

**Pendências/gaps conhecidos (ajustes pequenos, registrados):**
- **[teste]** conferência do **Painel Fiscal (Sub-frente II)** e do **painel da etapa 15** (Fase 5) no
  navegador — o usuário fará **amanhã**, junto do smoke real.
- **[Fase 5]** cancelar reverte a etapa 15 para `em_andamento` incondicionalmente — se houver **duas** NF-e
  autorizadas (append-only permite vários XMLs da fábrica no mesmo projeto), cancelar uma "desconclui" a
  etapa mesmo com a outra ainda válida. Caso de borda (fluxo típico = 1 nota); reavaliar se virar comum.
- **[GAP]** `cert_validade`/`cert_cnpj` são read-only no painel — o `PUT …/perfil-fiscal` (Sub-frente I) não
  os inclui na allowlist; torná-los editáveis é ~2 linhas no backend.
- **[Fase 4]** `mapa_fiscal`: PIS/COFINS CST "49" e o CSOSN são **do Simples** (marcado `# TODO Fase 4`) —
  ramificar por regime normal/presumido com o contador.
- **[Fase 4/5]** `custo_total`/`venda_total` do `preview` somam valores unitários **já arredondados** →
  pode divergir do total fiscal por centavos (reconciliar se comparar com a NF-e).

**Specs/planos:** `docs/superpowers/specs|plans/2026-07-05-nfe-*` e `…-perfil-fiscal-*` e `…-painel-fiscal-*`
(todos com Status **IMPLEMENTADO**, exceto o que resta das Fases 4-5). XMLs reais da fábrica em
`E:/2026/desenvolvimento/nfe-dalmobile` (fora do git).

Servidor: `python3 main.py` (porta 8765) — **atenção:
o `python3` do Bash aqui é o stub do WindowsApps (exit 127); subir com o interpretador real
`C:\Users\mbn19\AppData\Local\Python\pythoncore-3.14-64\python.exe main.py`, e sempre matar servidores
`main.py` obsoletos que fiquem presos na 8765 (senão o navegador fala com código velho).**
Branches: `main` + `worktree-agent-a3876ec2c1cd36c64` (worktree do harness, mantido).
Contrato agora é **HTML/Markdown → PDF (WeasyPrint)** — o caminho `.docx`/LibreOffice do contrato
foi aposentado (a **proposta** ainda usa docx/LibreOffice). **Diretório de trabalho:**
`E:/2026/desenvolvimento/orizon-manager` (pai renomeado nesta sessão). **MCP `orizon`** ativo e
ingerido; re-ingerir ao fechar frente (grafo re-ingerido após o merge da Sessão 45: código 920 nós,
banco 66 — inclui `CicloDocumento`/`CicloRevisao`). **[AMBIENTE — fix] `mcp-orizon/.env`:** o
`TARGET_PROJECT_PATH` ainda apontava para o path antigo `E:/2026/estudo_de_ia/omie_v3` (obsoleto desde
a renomeação da Sessão 44) — corrigido para `E:/2026/desenvolvimento/orizon-manager`. Sem isso o
container `mcp-orizon-api` monta diretório inexistente e a ingestão lê o projeto errado. Análogo ao fix
do `.mcp.json` na Sessão 44. (`.env` é gitignored → não vai pro repo; corrigir na máquina que rodar o
stack.) Para subir o stack quando o Docker Desktop está fechado: iniciar o Docker Desktop pela sessão do
usuário (`Start-Process` no PowerShell funciona; `cmd start` não pegou), aguardar `docker info`, então
`docker compose up -d` em `../mcp-orizon` e `POST http://localhost:8767/ingest/all`. **Produção (VPS 167.88.33.121:8765)** atualizada para
`ca05a61` (sessão 44) nesta sessão: `/root/orizon-manager`, banco `orizon.db`, remote novo, screen
`orizon-manager` (`ORIZON_HOST=0.0.0.0`), weasyprint 61.1, `/login` HTTP 200. **SSH por chave** já
configurado (deploy pode ser conduzido pelo agente). Pendências-baixa: conferir contrato PDF real em
prod (weasy 61 vs 69) e revisar chaves de terceiros no `authorized_keys` do root.

**Já na `main` (frentes recentes):** super_admin aterrissagem+árvore; acesso multi-loja; Frente C
(config financeira/provisões/margem real); provisões versionadas (Venda/Rev1/Rev2 + aprovação);
etapa Orçamento como hub + Imprimir Orçamento (proposta = 1º doc do banco #8). Fixes de contrato
(path PDF, staleness, tela cheia). E2E do início ao fim + geração real de contrato/assinatura.

**Status das specs:** atualizado o cabeçalho das specs implementadas+mergeadas (as 5 frentes recentes
+ multitenant F2/F3/F4). Specs anteriores a 24/06 não foram relabeladas (verificar caso a caso ao retomar).

**Pendências / próximos (backlog):**
1. **Banco de documentos da loja #8 (continuação):** ~~falta a lista "etapa → documento"~~ **RESOLVIDO
   (2026-07-06):** o `1.FLUXO_DE_PROCESSOS.docx` foi transcrito para `docs/referencia/01-fluxo-de-processos.md`
   (fonte editável do usuário; ver `docs/referencia/README.md`) — inclui a lista **etapa → documento (D1–D45)**.
   Ainda pendente: modelo de proposta/contrato **por loja** (Padrão/Personalizado).
2. **Conferência visual** dos 4 itens de UX do Imprimir Orçamento (botão/cards) no browser.
3. **Defers** (cosméticos): genericizar corpo do 500 da rota de proposta; remover `import _mprop` redundante.
4. **Seed Orizon (#6)**, **busca LGPD (#4)**, **config de rede (#7)**.
5. ~~**Não-pushed**~~ **OK (2026-07-06):** `main` sincronizada com `origin` (push funciona nesta máquina).
6. **EP-10 — Reconciliação do Ciclo (4 lacunas)** — do mapa 38 etapas ↔ ciclo (`docs/processos/FLUXO_38_ETAPAS.md`,
   canônico em `docs/referencia/01-fluxo-de-processos.md`; faixas em `docs/ARQUITETURA-MODULOS.md`). Registradas
   em `docs/historias/BACKLOG.md`: **US-32** NFS-e de montagem *(→ módulo Fiscal, o próximo item natural ao
   retomar o fechamento fiscal)*, **US-33** pós-entrega (follow-up/recompra), **US-34** posição da Aprovação
   Financeira (11d × Fase 3 — decisão de negócio), **US-35** marcos de Conferência/Transferência ao CD.

> **Nota (2026-07-04):** a antiga seção "🔼 PENDÊNCIA: PUSH" foi removida — o `git push origin main`
> funciona nesta máquina (Git Credential Manager do usuário). Remote:
> `https://github.com/mbnunes1972/orizon-manager.git`. Se algum dia falhar por credencial, peça ao
> usuário rodar `!git push origin main` no próprio shell.

Front 3 — **DRE Analítico×Resumido (v5 §3.1, branch `feat/fin-v5-dre-toggle`, suíte 732→733):** `dre()` passou a devolver `detalhe` (composição nível 3 por linha, só contas com movimento); UI ganhou toggle **Resumido** (padrão, nível 2) / **Analítico** (expande nível 3 sob cada linha). Sem dado novo. TDD (1 unit).

Front 4b — **Controle de Repasse à Fábrica (v5 §6.2, branch `feat/fin-v5-repasse`, suíte 733→736):** `Lancamento` ganhou `motivo` (‘defeito_fabrica’|‘outro’, migração idempotente) — dimensão do reparo em garantia, no padrão do projeto_id. `registrar_evento(motivo=)` propaga; `total_a_cobrar_fabrica()` soma os `execucao_reparo_garantia` marcados defeito de fábrica. API `GET /api/financeiro/repasse-fabrica`; aba **Repasse Fábrica** (total + registrar reparo com motivo). **Não** cria Contas a Receber (só fase 2, se a fábrica reembolsar). TDD (2 unit + 1 HTTP).

Front 4c — **IA de apoio à classificação (v5 §6.3, branch `feat/fin-v5-ia`, suíte 736→740):** `sugerir_conta(owner, texto)` — **heurística sem LLM externo**: sobreposição de tokens (sem acento) entre o texto e o nome da conta + histórico de lançamentos, **ponderada por IDF** (token raro como ‘aluguel’ pesa mais que comum como ‘loja’). API `POST /api/financeiro/sugerir-conta`; na aba Lançamentos, campo “descreva o evento” → pré-preenche o Débito. **Nunca lança sozinha** — funcionário confirma/troca; a **sugestão + a escolhida** ficam registradas em `Lancamento.ia_sugestao` (mesmo princípio de snapshot dos gates). Arquitetura plugável p/ LLM depois. TDD (3 unit + 1 HTTP). **✅ ATUALIZAÇÃO v2→v5 COMPLETA** — 5 fronts (selo de posição §2.3 · DRE Analítico×Resumido §3.1 · Balanço Patrimonial §4 · 3 provisões §5/§6 · Repasse à Fábrica §6.2 · IA §6.3). Suíte 730→740. **Follow-up:** painel de provisões DA VENDA + wiring `fechamento_venda_*` no contrato.

**Módulo Financeiro — v5→v6 + integração das Provisões da Venda (`Especificacao_Financeiro_Orizon_v6.docx` agora é a
FONTE DE VERDADE; branch `feat/fin-v6-provisoes-venda`, suíte 740→744):** a v6 = v5 + **§6.4** (origem do valor das
provisões = **percentual configurável**) e **§6.5** (conexão com o Gate I). Implementado: **config `provisoes_contabeis`
{montagem_pct, garantia_pct}** no painel de Provisões do Financeiro (default + validação 0–100; UI com 3 campos), e
**assistência HERDA `provisoes.assist_pct`** (não recria o dado). `mod_contabil.pcts_provisao_venda(cfg)` +
`constituir_provisoes_venda(...)` (valor = % × valor da venda; idempotente por ref; só constitui % > 0) — **wirada na
criação do contrato** (`_fin_provisoes_venda_seguro`, fail-soft/isolado, após `_registrar_provisao_venda`, valor =
`orc.valor_total`). **Fronteira preservada:** os % ficam no Financeiro, desacoplados do motor de preço do Comercial
(§6.4). **Painel de Provisões da venda:** `provisoes_da_venda(owner, projeto)` = as 3 provisões com **saldo em aberto**
(constituído − revertido = saldo credor da conta 2.1.04.x por projeto); API `GET /api/financeiro/provisoes-venda?
projeto=` + lookup na aba Margem/Projeto. TDD (4 unit). **§6.5 (Gate I):** os valores das 3 provisões já ficam
**queryáveis** (via `provisoes_da_venda`) para compor o snapshot do Gate I — as regras do gate não mudam (aprovação
humana, IA só apresenta, snapshot auditável); **surfacing na tela de revisão do gate = conexão a fazer** quando o Gate
I for tocado. **✅ v6 completa.**

**Reconstrução visual v4 (`Padrao_Design_Orizon_v4.docx` + imagens de referência regeradas são a FONTE DE VERDADE de front-end; substitui v2/v3):** frente puramente visual, sem impacto nas regras do Financeiro (v6). **Front A — tokens (§2):** `:root` recalibrado nos 2 temas (escuro menos "terminal": `--accent` #4FA89E→#5BB8AC, superfícies/borda/texto revisados; light borders); **`--shadow` novo** (profundidade por sombra, não borda). **Front B — botões (§4):** secundário (`.btn-ghost`) **sem borda** → `--surface-2` + `--shadow` (corrige o "terminal"); primário com sombra; **altura fixa** 28/36/44 (sm/md/lg), peso 500, transição 150ms. **Front C — navegação (§4, item 8, a mais visível):** as 8 seções do Financeiro saíram das **tabs no conteúdo** e viraram **submenu na sidebar** (`#sb-submodulo`, indentado sob "FINANCEIRO", renderizado por `finSubmenuRender`); o painel central mostra **só a seção selecionada**; título vira "Financeiro / <Seção>"; `finTab` reescrito (corrigiu bug: só 4 dos 8 painéis trocavam). Item ativo do nav = `--surface-2` + `--shadow` + `--accent` (não borda); ícone em anel ○. **Toggle de tema (item 7)** virou **controle segmentado** (Claro | Escuro) no rodapé, sem borda. **Contradição resolvida na v4:** seções principais **só na sidebar**; componente Tabs reservado a sub-navegação dentro de uma seção. Suíte 744 (frontend puro). **Próximo:** Dashboard do Financeiro (§5, cards de saldo/DRE/cobertura de caixa) + Diagramacao_v2 (Dashboard/Kanban/Negociação/Seletor de Status) conforme os módulos forem tocados.

**Dashboard do Financeiro (v4 §5 + Diagramacao_v2 §1.3, branch `feat/fin-dashboard`, suíte 744→746):** a seção **Provisões** virou o **dashboard do mockup** — `dashboard_financeiro(owner)` agrega o **saldo em aberto das 3 provisões** (Montagem/Assistência/Garantia, saldo credor das contas 2.1.04.x no nível owner) + **resumo do DRE** (receita líquida/EBITDA/lucro) + **indicador de cobertura de caixa** (Caixa 1.1.01 ÷ provisões em aberto — v6 §6.1, alerta se <1×). API `GET /api/financeiro/dashboard`; UI = cards com profundidade por `--shadow` (sem borda), + botão **"Configurar 
**Comercial — Kanban (funil de vendas, v4 §5 + Diagramacao_v2 §1.4, branch `feat/comercial-kanban`, suíte 746):** a aba Projetos ganhou um toggle **Lista | Funil**. O Funil renderiza o board Kanban do template §1.4: colunas fixas por status (Quente/Morno/Frio/Convertido/Fechado/Perdido, cada header com a cor do token `--st-*` + contador), cards com profundidade por `--shadow` (nome peso 500 + cliente muted), clique no card abre o projeto. **Mover é ação explícita** (menu 'mover ▾' no card → `projStatusSet` PATCH `/api/projetos/<nome>/status`), nunca automático — mesmo princípio dos gates. Frontend puro (reaproveita a lista `/projetos` + o endpoint de status existente; sem backend novo). **Follow-up:** drag-and-drop (hoje é por menu); Kanban da Expedição; submenu de sidebar para os demais módulos.

**Expedição — Kanban (pedidos por etapa, v4 §5 + Diagramacao_v2 §1.4, branch `feat/expedicao-kanban`, suíte 746→748):** nova tela **page-13** (Expedição/Logística) alcançada pelo card do Hub (`_HUB_DESTINO.expedicao`). Endpoint `GET /api/expedicao/kanban` (gate pelo módulo `expedicao`): agrupa os projetos da loja pela **etapa do ciclo em andamento** entre 12–16 (Implantação/Produção/Entrega no depósito/Emissão NF-e/Entrega no cliente) — usa a etapa mais avançada `em_andamento` de cada projeto. Board com cards de profundidade `--shadow` (nome_safe + cliente); clique abre o projeto (o avanço da etapa continua no fluxo do ciclo, com seus gates — não se move a etapa direto do Kanban). Manifesto: domínio `expedicao` += rota. **Gotcha corrigido:** `import mod_tenancy` dentro do handler tornava o nome local do `do_GET` inteiro (UnboundLocalError em 69 testes) — removido, pois já é import de módulo. TDD (2 HTTP). **Follow-up:** drag-and-drop; submenu de sidebar para Expedição (hoje só via Hub).

**Sidebar — ícones Tabler (fix visual):** os itens da sidebar renderizavam círculos genéricos (`::before`) herdados do PNG de referência. Trocado por **Tabler Icons webfont** (`@tabler/icons-webfont@3.31.0` via CDN, ao lado do Google Fonts): um ícone outline distinto por item — Módulos `ti-layout-grid`, Projetos `ti-diamond`, Admin `ti-settings`, Config `ti-adjustments`; submenu do Financeiro (`_FIN_SECOES` ganhou campo `ic`): Provisões `ti-shield-dollar`, Plano de Contas `ti-list-tree`, Lançamentos `ti-receipt`, DRE `ti-report-money`, Balanço `ti-scale`, Margem/Projeto `ti-chart-dots`, Reconciliação `ti-refresh`, Repasse Fábrica `ti-truck-delivery`. CSS: `.nav-item:has(>.ti)::before{display:none}` esconde o círculo onde há ícone (fallback preservado); o glifo herda `currentColor` → muted/accent como o resto. Sem emoji, stroke uniforme do webfont. Frontend puro (Ctrl+F5).

## Sessão 46 — Diagramação/Navegação v4 (2 correções)
**Correção 1 — Sidebar em acordeão (Diagramacao_v4 §2, suíte 748→749):** a sidebar deixou de mostrar só o módulo aberto. Novo `#sb-modulos` renderizado por `sbNavRender()` reusa `_usuarioAtual.hub` (mesmas faixas do Hub) e lista os módulos de domínio por faixa; `_SB_MODULOS` dá o ícone Tabler distinto de cada módulo/seção e as seções do submenu. Um só módulo expandido por vez (`_sbModuloAberto`); clicar num módulo com seções expande o acordeão e abre a 1ª seção, clicar noutro colapsa o anterior. Módulos-folha (Comercial→Projetos, Fiscal, Expedição) navegam direto; módulos sem tela (Produção/Estoque/Pós-venda) aparecem como 'em breve' (muted). Cadastro: seções (Clientes/Parceiros + stubs) migradas das abas do conteúdo para o submenu da sidebar (§2.5) e a barra de abas do page-10 foi ocultada (`#cad-tabs display:none`) p/ não duplicar navegação; `cadTab`/`finTab` passaram a sincronizar o acordeão. `goPage` chama `sbSyncActive(n)` (mapa `_PAGE_MODULO`) p/ realçar/expandir o módulo da página. Removido `finSubmenuRender`/`#sb-submodulo`.
**Correção 2 — Painel de Provisões data-driven (Diagramacao_v4 §1.3):** `mod_contabil.dashboard_financeiro` deixou de hardcodar as 3 provisões; agora enumera as contas ANALÍTICAS do grupo `2.1.04` que existirem no Plano de Contas (nome vem da conta), então criar uma provisão nova no plano faz surgir um card sem tocar na tela. Teste novo `test_dashboard_provisoes_data_driven`.
**Decisões/ambiguidades registradas (usuário pediu p/ documentar):**
- (C2) O doc diz 'um card por conta do grupo 2.1.x que existir' MAS também 'hoje são 3' — o PLANO_PADRAO tem 5 contas de provisão (inclui Comissão 2.1.04.01 e Devolução 2.1.04.04). Reconciliei enumerando o grupo e EXCLUINDO essas duas (`_PROV_PAINEL_EXCLUI`): Comissão é despesa de venda (baixa via pagamento_comissao), Devolução não tem evento/percentual hoje (saldo sempre 0). Assim 'hoje = 3' vale por exclusão explícita, e uma conta 2.1.04.06+ nova aparece sozinha. Descrição do card: mapa opcional `_PROV_PAINEL_SUB` com fallback genérico.
- (C1) 'os 8 módulos SEMPRE visíveis' vs tenancy (módulos desligáveis por loja): segui o Hub (`hub_layout`) e mostro os módulos ATIVOS agrupados por faixa — com tudo ligado (default) aparecem os 8. Prioriza consistência com o Hub e respeita o gating por loja.
- (C1) '§2.4 Remover Clientes e Parceiros da sidebar': no build atual eles NÃO estavam como itens de topo da sidebar; agora existem só como submenu de Cadastro (caminho único ao dado), cumprindo a intenção.
- (C1) Ordem do submenu de Cadastro: funcionais primeiro (Clientes, Parceiros) e depois os stubs (Fornecedores/Funcionários/Terceiros); o doc permite reordenar por frequência ('decisão de negócio').
- (C1) Projetos segue como único Atalho; na page-0 realço o Atalho (nav-00), não o módulo Comercial, p/ evitar realce duplicado do mesmo destino.

**Painel de Projetos — colunas Consultor e Especificador (lapidação):** a lista de projetos (`renderProjResultados`) ganhou duas colunas. **Consultor** = criador do projeto (`projetos_meta.criado_por_id`), resolvido no backend em `_enriquecer_projetos_com_status` (novo `consultor_id`/`consultor_nome` via `Usuario`). **Especificador** = 'Sim/Não' conforme houver parceiro cadastrado (`parceiro_nome`, já resolvido por `_enriquecer_projetos_com_parceiro`); no 'Sim' o nome do parceiro aparece no tooltip (atributo title). Teste e2e `test_lista_projetos_traz_consultor`.

**Projetos — consultor na criação + botão Editar (lapidação, suíte 750→755):** 
- **Criação:** o consultor responsável (`criado_por_id`) é o usuário logado por padrão. Gerente+ (níveis fora do escopo-próprio) veem um seletor `#novo-proj-consultor` (via `GET /api/projetos/consultores`, campo `pode_atribuir`) e podem indicar outro consultor da loja; o consultor cria sempre para si (seletor escondido e ignorado no backend). Enforcement em `/projetos/novo`.
- **Editar:** botão 'Editar' ao lado de 'Abrir' na lista abre modal `#modal-proj-editar` (Nome, Cliente, Parceiro/especificador, Consultor) pré-preenchido do `_projListaBase`; salva via `POST /api/projetos/<nome>/editar` enviando só os campos alterados. Regras: renomear altera só o rótulo (nome_safe/chave preservada); reatribuir consultor exige gerente+; Cliente e Parceiro travam após contrato totalmente assinado (mesmo princípio do endpoint de parceiro), Nome e Consultor seguem editáveis. Novo endpoint GET consultores + `_usuarios_atribuiveis_da_loja`/`_usuario_pertence_a_loja`. Testes: `test_projeto_editar_e2e.py` (5). 
**Decisões (confirmadas via AskUserQuestion):** consultor atribuível por gerente+ (consultor travado nele); Editar cobre Nome/Cliente/Parceiro/Consultor; pós-contrato trava Cliente e Parceiro. Nota: no form de criação o seletor do gerente vem pré-selecionado nele mesmo — ele troca para o consultor real.

## Sessão 47 — Revisão de módulos e navegação (Modulos_Orizon_v4)
**Manifesto (`modulos.py`):** renomeados os RÓTULOS (ids preservados) `producao`→'Projetos' e `expedicao`→'Expedição'. Removido o módulo `posvenda` (virou FAIXA, não módulo). Novos domínios stub `captacao` (faixa vendas), `montagem` e `assistencias` (faixa montagem). `DOMINIOS_ORDEM` atualizado (Captação primeiro; Montagem/Assistências ao fim). FAIXAS inalteradas. Testes ajustados em test_modulos.
**Navegação (frontend):** 
- **Hub removido** — page-08 repurposada como tela genérica **EM CONSTRUÇÃO** (`emConstrucao(rotulo)`); item 'Módulos' saiu da sidebar; `hubRender` não é mais chamado. Operacional aterrissa em **Projetos** (page-0).
- **Sidebar em lista PLANA** — `sbNavRender` achata `_usuarioAtual.hub` (sem cabeçalhos de faixa), todo módulo clicável. Módulo sem `go`/`secoes` → `sbModuloClick` mostra EM CONSTRUÇÃO (realce mantido via `sbSyncActive` no page-8). Ícones Tabler novos: captacao `target-arrow`, producao/Projetos `ruler-measure`, montagem `hammer`, assistencias `lifebuoy`.
- **Financeiro:** aba 'Repasse Fábrica' removida do submenu (`_FIN_SECOES`) — migra p/ Assistências (§6.2 v7). Endpoint/painel `repasse-fabrica` seguem existindo, só não são mais aba.
**Escopo desta passada = estrutural (módulos + navegação + stubs EM CONSTRUÇÃO), conforme o doc.** O **motor de lançamento de Assistências** (Especificacao_Financeiro v7 §6: casos motivo→custo Paga/Loja/Fábrica, venda no Comercial, Provisão Assist.Técnica/Garantia, relatório 'a cobrar da fábrica') fica como PRÓXIMA frente — depende do módulo Assistências (casos), hoje EM CONSTRUÇÃO. Nomenclatura das contas mantida (Assistência Técnica/Garantia; Loja/Fábrica é só mapeamento conceitual).

## Sessão 48 — Módulo Expedição: CicloLogistico + Kanban com painel de Detalhe (Modulos_Orizon_v5 §7 / Diagramacao_v5 §1.4)
O antigo Kanban (agrupava projetos por etapa do ciclo 12–16) foi substituído pela entidade dedicada **CicloLogistico** (`database.py`): status_atual (7 estágios: Pedido Enviado→Em Produção→Aguardando Recebimento→Recebido no Depósito→NFe Emitida→Em Trânsito→Entregue), prazos planejados + datas realizadas (4 pares), transporte (transportadora/CT-e/rastreio), referências por ID (projeto_nome, nfe_id) sem duplicar dado, e **CicloLogisticoTransicao** (histórico auditável quem/quando). `create_all` cria as tabelas.
**`mod_expedicao.py`** (novo módulo de domínio, registrado no manifesto): STATUS, mapeamentos REALIZADO_AO_ENTRAR (captura) e PRAZO_POR_STATUS (badge de atraso), `criar_ciclo`/`mover`/`atualizar_detalhe`/`card_kanban`/`card_detalhe`/`esta_atrasado`.
**Endpoints (main.py):** GET `/api/expedicao/kanban` (7 colunas por status + meta), GET `/api/expedicao/cards/<id>` (detalhe+histórico), POST `/api/expedicao/cards` (criar), POST `.../mover` (transição+captura), POST `.../<id>` (editar prazos/transporte). Gating por módulo + isolamento por loja.
**Frontend:** Kanban read-only (card = projeto/cliente + nº pedido + badge Atrasado; clique abre Detalhe). Painel de Detalhe (modal, template Detalhe/Formulário) com seções Identificação/Prazos/Transporte/Histórico; '+ Novo pedido' (projeto+nº+prazos). Regra de captura: ao trocar o status no seletor, os campos Realizado que ele captura são pré-preenchidos com hoje (editáveis) antes de 'Mover'. Planejado entra na criação. Testes: `test_expedicao.py` reescrito (7). Suíte 755→760.
**Decisões documentadas:** (a) card criado manualmente ('Novo pedido' pelo Assistente Logístico ao enviar o pedido à fábrica — é a única forma de gravar Planejado 'uma vez na criação'). (b) Como há 7 status e só 4 pares Planejado/Realizado, produção-concluída e saída-da-fábrica são capturadas juntas ao entrar em 'Aguardando Recebimento' (não há status próprio de saída); NFe Emitida e Em Trânsito não capturam prazo. Tudo editável no Detalhe. (c) 'Mover' altera só status+realizados; edições de prazo/transporte usam 'Salvar'.
**Nota:** o Diagramacao_v5 Parte 2 (Navegação) ainda descreve o modelo antigo (acordeão c/ faixas + Hub); como o usuário pediu 'navegação segue como estava' e esta frente é só Expedição, mantida a sidebar plana da Sessão 47. Frente futura: motor de lançamento de Assistências (Financeiro v7 §6).

## Sessão 49 — Módulo Assistências: motor de lançamento (Modulos_Orizon_v5 módulo 10 / Financeiro v7 §6)
Assistências deixou de ser EM CONSTRUÇÃO e ganhou o motor completo. **Duas dimensões independentes por caso:** sub_tipo (Assistência Montagem × Pós-Conclusão) e tipo_custo (Paga/Loja/Fábrica) DERIVADO do motivo (tabela dos 6 motivos). Modelo `AssistenciaCaso` (`database.py`); `create_all` cria a tabela.
**`mod_assistencias.py`** (novo domínio, depende_de += financeiro): MOTIVOS→tipo_custo, SUB_TIPOS, EVENTO_POR_CUSTO, `criar_caso`/`realizar_caso`/`listar`/`a_cobrar_fabrica`/`meta`. **Motor (v7 §6):** realizar um caso posta o lançamento via `mod_contabil.registrar_evento` (idempotente por ref `assist:<id>`): **Loja** → `execucao_assistencia` (baixa Provisão Assist.Técnica 2.1.04.05); **Fábrica** → `execucao_reparo_garantia` (baixa Provisão Garantia 2.1.04.03) + entra no relatório 'a cobrar da fábrica'; **Paga** → novo evento `venda_assistencia` (Contas a Receber 1.1.02 × Receita c/ Vendas de Assistência 4.1.02), sem tocar provisão.
**Endpoints (main.py):** GET `/api/assistencias/casos?tipo=` (lista + meta + a_cobrar_fabrica), POST `/casos` (criar; tipo_custo derivado), POST `/casos/<id>/realizar` (posta o razão via resolver_owner). Gating por módulo + isolamento por loja.
**Frontend:** nova page-14 (módulo Assistências agora abre tela, não EM CONSTRUÇÃO): card 'A cobrar da fábrica', filtro Todos/Loja/Fábrica/Paga, tabela de casos com badge de tipo de custo e ação Realizar, modal '+ Novo caso' (motivo mostra o tipo de custo derivado ao vivo). Testes: `test_assistencias.py` (7, incl. razão de cada tipo). Suíte 760→767.
**§6.2 honrado:** a classificação/relatório de repasse saiu do Financeiro (aba Repasse já removida na Sessão 47) e vive aqui; 'a cobrar da fábrica' NÃO é Contas a Receber formal (só controle p/ negociação; reembolso real = fase 2, flag `reembolsado_fabrica`). Nomenclatura das contas mantida (Assist. Técnica/Garantia). Montagem segue EM CONSTRUÇÃO.

## Sessão 50 — Correção Admin/Config: dois itens distintos do Núcleo (Modulos_Orizon_v8)
Desfaz a fusão da v7. **Admin** (identidade/acesso) ganhou a aba **Perfis de Usuário** (o antigo page-9 de limites de desconto por perfil migrou p/ dentro do Admin — `adminPerfisCarregar` renderiza os cards e chama `cfgRenderizarPerfis`). **Config** virou item distinto (page-9 repurposado) com abas **Provisões · Comissão de Vendas · Documentos**:
- **Provisões:** painel de % migrou do Financeiro/Admin p/ Config → Provisões (`adminFinanceiroCarregar` agora renderiza em `#cfg-panel-provisoes`), + **novo campo `comissao_pct`** (Provisão de Comissão de Vendas) em `provisoes_contabeis` (mod_provisoes default+validação).
- **Comissão de Vendas:** botão que abre o modal de faixas/limitador (deslocado do Financeiro p/ cá).
- **Documentos:** cards de modelos (contrato/proposta/demais) — edição em construção [NOVO].
**Financeiro → Provisões** ficou só monitoramento (removido o botão 'Configurar %'). Testes de config ajustados (comissao_pct). Suíte 767 verde.
**Decisões:** (a) Admin/Config são páginas com abas internas (consistente com o padrão de abas do Admin já existente), não submenu de sidebar. (b) O antigo 'Config' do rodapé (limites de desconto/perfil) era o mais próximo de 'Perfis de Usuário' → movido p/ Admin; a sidebar segue com Admin e Config como itens distintos (Admin no menu, Config no rodapé, como já era). (c) `comissao_pct` é persistido como config; a auto-constituição da Provisão de Comissão no fechamento fica como próxima frente (mesma cautela contábil das demais).

**Nova tela de entrada (static/login.html do usuário) ligada ao acesso:** a página substituída tinha o formulário (#email/#senha) mas só o script do toggle de tema — sem submit. Adicionado o handler que faz `POST /api/auth/login` ({login, senha}, credentials same-origin), exibe erro inline (#loginErro) e redireciona p/ `/` no sucesso; `<form>` com `novalidate` + estado 'Entrando…' no botão. Backend: `auth.fazer_login` passou a aceitar **login OU e-mail** (case-insensitive) — a tela nova usa e-mail e as contas antigas seguem entrando pelo login. `/login` já era servido de static/login.html (auth_routes) — sem mudança ali. Teste `test_login_email.py`. Suíte 768 verde.

**Numeração de contrato padronizada + proposta = 1ª página do contrato:** `gerar_num_contrato` passou ao formato **`<SIGLA><AAAAMMDD><SEQ:5>`** (sigla da loja de 3 letras + ano-mês-dia + 5 dígitos sequenciais, contínuos por prefixo) — ex. `INS2026071000001`; ganhou parâmetro `prefixo`. Novo `gerar_num_proposta` = mesmo formato com prefixo fixo **`PV`**. A **proposta comercial** agora é a **capa (1ª página) do contrato** via WeasyPrint (novos `montar_html_proposta`/`gerar_pdf_proposta` em mod_contrato — reaproveitam `_html_capa`, sem as cláusulas e sem a quebra de página), numerada com `PV...`. Endpoint `GET /api/orcamentos/<id>/proposta/pdf` repointado do .docx/LibreOffice para o PDF-da-capa; nº da proposta gerado 1x e persistido em `orcamentos.num_proposta` (nova coluna + migração). Testes: formato novo, sequência contínua, ignora formato antigo, prefixo PV, e capa da proposta com PV. Suíte 771. Legado (modelo_proposta.docx/mod_proposta) permanece mas sai do fluxo.
**Decisão registrada:** número concatenado sem separadores (sigla+data+seq); a sequência recomeça em 00001 para o formato novo (números antigos com traços não contaminam). Data no número é a de emissão; só o SEQ é sequencial.
