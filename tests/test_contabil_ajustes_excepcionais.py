"""Descontos e Acréscimos Excepcionais de Fábrica — ledger + E2E (spec 2026-07-21).

Exemplos numéricos da spec viram testes: Loja 3 (100.000 → 95.000 CMV / 104.500 a pagar,
conciliação SEM sobra/falta) e o triangular Inspirium/Verano (venda só na compradora, acerto
consolidado só na credora, invariantes de conta corrente). Implantação de saldos pelo PL (3.5).
"""
import json
import mod_contabil as mc


def _s(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id)


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def test_eventos_novos_pares_de_contas():
    E = mc.EVENTOS
    assert E["implantacao_credito_fabrica"][:2] == ("1.1.08", "3.5")
    assert E["implantacao_divida_fabrica"][:2] == ("3.5", "2.1.08")
    assert E["desconto_excepcional_fabrica"][:2] == ("2.1.04.06", "1.1.08")
    assert E["desconto_excepcional_intercompany"][:2] == ("2.1.04.06", "2.1.09")
    assert E["acrescimo_excepcional_fabrica"][:2] == ("2.1.08", "2.1.04.06")
    assert E["acerto_acordo_intercompany"][:2] == ("1.1.09", "1.1.08")
    assert E["liquidacao_conta_corrente_devedora"][:2] == ("2.1.09", "1.1.01")
    assert E["liquidacao_conta_corrente_credora"][:2] == ("1.1.01", "1.1.09")
    assert E["baixa_credito_fabrica"][:2] == ("3.5", "1.1.08")
    assert E["baixa_divida_fabrica"][:2] == ("2.1.08", "3.5")


def test_implantacao_pelo_pl_nunca_dre(app_db):
    db = app_db.get_session(); ot, oid = "loja", 970; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "implantacao_credito_fabrica", 10000.0, ref="i:c")
    mc.registrar_evento(db, ot, oid, "implantacao_divida_fabrica", 50000.0, ref="i:d")
    assert _s(db, ot, oid, "1.1.08") == 10000.0
    assert _s(db, ot, oid, "2.1.08") == 50000.0
    # contrapartida no PL (3.5), DRE intocada (4.4.02 / 5.6.10 zerados)
    assert _s(db, ot, oid, "4.4.02") == 0.0 and _s(db, ot, oid, "5.6.10") == 0.0
    db.close()


def _seed_projeto_conferivel(app_db, seed, nome_proj=None):
    """Projeto da loja 1 com provisão de fábrica constituída (contrato) — pronto p/ conferência."""
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, seed["orcamento_l1_id"])
    nome = nome_proj or orc.projeto_id
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    mc.constituir_provisoes_fechamento(db, ot, oid, nome, {"custo_fabrica": 100000.0},
                                       ref_base="pf:" + nome)
    db.commit(); db.close()
    return nome, ot, oid


