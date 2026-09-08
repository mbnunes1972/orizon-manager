# -*- coding: utf-8 -*-
"""F2-42 Rodada 2 (docs/db/TAREFA_F2_42_FONTE_UNICA_E_INTERFACE.md) — a causa da divergência
medida na Rodada 1 deixou de ser hipótese: `mod_negociacao.py:80-81` rateia VIAGEM proporcional
ao bruto do ambiente (a proporção reproduz exato) mas BRINDE em partes IGUAIS (uma parcela FIXA
que a proporção antiga multiplicava junto com a mercadoria — a divergência inteira). Decisão do
Marcelo: o MOTOR é a fonte OFICIAL do que é cobrado; a proporção (`valor_complemento_por_fator`)
virou sombra/fallback.

Álgebra (do próprio pacote): VAVA_i = k·VBVA_i + F. A proporção calcula k·VBVA_pe +
F·(VBVA_pe/VBVA_ct); o motor calcula k·VBVA_pe + F. divergência = F × (VBVA_pe/VBVA_ct − 1)."""
import json

import main
from tests.test_complemento_pe_e2e import _login, _setup, _upsert_compl


def _seed_projeto_com_params(app_db, seed, params, budgets_orders):
    """Contrato assinado com N ambientes reais, parâmetros de negociação CONTROLADOS (Part B
    precisa isolar viagem/brinde/custo especial um de cada vez). Devolve (nome, oid, [pids])."""
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    orc = db.get(main.Orcamento, oid)
    nome = orc.projeto_id
    orc.desconto_pct = 0.0   # explícito — o teste 3 deriva F assumindo d_orc=0
    proj = db.query(main.Projeto).filter_by(nome_safe=nome).first()
    proj.parametros_json = json.dumps(params)
    pids = []
    for i, (budget, order) in enumerate(budgets_orders):
        pa = main.PoolAmbiente(nome="PB%d" % i, nome_exibicao="PB%d" % i,
                               xml_path="fake/pb%d.xml" % i, ambientes_json="{}",
                               projeto_id=nome, budget_total=budget, order_total=order)
        db.add(pa); db.flush()
        db.add(main.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=i + 1))
        pids.append(pa.id)
    db.commit()
    db.close()
    return nome, oid, pids


def _divergencias(app_db, nome, oid, pids, vendas_pe):
    """Roda baseline + override (mesma disciplina de `_complemento_diferencas`) e devolve
    {pid: (vava_proporcao_equivalente_via_motor_pe, vava_motor, vava_contratado)} — usado pelos
    testes de propriedade da Part B, que comparam DIRETO contra o motor (fonte da verdade),
    sem depender de `_complemento_diferencas` (que já embute a decisão que estamos provando)."""
    db = app_db.get_session()
    try:
        orc = db.get(main.Orcamento, oid)
        d_base = main._negociacao_breakdown(orc, db)
        d_over = main._negociacao_breakdown(orc, db, vbva_override=vendas_pe)
        vava_ct = {a["id"]: a["VAVA"] for a in d_base["ambientes"]}
        vava_motor = {a["id"]: a["VAVA"] for a in d_over["ambientes"]}
        return vava_ct, vava_motor
    finally:
        db.close()


def test_partb_1_so_percentuais_divergencia_exatamente_zero(app_db, seed):
    """Part B, teste 1: contrato só com rubricas percentuais (comissão arq/fid), brinde=0,
    viagem=0 → divergência entre as duas fórmulas EXATAMENTE zero (nada fixo pra distorcer)."""
    params = {"incluir_custos": True, "comissao_arq_ativa": True, "comissao_arq_pct": 10.0,
             "fidelidade_ativa": True, "fidelidade_pct": 5.0, "carga_trib": 0.0}
    nome, oid, (pid_a, pid_b) = _seed_projeto_com_params(
        app_db, seed, params, [(80000.0, 30000.0), (40000.0, 16000.0)])
    vendas_pe = {pid_a: 95000.0, pid_b: 36000.0}
    vava_ct, vava_motor = _divergencias(app_db, nome, oid, [pid_a, pid_b], vendas_pe)

    import mod_conciliacao_pe as _mconc
    for pid, venda in vendas_pe.items():
        va_proporcao = _mconc.valor_complemento_por_fator(
            valor_venda_pe=venda, vava_contratado=vava_ct[pid],
            vbva_contratado={pid_a: 80000.0, pid_b: 40000.0}[pid])
        divergencia = round(va_proporcao - vava_motor[pid], 2)
        assert abs(divergencia) < 0.02, (pid, va_proporcao, vava_motor[pid], divergencia)


