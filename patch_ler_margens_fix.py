import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

OLD = """function lerMargensNegociacao(){
  const m = (projetoAtivo && projetoAtivo.margens) || {};
  return {
    desconto_pct:             parseFloat(document.getElementById('neg-desconto').value) || 0,
    fora_da_sede:             !!m.fora_da_sede,
    custo_viagem:             parseFloat(m.custo_viagem) || 0,
    comissao_arq_pct:         parseFloat(m.comissao_arq_pct) || 0,
    comissao_arq_ativa:       !!m.comissao_arq_ativa,
    fidelidade_pct:           parseFloat(m.fidelidade_pct) || 0,
    fidelidade_ativa:         !!m.fidelidade_ativa,
    custo_financeiro_pct: _acrescimoFin,
    brinde:               parseFloat(m.brinde) || 0,
    brinde_ativo:         !!m.brinde_ativo,
    incluir_custos:       !!m.incluir_custos,
  };
}"""

NEW = """function lerMargensNegociacao(){
  const m = (projetoAtivo && projetoAtivo.margens) || {};
  // Se o modal de parâmetros está aberto, lê o toggle diretamente
  const modalAberto = document.getElementById('modal-params')?.style.display === 'flex';
  const incluirCustos = modalAberto
    ? (document.getElementById('mp-incluir-custos')?.checked || false)
    : !!m.incluir_custos;
  return {
    desconto_pct:             parseFloat(document.getElementById('neg-desconto').value) || 0,
    fora_da_sede:             !!m.fora_da_sede,
    custo_viagem:             parseFloat(m.custo_viagem) || 0,
    comissao_arq_pct:         parseFloat(m.comissao_arq_pct) || 0,
    comissao_arq_ativa:       !!m.comissao_arq_ativa,
    fidelidade_pct:           parseFloat(m.fidelidade_pct) || 0,
    fidelidade_ativa:         !!m.fidelidade_ativa,
    custo_financeiro_pct: _acrescimoFin,
    brinde:               parseFloat(m.brinde) || 0,
    brinde_ativo:         !!m.brinde_ativo,
    incluir_custos:       incluirCustos,
  };
}"""

if OLD in html:
    html = html.replace(OLD, NEW, 1)
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(html)
    print("  ✓ PATCH - lerMargensNegociacao lê toggle diretamente")
else:
    print("  ✗ Trecho não encontrado")
    sys.exit(1)
