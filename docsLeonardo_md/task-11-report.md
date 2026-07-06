# Task 11 — Report

Remover código docx, rota `/contrato/editar` e testes antigos.

## O que foi removido

### `mod_contrato.py`
- Funções/símbolos docx do **motor de contrato**: `preencher_contrato`,
  `montar_variaveis_contrato`, `_formatar_bloco_pagamento`, e a constante `_MODELO`
  (caminho de `modelo_contrato_mapeado.docx`).
- Funções de preenchimento de tabela/grade específicas do docx do **contrato**:
  `_preencher_grade`, `_preencher_ambientes`, `_set_cell_text`, `_localizar_tabela`,
  `_unique_cells`, `_proteger_editaveis`.
- Import órfão: `from docx import Document` (nenhum consumidor restante no módulo).

### `main.py`
- Handler completo da rota `POST /api/projetos/<nome>/contrato/editar` (abria o
  .docx no Word/LibreOffice local com watcher de regeneração de PDF).
- Import de `montar_variaveis_contrato` (não usado em lugar nenhum de `main.py`).
- Variável morta `aviso = None` e o `if aviso: resp["aviso"] = aviso` na rota de
  geração do contrato (`POST /contrato`) — `aviso` nunca era escrito.

### `static/index.html`
- Botão "Editar contrato (gerencial)" (chamava `abrirModalEditarContrato()`).
- Funções JS `abrirModalEditarContrato()` e `confirmarEditarContrato()` (faziam
  `fetch` em `/contrato/editar`).

### `tests/test_contrato.py`
Removidos todos os testes que dependiam do motor docx do contrato:
`test_montar_variaveis_contrato_*`, `test_gerar_pdf_usa_modelo_e_chama_libreoffice`,
`test_preencher_signatario_e_testemunhas`, `test_geracao_completa_*`,
`test_cabecalho_num_contrato_substituido`, `test_template_oficial_tem_marcadores`,
`test_template_tem_marcador_tipo`, `test_template_assinaturas_normalizadas`,
`test_assinatura_cliente_mesmo_estilo_da_empresa`,
`test_assinaturas_nome_e_cpf_em_linhas_separadas`,
`test_substituir_marcadores_basico/case_e_duplo_colchete/em_tabela/cabecalho_fragmentado`,
`test_subst_preserva_formatacao_por_run`, `test_preencher_grade_*`,
`test_protegido_*` / `test_nao_protegido_sem_documentprotection`,
`test_converter_pdf_nao_regenera_docx`, `test_localizar_tabela_forma_pagamento`,
`test_preencher_ambientes_*`, `test_contrato_com_secao_ambientes` e o helper
`_ctx_parcelas` (só era usado pelo teste do cabeçalho removido).

Mantidos (motor novo + validações + utilitários independentes de docx):
`test_construir_contexto_*`, `_cliente_completo` + `test_validar_cliente_*`,
`test_email_fallback_consultor`, `test_gerar_num_contrato_*`,
`test_parse_pagamento_*`, `test_forma_label_mapeia_codigos`,
`test_montar_mapping_inclui_tipo/inclui_empresa_e_cpfs`, `test_ambientes_*`
(`ambientes_valor_contrato`), fixture `_isola_contratos_dir`.
(`validar_loja_para_contrato` e `contrato_desatualizado` já tinham suítes
próprias em `tests/test_contrato_loja.py` e `tests/test_contrato_staleness.py` —
não tocadas.)

## Desvio do brief (achado durante a remoção, verificado por grep antes de apagar)

O brief listava `_substituir_marcadores`, `_subst_paragrafo`, `_converter_pdf`,
`_libreoffice_cmd` e `LibreOfficeIndisponivel` para remoção. Ao rodar a suíte após
a primeira passada de remoção, `tests/test_proposta.py` e
`tests/test_proposta_e2e.py` quebraram: **`mod_proposta.py`** (frente separada —
Proposta comercial, ainda em `.docx`, ver `.superpowers/sdd/progress.md` linhas
259-267) importa e chama diretamente `mod_contrato._substituir_marcadores`,
`mod_contrato._converter_pdf` e `mod_contrato.LibreOfficeIndisponivel` (além de
`construir_contexto`, `_montar_mapping`, `_formatar_valor`, que já estavam na
lista de "manter").

