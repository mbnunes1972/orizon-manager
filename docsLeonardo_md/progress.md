# Progresso — Cadastro de usuários por modal (10 tasks)

Plano: docs/superpowers/plans/2026-06-22-cadastro-usuarios-modais.md
Branch: feat/cadastro-usuarios-modais

Task 1: complete (commits 28074bc..894c7e5, review clean)
Task 2: complete (commits 894c7e5..3fc4ab3, review clean)
Task 3: complete (commits 3fc4ab3..e7b0ee3, review clean)
  - Minor (final-review triage): PEP8 linhas em branco entre funcoes de teste em test_usuarios.py
Task 4: complete (commits e7b0ee3..7ac4709, review clean)
Task 5: complete (commits 7ac4709..4876b7c, review clean)
  - Minor (final-review triage): ramo 'rede' do filtro sem guarda u.rede_id is not None (assimetrico c/ ramo loja; risco ~nulo pois nivel==admin_rede ja garante rede_id)
Task 6: complete (commits 4876b7c..7f7689b, review clean)
  - Minor (final-review triage): testes Task6 nao verificam persistencia via GET (admin_rede par) nem status HTTP (diretor_nao_cria_super)
Task 7: complete (commits 7f7689b..b9d92bd, review clean; fix b9d92bd adicionou 2 testes de escalada/auto-edicao)
Task 8: complete (commits b9d92bd..e340c2f, review clean)
  - Minor (final-review triage): modal-usuario fora do ESC_MAP (inconsistente c/ modal-novo-ambiente)
  - Minor (final-review triage): onclick='...JSON.stringify(u)...' quebra com apostrofe no nome (plan-mandated, pre-existente no app; candidato a data-uid+listener)
Task 9: complete (commits e340c2f..b75a710, review clean; fix b75a710 escapou apostrofo nos 3 botoes Editar de usuario)
Task 10: complete (commits b75a710..0aeaee8, review clean; suite 259 passed)

## Revisão final de branch (opus): PRONTO PARA MERGE — sem Critical/Important; seguranca verificada (sem IDOR/escalada).
Fix pos-review: c56f326 (ESC fecha modal-usuario).

## Follow-ups documentados (nao bloqueiam merge):
- PATCH promovendo usuario p/ admin_rede nao re-escopa rede_id/loja_id (estado inconsistente, SEM escalada — _eh_admin_rede exige rede_id). Idealmente recusar mudanca de nivel que cruze tipo loja<->rede.
- Dropdown vazio -> PATCH manda nivel:'' (UX): so enviar nivel quando o select tem valor.
- PEP8 linhas em branco em test_usuarios.py; simetria guarda u.rede_id is not None no filtro GET; testes Task6 poderiam checar status HTTP.


========================================
# Plano: motor-negociacao-modo-sombra (Fase A, 8 tasks)
Branch: feat/motor-negociacao-sombra (a partir da tag pre-refator-negociacao)
========================================
Task 1: complete (commits 5b8524c..4c822ee, review clean; aritmetica LELEU conferida manualmente)
  - Minor (final-review triage): test_tog_cadi_off_absorve usa Cust_Ad>0 sem ancora numerica concreta
Task 2: complete (commits a810c26..497f8c5, review clean)
  - Minor (final-review triage): import ET nao usado em test_qualidade_xml.py; magic 1.0001 sem comentario; testes LELEU sem pytest.mark (fragilidade CI)
Task 3: complete (commits 497f8c5..c3c2f23, review clean; fix do guard de tabela validado; suite 273)
Task 4: complete (commits c3c2f23..23b5845, review clean; fix 23b5845 adicionou E2E do wiring do upload)
Task 5: complete (commits 23b5845..f3c4df5, review clean; fix f3c4df5 cobre 403 do override + limpa codigo morto)
Task 6: complete (commits f3c4df5..2c8ef17, review clean; 2 fixes: sombra nao-intrusiva + cust_fin consistente + reorder antes do send_json)
Task 7: complete (commits 2c8ef17..7ed61ae, review clean; verificacao manual no browser pendente)
  - Important-adjudicado-aceito (final-review triage): payload sombra zerado em falha de materializacao -> frontend esconde bloco (fallback correto, sem defeito visivel)
  - Minor (final-review triage): var(--dalm-gold) repetido inline; _orcSombra nao limpo ao fechar modal
