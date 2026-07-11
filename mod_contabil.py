"""mod_contabil.py — motor contábil (domínio financeiro). Sub-projeto #1: Plano de Contas.
Fonte de verdade: Especificacao_Financeiro_Orizon_v2.docx §2/§2.1."""
from database import get_session, Conta, Loja, Lancamento, PeriodoContabil

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
    ("2.1.04.03", "Provisão de Garantia"), ("2.1.04.04", "Provisão de Devolução"),
    ("2.1.04.05", "Provisão de Assistência Técnica"),
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
    ("5.6.01", "Constituição — Provisão de Garantia"),
    ("5.6.02", "Constituição — Provisão de Montagem"),
    ("5.6.03", "Constituição — Provisão de Assistência Técnica"),
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
    """Materializa/atualiza o plano-padrão do owner: cria as contas de PLANO_PADRAO que ainda
    faltam — **backfill idempotente** (planos já existentes ganham contas novas, ex.: as 3 provisões
    da v5). Retorna nº de contas criadas (0 se nada faltava)."""
    existentes = {c.codigo: c for c in db.query(Conta)
                  .filter_by(owner_tipo=owner_tipo, owner_id=owner_id).all()}
    codigos = {c for c, _ in PLANO_PADRAO}
    id_por_codigo = {cod: c.id for cod, c in existentes.items()}
    criadas = 0
    for ordem, (codigo, nome) in enumerate(PLANO_PADRAO):
        if codigo in existentes:
            continue
        grupo = int(codigo.split(".")[0])
        tipo = "sintetica" if any(o.startswith(codigo + ".") for o in codigos) else "analitica"
        pai_cod = _pai_codigo(codigo)
        pai_exist = existentes.get(pai_cod)
        if pai_exist is not None and pai_exist.tipo == "analitica":
            pai_exist.tipo = "sintetica"          # pai que era folha vira agrupador ao ganhar filho
        c = Conta(owner_tipo=owner_tipo, owner_id=owner_id, codigo=codigo, nome=nome,
                  grupo=grupo, tipo=tipo, natureza=_natureza(grupo),
                  pai_id=id_por_codigo.get(pai_cod), ativa=1, ordem=ordem)
        db.add(c)
        db.flush()
        id_por_codigo[codigo] = c.id
        criadas += 1
    if criadas:
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
            "projeto_id": l.projeto_id, "origem": l.origem, "historico": l.historico, "ref": l.ref}


def lancar(db, owner_tipo, owner_id, conta_debito_id, conta_credito_id, valor,
           data=None, projeto_id=None, origem="manual", historico="", ref=None,
           motivo=None, ia_sugestao=None):
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
                     historico=historico or "", ref=ref, motivo=motivo, ia_sugestao=ia_sugestao)
    db.add(lan)
    db.commit()
    return _lanc_serial(lan)


def lancamento_por_ref(db, owner_tipo, owner_id, ref):
    """Idempotência do wiring: retorna o serial do lançamento com este `ref` (ou None)."""
    if not ref:
        return None
    l = db.query(Lancamento).filter_by(owner_tipo=owner_tipo, owner_id=owner_id, ref=ref).first()
    return _lanc_serial(l) if l else None


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


