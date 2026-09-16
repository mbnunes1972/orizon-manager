# -*- coding: utf-8 -*-
"""PORTÃO (16/09) — custo repassado não é desconto: `Val_Liq_Portao` / `Desc_Tot_Portao`.

Pedido (Marcelo, 16/09): "com o toggle 'Incluir custos adicionais?' LIGADO, acrescentar custo de
viagem não pode mover o percentual de desconto verificado pelo portão de autorização; com o
toggle DESLIGADO, o comportamento de hoje se mantém."

Raiz (regra dos irmãos — mesmo defeito em dois lugares): `main._maior_composto_com_parametros_pct`
(por ambiente) e `Desc_Tot` (agregado, teto de 35% da tela) liam `Val_Liq`, que no REPASSA já
carrega a perda real `(viagem+brinde) × (1 − fator_desc)` (ACHADO-63, aceita e testada em
tests/test_achado63_custos_acompanham_desconto.py). Essa perda é dinheiro da loja, não desconto
a mais pro cliente — lida como desconto, inflava o percentual do portão.

Álgebra (por ambiente, repassa): vava = T + R·f, com T = termo_arqfid·fator_desc, R = via+bri,
f = fator_desc; base_custos = R·f ⇒ pro_amb = pct_fid·T e com_amb = pct_arq·(T − pro_amb) — nenhum
dos dois depende de R. Val_Liq = T + R·f − com − pro − R = (T − com − pro) − R·(1−f).
Val_Liq_Portao = Val_Liq + R·(1−f) = T − com − pro = o Val_Liq que existiria SEM viagem/brinde.
Absorve: Val_Liq_Portao == Val_Liq (nada muda). Custo especial só existe no agregado: soma de
volta `cust_esp × d_orc`.

Todos os números abaixo são derivados à mão (aritmética no comentário), não copiados do motor."""
import json

import mod_negociacao as mn


def _ap(a, b, tol=0.02):
    assert abs(a - b) <= tol, f"{a} != {b}"


_AMB = [{"VBVA": 10000.0, "CFA": 4000.0, "desc_amb_pct": 0}]


# ── Motor puro: viagem repassada não move o portão, em qualquer desconto ───────────────────────
# mercadoria=10.000, viagem=1.000 (1 ambiente → entra cheia), sem arq/fid.
#   d=0%:  Val_Liq = 10.000 − 0 = 10.000,00; vazamento = 1.000×0 = 0 → Portao = 10.000,00 → 0%
#   d=30%: Val_Liq = 10.000×0,70 − 1.000×0,30 = 6.700,00 (ACHADO-63, perda real de 300,00)
#          vazamento = 1.000×(1−0,70) = 300,00 → Portao = 7.000,00 = 10.000×0,70 → 30,00% EXATO
#          (o portão antigo lia 1 − 6.700/10.000 = 33,00% — 3 pontos de "desconto" que ninguém deu)

def test_repassa_viagem_nao_move_portao_em_30pct():
    p_com = {"incluir_custos": True, "fora_da_sede": True, "custo_viagem": 1000.0}
    p_sem = {"incluir_custos": True}
    d_com = mn.calcular_orcamento(_AMB, p_com, 30.0)
    d_sem = mn.calcular_orcamento(_AMB, p_sem, 30.0)
    a_com, a_sem = d_com["ambientes"][0], d_sem["ambientes"][0]
    _ap(a_com["Val_Liq"], 6700.0)            # contábil: perda real de 300,00 — INTOCADO
    _ap(a_com["Val_Liq_Portao"], 7000.0)     # portão: idêntico ao cenário sem viagem
    _ap(a_sem["Val_Liq_Portao"], 7000.0)
    _ap(a_sem["Val_Liq"], 7000.0)            # sem viagem: os dois campos coincidem
    pct_com = round((1 - a_com["Val_Liq_Portao"] / a_com["VBVA"]) * 100, 2)
    pct_sem = round((1 - a_sem["Val_Liq_Portao"] / a_sem["VBVA"]) * 100, 2)
    assert pct_com == pct_sem == 30.0, (pct_com, pct_sem)
    # agregado: mesma coisa — Desc_Tot (contábil) sobe, Desc_Tot_Portao não
    _ap(d_com["Desc_Tot"], 0.33, tol=0.0001)
    _ap(d_com["Desc_Tot_Portao"], 0.30, tol=0.0001)
    _ap(d_sem["Desc_Tot_Portao"], 0.30, tol=0.0001)
    _ap(d_com["Val_Liq_Portao"], 7000.0)


