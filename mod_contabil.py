"""mod_contabil.py — motor contábil (domínio financeiro). Sub-projeto #1: Plano de Contas.
Fonte de verdade: Especificacao_Financeiro_Orizon_v2.docx §2/§2.1."""
from database import get_session, Conta, Loja, Lancamento

# Plano-padrão (codigo, nome) — pai = prefixo; tipo/natureza derivados. Ordem = ordem contábil.
PLANO_PADRAO = [
    ("1", "ATIVO"),
    ("1.1", "Circulante"),
    ("1.1.01", "Caixa/Bancos"), ("1.1.02", "Contas a Receber (Clientes)"),
    ("1.1.03", "Estoques"), ("1.1.04", "Adiantamentos a Fornecedores"),
    ("1.2", "Não Circulante"),
    ("1.2.1", "Imobilizado"),
    ("1.2.1.01", "Itens de Informática"), ("1.2.1.02", "Veículos"),
    ("1.2.1.03", "Obras/Reforma de Loja"), ("1.2.1.04", "Show Room"),
    ("1.2.2", "Intangível"),
    ("2", "PASSIVO"),
    ("2.1", "Circulante"),
    ("2.1.01", "Fornecedores a Pagar"), ("2.1.02", "Obrigações Trabalhistas"),
    ("2.1.03", "Obrigações Tributárias"),
    ("2.1.04", "Provisões"),
    ("2.1.04.01", "Provisão de Comissão"), ("2.1.04.02", "Provisão de Montagem"),
    ("2.1.04.03", "Provisão de Garantia Técnica"), ("2.1.04.04", "Provisão de Devolução"),
    ("2.1.05", "Financiamento Total Flex a Pagar"),
    ("2.2", "Não Circulante"),
    ("2.2.01", "Financiamentos de Longo Prazo (principal)"),
    ("3", "PATRIMÔNIO LÍQUIDO"),
    ("3.1", "Capital Social"), ("3.2", "Reservas"),
    ("3.3", "Lucros/Prejuízos Acumulados"), ("3.4", "Distribuição de Lucros"),
    ("4", "RECEITAS"),
    ("4.1", "Vendas de Produtos"),
    ("4.1.01", "Receitas com Vendas"), ("4.1.02", "Receita com Vendas de Assistência"),
    ("4.2", "Serviços"),
    ("4.2.01", "Receita de Serviços"), ("4.2.02", "Prestação de Serviços para Terceiros"),
    ("4.3", "Deduções"),
    ("4.3.01", "Simples Nacional s/ Vendas"), ("4.3.02", "Devolução de Vendas"),
    ("4.4", "Outras Receitas Não Operacionais"),
    ("4.4.01", "Receita de Aluguéis"),
    ("5", "DESPESAS / CUSTOS"),
    ("5.1", "CMV"),
    ("5.1.01", "CMV Fábrica (Dal Mobile)"), ("5.1.02", "Frete Fábrica"),
    ("5.2", "Custo de Serviço"),
    ("5.2.01", "Montagem"), ("5.2.02", "Comissão Executivo de Montagem"),
    ("5.2.03", "Viagens de Pedido"), ("5.2.04", "Salários Operacionais"),
    ("5.2.05", "Ajudante Semanal"), ("5.2.06", "Combustível de Depósito"),
    ("5.2.07", "Pedágio"), ("5.2.08", "Frete Local"), ("5.2.09", "Insumos"),
    ("5.2.10", "Manutenção de Veículos"), ("5.2.11", "Viagens de Supervisão"),
    ("5.3", "Despesas Comerciais"),
    ("5.3.01", "Comissão de Vendedor"), ("5.3.02", "Comissão de Indicador"),
    ("5.3.03", "Comissão Administrativa"), ("5.3.04", "Pontos Programa de Indicação"),
    ("5.3.05", "Premiação de Vendedores"), ("5.3.06", "Salários de Vendas"),
    ("5.3.07", "Marketing/Campanhas de Divulgação"), ("5.3.08", "Salário Marketing"),
    ("5.3.09", "Site e Hospedagem"), ("5.3.10", "Combustível de Venda"),
    ("5.3.11", "Uniformes"), ("5.3.12", "Brindes"), ("5.3.13", "Suprimento a Cliente"),
    ("5.3.14", "Viagens de Especificador"),
    ("5.4", "Despesas Administrativas"),
    ("5.4.01", "Aluguel"), ("5.4.02", "Energia Elétrica"), ("5.4.03", "Água"),
    ("5.4.04", "Telefonia Fixa/Móvel e Internet"), ("5.4.05", "Contabilidade"),
    ("5.4.06", "Assessoria Jurídica"), ("5.4.07", "Consultoria"),
    ("5.4.08", "Segurança e Seguros"), ("5.4.09", "Material de Limpeza/Expediente"),
    ("5.4.10", "Sistemas (ERP, CRM, assinatura digital)"), ("5.4.11", "Salários Administrativos"),
    ("5.4.12", "Pró-labore"), ("5.4.13", "Encargos sobre Folha"),
    ("5.4.14", "Vale-Transporte"), ("5.4.15", "Sindicato"), ("5.4.16", "Rescisões"),
    ("5.4.17", "IPVA/IPTU/Licenciamentos"), ("5.4.18", "Manutenção (loja, veículos, informática)"),
    ("5.5", "Despesas Financeiras"),
    ("5.5.01", "Tarifas Bancárias"), ("5.5.02", "Juros de Empréstimos"),
    ("5.5.03", "Custo de Antecipação de Recebíveis"),
    ("5.6", "Constituição de Provisões"),
    ("5.6.01", "Constituição de Provisão"),
]


