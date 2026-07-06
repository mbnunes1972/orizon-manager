### Task 11: Remover código docx, rota /contrato/editar e testes antigos

**Files:**
- Modify: `mod_contrato.py`, `main.py`, `tests/test_contrato.py`

**Interfaces:** nenhuma nova (remoção).

- [ ] **Step 1: Remover funções docx de `mod_contrato.py`**

Apague: `preencher_contrato`, `_preencher_grade`, `_preencher_ambientes`, `_subst_paragrafo`, `_substituir_marcadores`, `_set_cell_text`, `_localizar_tabela`, `_unique_cells`, `_proteger_editaveis`, `_libreoffice_cmd`, `_converter_pdf`, `LibreOfficeIndisponivel`, `montar_variaveis_contrato`, `_formatar_bloco_pagamento`, e a constante `_MODELO`. Remova imports mortos (`from docx import Document`, `platform`, `subprocess`, `hashlib` se não usado — conferir; `hashlib` é usado por `calcular_hash_assinatura`, manter).

- [ ] **Step 2: Remover a rota `POST /contrato/editar`**

Em `main.py`, apague o handler `POST /api/projetos/<nome>/contrato/editar` (~L3353–3436) inteiro, e o botão/uso no frontend (`static/`) que chama `/contrato/editar` (grep por `contrato/editar`).

Run: `grep -rn "contrato/editar" main.py static/ 2>/dev/null`
Expected: sem resultados após a remoção.

- [ ] **Step 3: Remover testes específicos de docx**

Em `tests/test_contrato.py`, apague os testes que dependem do `.docx`/funções removidas: `test_preencher_grade_*`, `test_preencher_ambientes_*` (as versões docx), `test_subst_*`, `test_localizar_tabela_*`, `test_substituir_marcadores_*`, `test_template_*` (que abrem `_MODELO`), `test_protegido_*`, `test_geracao_completa_*`. **Mantenha** os testes de `ambientes_valor_contrato`, `_parse_pagamento`, `gerar_num_contrato`, `calcular_hash_assinatura`, `contrato_desatualizado`, `validar_*`.

- [ ] **Step 4: Rodar a suíte inteira**

Run: `python3 -m pytest -q`
Expected: PASS (verde). Corrigir qualquer import residual apontado pelos erros.

- [ ] **Step 5: Commit**

```bash
git add mod_contrato.py main.py tests/test_contrato.py static/
git commit -m "refactor(contrato): remove caminho docx, rota /contrato/editar e testes antigos"
```

---

