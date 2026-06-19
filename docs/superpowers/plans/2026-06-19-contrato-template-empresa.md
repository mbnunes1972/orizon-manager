# Alinhar geração de contrato ao template reestruturado — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer a geração de contrato preencher o bloco de assinatura reestruturado (empresa + cliente + 2 testemunhas, nome e CPF em marcadores separados), deixar a suíte verde, e robustecer o cabeçalho contra fragmentação de marcadores.

**Architecture:** `mod_contrato._montar_mapping` ganha os marcadores novos (`NOME_EMPRESA`, `CNPJ_EMPRESA`, `CPF_CLIENTE`, `CPF_TESTEMUNHA_1/2`) apontando para constantes reais (já no template) e dados de cliente/testemunhas. O ramo do cabeçalho de `_substituir_marcadores` passa a reusar `_subst_paragrafo` (que opera no texto concatenado do parágrafo → robusto a runs fragmentados). Dois testes que validavam o rótulo antigo "CPF/CNPJ:" inline são atualizados para a nova estrutura (marcador de CPF separado).

**Tech Stack:** Python + python-docx; pytest; geração real verificada via app/Playwright.

**Estrutura real do bloco de assinatura no template (Heading 2, cada um em seu parágrafo):**
linha de assinatura `____` → `[NOME_EMPRESA]` → `[CNPJ_EMPRESA]`; idem para `[NOME_CLIENTE]`/`[CPF_CLIENTE]`, `[NOME_TESTEMUNHA_1]`/`[CPF_TESTEMUNHA_1]`, `[NOME_TESTEMUNHA_2]`/`[CPF_TESTEMUNHA_2]`. Os marcadores de CPF estão **sozinhos** (sem rótulo "CPF/CNPJ:").

---

## File Structure

- `mod_contrato.py` — constantes `_NOME_EMPRESA`/`_CNPJ_EMPRESA`; novos itens em `_montar_mapping`; ramo de cabeçalho de `_substituir_marcadores` reusando `_subst_paragrafo`.
- `tests/test_contrato.py` — atualizar 2 testes estruturais; adicionar 1 teste de mapping e 1 de cabeçalho robusto.

---

## Task 1: Constantes da empresa + mapeamentos novos

**Files:**
- Modify: `mod_contrato.py` (constantes perto de `_TELEFONE_LOJA`/`_EMAIL_LOJA` ~21-33; `_montar_mapping` ~397-434)
- Test: `tests/test_contrato.py` (novo teste)

- [ ] **Step 1: Write the failing test** — append to `tests/test_contrato.py`:

```python
def test_montar_mapping_inclui_empresa_e_cpfs():
    from mod_contrato import _montar_mapping, _NOME_EMPRESA, _CNPJ_EMPRESA, _TESTEMUNHAS
    ctx = {"cliente_cpf": "111.222.333-44"}
    m = _montar_mapping(ctx, {})
    assert m["NOME_EMPRESA"] == _NOME_EMPRESA
    assert m["CNPJ_EMPRESA"] == _CNPJ_EMPRESA
    assert m["CPF_CLIENTE"] == "111.222.333-44"
    assert m["CPF_TESTEMUNHA_1"] == _TESTEMUNHAS[0][1]
    assert m["CPF_TESTEMUNHA_2"] == _TESTEMUNHAS[1][1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_contrato.py::test_montar_mapping_inclui_empresa_e_cpfs -v`
Expected: FAIL (`ImportError` para `_NOME_EMPRESA` / `KeyError`).

- [ ] **Step 3: Add the constants** — em `mod_contrato.py`, perto de `_EMAIL_LOJA`, adicionar:

```python
_NOME_EMPRESA = "INSPIRIUM MOVEIS PLANEJADOS E DECORACAO LTDA"  # TODO: configurador de lojas
_CNPJ_EMPRESA = "19.152.134/0001-56"                            # TODO: configurador de lojas
```

- [ ] **Step 4: Add the mappings** — em `_montar_mapping`, dentro do dict retornado, acrescentar (perto das chaves de testemunha):

```python
        "NOME_EMPRESA":      _NOME_EMPRESA,
        "CNPJ_EMPRESA":      _CNPJ_EMPRESA,
        "CPF_CLIENTE":       ctx.get("cliente_cpf", "") or "",
        "CPF_TESTEMUNHA_1":  _TESTEMUNHAS[0][1],
        "CPF_TESTEMUNHA_2":  _TESTEMUNHAS[1][1],
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_contrato.py::test_montar_mapping_inclui_empresa_e_cpfs -v`
Expected: PASS.

- [ ] **Step 6: Confirm the 4 auto-fixed tests now pass**

