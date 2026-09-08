# -*- coding: utf-8 -*-
"""F2-41 Rodada 1 (docs/db/TAREFA_F2_41_FONTE_UNICA_COMPLEMENTO.md) — SOMBRA: mede o valor que o
MOTOR daria pro mesmo ambiente (`_negociacao_breakdown(..., vbva_override=...)`, mesmo mecanismo
da tela "Comparação de Valores", main.py:2666-2677) ao lado do valor por proporção
(`valor_complemento_por_fator`) que já é o que se cobra hoje — SEM trocar o que é cobrado.

Origem da medição: teste do Marcelo em 08/09 — a tela e o modal do complemento mostram valores
diferentes pro MESMO ambiente (divergências de R$ 52,07 e R$ 5,66 medidas). Hipótese do mecanismo
(NÃO provada, é o que esta rodada mede): o à vista de um ambiente é `k×VBVA + F` (F = custos
adicionais, valor FIXO); a proporção multiplica o F junto com a mercadoria, o motor não.

Os 4 testes de propriedade pedidos (rodam contra o comportamento ATUAL do motor — se o teste 2
falhar, é achado da rodada, não bug a consertar aqui: ver NÃO AUTORIZA no pacote)."""
import json
from unittest import mock

import main
from tests.test_complemento_pe_e2e import _login, _setup, _upsert_compl


def _isolar_marcas(app_db, nome, pid):
    """seed/app_db são module-scoped NESTE arquivo (mesmo projeto reusado por todos os testes,
    mesma disciplina de test_complemento_pe_e2e.py) — `_setup` cria um "Cozinha" NOVO a cada
    chamada, sempre marcado `renegociar_pe=1`, empilhando sobre os de testes anteriores. Isola
    o teste atual desmarcando qualquer outro ambiente do projeto."""
    db = app_db.get_session()
    try:
        for pa in db.query(app_db.PoolAmbiente).filter_by(projeto_id=nome).all():
            if pa.id != pid:
                pa.renegociar_pe = 0
        db.commit()
    finally:
        db.close()


def test_xml_identico_diferenca_zero_nas_duas_formulas(app_db, seed):
    """Propriedade 1: XML idêntico ao contratado ⇒ diferença zero, tanto pela proporção
    (`diferenca`, o que é cobrado) quanto pelo motor (`divergencia` — as duas fórmulas concordam
    no ponto zero, mesmo que divirjam fora dele, exatamente a hipótese do F fixo: em XML idêntico
    não há F "a mais" pra distorcer nenhuma das duas)."""
    nome, pid, oid = _setup(app_db, seed)
    _isolar_marcas(app_db, nome, pid)
    _upsert_compl(app_db, nome, pid, venda=80000.0, cfo=30000.0)   # igual ao budget_total contratado

    db = app_db.get_session()
    try:
        linhas, resumo = main._complemento_diferencas(db, nome)
        assert linhas and len(linhas) == 1
        l = linhas[0]
        assert abs(l["diferenca"]) < 0.02, l
        assert l["vava_motor"] is not None, "sombra tinha que ter calculado (XML carregado)"
        assert abs(l["divergencia"]) < 0.02, l
        assert abs(resumo["divergencia_total"]) < 0.02
        assert abs(resumo["divergencia_maxima_abs"]) < 0.02
    finally:
        db.close()


def test_aceite_1_sombra_nao_muda_o_que_e_cobrado(app_db, seed):
    """Aceite 1 do pacote: `diferenca` (o que é cobrado) fixado com o número já conhecido de
    `test_complemento_pe_e2e.py::test_complemento_por_diferenca_ponta_a_ponta` (mesmo cenário:
    arq 10% repassado, venda 84.000 → diferença 4.444,44) — prova direta de que adicionar
    `vava_motor`/`divergencia` ao lado não mudou o número que já existia antes desta rodada."""
    nome, pid, oid = _setup(app_db, seed)
    _isolar_marcas(app_db, nome, pid)
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    db = app_db.get_session()
    try:
        linhas, resumo = main._complemento_diferencas(db, nome)
        l = next(x for x in linhas if x["pool_ambiente_id"] == pid)
        assert abs(l["diferenca"] - 4444.44) < 0.05, (
            "F2-41 não pode mudar o que é cobrado — %r" % l)
        assert abs(resumo["total_diferenca"] - 4444.44) < 0.05
        # a sombra é um campo A MAIS, não uma substituição — os dois convivem na mesma linha
        assert "vava_motor" in l and "divergencia" in l
    finally:
        db.close()


