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


def test_cronograma_projeto_view(app_db):
    from database import Projeto, CicloEtapa
    db = app_db.get_session()
    db.add(Projeto(nome_safe="Proj_C", data_entrega=datetime(2026, 3, 1)))
    db.add(CicloEtapa(projeto_nome="Proj_C", etapa_codigo="12",
                      data_prevista_conclusao=datetime(2026, 1, 20), concluido_em=datetime(2026, 1, 22)))
    db.commit()
    cfg = {"cronograma_padrao": [{"codigo": "12", "prazo_dias": 5},
                                 {"codigo": "13", "prazo_dias": 20},
                                 {"codigo": "16", "prazo_dias": 3}]}
    by = {x["codigo"]: x for x in mcr.cronograma_projeto_view(db, "Proj_C", cfg, codigo_entrega="16")}
    assert by["12"]["planejado"] is not None       # data_prevista_conclusao (do Cronograma Padrão)
    assert by["12"]["prazo_limite"] is not None     # regressivo (tem data_entrega)
    assert by["12"]["executado"] is not None        # concluido_em
    assert by["12"]["folga_dias"] is not None       # Limite − Planejada
    assert by["13"]["executado"] is None            # etapa sem CicloEtapa
    db.close()


def test_folga_medicao_entrega_cabe():
    cfg = {"cronograma_formato": 2, "cronograma_padrao": [
        {"codigo": "9", "prazo_dias": 3}, {"codigo": "10", "prazo_dias": 5},
        {"codigo": "11", "prazo_dias": 10}, {"codigo": "16", "prazo_dias": 5}]}
    med = datetime(2026, 8, 1); ent = datetime(2026, 9, 1)     # 31 dias corridos
    # etapas APÓS "10" até "16": 11(10) + 16(5) = 15 → folga = 31 − 15 = 16
    assert mcr.folga_medicao_entrega(cfg, med, ent) == 16


def test_folga_medicao_entrega_nao_cabe():
    cfg = {"cronograma_formato": 2, "cronograma_padrao": [
        {"codigo": "10", "prazo_dias": 5}, {"codigo": "11", "prazo_dias": 10},
        {"codigo": "16", "prazo_dias": 5}]}
    med = datetime(2026, 8, 1); ent = datetime(2026, 8, 10)    # 9 dias
    # após "10": 11(10)+16(5)=15 → folga = 9 − 15 = −6
    assert mcr.folga_medicao_entrega(cfg, med, ent) == -6


def test_folga_medicao_entrega_fallback_sem_10():
    # sem etapa "10" → âncora cai na "9"; após "9": 13(20)+16(5)=25
    cfg = {"cronograma_formato": 2, "cronograma_padrao": [
        {"codigo": "9", "prazo_dias": 4}, {"codigo": "13", "prazo_dias": 20},
        {"codigo": "16", "prazo_dias": 5}]}
    med = datetime(2026, 8, 1); ent = datetime(2026, 10, 1)    # 61 dias
    assert mcr.folga_medicao_entrega(cfg, med, ent) == 61 - 25


def test_folga_medicao_entrega_entrega_ausente_usa_ultima():
    # sem "16" → âncora de entrega cai na ÚLTIMA etapa; após "10": 11(10)+20(7)=17
    cfg = {"cronograma_formato": 2, "cronograma_padrao": [
        {"codigo": "10", "prazo_dias": 5}, {"codigo": "11", "prazo_dias": 10},
        {"codigo": "20", "prazo_dias": 7}]}
    from datetime import datetime as _dt
    assert mcr.folga_medicao_entrega(cfg, _dt(2026, 8, 1), _dt(2026, 9, 1)) == 31 - 17


def test_folga_medicao_entrega_sem_medicao_nem_9_usa_primeira():
    # sem "10" e sem "9" → âncora de medição cai na PRIMEIRA etapa (idx 0); após ela: 12(8)+16(4)=12
    cfg = {"cronograma_formato": 2, "cronograma_padrao": [
        {"codigo": "11", "prazo_dias": 3}, {"codigo": "12", "prazo_dias": 8},
        {"codigo": "16", "prazo_dias": 4}]}
    from datetime import datetime as _dt
    assert mcr.folga_medicao_entrega(cfg, _dt(2026, 8, 1), _dt(2026, 9, 1)) == 31 - 12
