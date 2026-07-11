"""Escopo de visibilidade de projetos por projetista:
- Consultor vê só os projetos que criou (+ legados sem criador);
- Gerente de Vendas e níveis acima (e operacionais de pós-venda) veem todos da loja.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_ve_apenas_proprios_projetos():
    from main import _ve_apenas_proprios_projetos
    assert _ve_apenas_proprios_projetos("operador") is True
    assert _ve_apenas_proprios_projetos("gerencial") is False
    assert _ve_apenas_proprios_projetos("master") is False
    assert _ve_apenas_proprios_projetos("master") is False
    assert _ve_apenas_proprios_projetos("projetista_executivo") is False


def test_projeto_visivel_ao_ator():
    from main import _projeto_visivel_ao_ator

    class _Meta:
        def __init__(self, cpid): self.criado_por_id = cpid

    do_cons10 = _Meta(10)
    legado    = _Meta(None)
    cons10      = {"nivel": "operador", "id": 10}
    outro_cons  = {"nivel": "operador", "id": 20}
    gerente     = {"nivel": "gerencial", "id": 30}

    assert _projeto_visivel_ao_ator(do_cons10, cons10) is True       # o próprio
    assert _projeto_visivel_ao_ator(do_cons10, outro_cons) is False  # de outro consultor
    assert _projeto_visivel_ao_ator(legado, outro_cons) is True      # legado (sem criador)
    assert _projeto_visivel_ao_ator(do_cons10, gerente) is True      # gerente vê tudo
    assert _projeto_visivel_ao_ator(None, cons10) is False


def test_filtrar_projetos_por_loja_escopo_projetista(app_db):
    import main
    db = app_db.get_session()
    try:
        l = app_db.Loja(nome="L Escopo")
        db.add(l); db.flush()
        db.add_all([
            app_db.Projeto(nome_safe="P_own",    loja_id=l.id, criado_por_id=10),
            app_db.Projeto(nome_safe="P_other",  loja_id=l.id, criado_por_id=20),
            app_db.Projeto(nome_safe="P_legacy", loja_id=l.id, criado_por_id=None),
        ])
        db.commit()
        projetos = [{"nome_safe": n} for n in ("P_own", "P_other", "P_legacy")]
        cons10 = {"nivel": "operador", "id": 10}
        gerente = {"nivel": "gerencial", "id": 30}
        vis_cons = {p["nome_safe"] for p in
                    main._filtrar_projetos_por_loja(projetos, db, l.id, ator=cons10)}
        vis_ger = {p["nome_safe"] for p in
                   main._filtrar_projetos_por_loja(projetos, db, l.id, ator=gerente)}
        # sem ator: comportamento antigo (só loja), sem restrição de criador
        vis_sem = {p["nome_safe"] for p in
                   main._filtrar_projetos_por_loja(projetos, db, l.id)}
    finally:
        db.close()
    assert vis_cons == {"P_own", "P_legacy"}                 # próprio + legado, não o de outro
    assert vis_ger == {"P_own", "P_other", "P_legacy"}       # gerente vê todos
    assert vis_sem == {"P_own", "P_other", "P_legacy"}       # sem ator: sem filtro por criador
