"""Cadastro de parceiro por usuário de loja:
- deve vincular automaticamente à loja ativa do usuário (sem exigir seletor de loja);
- se a loja pertence a uma rede, o usuário pode optar por abrangência 'rede';
- /api/auth/me informa o rede_id/rede_nome de cada loja (para o front decidir a opção de rede).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, f"login falhou para {who}"
    return c


def test_consultor_cadastra_parceiro_vincula_loja_ativa(http_client_factory, seed):
    """Um consultor (perfil de loja, sem acesso a /api/admin/lojas) cadastra parceiro
    informando só o nome+abrangência 'loja', sem escolher loja. Deve entrar na loja dele."""
    c = _login(http_client_factory, "cons_l1")
    status, body = c.post("/api/parceiros", {"nome": "Marcenaria Silva", "abrangencia": "loja"})
    assert status == 200 and body.get("ok") is True, body
    pid = body["parceiro"]["id"]
    # visível na listagem operacional da própria loja
    status, lst = c.get("/api/parceiros")
    assert status == 200
    ids = {p["id"] for p in lst["parceiros"]}
    assert pid in ids, "parceiro recém-criado não apareceu na loja do consultor"


def test_consultor_cadastra_parceiro_sem_abrangencia_nunca_orfao(http_client_factory, seed):
    """Sem 'abrangencia' no payload, o parceiro ainda deve entrar na loja ativa
    (nunca criado órfão/invisível)."""
    c = _login(http_client_factory, "cons_l1")
    status, body = c.post("/api/parceiros", {"nome": "Vidraçaria Sol"})
    assert status == 200 and body.get("ok") is True, body
    pid = body["parceiro"]["id"]
    status, lst = c.get("/api/parceiros")
    ids = {p["id"] for p in lst["parceiros"]}
    assert pid in ids


def test_consultor_pode_cadastrar_parceiro_de_rede_da_propria_loja(http_client_factory, seed):
    """A loja do consultor pertence a uma rede; ele pode dar abrangência 'rede'
    para a rede da própria loja."""
    c = _login(http_client_factory, "cons_l1")
    status, body = c.post("/api/parceiros",
                          {"nome": "Fornecedor Regional", "abrangencia": "rede",
                           "rede_id": seed["rede_id"]})
    assert status == 200 and body.get("ok") is True, body
    assert body["parceiro"].get("abrangencia") == "rede"


def test_consultor_nao_cadastra_parceiro_de_outra_rede(http_client_factory, seed):
    """Abrangência 'rede' para uma rede fora do escopo do usuário deve ser barrada."""
    c = _login(http_client_factory, "cons_l1")
    status, body = c.post("/api/parceiros",
                          {"nome": "Fornecedor X", "abrangencia": "rede",
                           "rede_id": seed["rede_id"] + 999})
    assert body.get("ok") is False


def test_auth_me_inclui_rede_da_loja(http_client_factory, seed):
    """/api/auth/me deve trazer rede_id (e rede_nome) de cada loja do usuário,
    para o front decidir se oferece a opção de abrangência 'rede'."""
    c = _login(http_client_factory, "cons_l1")
    status, body = c.get("/api/auth/me")
    assert status == 200 and body.get("ok") is True
    lojas = body["usuario"]["lojas"]
    assert lojas, "usuário deveria ter ao menos a própria loja"
    l = next(x for x in lojas if x["id"] == seed["loja1_id"])
    assert l.get("rede_id") == seed["rede_id"]
    assert "rede_nome" in l