# ── Motor evento → lançamento (sub-projeto #3) ───────────────────────────────
# As 5 regras do .docx §5. Contas resolvidas por CÓDIGO (estável: rename não muda o
# código; reparent/recodificar foi adiado no #1). (codigo_debito, codigo_credito, historico)
EVENTOS = {
    # Fechamento de venda — 3 provisões INDEPENDENTES: abre Despesa (5.6.x) × Provisão (2.1.04.x)
    "fechamento_venda_montagem":    ("5.6.02", "2.1.04.02", "Constituição — Provisão de Montagem (fechamento de venda)"),
    "fechamento_venda_assistencia": ("5.6.03", "2.1.04.05", "Constituição — Provisão de Assistência Técnica (fechamento de venda)"),
    "fechamento_venda_garantia":    ("5.6.01", "2.1.04.03", "Constituição — Provisão de Garantia (fechamento de venda)"),
    # Ciclo de caixa
    "faturamento":                  ("1.1.02", "4.1.01",    "Faturamento (NF-e emitida)"),
    "recebimento":                  ("1.1.01", "1.1.02",    "Recebimento do cliente"),
    "pagamento_comissao":           ("2.1.04.01", "1.1.01",  "Pagamento de comissão (baixa da provisão)"),
    # Execução — reverte a provisão respectiva: Provisão (2.1.04.x) × Caixa/Fornecedor
    "execucao_montagem":            ("2.1.04.02", "1.1.01",  "Execução da montagem (baixa da provisão)"),
    "execucao_assistencia":         ("2.1.04.05", "1.1.01",  "Execução de assistência técnica (baixa da provisão)"),
    "execucao_reparo_garantia":     ("2.1.04.03", "1.1.01",  "Execução de reparo em garantia (baixa da provisão)"),
    # Caso de Assistência — tipo de custo Paga: nova venda ao cliente, sem tocar provisão (v7 §6)
    "venda_assistencia":            ("1.1.02", "4.1.02",    "Venda de assistência (caso Paga — cobrança do cliente)"),
    # Folha de Pagamento (v10 §2.1): despesa nas contas 5.3 existentes × Caixa (sem conta nova)
    "folha_fixa":                   ("5.3.06", "1.1.01",    "Folha — parte fixa (Salários de Vendas)"),
    "folha_variavel":               ("5.3.01", "1.1.01",    "Folha — parte variável (Comissão de Vendedor)"),
}


def _conta_por_codigo(db, owner_tipo, owner_id, codigo):
    c = db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id, codigo=codigo).first()
    if c is None:
        raise ValueError("conta %s ausente no plano de contas do owner" % codigo)
    return c


def registrar_evento(db, owner_tipo, owner_id, tipo_evento, valor, projeto_id=None, data=None,
                     historico="", ref=None, motivo=None):
    """Gera o lançamento de partida dobrada correspondente a um evento de negócio (.docx §5/§6).
    Carrega projeto_id (dimensão gerencial) e, p/ reparo em garantia, `motivo` (§6.2).
    Se `ref` já foi lançado, é **idempotente** (não duplica)."""
    if tipo_evento not in EVENTOS:
        raise ValueError("evento desconhecido: %s" % tipo_evento)
    ja = lancamento_por_ref(db, owner_tipo, owner_id, ref)
    if ja is not None:
        return ja                          # idempotente: já lançado com este ref
    seed_plano(db, owner_tipo, owner_id)   # garante o plano-padrão
    cod_d, cod_c, hist_pad = EVENTOS[tipo_evento]
    cd = _conta_por_codigo(db, owner_tipo, owner_id, cod_d)
    cc = _conta_por_codigo(db, owner_tipo, owner_id, cod_c)
    return lancar(db, owner_tipo, owner_id, cd.id, cc.id, valor,
                  data=data, projeto_id=projeto_id, origem=tipo_evento,
                  historico=historico or hist_pad, ref=ref, motivo=motivo)


# ── Provisões da venda: % configurável + auto-constituição no fechamento (v6 §6.4) ──
_PROV_VENDA = {   # chave -> (evento de constituição, código da conta de Provisão no Passivo)
    "montagem":    ("fechamento_venda_montagem",    "2.1.04.02"),
    "assistencia": ("fechamento_venda_assistencia", "2.1.04.05"),
    "garantia":    ("fechamento_venda_garantia",    "2.1.04.03"),
}

# ── Painel de Provisões (dashboard) — DATA-DRIVEN pelo Plano de Contas (Diagramacao_v4 §1.3) ──
# Regra: um card por conta ANALÍTICA do grupo de Provisões que existir no plano — NUNCA hardcodar
# os 3 nomes como componentes fixos. Criar uma provisão nova no Plano de Contas faz surgir um card
# automaticamente, sem tocar no painel. Duas contas do grupo ficam de fora por terem tratamento
# próprio (documentado abaixo), de modo que "hoje são 3" (Montagem/Assistência/Garantia) continua
# valendo — mas por exclusão explícita, não por lista fixa das 3.
GRUPO_PROVISOES = "2.1.04"
_PROV_PAINEL_EXCLUI = {
    "2.1.04.01",   # Comissão — despesa de venda; baixa via pagamento_comissao, não é set-aside de custo
    "2.1.04.04",   # Devolução — sem evento/percentual de constituição hoje (saldo sempre 0)
}
# Descrição opcional por conta (enriquece o card; cai num texto genérico se a conta não estiver aqui):
_PROV_PAINEL_SUB = {
    "2.1.04.02": "Custo direto da venda · reverte na execução",
    "2.1.04.05": "Custo da loja · reverte no atendimento",
    "2.1.04.03": "Repasse à fábrica · controle de cobrança",
}


