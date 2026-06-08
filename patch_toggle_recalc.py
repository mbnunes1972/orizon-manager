import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

# PATCH 1 — adiciona recálculo ao mpToggleArq, Fid, Viagem e Brinde
OLD1 = """function mpToggleArq(){
  const cb=document.getElementById('mp-arq-ativa'), inp=document.getElementById('mp-arq-pct');
  inp.disabled=!cb.checked; inp.style.opacity=cb.checked?'1':'0.35';
}
function mpToggleFid(){
  const cb=document.getElementById('mp-fid-ativa'), inp=document.getElementById('mp-fid-pct');
  inp.disabled=!cb.checked; inp.style.opacity=cb.checked?'1':'0.35';
}
function mpToggleViagem(){
  const cb  = document.getElementById('mp-fora-sede');
  const inp = document.getElementById('mp-viagem');
  inp.disabled = !cb.checked;
  inp.style.opacity = cb.checked ? '1' : '0.35';
}"""

NEW1 = """function mpToggleArq(){
  const cb=document.getElementById('mp-arq-ativa'), inp=document.getElementById('mp-arq-pct');
  inp.disabled=!cb.checked; inp.style.opacity=cb.checked?'1':'0.35';
  mpRecalcularEstruturalModal();
}
function mpToggleFid(){
  const cb=document.getElementById('mp-fid-ativa'), inp=document.getElementById('mp-fid-pct');
  inp.disabled=!cb.checked; inp.style.opacity=cb.checked?'1':'0.35';
  mpRecalcularEstruturalModal();
}
function mpToggleViagem(){
  const cb  = document.getElementById('mp-fora-sede');
  const inp = document.getElementById('mp-viagem');
  inp.disabled = !cb.checked;
  inp.style.opacity = cb.checked ? '1' : '0.35';
  mpRecalcularEstruturalModal();
}

// Recalcula estrutural em _negBaseValues com base no estado atual dos toggles do modal
function mpRecalcularEstruturalModal(){
  if(!projetoAtivo || !_negBaseValues || !_negBaseValues.length) return;
  const id = s => document.getElementById(s);
  const mg = {
    incluir_custos:     id('mp-incluir-custos')?.checked || false,
    comissao_arq_ativa: id('mp-arq-ativa')?.checked || false,
    comissao_arq_pct:   parseFloat(id('mp-arq-pct')?.value) || 0,
    fidelidade_ativa:   id('mp-fid-ativa')?.checked || false,
    fidelidade_pct:     parseFloat(id('mp-fid-pct')?.value) || 0,
    fora_da_sede:       id('mp-fora-sede')?.checked || false,
    custo_viagem:       parseFloat(id('mp-viagem')?.value) || 0,
    brinde_ativo:       id('mp-brinde-ativo')?.checked || false,
    brinde:             parseFloat(id('mp-brinde')?.value) || 0,
  };
  const ambs = projetoAtivo.ambientes || [];
  const brutosCliente = calcularValorBrutoCliente(mg);
  _negBaseValues = _negBaseValues.map(b => {
    const amb = ambs.find(a => a.arquivo === b.arquivo);
    return { ...b, estrutural: brutosCliente[b.arquivo] || (amb?.total || b.estrutural) };
  });
  mpAtualizarApoio();
}"""

# PATCH 2 — mpToggleBrinde também chama recálculo
OLD2 = """function mpToggleBrinde(){"""
NEW2 = """function mpToggleBrindeRecalc(){ mpRecalcularEstruturalModal(); }
function mpToggleBrinde(){"""

# PATCH 3 — adicionar chamada ao mpToggleBrindeRecalc no onchange do brinde
OLD3 = """<input type="checkbox" id="mp-brinde-ativo" onchange="mpToggleBrinde();agendarDiscriminacao()">"""
NEW3 = """<input type="checkbox" id="mp-brinde-ativo" onchange="mpToggleBrinde();mpToggleBrindeRecalc();agendarDiscriminacao()">"""

# PATCH 4 — mpToggleIncluirCustos também chama recálculo
OLD4 = """function mpToggleIncluirCustos(){
  // Quando ativado, recalcula o valor bruto do cliente incluindo os custos
  agendarDiscriminacao();
  // Força recalculo das margens salvas para atualizar a tela de negociação
  if(projetoAtivo){
    const mg = lerMargensNegociacao();
    mg.incluir_custos = document.getElementById('mp-incluir-custos')?.checked || false;
    calcularValorBrutoCliente(mg);
  }
}"""

NEW4 = """function mpToggleIncluirCustos(){
  mpRecalcularEstruturalModal();
  agendarDiscriminacao();
}"""

patches = [
    ("PATCH 1 - toggles recalculam estrutural", OLD1, NEW1),
    ("PATCH 2 - mpToggleBrindeRecalc",          OLD2, NEW2),
    ("PATCH 3 - onchange brinde chama recalc",  OLD3, NEW3),
    ("PATCH 4 - mpToggleIncluirCustos simplif", OLD4, NEW4),
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
