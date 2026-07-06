# Progresso — Contrato HTML/Markdown -> PDF (12 tasks)

Plano: docs/superpowers/plans/2026-07-02-contrato-html-pdf.md
Branch: feat/contrato-html-pdf
BASE: e2ccf94 (snapshot docx preservado)

Task 1: complete (commits e2ccf94..7deda53, review clean apos fix do nome apt weasyprint)
Task 2: complete (commits 7deda53..a918bdf, review clean)
  - Minor (final-review triage): _substituir_marcadores_html duplica _aplica_mark (candidato a colapsar em _aplica_mark)
Task 3: complete (commits a918bdf..e3075e2, review clean apos fix da linha vazia completa)
Task 4: complete (commits e3075e2..2e358ab, review clean)
Task 5: complete (commits 2e358ab..021f248, review clean apos redesign linha-a-linha)
  - DESIGN: _html_corpo processa linha-a-linha (Markdown so inline); evita <ol>/<li> das linhas numeradas. Atualizar spec/plano (Opcao A) para refletir isso.
Task 6: complete (commits 021f248..3112c17, review clean; logo=word/media/image1.png)
Task 7: complete (commits 3112c17..18dfc33, review clean; teste do adendo deferido p/ Task 8)
  - Minor (Task 8 triage): assercao OR fraca no teste da capa (checar positivamente ausencia de [NOME_CLIENTE] etc.)
Task 9: complete (commits 18dfc33..1106b4f, review clean; PDF real 25KB, sem warnings WeasyPrint)
  - NOTA: troca de gerar_pdf_contrato deixou 2 testes pre-existentes RED (test_gerar_pdf_usa_modelo_e_chama_libreoffice [docx] e test_contrato_real_geracao_e_assinatura [E2E]) — quebra encenada planejada; resolvidas na Task 10 (E2E) e Task 11 (remove teste docx).

## PARADA (checkpoint): tasks aditivas 1-7,9 completas. Falta: Task 8 (gate humano: migracao juridica), Task 10 (rota), Task 11 (remove docx), Task 12 (verificacao visual).
Task 8: complete (migracao contrato.md + refinamentos de capa/corpo; verificado visualmente via PDF; commit apos gate humano interativo)
  - PENDENCIA: fonte de config do REDE_IDENTIFICADOR (hoje fallback cidade da loja) — decidir/ligar na rota
  - PENDENCIA: 3.6 ausente na origem (mantido); revisao juridica final do contrato.md recomendada
Task 10: complete (commits 07e4f9e..f3941a0, review clean; E2E verde, rota usa novo motor)
  - Minor (Task 11): variavel 'aviso' morta em main.py (limpar ao remover fallback docx)
Task 11: complete (commits f3941a0..ce06f54, review clean; docx do contrato removido, proposta-legado preservado; suite 376/0)
  - Minor (final-review triage): contrato_editar.py orfao (modulo morto); branch aviso-LibreOffice inalcançavel em static/index.html (pre-existente)
Task 12: complete (DEV_LOG sessao 39; verificacao visual feita nas rodadas de review da Task 8; PDF minimo+completo confirmados %PDF-)

## REVISAO FINAL DA BRANCH (opus): 2 Important corrigidos
- escape de valores de marcador (adendo/nome/endereco) no caminho HTML — commit final
- underscores da clausula 2.3.4.1 preservados (protege '_' no _inline_md) — verificado visualmente
- Minor: 2.3.4.1 (4 niveis) agora cl-3 (nao alinea)
- Minors nao-bloqueantes deixados p/ follow-up: _aplica_mark morto (se ainda existir); assercao OR fraca no teste da capa; contrato_editar.py orfao; branch aviso-LibreOffice no static/index.html (pre-existente)
- PENDENCIAS de produto: fonte de config do REDE_IDENTIFICADOR; revisao juridica final do contrato.md (3.6 ausente)