def _pai_codigo(codigo):
    return codigo.rsplit(".", 1)[0] if "." in codigo else None


def _natureza(grupo):
    # Ativo(1)/Despesa(5) devedora; Passivo(2)/PL(3)/Receita(4) credora
    return "devedora" if grupo in (1, 5) else "credora"


def resolver_owner(db, usuario):
    """(owner_tipo, owner_id) do usuário: rede da loja se houver; senão a loja; admin de rede -> rede."""
    rid = usuario.get("rede_id")
    lid = usuario.get("loja_id")
    if lid:
        loja = db.get(Loja, lid)
        if loja and loja.rede_id:
            return ("rede", loja.rede_id)
        return ("loja", lid)
    if rid:
        return ("rede", rid)
    raise ValueError("usuário sem loja nem rede para resolver owner contábil")


def seed_plano(db, owner_tipo, owner_id):
    """Materializa o plano-padrão para o owner se ele ainda não tiver contas.
    Retorna nº de contas criadas (0 se já existia)."""
    existe = db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id).first()
    if existe:
        return 0
    codigos = {c for c, _ in PLANO_PADRAO}
    id_por_codigo = {}
    criadas = 0
    for ordem, (codigo, nome) in enumerate(PLANO_PADRAO):
        grupo = int(codigo.split(".")[0])
        tipo = "sintetica" if any(o.startswith(codigo + ".") for o in codigos) else "analitica"
        pai_cod = _pai_codigo(codigo)
        c = Conta(owner_tipo=owner_tipo, owner_id=owner_id, codigo=codigo, nome=nome,
                  grupo=grupo, tipo=tipo, natureza=_natureza(grupo),
                  pai_id=id_por_codigo.get(pai_cod), ativa=1, ordem=ordem)
        db.add(c)
        db.flush()
        id_por_codigo[codigo] = c.id
        criadas += 1
    db.commit()
    return criadas


def _serial(c):
    return {"id": c.id, "codigo": c.codigo, "nome": c.nome, "grupo": c.grupo,
            "tipo": c.tipo, "natureza": c.natureza, "pai_id": c.pai_id, "ativa": bool(c.ativa)}


