from datetime import datetime
import mod_folha
import mod_contabil as mc
import mod_provisoes


def _cfg_pct(pct):
    cfg = mod_provisoes.config_financeira_default()
    cfg["comissao_vendas"]["faixas_comissao"] = [{"venda_ate": None, "pct": pct}]
    return cfg


def test_calcular_folha_fixa_mais_variavel(seed, app_db):
    db = app_db.get_session()
    u = db.query(app_db.Usuario).filter_by(login="cons_l1").first()   # consultor loja1
    loja = u.loja_id
    f = app_db.Funcionario(loja_id=loja, nome="Vend", remuneracao_tipo="fixa_variavel",
                           remuneracao_fixa=2000.0, usuario_id=u.id, status="ativo")
    db.add(f); db.flush()
    # venda fechada no período, atribuída ao consultor, com orçamento (valor líquido)
    db.add(app_db.Projeto(nome_safe="PFolha", loja_id=loja, criado_por_id=u.id,
                          status="fechado", status_at=datetime(2026, 7, 15)))
    db.add(app_db.Orcamento(projeto_id="PFolha", nome="O", ordem=1, loja_id=loja, valor_liquido=10000.0))
    db.commit()
    c = mod_folha.calcular_folha(db, loja, f, "2026-07", _cfg_pct(3.0))
    assert c["parte_fixa"] == 2000.0
    assert c["vendas_liq"] == 10000.0
    assert c["faixa_pct"] == 3.0
    assert c["parte_variavel"] == 300.0     # 10000 × 3%
    assert c["total"] == 2300.0
    # venda de OUTRO mês não conta
    c2 = mod_folha.calcular_folha(db, loja, f, "2026-08", _cfg_pct(3.0))
    assert c2["vendas_liq"] == 0.0 and c2["parte_variavel"] == 0.0 and c2["total"] == 2000.0
    db.close()


def test_gerar_folha_um_por_funcionario_ativo_idempotente(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id   # loja2: isolada de outros testes
    fa = app_db.Funcionario(loja_id=loja, nome="A", remuneracao_tipo="fixa", remuneracao_fixa=1500.0, status="ativo")
    fb = app_db.Funcionario(loja_id=loja, nome="B", remuneracao_tipo="fixa", remuneracao_fixa=1000.0, status="inativo")
    db.add(fa); db.add(fb); db.commit()
    mod_folha.gerar_folha(db, loja, "2026-07", _cfg_pct(0.0)); db.commit()
    regs = {r.funcionario_id: r for r in
            db.query(app_db.FolhaPagamento).filter_by(loja_id=loja, competencia="2026-07").all()}
    assert fa.id in regs and regs[fa.id].parte_fixa == 1500.0        # ativo entra
    assert fb.id not in regs                                          # inativo não entra
    mod_folha.gerar_folha(db, loja, "2026-07", _cfg_pct(0.0)); db.commit()
    n = db.query(app_db.FolhaPagamento).filter_by(loja_id=loja, competencia="2026-07", funcionario_id=fa.id).count()
    assert n == 1  # idempotente
    db.close()


def test_pagar_posta_nas_contas_5_3(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 91)
    # Funcionario.loja_id / FolhaPagamento.loja_id são FK reais (lojas.id) — cria a loja de
    # verdade em vez do literal fabricado `1` (91 acima é só o owner_id do plano de contas,
    # sem FK). Não precisa coincidir com o id da loja.
    loja = app_db.Loja(nome="Loja Folha Pagar")
    db.add(loja); db.flush()
    f = app_db.Funcionario(loja_id=loja.id, nome="X", remuneracao_tipo="fixa_variavel", status="ativo", pix="x@pix")
    db.add(f); db.flush()
    reg = app_db.FolhaPagamento(loja_id=loja.id, funcionario_id=f.id, competencia="2026-07",
                                parte_fixa=2000.0, parte_variavel=300.0, total=2300.0, status="aberta")
    db.add(reg); db.flush()
    mod_folha.pagar(db, "loja", 91, reg)

    def saldo(cod):
        c = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=91, codigo=cod).first()
        return mc.saldo_conta(db, "loja", 91, c.id) if c else 0.0
    assert saldo("5.3.06") == 2000.0    # Salários de Vendas (parte fixa)
    assert saldo("5.3.01") == 300.0     # Comissão de Vendedor (parte variável)
    assert reg.status == "paga"
    mod_folha.pagar(db, "loja", 91, reg)   # idempotente
    assert saldo("5.3.01") == 300.0
    assert mod_folha.serialize(db, reg)["pagamento"] == "PIX: x@pix"   # usa PIX cadastrado
    db.close()


# ── HTTP: geração e listagem via endpoints ───────────────────────────────────
def test_folha_endpoints(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post("/api/funcionarios", {"nome": "Fixo", "remuneracao_tipo": "fixa", "remuneracao_fixa": 1800})
    st, d = c.post("/api/folha/gerar", {"competencia": "2026-07"})
    assert st == 200, d
    assert any(x["funcionario"] == "Fixo" and x["parte_fixa"] == 1800 for x in d["folha"]["itens"])
    st2, d2 = c.get("/api/folha?competencia=2026-07")
    assert st2 == 200 and d2["folha"]["total_fixa"] >= 1800
