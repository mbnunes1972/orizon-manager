# -*- coding: utf-8 -*-
"""Captação provisória (14/09/2026, PLANO_SEMANA_1.md) — Lead como entidade própria, nascendo
antes do Cliente e do Projeto. NÃO é o módulo de Captação definitivo (LISTA_PARALELA.md §
FRONTEIRA). Cobre: criar lead, conversar, converter em cliente com histórico preservado e troca
de responsável, e a regra `Cliente.origem = "lead/" + Lead.canal`."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _login(factory, who="dir_l1"):
    c = factory()
    st, body = c.login(who, "senha123")
    assert st == 200 and body["ok"], body
    return c, body["usuario"]["id"]


def test_criar_lead(http_client_factory, seed, app_db):
    c, _uid = _login(http_client_factory)
    st, body = c.post("/api/leads", {"nome": "Fulano Interessado", "telefone": "11999990000",
                                     "canal": "google"})
    assert st == 200 and body["ok"], body
    lead = body["lead"]
    assert lead["nome"] == "Fulano Interessado"
    assert lead["canal"] == "google"
    assert lead["situacao"] == "novo"
    assert lead["cliente_id"] is None

    db = app_db.get_session()
    try:
        l = db.get(app_db.Lead, lead["id"])
        assert l is not None
        assert l.loja_id == seed["loja1_id"]
    finally:
        db.close()


def test_criar_lead_recusa_sem_nome(http_client_factory, seed):
    c, _uid = _login(http_client_factory)
    st, body = c.post("/api/leads", {"telefone": "11999990000"})
    assert st == 400 and not body["ok"], body


def test_criar_lead_com_dados_extra_por_template(http_client_factory, seed, app_db):
    """`dados`/`template` cobrem o que varia por formulário de captação, sem migration."""
    c, _uid = _login(http_client_factory)
    st, body = c.post("/api/leads", {
        "nome": "Ciclana", "canal": "instagram", "template": "form_instagram_v1",
        "dados": {"expectativa_orcamento": 45000, "ambiente_interesse": "cozinha"},
    })
    assert st == 200 and body["ok"], body
    assert body["lead"]["template"] == "form_instagram_v1"
    assert body["lead"]["dados"] == {"expectativa_orcamento": 45000, "ambiente_interesse": "cozinha"}


def test_conversar_com_lead(http_client_factory, seed, app_db):
    c, _uid = _login(http_client_factory)
    st, body = c.post("/api/leads", {"nome": "Beltrano", "canal": "facebook"})
    lead_id = body["lead"]["id"]

    st, body = c.post(f"/api/leads/{lead_id}/conversa/mensagens", {"corpo": "Primeiro contato feito."})
    assert st == 200 and body["ok"], body

    st, body = c.get(f"/api/leads/{lead_id}/conversa")
    assert st == 200 and body["ok"], body
    corpos = [m["corpo"] for m in body["mensagens"]]
    assert "Primeiro contato feito." in corpos
    assert body["conversa"]["lead_id"] == lead_id
    assert body["conversa"]["cliente_id"] is None


def test_conversa_do_lead_e_unica_get_or_create(http_client_factory, seed):
    c, _uid = _login(http_client_factory)
    st, body = c.post("/api/leads", {"nome": "Sicrano", "canal": "site"})
    lead_id = body["lead"]["id"]
    st, body1 = c.get(f"/api/leads/{lead_id}/conversa")
    st, body2 = c.get(f"/api/leads/{lead_id}/conversa")
    assert body1["conversa"]["id"] == body2["conversa"]["id"]


def test_converter_lead_em_cliente_leva_conversa_e_troca_responsavel(http_client_factory, seed, app_db):
    c, dir_id = _login(http_client_factory)
    st, body = c.post("/api/leads", {"nome": "Novo Cliente Via Lead", "telefone": "11988887777",
                                     "canal": "google"})
    assert st == 200 and body["ok"], body
    lead_id = body["lead"]["id"]

    # histórico ANTES da conversão — é o que prova que não fica órfão.
    st, body = c.post(f"/api/leads/{lead_id}/conversa/mensagens",
                      {"corpo": "Cliente pediu orçamento de cozinha planejada."})
    assert st == 200 and body["ok"], body

    c_consultor, consultor_id = _login(http_client_factory, "cons_l1")
    assert consultor_id != dir_id

    st, body = c.post(f"/api/leads/{lead_id}/converter",
                      {"consultor_id": consultor_id, "cpf": "529.982.247-25"})
    assert st == 200 and body["ok"], body
    cliente = body["cliente"]
    assert cliente["nome"] == "Novo Cliente Via Lead"
    assert cliente["telefone"] == "11988887777"
    assert cliente["origem"] == "lead/google"
    assert body["lead"]["situacao"] == "convertido"
    assert body["lead"]["cliente_id"] == cliente["id"]

    # a conversa segue com o histórico E muda de dono — os dois testados contra o banco direto,
    # não só a resposta da API.
    db = app_db.get_session()
    try:
        from database import Conversa, ConversaMensagem
        conv = db.query(Conversa).filter_by(lead_id=lead_id).order_by(Conversa.id.asc()).first()
        assert conv is not None
        assert conv.cliente_id == cliente["id"], "cliente_id tem que ser ADICIONADO na conversão"
        assert conv.lead_id == lead_id, "lead_id é proveniência — nunca é limpo na conversão"
        assert conv.responsavel_usuario_id == consultor_id, (
            "responsável passa a ser o consultor que fará o briefing")
        corpos = [m.corpo for m in
                 db.query(ConversaMensagem).filter_by(conversa_id=conv.id).all()]
        assert "Cliente pediu orçamento de cozinha planejada." in corpos, (
            "histórico órfão na conversão é o que separaria 'simples' de 'descartável'")

        lead = db.get(app_db.Lead, lead_id)
        assert lead.responsavel_usuario_id == consultor_id, (
            "Lead.responsavel_usuario_id não pode divergir do da conversa — mesma transferência")
    finally:
        db.close()


def test_origem_sem_canal_no_lead_ainda_marca_como_lead(http_client_factory, seed, app_db):
    """Lead sem canal preenchido (formulário incompleto) não pode travar a conversão nem
    inventar um canal — cai em 'lead' liso, nunca 'lead/None' ou string vazia."""
    c, _uid = _login(http_client_factory)
    st, body = c.post("/api/leads", {"nome": "Sem Canal Nenhum"})
    assert st == 200 and body["ok"], body
    lead_id = body["lead"]["id"]
    _c2, consultor_id = _login(http_client_factory, "cons_l1")
    st, body = c.post(f"/api/leads/{lead_id}/converter", {"consultor_id": consultor_id})
    assert st == 200 and body["ok"], body
    assert body["cliente"]["origem"] == "lead"


def test_converter_lead_ja_convertido_recusa(http_client_factory, seed):
    c, _uid = _login(http_client_factory)
    st, body = c.post("/api/leads", {"nome": "Duplo Convertido", "canal": "site"})
    lead_id = body["lead"]["id"]
    _c2, consultor_id = _login(http_client_factory, "cons_l1")
    st, body = c.post(f"/api/leads/{lead_id}/converter", {"consultor_id": consultor_id})
    assert st == 200 and body["ok"], body
    st, body = c.post(f"/api/leads/{lead_id}/converter", {"consultor_id": consultor_id})
    assert st == 400 and not body["ok"], body


def test_converter_lead_recusa_cpf_invalido(http_client_factory, seed):
    c, _uid = _login(http_client_factory)
    st, body = c.post("/api/leads", {"nome": "CPF Ruim", "canal": "site"})
    lead_id = body["lead"]["id"]
    _c2, consultor_id = _login(http_client_factory, "cons_l1")
    st, body = c.post(f"/api/leads/{lead_id}/converter",
                      {"consultor_id": consultor_id, "cpf": "111.111.111-11"})
    assert st == 400 and not body["ok"], body


def test_conversa_do_lead_acessivel_pelo_endpoint_generico_do_chat(http_client_factory, seed):
    """O frontend abre/posta na conversa do lead pelos endpoints GENÉRICOS do chat
    (/api/comunicacao/conversas/<id>/...), não pelos dedicados de /api/leads/. Esses endpoints
    exigem participante (`pode_escrever_conversa`) — sem o responsável do lead virar participante
    na criação da conversa, ele mesmo não conseguiria postar por esse caminho."""
    c, dir_id = _login(http_client_factory)
    st, body = c.post("/api/leads", {"nome": "Genérico", "canal": "site"})
    lead_id = body["lead"]["id"]
    st, body = c.get(f"/api/leads/{lead_id}/conversa")
    conv_id = body["conversa"]["id"]

    st, body = c.get(f"/api/comunicacao/conversas/{conv_id}/mensagens")
    assert st == 200 and body["ok"], body

    st, body = c.post(f"/api/comunicacao/conversas/{conv_id}/mensagens",
                      {"corpo": "Mensagem pelo endpoint genérico."})
    assert st == 201 and body["ok"], body

    st, body = c.get(f"/api/comunicacao/conversas/{conv_id}/mensagens")
    assert st == 200 and body["ok"], body
    assert "Mensagem pelo endpoint genérico." in [m["corpo"] for m in body["mensagens"]]

    _c2, consultor_id = _login(http_client_factory, "cons_l1")
    st, body = c.post(f"/api/leads/{lead_id}/converter", {"consultor_id": consultor_id})
    assert st == 200 and body["ok"], body

    st, body = _c2.post(f"/api/comunicacao/conversas/{conv_id}/mensagens",
                        {"corpo": "Consultor assumiu após a conversão."})
    assert st == 201 and body["ok"], body


def test_listar_leads_da_loja(http_client_factory, seed):
    c, _uid = _login(http_client_factory)
    c.post("/api/leads", {"nome": "Lista Um", "canal": "site"})
    c.post("/api/leads", {"nome": "Lista Dois", "canal": "google"})
    st, body = c.get("/api/leads")
    assert st == 200 and body["ok"], body
    nomes = {l["nome"] for l in body["leads"]}
    assert {"Lista Um", "Lista Dois"}.issubset(nomes)