Run: `python -m pytest tests/test_contrato.py::test_geracao_completa_sem_marcadores_remanescentes tests/test_contrato.py::test_protegido_mantem_texto_e_valores tests/test_contrato.py::test_geracao_completa_com_forma_parcela tests/test_contrato.py::test_assinatura_cliente_mesmo_estilo_da_empresa -v`
Expected: 4 passed (os mapeamentos eliminam os marcadores remanescentes; `[NOME_EMPRESA]`→nome real contém "INSPIRIUM MOVEIS PLANEJADOS", Heading 2 preservado).

- [ ] **Step 7: Commit**

```bash
git add mod_contrato.py tests/test_contrato.py
git commit -m "feat(contrato): mapeia empresa (NOME/CNPJ) e CPFs separados do bloco de assinatura"
```

---

## Task 2: Atualizar os 2 testes estruturais ao novo bloco

**Files:**
- Modify: `tests/test_contrato.py` (`test_preencher_signatario_e_testemunhas` ~275; `test_assinaturas_nome_e_cpf_em_linhas_separadas` ~782-806)

- [ ] **Step 1: `test_preencher_signatario_e_testemunhas`** — a asserção do formato antigo (linha 275):

```python
    assert "Ana Cliente\nCPF/CNPJ:" in full   # cliente: nome numa linha, CPF/CNPJ na linha de baixo
```

substituir por (nome do cliente numa linha e o **valor** do CPF na linha imediatamente abaixo, conforme novos marcadores `[NOME_CLIENTE]`/`[CPF_CLIENTE]`):

```python
    assert "Ana Cliente\n111.222.333-44" in full   # nome numa linha, CPF (valor) na linha de baixo
```

(As demais asserções do teste — "Consultor Z", "Jaime Perinazzo", "Felipe Guizalberte" — permanecem.)

- [ ] **Step 2: `test_assinaturas_nome_e_cpf_em_linhas_separadas`** — o teste lê o TEMPLATE e exige que a linha após `[NOME_*]` comece com um rótulo de CPF. No template novo a linha seguinte é o **marcador** de CPF correspondente. Substituir o corpo do teste por:

```python
def test_assinaturas_nome_e_cpf_em_linhas_separadas():
    """Cada signatário do bloco de assinatura tem o NOME numa linha e o
    marcador de CPF/CNPJ na linha imediatamente abaixo (nova estrutura)."""
    from docx import Document
    from mod_contrato import _MODELO
    d = Document(_MODELO)
    pars = [(p.text or "").strip() for p in d.paragraphs]

    def linha_seguinte(marcador_nome, marcador_doc):
        for i, t in enumerate(pars):
            if marcador_nome in t:
                assert "CPF" not in t and "CNPJ" not in t, f"{marcador_nome} tem doc na mesma linha: {t!r}"
                j = i + 1
                while j < len(pars) and not pars[j]:
                    j += 1
                assert j < len(pars) and marcador_doc in pars[j], \
                    f"linha de doc de {marcador_nome} inesperada: {pars[j] if j < len(pars) else None!r}"
                return
        raise AssertionError(f"marcador {marcador_nome} não encontrado")

    linha_seguinte("[NOME_EMPRESA]",      "[CNPJ_EMPRESA]")
    linha_seguinte("[NOME_CLIENTE]",      "[CPF_CLIENTE]")
    linha_seguinte("[NOME_TESTEMUNHA_1]", "[CPF_TESTEMUNHA_1]")
    linha_seguinte("[NOME_TESTEMUNHA_2]", "[CPF_TESTEMUNHA_2]")
```

- [ ] **Step 3: Run both updated tests**

Run: `python -m pytest tests/test_contrato.py::test_preencher_signatario_e_testemunhas tests/test_contrato.py::test_assinaturas_nome_e_cpf_em_linhas_separadas -v`
Expected: 2 passed.

- [ ] **Step 4: Full contract test file**

Run: `python -m pytest tests/test_contrato.py -q`
Expected: tudo verde (os 6 originais + os novos).

- [ ] **Step 5: Commit**

```bash
git add tests/test_contrato.py
git commit -m "test(contrato): atualiza bloco de assinatura ao novo template (nome/CPF em marcadores separados)"
```

---

## Task 3: Cabeçalho robusto a fragmentação (defensivo)

**Files:**
- Modify: `mod_contrato.py` (ramo de headers em `_substituir_marcadores` ~163-167)
- Test: `tests/test_contrato.py` (novo teste)

- [ ] **Step 1: Write the failing test** — append to `tests/test_contrato.py`:

```python
def test_substituir_marcadores_cabecalho_fragmentado():
    """Marcador fragmentado em múltiplos runs no cabeçalho é substituído."""
    from docx import Document
    from docx.oxml.ns import qn
    from mod_contrato import _substituir_marcadores
    d = Document()
    hdr = d.sections[0].header
    p = hdr.paragraphs[0]
    # simula fragmentação do Word: '[', 'NUM_CONTRATO', ']'
    p.add_run("[")
    p.add_run("NUM_CONTRATO")
    p.add_run("]")
    _substituir_marcadores(d, {"NUM_CONTRATO": "INS-2026-01-01-001"})
    txt = "".join(t.text or "" for t in hdr._element.iter(qn('w:t')))
    assert "INS-2026-01-01-001" in txt
    assert "[NUM_CONTRATO]" not in txt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_contrato.py::test_substituir_marcadores_cabecalho_fragmentado -v`
