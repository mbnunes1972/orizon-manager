# tests/test_isolamento_f4.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_escopo_operacional_usuario_de_loja():
    import mod_tenancy as mt
    loja_id, err = mt.escopo_operacional({"nivel": "consultor", "loja_id": 7, "rede_id": None, "active_loja_id": 7})
    assert loja_id == 7 and err is None


def test_escopo_operacional_super_admin_sem_acesso():
    import mod_tenancy as mt
    loja_id, err = mt.escopo_operacional({"nivel": "super_admin", "loja_id": None, "rede_id": None, "active_loja_id": None})
    assert loja_id is None and err  # mensagem não-vazia


def test_escopo_operacional_admin_rede_sem_acesso():
    import mod_tenancy as mt
    loja_id, err = mt.escopo_operacional({"nivel": "admin_rede", "loja_id": None, "rede_id": 3, "active_loja_id": None})
    assert loja_id is None and err


def test_obj_da_loja():
    import main
    class _Obj:
        def __init__(self, loja_id): self.loja_id = loja_id
    class _DB:
        def __init__(self, obj): self._obj = obj
        def get(self, model, pk): return self._obj
    assert main._obj_da_loja(_DB(_Obj(1)), object, 5, 1).loja_id == 1   # mesma loja
    assert main._obj_da_loja(_DB(_Obj(2)), object, 5, 1) is None        # outra loja
    assert main._obj_da_loja(_DB(None), object, 5, 1) is None           # inexistente
    assert main._obj_da_loja(_DB(_Obj(1)), object, None, 1) is None     # pk vazio
    assert main._obj_da_loja(_DB(_Obj(1)), object, 0, 1) is None        # pk falsy (0)
    assert main._obj_da_loja(_DB(_Obj(1)), object, "", 1) is None       # pk falsy ("")


def test_projeto_da_loja():
    import main
    class _Proj:
        def __init__(self, loja_id): self.loja_id = loja_id
    class _DB:
        def __init__(self, p): self._p = p
        def get(self, model, pk): return self._p
    assert main._projeto_da_loja(_DB(_Proj(1)), "casa_a", 1).loja_id == 1
    assert main._projeto_da_loja(_DB(_Proj(2)), "casa_a", 1) is None
    assert main._projeto_da_loja(_DB(None), "casa_a", 1) is None
    assert main._projeto_da_loja(_DB(_Proj(1)), "", 1) is None           # nome_safe vazio


