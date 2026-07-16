"""FASE B2.3 — reescalonamento dos itens da NF-e para a parcela Mercadoria (pura, sem I/O).
Σ round(qCom·preco_venda_unit, 2) == total_alvo EXATO (mesma soma que a nota fiscal usa)."""
from fiscal import mod_nfe


def _total(itens):
    return round(sum(round((it.get("qCom") or 0) * (it.get("preco_venda_unit") or 0), 2) for it in itens), 2)


def test_rescalar_fecha_no_alvo_exato():
    itens = [
        {"cProd": "A", "qCom": 2, "preco_venda_unit": 100.0},   # 200
        {"cProd": "B", "qCom": 1, "preco_venda_unit": 50.0},    # 50
        {"cProd": "C", "qCom": 3, "preco_venda_unit": 10.0},    # 30
    ]   # total atual 280
    out = mod_nfe.rescalar_itens_para_total(itens, 140.0)
    assert _total(out) == 140.0


def test_rescalar_residuo_absorvido_no_ultimo():
    itens = [{"cProd": "A", "qCom": 3, "preco_venda_unit": 1.0}]   # total 3 → alvo 10 gera dízima
    out = mod_nfe.rescalar_itens_para_total(itens, 10.0)
    assert _total(out) == 10.0


def test_rescalar_alvo_com_centavo_quebrado():
    itens = [
        {"cProd": "A", "qCom": 7, "preco_venda_unit": 13.33},
        {"cProd": "B", "qCom": 2, "preco_venda_unit": 9.99},
    ]
    out = mod_nfe.rescalar_itens_para_total(itens, 65000.01)
    assert _total(out) == 65000.01


def test_rescalar_total_zero_ou_vazio_nao_quebra():
    assert mod_nfe.rescalar_itens_para_total([], 100.0) == []
    itens = [{"cProd": "A", "qCom": 1, "preco_venda_unit": 0.0}]   # total atual 0 → inalterado
    out = mod_nfe.rescalar_itens_para_total(itens, 100.0)
    assert out[0]["preco_venda_unit"] == 0.0


def test_rescalar_nao_muta_original():
    itens = [{"cProd": "A", "qCom": 2, "preco_venda_unit": 100.0}]
    mod_nfe.rescalar_itens_para_total(itens, 50.0)
    assert itens[0]["preco_venda_unit"] == 100.0   # original intacto


def test_rescalar_idempotente_no_total():
    itens = [{"cProd": "A", "qCom": 2, "preco_venda_unit": 100.0},
             {"cProd": "B", "qCom": 1, "preco_venda_unit": 50.0}]
    o1 = mod_nfe.rescalar_itens_para_total(itens, 125.0)
    o2 = mod_nfe.rescalar_itens_para_total(o1, 125.0)
    assert _total(o2) == 125.0
