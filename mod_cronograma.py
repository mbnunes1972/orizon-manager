"""mod_cronograma.py — Cronograma do Ciclo (Modulos_Orizon_v11).

Na assinatura do contrato (D0 = ambas as partes assinaram — mesmo gatilho que constitui as
Provisões, Financeiro §6.4), constitui a data prevista de conclusão de cada etapa a partir do
Cronograma de Projeto Padrão (Config): data_prevista_conclusao = D0 + Σ(durações até a etapa,
inclusive). prazo_dias é a DURAÇÃO da etapa (dias corridos), não um offset absoluto desde D0.

data_conclusao (= CicloEtapa.concluido_em) nasce vazia — preenche quando a etapa é de fato
concluída. Idempotente por (projeto, etapa): reexecutar recomputa a data prevista a partir de D0.
"""
from datetime import timedelta

from database import CicloEtapa, Projeto


def cronograma_padrao(cfg):
    """Normaliza a lista de fases do Cronograma Padrão da config: [{codigo, prazo_dias, funcao_id}].
    funcao_id (→ Tabela de Funções, Modulos_Orizon_v12) é a FUNÇÃO responsável pela fase; None se não
    definida."""
    itens = (cfg or {}).get("cronograma_padrao") or []
    out = []
    for it in itens:
        cod = str((it or {}).get("codigo") or "").strip()
        if not cod:
            continue
        try:
            prazo = int((it or {}).get("prazo_dias") or 0)
        except (TypeError, ValueError):
            prazo = 0
        try:
            fid = int((it or {}).get("funcao_id")) if (it or {}).get("funcao_id") else None
        except (TypeError, ValueError):
            fid = None
        out.append({"codigo": cod, "prazo_dias": max(0, prazo), "funcao_id": fid})
    return out


def gerar_cronograma_projeto(db, projeto_nome, cfg, d0):
    """Para cada fase do Cronograma Padrão, cria/atualiza a etapa do projeto com
    data_prevista_conclusao = d0 + Σ(durações das etapas até esta, inclusive). prazo_dias é a DURAÇÃO
    da etapa (dias corridos). Não toca data de conclusão. Idempotente. Retorna as CicloEtapa afetadas."""
    afetadas = []
    acc = 0
    for fase in cronograma_padrao(cfg):
        acc += fase["prazo_dias"]
        prevista = d0 + timedelta(days=acc)
        reg = (db.query(CicloEtapa)
               .filter_by(projeto_nome=projeto_nome, etapa_codigo=fase["codigo"]).first())
        if reg is None:
            reg = CicloEtapa(projeto_nome=projeto_nome, etapa_codigo=fase["codigo"])
            db.add(reg)
        reg.data_prevista_conclusao = prevista
        # Herda a FUNÇÃO responsável do padrão (v12); não sobrescreve o funcionário já escolhido.
        reg.funcao_responsavel_id = fase.get("funcao_id")
        afetadas.append(reg)
    db.flush()
    return afetadas


# ── Fase A — prazo por fase validado contra o cronograma do projeto ──────────────────────────────

def limite_etapa(db, projeto_nome, etapa_codigo):
    """Limite do cronograma (data_prevista_conclusao) da etapa do projeto; None se não houver."""
    reg = (db.query(CicloEtapa)
           .filter_by(projeto_nome=projeto_nome, etapa_codigo=str(etapa_codigo)).first())
    return reg.data_prevista_conclusao if reg else None


def prazo_excede_limite(limite, prazo):
    """True se `prazo` ultrapassa o `limite` do cronograma. Sem limite (None) ou sem prazo (None) →
    False (nada a exceder). Igualar o limite NÃO excede."""
    if limite is None or prazo is None:
        return False
    return prazo > limite


def tem_cronograma(db, projeto_nome):
    """True se o projeto já tem ao menos uma etapa com data prevista (cronograma gerado)."""
    return (db.query(CicloEtapa)
            .filter(CicloEtapa.projeto_nome == projeto_nome,
                    CicloEtapa.data_prevista_conclusao.isnot(None)).first() is not None)


def garantir_cronograma(db, projeto_nome, cfg, d0):
    """Todo projeto deve ter cronograma: se ainda não tem, gera do Cronograma Padrão (cfg) a partir do
    d0. NÃO sobrescreve um cronograma existente. Retorna True se gerou agora, False se já existia."""
    if tem_cronograma(db, projeto_nome):
        return False
    gerar_cronograma_projeto(db, projeto_nome, cfg, d0)
    return True


