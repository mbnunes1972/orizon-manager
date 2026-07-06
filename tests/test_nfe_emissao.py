import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
import nfe_emissao
from emissor_fiscal import resultado_de_focus, StatusNota


class FakeClient:
    def __init__(self): self.baixados = []
    def aguardar_processamento(self, ref, timeout=60, intervalo=3):
        return {"ref": ref, "status": "autorizado", "chave_nfe": "CH123", "numero": "10", "serie": "1",
                "caminho_xml_nota_fiscal": "/nfe/xml.xml", "caminho_danfe": "/nfe/danfe.pdf"}
    def baixar(self, caminho):
        self.baixados.append(caminho)
        return b"BYTES:" + caminho.encode()


class FakeEmissor:
    def __init__(self, status="processando_autorizacao", erros=None):
        self.client = FakeClient(); self._status = status; self._erros = erros; self.emit_calls = 0
    def emitir_nfe_produto(self, nota):
        self.emit_calls += 1
        d = {"ref": nota["ref"], "status": self._status}
        if self._erros: d["erros"] = self._erros
        return resultado_de_focus(d)
    def consultar_status(self, ref):
        return resultado_de_focus({"ref": ref, "status": "autorizado", "chave_nfe": "CH",
                                   "caminho_xml_nota_fiscal": "/x.xml", "caminho_danfe": "/d.pdf"})
    def cancelar(self, ref, justificativa):
        return resultado_de_focus({"ref": ref, "status": "cancelado", "caminho_xml_cancelamento": "/c.xml"})


def _nota(ref):
    return {"ref": ref, "natureza_operacao": "Venda", "data_emissao": "D",
            "emitente": {"doc_tipo": "cnpj", "doc": "1", "nome": "L", "regime": 1, "ie": "1",
                         "logradouro": "a", "numero": "1", "bairro": "b", "municipio": "c", "uf": "SP", "cep": "1"},
            "destinatario": {"nome": "C", "doc_tipo": "cpf", "doc": "2", "logradouro": "a", "numero": "1",
                             "bairro": "b", "municipio": "c", "uf": "SP", "cep": "1"},
            "fiscal": {"csosn": "101", "cfop_dentro": "5102", "cfop_fora": "6102", "pis_cst": "49", "cofins_cst": "49"},
            "itens": [{"cProd": "X", "xProd": "P", "ncm": "9403", "uCom": "UN", "qCom": 1.0, "preco_venda_unit": 10.0}]}


def _reset(app_db, ref, proj):
    db = app_db.get_session()
    db.query(app_db.NfeEmissao).filter_by(ref=ref).delete()
    db.query(app_db.CicloDocumento).filter_by(projeto_nome=proj, etapa_codigo="15").delete()
    db.commit(); db.close()


def _perfil(app_db, loja_id, ambiente="homologacao"):
    db = app_db.get_session()
    db.query(app_db.PerfilFiscal).filter_by(loja_id=loja_id).delete()
    db.add(app_db.PerfilFiscal(loja_id=loja_id, ambiente_ativo=ambiente, csosn_padrao="101",
                               cfop_dentro_uf="5102", cfop_fora_uf="6102"))
    db.commit(); db.close()


def test_emitir_autoriza_guarda_docs(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-1", proj); _perfil(app_db, lid, "homologacao")
    fake = FakeEmissor()
    db = app_db.get_session()
    res = nfe_emissao.emitir(db, lid, proj, _nota("R-1"), emissor=fake)
    assert res.status == StatusNota.AUTORIZADO and res.chave == "CH123"
    reg = db.query(app_db.NfeEmissao).filter_by(ref="R-1").first()
    assert reg.status == "autorizado" and reg.xml_doc_id and reg.danfe_doc_id
    docs = db.query(app_db.CicloDocumento).filter_by(projeto_nome=proj, etapa_codigo="15").all()
    assert {d.tipo for d in docs} == {"nfe_loja_xml", "nfe_loja_danfe"}
    assert fake.client.baixados == ["/nfe/xml.xml", "/nfe/danfe.pdf"]
    db.close()


def test_emitir_idempotente(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-2", proj); _perfil(app_db, lid, "homologacao")
    fake = FakeEmissor()
    db = app_db.get_session()
    nfe_emissao.emitir(db, lid, proj, _nota("R-2"), emissor=fake)
    nfe_emissao.emitir(db, lid, proj, _nota("R-2"), emissor=fake)
    assert fake.emit_calls == 1
    db.close()


def test_emitir_guarda_producao(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-3", proj); _perfil(app_db, lid, "producao")
    db = app_db.get_session()
    with pytest.raises(ValueError):
        nfe_emissao.emitir(db, lid, proj, _nota("R-3"), emissor=FakeEmissor())
    res = nfe_emissao.emitir(db, lid, proj, _nota("R-3"), permitir_producao=True, emissor=FakeEmissor())
    assert res.status == StatusNota.AUTORIZADO
    db.close()


def test_emitir_erro_autorizacao(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-4", proj); _perfil(app_db, lid, "homologacao")
    fake = FakeEmissor(status="erro_autorizacao", erros=[{"codigo": "215", "mensagem": "falha"}])
    db = app_db.get_session()
    res = nfe_emissao.emitir(db, lid, proj, _nota("R-4"), emissor=fake)
    assert res.status == StatusNota.ERRO
    reg = db.query(app_db.NfeEmissao).filter_by(ref="R-4").first()
    assert reg.status == "erro" and reg.erros_json and not reg.xml_doc_id
    db.close()