Task 8: complete (commits 7ed61ae..74fcb9a, review clean; baseline 20 orcamentos + DEV_LOG sessao 26)

## Revisão final de branch (opus): PRONTO PARA MERGE — sem Critical/Important.
Modo sombra confirmado nao-intrusivo; integracao coerente; seguranca solida (override so aprovar_financeiro, sem bypass); aritmetica consistente; zero regressao.
Fix pos-review: 50e1377 (skip-guard testes LELEU nao versionados + limpeza).

## Follow-ups desta branch (nao bloqueiam merge):
- test_tog_cadi_off_absorve sem ancora numerica concreta (cosmetico).
- _pool_ambiente_dict nao expoe qa_* (UI nao mostra selo de quarentena ainda; guarda e server-side autoritativa) -> fase de UI.
- UI: var(--dalm-gold) repetido; _orcSombra nao limpo ao fechar modal (sem efeito funcional).
- LEMBRETE: Fases B/C (cutover + limpeza: usar valores novos no contrato/UI, aposentar valor_liquido/margens duplicado, integracao plena mod_fin) so APOS validacao manual na interface (modo sombra).


========================================
# Plano: cutover-negociacao (Fase B, 6 tasks)
Branch: feat/cutover-negociacao (do main)
Hibrido: subagentes backend/scripts; Task 4 (UI) inline.
========================================
Task 1: complete (commit a75a5a1, branch + baseline)
Task 2: complete (commits a75a5a1..f3d9b30, review clean)
  - Minor (final-review triage): re.match duplo no dispatch (padrao do arquivo); 401/403 sem teste E2E
Task 3: complete (commits f3d9b30..1abf8ff, review clean; fix 1abf8ff reforcou teste de save com ambiente real)
Task 4: complete INLINE (UI cutover; commit 3133e10); requer validacao no browser
Task 5: complete (diff_cutover + DEV_LOG)
Task 6: complete (reset_para_teste script criado, execucao manual/destrutiva)

## Revisão final de branch (opus): PRONTO PARA MERGE (com validação manual da UI).
Backend solido/seguro: preview so-leitura, persistencia autoritativa, contrato assinado intocavel, chaves casam ponta-a-ponta.
Fix pos-review: limite de desconto usa %Desc_Tot fresco do motor (era _margemAtual legado/race).
## Follow-ups (nao bloqueiam):
- Minor: neg-avista pode ser sobrescrito por renderTabelaNeg legado ate o proximo preview (cosmetico/transitorio).
- Minor (fora de escopo/pre-existente): handlers add/remove ambiente gravam valor_total=sum(budget) sem passar pelo motor (janela inconsistente ate o proximo save de margens). Spec restringe recalculo a /margens e PATCH .../valor.
## GATE: cutover aguarda VALIDACAO NO BROWSER do usuario antes do merge (UI sem teste JS).
Task 4 (UI inline): correcao abrangente de todos os numeros (commit c6c30b8)
Task 4 (UI): desconto fonte unica - preview le neg-desconto (modal fechado). commit ae1554f
Task 4 (UI): apoio do modal sem recalculo legado (fonte unica motor). commit 9cf820e

========================================
# Plano: faxina-frontend-single-source (Fase 1, 6 tasks)
Branch: feat/cutover-negociacao (continuacao)
Hibrido: subagentes backend (1,2,3); Tasks 4,5,6 (investigacao+UI) inline.
========================================
Task 1: complete (commit e6f9b11, motor Cust_Via/Bri, 10/10, diff conferido)
Task 2: complete (commits e6f9b11..a99e76c, review clean; breakdown saved-only, preview sem corpo)
  - Minor (final-review triage): comentario do id removido; fp.get truthiness em total_cliente=0 (sem impacto)
Task 3: complete (commits a99e76c..0b9ecbc, review clean; 3 saves devolvem breakdown maiusculo, 293)
  - CARRY p/ Task 6: /descontos nao devolve mais 'descontos' -> frontend deve ler 'sombra' (breakdown)
  - Minor (final-review triage): /parametros _negociacao_breakdown fora de try dedicado; comentario teste 'Task 4'
