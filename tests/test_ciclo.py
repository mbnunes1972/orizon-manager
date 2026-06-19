import mod_ciclo as mc


def test_etapa_anterior():
    assert mc.etapa_anterior("4") == "3"
    assert mc.etapa_anterior("2") == "1"
    assert mc.etapa_anterior("1") is None
    assert mc.etapa_anterior("11a") is None


def test_ordenar_codigos_numerico_com_subetapas():
    entrada = ["10", "2", "11a", "11", "3", "1", "17a", "17"]
    assert mc.ordenar_codigos(entrada) == ["1", "2", "3", "10", "11", "11a", "17", "17a"]


def test_pode_avancar_principal_exige_anterior_concluida():
    assert mc.pode_avancar("4", {"3": "concluido"}) is True
    assert mc.pode_avancar("4", {"3": "pendente"}) is False
    assert mc.pode_avancar("4", {}) is False


def test_pode_avancar_aceita_status_conclusivos_alternativos():
    # Etapas da cauda concluem com status alternativos (ex.: 'entregue', 'implantado').
    assert mc.pode_avancar("13", {"12": "implantado"}) is True
    assert mc.pode_avancar("8", {"7": "assinado"}) is True
    assert mc.pode_avancar("4", {"3": "em_andamento"}) is False


def test_pode_avancar_primeira_etapa_sempre_liberada():
    assert mc.pode_avancar("1", {}) is True


def test_etapa_pai():
    assert mc.etapa_pai("11a") == "11"
    assert mc.etapa_pai("11e") == "11"
    assert mc.etapa_pai("17a") == "17"
    assert mc.etapa_pai("11") is None      # principal não tem "pai"
    assert mc.etapa_pai("1") is None


def test_pode_avancar_subetapa_herda_gating_da_mae():
    # Sub-etapa do PE (11x) segue o gating da etapa-mãe 11 (que exige a 10 concluída).
    assert mc.pode_avancar("11a", {"10": "pendente"}) is False
    assert mc.pode_avancar("11a", {}) is False
    assert mc.pode_avancar("11a", {"10": "concluido"}) is True
    # Mesma resposta que a etapa-mãe:
    for st in ({}, {"10": "pendente"}, {"10": "concluido"}, {"10": "entregue"}):
        assert mc.pode_avancar("11a", st) == mc.pode_avancar("11", st)
    # Sub-etapa da Montagem (17a) segue a 17 (que exige a 16 concluída).
    assert mc.pode_avancar("17a", {"16": "pendente"}) is False
    assert mc.pode_avancar("17a", {"16": "entregue"}) is True


def test_codigos_a_resetar_inclui_alvo_e_posteriores_e_subs():
    existentes = ["1", "2", "3", "4", "5", "11", "11a", "11b"]
    resetar = mc.codigos_a_resetar("3", existentes)
    assert set(resetar) == {"3", "4", "5", "11", "11a", "11b"}
    assert "1" not in resetar and "2" not in resetar


def test_reabertura_bloqueada_por_contrato():
    assert mc.reabertura_bloqueada_por_contrato(["3", "7"], "assinado") is True
    assert mc.reabertura_bloqueada_por_contrato(["3", "7"], "vigente") is True
    assert mc.reabertura_bloqueada_por_contrato(["3", "7"], "rascunho") is False
    assert mc.reabertura_bloqueada_por_contrato(["8", "9"], "assinado") is False


def test_chave_ordenacao():
    assert mc.chave_ordenacao("11a") == (11, "a")
    assert mc.chave_ordenacao("2") == (2, "")


def test_etapa_nome_em_sincronia_com_principais():
    # Toda etapa principal tem nome e vice-versa.
    assert set(mc.ETAPA_NOME) == set(mc.ETAPAS_PRINCIPAIS)


import sqlite3
import database


def _mk_ciclo_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE ciclo_etapas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        projeto_nome TEXT, etapa_codigo TEXT, status TEXT)""")
    conn.executemany(
        "INSERT INTO ciclo_etapas(projeto_nome, etapa_codigo, status) VALUES(?,?,?)",
        [("P", "1", "concluido"), ("P", "2", "concluido"), ("P", "3", "concluido"),
         ("P", "4", "pendente")],
    )
    conn.commit()
    return conn


def _codigos(conn):
    cur = conn.execute("SELECT etapa_codigo FROM ciclo_etapas ORDER BY etapa_codigo")
    return [r[0] for r in cur.fetchall()]


def test_swap_2_3_troca_os_codigos():
    conn = _mk_ciclo_db()
    database._run_migracoes(conn)
    assert _codigos(conn) == ["1", "2", "3", "4"]
    cur = conn.execute("SELECT id FROM schema_migrations WHERE id='etapas_swap_2_3'")
    assert cur.fetchone() is not None


def test_swap_2_3_idempotente():
    conn = _mk_ciclo_db()
    database._run_migracoes(conn)
    database._run_migracoes(conn)
    assert _codigos(conn) == ["1", "2", "3", "4"]
    cur = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE id='etapas_swap_2_3'")
    assert cur.fetchone()[0] == 1


def test_swap_2_3_inverte_conteudo():
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE ciclo_etapas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        projeto_nome TEXT, etapa_codigo TEXT, status TEXT)""")
    conn.executemany(
        "INSERT INTO ciclo_etapas(projeto_nome, etapa_codigo, status) VALUES(?,?,?)",
        [("P", "2", "era_briefing"), ("P", "3", "era_criacao")],
    )
    conn.commit()
    database._run_migracoes(conn)
    cur = conn.execute("SELECT etapa_codigo, status FROM ciclo_etapas ORDER BY etapa_codigo")
    pares = dict(cur.fetchall())
    assert pares["2"] == "era_criacao"
    assert pares["3"] == "era_briefing"


def test_exige_aprovacao_financeira():
    assert mc.exige_aprovacao_financeira("8") is True
    assert mc.exige_aprovacao_financeira("11d") is True
    assert mc.exige_aprovacao_financeira("7") is False
    assert mc.exige_aprovacao_financeira("11") is False
    assert mc.exige_aprovacao_financeira("9") is False


def test_etapa10_renomeada_medicao():
    assert mc.ETAPA_NOME["10"] == "Medição"
