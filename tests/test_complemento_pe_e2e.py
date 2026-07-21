"""Fatia 3 da Revisão de PE (2026-07-21) — E2E HTTP do Negociar Complemento + Termo Aditivo.

Orçamento de COMPLEMENTO: só os ambientes marcados, base de valores = PE, editável
mesmo com contrato assinado (isenção deliberada da trava). Termo Aditivo: modelo versionado
da loja (tipo 'termo_aditivo'), PDF, assinatura loja+cliente — SEM efeito contábil.
"""
import json
import os


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def _setup(app_db, seed, http_client_factory):
    """Ambiente 80k no orçamento do contrato, PE de 84k, marcado Renegociar, contrato ASSINADO."""
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    nome = orc.projeto_id
    pa = app_db.PoolAmbiente(nome="Cozinha", nome_exibicao="Cozinha", xml_path="fake/coz.xml",
                             ambientes_json="{}", projeto_id=nome,
                             budget_total=80000.0, order_total=30000.0)
    db.add(pa); db.flush()
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=1))
    db.add(app_db.ArquivoPE(projeto_nome=nome, pool_ambiente_id=pa.id, formato="xml_pe",
                            valor_atualizado=32000.0, valor_venda=84000.0))
    pa.renegociar_pe = 1
    # assina o contrato do seed (1ª assinatura já liga a trava _contrato_assinado)
    ct = (db.query(app_db.Contrato).filter_by(projeto_nome=nome)
            .order_by(app_db.Contrato.id.desc()).first())
    db.add(app_db.ContratoAssinatura(contrato_id=ct.id, parte="loja", nome="Loja",
                                     cpf="000.000.000-00", hash_sha256="x"))
    db.commit()
    pid = pa.id
    db.close()
    # projeto.json mínimo (a geração de documentos lê do disco; cliente cai no fallback do banco)
    import main as _main
    pdir = os.path.join(_main.PROJETOS_DIR, nome)
    os.makedirs(pdir, exist_ok=True)
    with open(os.path.join(pdir, "projeto.json"), "w", encoding="utf-8") as f:
        json.dump({"nome_projeto": nome}, f)
    return nome, pid, oid


def test_complemento_e_aditivo_ponta_a_ponta(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed, http_client_factory)
    c = _login(http_client_factory, "dir_l1")

    # 1) get-or-create do orçamento de ajuste: só o marcado, base = PE (84k)
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 200 and body["ok"], body
    aj = body["orcamento"]
    assert aj["complemento_pe"] is True and aj["nome"] == "Complemento PE"
    assert abs(aj["valor_total"] - 84000.0) < 0.5, aj["valor_total"]
    aj_id = aj["id"]

    # idempotente: repetir devolve o MESMO orçamento
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 200 and body["orcamento"]["id"] == aj_id

    # 2) trava: o orçamento CONTRATADO segue bloqueado; o AJUSTE é editável
    st, body = c.post(f"/api/orcamentos/{oid}/margens", {"desconto_pct": 5})
    assert st == 403, body
    st, body = c.post(f"/api/orcamentos/{aj_id}/margens", {"desconto_pct": 0})
    assert st == 200 and body["ok"], body

    # 3) aditivo exige modelo ativo do tipo termo_aditivo
    st, body = c.post(f"/api/projetos/{nome}/aditivo", {})
    assert st == 400 and "modelo" in (body.get("erro") or "").lower(), body

    import mod_documentos
    db = app_db.get_session()
    corpo = ("# TERMO ADITIVO [NUM_ADITIVO]\n"
             "1. Aditivo ao contrato [NUM_CONTRATO_ORIGINAL].\n"
             "2. Ambientes renegociados:\n[AMBIENTES_COMPLEMENTO]\n"
             "3. Valor original [VALOR_ORIGINAL_COMPLEMENTO]; novo [VALOR_NOVO_COMPLEMENTO]; "
             "diferença [VALOR_COMPLEMENTO].\n")
    mv = mod_documentos.criar_versao(db, seed["loja1_id"], "termo_aditivo", corpo, "teste.md", None)
    mod_documentos.ativar(db, mv.id)
    db.close()

    # 4) gera o aditivo: diferença = 84.000 − 80.000 = 4.000 (só os renegociados, por ambiente)
    st, body = c.post(f"/api/projetos/{nome}/aditivo", {})
    assert st == 200 and body["ok"], body
    ad = body["aditivo"]
    assert ad["num_aditivo"].startswith("TA")
    assert ad["status"] == "para_assinatura" and ad["tem_pdf"] is True
    assert abs(ad["dados"]["diferenca"] - 4000.0) < 0.5, ad["dados"]
    assert ad["dados"]["ambientes"][0]["ambiente"] == "Cozinha"

    # 5) assinatura loja + cliente → assinado; regerar depois é recusado
    st, body = c.post(f"/api/projetos/{nome}/aditivo/assinar",
                      {"parte": "loja", "nome": "Rep Loja", "cpf": "111.111.111-11"})
    assert st == 200 and body["status"] == "assinado_loja", body
    st, body = c.post(f"/api/projetos/{nome}/aditivo/assinar",
                      {"parte": "loja", "nome": "Rep Loja", "cpf": "111.111.111-11"})
    assert st == 400   # parte repetida
    st, body = c.post(f"/api/projetos/{nome}/aditivo/assinar",
                      {"parte": "cliente", "nome": "Cliente L1", "cpf": "111.444.777-35"})
    assert st == 200 and body["status"] == "assinado", body
    st, body = c.post(f"/api/projetos/{nome}/aditivo", {})
    assert st == 403, body

    # 6) GET devolve o estado completo
    st, body = c.get(f"/api/projetos/{nome}/aditivo")
    assert st == 200 and body["aditivo"]["status"] == "assinado"
    assert {a["parte"] for a in body["aditivo"]["assinaturas"]} == {"loja", "cliente"}


def test_complemento_sem_marcados_e_escopo(http_client_factory, seed, app_db):
    # sem ambiente marcado → 400; outra loja → 404
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, seed["orcamento_l1_id"])
    nome = orc.projeto_id
    for pa in db.query(app_db.PoolAmbiente).filter_by(projeto_id=nome).all():
        pa.renegociar_pe = 0
    db.commit(); db.close()
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 400 and "marcado" in (body.get("erro") or "").lower()
    c2 = _login(http_client_factory, "dir_l2")
    st, body = c2.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 404