def _cfg_f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def pcts_provisao_venda(cfg):
    """% das 3 provisões (v6 §6.4): montagem/garantia da config nova `provisoes_contabeis`;
    **assistência herda** `provisoes.assist_pct` da negociação (não recria o dado)."""
    cfg = cfg or {}
    pc = cfg.get("provisoes_contabeis", {}) or {}
    return {"montagem": _cfg_f(pc.get("montagem_pct")),
            "assistencia": _cfg_f((cfg.get("provisoes", {}) or {}).get("assist_pct")),
            "garantia": _cfg_f(pc.get("garantia_pct"))}


def constituir_provisoes_venda(db, owner_tipo, owner_id, projeto_id, valor_venda, cfg, ref_base):
    """Auto-constitui as 3 provisões no fechamento da venda (v6 §6.4): valor = % × valor_venda.
    Idempotente por `ref` (ref_base:<chave>). Só constitui as com % > 0. Retorna os lançamentos."""
    pcts = pcts_provisao_venda(cfg)
    out = []
    for chave, (evento, _cod) in _PROV_VENDA.items():
        val = round(_cfg_f(valor_venda) * pcts[chave] / 100.0, 2)
        if val > 0:
            out.append(registrar_evento(db, owner_tipo, owner_id, evento, val,
                                        projeto_id=projeto_id, ref=ref_base + ":" + chave))
    return out


def contas_provisao_do_plano(db, owner_tipo, owner_id, ini=None, fim=None):
    """Contas ANALÍTICAS do grupo de Provisões (GRUPO_PROVISOES) presentes no plano, data-driven,
    cada uma com o saldo EM ABERTO. Exclui as de tratamento próprio (_PROV_PAINEL_EXCLUI). Fonte
    única do painel de Provisões (dashboard) e reusável (individualização por projeto, etc.).
    Assume o plano já semeado (o dashboard chama seed_plano antes)."""
    contas = (db.query(Conta)
              .filter_by(owner_tipo=owner_tipo, owner_id=owner_id, tipo="analitica")
              .filter(Conta.codigo.like(GRUPO_PROVISOES + ".%"))
              .order_by(Conta.codigo).all())
    out = []
    for c in contas:
        if c.codigo in _PROV_PAINEL_EXCLUI:
            continue
        out.append({"codigo": c.codigo, "nome": c.nome,
                    "sub": _PROV_PAINEL_SUB.get(c.codigo, "Saldo provisionado em aberto"),
                    "saldo_em_aberto": saldo_conta(db, owner_tipo, owner_id, c.id, ini, fim)})
    return out


def dashboard_financeiro(db, owner_tipo, owner_id, ini=None, fim=None):
    """Dashboard do Financeiro (Padrao_Design_Orizon_v4 §5 / Diagramacao_v4 §1.3): um card por
    provisão que EXISTIR no Plano de Contas (grupo GRUPO_PROVISOES), data-driven (via
    contas_provisao_do_plano) — nunca lista fixa de 3. Mais o resumo do DRE e o indicador de
    cobertura de caixa (v6 §6.1: caixa vs provisões)."""
    seed_plano(db, owner_tipo, owner_id)
    provs = contas_provisao_do_plano(db, owner_tipo, owner_id, ini, fim)
    total_prov = round(sum(p["saldo_em_aberto"] for p in provs), 2)
    d = dre(db, owner_tipo, owner_id, ini, fim)
    caixa_c = db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id, codigo="1.1.01").first()
    caixa = saldo_conta(db, owner_tipo, owner_id, caixa_c.id, None, fim) if caixa_c else 0.0
    indice = round(caixa / total_prov, 2) if total_prov > 0 else None
    return {
        "provisoes": provs,
        "total_provisoes_abertas": total_prov,
        "dre_resumo": {"receita_liquida": d["receita_liquida"], "ebitda": d["ebitda"],
                       "lucro_liquido": d["lucro_liquido"]},
        "cobertura_caixa": {"caixa": caixa, "provisoes_abertas": total_prov, "indice": indice},
    }


