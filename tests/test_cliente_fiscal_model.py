import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_cliente_campos_fiscais(app_db):
    s = app_db.get_session()
    c = app_db.Cliente(nome="ACME", tipo_dest="contribuinte", cnpj="11.222.333/0001-44",
                       inscricao_estadual="123456")
    s.add(c); s.commit()
    lido = s.query(app_db.Cliente).filter_by(nome="ACME").first()
    assert lido.tipo_dest == "contribuinte" and lido.cnpj == "11.222.333/0001-44" and lido.inscricao_estadual == "123456"
    s.close()

def test_cliente_default_nao_contribuinte(app_db):
    s = app_db.get_session()
    c = app_db.Cliente(nome="PF", cpf="1"); s.add(c); s.commit()
    assert s.query(app_db.Cliente).filter_by(nome="PF").first().tipo_dest == "nao_contribuinte"
    s.close()