Como o motor de marcadores em `.docx` e a conversão via LibreOffice ainda são a
via de produção da Proposta (frente concluída e em produção, fora do escopo desta
task), **restaurei essas 5 peças** (`_subst_paragrafo`, `_substituir_marcadores`,
`LibreOfficeIndisponivel`, `_libreoffice_cmd`, `_converter_pdf`) e os imports
`subprocess`/`platform` que elas usam, com um comentário no topo do módulo e nas
seções explicando que são legado mantido só para `mod_proposta.py` — não removê-las
sem migrar a Proposta primeiro. Tudo o mais da lista original do brief (`_MODELO`,
`preencher_contrato`, `_preencher_grade`, `_preencher_ambientes`, `_set_cell_text`,
`_localizar_tabela`, `_unique_cells`, `_proteger_editaveis`,
`montar_variaveis_contrato`, `_formatar_bloco_pagamento`) foi confirmado — via
grep, antes de apagar — como usado apenas pelo motor docx do contrato (agora
morto) e permanece removido.

## Resultado da suíte

```
$ python3 -m pytest -q
376 passed, 647 warnings in 20.65s
```

0 failed.

## Self-review

- Suíte 100% verde (376 passed / 0 failed) — comando e saída acima.
- `grep -n "contrato/editar\|LibreOffice\|_MODELO\|preencher_contrato" mod_contrato.py main.py static/index.html`:
  únicas ocorrências restantes são (a) o comentário/seção de `mod_contrato.py`
  explicando por que `LibreOfficeIndisponivel`/`_libreoffice_cmd`/`_converter_pdf`
  foram mantidos para `mod_proposta.py`, e (b) um aviso de UI pré-existente em
  `static/index.html` ("LibreOffice não encontrado no servidor...") ligado ao
  branch `temDocx && !temPdf` da rota `GET /contrato` (status), não à rota
  `/contrato/editar` removida — fora do escopo listado no brief, deixado como
  está (é código morto hoje porque `gerar_pdf_contrato` só produz `.pdf`, mas
  remover esse branch de UI não fazia parte da task e teria efeito colateral
  maior que o escopo pedido).
- Nenhum símbolo docx do contrato (`preencher_contrato`, `_preencher_grade`,
  `_preencher_ambientes`, `_set_cell_text`, `_localizar_tabela`, `_unique_cells`,
  `_proteger_editaveis`, `montar_variaveis_contrato`, `_formatar_bloco_pagamento`,
  `_MODELO`) é referenciado em nenhum lugar do repo (grep limpo).
- Imports órfãos removidos de `mod_contrato.py` (`from docx import Document`) e de
  `main.py` (`montar_variaveis_contrato`). `hashlib`, `os`, `json`,
  `datetime` mantidos (usados). `subprocess`/`platform` foram removidos e depois
  restaurados (ver seção "Desvio do brief" acima) porque ainda servem
  `_converter_pdf`/`_libreoffice_cmd` (legado da Proposta).
- `modelo_contrato_mapeado.docx` **não foi tocado/apagado** (fora de escopo;
  confirmado presente em `ls -la`).
- `contrato_editar.py` (módulo usado só pela rota removida) **não foi tocado** —
  fora do escopo do brief (arquivos listados eram só `mod_contrato.py`,
  `main.py`, `tests/test_contrato.py`, `static/index.html`). Ficou órfão (nada
  mais o importa em `main.py`), mas seu teste próprio,
  `tests/test_editar_contrato.py`, testa as funções do módulo diretamente (não
  via rota HTTP) e continua passando — não removido.

## Concerns

- `contrato_editar.py` ficou sem nenhum chamador em `main.py` (órfão) — decisão
  de manter, pois remover o arquivo em si estava fora do escopo listado no brief
  para esta task; pode ser endereçado numa limpeza futura junto com seu teste.
- O aviso de UI "LibreOffice não encontrado..." em `static/index.html` (branch
  `temDocx && !temPdf`) é hoje inalcançável para contratos novos (sempre gerados
  em PDF via WeasyPrint), mas foi deixado por estar fora do escopo explícito do
  brief.
- Peguei a divergência do brief (símbolos ainda usados por `mod_proposta.py`)
  só depois de rodar a suíte inteira — o `grep -n` pedido no brief antes de cada
  remoção foi feito símbolo a símbolo dentro de `mod_contrato.py`/`main.py`/
  `static/`, mas não cobria `mod_proposta.py` de saída; a suíte completa (que
  inclui `tests/test_proposta*.py`) foi o que expôs o problema, e a correção foi
  aplicada antes de fechar a task.

## Arquivos alterados

- `/mnt/e/2026/estudo_de_ia/omie_v3/mod_contrato.py`
- `/mnt/e/2026/estudo_de_ia/omie_v3/main.py`
- `/mnt/e/2026/estudo_de_ia/omie_v3/static/index.html`
- `/mnt/e/2026/estudo_de_ia/omie_v3/tests/test_contrato.py`