Expected: FAIL (o ramo atual substitui por `w:t` isolado; fragmentado não é trocado).

- [ ] **Step 3: Refactor the header branch** — em `_substituir_marcadores`, substituir o bloco atual dos headers:

```python
    for sec in doc.sections:
        for hdr in (sec.header, sec.first_page_header, sec.even_page_header):
            for t_el in hdr._element.iter(qn('w:t')):
                if t_el.text and "[" in t_el.text:
                    t_el.text = _aplica_mark(t_el.text, mapping)
```

por (reusa `_subst_paragrafo`, robusto a runs; NÃO passa `coletor` — cabeçalho é fixo):

```python
    for sec in doc.sections:
        for hdr in (sec.header, sec.first_page_header, sec.even_page_header):
            for par in hdr.paragraphs:
                _subst_paragrafo(par, mapping)
            for tbl in hdr.tables:
                for row in tbl.rows:
                    for cell in row.cells:
                        for par in cell.paragraphs:
                            _subst_paragrafo(par, mapping)
```

(`qn` pode deixar de ser usado nesse ponto; manter o import se ainda for usado em outro lugar do arquivo — verifique antes de remover.)

- [ ] **Step 4: Run the new test + the existing header test**

Run: `python -m pytest tests/test_contrato.py::test_substituir_marcadores_cabecalho_fragmentado tests/test_contrato.py::test_cabecalho_num_contrato_substituido -v`
Expected: 2 passed (o novo passa; o existente do número de contrato no cabeçalho continua verde).

- [ ] **Step 5: Commit**

```bash
git add mod_contrato.py tests/test_contrato.py
git commit -m "fix(contrato): cabecalho robusto a marcadores fragmentados em runs (reusa _subst_paragrafo)"
```

---

## Task 4: Verificação end-to-end

**Files:** nenhum (execução/verificação)

- [ ] **Step 1: Suíte completa**

Run: `python -m pytest -q`
Expected: tudo verde (incluindo os 6 antes falhos + os 3 novos testes).

- [ ] **Step 2: Geração com dados reais** — ver [[contrato-verificacao-dados-reais]] e [[gui-verification-playwright]]. Com o app rodando (login `pdm2026`/`teste123`), gerar um contrato real (orçamento com pagamento via `/calcular_*`) e baixar o `.docx`. Confirmar:
  - **Nenhum** marcador `[...]` remanescente no documento.
  - Bloco de assinatura: `INSPIRIUM MOVEIS PLANEJADOS E DECORACAO LTDA` + `19.152.134/0001-56`; nome+CPF do cliente; nomes+CPFs das testemunhas.
  - Número e data do contrato no cabeçalho corretos.

- [ ] **Step 3: Confirmar o docx do template versionado** — o template editado pelo usuário (`modelo_contrato_mapeado.docx`, working tree) deve ser **commitado** junto desta entrega (faz parte do alinhamento). Garantir que `git add modelo_contrato_mapeado.docx` foi incluído em algum commit desta branch (se ainda não, commitar agora):

```bash
git add modelo_contrato_mapeado.docx
git commit -m "chore(contrato): template com bloco de assinatura reestruturado (empresa + CPFs separados)"
```

- [ ] **Step 4: DEV_LOG + finalizar branch**
  - Acrescentar seção de sessão ao `DEV_LOG.md`.
  - Seguir `superpowers:finishing-a-development-branch` (merge em `main`).

```bash
git add DEV_LOG.md
git commit -m "docs: DEV_LOG — alinhamento do contrato ao template reestruturado"
```

---

## Self-Review (cobertura da spec)

- **Mapear NOME_EMPRESA/CNPJ_EMPRESA (valores reais) + CPF_CLIENTE/CPF_TESTEMUNHA_1/2** → Task 1.
- **4 testes de "marcador remanescente"/estilo passam com os mapeamentos** → Task 1 Step 6.
- **2 testes estruturais atualizados ao novo bloco** → Task 2.
- **Cabeçalho robusto a fragmentação** → Task 3.
- **Suíte verde + geração real** → Task 4.
- **Commitar o template editado** → Task 4 Step 3.
- **Consistência de nomes:** `_NOME_EMPRESA`/`_CNPJ_EMPRESA` (constantes), chaves `NOME_EMPRESA`/`CNPJ_EMPRESA`/`CPF_CLIENTE`/`CPF_TESTEMUNHA_1`/`CPF_TESTEMUNHA_2` (mapping) — idênticas aos marcadores do template.
