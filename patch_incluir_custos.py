import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

# PATCH 1 — Adiciona toggle "Incluir custos adicionais?" no modal, antes do desconto
OLD1 = """    <div class="toggle-row">
      <span class="toggle-label" style="flex:1">Desconto de venda</span>
      <input type="number" class="toggle-input" id="mp-desconto" min="0" max="100" step="0.5" value="0"
             onfocus="this._prev=this.value"
             oninput="mpDescontoValidar(this); negSyncSidebar(this.value); agendarDiscriminacao()"
             onkeydown="mpDescontoKeydown(event,this)">
      <div id="mp-desc-hint" style="display:none;font-size:10px;color:var(--err);margin-top:4px;grid-column:1/-1"></div>
      <span class="toggle-unit">%</span>
    </div>"""

NEW1 = """    <!-- Toggle: Incluir custos adicionais ao valor bruto -->
    <div class="toggle-row" style="background:rgba(239,159,39,.06);border:1px solid rgba(239,159,39,.2);border-radius:8px;padding:10px 12px;margin-bottom:4px">
      <span class="toggle-label" style="flex:1;color:var(--warn)">Incluir custos adicionais?</span>
      <label class="sw" style="margin-right:8px">
        <input type="checkbox" id="mp-incluir-custos" onchange="mpToggleIncluirCustos()">
        <span class="sw-slider"></span>
      </label>
      <span style="font-size:10px;color:var(--muted);max-width:140px;line-height:1.3">
        Acrescenta custos ao valor bruto do cliente
      </span>
    </div>
    <div class="toggle-row">
      <span class="toggle-label" style="flex:1">Desconto de venda</span>
      <input type="number" class="toggle-input" id="mp-desconto" min="0" max="100" step="0.5" value="0"
             onfocus="this._prev=this.value"
             oninput="mpDescontoValidar(this); negSyncSidebar(this.value); agendarDiscriminacao()"
             onkeydown="mpDescontoKeydown(event,this)">
      <div id="mp-desc-hint" style="display:none;font-size:10px;color:var(--err);margin-top:4px;grid-column:1/-1"></div>
      <span class="toggle-unit">%</span>
    </div>"""

# PATCH 2 — Adiciona incluir_custos ao snapshot e ao save
OLD2 = """  _mpSnapshot = {
    desconto_pct:       descontoAtual,
    comissao_arq_ativa: !!m.comissao_arq_ativa,
    comissao_arq_pct:   m.comissao_arq_pct || 0,
    fidelidade_ativa:   !!m.fidelidade_ativa,
    fidelidade_pct:     m.fidelidade_pct || 0,
    fora_da_sede:       !!m.fora_da_sede,
    custo_viagem:       m.custo_viagem || 0,
    brinde_ativo:       !!m.brinde_ativo,
    brinde:             m.brinde || 0,
  };"""

NEW2 = """  // Carrega toggle incluir_custos
  const incEl = document.getElementById('mp-incluir-custos');
  if(incEl) incEl.checked = !!m.incluir_custos;

  _mpSnapshot = {
    desconto_pct:       descontoAtual,
    comissao_arq_ativa: !!m.comissao_arq_ativa,
    comissao_arq_pct:   m.comissao_arq_pct || 0,
    fidelidade_ativa:   !!m.fidelidade_ativa,
    fidelidade_pct:     m.fidelidade_pct || 0,
    fora_da_sede:       !!m.fora_da_sede,
    custo_viagem:       m.custo_viagem || 0,
    brinde_ativo:       !!m.brinde_ativo,
    brinde:             m.brinde || 0,
    incluir_custos:     !!m.incluir_custos,
  };"""

# PATCH 3 — Restaurar incluir_custos ao cancelar
OLD3 = """    id('mp-brinde-ativo').checked = s.brinde_ativo;
    id('mp-brinde').value         = s.brinde;
    mpToggleArq(); mpToggleFid(); mpToggleViagem(); mpToggleBrinde();
    negSyncSidebar(s.desconto_pct);
    _mpSnapshot = null;
    return;"""

NEW3 = """    id('mp-brinde-ativo').checked = s.brinde_ativo;
    id('mp-brinde').value         = s.brinde;
    const incEl2 = document.getElementById('mp-incluir-custos');
    if(incEl2) incEl2.checked = !!s.incluir_custos;
    mpToggleArq(); mpToggleFid(); mpToggleViagem(); mpToggleBrinde();
    negSyncSidebar(s.desconto_pct);
    _mpSnapshot = null;
    return;"""