def provisoes_da_venda(db, owner_tipo, owner_id, projeto_id, ini=None, fim=None):
    """Painel de Provisões da venda (v6 §6): as 3 provisões do projeto com o saldo EM ABERTO
    (constituído − revertido) = saldo da conta de Provisão (credora) filtrado pelo projeto."""
    linhas = []
    for chave, (_ev, cod) in _PROV_VENDA.items():
        c = db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id, codigo=cod).first()
        saldo = 0.0
        if c is not None:
            saldo = _mov(db, owner_tipo, owner_id, cod, "credor", ini, fim, projeto_id=projeto_id)
        linhas.append({"chave": chave, "codigo": cod, "nome": c.nome if c else chave,
                       "saldo_em_aberto": saldo})
    return {"projeto_id": projeto_id, "provisoes": linhas,
            "total_em_aberto": round(sum(l["saldo_em_aberto"] for l in linhas), 2)}


def _norm_tokens(s):
    import re as _re, unicodedata as _u
    s = _u.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return set(_re.findall(r"[a-z0-9]{3,}", s))   # tokens de 3+ chars (sem acento)


def sugerir_conta(db, owner_tipo, owner_id, texto):
    """IA de apoio à classificação (v5 §6.3) — HEURÍSTICA (sem LLM externo): sugere uma conta
    ANALÍTICA para `texto` por sobreposição de palavras com o nome da conta + histórico de
    lançamentos similares. **NUNCA lança** — só sugere; o funcionário confirma/troca."""
    import math
    from collections import Counter
    seed_plano(db, owner_tipo, owner_id)
    toks = _norm_tokens(texto)
    if not toks:
        return None
    contas = db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id,
                                       tipo="analitica", ativa=1).all()
    conta_toks = {c.id: _norm_tokens(c.nome) for c in contas}
    # IDF: token raro (ex.: 'aluguel') pesa mais que comum (ex.: 'loja', 'conta')
    df = Counter()
    for ts in conta_toks.values():
        for t in ts:
            df[t] += 1
    n = len(contas) or 1
    idf = lambda t: math.log((n + 1) / (df.get(t, 0) + 1)) + 1.0
    peso = lambda ts: sum(idf(t) for t in (toks & ts))
    scores = {}
    for cid, ts in conta_toks.items():
        w = peso(ts)
        if w:
            scores[cid] = scores.get(cid, 0) + w * 2.0           # nome da conta
    for l in (db.query(Lancamento).filter_by(owner_tipo=owner_tipo, owner_id=owner_id)
              .order_by(Lancamento.id.desc()).limit(300).all()):   # histórico recente
        w = peso(_norm_tokens(l.historico))
        if w:
            for cid in (l.conta_debito_id, l.conta_credito_id):
                scores[cid] = scores.get(cid, 0) + w             # histórico similar
    if not scores:
        return None
    best_id = max(scores, key=scores.get)
    c = db.get(Conta, best_id)
    return {"conta_id": c.id, "codigo": c.codigo, "nome": c.nome, "grupo": c.grupo,
            "score": scores[best_id],
            "motivo": "heurística: sobreposição com nome da conta + histórico similar"}


def total_a_cobrar_fabrica(db, owner_tipo, owner_id, ini=None, fim=None):
    """Repasse à Fábrica (§6.2): soma dos reparos em GARANTIA marcados 'defeito_fabrica' — o custo
    que deveria ser da Dal Mobile. Ferramenta de negociação; NÃO é Contas a Receber (só fase 2)."""
    q = db.query(Lancamento).filter_by(owner_tipo=owner_tipo, owner_id=owner_id,
                                       origem="execucao_reparo_garantia", motivo="defeito_fabrica")
    lans = _filtra_periodo(q, ini, fim).order_by(Lancamento.data.desc()).all()
    itens = [{"id": l.id, "data": l.data.isoformat() if l.data else None, "valor": l.valor,
              "projeto_id": l.projeto_id, "historico": l.historico} for l in lans]
    return {"total": round(sum(l.valor for l in lans), 2), "qtd": len(itens), "itens": itens}


# ── DRE societário (sub-projeto #4) ──────────────────────────────────────────
def _totais_conta(db, ot, oid, conta_id, ini, fim, projeto_id=None):
    base = db.query(Lancamento).filter_by(owner_tipo=ot, owner_id=oid)
    if projeto_id is not None:
        base = base.filter(Lancamento.projeto_id == projeto_id)
    deb = sum(l.valor for l in _filtra_periodo(base.filter(Lancamento.conta_debito_id == conta_id), ini, fim).all())
    cred = sum(l.valor for l in _filtra_periodo(base.filter(Lancamento.conta_credito_id == conta_id), ini, fim).all())
    return deb, cred


