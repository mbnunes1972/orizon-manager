import importlib.util
import pytest

_weasy_ausente = importlib.util.find_spec("weasyprint") is None
skip_sem_weasy = pytest.mark.skipif(_weasy_ausente, reason="weasyprint não instalado")


def test_markdown_disponivel():
    import markdown  # noqa: F401
