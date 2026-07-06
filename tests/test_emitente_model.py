import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


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


def test_migracao_perfil_fiscal_para_emitente_idempotente(app_db):
    """Backfill perfil_fiscal -> emitente: cria Emitente, seta loja.emitente_id, preserva o
    token e o endereço da loja (estado -> uf), e é idempotente (rodar 2x não duplica)."""
    import sqlite3
    s = app_db.get_session()
    lj = app_db.Loja(nome="Loja Fiscal", cnpj="19152134000156", estado="SP",
                     cidade="SAO PAULO", logradouro="Rua A", numero="10", bairro="Centro",
                     cep="12000-000")
    s.add(lj); s.flush()
    pf = app_db.PerfilFiscal(loja_id=lj.id, razao_social="INSPIRIUM",
                             regime_tributario="simples", csosn_padrao="101",
                             cfop_dentro_uf="5102", cfop_fora_uf="6102", serie_nfe="1",
                             papel_cnpj="loja_produto_servico",
                             focus_token_prod_enc="TOKEN_SECRETO_ENC",
                             ambiente_ativo="producao")
    s.add(pf); s.commit()
    loja_id = lj.id
    s.close()

    # roda a migração de dados 2x sobre o mesmo banco (idempotência)
    conn = sqlite3.connect(app_db.DB_PATH)
    app_db._run_migracoes(conn)
    app_db._run_migracoes(conn)
    conn.close()

    s = app_db.get_session()
    lj2 = s.query(app_db.Loja).get(loja_id)
    assert lj2.emitente_id is not None
    ems = s.query(app_db.Emitente).filter_by(razao_social="INSPIRIUM").all()
    assert len(ems) == 1                       # não duplicou
    em = ems[0]
    assert lj2.emitente_id == em.id
    assert em.cnpj == "19152134000156"
    assert em.uf == "SP" and em.cidade == "SAO PAULO"      # lojas.estado -> emitente.uf
    assert em.logradouro == "Rua A" and em.cep == "12000-000"
    assert em.focus_token_prod_enc == "TOKEN_SECRETO_ENC"  # token preservado
    assert em.ambiente_ativo == "producao"
    s.close()


def test_migracao_emitente_sem_perfil_fiscal_nao_estoura(app_db):
    """Idempotente e robusto: banco sem perfil_fiscal correspondente não gera Emitente órfão."""
    import sqlite3
    conn = sqlite3.connect(app_db.DB_PATH)
    app_db._run_migracoes(conn)   # não deve levantar
    conn.close()