def _mov(db, ot, oid, prefixo, sentido, ini, fim, projeto_id=None):
    """Movimento das analíticas sob `prefixo`, no sentido pedido ('credor' = C−D p/ receitas;
    'devedor' = D−C p/ deduções/despesas). `projeto_id` filtra a dimensão gerencial."""
    contas = [c for c in db.query(Conta).filter_by(owner_tipo=ot, owner_id=oid, tipo="analitica").all()
              if c.codigo == prefixo or c.codigo.startswith(prefixo + ".")]
    deb = cred = 0.0
    for c in contas:
        d, cr = _totais_conta(db, ot, oid, c.id, ini, fim, projeto_id=projeto_id)
        deb += d
        cred += cr
    return round(cred - deb if sentido == "credor" else deb - cred, 2)


def _detalhe_grupo(db, ot, oid, prefixos, sentido, ini, fim):
    """Composição nível 3 (analíticas com movimento) de um ou mais prefixos, no sentido pedido.
    Alimenta o modo Analítico da DRE (v5 §3.1) — Resumido usa só os totais de nível 2."""
    if isinstance(prefixos, str):
        prefixos = [prefixos]
    contas = db.query(Conta).filter_by(owner_tipo=ot, owner_id=oid, tipo="analitica").all()
    linhas = []
    for c in sorted(contas, key=lambda x: x.codigo):
        if not any(c.codigo == p or c.codigo.startswith(p + ".") for p in prefixos):
            continue
        d, cr = _totais_conta(db, ot, oid, c.id, ini, fim)
        val = round(cr - d if sentido == "credor" else d - cr, 2)
        if val:
            linhas.append({"codigo": c.codigo, "nome": c.nome, "valor": val})
    return linhas


def dre(db, owner_tipo, owner_id, ini=None, fim=None):
    """DRE societário (competência) a partir do livro (.docx §3). Deduções/despesas já com o sinal certo.
    Inclui `detalhe` (composição nível 3 por linha) p/ o toggle Analítico×Resumido (v5 §3.1)."""
    m = lambda pref, sen: _mov(db, owner_tipo, owner_id, pref, sen, ini, fim)
    det = lambda prefs, sen: _detalhe_grupo(db, owner_tipo, owner_id, prefs, sen, ini, fim)
    receita_bruta = round(m("4.1", "credor") + m("4.2", "credor"), 2)
    deducoes = m("4.3", "devedor")
    receita_liquida = round(receita_bruta - deducoes, 2)
    cmv_csp = round(m("5.1", "devedor") + m("5.2", "devedor"), 2)
    lucro_bruto = round(receita_liquida - cmv_csp, 2)
    desp_com = m("5.3", "devedor")
    desp_adm = m("5.4", "devedor")
    const_prov = m("5.6", "devedor")
    ebitda = round(lucro_bruto - desp_com - desp_adm - const_prov, 2)
    depreciacao = 0.0                                  # sem conta dedicada no seed
    ebit = round(ebitda - depreciacao, 2)
    resultado_financeiro = round(-m("5.5", "devedor"), 2)
    resultado_antes_impostos = round(ebit + resultado_financeiro, 2)
    impostos = 0.0                                     # Simples/DAS já em Deduções (4.3)
    lucro_liquido = round(resultado_antes_impostos - impostos, 2)
    return {
        "periodo": {"ini": ini.isoformat() if ini else None, "fim": fim.isoformat() if fim else None},
        "receita_bruta": receita_bruta, "deducoes": deducoes, "receita_liquida": receita_liquida,
        "cmv_csp": cmv_csp, "lucro_bruto": lucro_bruto,
        "despesas_comerciais": desp_com, "despesas_administrativas": desp_adm,
        "constituicao_provisoes": const_prov, "ebitda": ebitda,
        "depreciacao": depreciacao, "ebit": ebit,
        "resultado_financeiro": resultado_financeiro, "resultado_antes_impostos": resultado_antes_impostos,
        "impostos": impostos, "lucro_liquido": lucro_liquido,
        "obs": "Depreciação e Impostos = 0 (sem conta dedicada no seed; Simples/DAS já em Deduções). Refinar com contador.",
        "detalhe": {   # composição nível 3 por linha (modo Analítico)
            "receita_bruta": det(["4.1", "4.2"], "credor"),
            "deducoes": det("4.3", "devedor"),
            "cmv_csp": det(["5.1", "5.2"], "devedor"),
            "despesas_comerciais": det("5.3", "devedor"),
            "despesas_administrativas": det("5.4", "devedor"),
            "constituicao_provisoes": det("5.6", "devedor"),
            "resultado_financeiro": det("5.5", "devedor"),
        },
    }


