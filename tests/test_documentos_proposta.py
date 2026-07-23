import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
import mod_contrato
import mod_documentos


@pytest.fixture
def db(db_pg_schema):
    """Sessão num schema recém-criado do Postgres de teste (sem seeds). As linhas
    mínimas que os testes referenciam por FK (lojas 1/2, usuário 1) são criadas aqui —
    no SQLite as FKs fabricadas passavam; no Postgres elas são reais."""
    s = db_pg_schema.Session()
    s.add_all([db_pg_schema.Loja(id=1, nome="L1"),
               db_pg_schema.Loja(id=2, nome="L2"),
               db_pg_schema.Usuario(id=1, nome="U", login="u1", senha_hash="x", nivel="master")])
    s.commit()
    yield s
    s.close()


# montar_html_proposta chama _html_capa(ctx) — use construir_contexto, como
# tests/test_contrato.py. ctx montado na mão quebra na capa.
CLIENTE = {"nome": "CLIENTE TESTE", "cpf": "000.000.000-00",
           "email": "t@t.com", "telefone": "(12) 90000-0000",
           "logradouro": "Rua X", "numero": "1", "bairro": "Centro",
           "cidade": "São José dos Campos", "estado": "SP", "cep": "12200-000",
           "inst_mesmo_residencial": True}
USUARIO = {"nome": "Consultor", "telefone": "", "email": ""}
LOJA = {"id": 1, "nome": "LOJA TESTE", "cnpj": "00.000.000/0001-00"}


def _ctx(**extra):
    ctx = mod_contrato.construir_contexto(CLIENTE, USUARIO, "", LOJA)
    ctx["num_contrato"] = "PV000000001"
    ctx.update(extra)
    return ctx


def test_proposta_sem_db_e_capa_so_como_hoje():
    """Regressão zero: chamador que não passa _db não muda de comportamento."""
    html = mod_contrato.montar_html_proposta(_ctx())
    assert "<!--CORPO-->" not in html
    assert "CLÁUSULA" not in html


def test_proposta_sem_modelo_e_capa_so(db):
    html = mod_contrato.montar_html_proposta(_ctx(_db=db))
    assert "CLÁUSULA" not in html


def test_proposta_com_modelo_ativo_ganha_o_corpo(db):
    m = mod_documentos.criar_versao(db, 1, "proposta",
                                    "# CLÁUSULA ÚNICA\n1.1. Proposta válida por 10 dias.\n",
                                    "p.docx", 1)
    mod_documentos.ativar(db, m.id)
    html = mod_contrato.montar_html_proposta(_ctx(_db=db))
    assert "CLÁUSULA ÚNICA" in html
    assert "Proposta válida por 10 dias." in html


def test_modelo_de_contrato_nao_vaza_para_a_proposta(db):
    m = mod_documentos.criar_versao(db, 1, "contrato",
                                    "# CLÁUSULA DO CONTRATO\n1.1. Não é da proposta.\n",
                                    "c.docx", 1)
    mod_documentos.ativar(db, m.id)
    html = mod_contrato.montar_html_proposta(_ctx(_db=db))
    assert "CLÁUSULA DO CONTRATO" not in html
