import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

# PATCH 1 — lerMargensNegociacao inclui incluir_custos
OLD1 = """function lerMargensNegociacao(){
  const m = (projetoAtivo && projetoAtivo.margens) || {};
  return {
    desconto_pct:             parseFloat(document.getElementById('neg-desconto').value) || 0,
    fora_da_sede:             !!m.fora_da_sede,
    custo_viagem:             parseFloat(m.custo_viagem) || 0,
    comissao_arq_pct:         parseFloat(m.comissao_arq_pct) || 0,
    comissao_arq_ativa:       !!m.comissao_arq_ativa,
    fidelidade_pct:           parseFloat(m.fidelidade_pct) || 0,
    fidelidade_ativa:         !!m.fidelidade_ativa,
    custo_financeiro_pct: _acrescimoFin,  // taxa de retencao da forma de pagamento selecionada
    brinde:               parseFloat(m.brinde) || 0,
    brinde_ativo:         !!m.brinde_ativo,
  };
}"""

NEW1 = """function lerMargensNegociacao(){
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

# PATCH 2 — após salvar parâmetros, recarregar negociação para atualizar valor bruto
OLD2 = """  if(salvar && projetoAtivo){
    const id = s => document.getElementById(s);
    const mg = {
      desconto_pct:          parseFloat(id('mp-desconto').value)||0,
      comissao_arq_ativa:    id('mp-arq-ativa').checked,
      comissao_arq_pct:   parseFloat(id('mp-arq-pct').value)||0,
      fidelidade_ativa:   id('mp-fid-ativa').checked,
      fidelidade_pct:     parseFloat(id('mp-fid-pct').value)||0,
      fora_da_sede:       id('mp-fora-sede').checked,
      custo_viagem:       parseFloat(id('mp-viagem').value)||0,
      brinde_ativo:       id('mp-brinde-ativo').checked,
      brinde:             parseFloat(id('mp-brinde').value)||0,
      incluir_custos:     document.getElementById('mp-incluir-custos')?.checked || false,"""

NEW2 = """  if(salvar && projetoAtivo){
    const id = s => document.getElementById(s);
    const novoIncluirCustos = document.getElementById('mp-incluir-custos')?.checked || false;
    const mg = {
      desconto_pct:          parseFloat(id('mp-desconto').value)||0,
      comissao_arq_ativa:    id('mp-arq-ativa').checked,
      comissao_arq_pct:   parseFloat(id('mp-arq-pct').value)||0,
      fidelidade_ativa:   id('mp-fid-ativa').checked,
      fidelidade_pct:     parseFloat(id('mp-fid-pct').value)||0,
      fora_da_sede:       id('mp-fora-sede').checked,
      custo_viagem:       parseFloat(id('mp-viagem').value)||0,
      brinde_ativo:       id('mp-brinde-ativo').checked,
      brinde:             parseFloat(id('mp-brinde').value)||0,
      incluir_custos:     novoIncluirCustos,"""

patches = [
    ("PATCH 1 - lerMargensNegociacao inclui incluir_custos", OLD1, NEW1),
    ("PATCH 2 - salva incluir_custos corretamente",          OLD2, NEW2),
]

erros = []
for nome, old, new in patches:
    if old in html:
        html = html.replace(old, new, 1)
        print(f"  ✓ {nome}")
    else:
        print(f"  ✗ {nome} — trecho não encontrado")
        erros.append(nome)

if erros:
    print(f"\n  ATENÇÃO: {len(erros)} patch(es) não aplicado(s). Arquivo não foi salvo.")
    sys.exit(1)

with open(INDEX, "w", encoding="utf-8") as f:
    f.write(html)

print(f"\n  ✓ index.html atualizado com sucesso.")
