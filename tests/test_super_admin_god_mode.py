"""super_admin = acesso pleno e irrestrito (god-mode): ignora todos os gates de
capacidade e de módulo/painel; opera dentro de qualquer loja (loja do header)."""
from auth import perfis
import mod_tenancy


def test_super_admin_pode_qualquer_capacidade():
    # capacidades reais e uma inexistente — super_admin nunca é barrado
    for cap in ("gerir_usuarios", "gerir_perfis", "acesso_operacional",
                "acesso_financeiro", "acesso_fiscal", "autorizar",
                "ver_parametros", "editar_dados_loja", "capacidade_que_nao_existe"):
        assert perfis.pode("super_admin", cap) is True, cap


def test_super_admin_acessa_todo_modulo_e_painel():
    for mod in ("cadastro", "comercial", "financeiro", "folha", "fiscal",
                "estoque", "expedicao", "montagem", "assistencias"):
        assert perfis.acessa_modulo("super_admin", mod) is True, mod
    assert perfis.acessa_painel("super_admin", "admin") is True
    assert perfis.acessa_painel("super_admin", "config") is True


def test_bypass_nao_vaza_para_outros_perfis():
    # operador continua barrado onde já era barrado (não abre buraco lateral)
    assert perfis.pode("operador", "gerir_perfis") is False
    assert perfis.acessa_modulo("operador", "financeiro") is False
    assert perfis.acessa_painel("operador", "admin") is False


def test_super_admin_adota_loja_do_header():
    # sem membership e sem loja própria, mas com header → loja ativa = header
    assert mod_tenancy.resolver_loja_ativa([], 5, None, is_super=True) == 5
    # sem header → sem loja ativa (precisa escolher uma loja no console)
    assert mod_tenancy.resolver_loja_ativa([], None, None, is_super=True) is None


def test_resolver_loja_ativa_nao_super_inalterado():
    # comportamento pré-existente preservado p/ usuário de loja
    assert mod_tenancy.resolver_loja_ativa([], 5, None) is None          # header sem acesso → None
    assert mod_tenancy.resolver_loja_ativa([7], None, 7) == 7            # default acessível
    assert mod_tenancy.resolver_loja_ativa([7], 7, None) == 7            # header acessível


def test_super_admin_cria_e_le_perfil_na_loja_escolhida(http_client_factory, seed, app_db):
    db = app_db.get_session()
    l1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    db.close()
    c = http_client_factory(); c.login("super", "senha123")
    c.loja_ativa = l1                                   # "entra" na loja L1
    # cria um perfil de acesso NA loja L1
    st, out = c.post("/api/admin/perfis", {"nome": "Vendas Plus", "base": "operador",
                                           "modulos": ["cadastro", "comercial"]})
    assert st == 201 and out["ok"], (st, out)
    # a matriz da loja L1 agora inclui o perfil recém-criado
    st, m = c.get("/api/admin/perfis")
    assert st == 200 and m["ok"]
    nomes = {p["nome"] for p in m["perfis"]}
    assert "Vendas Plus" in nomes, nomes


def test_super_admin_sem_loja_selecionada_erro_ao_criar_perfil(http_client_factory, seed):
    c = http_client_factory(); c.login("super", "senha123")   # sem c.loja_ativa
    st, out = c.post("/api/admin/perfis", {"nome": "X", "base": "operador", "modulos": []})
    assert out["ok"] is False and "loja" in (out.get("erro", "").lower())
