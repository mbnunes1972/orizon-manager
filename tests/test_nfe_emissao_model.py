import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_modelo_nfe_emissao(db_pg_limpo):
    """Persistência do DocumentoFiscal + unicidade do ref. No Postgres as FKs são reais
    (emitente/loja/ciclo_documento precisam existir — o SQLite deixava id fabricado passar)."""
    database = db_pg_limpo
    s = database.Session()
    em = database.Emitente(cnpj="19152134000156", razao_social="EMIT TESTE")
    doc = database.CicloDocumento(projeto_nome="Proj_L2", etapa_codigo="12",
                                  tipo="pedido_fabrica", arquivo_path="x.pdf",
                                  nome_original="x.pdf")
    s.add_all([em, doc]); s.flush()
    loja_id = s.query(database.Loja).first().id      # loja seed do init_db
    e = database.DocumentoFiscal(ref="TESTE-1", projeto_nome="Proj_L2", tipo_documento="produto",
                                 emitente_id=em.id, loja_id=loja_id,
                                 status="autorizado", chave_nfe="CH", numero="10", serie="1",
                                 fabrica_doc_id=doc.id)
    s.add(e); s.commit()
    lido = s.query(database.DocumentoFiscal).filter_by(ref="TESTE-1").first()
    assert lido.status == "autorizado" and lido.chave_nfe == "CH" and lido.etapa_codigo == "15"
    assert lido.fabrica_doc_id == doc.id
    assert lido.tipo_documento == "produto" and lido.emitente_id == em.id
    from sqlalchemy.exc import IntegrityError
    import pytest
    s.add(database.DocumentoFiscal(ref="TESTE-1"))
    with pytest.raises(IntegrityError):
        s.commit()
    s.rollback(); s.close()
