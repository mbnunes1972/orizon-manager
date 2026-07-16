import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
from integracoes import emissor_fiscal as ef


def test_statusnota_valores():
    assert ef.StatusNota.AUTORIZADO.value == "autorizado"
    assert set(ef.StatusNota) >= {
        ef.StatusNota.PROCESSANDO, ef.StatusNota.AUTORIZADO,
        ef.StatusNota.ERRO, ef.StatusNota.CANCELADO, ef.StatusNota.DESCONHECIDO}


def test_resultado_de_focus_autorizado():
    dados = {"ref": "R1", "status": "autorizado", "chave_nfe": "CH", "numero": "10",
             "serie": "1", "status_sefaz": "100", "mensagem_sefaz": "Autorizado",
             "caminho_xml_nota_fiscal": "/x.xml", "caminho_danfe": "/d.pdf"}
    r = ef.resultado_de_focus(dados)
    assert r.ref == "R1" and r.status == ef.StatusNota.AUTORIZADO
    assert r.chave == "CH" and r.numero == "10" and r.serie == "1"
    assert r.xml_url == "/x.xml" and r.danfe_url == "/d.pdf"
    assert r.raw == dados


def test_resultado_de_focus_processando_erro_cancelado():
    assert ef.resultado_de_focus({"status": "processando_autorizacao"}).status == ef.StatusNota.PROCESSANDO
    r_erro = ef.resultado_de_focus({"status": "erro_autorizacao", "erros": [{"codigo": "1", "mensagem": "x"}]})
    assert r_erro.status == ef.StatusNota.ERRO and r_erro.erros == [{"codigo": "1", "mensagem": "x"}]
    r_can = ef.resultado_de_focus({"status": "cancelado", "caminho_xml_cancelamento": "/c.xml"})
    assert r_can.status == ef.StatusNota.CANCELADO and r_can.xml_cancelamento_url == "/c.xml"


def test_resultado_de_focus_desconhecido():
    assert ef.resultado_de_focus({}).status == ef.StatusNota.DESCONHECIDO
    assert ef.resultado_de_focus({"status": "algo_novo"}).status == ef.StatusNota.DESCONHECIDO


def test_emissor_fiscal_abc_nao_instancia():
    with pytest.raises(TypeError):
        ef.EmissorFiscal()


def test_nfse_stub_levanta_notimplemented():
    class E(ef.EmissorFiscal):
        def emitir_nfe_produto(self, nota): return None
        def consultar_status(self, ref): return None
        def cancelar(self, ref, justificativa): return None
    with pytest.raises(NotImplementedError):
        E().emitir_nfse_servico({})