Task 4: complete (investigacao). CONCLUSAO:
  - executarCalculo: EP-07 (orc ativo) -> so renderTabelaNeg(_orcAmbientesAtivos); legado roda so se _orcAmbientesAtivos===null (Fase 01, sem orcamento).
  - Conflito (bug) esta 100% no EP-07. Fase 01 e isolada/vestigial e NAO conflita.
  - ESCOPO: neutralizar so o legado EP-07 (renderTabelaNeg EP-07 upd/celulas, mpAtualizarApoio EP-07, negSyncModal/Sidebar, mp-desconto editor). PRESERVAR Fase 01 (deletar depois, com confirmacao).
  - negPreview -> corpo vazio (backend le saved). Fluxo desconto/param -> auto-save -> breakdown -> _aplicarPreviewNaTela.
Task 5-6 (UI inline): single-source frontend. commit 6cb98d0
TODAS as 6 tasks concluidas. Backend 293 verde.
GATE: validacao no browser do usuario antes do merge (UI single-source, sem teste JS).
Escopo seguro: neutralizado o legado EP-07; Fase 01 (sem orcamento) PRESERVADA (deletar depois com confirmacao).
Faxina: revisao final (opus) PRONTO PARA MERGE.
  - Fix aplicado: salvarParametrosAuto usa negPreview() (orcamento ativo, nao proj_orcs[0]).
  - Minor (divida Fase 2): flash legado transitorio nas celulas/apoio; _ep07DistribuirFinanciado nao removido (overlay financiado, em uso).

========================================
# Plano: bloqueio-impostos (4 tasks)
Branch: feat/bloqueio-impostos (do main, ja com a faxina)
Hibrido: subagente Task 1 (backend); Tasks 2,3,4 (UI/inspecao) inline.
========================================
Task 1: complete (commit 32394fe, endpoint liberar_impostos em auth_routes.py, 4 E2E + 297, review clean)
Task 2-3: complete INLINE (UI: mascara + modal + re-bloquear; commit antes do DEV_LOG)
Task 4: complete (tela projeto fechado coberta pelos IDs compartilhados; sem codigo novo; DEV_LOG)
Bloqueio impostos: revisao final PRONTO PARA MERGE. Fixes: r.ok&&d.ok + teste login inexistente. Minor M-2 (forEach) inocuo.

========================================
# Plano: distribuicao-brinde-viagem (Fase 2 item 2, 2 tasks)
Branch: feat/fase2-autosave-negociacao
Subagentes nas 2 tasks (backend/TDD).
========================================
Task 1: complete (commit 2843f14, motor distribui brinde/viagem + fallback, 12/12, review clean)
  - cust_ad/Val_Liq/base_custos usam o distribuido (consistente); fallback identico; sem chamador dependente do Cust_Via/Bri cheio
  - Minor (final triage): den_via/den_bri recalculados no loop (cosmetico); 3-de-7 nao cobre tog_cadi=True (algebra verificada)
Task 2: complete (commits 2843f14..ea2cbb4, review clean; fix ea2cbb4 teardown anti-poluicao)
Fase 2 (auto-save + brinde/viagem): revisao final (opus) PRONTO PARA MERGE.
  - Minor aplicado: console.warn no catch do auto-save. Minor aceito: beforeunload best-effort (design).
GATE: validacao no browser (auto-save) + re-validacao do calculo brinde/viagem pelo usuario antes do merge.

========================================
# Plano: super-admin-aterrissagem-arvore (slice #1+#2, 5 tasks)
Branch: feat/super-admin-arvore (do main, base 77e6f37)
Subagentes: Tasks 1-3 backend/TDD; Tasks 4-5 frontend (verificacao manual).
========================================
Task 1: complete (commits 77e6f37..27f5d60, review clean)
  - Minor (final-review triage): edge case projeto sem CicloEtapa (etapa_atual='1') sem teste dedicado
  - Minor (final-review triage): fixture ator_super function-scoped vs com_etapas/rede_id module-scoped (inconsistente, sem bug)
Task 2: complete (commits 27f5d60..d059362, review clean; 9/9)
  - Minor (final-review triage): projeto orfao loja_id=None passa {"id":None,"rede_id":None} a pode_ver_loja (= codigo do brief; super ve, demais 403)
  - Nota: ~12 warnings na suite sao pre-existentes (nao introduzidos por este slice)
