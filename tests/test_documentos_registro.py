import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
import mod_documentos


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Banco isolado por teste."""
    import database
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "t.db"))
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    eng = create_engine("sqlite:///" + str(tmp_path / "t.db"))
    database.Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng)
    s = S()
    yield s
    s.close()


def test_criar_versao_comeca_em_1(db):
    m = mod_documentos.criar_versao(db, loja_id=1, tipo="contrato",
                                    corpo_md="# CLÁUSULA\n1.1. Ok.\n",
                                    origem_nome="c.docx", usuario_id=1)
    assert m.versao == 1


def test_versoes_sao_sequenciais_por_loja_e_tipo(db):
    mod_documentos.criar_versao(db, 1, "contrato", "a", "c.docx", 1)
    m2 = mod_documentos.criar_versao(db, 1, "contrato", "b", "c.docx", 1)
    outra_loja = mod_documentos.criar_versao(db, 2, "contrato", "c", "c.docx", 1)
    outro_tipo = mod_documentos.criar_versao(db, 1, "proposta", "d", "p.docx", 1)
    assert m2.versao == 2
    assert outra_loja.versao == 1, "loja 2 tem sequência própria"
    assert outro_tipo.versao == 1, "proposta tem sequência própria"


def test_ativar_desliga_a_anterior(db):
    m1 = mod_documentos.criar_versao(db, 1, "contrato", "a", "c.docx", 1)
    m2 = mod_documentos.criar_versao(db, 1, "contrato", "b", "c.docx", 1)
    mod_documentos.ativar(db, m1.id)
    mod_documentos.ativar(db, m2.id)
    db.refresh(m1)
    assert m1.ativo == 0
    assert m2.ativo == 1


def test_ativar_nao_mexe_em_outro_tipo(db):
    c = mod_documentos.criar_versao(db, 1, "contrato", "a", "c.docx", 1)
    p = mod_documentos.criar_versao(db, 1, "proposta", "b", "p.docx", 1)
    mod_documentos.ativar(db, c.id)
    mod_documentos.ativar(db, p.id)
    db.refresh(c)
    assert c.ativo == 1, "ativar proposta não pode desligar o contrato"


def test_resolver_modelo_devolve_a_versao_ativa(db):
    m = mod_documentos.criar_versao(db, 1, "contrato", "CORPO DA LOJA", "c.docx", 1)
    mod_documentos.ativar(db, m.id)
    assert mod_documentos.resolver_modelo(db, 1, "contrato") == "CORPO DA LOJA"


def test_resolver_modelo_cai_no_global_quando_a_loja_nao_tem(db):
    """Loja sem modelo próprio continua igual a hoje — migração zero."""
    import mod_contrato
    assert mod_documentos.resolver_modelo(db, 99, "contrato") == mod_contrato._carregar_md()


def test_resolver_modelo_de_proposta_sem_modelo_e_vazio(db):
    """Proposta é capa-só hoje: sem modelo, corpo vazio."""
    assert mod_documentos.resolver_modelo(db, 99, "proposta") == ""


def test_resolver_modelo_ignora_versao_inativa(db):
    mod_documentos.criar_versao(db, 1, "contrato", "RASCUNHO", "c.docx", 1)
    import mod_contrato
    assert mod_documentos.resolver_modelo(db, 1, "contrato") == mod_contrato._carregar_md()


def test_listar_e_escopado_por_loja(db):
    mod_documentos.criar_versao(db, 1, "contrato", "a", "c.docx", 1)
    mod_documentos.criar_versao(db, 2, "contrato", "b", "c.docx", 1)
    assert len(mod_documentos.listar(db, 1)) == 1, "loja A não pode ver modelo da loja B"


def test_tipo_invalido_e_recusado(db):
    with pytest.raises(ValueError):
        mod_documentos.criar_versao(db, 1, "custom", "a", "x.docx", 1)


def test_corpo_vazio_e_recusado(db):
    with pytest.raises(ValueError):
        mod_documentos.criar_versao(db, 1, "contrato", "   ", "c.docx", 1)


def test_original_do_staging_e_promovido_para_a_versao(db, tmp_path, monkeypatch):
    """Auditoria: o arquivo subido tem que sobreviver ao lado da versão."""
    monkeypatch.setattr(mod_documentos, "DOCS_LOJA_DIR", str(tmp_path / "docs"))
    caminho, sha = mod_documentos.guardar_staging(1, "contrato", "meu.docx", b"conteudo-x")
    assert os.path.exists(caminho)
    m = mod_documentos.criar_versao(db, 1, "contrato", "# C\n1.1. Ok.\n", "meu.docx", 1,
                                    staging_path=caminho, origem_sha256=sha)
    assert m.origem_sha256 == sha
    assert m.origem_path and os.path.exists(m.origem_path)
    assert "v1" in m.origem_path
    assert not os.path.exists(caminho), "o staging foi movido, não copiado"
    assert open(m.origem_path, "rb").read() == b"conteudo-x"


def test_criar_versao_sem_staging_nao_explode(db):
    m = mod_documentos.criar_versao(db, 1, "contrato", "# C\n1.1. Ok.\n", "c.docx", 1)
    assert m.origem_path is None