def _seed_dois_ambientes(app_db, seed, budgets_orders):
    """Contrato assinado com N ambientes reais (sem XML de complemento — usado pelos testes
    diretos do MOTOR, 2/3, que não precisam do lado do complemento, só de
    `_negociacao_breakdown`/`vbva_override`). `budgets_orders`: [(budget, order), ...]."""
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    orc = db.get(main.Orcamento, oid)
    nome = orc.projeto_id
    proj = db.query(main.Projeto).filter_by(nome_safe=nome).first()
    proj.parametros_json = json.dumps({"incluir_custos": True, "comissao_arq_ativa": True,
                                       "comissao_arq_pct": 10.0, "carga_trib": 0.0})
    pids = []
    for i, (budget, order) in enumerate(budgets_orders):
        pa = main.PoolAmbiente(nome="Amb%d" % i, nome_exibicao="Amb%d" % i,
                               xml_path="fake/amb%d.xml" % i, ambientes_json="{}",
                               projeto_id=nome, budget_total=budget, order_total=order)
        db.add(pa); db.flush()
        db.add(main.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=i + 1))
        pids.append(pa.id)
    db.commit()
    db.close()
    return nome, oid, pids


def test_sem_vazamento_entre_ambientes(app_db, seed):
    """Propriedade 2 (o teste que a Comparação de Valores hoje NÃO consegue fazer, porque só
    monta o dicionário pros ambientes com PE carregado): substituir o VBVA de UM ambiente não
    pode alterar o VAVA de NENHUM outro na mesma chamada do motor. Se isto falhar, é achado da
    rodada — não conserta o motor aqui (instrução explícita do pacote)."""
    nome, oid, (pid_a, pid_b) = _seed_dois_ambientes(
        app_db, seed, [(80000.0, 30000.0), (40000.0, 16000.0)])

    db = app_db.get_session()
    try:
        orc = db.get(main.Orcamento, oid)
        d_base = main._negociacao_breakdown(orc, db)
        vava_b_base = next(a["VAVA"] for a in d_base["ambientes"] if a["id"] == pid_b)

        # só o ambiente A é substituído — B fica de fora do override
        d_over = main._negociacao_breakdown(orc, db, vbva_override={pid_a: 95000.0})
        vava_b_over = next(a["VAVA"] for a in d_over["ambientes"] if a["id"] == pid_b)

        assert abs(vava_b_base - vava_b_over) < 0.01, (
            "vazamento: substituir o VBVA de A mudou o VAVA de B — %r vs %r"
            % (vava_b_base, vava_b_over))
    finally:
        db.close()


def test_soma_das_diferencas_fecha_com_a_diferenca_do_total(app_db, seed):
    """Propriedade 3: soma das diferenças (motor, por ambiente) entre a passada substituída e a
    original bate com a diferença dos totais (VAVO das duas passadas) — nenhuma perda/duplicação
    ao agregar."""
    nome, oid, (pid_a, pid_b) = _seed_dois_ambientes(
        app_db, seed, [(80000.0, 30000.0), (40000.0, 16000.0)])

    db = app_db.get_session()
    try:
        orc = db.get(main.Orcamento, oid)
        d_base = main._negociacao_breakdown(orc, db)
        override = {pid_a: 95000.0, pid_b: 36000.0}
        d_over = main._negociacao_breakdown(orc, db, vbva_override=override)

        vava_base = {a["id"]: a["VAVA"] for a in d_base["ambientes"]}
        vava_over = {a["id"]: a["VAVA"] for a in d_over["ambientes"]}
        soma_diferencas = sum(vava_over[i] - vava_base[i] for i in vava_base)
        diferenca_total = d_over["VAVO"] - d_base["VAVO"]

        assert abs(soma_diferencas - diferenca_total) < 0.02, (
            "soma por ambiente (%.2f) não fecha com a diferença do total VAVO (%.2f)"
            % (soma_diferencas, diferenca_total))
    finally:
        db.close()


