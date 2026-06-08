import os, sys

MAIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")

with open(MAIN, "r", encoding="utf-8") as f:
    content = f.read()

OLD = """                m_atual.update({
                    "desconto_pct":          float(req.get("desconto_pct",          m_atual.get("desconto_pct", 0))),
                    "custo_financeiro_pct":  float(req.get("custo_financeiro_pct",  m_atual.get("custo_financeiro_pct", 0))),
                    "fora_da_sede":          bool( req.get("fora_da_sede",           m_atual.get("fora_da_sede", False))),
                    "custo_viagem":       float(req.get("custo_viagem",        m_atual.get("custo_viagem", 0))),
                    "brinde":             float(req.get("brinde",              m_atual.get("brinde", 0))),
                    "brinde_ativo":       bool( req.get("brinde_ativo",        m_atual.get("brinde_ativo", False))),
                    "comissao_arq_pct":   float(req.get("comissao_arq_pct",   m_atual.get("comissao_arq_pct", 0))),
                    "comissao_arq_ativa": bool( req.get("comissao_arq_ativa",  m_atual.get("comissao_arq_ativa", False))),
                    "fidelidade_pct":     float(req.get("fidelidade_pct",     m_atual.get("fidelidade_pct", 0))),
                    "fidelidade_ativa":   bool( req.get("fidelidade_ativa",    m_atual.get("fidelidade_ativa", False))),
                })"""

NEW = """                m_atual.update({
                    "desconto_pct":          float(req.get("desconto_pct",          m_atual.get("desconto_pct", 0))),
                    "custo_financeiro_pct":  float(req.get("custo_financeiro_pct",  m_atual.get("custo_financeiro_pct", 0))),
                    "fora_da_sede":          bool( req.get("fora_da_sede",           m_atual.get("fora_da_sede", False))),
                    "custo_viagem":       float(req.get("custo_viagem",        m_atual.get("custo_viagem", 0))),
                    "brinde":             float(req.get("brinde",              m_atual.get("brinde", 0))),
                    "brinde_ativo":       bool( req.get("brinde_ativo",        m_atual.get("brinde_ativo", False))),
                    "comissao_arq_pct":   float(req.get("comissao_arq_pct",   m_atual.get("comissao_arq_pct", 0))),
                    "comissao_arq_ativa": bool( req.get("comissao_arq_ativa",  m_atual.get("comissao_arq_ativa", False))),
                    "fidelidade_pct":     float(req.get("fidelidade_pct",     m_atual.get("fidelidade_pct", 0))),
                    "fidelidade_ativa":   bool( req.get("fidelidade_ativa",    m_atual.get("fidelidade_ativa", False))),
                    "incluir_custos":     bool( req.get("incluir_custos",      m_atual.get("incluir_custos", False))),
                })"""

if OLD in content:
    content = content.replace(OLD, NEW, 1)
    with open(MAIN, "w", encoding="utf-8") as f:
        f.write(content)
    print("  \u2713 PATCH - main.py salva incluir_custos")
else:
    print("  \u2717 Trecho não encontrado")
    sys.exit(1)
