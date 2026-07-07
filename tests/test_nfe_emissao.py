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
        self.nota_recebida = None
    def emitir_nfe_produto(self, nota):
        self.nota_recebida = nota
        self.emit_calls += 1
        d = {"ref": nota["ref"], "status": self._status}
        if self._erros: d["erros"] = self._erros
        return resultado_de_focus(d)
    def consultar_status(self, ref):
        return resultado_de_focus({"ref": ref, "status": "autorizado", "chave_nfe": "CH",
                                   "caminho_xml_nota_fiscal": "/x.xml", "caminho_danfe": "/d.pdf"})
    def cancelar(self, ref, justificativa):
        return resultado_de_focus({"ref": ref, "status": "cancelado", "caminho_xml_cancelamento": "/c.xml"})


class FakeClientNfse:
    def __init__(self): self.baixados = []
    def aguardar_processamento_nfse(self, ref, timeout=60, intervalo=3):
        return {"ref": ref, "status": "autorizado", "chave_nfe": "CHS1", "numero": "5", "serie": "1",
                "caminho_xml_nota_fiscal": "/nfse/xml.xml", "url": "/nfse/nota.pdf"}
    def baixar(self, caminho):
        self.baixados.append(caminho)
        return b"BYTES:" + caminho.encode()


class FakeEmissorNfse:
    """Emissor de NFS-e: espelha o de produto mas usa emitir_nfse_servico/consultar_status_nfse/cancelar_nfse."""
    def __init__(self, status="processando_autorizacao"):
        self.client = FakeClientNfse(); self._status = status; self.emit_calls = 0
        self.nota_recebida = None
    def emitir_nfse_servico(self, nota):
        self.nota_recebida = nota
        self.emit_calls += 1
        return resultado_de_focus({"ref": nota["ref"], "status": self._status})
    def consultar_status_nfse(self, ref):
        return resultado_de_focus({"ref": ref, "status": "autorizado", "chave_nfe": "CHS",
                                   "caminho_xml_nota_fiscal": "/x.xml", "url": "/nota.pdf"})
    def cancelar_nfse(self, ref, justificativa):
        return resultado_de_focus({"ref": ref, "status": "cancelado", "caminho_xml_cancelamento": "/c.xml"})


def _nota_nfse(ref):
    return {"ref": ref, "data_emissao": "D",
            "prestador": {"cnpj": "1", "inscricao_municipal": "IM", "codigo_municipio": "3549904",
                          "razao_social": "L"},
            "tomador": {"doc_tipo": "cpf", "doc": "2", "razao_social": "C", "logradouro": "a",
                        "numero": "1", "bairro": "b", "municipio": "c", "uf": "SP", "cep": "1"},
            "servico": {"valor_servicos": 100.0, "aliquota": 2.0, "discriminacao": "Montagem",
                        "iss_retido": False, "item_lista_servico": "14.06",
                        "codigo_tributario_municipio": "3101"}}


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
    db.query(app_db.DocumentoFiscal).filter_by(ref=ref).delete()
    db.query(app_db.CicloDocumento).filter_by(projeto_nome=proj, etapa_codigo="15").delete()
    db.commit(); db.close()


def _perfil(app_db, loja_id, ambiente="homologacao"):
    """Garante o Emitente da loja (o do seed) com o ambiente pedido; devolve seu id.
    A emissão agora lê o Emitente (não o PerfilFiscal)."""
    db = app_db.get_session()
    loja = db.get(app_db.Loja, loja_id)
    em = db.get(app_db.Emitente, loja.emitente_id)
    em.ambiente_ativo = ambiente
    db.commit()
    eid = em.id
    db.close()
    return eid


