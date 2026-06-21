# tests/test_contrato_loja.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import sqlite3
import database


def _loja_completa():
    return {
        "nome": "INSPIRIUM MOVEIS LTDA", "cnpj": "19.152.134/0001-56", "codigo": "INS",
        "telefone": "(12) 3341-8777", "email": "sac@dalmobilesjc.com.br",
        "cep": "12200-000", "logradouro": "Rua A", "numero": "100",
        "complemento": "", "bairro": "Centro", "cidade": "SJC", "estado": "SP",
        "testemunha1_nome": "Jaime Perinazzo", "testemunha1_cpf": "123.456.789-00",
        "testemunha2_nome": "Felipe Guizalberte", "testemunha2_cpf": "987.654.321-00",
    }


def test_validar_loja_completa():
    from mod_contrato import validar_loja_para_contrato
    assert validar_loja_para_contrato(_loja_completa()) == []


def test_validar_loja_complemento_opcional():
    from mod_contrato import validar_loja_para_contrato
    loja = _loja_completa(); loja["complemento"] = ""
    assert validar_loja_para_contrato(loja) == []


def test_validar_loja_cpf_placeholder_conta_como_faltando():
    from mod_contrato import validar_loja_para_contrato
    loja = _loja_completa()
    loja["testemunha1_cpf"] = "xxx.xxx.xxx-xx"
    loja["testemunha2_cpf"] = "yyy.yyy.yyy-yy"
    faltando = validar_loja_para_contrato(loja)
    j = " ".join(faltando).lower()
    assert "testemunha 1" in j and "testemunha 2" in j


def test_validar_loja_telefone_email_endereco_obrigatorios():
    from mod_contrato import validar_loja_para_contrato
    loja = _loja_completa()
    for c in ("telefone", "email", "cep", "logradouro", "numero", "bairro", "cidade", "estado"):
        loja[c] = ""
    faltando = " ".join(validar_loja_para_contrato(loja)).lower()
    for termo in ("telefone", "e-mail", "cep", "logradouro", "número", "bairro", "cidade", "estado"):
        assert termo in faltando


def test_validar_loja_vazia_acusa_tudo():
    from mod_contrato import validar_loja_para_contrato
    assert len(validar_loja_para_contrato({})) >= 13


_TABELAS_LEGADO = ["clientes", "usuarios", "projetos_meta", "contratos",
                   "orcamentos", "orcamento_ambientes", "briefings", "parceiros"]


def _db_legado(path):
    conn = sqlite3.connect(path)
    for t in _TABELAS_LEGADO:
        conn.execute(f"CREATE TABLE {t} (id INTEGER PRIMARY KEY)")
    conn.commit(); conn.close()


def test_migracao_cria_loja_snapshot_json(tmp_path, monkeypatch):
    db = str(tmp_path / "legado.db")
    _db_legado(db)
    monkeypatch.setattr(database, "DB_PATH", db)
    database._migrar_colunas()
    conn = sqlite3.connect(db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(contratos)")}
    conn.close()
    assert "loja_snapshot_json" in cols


def test_migracao_loja_snapshot_idempotente(tmp_path, monkeypatch):
    db = str(tmp_path / "legado.db")
    _db_legado(db)
    monkeypatch.setattr(database, "DB_PATH", db)
    database._migrar_colunas()
    database._migrar_colunas()   # 2ª vez não quebra
    conn = sqlite3.connect(db)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(contratos)")]
    conn.close()
    assert cols.count("loja_snapshot_json") == 1


def test_loja_dict_para_contrato_mapeia_campos():
    import main

    class _FakeLoja:
        id = 1; nome = "INSPIRIUM"; cnpj = "19.152.134/0001-56"; codigo = "INS"
        telefone = "(12) 3341-8777"; email = "sac@x.com"; cep = "12200-000"
        logradouro = "Rua A"; numero = "100"; complemento = ""; bairro = "Centro"
        cidade = "SJC"; estado = "SP"
        testemunha1_nome = "Jaime"; testemunha1_cpf = "123.456.789-00"
        testemunha2_nome = "Felipe"; testemunha2_cpf = "987.654.321-00"

    class _FakeDB:
        def get(self, model, pk):
            return _FakeLoja() if pk == 1 else None

    d = main._loja_dict_para_contrato(_FakeDB(), 1)
    assert d["codigo"] == "INS"
    assert d["nome"] == "INSPIRIUM"
    assert d["testemunha1_cpf"] == "123.456.789-00"
    assert d["cidade"] == "SJC"


def test_loja_dict_para_contrato_sem_loja():
    import main
    class _FakeDB:
        def get(self, model, pk): return None
    assert main._loja_dict_para_contrato(_FakeDB(), None) == {}
    assert main._loja_dict_para_contrato(_FakeDB(), 999) == {}