def test_repassa_viagem_em_0pct_portao_e_zero():
    p = {"incluir_custos": True, "fora_da_sede": True, "custo_viagem": 1000.0}
    d = mn.calcular_orcamento(_AMB, p, 0.0)
    _ap(d["ambientes"][0]["Val_Liq_Portao"], 10000.0)
    _ap(d["Desc_Tot_Portao"], 0.0, tol=0.0001)
    _ap(d["Desc_Tot"], 0.0, tol=0.0001)     # a d=0 não há vazamento — os dois coincidem


# ── Absorve (toggle desligado): comportamento de hoje, os campos novos são cópias dos antigos ──
# mercadoria=10.000, viagem=1.000, d=30%: vava=7.000; Val_Liq = 7.000 − 1.000 = 6.000 (custo 100%
# da loja, e HOJE o portão conta isso como 40% — mantido). Val_Liq_Portao == Val_Liq == 6.000.

def test_absorve_nada_muda_campos_novos_iguais_aos_antigos():
    p = {"incluir_custos": False, "fora_da_sede": True, "custo_viagem": 1000.0,
         "brinde_ativo": True, "brinde": 500.0,
         "custo_especial_ativo": True, "custo_especial": 800.0}
    for d_pct in (0.0, 10.0, 30.0):
        d = mn.calcular_orcamento(_AMB, p, d_pct)
        a = d["ambientes"][0]
        assert a["Val_Liq_Portao"] == a["Val_Liq"], d_pct
        assert d["Val_Liq_Portao"] == d["Val_Liq"], d_pct
        assert d["Desc_Tot_Portao"] == d["Desc_Tot"], d_pct
    d30 = mn.calcular_orcamento(_AMB, p, 30.0)
    _ap(d30["ambientes"][0]["Val_Liq_Portao"], 7000.0 - 1000.0 - 500.0)   # 5.500 (via+bri cheios)
    _ap(d30["Val_Liq_Portao"], 7000.0 - 1000.0 - 500.0 - 800.0)           # 4.700 (+cust_esp)


# ── ACHADO-42 preservado: comissão/fidelidade continuam contando no portão ────────────────────
# Absorve, sem viagem: mercadoria=10.000, arq=30%, d=0: com = 3.000 → Portao = 7.000 → 30%
# (é o número que test_aceite_achado42_portao usa pra compor 51% com o desconto de 30%).
# Repassa (gross-up), arq=10%, d=30%: T = (10.000/0,90)×0,70 = 7.777,78; com = 777,78;
# Portao = Val_Liq = 7.000,00 → 30% (o gross-up já faz o cliente pagar a comissão — inalterado).

def test_comissao_continua_contando_no_portao_absorve_e_repassa():
    d_abs = mn.calcular_orcamento(_AMB, {"incluir_custos": False, "comissao_arq_ativa": True,
                                         "comissao_arq_pct": 30.0}, 0.0)
    _ap(d_abs["ambientes"][0]["Val_Liq_Portao"], 7000.0)
    _ap(d_abs["Desc_Tot_Portao"], 0.30, tol=0.0001)
    d_rep = mn.calcular_orcamento(_AMB, {"incluir_custos": True, "comissao_arq_ativa": True,
                                         "comissao_arq_pct": 10.0}, 30.0)
    _ap(d_rep["ambientes"][0]["Val_Liq"], 7000.0)
    _ap(d_rep["ambientes"][0]["Val_Liq_Portao"], 7000.0)


# ── Combinado (mesmo cenário do test_combinado_identidade_e_perda_825): a prova da fórmula é a
# IGUALDADE entre `Val_Liq_Portao` do cenário COM viagem/brinde/cust_esp e o `Val_Liq` do
# cenário SEM (mesma mercadoria, mesmos arq/fid): 15.000,00, por ambiente e no agregado.
#   vazamento_amb = (1.500+1.000)×0,25 = 625,00; vazamento cust_esp = 800×0,25 = 200,00
#   Val_Liq_A = 14.175,00 → Portao = 14.175 + 625 + 200 = 15.000,00 == Val_Liq_B