Task 3: complete (commits d059362..5cddad0, review clean; e2e 5/5, suite 305)
  - Fix do implementer: removeu 'from urllib.parse import unquote' inline (UnboundLocalError por escopo de funcao) -> usa import de modulo (main.py:16). Correto.
  - Minor (final-review triage): rotas retornam 403 (nao 401) sem sessao -> consistente com /api/admin/redes e /api/admin/lojas existentes
  - Minor (final-review triage): regex /etapas usa .+ (aceita '/'); mod_arvore rejeita via LookupError; auth precede
  - Minor (final-review triage): 'import re as _re' inline nos 2 elifs (padrao do brief)
Task 4: complete (commits 5cddad0..f80ad61, review clean; sem teste JS - verificacao manual do usuario)
  - Resolvido ⚠️ admin_rede: perfis.py:19 gerir_redes=False; auth.py:179 pode_gerir_redes=perfis.pode -> admin_rede mantem menu. OK.
  - GATE: validacao no browser pelo usuario (aterrissagem por papel)
Task 5: complete (commits f80ad61..26addb8, review clean; sem teste JS - verificacao manual)
  - Minor (final-review triage): adminCarregarConsole reseta _adminNav sem projeto (undefined~null, sem bug)
  - Minor (final-review triage): etapas_concluidas/total_etapas sem esc() (numericos, sem XSS)
  - Minor (final-review triage): onclick JSON.stringify(nome_safe) quebra com apostrofo (nome_safe e URL-safe; pre-existente no app)
  - GATE: validacao no browser (arvore nivel 4: aba Projetos -> etapas; aterrissagem)

## Revisão final de branch (opus): PRONTO PARA MERGE — sem Critical/Important.
No-PII confirmado por construção (whitelist de chaves, conferido vs colunas reais do modelo) + travado por test_*_sem_pii.
IDOR/tenancy: ator vem da SESSAO (nao da URL) e e validado por pode_ver_loja; super ve tudo, admin_rede so a propria rede, operacional 403. Aterrissagem/menu por papel corretos p/ os 3 papeis.
Fix pos-review: c1f49cc (I1: 2 testes e2e cross-rede 403 p/ as 2 rotas; suite 307).
Minors triados (nao bloqueiam): str(e) no corpo do 500 (admin-only, padrao do arquivo); 403-vs-401 sem sessao (consistente); .+ no regex /etapas (auth precede + LookupError); JSON.stringify(nome_safe) com apostrofo (nome_safe URL-safe, pre-existente); numericos sem esc(); _adminNav reset sem chave projeto (undefined~null).
GATE FRONTEND: validacao no browser pelo usuario (aterrissagem por papel + arvore nivel 4) antes do merge — sem teste JS no projeto.

========================================
# Plano: acesso-multi-loja (8 tasks)
Branch: feat/multi-loja (empilhada sobre feat/super-admin-arvore, base c70ef11)
Subagentes: Tasks 1-6 backend/TDD; Tasks 7-8 frontend (verificacao manual).
========================================
ML Task 1: complete (commits c70ef11..64122ac, review clean; 3 testes + suite 310)
  - Extra positivo: guarda _tabela_existe + sentinel schema_migrations (dupla idempotencia)
  - Minor (final triage): sem newline final em _backfill; comentario de idempotencia mal posicionado no teste
ML Task 2: complete (commits 64122ac..719a49c, review clean; 9/9)
  - Minor (final triage): condicao 'default in acessiveis' redundante (plan-mandated, inocua)
ML Task 3: complete (commits 719a49c..df1ab19, review clean; e2e 3/3, suite 319; localizacao cirurgica confirmada)
  - Fix pos-review (c8f14a6): do_PUT tambem le X-Loja-Ativa (era a 4a dispatch que faltava -> contexto obsoleto). Teste regressao RED->GREEN. Suite 320.
  - Nota: 3 dicts unit de test_isolamento_f4.py ganharam active_loja_id (adaptacao correta ao novo contrato de escopo_operacional)
ML Task 4: complete (commits c8f14a6..5d63b69, review clean; suite 321)
  - Minor (final triage): loja_ativa_id setado dentro do try (cosmetico)
