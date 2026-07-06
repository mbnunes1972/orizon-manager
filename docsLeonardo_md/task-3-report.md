# Task 3 Report: Linhas de ambientes (HTML)

## Summary
Implementou funções puras em `mod_contrato.py` para gerar `<tr>`s da tabela de ambientes da capa do contrato em HTML: 2 ambientes por linha, sobra ímpar com traços.

## TDD Process

### Step 1: RED (Testes que falham)
Adicionados 2 testes a `tests/test_contrato_pdf.py`:
- `test_html_ambientes_linhas_par_e_impar()`: 3 items (par/ímpar) → 2 linhas, com traços na sobra ímpar
- `test_html_ambientes_linhas_vazio()`: lista vazia → 1 linha com 1 slot em traços

```bash
python3 -m pytest tests/test_contrato_pdf.py -k html_ambientes -q
# Resultado: 2 failed (ImportError: cannot import name '_html_ambientes_linhas')
```

### Step 2: GREEN (Implementação)
Adicionadas 2 funções em `mod_contrato.py` (após `_formatar_data_br`):

**`_cel_amb(rotulo, valor)`**: Helper que retorna 2 `<td>`s (rótulo + valor) para um ambiente.

**`_html_ambientes_linhas(itens_valores: list[tuple[str,float]]) -> str`**: 
- Consome `_formatar_valor` e `_TRACO` (já existiam)
- Retorna `<tr>`s com 2 ambientes por linha
- Sobra ímpar (último slot de última linha) preenchida com traços
- Lista vazia → 1 linha com 1 slot em traços
- Escapa nomes com `from html import escape`

Lógica:
```python
n_linhas = ceil(n/2)  # (n + 1) // 2
Para cada linha k:
  slot 0: idx=2k   → item ou traço
  slot 1: idx=2k+1 → item ou traço
```

```bash
python3 -m pytest tests/test_contrato_pdf.py -k html_ambientes -q
# Resultado: 2 passed
```

### Step 3: Suíte completa
```bash
python3 -m pytest tests/ -q
# Resultado: 394 passed, 647 warnings
```

Todos os testes passam, sem regressão.

## Commit
```bash
git add mod_contrato.py tests/test_contrato_pdf.py
git commit -m "feat(contrato): linhas HTML de ambientes (2/linha, tracos na sobra)"
# [feat/contrato-html-pdf bcbc51e] feat(contrato): linhas HTML de ambientes (2/linha, tracos na sobra)
```

## Arquivos modificados
- `/mnt/e/2026/estudo_de_ia/omie_v3/mod_contrato.py`: +38 linhas (2 funções)
- `/mnt/e/2026/estudo_de_ia/omie_v3/tests/test_contrato_pdf.py`: +18 linhas (2 testes)

## Self-Review

### Nomes par/ímpar e linhas
✓ `n_linhas = (n + 1) // 2` (ceiling de n/2)
- n=0: 1 linha (special case) ✓
- n=1: 1 linha (2 slots, 1 vazio) ✓
- n=2: 1 linha (2 slots, ambos preenchidos) ✓
- n=3: 2 linhas (L1: 2 items, L2: 1 item + 1 vazio) ✓

### Escape de nomes
✓ `from html import escape` aplicado: `escape(str(nome))`
- Protege contra injeção de HTML em nomes de ambientes
- Conversão segura de qualquer tipo para string

### YAGNI
✓ Apenas 2 funções necessárias: helper `_cel_amb` + main `_html_ambientes_linhas`
✓ Reutiliza `_formatar_valor` e `_TRACO` existentes
✓ Sem lógica desnecessária

### Teste verifica comportamento real
✓ `test_html_ambientes_linhas_par_e_impar()`:
  - Conta `<tr>` (2 esperados)
  - Verifica presença de nomes e valores formatados ("Cozinha", "R$ 20.000,00")
  - Verifica 2 traços na sobra ímpar (rótulo + valor do 2º slot vazio)

✓ `test_html_ambientes_linhas_vazio()`:
  - Conta `<tr>` (1 esperado)
  - Conta traços (2 esperados = 1 slot vazio)

### Saída pristina
✓ Estrutura HTML limpa: `<tr><td class="...">...</td>...</tr>`
✓ Classes CSS: `amb-rotulo`, `amb-valor`
✓ Múltiplas linhas separadas por `\n`
✓ Sem espaços desnecessários

## Concerns
Nenhum concern crítico. A implementação segue exatamente o brief, com special case para lista vazia (1 slot em traços) necessário para passar nos testes.

## Resultado final
- Status: ✓ DONE
- Testes: 394 passed (incluindo 2 novos)
- Regressão: Nenhuma
- Commit: bcbc51e

---

## Fix de review (regra do design: linhas sempre completas)

**Problema:** O caso especial de lista vazia produzia 1 linha com apenas 1 slot (2 células/traços), mas a tabela tem 4 colunas (2 slots). Regra do design: "sempre linhas completas".

**Correção em `mod_contrato.py` (`_html_ambientes_linhas`):**
- Removido o bloco `if n == 0: return "<tr>" + _cel_amb(_TRACO, _TRACO) + "</tr>"`
- `n_linhas = (n + 1) // 2` → `n_linhas = max(1, (n + 1) // 2)`
- O laço já preenche os 2 slots com traços quando `idx >= n`.
- Resultado: vazio → uma `<tr>` com 4 `<td>` (2 slots em traços = 4 ocorrências de `_TRACO`).

**Correção em `tests/test_contrato_pdf.py` (`test_html_ambientes_linhas_vazio`):**
- Asserção final: `html.count(_TRACO) == 2` → `html.count(_TRACO) == 4`

### RED (antes da correção do código, com teste já atualizado para 4)
O teste `test_html_ambientes_linhas_vazio` esperava 4 traços mas o código ainda tinha o special case retornando 2 — FAIL esperado (correção de código + teste aplicadas em conjunto).

### GREEN
```bash
python3 -m pytest tests/test_contrato_pdf.py -k html_ambientes -q
# Resultado: 2 passed, 3 deselected

python3 -m pytest tests/ -q
# Resultado: 394 passed, 647 warnings
```

### Commit
```bash
git add mod_contrato.py tests/test_contrato_pdf.py
git commit -m "fix(contrato): linha vazia de ambientes vira linha completa (4 tracos)"
# [feat/contrato-html-pdf e3075e2] fix(contrato): linha vazia de ambientes vira linha completa (4 tracos)
```

## Resultado final (pós-fix)
- Status: ✓ DONE
- Testes: 394 passed
- Regressão: Nenhuma
- Commits: bcbc51e (feat) + e3075e2 (fix)