def test_combinado_portao_com_custos_igual_val_liq_sem_custos():
    amb = [{"VBVA": 20000.0, "CFA": 8000.0, "desc_amb_pct": 0}]
    p_com = {"incluir_custos": True, "fora_da_sede": True, "custo_viagem": 1500.0,
             "brinde_ativo": True, "brinde": 1000.0,
             "custo_especial_ativo": True, "custo_especial": 800.0,
             "comissao_arq_ativa": True, "comissao_arq_pct": 5.0,
             "fidelidade_ativa": True, "fidelidade_pct": 2.0}
    p_sem = {"incluir_custos": True, "comissao_arq_ativa": True, "comissao_arq_pct": 5.0,
             "fidelidade_ativa": True, "fidelidade_pct": 2.0}
    d_com = mn.calcular_orcamento(amb, p_com, 25.0)
    d_sem = mn.calcular_orcamento(amb, p_sem, 25.0)
    _ap(d_com["Val_Liq"], 14175.0)                       # contábil, perda de 825 — intocado
    # por ambiente: liq_amb = 14.175 + 200 (cust_esp nunca passa pelo ambiente) = 14.375;
    # + vazamento de viagem/brinde (625) = 15.000,00
    _ap(d_com["ambientes"][0]["Val_Liq"], 14375.0)
    _ap(d_com["ambientes"][0]["Val_Liq_Portao"], 15000.0)
    _ap(d_com["ambientes"][0]["Val_Liq_Portao"], d_sem["ambientes"][0]["Val_Liq"])
    # agregado: viagem/brinde (625) + cust_esp (200)
    _ap(d_com["Val_Liq_Portao"], 15000.0)
    _ap(d_com["Val_Liq_Portao"], d_sem["Val_Liq"])
    _ap(d_com["Desc_Tot_Portao"], d_sem["Desc_Tot"], tol=0.0001)
    assert d_com["Desc_Tot"] > d_com["Desc_Tot_Portao"]   # o contábil continua mostrando a perda


# ── Custo especial (só agregado): mercadoria=10.000, cust_esp=1.000, d=30% ────────────────────
#   Val_Liq = 7.000 + 700 − 1.000 = 6.700 → Desc_Tot = 33%; Portao = 6.700 + 1.000×0,30 = 7.000 → 30%

def test_custo_especial_repassado_nao_move_portao_agregado():
    p = {"incluir_custos": True, "custo_especial_ativo": True, "custo_especial": 1000.0}
    d = mn.calcular_orcamento(_AMB, p, 30.0)
    _ap(d["Val_Liq"], 6700.0)
    _ap(d["Val_Liq_Portao"], 7000.0)
    _ap(d["Desc_Tot"], 0.33, tol=0.0001)
    _ap(d["Desc_Tot_Portao"], 0.30, tol=0.0001)
    _ap(d["ambientes"][0]["Val_Liq_Portao"], 7000.0)   # ambiente nem vê o cust_esp


# ── Desconto por ambiente: o vazamento usa o fator DESTE ambiente ─────────────────────────────
# amb1 VBVA=12.000 d_amb=0 (f=0,75); amb2 VBVA=8.000 d_amb=10% (f=0,675); viagem=2.000 rateada
# por VBVA (den_via=VBVO=20.000): via1=1.200, via2=800. Sem arq/fid.
#   amb1: Val_Liq = (12.000+1.200)×0,75 − 1.200 = 9.900 − 1.200 = 8.700; Portao = 12.000×0,75 = 9.000
#   amb2: Val_Liq = (8.000+800)×0,675 − 800 = 5.940 − 800 = 5.140;      Portao = 8.000×0,675 = 5.400
#   portão por ambiente = 25,00% e 32,50% (= 1 − 0,675) — puro desconto, viagem invisível.

def test_desconto_por_ambiente_portao_usa_fator_do_proprio_ambiente():
    ambs = [{"VBVA": 12000.0, "CFA": 5000.0, "desc_amb_pct": 0.0},
            {"VBVA": 8000.0, "CFA": 3000.0, "desc_amb_pct": 10.0}]
    p = {"incluir_custos": True, "fora_da_sede": True, "custo_viagem": 2000.0}
    d = mn.calcular_orcamento(ambs, p, 25.0)
    a1, a2 = d["ambientes"]
    _ap(a1["Val_Liq"], 8700.0); _ap(a1["Val_Liq_Portao"], 9000.0)
    _ap(a2["Val_Liq"], 5140.0); _ap(a2["Val_Liq_Portao"], 5400.0)
    assert round((1 - a1["Val_Liq_Portao"] / 12000.0) * 100, 2) == 25.0
    assert round((1 - a2["Val_Liq_Portao"] / 8000.0) * 100, 2) == 32.5
    _ap(d["Val_Liq_Portao"], 9000.0 + 5400.0)


# ── main._maior_composto_com_parametros_pct: portão lê Val_Liq_Portao, corte duro lê Val_Liq ──