# ── Balanço Patrimonial (v5 §4) ──────────────────────────────────────────────
def balanco(db, owner_tipo, owner_id, data_corte=None):
    """Posição patrimonial num instante: saldo ACUMULADO (do início até `data_corte`) dos grupos
    1/2/3. O resultado do exercício (Receitas − Despesas acumuladas) entra no PL → fecha por
    partida dobrada (Ativo = Passivo + PL). `data_corte` = fim; ini=None (desde o começo)."""
    s = lambda pref, sen: _mov(db, owner_tipo, owner_id, pref, sen, None, data_corte)
    ativo_circ = s("1.1", "devedor")
    ativo_ncirc = s("1.2", "devedor")
    total_ativo = round(ativo_circ + ativo_ncirc, 2)
    passivo_circ = s("2.1", "credor")
    passivo_ncirc = s("2.2", "credor")
    total_passivo = round(passivo_circ + passivo_ncirc, 2)
    pl_contas = s("3", "credor")
    resultado = round(s("4", "credor") - s("5", "devedor"), 2)   # lucro/prejuízo acumulado do período
    total_pl = round(pl_contas + resultado, 2)
    total_passivo_pl = round(total_passivo + total_pl, 2)
    return {
        "data_corte": data_corte.isoformat() if data_corte else None,
        "ativo": {"circulante": ativo_circ, "nao_circulante": ativo_ncirc, "total": total_ativo},
        "passivo": {"circulante": passivo_circ, "nao_circulante": passivo_ncirc, "total": total_passivo},
        "patrimonio_liquido": {"contas": pl_contas, "resultado_exercicio": resultado, "total": total_pl},
        "total_passivo_mais_pl": total_passivo_pl,
        "confere": abs(total_ativo - total_passivo_pl) < 0.01,
    }


# ── DRE por projeto / margem de contribuição (sub-projeto #5) ─────────────────
def margem_projeto(db, owner_tipo, owner_id, projeto_id, ini=None, fim=None):
    """Margem de contribuição de um projeto (v5 §5): receita − custo direto de produto −
    Provisão de Montagem − Provisão de Assistência Técnica − Provisão de Garantia − comissão.
    Garantia entra pelo **valor bruto** (custo real da loja); repasse à fábrica é controle à parte (§6.2).
    NÃO aloca despesa fixa (isso é o rateio da Auditoria)."""
    m = lambda pref, sen: _mov(db, owner_tipo, owner_id, pref, sen, ini, fim, projeto_id=projeto_id)
    receita = round(m("4.1", "credor") + m("4.2", "credor"), 2)
    custo_produto = m("5.1", "devedor")
    prov_montagem = m("5.6.02", "devedor")
    prov_assistencia = m("5.6.03", "devedor")
    prov_garantia = m("5.6.01", "devedor")
    comissao = m("5.3", "devedor")           # comissão do consultor + demais comerciais tagueados ao projeto
    margem = round(receita - custo_produto - prov_montagem - prov_assistencia - prov_garantia - comissao, 2)
    return {"projeto_id": projeto_id, "receita": receita, "custo_produto": custo_produto,
            "prov_montagem": prov_montagem, "prov_assistencia": prov_assistencia,
            "prov_garantia": prov_garantia, "comissao": comissao, "margem_contribuicao": margem}


def projetos_com_lancamento(db, owner_tipo, owner_id):
    rows = (db.query(Lancamento.projeto_id).filter_by(owner_tipo=owner_tipo, owner_id=owner_id)
            .filter(Lancamento.projeto_id.isnot(None)).distinct().all())
    return sorted(r[0] for r in rows if r[0])


