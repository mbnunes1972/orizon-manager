# -*- coding: utf-8 -*-
"""Unicidade de cliente por REDE — decisão 2026-09-16 (Homologação, achado do vazamento de
tenancy: pdm2026 alcançando a Loja Teste). A regra fechada com o Marcelo:

  "A unicidade do cliente é por rede. Loja de rede, ao encontrar o CPF já cadastrado em outra
  loja da mesma rede, puxa o cadastro existente e confirma com o cliente. Loja avulsa duplica.
  Compartilha-se o cadastro, nunca o histórico comercial — nome, CPF, contato e endereço viajam
  entre lojas da mesma rede; projetos, orçamentos e valores não."

Cobre: constraint composta no banco (rede/loja avulsa), o convite no cadastro, a listagem
ampliada (`/api/clientes`), o acesso cross-loja ao cadastro (`_cliente_acessivel`) e o isolamento
do histórico comercial (projetos) mesmo com cadastro compartilhado.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, f"login falhou para {who}"
    return c


# ── Constraint no banco (sem HTTP — prova direta da regra composta) ─────────────────────────

def test_constraint_permite_mesmo_cpf_em_redes_diferentes(app_db):
    from sqlalchemy.exc import IntegrityError
    db = app_db.get_session()
    r1 = app_db.Rede(nome="Rede A"); r2 = app_db.Rede(nome="Rede B")
    db.add_all([r1, r2]); db.flush()
    l1 = app_db.Loja(nome="Loja A1", rede_id=r1.id, codigo="LA1")
    l2 = app_db.Loja(nome="Loja B1", rede_id=r2.id, codigo="LB1")
    db.add_all([l1, l2]); db.flush()
    db.add(app_db.Cliente(nome="Fulano", cpf="123.456.789-09", loja_id=l1.id, rede_id=r1.id))
    db.commit()
    # mesmo CPF, rede diferente: permitido
    db.add(app_db.Cliente(nome="Fulano B", cpf="123.456.789-09", loja_id=l2.id, rede_id=r2.id))
    db.commit()
    total = db.query(app_db.Cliente).filter_by(cpf="123.456.789-09").count()
    db.close()
    assert total == 2


def test_constraint_bloqueia_mesmo_cpf_na_mesma_rede_lojas_diferentes(app_db):
    from sqlalchemy.exc import IntegrityError
    db = app_db.get_session()
    r1 = app_db.Rede(nome="Rede C"); db.add(r1); db.flush()
    l1 = app_db.Loja(nome="Loja C1", rede_id=r1.id, codigo="LC1")
    l2 = app_db.Loja(nome="Loja C2", rede_id=r1.id, codigo="LC2")
    db.add_all([l1, l2]); db.flush()
    db.add(app_db.Cliente(nome="Ciclano", cpf="987.654.321-00", loja_id=l1.id, rede_id=r1.id))
    db.commit()
    db.add(app_db.Cliente(nome="Ciclano 2", cpf="987.654.321-00", loja_id=l2.id, rede_id=r1.id))
    try:
        db.commit()
        assert False, "constraint uq_clientes_cpf_rede deveria ter barrado"
    except IntegrityError:
        db.rollback()
    db.close()


def test_constraint_permite_mesmo_cpf_em_duas_lojas_avulsas(app_db):
    db = app_db.get_session()
    l1 = app_db.Loja(nome="Avulsa 1", codigo="AV1")   # rede_id NULL
    l2 = app_db.Loja(nome="Avulsa 2", codigo="AV2")   # rede_id NULL
    db.add_all([l1, l2]); db.flush()
    db.add(app_db.Cliente(nome="Beltrano", cpf="111.222.333-96", loja_id=l1.id))
    db.commit()
    db.add(app_db.Cliente(nome="Beltrano 2", cpf="111.222.333-96", loja_id=l2.id))
    db.commit()   # não deve levantar — duas lojas avulsas são escopos independentes
    total = db.query(app_db.Cliente).filter_by(cpf="111.222.333-96").count()
    db.close()
    assert total == 2


def test_constraint_bloqueia_mesmo_cpf_duas_vezes_na_mesma_loja_avulsa(app_db):
    from sqlalchemy.exc import IntegrityError
    db = app_db.get_session()
    l1 = app_db.Loja(nome="Avulsa 3", codigo="AV3")
    db.add(l1); db.flush()
    db.add(app_db.Cliente(nome="X", cpf="444.555.666-58", loja_id=l1.id))
    db.commit()
    db.add(app_db.Cliente(nome="X2", cpf="444.555.666-58", loja_id=l1.id))
    try:
        db.commit()
        assert False, "constraint uq_clientes_cpf_loja_avulsa deveria ter barrado"
    except IntegrityError:
        db.rollback()
    db.close()


# ── HTTP: convite, acesso cross-loja e isolamento de histórico ──────────────────────────────
# seed (conftest.py): l1/l2 na MESMA rede; cliente_l1 (CPF 111.444.777-35) é da loja 1.

def test_convite_cross_loja_mesma_rede_nao_cria_duplicata(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    status, body = c.post("/api/clientes",
                          {"nome": "Novo Nome Tentado", "cpf": "111.444.777-35",
                           "email": "x@x.com", "telefone": "(11) 90000-0000"})
    assert status == 200 and body["ok"] is True
    assert body.get("cliente_existente") is True
    assert body["cliente"]["id"] == seed["cliente_l1_id"]
    assert body["cliente"]["nome"] == "Cliente L1"   # o cadastro ORIGINAL, não o nome tentado
    db = app_db.get_session()
    total = db.query(app_db.Cliente).filter_by(cpf="111.444.777-35").count()
    db.close()
    assert total == 1, "convite não pode duplicar a linha"


def test_editar_cadastro_compartilhado_de_outra_loja_da_mesma_rede(http_client_factory, seed):
    """Decisão 16/09 confirmada: editar contato/endereço de um cliente compartilhado é permitido
    de qualquer loja da rede — é uma linha só, uma verdade só."""
    c = _login(http_client_factory, "dir_l2")
    status, body = c.post("/api/clientes/%d/editar" % seed["cliente_l1_id"],
                          {"telefone": "(11) 98888-7777"})
    assert status == 200 and body["ok"] is True
    assert body["cliente"]["telefone"] == "(11) 98888-7777"


def test_projeto_novo_em_loja_b_com_cliente_compartilhado_de_loja_a(
        http_client_factory, seed, app_db):
    """A mecânica real de 'puxar o cadastro': loja B cria um projeto NOVO usando o cliente_id
    de um cliente cujo cadastro nasceu na loja A (mesma rede) — sem duplicar o cadastro, e sem
    o projeto vazar para a loja A."""
    c = _login(http_client_factory, "dir_l2")
    status, body = c.post("/projetos/novo",
                          {"nome_projeto": "Projeto via cadastro compartilhado",
                           "cliente_id": seed["cliente_l1_id"]})
    assert status == 200 and body.get("ok") is True, body
    nome_safe = body["projeto"]["nome_safe"]

    db = app_db.get_session()
    meta = db.query(app_db.Projeto).filter_by(nome_safe=nome_safe).first()
    loja_do_projeto = meta.loja_id if meta else None
    db.close()
    assert loja_do_projeto == seed["loja2_id"], "o projeto tem que pertencer a quem criou (loja B)"

    # E a lista de clientes da loja B agora inclui esse cliente (Confirmação 1 do design)
    status, lst = c.get("/api/clientes")
    ids = {cl["id"] for cl in lst["clientes"]}
    assert seed["cliente_l1_id"] in ids, "cliente puxado tem que aparecer na lista de quem o atende agora"

    # Mas a loja A (dona do cadastro) NÃO vê o projeto criado pela loja B nessa lista de histórico
    c1 = _login(http_client_factory, "dir_l1")
    status, dp = c1.get("/api/clientes/%d/projetos" % seed["cliente_l1_id"])
    assert status == 200
    nomes_visiveis = {p["nome_safe"] for p in dp["projetos"]}
    assert nome_safe not in nomes_visiveis, (
        "histórico comercial de outra loja vazou mesmo com cadastro compartilhado")