def _preparar_projeto(app_db, seed, params, vbva=10000.0, cfa=4000.0):
    """Ambiente único, orçamento sem desconto, parametros_json = `params` (controla o toggle)."""
    db = app_db.get_session()
    oid = seed["orcamento_l1_id"]
    orc = db.get(app_db.Orcamento, oid)
    orc.desconto_pct = 0.0
    for lk in db.query(app_db.OrcamentoAmbiente).filter_by(orcamento_id=oid).all():
        db.delete(lk)
    db.flush()
    # viagem é rateada pelo pool do PROJETO (`vbvo_proj` em _negociacao_breakdown) — um pool
    # residual de teste anterior dividiria a viagem e mudaria os números derivados à mão.
    for pa_old in db.query(app_db.PoolAmbiente).filter_by(projeto_id=seed["projeto_l1"]).all():
        db.delete(pa_old)
    db.flush()
    pa = app_db.PoolAmbiente(projeto_id=seed["projeto_l1"], nome="portao_rep", nome_exibicao="Cozinha",
                             xml_path="p", ambientes_json="[]", order_total=cfa, budget_total=vbva)
    db.add(pa); db.flush()
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=1))
    proj = db.get(app_db.Projeto, seed["projeto_l1"])
    proj.parametros_json = json.dumps(params) if params is not None else None
    db.commit()
    db.close()
    return oid


_VIAGEM = {"fora_da_sede": True, "custo_viagem": 1000.0}


def test_maior_composto_repassa_viagem_pct_e_so_o_desconto_e_menor_val_liq_e_o_real(seed, app_db):
    """d=30%, viagem 1.000 repassada: pct do portão = 30,00 (não 33,00); menor_val_liq = 6.700,00
    (o Val_Liq REAL, com a perda — corte duro de margem negativa segue lendo dinheiro)."""
    import main as _main
    oid = _preparar_projeto(app_db, seed, {"incluir_custos": True, **_VIAGEM})
    db = app_db.get_session()
    try:
        pct, menor = _main._maior_composto_com_parametros_pct(
            db, seed["projeto_l1"], orc_id_alvo=oid, desconto_pct_override=30.0)
    finally:
        db.close()
    assert pct == 30.0, pct
    _ap(menor, 6700.0)


def test_maior_composto_absorve_viagem_comportamento_de_hoje(seed, app_db):
    """Toggle desligado: viagem é 100% da loja e o portão continua contando — 1 − 6.000/10.000 = 40%."""
    import main as _main
    oid = _preparar_projeto(app_db, seed, {"incluir_custos": False, **_VIAGEM})
    db = app_db.get_session()
    try:
        pct, menor = _main._maior_composto_com_parametros_pct(
            db, seed["projeto_l1"], orc_id_alvo=oid, desconto_pct_override=30.0)
    finally:
        db.close()
    assert pct == 40.0, pct
    _ap(menor, 6000.0)


# ── Ponta a ponta (/margens): operador com limite 10% ─────────────────────────────────────────

def _login(f, who):
    c = f()
    c.login(who, "senha123")
    assert c.cookie
    return c


def test_margens_repassa_viagem_desconto_no_limite_passa_sem_autorizacao(http_client_factory, seed, app_db):
    """cons_l1 (limite 10%) pede 10% com viagem 1.000 REPASSADA: portão = 10,00 → 200.
    (Antes: 1 − (9.000 − 100)/10.000 = 11,00% > 10 → pedia senha de gerente por causa da viagem.)"""
    oid = _preparar_projeto(app_db, seed, {"incluir_custos": True, **_VIAGEM})
    c = _login(http_client_factory, "cons_l1")
    st, body = c.post(f"/api/orcamentos/{oid}/margens", {"desconto_pct": 10})
    assert st == 200 and body["ok"] is True, body
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    assert (orc.desconto_pct or 0) == 10
    db.close()


def test_margens_absorve_viagem_continua_exigindo_autorizacao(http_client_factory, seed, app_db):
    """Mesmo pedido com a viagem ABSORVIDA: 1 − (9.000 − 1.000)/10.000 = 20% > 10 → 403, como hoje."""
    oid = _preparar_projeto(app_db, seed, {"incluir_custos": False, **_VIAGEM})
    c = _login(http_client_factory, "cons_l1")
    st, body = c.post(f"/api/orcamentos/{oid}/margens", {"desconto_pct": 10})
    assert st == 403, body
    assert body["requer_autorizacao"] is True
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    assert (orc.desconto_pct or 0) != 10
    db.close()
