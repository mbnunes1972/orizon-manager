"""FASE B1 — Segmentação na Loja (default 65/35) e o resolver a partir do objeto Loja."""
import mod_orcamento_params as mp
from database import Loja


def test_loja_nova_nasce_65_35(app_db):
    """Loja criada via ORM já nasce com 65/35 (default do modelo)."""
    db = app_db.get_session()
    lj = Loja(nome="Loja Seg Teste")
    db.add(lj); db.commit()
    lj2 = db.query(Loja).filter_by(nome="Loja Seg Teste").first()
    assert lj2.pct_mercadoria == 65.0
    assert lj2.pct_servico == 35.0
    db.close()


def test_resolver_a_partir_da_loja(app_db):
    db = app_db.get_session()
    lj = Loja(nome="Loja Seg 2", pct_mercadoria=80.0, pct_servico=20.0)
    db.add(lj); db.commit()
    seg = mp.resolver_segmentacao(lj.pct_mercadoria, lj.pct_servico)
    assert seg == {"pct_mercadoria": 80.0, "pct_servico": 20.0}
    db.close()
