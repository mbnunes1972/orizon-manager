import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

# PATCH 1 — ao cancelar autorização na sidebar, volta ao valor anterior
OLD1 = """async function negConfirmarDesconto(){
  const disc = parseFloat(document.getElementById('neg-desconto').value) || 0;
  const max  = cfgGetDescontoMax();
  if(disc <= max) return;
  // Abre modal de autorização passando contexto 'sidebar' para não mexer em mp-desconto
  const ok = await abrirModalAutorizacaoSidebar(disc, max);
  if(ok){
    const el   = document.getElementById('neg-desconto');
    const hint = document.getElementById('neg-limite-hint');
    const btn  = document.getElementById('neg-desc-confirmar');
    if(el){ el.style.borderColor=''; el.style.color=''; el._prev = disc; }
    if(hint){ hint.style.display='none'; }
    if(btn){ btn.style.display='none'; }
    // Salva o desconto no backend
    agendarCalculo();
    agendarSalvarDesconto();
  }
}"""

NEW1 = """async function negConfirmarDesconto(){
  const disc = parseFloat(document.getElementById('neg-desconto').value) || 0;
  const max  = cfgGetDescontoMax();
  if(disc <= max) return;
  const ok = await abrirModalAutorizacaoSidebar(disc, max);
  const el   = document.getElementById('neg-desconto');
  const hint = document.getElementById('neg-limite-hint');
  const btn  = document.getElementById('neg-desc-confirmar');
  if(ok){
    // Autorizado — aceita o novo desconto
    if(el){ el.style.borderColor=''; el.style.color=''; el._prev = disc; }
    if(hint){ hint.style.display='none'; }
    if(btn){ btn.style.display='none'; }
    agendarCalculo();
    agendarSalvarDesconto();
  } else {
    // Cancelado — volta ao valor anterior
    const prev = (el && el._prev != null) ? parseFloat(el._prev) : max;
    if(el){ el.value = prev; el.style.borderColor=''; el.style.color=''; }
    if(hint){ hint.style.display='none'; }
    if(btn){ btn.style.display='none'; }
    negSyncModal(prev);
    agendarCalculo();
  }
}"""

# PATCH 2 — ao carregar margens do projeto, seta _limiteAutorizado com desconto salvo
OLD2 = """async function carregarMargensSalvas(){
  if(!projetoAtivo) return;
  _limiteAutorizado = null; // reseta ao trocar de projeto
  _descAdicional  = {};
  _descIndividual = {};"""

NEW2 = """async function carregarMargensSalvas(){
  if(!projetoAtivo) return;
  // Ao carregar projeto, o desconto salvo passa a ser o limite autorizado
  // (foi aprovado em algum momento anterior)
  const descontoSalvo = parseFloat((projetoAtivo.margens||{}).desconto_pct) || 0;
  const limiteBase = _usuarioAtual ? (_LIMITES_NIVEL[_usuarioAtual.nivel] || 10) : 10;
  _limiteAutorizado = descontoSalvo > limiteBase ? descontoSalvo : null;
  _descAdicional  = {};
  _descIndividual = {};"""

patches = [
    ("PATCH 1 - cancelar autorização volta ao valor anterior", OLD1, NEW1),
    ("PATCH 2 - desconto salvo vira limite autorizado",        OLD2, NEW2),
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
