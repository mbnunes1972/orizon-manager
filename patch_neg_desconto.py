"""
patch_neg_desconto.py — Corrige validação de desconto na sidebar (neg-desconto)
para usar cfgGetDescontoMax() (que respeita _limiteAutorizado) em vez de cfgValidarDesconto()
"""
import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

OLD = """function negValidarLimiteDesconto(val){
  const disc = parseFloat(val) || 0;
  const v = cfgValidarDesconto(disc);
  const el = document.getElementById('neg-desconto');
  const hint = document.getElementById('neg-limite-hint');
  if(!v.ok){
    if(el){ el.style.borderColor='var(--err)'; el.style.color='var(--err)'; }
    if(hint){ hint.textContent='⚠ Limite do perfil: '+v.max+'%'; hint.style.display='block'; }
  } else {
    if(el){ el.style.borderColor=''; el.style.color=''; }
    if(hint){ hint.style.display='none'; }
  }
}"""

NEW = """function negValidarLimiteDesconto(val){
  const disc = parseFloat(val) || 0;
  const max  = cfgGetDescontoMax(); // respeita _limiteAutorizado se existir
  const el   = document.getElementById('neg-desconto');
  const hint = document.getElementById('neg-limite-hint');
  if(disc > max){
    if(el){ el.style.borderColor='var(--err)'; el.style.color='var(--err)'; }
    if(hint){
      const limiteBase = _usuarioAtual ? (_LIMITES_NIVEL[_usuarioAtual.nivel] || 10) : 10;
      hint.textContent = '⚠ Limite do perfil: ' + limiteBase + '%';
      hint.style.display = 'block';
    }
  } else {
    if(el){ el.style.borderColor=''; el.style.color=''; }
    if(hint){ hint.style.display='none'; }
  }
}"""

if OLD in html:
    html = html.replace(OLD, NEW, 1)
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(html)
    print("  ✓ PATCH - negValidarLimiteDesconto corrigido")
    print("  ✓ index.html atualizado com sucesso.")
else:
    print("  ✗ Trecho não encontrado")
    sys.exit(1)
