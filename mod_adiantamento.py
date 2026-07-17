"""mod_adiantamento.py — Adiantamentos/empréstimos a funcionários (Fase 5). Saldo de débito, abatimento
no líquido e a regra oficial (40% do salário fixo em carteira)."""
from database import AdiantamentoFuncionario, Funcao


def saldo_debito(db, funcionario_id):
    """Σ dos adiantamentos/empréstimos NÃO quitados do funcionário (o que ele deve à empresa)."""
    itens = db.query(AdiantamentoFuncionario).filter_by(funcionario_id=funcionario_id, quitado=0).all()
    return round(sum(float(a.valor or 0.0) for a in itens), 2)


def abatimentos_competencia(db, funcionario_id, competencia):
    """Σ dos adiantamentos a abater (abater=1, não quitados) cuja competencia_abate = `competencia`."""
    itens = (db.query(AdiantamentoFuncionario)
             .filter_by(funcionario_id=funcionario_id, competencia_abate=competencia, quitado=0)
             .filter(AdiantamentoFuncionario.abater == 1).all())
    return round(sum(float(a.valor or 0.0) for a in itens), 2)


def upsert_oficial(db, loja_id, f, competencia, pct):
    """Cria/atualiza (idempotente por ref) o adiantamento oficial do mês para funcionário REGISTRADO.
    valor = pct% × salário fixo da Função; abate na própria competência. Retorna o item, ou None."""
    funcao = db.get(Funcao, f.funcao_id) if f.funcao_id else None
    if not funcao or (funcao.regime_contratacao or "") != "registrado":
        return None
    fixo = float(funcao.salario_fixo or 0.0)
    if fixo <= 0 or float(pct) <= 0:
        return None
    valor = round(fixo * float(pct) / 100.0, 2)
    ref = "oficial:%d:%s" % (f.id, competencia)
    it = db.query(AdiantamentoFuncionario).filter_by(ref=ref).first()
    if it is None:
        it = AdiantamentoFuncionario(loja_id=loja_id, funcionario_id=f.id, tipo="oficial",
                                     competencia=competencia, competencia_abate=competencia,
                                     abater=1, ref=ref)
        db.add(it)
    if it.quitado:
        return it
    it.valor = valor
    db.flush()
    return it


def quitar_da_competencia(db, funcionario_id, competencia):
    """Marca como quitados os adiantamentos abatidos naquela competência (ao pagar a folha)."""
    itens = (db.query(AdiantamentoFuncionario)
             .filter_by(funcionario_id=funcionario_id, competencia_abate=competencia)
             .filter(AdiantamentoFuncionario.abater == 1).all())
    for a in itens:
        a.quitado = 1
    db.flush()
    return len(itens)