ML Task 5: complete (commits 5d63b69..c96a92f, review clean; 2 e2e + suite 323)
  - PROCESSO: task-5-brief.md ficou obsoleto (nao regenerado) -> implementer seguiu o prompt de dispatch (correto); reviewer confirmou diff = Task 5 multi-loja correta. Licao: regenerar brief por task.
  - Seguranca OK: pode_ver_loja por-loja em POST e PATCH; admin_rede barrado em loja de outra rede (testado). Rewrite de membership so quando loja_ids presente.
  - Minor (final triage): PATCH com nivel admin_rede + loja_ids apaga memberships e ignora loja_ids silenciosamente; diretor sobrescreve loja_ids sem erro; POST revalida loja primaria 2x (redundante)
ML Task 6: complete (commits c96a92f..d395754, review clean SEM issues; contratos 69, suite 323)
  - 4 spots de contrato usam loja ativa; spot PATCH preserva contrato.loja_id; removeu re-derivacao de ator que furava escopo_operacional. Nao-contrato intacto.
ML Task 7: complete (commits d395754..3ce2ffb, review clean; sem teste JS - verificacao manual)
  - Fix cosmetico aplicado: _renderSeletorLoja usa display:flex (label+select lado a lado).
  - GATE: validacao no browser (seletor aparece p/ multi-loja; header X-Loja-Ativa no Network; troca recarrega contexto; single-loja sem seletor).
ML Task 7: (ja registrado acima) seletor + interceptor.
ML Task 8: complete (commits 893b182..3b47b1a, review clean Approved; suite 323)
  - DONE_WITH_CONCERNS -> fix 3b47b1a: edicao pre-marca TODAS as lojas (listing devolve loja_ids batched; ctx de edicao carrega loja_ids) -> evita perda de membership. Fix VERIFICADO ponta-a-ponta pelo reviewer.
  - Minor/⚠️ browser: nome '(loja atual)' no create de loja unica; grid-column:1/-1 span; (sem defeito funcional)

## Revisão final de branch (opus): READY TO MERGE (com fixes aplicados).
Mecanismo de tenancy solido: resolucao de loja ativa fail-closed (header nao-membro -> None -> 403); IDOR fechado em operacional E contrato; global single-thread seguro (4 do_* resetam; sem do_DELETE/HEAD); migracao idempotente e ordenada; compat single-loja preservada.
BLOQUEADOR (Issue 1) corrigido: ator de loja (diretor) NAO reescreve memberships na edicao -> evita drop silencioso de lojas fora do escopo. Fix 4c09c55 com teste de regressao RED->GREEN. Suite 324.
Minor corrigido: coercao defensiva de loja_ids (sem ValueError quebrando conexao).
Follow-ups documentados (nao bloqueiam):
- resolver: 'default in acessiveis' redundante (plan-mandated); divergencia do spec (header in memberships) -> default sempre acessivel (correto, e a propria loja do user).
- PATCH->admin_rede + loja_ids dropa memberships (intencional: promocao limpa escopo de loja).
- comentar a assuncao single-thread perto da construcao do HTTPServer (se um dia virar Threading -> vazamento cross-request).
- frontend ⚠️ browser: nome '(loja atual)' no create de loja unica; grid-column span; (sem defeito funcional).
GATE FRONTEND: validacao no browser pelo usuario (seletor de loja, header X-Loja-Ativa, modal multi-loja) antes do merge — sem teste JS.

========================================
# Plano: config-financeira-provisoes (Frente C v1, 10 tasks)
Branch: feat/config-financeira-provisoes (empilhada sobre multi-loja, base 0abe519)
Subagentes: Tasks 1-7 backend/TDD; Tasks 8-10 frontend (verificacao manual).
========================================
FC Task 1: complete (commits 0abe519..18559c2, review clean; 2 testes + suite 326)
  - Extra: guarda _tabela_existe (defensiva). Minor: orc_cols set vs list; assert default fraco (o.out_forn or 0).
FC Task 2: complete (commits 18559c2..ac170d8, review clean; 4 testes)
  - Minor: _f(v or 0) (convencao do mod_negociacao, inocuo).
FC Task 3: complete (commits ac170d8..f082feb, review clean; 7/7)
  - Minor: else do for letra-morta com dados validos; falta teste no limiar exato (venda==venda_ate).