def listar_contas(db, owner_tipo, owner_id, incluir_inativas=False):
    """Árvore (lista de raízes com 'filhos'), ordenada por 'ordem'/codigo. Seed-on-first-access."""
    seed_plano(db, owner_tipo, owner_id)
    q = db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id)
    if not incluir_inativas:
        q = q.filter(Conta.ativa == 1)
    contas = q.order_by(Conta.ordem, Conta.codigo).all()
    nodes = {c.id: {**_serial(c), "filhos": []} for c in contas}
    raizes = []
    for c in contas:
        if c.pai_id and c.pai_id in nodes:
            nodes[c.pai_id]["filhos"].append(nodes[c.id])
        else:
            raizes.append(nodes[c.id])
    return raizes


# ── CRUD ────────────────────────────────────────────────────────────────────
def _get_own(db, owner_tipo, owner_id, conta_id):
    c = db.get(Conta, conta_id)
    if c is None:
        raise ValueError("conta inexistente")
    if c.owner_tipo != owner_tipo or c.owner_id != owner_id:
        raise PermissionError("conta de outro owner")
    return c


def _tem_filhos(db, conta):
    return db.query(Conta).filter_by(owner_tipo=conta.owner_tipo, owner_id=conta.owner_id,
                                     pai_id=conta.id).first() is not None


def _tem_lancamentos(db, conta):
    from sqlalchemy import or_
    return db.query(Lancamento).filter_by(owner_tipo=conta.owner_tipo, owner_id=conta.owner_id).filter(
        or_(Lancamento.conta_debito_id == conta.id,
            Lancamento.conta_credito_id == conta.id)).first() is not None


def _proximo_codigo(db, pai):
    filhos = db.query(Conta).filter_by(owner_tipo=pai.owner_tipo, owner_id=pai.owner_id,
                                       pai_id=pai.id).all()
    usados = set()
    for f in filhos:
        try:
            usados.add(int(f.codigo.rsplit(".", 1)[-1]))
        except ValueError:
            pass
    seq = 1
    while seq in usados:
        seq += 1
    return f"{pai.codigo}.{seq:02d}"


def criar_conta(db, owner_tipo, owner_id, pai_id, nome):
    pai = _get_own(db, owner_tipo, owner_id, pai_id)
    if not (nome or "").strip():
        raise ValueError("nome obrigatório")
    if pai.tipo == "analitica":
        pai.tipo = "sintetica"                            # pai passa a agrupar
    c = Conta(owner_tipo=owner_tipo, owner_id=owner_id, codigo=_proximo_codigo(db, pai),
              nome=nome.strip(), grupo=pai.grupo, tipo="analitica", natureza=_natureza(pai.grupo),
              pai_id=pai.id, ativa=1, ordem=999)
    db.add(c)
    db.commit()
    return _serial(c)


def editar_conta(db, owner_tipo, owner_id, conta_id, nome=None, ordem=None):
    c = _get_own(db, owner_tipo, owner_id, conta_id)
    if nome is not None:
        if not nome.strip():
            raise ValueError("nome obrigatório")
        c.nome = nome.strip()
    if ordem is not None:
        c.ordem = int(ordem)
    db.commit()
    return _serial(c)


def remover_conta(db, owner_tipo, owner_id, conta_id):
    """Folha sem lançamento -> apaga; senão inativa (regra do .docx)."""
    c = _get_own(db, owner_tipo, owner_id, conta_id)
    if not _tem_filhos(db, c) and not _tem_lancamentos(db, c):
        db.delete(c)
        db.commit()
        return {"acao": "apagada", "id": conta_id}
    c.ativa = 0
    db.commit()
    return {"acao": "inativada", "id": conta_id}


# ── Livro de Lançamentos (sub-projeto #2) ────────────────────────────────────
def _lanc_serial(l):
    return {"id": l.id, "data": l.data.isoformat() if l.data else None, "valor": l.valor,
            "conta_debito_id": l.conta_debito_id, "conta_credito_id": l.conta_credito_id,
            "projeto_id": l.projeto_id, "origem": l.origem, "historico": l.historico}


