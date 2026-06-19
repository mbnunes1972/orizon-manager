# DEV_LOG.md — Diário de Desenvolvimento
## Omie_V3 | Dalmóbile

---

## RESUMO ATUAL
> Atualizado em: 2026-06-19 (sessão 16 — parâmetros de negociação por orçamento no banco: margens + desconto individual por ambiente persistidos por orçamento; migração automática do projeto.json. Antes: sessão 15 — fix do bloqueio pós-aprovação)

### [ESTADO] O que está funcionando
- App rodando em `http://167.88.33.121:8765` (servidor DEV) e `http://127.0.0.1:8765` (local)
- Sistema de autenticação completo: login, logout, sessões via cookie
- **10 perfis (`perfis.py`, fonte única):** Diretor (50%), Gerente de Vendas (20%), Consultor (10%), Gerente Administrativo/Financeiro, Assistente Logístico, Conferente, Supervisor de Montagem, Assistente Administrativo, Projetista Executivo, Medidor. Permissões centralizadas: `desconto_max`, `ver_parametros`, `autorizar` (desconto), `gerir_usuarios`, `aprovar_financeiro`, `registrar_medicao`, `aprovar_medicao_reprovada`. Perfil técnico `admin` **aposentado** (migrado para `diretor` via `perfis_v2_2026`). Detalhes em `docs/USUARIOS.md`.
- **Usuários-exemplo (`seed.py`, 1 por perfil):** `pdm2026` (Diretor), `lds2026` (Ger. Vendas), `mds2026` (Consultor), `gaf2026` (Ger. Adm/Fin), `med2026` (Medidor) + demais — **senhas de exemplo, trocar antes de produção**.
- **Painel Admin → Usuários:** CRUD (criar/editar perfil/telefone/ativar-desativar/resetar senha), acesso para Diretor ou Gerente Adm/Financeiro; `nav-07` gateado por `pode_gerir_usuarios`.
- Módulo Clientes completo com ViaCEP, máscaras, CRUD, unicidade
- **Auto-sync Omie:** ao criar cliente, tenta registrar no Omie em background thread; grava `omie_sync_status` (`ok`/`pendente`/`erro`) + `omie_sync_erro` na tabela `clientes`
- Módulo Parceiros completo com tipos, comissão padrão, CRUD
- **Painel Admin (page-07):** fila de clientes com sync pendente/erro, botão "Tentar" por cliente
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
- **Módulo Contrato (EP-10):** `mod_contrato.py` gera o `.docx` a partir do template por marcadores `modelo_contrato_mapeado.docx` (`_substituir_marcadores` + `_preencher_grade`) → PDF via LibreOffice; **número do contrato** `INS-AAAA-MM-DD-SEQ` no cabeçalho + data; grade de parcelas valor+data (sem ordinal, traços nos vazios); `[TOTAL_CONTRATO]`; 2º signatário = cliente; testemunhas provisórias; hash SHA-256 de assinatura
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
- `salvarOrcamento()` no frontend é stub (só mostra toast) — não persiste nada além do que já é auto-salvo nos endpoints de ambiente/margem
- Módulo Clientes e Parceiros vinculados a orçamentos (planejado)
- **Trocar as senhas de exemplo do `seed.py`** (10 usuários) antes de produção — pelo Painel Admin → Usuários (perfil técnico `admin` foi aposentado)
- Refinar espaçamento visual do bloco de assinaturas no PDF (validado por estrutura, não por render — LibreOffice ausente no dev local)
- **Template do contrato:** ajustes nas variáveis (backlog anotado no último commit — ver `docs/` ou `CONTRATOS/`)
- **LibreOffice no VPS:** verificar disponibilidade; app funciona sem ele (fallback .docx), mas PDF é o ideal
- Etapa 6 do ciclo: marcada ao gerar contrato — testar fluxo completo no VPS

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