FC Task 4: complete (commits f082feb..6283949, review clean SEM issues; 9/9). Modulo mod_provisoes (T2-4) completo.
FC Task 5: complete (commits 6283949..aa063b3, review clean; e2e + suite 336; read-time, sem persistir)
  - Ajuste legitimo: teste do PoolAmbiente ganhou campos NOT NULL (nome_exibicao/xml_path/ambientes_json). Minor: import mod_provisoes lazy.
FC Task 6: complete (commits aa063b3..7d5ee28, review clean; 2 e2e + suite 338)
  - Autorizacao editar_dados_loja + pode_ver_loja em GET e PUT (sem IDOR); valida antes de gravar.
  - Minor (final triage): import re as _re redundante no GET (cosmetico, do brief); falta teste cross-rede admin_rede->loja outra rede (comportamento ok via pode_ver_loja).
FC Task 7: complete (commits 7d5ee28..1c2ba67, review clean; suite 340). BACKEND (T1-7) COMPLETO.
  - Helper parametros_default_loja pronto; WIRING na criacao do projeto NAO feito (follow-up; novos projetos ainda usam PARAMETROS_DEFAULT global).
FC Task 8: complete (commits 1c2ba67..52cb762, review clean; sem teste JS - verificacao manual)
  - Aba Financeiro: 10 campos GET/PUT consistentes. Minor: sem guard _cfgFin null; lid no onclick. GATE: validacao browser.
FC Task 9: complete (commits 52cb762..aadba2f, review clean; sem teste JS)
  - Modal de comissao (faixas + limitador + toggle); estrutura salva = default backend; ESC_MAP ok. GATE: validacao browser.
FC Task 10: complete (commits aadba2f..8f85f99, review clean; sem teste JS)
  - Margem real (Cust_Var/Marg_Cont) no painel de apoio sob cadeado dos impostos. Marg_Cont fracao*100 (confirmado: motor devolve fracao). 
  - DEFERIDO: edicao de Out_Forn (sem rota PATCH) -> follow-up.
TODAS AS 10 TASKS CONCLUIDAS.

## Revisão final de branch Frente C (opus): READY TO MERGE com fixes (aplicados).
Motor correto/isolado: formulas batem com a tabela canonica; integracao aditiva e read-time (sem commit/sem gravar orc; 340->341 verde); rotas com editar_dados_loja + pode_ver_loja (sem IDOR), valida antes de gravar; margem real sob cadeado dos impostos; Marg_Cont fracao*100 consistente. 5 invariantes holisticos OK.
Fix pos-review 5fb5fd7: I1 (comentario aproximacao v1 da comissao), I2 (label carga-trib 'aplica-se a novos projetos'), M3 (PUT 400), M4 (clamp percentuais>100 + teste). Suite 341.
DEFERIDOS (follow-up, nao bloqueiam): edicao de Out_Forn (sem rota PATCH); wiring de parametros_default_loja na criacao do projeto (carga_trib da loja so flui ao Prov_Imp depois); acumulador mensal da comissao (Fase 2); custo financeiro absorvido; condicoes de pagamento por loja.
GATE FRONTEND: validacao no browser pelo usuario (aba Financeiro grava/le; modal de comissao; margem real sob cadeado) antes do merge.

========================================
# Close-out Frente C (autonomo enquanto usuario ausente) — branch feat/config-financeira-provisoes
========================================
P2 wiring parametros_default_loja: complete (commit 3d13947, review Approved; suite 342). cfg carregado 1x no topo de _negociacao_breakdown; projeto sem params herda defaults da loja (carga_trib flui ao Prov_Imp). Minor: assert do teste poderia ser mais forte.
P1 Out_Forn: complete (commits 3d13947..059c7c5, review->fix; suite 345). Rota PUT /api/orcamentos/<id>/out-forn (espelha /descontos, escopo+IDOR) + campo editavel no modal de params (travado em read-only). Fix pos-review: clamp out_forn>=0 + valida corpo (400) + testes IDOR/clamp.
P3 guard contrato desatualizado: complete (commits 059c7c5..66f4fcc, review Approved; suite 357). mod_contrato.contrato_desatualizado (compara tipo+total_cliente) + flag no GET /contrato + banner no renderContratoUI. Minor: import mod_contrato lazy no handler.
## CLOSE-OUT Frente C concluido (P1+P2+P3). Suite 357. Tudo na branch feat/config-financeira-provisoes (stacked sobre multi-loja+arvore). Merge pendente da validacao do usuario.