def test_emitir_autoriza_guarda_docs(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-1", proj); eid = _perfil(app_db, lid, "homologacao")
    fake = FakeEmissor()
    db = app_db.get_session()
    res = nfe_emissao.emitir(db, lid, proj, _nota("R-1"), emitente_id=eid, emissor=fake)
    assert res.status == StatusNota.AUTORIZADO and res.chave == "CH123"
    reg = db.query(app_db.DocumentoFiscal).filter_by(ref="R-1").first()
    assert reg.status == "autorizado" and reg.xml_doc_id and reg.danfe_doc_id
    docs = db.query(app_db.CicloDocumento).filter_by(projeto_nome=proj, etapa_codigo="15").all()
    assert {d.tipo for d in docs} == {"nfe_loja_xml", "nfe_loja_danfe"}
    assert fake.client.baixados == ["/nfe/xml.xml", "/nfe/danfe.pdf"]
    db.close()


def test_emitir_idempotente(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-2", proj); eid = _perfil(app_db, lid, "homologacao")
    fake = FakeEmissor()
    db = app_db.get_session()
    nfe_emissao.emitir(db, lid, proj, _nota("R-2"), emitente_id=eid, emissor=fake)
    nfe_emissao.emitir(db, lid, proj, _nota("R-2"), emitente_id=eid, emissor=fake)
    assert fake.emit_calls == 1
    db.close()


def test_emitir_guarda_producao(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-3", proj); eid = _perfil(app_db, lid, "producao")
    db = app_db.get_session()
    with pytest.raises(ValueError):
        nfe_emissao.emitir(db, lid, proj, _nota("R-3"), emitente_id=eid, emissor=FakeEmissor())
    res = nfe_emissao.emitir(db, lid, proj, _nota("R-3"), emitente_id=eid,
                             permitir_producao=True, emissor=FakeEmissor())
    assert res.status == StatusNota.AUTORIZADO
    db.close()


def test_emitir_erro_autorizacao(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-4", proj); eid = _perfil(app_db, lid, "homologacao")
    fake = FakeEmissor(status="erro_autorizacao", erros=[{"codigo": "215", "mensagem": "falha"}])
    db = app_db.get_session()
    res = nfe_emissao.emitir(db, lid, proj, _nota("R-4"), emitente_id=eid, emissor=fake)
    assert res.status == StatusNota.ERRO
    reg = db.query(app_db.DocumentoFiscal).filter_by(ref="R-4").first()
    assert reg.status == "erro" and reg.erros_json and not reg.xml_doc_id
    db.close()


def test_consultar_atualiza_registro(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-5", proj); eid = _perfil(app_db, lid, "homologacao")
    db = app_db.get_session()
    db.add(app_db.DocumentoFiscal(ref="R-5", projeto_nome=proj, loja_id=lid, emitente_id=eid, status="processando"))
    db.commit()
    res = nfe_emissao.consultar(db, "R-5", emissor=FakeEmissor())
    assert res.status == StatusNota.AUTORIZADO
    reg = db.query(app_db.DocumentoFiscal).filter_by(ref="R-5").first()
    assert reg.status == "autorizado" and reg.xml_doc_id       # baixou docs ao autorizar
    db.close()


def test_cancelar_atualiza_registro(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-6", proj); eid = _perfil(app_db, lid, "homologacao")
    db = app_db.get_session()
    db.add(app_db.DocumentoFiscal(ref="R-6", projeto_nome=proj, loja_id=lid, emitente_id=eid, status="autorizado"))
    db.commit()
    res = nfe_emissao.cancelar(db, "R-6", "cancelamento por erro de digitacao", emissor=FakeEmissor())
    assert res.status == StatusNota.CANCELADO
    reg = db.query(app_db.DocumentoFiscal).filter_by(ref="R-6").first()
    assert reg.status == "cancelado"
    db.close()


def test_consultar_resolve_emissor_pelo_emitente_id(app_db, seed, projetos_dir, monkeypatch):
    # o switch reg.loja_id -> reg.emitente_id: consultar SEM emissor injetado resolve pelo emitente do documento
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-7", proj)
    db = app_db.get_session()
    db.add(app_db.DocumentoFiscal(ref="R-7", projeto_nome=proj, loja_id=lid, emitente_id=777, status="processando"))
    db.commit()
    capturado = {}
    def _fake_emissor_para(_db, emitente_id):
        capturado["eid"] = emitente_id
        return FakeEmissor()
    monkeypatch.setattr(nfe_emissao, "_emissor_para", _fake_emissor_para)
    nfe_emissao.consultar(db, "R-7")
    assert capturado["eid"] == 777      # resolveu pelo emitente do documento, não pela loja (lid != 777)
    db.close()


def test_consultar_ref_inexistente(app_db, seed, projetos_dir):
    db = app_db.get_session()
    with pytest.raises(ValueError):
        nfe_emissao.consultar(db, "NAO-EXISTE", emissor=FakeEmissor())
    db.close()


def test_emitir_grava_fabrica_doc_id(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-F1", proj); eid = _perfil(app_db, lid, "homologacao")
    db = app_db.get_session()
    nfe_emissao.emitir(db, lid, proj, _nota("R-F1"), emitente_id=eid, emissor=FakeEmissor(),
                       fabrica_doc_id=99)
    reg = db.query(app_db.DocumentoFiscal).filter_by(ref="R-F1").first()
    assert reg.fabrica_doc_id == 99 and reg.emitente_id == eid
    db.close()


def test_emitir_homologacao_forca_nome_dest_sefaz(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-F2", proj); eid = _perfil(app_db, lid, "homologacao")
    fake = FakeEmissor()
    db = app_db.get_session()
    nfe_emissao.emitir(db, lid, proj, _nota("R-F2"), emitente_id=eid, emissor=fake)
    assert fake.nota_recebida["destinatario"]["nome"] == \
        "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL"
    db.close()


def test_emitir_producao_nao_forca_nome_dest(app_db, seed, projetos_dir):
    # regra SEFAZ só vale em homologação: em produção o nome do destinatário é preservado
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-F3", proj); eid = _perfil(app_db, lid, "producao")
    fake = FakeEmissor()
    db = app_db.get_session()
    nfe_emissao.emitir(db, lid, proj, _nota("R-F3"), emitente_id=eid,
                       permitir_producao=True, emissor=fake)
    assert fake.nota_recebida["destinatario"]["nome"] == "C"
    db.close()


# ------------------------------------------------------------------------------------------------
# NFS-e de serviço: emitir ramifica por tipo_documento="servico" (caminho aditivo, produto intacto)
# ------------------------------------------------------------------------------------------------

def test_emitir_servico_autoriza_guarda_docs(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "S-1", proj); eid = _perfil(app_db, lid, "homologacao")
    fake = FakeEmissorNfse()
    db = app_db.get_session()
    res = nfe_emissao.emitir(db, lid, proj, _nota_nfse("S-1"), tipo_documento="servico",
                             emitente_id=eid, emissor=fake)
    assert res.status == StatusNota.AUTORIZADO and res.chave == "CHS1"
    reg = db.query(app_db.DocumentoFiscal).filter_by(ref="S-1").first()
    assert reg.tipo_documento == "servico" and reg.status == "autorizado"
    assert reg.xml_doc_id and reg.danfe_doc_id
    docs = db.query(app_db.CicloDocumento).filter_by(projeto_nome=proj, etapa_codigo="15").all()
    assert {d.tipo for d in docs} == {"nfse_loja_xml", "nfse_loja_pdf"}
    assert fake.client.baixados == ["/nfse/xml.xml", "/nfse/nota.pdf"]
    db.close()


def test_emitir_servico_nao_carimba_nome_dest(app_db, seed, projetos_dir):
    # a NFS-e não tem `destinatario`; o carimbo SEFAZ de homologação (regra do NF-e) não se aplica.
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "S-2", proj); eid = _perfil(app_db, lid, "homologacao")
    fake = FakeEmissorNfse()
    db = app_db.get_session()
    nfe_emissao.emitir(db, lid, proj, _nota_nfse("S-2"), tipo_documento="servico",
                       emitente_id=eid, emissor=fake)
    assert "destinatario" not in fake.nota_recebida     # nota NFS-e intacta, sem carimbo
    db.close()


def test_consultar_servico_usa_caminho_nfse(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "S-3", proj); eid = _perfil(app_db, lid, "homologacao")
    db = app_db.get_session()
    db.add(app_db.DocumentoFiscal(ref="S-3", projeto_nome=proj, loja_id=lid, emitente_id=eid,
                                  tipo_documento="servico", status="processando"))
    db.commit()
    res = nfe_emissao.consultar(db, "S-3", emissor=FakeEmissorNfse())
    assert res.status == StatusNota.AUTORIZADO and res.chave == "CHS"
    reg = db.query(app_db.DocumentoFiscal).filter_by(ref="S-3").first()
    assert reg.status == "autorizado" and reg.xml_doc_id
    db.close()


def test_cancelar_servico_usa_caminho_nfse(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "S-4", proj); eid = _perfil(app_db, lid, "homologacao")
    db = app_db.get_session()
    db.add(app_db.DocumentoFiscal(ref="S-4", projeto_nome=proj, loja_id=lid, emitente_id=eid,
                                  tipo_documento="servico", status="autorizado"))
    db.commit()
    res = nfe_emissao.cancelar(db, "S-4", "cancelamento por erro de digitacao", emissor=FakeEmissorNfse())
    assert res.status == StatusNota.CANCELADO
    reg = db.query(app_db.DocumentoFiscal).filter_by(ref="S-4").first()
    assert reg.status == "cancelado"
    db.close()


class _FakeClientBaixaFalha(FakeClient):
    def baixar(self, caminho):
        raise RuntimeError("rede caiu ao baixar XML")


class _FakeEmissorBaixaFalha(FakeEmissor):
    def __init__(self):
        super().__init__(); self.client = _FakeClientBaixaFalha()


def test_emitir_autorizado_persiste_mesmo_se_baixa_falha(app_db, seed, projetos_dir):
    """Auditoria A9: se a baixa de XML/DANFE falhar, a nota JÁ autorizada não é desfeita;
    `consultar` rebaixa os documentos depois."""
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-A9", proj); eid = _perfil(app_db, lid, "homologacao")
    db = app_db.get_session()
    res = nfe_emissao.emitir(db, lid, proj, _nota("R-A9"), emitente_id=eid, emissor=_FakeEmissorBaixaFalha())
    assert res.status == StatusNota.AUTORIZADO
    reg = db.query(app_db.DocumentoFiscal).filter_by(ref="R-A9").first()
    assert reg is not None and reg.status == "autorizado"        # a nota NÃO se perdeu
    assert reg.xml_doc_id is None and reg.danfe_doc_id is None    # a baixa falhou
    db.close()
    # consultar (com cliente que baixa OK) recupera os documentos
    db2 = app_db.get_session()
    nfe_emissao.consultar(db2, "R-A9", emissor=FakeEmissor())
    reg2 = db2.query(app_db.DocumentoFiscal).filter_by(ref="R-A9").first()
    assert reg2.xml_doc_id and reg2.danfe_doc_id
    db2.close()
