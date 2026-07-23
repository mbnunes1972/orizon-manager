import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest

def test_emitente_persiste_campos_fiscais(app_db):
    s = app_db.get_session()
    e = app_db.Emitente(cnpj="19152134000156", razao_social="LOJA X", regime_tributario="simples",
                        csosn_padrao="101", cfop_dentro_uf="5102", cfop_fora_uf="6102", uf="SP",
                        cidade="SAO PAULO", ambiente_ativo="homologacao", papel_cnpj="loja_produto_servico")
    s.add(e); s.commit(); eid = e.id
    lido = s.query(app_db.Emitente).get(eid)
    assert lido.cnpj == "19152134000156" and lido.uf == "SP" and lido.ambiente_ativo == "homologacao"
    s.close()


def test_loja_e_rede_referenciam_emitente(app_db):
    s = app_db.get_session()
    e = app_db.Emitente(cnpj="1"); s.add(e); s.flush()
    r = app_db.Rede(nome="R", emitente_central_id=e.id); s.add(r); s.flush()
    l = app_db.Loja(nome="L", rede_id=r.id, emitente_id=e.id); s.add(l); s.commit()
    assert s.query(app_db.Loja).filter_by(nome="L").first().emitente_id == e.id
    assert s.query(app_db.Rede).filter_by(nome="R").first().emitente_central_id == e.id
    s.close()