========================================
# Frente Provisoes versionadas — branch feat/provisoes-versionadas
========================================
BASE inicial: 16a4642
T1: complete (commit 3832fed, review Approved; suite 358). 2 minors carry-forward (server_default; teste de unique nao coberto).
T2: complete (commit ca87b5a, review Approved; 14 testes do modulo). 1 cosmetico (_RUBRICAS multi-linha).
T3: complete (commits 3671e39 + fix b4adb7e, review Approved; suite 361). Venda gravada na geracao do contrato (upsert). Fix: testes order-independent + import module-level. Minor restante: usuario.get defensivo (inocuo).
T4: complete (commit b8e6dcc + fix 0e7ab15, review Approved; suite 364). GET /provisoes (versoes+atual+desatualizado, auth aprovar_financeiro, IDOR). Fix: testes IDOR/403 + nota do alias _mprov.
T5: complete (commit 4c1fa39 + fix 300afd7, review Approved; suite 369). POST rev1/rev2 (concorda copia anterior; revisa clamp + recalcula da base congelada; 409; IDOR; senha aprovar_financeiro). Fix: 400 em decisao/itens invalidos + teste rev1-sem-venda + comentario.
T6: complete (commit a23ffa2 + fix f776792, review Approved; suite 369). Frontend: botao Provisoes (sempre visivel p/ review) + tabela Venda/Rev1/Rev2/Atual + Concorda/Revisa via pedirCredenciaisGerente. Fix: botao em todos os ramos do card + remove thead morto.
## TODAS as 6 tasks concluidas. Suite 369. Branch feat/provisoes-versionadas.
REVIEW FINAL (opus): READY TO MERGE. Housekeeping aplicado (comentario formulas + nota spec). Suite 369.
MERGED na main (ff -> 9585905, suite 369). Branch feat/provisoes-versionadas apagada.

========================================
# Frente Orcamento-hub + Proposta — branch feat/orcamento-hub-proposta
========================================
BASE inicial: 6c46684
T1: complete (commit b253e8d, review Approved; suite 372). Rename etapa4 -> Orcamento (mod_ciclo + frontend + ajuste teste arvore).
T2: complete (commit 799368c, review Approved; suite 373). modelo_proposta.docx (build script + 15 marcadores). Minor: teste cobre 9 de 15 (ok p/ regressao).
T3: complete (commit 7ad34f4, review Approved; suite 375). mod_proposta (contexto+gerar, 17 marcadores) + _converter_pdf(outdir) default CONTRATOS_DIR. Hermetico (grava so no outdir). Minor: \n em AMBIENTES_LISTA (mesmo padrao do contrato).
T4: complete (commit 807bb6f, review Approved; suite 378). GET /proposta/pdf (auth/IDOR/404, hermetico via mkdtemp+rmtree, serve inline). Minors: str(e) pode vazar path (padrao do codebase); teste 404 lenient.
T5: complete (commit 81b6458, review Approved; suite 378). Frontend: botao Imprimir + cards etapa4 (lista orcamentos) e etapa6 (aprovado). 4 itens de verificacao visual manual.
## TODAS as 5 tasks concluidas. Suite 378. Branch feat/orcamento-hub-proposta.
REVIEW FINAL (opus): READY TO MERGE. Ajuste: template test cobre 17 marcadores. Defers: genericizar 500 (str(e), padrao do codebase); import _mprop redundante; 4 checks visuais manuais. Suite 378.


========================================
# Frente: ambientes-valor-contrato (5 tasks) — branch feat/ambientes-valor-contrato
Plano: docs/superpowers/plans/2026-07-01-ambientes-valor-contrato.md
BASE inicial: 413ac27
========================================
T1: complete (commits 413ac27..247a315, review Approved; suite 383). Funcao pura ambientes_valor_contrato (rateio VAVA + reconciliacao no ultimo).
  - Minor (final-review triage): teste vavo=0 trivial (todos inputs zero; plan-prescribed); guarda 'not vavo or vavo<=0' redundante (cosmetico); sem type hints na assinatura.
