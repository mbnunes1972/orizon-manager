### Task 1: Dependências + guard de teste

**Files:**
- Modify: `requirements.txt`
- Create: `tests/test_contrato_pdf.py`

**Interfaces:**
- Produces: marcador de skip `_weasy_ausente` reutilizado pelos testes de PDF.

- [ ] **Step 1: Adicionar deps ao requirements.txt**

No topo (bloco de deps de runtime), acrescente após `SQLAlchemy`:

```
weasyprint
markdown
```

E no comentário do `apt` do servidor, acrescente `weasyprint python3-markdown` à linha de instalação.

- [ ] **Step 2: Instalar no dev**

Run: `python3 -m pip install --user weasyprint markdown`
Expected: instala sem erro (se falhar por libs de sistema, anote — os testes de PDF serão pulados; o restante roda).

- [ ] **Step 3: Criar o arquivo de teste com o guard**

```python
# tests/test_contrato_pdf.py
import importlib.util
import pytest

_weasy_ausente = importlib.util.find_spec("weasyprint") is None
skip_sem_weasy = pytest.mark.skipif(_weasy_ausente, reason="weasyprint não instalado")


def test_markdown_disponivel():
    import markdown  # noqa: F401
```

- [ ] **Step 4: Rodar**

Run: `python3 -m pytest tests/test_contrato_pdf.py -q`
Expected: PASS (1 passed) — se `markdown` não instalou, corrigir a instalação antes de seguir.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt tests/test_contrato_pdf.py
git commit -m "chore(contrato): deps weasyprint+markdown e guard de teste de PDF"
```

---