# PATCH 4 — Incluir incluir_custos no save
OLD4 = """    const mg = {
      desconto_pct:          parseFloat(id('mp-desconto').value)||0,
      comissao_arq_ativa:    id('mp-arq-ativa').checked,
      comissao_arq_pct:   parseFloat(id('mp-arq-pct').value)||0,
      fidelidade_ativa:   id('mp-fid-ativa').checked,
      fidelidade_pct:     parseFloat(id('mp-fid-pct').value)||0,
      fora_da_sede:       id('mp-fora-sede').checked,
      custo_viagem:       parseFloat(id('mp-viagem').value)||0,
      brinde_ativo:       id('mp-brinde-ativo').checked,
      brinde:             parseFloat(id('mp-brinde').value)||0,"""

NEW4 = """    const mg = {
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

# PATCH 5 — Função mpToggleIncluirCustos + cálculo do valor bruto do cliente
OLD5 = """function mpDescontoValidar(el){"""

NEW5 = """function mpToggleIncluirCustos(){
  // Quando ativado, recalcula o valor bruto do cliente incluindo os custos
  agendarDiscriminacao();
  // Força recalculo das margens salvas para atualizar a tela de negociação
  if(projetoAtivo){
    const mg = lerMargensNegociacao();
    mg.incluir_custos = document.getElementById('mp-incluir-custos')?.checked || false;
    calcularValorBrutoCliente(mg);
  }
}

function calcularValorBrutoCliente(mg){
  // Calcula o valor bruto que o cliente vê, com ou sem custos adicionais
  // Retorna um map arquivo -> valor_bruto_cliente
  const ambs = (projetoAtivo && projetoAtivo.ambientes) || [];
  const resultado = {};
  ambs.forEach(amb => {
    let bruto = amb.total || 0;
    if(mg.incluir_custos){
      // Gross-up: acrescenta custos ao valor bruto
      if(mg.comissao_arq_ativa && mg.comissao_arq_pct > 0)
        bruto = bruto / (1 - mg.comissao_arq_pct / 100);
      if(mg.fidelidade_ativa && mg.fidelidade_pct > 0)
        bruto = bruto / (1 - mg.fidelidade_pct / 100);
      const n_ambs = ambs.length || 1;
      if(mg.fora_da_sede && mg.custo_viagem > 0)
        bruto = bruto + (mg.custo_viagem / n_ambs);
      if(mg.brinde_ativo && mg.brinde > 0)
        bruto = bruto + (mg.brinde / n_ambs);
    }
    resultado[amb.arquivo] = Math.round(bruto * 100) / 100;
  });
  return resultado;
}

function mpDescontoValidar(el){"""

# PATCH 6 — Usar calcularValorBrutoCliente no carregarNegociacao
OLD6 = """  window._negBaseValues = _negBaseValues = baseResults.map((res, i) => ({
    arquivo:    allAmbs[i].arquivo,
    nome:       allAmbs[i].ambiente||allAmbs[i].projeto||allAmbs[i].arquivo,
    val_bruto:  allAmbs[i].total,
    estrutural: allAmbs[i].total,  // valor bruto original do XML — parâmetros internos não afetam o cliente
    margem_interna: rnd(res.valor_liquido_avista),  // valor líquido da loja (uso interno)
  }));"""

NEW6 = """  // Calcula valor bruto do cliente (com ou sem custos adicionais)
  const brutosCliente = calcularValorBrutoCliente(mg);
  window._negBaseValues = _negBaseValues = baseResults.map((res, i) => ({
    arquivo:    allAmbs[i].arquivo,
    nome:       allAmbs[i].ambiente||allAmbs[i].projeto||allAmbs[i].arquivo,
    val_bruto:  allAmbs[i].total,
    estrutural: brutosCliente[allAmbs[i].arquivo] || allAmbs[i].total,
    margem_interna: rnd(res.valor_liquido_avista),  // valor líquido da loja (uso interno)
  }));"""

patches = [
    ("PATCH 1 - toggle Incluir custos adicionais",     OLD1, NEW1),
    ("PATCH 2 - snapshot incluir_custos",              OLD2, NEW2),
    ("PATCH 3 - restaurar incluir_custos ao cancelar", OLD3, NEW3),
    ("PATCH 4 - salvar incluir_custos",                OLD4, NEW4),
    ("PATCH 5 - mpToggleIncluirCustos + cálculo",      OLD5, NEW5),
    ("PATCH 6 - usar calcularValorBrutoCliente",       OLD6, NEW6),
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