def test_nao_cobra_duas_vezes_apos_aditivo_assinado_sem_mudar_xml(app_db, seed, http_client_factory):
    """Propriedade 4 (ACHADO-21, 6-b, reconfirmada neste pacote): complemento gerado depois de um
    aditivo assinado, SEM mudança de XML, dá diferença zero — a diferença já foi contratada
    (`ja_contratado`, via `_pe_fator_contexto`), cobrar de novo pelo mesmo XML duplicaria."""
    nome, pid, oid = _setup(app_db, seed)
    c = _login(http_client_factory, "dir_l1")
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)

    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 200 and body["ok"], body

    import mod_documentos
    db = app_db.get_session()
    mv = mod_documentos.criar_versao(db, seed["loja1_id"], "termo_aditivo",
                                     "# TERMO ADITIVO [NUM_ADITIVO]\n1. [AMBIENTES_COMPLEMENTO]\n"
                                     "2. Complemento: [VALOR_COMPLEMENTO].\n", "t.md", None)
    mod_documentos.ativar(db, mv.id)
    db.close()
    st, body = c.post(f"/api/projetos/{nome}/aditivo", {})
    assert st == 200 and body["ok"], body
    for parte, quem in (("loja", "Rep Loja"), ("cliente", "Cliente L1")):
        corpo = {"parte": parte, "nome": quem, "cpf": "111.444.777-35"}
        if parte == "cliente":
            corpo["forma_pagamento"] = json.dumps(
                {"tipo": "avista", "total_cliente": 4444.44, "entrada_valor": 1.0})
        st, body = c.post(f"/api/projetos/{nome}/aditivo/assinar", corpo)
        assert st == 200, body
    assert body["status"] == "assinado"

    # MESMO xml_compl, sem mudança — recomputa a diferença: tem que dar zero.
    db = app_db.get_session()
    try:
        linhas, resumo = main._complemento_diferencas(db, nome)
        l = next(x for x in linhas if x["pool_ambiente_id"] == pid)
        assert abs(l["diferenca"]) < 0.02, (
            "cobrança duplicada: diferença deveria ser zero pós-aditivo assinado, sem mudar o "
            "XML — %r" % l)
    finally:
        db.close()


