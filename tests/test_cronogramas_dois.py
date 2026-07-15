"""Núcleo dos DOIS cronogramas derivados do mesmo Cronograma Padrão (mesmos prazos, âncoras opostas):
- Progressivo (cedo): ancora no INÍCIO → o quanto ANTES cada etapa pode terminar.
- Regressivo (limite): ancora na ENTREGA (etapa do cliente) → o Prazo LIMITE de cada etapa.
- Folga = Regressivo − Progressivo (negativa = não cabe → cronograma próprio + senha)."""
from datetime import datetime
import mod_cronograma as mcr


def test_cronogramas_progressivo_regressivo_folga():
    etapas = [("A", 10), ("B", 20), ("C", 5)]   # (codigo, prazo_dias), ordenado; C = etapa de entrega
    inicio = datetime(2026, 1, 1)
    entrega = datetime(2026, 3, 1)
    by = {x["codigo"]: x for x in mcr.cronogramas(etapas, inicio, entrega, "C")}
    # progressivo: acumula do início (A +10, B +30, C +35)
    assert by["A"]["progressivo"] == datetime(2026, 1, 11)
    assert by["B"]["progressivo"] == datetime(2026, 1, 31)
    assert by["C"]["progressivo"] == datetime(2026, 2, 5)
    # regressivo: recua da entrega (C = entrega; B = -5; A = -25)
    assert by["C"]["regressivo"] == datetime(2026, 3, 1)
    assert by["B"]["regressivo"] == datetime(2026, 2, 24)
    assert by["A"]["regressivo"] == datetime(2026, 2, 4)
    # folga = regressivo - progressivo (dias)
    assert by["C"]["folga_dias"] == 24    # 05/02 -> 01/03
    assert by["A"]["folga_dias"] == (datetime(2026, 2, 4) - datetime(2026, 1, 11)).days


def test_cronogramas_folga_negativa_quando_nao_cabe():
    # entrega apertada: menos que a soma dos prazos (10+20+5 = 35 dias) → folga negativa em alguma etapa
    etapas = [("A", 10), ("B", 20), ("C", 5)]
    inicio = datetime(2026, 1, 1)
    entrega = datetime(2026, 1, 20)   # só 19 dias, mas o padrão precisa de 35
    by = {x["codigo"]: x for x in mcr.cronogramas(etapas, inicio, entrega, "C")}
    assert any(by[c]["folga_dias"] < 0 for c in ("A", "B", "C"))   # não cabe


def test_cronogramas_etapa_depois_da_entrega_avanca():
    # etapa após a de entrega recua/avança a partir da entrega (montagem depois da entrega ao cliente)
    etapas = [("ENT", 5), ("MON", 3)]   # ENT = entrega; MON = montagem (depois)
    inicio = datetime(2026, 1, 1)
    entrega = datetime(2026, 2, 1)
    by = {x["codigo"]: x for x in mcr.cronogramas(etapas, inicio, entrega, "ENT")}
    assert by["ENT"]["regressivo"] == datetime(2026, 2, 1)
    assert by["MON"]["regressivo"] == datetime(2026, 2, 4)   # entrega + 3


def test_cronograma_do_projeto_e_viabilidade():
    cfg = {"cronograma_padrao": [
        {"codigo": "12", "prazo_dias": 5},
        {"codigo": "13", "prazo_dias": 20},
        {"codigo": "16", "prazo_dias": 3},   # entrega
    ]}
    inicio = datetime(2026, 1, 1)
    r = mcr.cronograma_do_projeto(cfg, inicio, datetime(2026, 3, 1), codigo_entrega="16")  # folgado
    assert len(r) == 3 and mcr.cabe_no_cronograma(r) is True
    r2 = mcr.cronograma_do_projeto(cfg, inicio, datetime(2026, 1, 10), codigo_entrega="16")  # apertado
    assert mcr.cabe_no_cronograma(r2) is False
