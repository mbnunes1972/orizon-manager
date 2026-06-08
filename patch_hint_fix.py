"""
patch_hint_fix.py — Corrige hint: após autorização, só mostra se ultrapassar limite do autorizador
"""
import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

OLD = """function mpDescontoValidar(el){
  const val  = parseFloat(el.value) || 0;
  const max  = cfgGetDescontoMax();
  const hint = document.getElementById('mp-desc-hint');
  if(val > max){
    el.style.borderColor = 'var(--err)';
    if(hint){
      const limiteBase = _usuarioAtual ? (_LIMITES_NIVEL[_usuarioAtual.nivel] || 10) : 10;
      hint.textContent = `Limite do seu perfil: ${limiteBase}%. Salvar solicitará autorização.`;
      hint.style.display = 'block';
    }
  } else {
    el.style.borderColor = '';
    if(hint){ hint.style.display = 'none'; }
  }
}"""

NEW = """function mpDescontoValidar(el){
  const val  = parseFloat(el.value) || 0;
  const max  = cfgGetDescontoMax(); // retorna _limiteAutorizado se existir, senão limite do perfil
  const hint = document.getElementById('mp-desc-hint');
  if(val > max){
    el.style.borderColor = 'var(--err)';
    if(hint){
      if(_limiteAutorizado !== null){
        // Já foi autorizado — informa que precisa de nova autorização para esse valor maior
        hint.textContent = `Desconto acima do limite autorizado (${_limiteAutorizado}%). Salvar solicitará nova autorização.`;
      } else {
        const limiteBase = _usuarioAtual ? (_LIMITES_NIVEL[_usuarioAtual.nivel] || 10) : 10;
        hint.textContent = `Limite do seu perfil: ${limiteBase}%. Salvar solicitará autorização.`;
      }
      hint.style.display = 'block';
    }
  } else {
    el.style.borderColor = '';
    if(hint){ hint.style.display = 'none'; }
  }
}"""

if OLD in html:
    html = html.replace(OLD, NEW, 1)
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(html)
    print("  ✓ PATCH - hint inteligente após autorização")
    print("  ✓ index.html atualizado com sucesso.")
else:
    print("  ✗ Trecho não encontrado")
    sys.exit(1)
