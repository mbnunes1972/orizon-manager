"""Fase A — prazo por fase validado contra o cronograma do projeto: `limite_etapa` (data prevista da
etapa) + `prazo_excede_limite` (base do step-up quando o desmembramento excede o limite) +
`garantir_cronograma` (todo projeto deve ter cronograma — cria do padrão se faltar)."""
from datetime import datetime
import mod_cronograma as mcr


def test_prazo_excede_limite():
    lim = datetime(2026, 12, 1)
    assert mcr.prazo_excede_limite(lim, datetime(2026, 12, 15)) is True    # depois do limite → excede
    assert mcr.prazo_excede_limite(lim, datetime(2026, 11, 20)) is False   # dentro
    assert mcr.prazo_excede_limite(lim, datetime(2026, 12, 1)) is False    # no limite exato → não excede
    assert mcr.prazo_excede_limite(None, datetime(2026, 12, 1)) is False   # sem limite → nada a exceder


def test_limite_etapa_le_do_cronograma(app_db):
    db = app_db.get_session()
    cfg = {"cronograma_padrao": [{"codigo": "12", "prazo_dias": 30}]}
    mcr.gerar_cronograma_projeto(db, "Proj_X", cfg, datetime(2026, 1, 1)); db.commit()
    assert mcr.limite_etapa(db, "Proj_X", "12") == datetime(2026, 1, 31)   # d0 + 30 dias
    assert mcr.limite_etapa(db, "Proj_X", "99") is None                    # etapa sem registro
    assert mcr.limite_etapa(db, "Outro", "12") is None                     # projeto sem cronograma
    db.close()


def test_garantir_cronograma_cria_se_faltar(app_db):
    db = app_db.get_session()
    cfg = {"cronograma_padrao": [{"codigo": "12", "prazo_dias": 10}]}
    assert mcr.tem_cronograma(db, "Proj_Y") is False
    assert mcr.garantir_cronograma(db, "Proj_Y", cfg, datetime(2026, 1, 1)) is True   # gerou agora
    db.commit()
    assert mcr.tem_cronograma(db, "Proj_Y") is True
    assert mcr.limite_etapa(db, "Proj_Y", "12") == datetime(2026, 1, 11)
    assert mcr.garantir_cronograma(db, "Proj_Y", cfg, datetime(2026, 1, 1)) is False  # já existe → não regenera
    db.close()