def lancar(db, owner_tipo, owner_id, conta_debito_id, conta_credito_id, valor,
           data=None, projeto_id=None, origem="manual", historico=""):
    """Registra um lançamento de partida dobrada. Débito e crédito devem ser contas
    ANALÍTICAS ativas do mesmo owner; valor > 0; contas distintas."""
    if valor is None or float(valor) <= 0:
        raise ValueError("valor deve ser > 0")
    if conta_debito_id == conta_credito_id:
        raise ValueError("débito e crédito não podem ser a mesma conta")
    cd = _get_own(db, owner_tipo, owner_id, conta_debito_id)
    cc = _get_own(db, owner_tipo, owner_id, conta_credito_id)
    for c in (cd, cc):
        if c.tipo != "analitica":
            raise ValueError("conta %s é sintética; só analítica recebe lançamento" % c.codigo)
        if not c.ativa:
            raise ValueError("conta %s está inativa" % c.codigo)
    from datetime import datetime as _dt
    lan = Lancamento(owner_tipo=owner_tipo, owner_id=owner_id, data=data or _dt.utcnow(),
                     conta_debito_id=conta_debito_id, conta_credito_id=conta_credito_id,
                     valor=round(float(valor), 2), projeto_id=projeto_id, origem=origem,
                     historico=historico or "")
    db.add(lan)
    db.commit()
    return _lanc_serial(lan)


def _filtra_periodo(q, ini, fim):
    if ini:
        q = q.filter(Lancamento.data >= ini)
    if fim:
        q = q.filter(Lancamento.data <= fim)
    return q


def saldo_conta(db, owner_tipo, owner_id, conta_id, ini=None, fim=None):
    """Saldo da conta na natureza dela (devedora: D−C; credora: C−D)."""
    c = _get_own(db, owner_tipo, owner_id, conta_id)
    base = db.query(Lancamento).filter_by(owner_tipo=owner_tipo, owner_id=owner_id)
    deb = sum(l.valor for l in _filtra_periodo(base.filter(Lancamento.conta_debito_id == conta_id), ini, fim).all())
    cred = sum(l.valor for l in _filtra_periodo(base.filter(Lancamento.conta_credito_id == conta_id), ini, fim).all())
    return round(deb - cred if c.natureza == "devedora" else cred - deb, 2)


def razao(db, owner_tipo, owner_id, conta_id, ini=None, fim=None):
    """Extrato (razão) de uma conta: linhas D/C com saldo corrido na natureza da conta."""
    from sqlalchemy import or_
    c = _get_own(db, owner_tipo, owner_id, conta_id)
    q = db.query(Lancamento).filter_by(owner_tipo=owner_tipo, owner_id=owner_id).filter(
        or_(Lancamento.conta_debito_id == conta_id, Lancamento.conta_credito_id == conta_id))
    lans = _filtra_periodo(q, ini, fim).order_by(Lancamento.data, Lancamento.id).all()
    saldo = 0.0
    linhas = []
    for l in lans:
        deb = l.conta_debito_id == conta_id
        mov = l.valor if (deb == (c.natureza == "devedora")) else -l.valor
        saldo = round(saldo + mov, 2)
        linhas.append({"id": l.id, "data": l.data.isoformat() if l.data else None,
                       "dc": "D" if deb else "C", "valor": l.valor,
                       "contrapartida_id": l.conta_credito_id if deb else l.conta_debito_id,
                       "projeto_id": l.projeto_id, "historico": l.historico, "saldo": saldo})
    return {"conta_id": conta_id, "codigo": c.codigo, "nome": c.nome, "natureza": c.natureza,
            "linhas": linhas, "saldo_final": saldo}


def listar_lancamentos(db, owner_tipo, owner_id, projeto_id=None, ini=None, fim=None, limite=500):
    q = db.query(Lancamento).filter_by(owner_tipo=owner_tipo, owner_id=owner_id)
    if projeto_id:
        q = q.filter(Lancamento.projeto_id == projeto_id)
    q = _filtra_periodo(q, ini, fim).order_by(Lancamento.data.desc(), Lancamento.id.desc())
    return [_lanc_serial(l) for l in q.limit(limite).all()]
