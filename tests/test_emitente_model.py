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


def test_upgrade_nfe_emissao_preserva_dados_via_init_db(tmp_path, monkeypatch):
    """Regressão: em banco legado com nfe_emissao populada, init_db() deve mover os dados para
    documento_fiscal (rename ANTES do create_all) e backfillar emitente_id."""
    import sqlite3, importlib, database as _db
    dbfile = str(tmp_path / "legado.db")
    # monta um banco "antigo": lojas (com emitente_id) + nfe_emissao com 1 emissão
    conn = sqlite3.connect(dbfile); c = conn.cursor()
    c.execute("CREATE TABLE lojas (id INTEGER PRIMARY KEY, nome TEXT, emitente_id INTEGER)")
    c.execute("INSERT INTO lojas (id, nome, emitente_id) VALUES (7, 'L', 55)")
    c.execute("CREATE TABLE nfe_emissao (id INTEGER PRIMARY KEY, ref TEXT, projeto_nome TEXT, loja_id INTEGER, status TEXT, chave_nfe TEXT)")
    c.execute("INSERT INTO nfe_emissao (ref, projeto_nome, loja_id, status, chave_nfe) VALUES ('R-OLD','ProjX',7,'autorizado','CH-OLD')")
    conn.commit(); conn.close()
    # aponta o database para esse arquivo e roda init_db (rebind engine/DB_PATH)
    monkeypatch.setattr(_db, "DB_PATH", dbfile)
    monkeypatch.setattr(_db, "ENGINE", _db.create_engine(f"sqlite:///{dbfile}"))
    _db.init_db()
    # a emissão antiga tem de aparecer em documento_fiscal, com emitente_id backfillado
    conn = sqlite3.connect(dbfile); c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='nfe_emissao'")
    assert c.fetchone() is None                               # tabela antiga renomeada
    c.execute("SELECT ref, chave_nfe, tipo_documento, emitente_id FROM documento_fiscal WHERE ref='R-OLD'")
    row = c.fetchone(); conn.close()
    assert row == ('R-OLD', 'CH-OLD', 'produto', 55)          # dados preservados + backfill
