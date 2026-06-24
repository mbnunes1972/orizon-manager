# DEV_LOG.md — Diário de Desenvolvimento
## Omie_V3 | Dalmóbile

---

## RESUMO ATUAL
> Atualizado em: 2026-06-22 (sessão 25 — **F4: suíte de regressão E2E de isolamento** (substitui o smoke manual pendente). Harness hermético em `tests/conftest.py` — servidor real (`main.Handler`) numa thread em porta efêmera + banco SQLite e `PROJETOS_DIR` **temporários** (rebind de `database.ENGINE`/`Session`/`DB_PATH` e `PROJETOS_DIR` em storage/main/mod_omie, restaurados no teardown) + login real (cookie `omie_session`). **33 testes** em `tests/test_isolamento_f4_e2e.py` cobrindo toda a matriz: leitura cross-loja de cliente/projeto/orçamento/contrato → **404**, listagens escopadas, **403** administrativo, **401** anônimo em todos os IDORs corrigidos (status/descontos/valor/parceiros/briefings/ambientes), escrita cross-loja bloqueada com estado intacto, carimbo de `loja_id` na criação, colisão de CPF sem vazamento. **234 testes verdes**. **Bug de produção achado e corrigido:** `import threading` redundante em `do_POST` tornava `threading` local à função inteira → `UnboundLocalError` (quebrava o sync Omie em background ao criar cliente + threads do fluxo de negociação); guard `test_do_post_nao_faz_shadowing_de_threading`. Mergeado na `main` (não-pushed: 38 commits à frente de origin). Antes: sessão 24 — F4 isolamento operacional (~30 endpoints escopados, vários IDORs reais corrigidos); sessão 23 — F3 contrato puxa da loja)

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
- GitHub: `https://github.com/mbnunes1972/omie_v3`
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

**Verificação:** pytest **167** verde (10 novos: schema, colunas, migração+idempotência+não-sobrescreve-abrangência, seed). Smoke do `init_db()` completo sobre uma **cópia do `omie.db` real**: loja seed criada e **0 registros com `loja_id` NULL** (11 usuários, 6 clientes, 14 projetos, 20 orçamentos, 13 contratos). Sem mudança de UI/rotas/contrato (confirmado por revisão de spec em cada task) — regressão por construção. **Pendente:** regressão Playwright ao vivo não rodada (evitar mutar o DEV DB antes do merge; F1 não tem superfície de UI).

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
- **Deploy:** sub-projetos 1–4 + correções empurrados ao GitHub; produção atualizada via runbook (deps já instaladas, `OMIE_HOST=0.0.0.0`, banco recriado/seedado com os 10 perfis, `no-cache` ativo).

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