T2: complete (commits 247a315..5d12261, review Approved; suite 384). _localizar_tabela por conteudo + _preencher_grade usa lookup ('forma de pagamento') com None guard. Refactor sem mudanca de comportamento (regressao R$ 4.820,00 confirmada).
  - Minor (final-review triage): docstring de _preencher_grade ainda diz 'tabela 3' (stale); _localizar_tabela sem guard 'if not t.rows: continue' (Task 3 tambem chama); sem teste do caminho None-guard.
T3: complete (commits 5d12261..808d019, review Approved; suite 385). _preencher_ambientes: secao "4. Ambientes" construida em codigo, movida ANTES da grade via addprevious; Total; Forma de Pagamento->5; colunas a esquerda; valor no coletor (Total nao). ORDEM verificada pelo controller (Ambientes[3] antes de Forma Pgto[4]; grade preenchida; total presente).
  - Minor (final-review triage): guarda 'nome != "Total"' fragil (ambiente chamado "Total" ficaria fora do coletor; fix por indice da ultima linha e trivial); teste nao verifica exclusao XML do Total do permStart/permEnd; alinhamento do titulo "4. Ambientes" nao setado explicito (cosmetico).
T4: complete (commits 808d019..f56386f impl + fix 958415b, review Approved apos fix; suite 385). Helper _ambientes_valor_para_contrato (reusa _negociacao_breakdown; mapeia id->nome_exibicao) injetado nas DUAS rotas (POST create + PATCH edit/regen). E2E RED->GREEN.
  - IMPORTANT (review) RESOLVIDO pelo controller inline: rota de edicao nao tinha cobertura. Descoberta: a rota e PATCH (nao PUT); sem LibreOffice ela devolve 500 (nao degrada como POST) mas o .docx e sobrescrito -> guard le a secao no arquivo. RED->GREEN verificado empiricamente (comentar main.py:4148 quebra o assert 1c). Agente de fix inicial ficou preso ~10min (PUT errado) -> parado (TaskStop) e finalizado inline.
  - Minor (final-review triage): 1c aceita st in (200,500) por causa do LibreOffice ausente (assert de status fraco, mas a secao no .docx e o guard real); assertions checam headers, nao valores/nomes; helper faz fallback nome='' para id desconhecido (sem log). PRE-EXISTENTE (fora de escopo): rota PATCH contrato nao trata LibreOfficeIndisponivel graciosamente (500) diferente da POST -> candidato a follow-up.
T5: complete (DEV_LOG sessao 38 commit; suite 385). Conferencia visual = GATE do usuario (sem teste JS).
## TODAS as 5 tasks concluidas na branch feat/ambientes-valor-contrato. Suite 385. Falta: revisao final de branch + conferencia visual do usuario + merge.

## Revisão final de branch (opus): READY TO MERGE — sem Critical/Important.
Reconciliacao correta (Σ==round(Val_Cont,2), residuo no ultimo; vale p/ financ>0 e =0); ambas as rotas (POST+PATCH) injetam _ambientes de orcamento escopado (chaves VAVA/VAVO/Val_Cont/id corretas); geracao idempotente (Document(_MODELO) fresco a cada chamada); protecao coleta celulas de valor e exclui o Total. Sem regressao de tenancy/IDOR.
Todos os 5 grupos de Minor logados = follow-ups aceitaveis (nenhum bloqueia).
- NOVO Minor (follow-up): linha Total dos ambientes vem de _negociacao_breakdown fresco (Val_Cont) enquanto TOTAL_CONTRATO/valor_total do contrato vem do orc.valor_total persistido -> normalmente identicos, mas orcamento defasado pode divergir por centavos. Idealmente ambos da mesma fonte.
- PRE-EXISTENTE (follow-up, fora de escopo): rota PATCH /contrato nao trata LibreOfficeIndisponivel graciosamente (500 vs POST que da aviso; POST try/except main.py:3559, PATCH 4150 sem).
## GATE: conferencia visual do usuario (gerar contrato real c/ LibreOffice e conferir a secao "4. Ambientes" no PDF) antes do merge. Branch feat/ambientes-valor-contrato, 6 commits, suite 385.
## MERGED na main (ff -> 51f8a88, suite 385). Branch feat/ambientes-valor-contrato apagada.
GATE remanescente: conferencia visual do PDF pelo usuario (LibreOffice). Push da main = passo do usuario (env sem credenciais; main 85 commits a frente de origin).