def cronogramas(etapas, inicio, entrega, codigo_entrega):
    """Dois cronogramas derivados do MESMO Cronograma Padrão (mesmos prazos, âncoras opostas) — puro.
    `etapas`: lista ORDENADA de (codigo, prazo_dias). `codigo_entrega` marca a etapa de ENTREGA ao cliente
    (âncora do regressivo; default = última). `inicio` = âncora do progressivo. Retorna
    [{codigo, progressivo, regressivo, folga_dias}]:
      - progressivo[i] = inicio + Σ prazos ATÉ i (inclusive) — o quanto ANTES a etapa pode terminar;
      - regressivo[i] = entrega recuada pelos prazos entre i e a entrega (o Prazo LIMITE); etapas DEPOIS
        da entrega avançam a partir dela;
      - folga_dias = (regressivo − progressivo).days (negativa = o prazo não cabe no padrão)."""
    prog = {}
    acc = inicio
    for cod, pz in etapas:
        acc = acc + timedelta(days=int(pz or 0))
        prog[cod] = acc
    idx = next((i for i, (c, _) in enumerate(etapas) if c == codigo_entrega), len(etapas) - 1)
    reg = {}
    for j, (cod, _) in enumerate(etapas):
        if j <= idx:
            dias = sum(int(p or 0) for _, p in etapas[j + 1:idx + 1])
            reg[cod] = entrega - timedelta(days=dias)
        else:
            dias = sum(int(p or 0) for _, p in etapas[idx + 1:j + 1])
            reg[cod] = entrega + timedelta(days=dias)
    return [{"codigo": cod, "progressivo": prog[cod], "regressivo": reg[cod],
             "folga_dias": (reg[cod] - prog[cod]).days} for cod, _ in etapas]


def cronograma_do_projeto(cfg, inicio, entrega, codigo_entrega="16"):
    """Dois cronogramas do projeto a partir do Cronograma Padrão (cfg) + âncoras (início, entrega).
    Extrai as etapas/prazos do padrão na ordem e delega a `cronogramas()`. `codigo_entrega` default = "16"
    (Entrega no cliente)."""
    etapas = [(f["codigo"], f["prazo_dias"]) for f in cronograma_padrao(cfg)]
    return cronogramas(etapas, inicio, entrega, codigo_entrega)


def cabe_no_cronograma(resultado):
    """True se NENHUMA etapa tem folga negativa — o prazo do cliente CABE no Cronograma Padrão. Se folga
    negativa em alguma etapa, o projeto precisa do cronograma PRÓPRIO (edição + senha de gerente/diretor)."""
    return all(e["folga_dias"] >= 0 for e in (resultado or []))


def cronograma_projeto_view(db, projeto_nome, cfg, codigo_entrega="16"):
    """Dados das 3 datas do ciclo por etapa — **Planejada** (`CicloEtapa.data_prevista_conclusao`, do
    Cronograma Padrão gerado na assinatura), **Prazo Limite** (regressivo, âncora `Projeto.data_entrega`)
    e **Executada** (`concluido_em`). Folga = Limite − Planejada. Regressivo/folga só saem se `data_entrega`
    estiver definida. Datas em ISO (ou None). Retorna [{codigo, prazo_limite, planejado, executado,
    folga_dias}]."""
    p = db.get(Projeto, projeto_nome)
    entrega = getattr(p, "data_entrega", None) if p else None
    etapas = [(f["codigo"], f["prazo_dias"]) for f in cronograma_padrao(cfg)]
    # Prazo Limite = regressivo (depende só da entrega); reusa cronogramas() e usa só o regressivo.
    reg = ({x["codigo"]: x["regressivo"] for x in cronogramas(etapas, entrega, entrega, codigo_entrega)}
           if entrega else {})
    cetapas = {e.etapa_codigo: e for e in db.query(CicloEtapa).filter_by(projeto_nome=projeto_nome).all()}
    _iso = lambda d: d.isoformat() if d else None
    out = []
    for cod, _ in etapas:
        ce = cetapas.get(cod)
        planejada = getattr(ce, "data_prevista_conclusao", None) if ce else None
        limite = reg.get(cod)
        executada = getattr(ce, "concluido_em", None) if ce else None
        folga = (limite - planejada).days if (limite and planejada) else None
        out.append({"codigo": cod, "prazo_limite": _iso(limite), "planejado": _iso(planejada),
                    "executado": _iso(executada), "folga_dias": folga})
    return out
