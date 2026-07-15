import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
import mod_documentos
import mod_contrato


@pytest.fixture
def db(tmp_path, monkeypatch):
    import database
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "t.db"))
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    eng = create_engine("sqlite:///" + str(tmp_path / "t.db"))
    database.Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


# _montar_html_contrato chama _html_capa(ctx), que espera um contexto COMPLETO.
# Monte-o com construir_contexto, como faz tests/test_contrato.py:303-309 — ctx
# montado na mão quebra na capa, não no que estamos testando.
CLIENTE = {"nome": "CLIENTE TESTE", "cpf": "000.000.000-00",
           "email": "t@t.com", "telefone": "(12) 90000-0000",
           "logradouro": "Rua X", "numero": "1", "bairro": "Centro",
           "cidade": "São José dos Campos", "estado": "SP", "cep": "12200-000",
           "inst_mesmo_residencial": True}
USUARIO = {"nome": "Consultor", "telefone": "", "email": ""}
LOJA = {"id": 1, "nome": "LOJA TESTE", "cnpj": "00.000.000/0001-00",
        "cidade": "São José dos Campos"}


def _ctx(**extra):
    ctx = mod_contrato.construir_contexto(CLIENTE, USUARIO, "", LOJA)
    ctx.update(extra)
    return ctx


class _ContratoFake:
    """Só o que versao_para_contrato lê — evita montar um Contrato completo."""
    def __init__(self, modelo_versao_id=None, gerado_em=None):
        self.modelo_versao_id = modelo_versao_id
        self.gerado_em = gerado_em


def test_contrato_tem_a_coluna_modelo_versao_id():
    from database import Contrato
    assert hasattr(Contrato, "modelo_versao_id")


def test_corpo_da_versao_devolve_o_corpo_congelado(db):
    m = mod_documentos.criar_versao(db, 1, "contrato", "# CLÁUSULA V1\n1.1. Original.\n",
                                    "c.docx", 1)
    mod_documentos.ativar(db, m.id)
    m2 = mod_documentos.criar_versao(db, 1, "contrato", "# CLÁUSULA V2\n1.1. Nova.\n",
                                     "c2.docx", 1)
    mod_documentos.ativar(db, m2.id)
    assert "Original" in mod_documentos.corpo_da_versao(db, m.id), \
        "a versão 1 é imutável — ativar a 2 não pode alterá-la"
    assert "Nova" in mod_documentos.corpo_da_versao(db, m2.id)


def test_regerar_contrato_antigo_reproduz_as_clausulas_originais(db):
    """A garantia jurídica da frente. Sem este verde, o versionamento é decorativo."""
    v1 = mod_documentos.criar_versao(db, 1, "contrato",
                                     "# CLÁUSULA PRIMEIRA\n1.1. Texto ORIGINAL assinado.\n",
                                     "c.docx", 1)
    mod_documentos.ativar(db, v1.id)

    ctx_assinado = _ctx(_db=db, _modelo_versao_id=v1.id)
    html_na_assinatura = mod_contrato._montar_html_contrato(ctx_assinado)
    assert "Texto ORIGINAL assinado." in html_na_assinatura

    # a loja troca o modelo depois da assinatura
    v2 = mod_documentos.criar_versao(db, 1, "contrato",
                                     "# CLÁUSULA PRIMEIRA\n1.1. Texto NOVO da loja.\n",
                                     "c2.docx", 1)
    mod_documentos.ativar(db, v2.id)

    html_regerado = mod_contrato._montar_html_contrato(ctx_assinado)
    assert "Texto ORIGINAL assinado." in html_regerado, \
        "regerar contrato assinado NÃO pode trazer a cláusula nova"
    assert "Texto NOVO da loja." not in html_regerado


def test_contrato_sem_db_cai_no_template_global(db):
    """Chamador que não passa _db segue idêntico a hoje."""
    html = mod_contrato._montar_html_contrato(_ctx())
    global_md = mod_contrato._carregar_md()
    if global_md.strip():
        primeira = [l for l in global_md.split("\n") if l.strip()][0]
        assert primeira[:20] in html


def test_contrato_com_db_mas_sem_modelo_cai_no_global(db):
    html = mod_contrato._montar_html_contrato(_ctx(_db=db))
    global_md = mod_contrato._carregar_md()
    if global_md.strip():
        primeira = [l for l in global_md.split("\n") if l.strip()][0]
        assert primeira[:20] in html


def test_contrato_novo_adota_e_fixa_o_modelo_ativo(db):
    m = mod_documentos.criar_versao(db, 1, "contrato", "# C\n1.1. Ok.\n", "c.docx", 1)
    mod_documentos.ativar(db, m.id)
    c = _ContratoFake(gerado_em=None)
    assert mod_documentos.versao_para_contrato(db, c, 1) == m.id
    assert c.modelo_versao_id == m.id, "tem que FIXAR, não só devolver"


def test_contrato_legado_nunca_adota_modelo_novo(db):
    """O contrato já foi gerado (e talvez assinado) antes de a loja ter modelo.
    Regerar NÃO pode trazer as cláusulas novas."""
    from datetime import datetime
    m = mod_documentos.criar_versao(db, 1, "contrato", "# NOVO\n1.1. Cláusula nova.\n",
                                    "c.docx", 1)
    mod_documentos.ativar(db, m.id)
    legado = _ContratoFake(gerado_em=datetime(2026, 1, 1))
    assert mod_documentos.versao_para_contrato(db, legado, 1) is None
    assert legado.modelo_versao_id is None


def test_contrato_ja_fixado_ignora_o_modelo_ativo(db):
    v1 = mod_documentos.criar_versao(db, 1, "contrato", "# V1\n1.1. Original.\n", "c.docx", 1)
    v2 = mod_documentos.criar_versao(db, 1, "contrato", "# V2\n1.1. Nova.\n", "c2.docx", 1)
    mod_documentos.ativar(db, v2.id)
    c = _ContratoFake(modelo_versao_id=v1.id, gerado_em=None)
    assert mod_documentos.versao_para_contrato(db, c, 1) == v1.id


def test_contrato_novo_sem_modelo_na_loja_fica_no_global(db):
    c = _ContratoFake(gerado_em=None)
    assert mod_documentos.versao_para_contrato(db, c, 1) is None


def test_legado_nao_vaza_pro_modelo_ativo_mesmo_se_a_loja_ganhar_um_depois(db):
    """Bug pego só por execução (E2E real, não pelos testes com _ContratoFake): quando
    o chamador passa _modelo_versao_id=None (resultado de versao_para_contrato() para
    um contrato legado), _resolver_corpo_contrato caía no 'ativo da loja' — se a loja
    ganhasse um modelo DEPOIS do contrato legado já gerado, a cláusula nova vazava pro
    documento antigo ao regerar. A chave tem que valer como resposta final quando
    presente, mesmo com valor None."""
    from datetime import datetime
    m = mod_documentos.criar_versao(db, 1, "contrato", "# NOVO\n1.1. Cláusula nova da loja.\n",
                                    "c.docx", 1)
    mod_documentos.ativar(db, m.id)
    legado = _ContratoFake(gerado_em=datetime(2026, 1, 1))
    versao_id = mod_documentos.versao_para_contrato(db, legado, 1)
    assert versao_id is None

    ctx = _ctx(_db=db, _modelo_versao_id=versao_id, loja={"id": 1})
    html = mod_contrato._montar_html_contrato(ctx)
    assert "Cláusula nova da loja" not in html, \
        "contrato legado não pode adotar o modelo ativo da loja ao regerar"
