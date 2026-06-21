# tests/test_isolamento_f4.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_escopo_operacional_usuario_de_loja():
    import mod_tenancy as mt
    loja_id, err = mt.escopo_operacional({"nivel": "consultor", "loja_id": 7, "rede_id": None})
    assert loja_id == 7 and err is None


def test_escopo_operacional_super_admin_sem_acesso():
    import mod_tenancy as mt
    loja_id, err = mt.escopo_operacional({"nivel": "super_admin", "loja_id": None, "rede_id": None})
    assert loja_id is None and err  # mensagem não-vazia


def test_escopo_operacional_admin_rede_sem_acesso():
    import mod_tenancy as mt
    loja_id, err = mt.escopo_operacional({"nivel": "admin_rede", "loja_id": None, "rede_id": 3})
    assert loja_id is None and err