def margem_todos_projetos(db, owner_tipo, owner_id, ini=None, fim=None):
    """Margem de contribuição de cada projeto com lançamento (ordenado por margem desc)."""
    res = [margem_projeto(db, owner_tipo, owner_id, p, ini, fim)
           for p in projetos_com_lancamento(db, owner_tipo, owner_id)]
    return sorted(res, key=lambda r: r["margem_contribuicao"], reverse=True)


# ── Auditoria / Reconciliação periódica (sub-projeto #6) ─────────────────────
BASES_RATEIO = ("proporcional_receita", "proporcional_custo_direto", "linear_por_projeto")


def reconciliar(db, owner_tipo, owner_id, ini=None, fim=None, metodologia="proporcional_receita"):
    """Rateia a despesa fixa do período (grupo 5.4) aos projetos → margem plena (full cost),
    e calcula a divergência residual vs. o resultado societário (DRE). Não persiste (ver fechar_periodo)."""
    if metodologia not in BASES_RATEIO:
        raise ValueError("metodologia de rateio inválida: %s" % metodologia)
    margens = margem_todos_projetos(db, owner_tipo, owner_id, ini, fim)
    despesas_fixas = _mov(db, owner_tipo, owner_id, "5.4", "devedor", ini, fim)

    def _peso(m):
        if metodologia == "proporcional_receita":
            return max(m["receita"], 0.0)
        if metodologia == "proporcional_custo_direto":
            return max(m["custo_produto"] + m["custo_servico"], 0.0)
        return 1.0   # linear_por_projeto

    total_peso = sum(_peso(m) for m in margens)
    alocacao = []
    for m in margens:
        w = _peso(m)
        rateado = round(despesas_fixas * (w / total_peso), 2) if total_peso > 0 else 0.0
        alocacao.append({
            "projeto_id": m["projeto_id"],
            "margem_contribuicao": m["margem_contribuicao"],
            "valor_rateado": rateado,
            "margem_plena": round(m["margem_contribuicao"] - rateado, 2),
        })
    soma_margem_plena = round(sum(a["margem_plena"] for a in alocacao), 2)
    resultado_societario = dre(db, owner_tipo, owner_id, ini, fim)["lucro_liquido"]
    divergencia = round(resultado_societario - soma_margem_plena, 2)
    return {
        "metodologia": metodologia,
        "despesas_fixas_periodo": despesas_fixas,
        "alocacao_por_projeto": alocacao,
        "soma_margem_plena": soma_margem_plena,
        "resultado_societario_oficial": resultado_societario,
        "divergencia_residual": divergencia,
        "nota_explicativa": (
            "%d projeto(s) no período; despesa fixa (grupo 5.4) R$ %.2f rateada por %s. "
            "A divergência é estrutural (itens não alocados a projeto: deduções, resultado financeiro, "
            "custos sem projeto, provisões ainda não realizadas) — tende a um piso pequeno, não a zero."
            % (len(alocacao), despesas_fixas, metodologia)),
    }


def fechar_periodo(db, owner_tipo, owner_id, ini=None, fim=None, metodologia="proporcional_receita"):
    """Calcula a reconciliação e persiste um PeriodoContabil (status='fechado')."""
    import json as _json
    rec = reconciliar(db, owner_tipo, owner_id, ini, fim, metodologia)
    p = PeriodoContabil(owner_tipo=owner_tipo, owner_id=owner_id, inicio=ini, fim=fim, status="fechado",
                        metodologia=metodologia, resultado_societario=rec["resultado_societario_oficial"],
                        soma_margem_plena=rec["soma_margem_plena"], divergencia_residual=rec["divergencia_residual"],
                        dados_json=_json.dumps(rec["alocacao_por_projeto"]))
    db.add(p)
    db.commit()
    return {"id": p.id, **rec}


def listar_periodos(db, owner_tipo, owner_id):
    ps = (db.query(PeriodoContabil).filter_by(owner_tipo=owner_tipo, owner_id=owner_id)
          .order_by(PeriodoContabil.criado_em.desc()).all())
    return [{"id": p.id, "inicio": p.inicio.isoformat() if p.inicio else None,
             "fim": p.fim.isoformat() if p.fim else None, "status": p.status,
             "metodologia": p.metodologia, "resultado_societario": p.resultado_societario,
             "soma_margem_plena": p.soma_margem_plena, "divergencia_residual": p.divergencia_residual}
            for p in ps]