def test_partb_2_com_viagem_proporcional_divergencia_zero(app_db, seed):
    """Part B, teste 2: mesmo contrato + VIAGEM > 0, brinde = 0 → divergência ainda EXATAMENTE
    zero (viagem é rateada proporcional ao bruto — a proporção reproduz exato)."""
    params = {"incluir_custos": True, "comissao_arq_ativa": True, "comissao_arq_pct": 10.0,
             "fidelidade_ativa": True, "fidelidade_pct": 5.0,
             "fora_da_sede": True, "custo_viagem": 2000.0, "carga_trib": 0.0}
    nome, oid, (pid_a, pid_b) = _seed_projeto_com_params(
        app_db, seed, params, [(80000.0, 30000.0), (40000.0, 16000.0)])
    vendas_pe = {pid_a: 95000.0, pid_b: 36000.0}
    vava_ct, vava_motor = _divergencias(app_db, nome, oid, [pid_a, pid_b], vendas_pe)

    import mod_conciliacao_pe as _mconc
    for pid, venda in vendas_pe.items():
        va_proporcao = _mconc.valor_complemento_por_fator(
            valor_venda_pe=venda, vava_contratado=vava_ct[pid],
            vbva_contratado={pid_a: 80000.0, pid_b: 40000.0}[pid])
        divergencia = round(va_proporcao - vava_motor[pid], 2)
        assert abs(divergencia) < 0.02, (pid, va_proporcao, vava_motor[pid], divergencia)


def test_partb_3_com_brinde_divergencia_bate_com_a_formula_fechada(app_db, seed):
    """Part B, teste 3 — O TESTE QUE PROVA A CAUSA: mesmo contrato + BRINDE > 0 → divergência
    DIFERENTE de zero, e igual a (brinde/n) × fator_desc × (VBVA_pe/VBVA_ct − 1) por ambiente,
    dentro do arredondamento de centavos. n = contagem de PoolAmbiente do PROJETO (não só os
    vinculados a este orçamento — `_negociacao_breakdown` usa `n_total_proj`), medida ao vivo
    pra não depender de nenhum teste anterior ter deixado ambientes soltos no mesmo projeto."""
    d_orc_pct = 0.0
    brinde = 500.0
    params = {"incluir_custos": True, "comissao_arq_ativa": True, "comissao_arq_pct": 10.0,
             "fidelidade_ativa": True, "fidelidade_pct": 5.0,
             "brinde_ativo": True, "brinde": brinde, "carga_trib": 0.0}
    nome, oid, (pid_a, pid_b) = _seed_projeto_com_params(
        app_db, seed, params, [(80000.0, 30000.0), (40000.0, 16000.0)])
    vendas_pe = {pid_a: 95000.0, pid_b: 36000.0}
    vava_ct, vava_motor = _divergencias(app_db, nome, oid, [pid_a, pid_b], vendas_pe)

    db = app_db.get_session()
    try:
        n_total_proj = db.query(main.PoolAmbiente).filter_by(projeto_id=nome).count()
    finally:
        db.close()
    fator_desc = 1 - d_orc_pct / 100.0
    F = fator_desc * brinde / n_total_proj

    import mod_conciliacao_pe as _mconc
    vbva_ct_map = {pid_a: 80000.0, pid_b: 40000.0}
    algum_nao_zero = False
    for pid, venda in vendas_pe.items():
        va_proporcao = _mconc.valor_complemento_por_fator(
            valor_venda_pe=venda, vava_contratado=vava_ct[pid], vbva_contratado=vbva_ct_map[pid])
        divergencia = round(va_proporcao - vava_motor[pid], 2)
        esperado = round(F * (venda / vbva_ct_map[pid] - 1), 2)
        assert abs(divergencia - esperado) < 0.03, (
            "divergência não bate com a fórmula fechada F×(VBVA_pe/VBVA_ct−1) — pid=%r "
            "divergencia=%.2f esperado=%.2f F=%.4f" % (pid, divergencia, esperado, F))
        if abs(divergencia) > 0.01:
            algum_nao_zero = True
    assert algum_nao_zero, "com brinde>0 e VBVA mudando, a divergência tem que ser NÃO-zero"


def test_partb_4_custo_especial_nao_e_rateado_por_ambiente_divergencia_zero(app_db, seed):
    """Part B, teste 4: Custo Especial > 0, brinde = 0 → divergência zero (ele é linha do
    orçamento, não rateado nos ambientes — não pode causar divergência por ambiente,
    mod_negociacao.py:130 e docstring de `_complemento_diferencas`)."""
    params = {"incluir_custos": True, "comissao_arq_ativa": True, "comissao_arq_pct": 10.0,
             "custo_especial_ativo": True, "custo_especial": 1000.0, "carga_trib": 0.0}
    nome, oid, (pid_a, pid_b) = _seed_projeto_com_params(
        app_db, seed, params, [(80000.0, 30000.0), (40000.0, 16000.0)])
    vendas_pe = {pid_a: 95000.0, pid_b: 36000.0}
    vava_ct, vava_motor = _divergencias(app_db, nome, oid, [pid_a, pid_b], vendas_pe)

    import mod_conciliacao_pe as _mconc
    for pid, venda in vendas_pe.items():
        va_proporcao = _mconc.valor_complemento_por_fator(
            valor_venda_pe=venda, vava_contratado=vava_ct[pid],
            vbva_contratado={pid_a: 80000.0, pid_b: 40000.0}[pid])
        divergencia = round(va_proporcao - vava_motor[pid], 2)
        assert abs(divergencia) < 0.02, (pid, va_proporcao, vava_motor[pid], divergencia)