def test_exemplo_loja3_ciclo_completo_sem_sobra_falta(http_client_factory, seed, app_db):
    # spec §Exemplo fechado: contrato 100k → conferência com 5% custo + 10% consumir_saldo
    # → a pagar 104.500 / CMV 95.000 / dívida abatida 9.500 → matching → pagamento →
    # conciliação SEM sobra/falta (hoje os 9.500 virariam falta 5.6.10).
    nome, ot, oid = _seed_projeto_conferivel(app_db, seed)
    c = _login(http_client_factory, "dir_l1")

    # acordo de DÍVIDA da própria loja (implantação 50.000) + os dois ajustes
    st, body = c.post("/api/admin/acordos-fabrica",
                      {"descricao": "Dívida fábrica", "tipo": "divida",
                       "loja_titular_id": seed["loja1_id"], "valor": 50000.0})
    assert st == 200 and body["ok"], body
    acordo_id = body["acordo"]["id"]
    st, body = c.post("/api/admin/ajustes-fabrica",
                      {"loja_id": seed["loja1_id"], "tipo": "desconto", "pct": 5.0,
                       "tratamento": "custo", "descricao": "cashback"})
    assert st == 200, body
    st, body = c.post("/api/admin/ajustes-fabrica",
                      {"loja_id": seed["loja1_id"], "tipo": "acrescimo", "pct": 10.0,
                       "tratamento": "consumir_saldo", "acordo_id": acordo_id})
    assert st == 200, body

    # preview antes de aplicar
    st, body = c.get(f"/api/projetos/{nome}/conferencia/ajustes-preview?valor=100000")
    assert st == 200 and body["preview"]["a_pagar_final"] == 104500.0

    # conferência aplica (custo_fabrica_novo = 100.000, sem outros fornecedores)
    st, body = c.post(f"/api/projetos/{nome}/conferencia",
                      {"custo_fabrica_novo": 100000.0, "valor_outros_forn": 0,
                       "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"], body
    assert body["ajustes"]["a_pagar_final"] == 104500.0
    assert body["ajustes"]["custo_fabrica_final"] == 95000.0

    db = app_db.get_session()
    assert _s(db, ot, oid, "2.1.04.06") == 104500.0   # a pagar casa com a NF-e
    assert _s(db, ot, oid, "1.1.06.06") == 95000.0    # CMV futuro
    assert _s(db, ot, oid, "2.1.08") == 40500.0       # dívida abatida em 9.500
    # idempotência: repetir a conferência não duplica
    db.close()
    st, body = c.post(f"/api/projetos/{nome}/conferencia",
                      {"custo_fabrica_novo": 100000.0, "valor_outros_forn": 0,
                       "login": "dir_l1", "senha": "senha123"})
    assert st == 200
    db = app_db.get_session()
    assert _s(db, ot, oid, "2.1.04.06") == 104500.0
    # NF-e (matching pleno pelo saldo planejado) + pagamento à fábrica
    mc.reconhecer_despesas_nfe(db, ot, oid, nome, ref_base="match:" + nome)
    assert _s(db, ot, oid, "5.1.01") == 95000.0       # CMV reconhecido = 95.000
    mc.registrar_evento(db, ot, oid, "pagamento_fabrica", 104500.0, projeto_id=nome,
                        ref="pag:" + nome)
    # conciliação final: NADA sobra/falta na provisão de fábrica
    out = mc.conciliar_final(db, ot, oid, nome, ref_base="cf:" + nome)
    assert "2.1.04.06" not in out, out
    assert _s(db, ot, oid, "2.1.04.06") == 0.0
    db.commit(); db.close()


def _loja_avulsa(app_db, nome, codigo, login):
    """Loja SEM rede (owner próprio) + diretor — para exercitar o intercompany de verdade.
    Get-or-create (o banco do módulo é compartilhado entre os testes)."""
    db = app_db.get_session()
    lj = db.query(app_db.Loja).filter_by(codigo=codigo).first()
    if lj is None:
        lj = app_db.Loja(nome=nome, codigo=codigo)      # rede_id NULL → owner ("loja", id)
        db.add(lj); db.flush()
        from auth import perfil_store
        perfil_store.seed_perfis_loja(db, lj.id)
    if db.query(app_db.Usuario).filter_by(login=login).first() is None:
        u = app_db.Usuario(nome="Dir " + nome, login=login, nivel="master",
                           loja_id=lj.id, ativo=1)
        u.set_senha("senha123")
        db.add(u)
    db.commit()
    lid = lj.id
    db.close()
    from auth import perfis as _perfis
    _perfis.recarregar()
    return lid


def test_triangular_inspirium_verano_manual(http_client_factory, seed, app_db):
    # Revisão "Acordos Financeiros" (2026-07-21): SEM acerto automático/data-corte — cada loja
    # registra só o seu lado. Verano: crédito c/ a Fábrica (10.000) + conta corrente CREDORA da
    # Inspirium (nasce zerada; recebe por TRANSFERÊNCIA manual do crédito da fábrica). Inspirium:
    # dívida c/ a EMPRESA Verano (nasce zerada; ACUMULA sem cap a cada desconto consumido).
    insp = _loja_avulsa(app_db, "Inspirium", "INS", "dir_insp")
    ver = _loja_avulsa(app_db, "Verano", "VER", "dir_ver")
    su = _login(http_client_factory, "super")

    st, body = su.post("/api/admin/acordos-fabrica",
                       {"descricao": "Crédito Verano c/ Fábrica", "tipo": "credito",
                        "contraparte_tipo": "fabrica", "loja_titular_id": ver, "valor": 10000.0})
    assert st == 200, body
    ac_ver_fab = body["acordo"]["id"]
    st, body = su.post("/api/admin/acordos-fabrica",
                       {"descricao": "CC Inspirium (devedora)", "tipo": "credito",
                        "contraparte_tipo": "empresa", "contraparte_nome": "Inspirium",
                        "loja_titular_id": ver, "valor": 0})
    assert st == 200, body                      # conta corrente pode nascer zerada
    ac_ver_insp = body["acordo"]["id"]
    st, body = su.post("/api/admin/acordos-fabrica",
                       {"descricao": "CC Verano (credora)", "tipo": "divida",
                        "contraparte_tipo": "empresa", "contraparte_nome": "Verano",
                        "loja_titular_id": insp, "valor": 0})
    assert st == 200, body
    ac_insp_ver = body["acordo"]["id"]

    # ajustes: 3% Inspirium ACUMULA a dívida com a Verano (sem cap); 5% Verano consome o próprio crédito
    st, body = su.post("/api/admin/ajustes-fabrica",
                       {"loja_id": insp, "tipo": "desconto", "pct": 3.0,
                        "tratamento": "consumir_saldo", "acordo_id": ac_insp_ver})
    assert st == 200, body
    st, body = su.post("/api/admin/ajustes-fabrica",
                       {"loja_id": ver, "tipo": "desconto", "pct": 5.0,
                        "tratamento": "consumir_saldo", "acordo_id": ac_ver_fab})
    assert st == 200, body

    db = app_db.get_session()
    for lid, pnome in ((insp, "Proj_INS"), (ver, "Proj_VER")):
        db.add(app_db.Projeto(nome_safe=pnome, loja_id=lid, status="quente"))
        mc.constituir_provisoes_fechamento(db, "loja", lid, pnome,
                                           {"custo_fabrica": 100000.0}, ref_base="pf:" + pnome)
    db.commit(); db.close()

    # Inspirium confere: paga 97.000 à fábrica; CMV íntegro; dívida com a Verano ACUMULA 3.000
    ci = _login(http_client_factory, "dir_insp")
    st, body = ci.post("/api/projetos/Proj_INS/conferencia",
                       {"custo_fabrica_novo": 100000.0, "valor_outros_forn": 0,
                        "login": "dir_insp", "senha": "senha123"})
    assert st == 200 and body["ok"], body
    db = app_db.get_session()
    assert _s(db, "loja", insp, "2.1.04.06") == 97000.0
    assert _s(db, "loja", insp, "1.1.06.06") == 100000.0   # CMV íntegro
    assert _s(db, "loja", insp, "2.1.09") == 3000.0        # dívida com a Verano (só o razão dela)
    assert _s(db, "loja", ver, "1.1.08") == 10000.0        # Verano intocada
    db.close()
    su2 = _login(http_client_factory, "super")
    st, body = su2.get("/api/admin/acordos-fabrica")
    por_id = {a["id"]: a for a in body["acordos"]}
    assert por_id[ac_insp_ver]["saldos"]["contabil"] == 3000.0    # acumulou (sem cap)

    # Verano confere: consumo direto do próprio crédito (capado)
    cv = _login(http_client_factory, "dir_ver")
    st, body = cv.post("/api/projetos/Proj_VER/conferencia",
                       {"custo_fabrica_novo": 100000.0, "valor_outros_forn": 0,
                        "login": "dir_ver", "senha": "senha123"})
    assert st == 200 and body["ok"], body
    db = app_db.get_session()
    assert _s(db, "loja", ver, "2.1.04.06") == 95000.0
    assert _s(db, "loja", ver, "1.1.08") == 5000.0
    db.close()

    # Verano TRANSFERE 3.000 do crédito-fábrica p/ a conta corrente da Inspirium (registro manual)
    st, body = su2.post(f"/api/admin/acordos-fabrica/{ac_ver_fab}/movimento",
                        {"acao": "transferir", "valor": 3000.0,
                         "destino_acordo_id": ac_ver_insp})
    assert st == 200 and body["ok"], body
    db = app_db.get_session()
    assert _s(db, "loja", ver, "1.1.09") == 3000.0         # a receber da Inspirium
    assert _s(db, "loja", ver, "1.1.08") == 2000.0
    db.close()

    # liquidação em dinheiro: Inspirium PAGA (o seu lado); Verano RECEBE (o dela)
    st, body = su2.post(f"/api/admin/acordos-fabrica/{ac_insp_ver}/movimento",
                        {"acao": "pagar", "valor": 3000.0})
    assert st == 200 and body["valor"] == 3000.0
    st, body = su2.post(f"/api/admin/acordos-fabrica/{ac_ver_insp}/movimento",
                        {"acao": "receber", "valor": 3000.0})
    assert st == 200 and body["valor"] == 3000.0
    db = app_db.get_session()
    assert _s(db, "loja", insp, "2.1.09") == 0.0
    assert _s(db, "loja", ver, "1.1.09") == 0.0
    db.close()


def test_emprestimo_bancario_ciclo(http_client_factory, seed, app_db):
    # Revisão 2026-07-21: empréstimo como acordo financeiro — captação (dinheiro entra no
    # caixa), atualização de juros (5.5.02, despesa corrente LEGÍTIMA) e pagamento.
    lid = _loja_avulsa(app_db, "Loja Banco", "BNC", "dir_bnc")
    su = _login(http_client_factory, "super")
    st, body = su.post("/api/admin/acordos-fabrica",
                       {"descricao": "Empréstimo capital de giro", "tipo": "divida",
                        "contraparte_tipo": "banco", "contraparte_nome": "Banco Itaú",
                        "loja_titular_id": lid, "valor": 100000.0, "captacao": True})
    assert st == 200, body
    ac_id = body["acordo"]["id"]
    db = app_db.get_session()
    assert _s(db, "loja", lid, "1.1.01") == 100000.0       # dinheiro entrou no caixa
    assert _s(db, "loja", lid, "2.1.10") == 100000.0
    assert _s(db, "loja", lid, "3.5") == 0.0               # captação NÃO passa pelo PL
    db.close()

    st, body = su.post(f"/api/admin/acordos-fabrica/{ac_id}/movimento",
                       {"acao": "atualizar", "valor": 2000.0})
    assert st == 200 and body["saldos"]["contabil"] == 102000.0
    st, body = su.post(f"/api/admin/acordos-fabrica/{ac_id}/movimento",
                       {"acao": "pagar", "valor": 50000.0})
    assert st == 200 and body["saldos"]["contabil"] == 52000.0
    db = app_db.get_session()
    assert _s(db, "loja", lid, "2.1.10") == 52000.0
    assert _s(db, "loja", lid, "5.5.02") == 2000.0         # juros na DRE (correto p/ empréstimo)
    assert _s(db, "loja", lid, "1.1.01") == 50000.0        # 100k − 50k pagos
    # pagar acima do saldo é capado
    st, body = su.post(f"/api/admin/acordos-fabrica/{ac_id}/movimento",
                       {"acao": "pagar", "valor": 99999.0})
    assert st == 200 and body["valor"] == 52000.0
    assert body["saldos"]["contabil"] == 0.0
    db.close()


def test_desconto_por_periodo_vigencia(http_client_factory, seed, app_db):
    # Revisão 2026-07-21: desconto específico POR PERÍODO, sem crédito/dívida (tratamento=custo
    # com vigência) — fora da janela não aplica.
    lid = _loja_avulsa(app_db, "Loja Per", "PER", "dir_per")
    su = _login(http_client_factory, "super")
    st, body = su.post("/api/admin/ajustes-fabrica",
                       {"loja_id": lid, "tipo": "desconto", "pct": 4.0, "tratamento": "custo",
                        "descricao": "campanha", "vigencia_de": "2020-01-01",
                        "vigencia_ate": "2020-12-31"})
    assert st == 200, body           # janela no passado → não vigente hoje
    st, body = su.post("/api/admin/ajustes-fabrica",
                       {"loja_id": lid, "tipo": "desconto", "pct": 2.0, "tratamento": "custo",
                        "descricao": "vigente", "vigencia_de": "2020-01-01"})
    assert st == 200, body           # aberta até hoje → vigente
    db = app_db.get_session()
    db.add(app_db.Projeto(nome_safe="Proj_PER", loja_id=lid, status="quente"))
    mc.constituir_provisoes_fechamento(db, "loja", lid, "Proj_PER",
                                       {"custo_fabrica": 100000.0}, ref_base="pf:Proj_PER")
    db.commit(); db.close()
    cp = _login(http_client_factory, "dir_per")
    st, body = cp.get("/api/projetos/Proj_PER/conferencia/ajustes-preview?valor=100000")
    assert st == 200, body
    aps = body["preview"]["aplicacoes"]
    assert len(aps) == 1 and aps[0]["pct"] == 2.0          # só o vigente aplica
    assert body["preview"]["a_pagar_final"] == 98000.0


def test_cap_esgota_acordo_e_devolucao_repoe_saldo(http_client_factory, seed, app_db):
    # cap ao disponível + esgotamento + devolução devolvendo saldo ao acordo (spec, riscos)
    lid = _loja_avulsa(app_db, "Loja Cap", "CAP", "dir_cap")
    su = _login(http_client_factory, "super")
    st, body = su.post("/api/admin/acordos-fabrica",
                       {"descricao": "crédito curto", "tipo": "credito",
                        "loja_titular_id": lid, "valor": 1200.0})
    acordo_id = body["acordo"]["id"]
    st, body = su.post("/api/admin/ajustes-fabrica",
                       {"loja_id": lid, "tipo": "desconto", "pct": 5.0,
                        "tratamento": "consumir_saldo", "acordo_id": acordo_id})
    assert st == 200, body

    db = app_db.get_session()
    db.add(app_db.Projeto(nome_safe="Proj_CAP", loja_id=lid, status="quente"))
    mc.constituir_provisoes_fechamento(db, "loja", lid, "Proj_CAP",
                                       {"custo_fabrica": 100000.0}, ref_base="pf:Proj_CAP")
    db.commit(); db.close()

    cc = _login(http_client_factory, "dir_cap")
    st, body = cc.post("/api/projetos/Proj_CAP/conferencia",
                       {"custo_fabrica_novo": 100000.0, "valor_outros_forn": 0,
                        "login": "dir_cap", "senha": "senha123"})
    assert st == 200, body
    ap = body["ajustes"]["aplicacoes"][0]
    assert ap["valor"] == 1200.0 and ap["capado"] is True    # 5% seria 5.000; cap = 1.200
    db = app_db.get_session()
    assert _s(db, "loja", lid, "1.1.08") == 0.0
    ac = db.get(app_db.AcordoFabrica, acordo_id)
    assert ac.status == "esgotado"
    db.close()

    # devolução de 50%: metade do consumo volta ao acordo, que REATIVA
    st, body = su.post("/api/admin/acordos-fabrica", {})  # sanity: rota errada não interfere
    db = app_db.get_session()
    ot_l, own_l = "loja", lid
    from main import _reverter_aplicacoes_fabrica
    out = _reverter_aplicacoes_fabrica(db, ot_l, own_l, "Proj_CAP", 0.5, "dev:Proj_CAP:1")
    db.commit()
    assert out and out[0]["revertido"] == 600.0
    assert _s(db, "loja", lid, "1.1.08") == 600.0
    ac = db.get(app_db.AcordoFabrica, acordo_id)
    assert ac.status == "ativo"
    db.close()


def test_devolucao_total_com_ajuste_custo_zera_o_par(http_client_factory, seed, app_db):
    # QA Vera 🔴: devolver 100% com ajuste tratamento=custo deixava resíduo fantasma (o
    # devolver_venda genérico já reverte o par; a reversão de aplicações NÃO pode tocá-lo).
    lid = _loja_avulsa(app_db, "Loja Dev", "DVC", "dir_dvc")
    su = _login(http_client_factory, "super")
    st, body = su.post("/api/admin/ajustes-fabrica",
                       {"loja_id": lid, "tipo": "desconto", "pct": 5.0, "tratamento": "custo"})
    assert st == 200, body
    db = app_db.get_session()
    db.add(app_db.Projeto(nome_safe="Proj_DVC", loja_id=lid, status="quente"))
    mc.constituir_provisoes_fechamento(db, "loja", lid, "Proj_DVC",
                                       {"custo_fabrica": 100000.0}, ref_base="pf:Proj_DVC")
    db.commit(); db.close()
    cd = _login(http_client_factory, "dir_dvc")
    st, body = cd.post("/api/projetos/Proj_DVC/conferencia",
                       {"custo_fabrica_novo": 100000.0, "valor_outros_forn": 0,
                        "login": "dir_dvc", "senha": "senha123"})
    assert st == 200, body
    db = app_db.get_session()
    assert _s(db, "loja", lid, "2.1.04.06") == 95000.0
    # devolução TOTAL: genérico reverte o par; aplicações de custo NÃO re-entram
    mc.devolver_venda(db, "loja", lid, "Proj_DVC", 1.0, ref_base="dev:Proj_DVC:1")
    from main import _reverter_aplicacoes_fabrica
    out = _reverter_aplicacoes_fabrica(db, "loja", lid, "Proj_DVC", 1.0, "dev:Proj_DVC:1")
    db.commit()
    assert out == []                                        # nada de consumir_saldo a reverter
    assert _s(db, "loja", lid, "2.1.04.06") == 0.0          # sem resíduo fantasma
    assert _s(db, "loja", lid, "1.1.06.06") == 0.0
    db.close()


def test_reconferencia_com_pe_diferente_rebaseia_e_payload_bate(http_client_factory, seed, app_db):
    # QA Vera 🟠: reconferir com PE diferente congelava os ajustes no valor antigo e o payload
    # divergia do razão. Agora o delta rebaseia: razão == recalculado sobre o PE novo.
    lid = _loja_avulsa(app_db, "Loja Reb", "REB", "dir_reb")
    su = _login(http_client_factory, "super")
    st, body = su.post("/api/admin/acordos-fabrica",
                       {"descricao": "dívida", "tipo": "divida",
                        "loja_titular_id": lid, "valor": 50000.0})
    acordo_id = body["acordo"]["id"]
    su.post("/api/admin/ajustes-fabrica",
            {"loja_id": lid, "tipo": "desconto", "pct": 5.0, "tratamento": "custo"})
    su.post("/api/admin/ajustes-fabrica",
            {"loja_id": lid, "tipo": "acrescimo", "pct": 10.0,
             "tratamento": "consumir_saldo", "acordo_id": acordo_id})
    db = app_db.get_session()
    db.add(app_db.Projeto(nome_safe="Proj_REB", loja_id=lid, status="quente"))
    mc.constituir_provisoes_fechamento(db, "loja", lid, "Proj_REB",
                                       {"custo_fabrica": 100000.0}, ref_base="pf:Proj_REB")
    db.commit(); db.close()
    cr = _login(http_client_factory, "dir_reb")
    st, body = cr.post("/api/projetos/Proj_REB/conferencia",
                       {"custo_fabrica_novo": 100000.0, "valor_outros_forn": 0,
                        "login": "dir_reb", "senha": "senha123"})
    assert st == 200 and body["ajustes"]["a_pagar_final"] == 104500.0

    # PE corrigido para 98.000: recalculado = 98.000 − 4.900 + 9.310 = 102.410 / CMV 93.100
    st, body = cr.post("/api/projetos/Proj_REB/conferencia",
                       {"custo_fabrica_novo": 98000.0, "valor_outros_forn": 0,
                        "login": "dir_reb", "senha": "senha123"})
    assert st == 200, body
    assert body["ajustes"]["a_pagar_final"] == 102410.0
    assert body["ajustes"]["custo_fabrica_final"] == 93100.0
    db = app_db.get_session()
    assert _s(db, "loja", lid, "2.1.04.06") == 102410.0     # razão == payload
    assert _s(db, "loja", lid, "1.1.06.06") == 93100.0
    assert _s(db, "loja", lid, "2.1.08") == round(50000.0 - 9310.0, 2)   # dívida re-baseada
    db.close()


def test_soma_de_descontos_custo_acima_de_100_rejeitada(http_client_factory, seed, app_db):
    # QA Vera 🟡: dois recorrentes de custo somando >100% do conferido — barrado na criação
    lid = _loja_avulsa(app_db, "Loja Cem", "CEM", "dir_cem")
    su = _login(http_client_factory, "super")
    st, _ = su.post("/api/admin/ajustes-fabrica",
                    {"loja_id": lid, "tipo": "desconto", "pct": 60.0, "tratamento": "custo"})
    assert st == 200
    st, body = su.post("/api/admin/ajustes-fabrica",
                       {"loja_id": lid, "tipo": "desconto", "pct": 50.0, "tratamento": "custo"})
    assert st == 400 and "100" in (body.get("erro") or "")


def test_movimento_reativa_esgotado_e_nonce_idempotente(http_client_factory, seed, app_db):
    # QA Vera: (1) juros/transferência devolvem saldo a acordo esgotado → REATIVA;
    # (2) nonce torna o movimento idempotente (duplo clique não lança juros 2×).
    lid = _loja_avulsa(app_db, "Loja Reat", "REA", "dir_rea")
    su = _login(http_client_factory, "super")
    st, body = su.post("/api/admin/acordos-fabrica",
                       {"descricao": "empréstimo", "tipo": "divida", "contraparte_tipo": "banco",
                        "loja_titular_id": lid, "valor": 1000.0, "captacao": True})
    ac_id = body["acordo"]["id"]
    st, body = su.post(f"/api/admin/acordos-fabrica/{ac_id}/movimento",
                       {"acao": "pagar", "valor": 1000.0})
    assert st == 200 and body["saldos"]["contabil"] == 0.0
    db = app_db.get_session()
    assert db.get(app_db.AcordoFabrica, ac_id).status == "esgotado"
    db.close()
    # juros devolvem saldo → acordo REATIVA
    st, body = su.post(f"/api/admin/acordos-fabrica/{ac_id}/movimento",
                       {"acao": "atualizar", "valor": 500.0, "nonce": "n1"})
    assert st == 200 and body["saldos"]["contabil"] == 500.0
    db = app_db.get_session()
    assert db.get(app_db.AcordoFabrica, ac_id).status == "ativo"
    db.close()
    # nonce repetido → recusado (sem duplicar os juros)
    st, body = su.post(f"/api/admin/acordos-fabrica/{ac_id}/movimento",
                       {"acao": "atualizar", "valor": 500.0, "nonce": "n1"})
    assert st == 400 and "repeti" in (body.get("erro") or "").lower()
    db = app_db.get_session()
    assert _s(db, "loja", lid, "2.1.10") == 500.0          # só 1× lançado
    db.close()
