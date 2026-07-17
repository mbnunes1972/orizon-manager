import mod_cadastro


def test_func_sync_acesso_herda_funcao_e_senha_provisoria(app_db):
    db = app_db.get_session()
    loja = app_db.Loja(nome="L Acesso"); db.add(loja); db.flush()
    fn = app_db.Funcao(loja_id=loja.id, nome="Consultor de Vendas", perfil_padrao="operador", status="ativo")
    db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja.id, nome="Nova Consultora", cpf="12345678900",
                           funcao_id=fn.id, email="nova@loja.com", status="ativo")
    db.add(f); db.flush()
    ok, err = mod_cadastro.func_sync_acesso(db, f, {"acesso": {"tem_acesso": True, "email": "nova@loja.com"}})
    assert ok, err
    u = db.get(app_db.Usuario, f.usuario_id)
    assert u is not None
    assert u.funcao_id == fn.id          # conta herda a função do funcionário
    assert u.nivel == "operador"         # perfil default = perfil_padrao da função
    assert u.senha_provisoria == 1       # troca no 1º acesso
    assert u.login == "nova@loja.com"
    db.close()


def test_seletor_consultor_filtra_por_funcao(app_db):
    import main
    db = app_db.get_session()
    loja = app_db.Loja(nome="L Sel"); db.add(loja); db.flush()
    fc = app_db.Funcao(loja_id=loja.id, nome="Consultor de Vendas", status="ativo")
    fg = app_db.Funcao(loja_id=loja.id, nome="Gerente de Vendas", status="ativo")
    fm = app_db.Funcao(loja_id=loja.id, nome="Medidor", status="ativo")
    db.add_all([fc, fg, fm]); db.flush()

    def mkuser(nome, fid):
        u = app_db.Usuario(nome=nome, login=nome + "@l.com", nivel="operador",
                           loja_id=loja.id, ativo=1, funcao_id=fid)
        u.set_senha("x"); db.add(u); return u
    mkuser("Cons", fc.id); mkuser("Ger", fg.id); mkuser("Med", fm.id); mkuser("SemFuncao", None)
    db.commit()
    nomes = {u.nome for u in main._usuarios_atribuiveis_da_loja(db, loja.id)}
    assert nomes == {"Cons", "Ger"}     # medidor e sem-função ficam de fora
    db.close()


def test_seletor_resolve_funcao_via_funcionario_vinculado(app_db):
    import main
    db = app_db.get_session()
    loja = app_db.Loja(nome="L Sel2"); db.add(loja); db.flush()
    fc = app_db.Funcao(loja_id=loja.id, nome="Consultor de Vendas", status="ativo")
    db.add(fc); db.flush()
    func = app_db.Funcionario(loja_id=loja.id, nome="Via RH", funcao_id=fc.id, status="ativo")
    db.add(func); db.flush()
    u = app_db.Usuario(nome="Via RH", login="viarh@l.com", nivel="operador", loja_id=loja.id,
                       ativo=1, funcionario_id=func.id)   # função só no funcionário
    u.set_senha("x"); db.add(u); db.commit()
    nomes = {x.nome for x in main._usuarios_atribuiveis_da_loja(db, loja.id)}
    assert "Via RH" in nomes
    db.close()


def test_backfill_liga_usa_comissao_vendas(app_db):
    import database
    db = app_db.get_session()
    loja = app_db.Loja(nome="L Backfill"); db.add(loja); db.flush()
    fn = app_db.Funcao(loja_id=loja.id, nome="Consultor de Vendas", usa_comissao_vendas=0, status="ativo")
    db.add(fn); db.commit(); fid = fn.id; db.close()
    database._backfill_funcao_flags()
    db2 = app_db.get_session()
    assert db2.get(app_db.Funcao, fid).usa_comissao_vendas == 1
    db2.close()