def test_aceite_3_os_tres_consumidores_movem_juntos(app_db, seed, http_client_factory):
    """Aceite 3 do pacote: os 3 consumidores de `valor_complemento_por_fator` (unificados em
    15/08 pra não divergirem) se movem JUNTOS — a `diferenca` do Complemento de fato
    (`_complemento_diferencas`, via xml_compl) bate com a `diferenca_valor_contrato` da prévia da
    AF2 (`GET /pe/conciliacao`, via xml_pe) pro MESMO ambiente/venda, sem aditivo assinado ainda
    (única condição em que os dois usam a mesma base — `vava_contratado` puro — ver comentário
    de main.py:2746-2752, fora do escopo desta tarefa)."""
    nome, pid, oid = _setup(app_db, seed)   # arq 10% repassado, budget 80.000/order 30.000
    c = _login(http_client_factory, "dir_l1")

    venda = 95000.0
    _upsert_compl(app_db, nome, pid, venda=venda, cfo=34000.0)   # xml_compl — Complemento de fato
    db = app_db.get_session()
    db.add(main.ArquivoPE(projeto_nome=nome, pool_ambiente_id=pid, formato="xml_pe",
                          valor_venda=venda, valor_atualizado=34000.0))   # xml_pe — prévia da AF2
    db.commit(); db.close()

    db = app_db.get_session()
    try:
        linhas, _resumo = main._complemento_diferencas(db, nome)
        l = next(x for x in linhas if x["pool_ambiente_id"] == pid)
        diferenca_complemento = l["diferenca"]
    finally:
        db.close()

    st, body = c.get(f"/api/projetos/{nome}/pe/conciliacao")
    assert st == 200 and body["ok"], body
    linha_af2 = next(a for f in body["fases"] for a in f["ambientes"]
                     if a["pool_ambiente_id"] == pid)
    diferenca_af2 = linha_af2["diferenca_valor_contrato"]

    assert abs(diferenca_complemento - diferenca_af2) < 0.02, (
        "os 3 consumidores tinham que mover juntos — Complemento: %.2f, AF2: %.2f"
        % (diferenca_complemento, diferenca_af2))


def test_aceite_4_fallback_log_nao_aparece_em_cenario_normal(app_db, seed, capsys):
    """Aceite 4: `[F2-42-FALLBACK]` não aparece em nenhum cenário NORMAL (motor calculando certo
    pra todo ambiente carregado)."""
    nome, pid, oid = _setup(app_db, seed)
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    db = app_db.get_session()
    try:
        linhas, resumo = main._complemento_diferencas(db, nome)
        assert linhas[0]["divergencia"] is not None   # motor calculou — não é um fallback
    finally:
        db.close()
    saida = capsys.readouterr().out
    assert "[F2-42-FALLBACK]" not in saida, saida


def test_fallback_e_observavel_quando_motor_nao_calcula_o_ambiente(app_db, seed, capsys):
    """O fallback tem que ser EXCEÇÃO OBSERVÁVEL, nunca caminho silencioso: se o ambiente
    carregado (xml_compl) não está de fato vinculado ao orçamento contratado (o motor não pode
    calcular o VAVA dele), a cobrança cai na proporção E o log `[F2-42-FALLBACK]` aparece."""
    nome, pid, oid = _setup(app_db, seed)
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    # Remove o vínculo do ambiente com o orçamento CONTRATADO — o motor deixa de enxergá-lo
    # (simula "PE carregado, mas ambiente fora do orçamento vigente" sem precisar derrubar o
    # motor inteiro com uma exceção).
    db = app_db.get_session()
    db.query(main.OrcamentoAmbiente).filter_by(orcamento_id=oid, pool_ambiente_id=pid).delete()
    db.commit(); db.close()

    db = app_db.get_session()
    try:
        linhas, resumo = main._complemento_diferencas(db, nome)
        l = next(x for x in linhas if x["pool_ambiente_id"] == pid)
        assert l["divergencia"] == 0.0, "sem motor pro ambiente, cai na proporção — divergência 0"
        assert abs(l["vava_complemento"] - l["vava_proporcao"]) < 0.001, (
            "no fallback, vava_complemento (o que é cobrado) tem que SER a proporção")
    finally:
        db.close()
    saida = capsys.readouterr().out
    assert "[F2-42-FALLBACK]" in saida, "fallback tem que ser logado, nunca silencioso"