def test_aceite_3_uma_chamada_de_motor_por_invocacao_nao_escala_com_ambientes(app_db, seed):
    """Aceite 3 do pacote: a contagem de chamadas a `_negociacao_breakdown` dentro de UMA
    invocação de `_complemento_diferencas` tem que ser CONSTANTE — não escalar com o número de
    ambientes marcados (a prova real de que a sombra não roda dentro do laço: se rodasse, 3
    ambientes chamariam o motor 3× mais que 1 ambiente). O total (2) é: 1 chamada de baseline
    dentro de `_pe_fator_contexto` (pré-existente, não é desta rodada) + 1 chamada da sombra
    (nova), sempre — independente de quantos ambientes tem a marcar."""
    nome, oid, pids = _seed_dois_ambientes(
        app_db, seed, [(80000.0, 30000.0), (40000.0, 16000.0), (20000.0, 8000.0)])
    db0 = app_db.get_session()
    # seed/app_db são module-scoped neste arquivo — testes anteriores (_setup) podem ter deixado
    # outros ambientes marcados; este teste precisa de uma contagem EXATA, então limpa tudo
    # antes de marcar só os 3 que são dele.
    for pa in db0.query(main.PoolAmbiente).filter_by(projeto_id=nome).all():
        pa.renegociar_pe = 1 if pa.id in pids else 0
    db0.commit(); db0.close()
    for i, pid in enumerate(pids):
        _upsert_compl(app_db, nome, pid, venda=80000.0 + i * 5000, cfo=30000.0)

    db = app_db.get_session()
    try:
        with mock.patch.object(main, "_negociacao_breakdown",
                               wraps=main._negociacao_breakdown) as _spy:
            linhas, resumo = main._complemento_diferencas(db, nome)
            assert len(linhas) == 3, "pré-condição: os 3 ambientes marcados têm que aparecer"
            chamadas_com_3_ambientes = _spy.call_count

        # Agora só 1 ambiente marcado (mesmo projeto) — a contagem tem que ser A MESMA.
        for pid in pids[1:]:
            db.query(main.PoolAmbiente).filter_by(id=pid).update({"renegociar_pe": 0})
        db.commit()
        with mock.patch.object(main, "_negociacao_breakdown",
                               wraps=main._negociacao_breakdown) as _spy:
            linhas1, _ = main._complemento_diferencas(db, nome)
            assert len(linhas1) == 1
            chamadas_com_1_ambiente = _spy.call_count

        assert chamadas_com_3_ambientes == chamadas_com_1_ambiente == 2, (
            "chamadas ao motor não podem escalar com o número de ambientes — 3 ambientes: %d, "
            "1 ambiente: %d (esperado 2 nos dois — 1 baseline de _pe_fator_contexto + 1 sombra)"
            % (chamadas_com_3_ambientes, chamadas_com_1_ambiente))
    finally:
        db.close()


def test_aceite_2_e_3_complemento_diferencas_fase_tambem_tem_sombra_em_uma_chamada(app_db, seed):
    """Mesma prova do aceite 2/3, agora para `_complemento_diferencas_fase` (complemento por
    FASE, alimentado por `ConciliacaoPeFase`/`xml_pe` em vez de `renegociar_pe`/`xml_compl`) —
    `vava_motor`/`divergencia` presentes e uma única chamada ao motor, também sem escalar com o
    número de ambientes."""
    nome, oid, pids = _seed_dois_ambientes(
        app_db, seed, [(80000.0, 30000.0), (40000.0, 16000.0), (20000.0, 8000.0)])
    db0 = app_db.get_session()
    for pa in db0.query(main.PoolAmbiente).filter_by(projeto_id=nome).all():
        pa.renegociar_pe = 0   # complemento por fase não usa esta flag — garante que fica de fora
    for i, pid in enumerate(pids):
        db0.add(main.ArquivoPE(projeto_nome=nome, pool_ambiente_id=pid, formato="xml_pe",
                               valor_venda=80000.0 + i * 5000, valor_atualizado=30000.0))
        db0.add(main.ConciliacaoPeFase(projeto_nome=nome, parcela_id=None, pool_ambiente_id=pid,
                                       tipo_decisao="cobrar", diferenca_cfo=0.0,
                                       diferenca_valor_contrato=0.0, valor_aprovado=0.0))
    db0.commit(); db0.close()

    db = app_db.get_session()
    try:
        with mock.patch.object(main, "_negociacao_breakdown",
                               wraps=main._negociacao_breakdown) as _spy:
            linhas, resumo = main._complemento_diferencas_fase(db, nome, parcela_id=None)
            assert len(linhas) == 3
            for l in linhas:
                assert l["vava_motor"] is not None
                assert l["divergencia"] is not None
            assert "divergencia_total" in resumo and "divergencia_maxima_abs" in resumo
            chamadas = _spy.call_count
        assert chamadas == 2, (
            "esperado 2 chamadas (1 baseline de _pe_fator_contexto + 1 sombra) — %d" % chamadas)
    finally:
        db.close()
