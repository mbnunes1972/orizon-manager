"""
patch_limite_autorizado.py — Corrige hint após autorização delegada
Após autorização bem-sucedida, armazena o limite do autorizador e
cfgGetDescontoMax() passa a retorná-lo até o modal ser fechado.
"""
import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

# PATCH 1 — cfgGetDescontoMax considera _limiteAutorizado
OLD1 = """function cfgGetDescontoMax(){
  if(_usuarioAtual && _usuarioAtual.nivel){
    return _LIMITES_NIVEL[_usuarioAtual.nivel] || 10;
  }
  return parseFloat((_perfilAtivo.config && _perfilAtivo.config.desconto_max_pct) || 100);
}"""

NEW1 = """let _limiteAutorizado = null; // limite temporário após autorização delegada

function cfgGetDescontoMax(){
  if(_limiteAutorizado !== null) return _limiteAutorizado;
  if(_usuarioAtual && _usuarioAtual.nivel){
    return _LIMITES_NIVEL[_usuarioAtual.nivel] || 10;
  }
  return parseFloat((_perfilAtivo.config && _perfilAtivo.config.desconto_max_pct) || 100);
}"""

# PATCH 2 — ao confirmar autorização, armazena limite do autorizador e limpa hint
OLD2 = """    if(d.ok){ showToast(`Desconto autorizado por ${d.autorizador.nome}`); fecharModalAutorizacao(true); }"""

NEW2 = """    if(d.ok){
      // Armazena limite do autorizador temporariamente
      _limiteAutorizado = _LIMITES_NIVEL[d.autorizador.nivel] || 50;
      // Limpa hint e borda vermelha do campo
      const el = document.getElementById('mp-desconto');
      const hint = document.getElementById('mp-desc-hint');
      if(el) el.style.borderColor = '';
      if(hint) hint.style.display = 'none';
      showToast(`Desconto autorizado por ${d.autorizador.nome} (limite ${_limiteAutorizado}%)`);
      fecharModalAutorizacao(true);
    }"""

# PATCH 3 — ao fechar o modal (salvar ou cancelar), reseta _limiteAutorizado
OLD3 = """async function fecharModalParams(salvar){
  document.getElementById('modal-params').style.display = 'none';
  if(!salvar && _mpSnapshot){"""

NEW3 = """async function fecharModalParams(salvar){
  document.getElementById('modal-params').style.display = 'none';
  _limiteAutorizado = null; // reseta limite temporário ao fechar modal
  if(!salvar && _mpSnapshot){"""

# PATCH 4 — mpDescontoValidar também limpa hint se dentro do limite autorizado
OLD4 = """function mpDescontoValidar(el){
  const val  = parseFloat(el.value) || 0;
  const max  = cfgGetDescontoMax();
  const hint = document.getElementById('mp-desc-hint');
  if(val > max){
    el.style.borderColor = 'var(--err)';
    if(hint){ hint.textContent = `Limite do seu perfil: ${max}%. Salvar solicitará autorização.`; hint.style.display = 'block'; }
  } else {
    el.style.borderColor = '';
    if(hint){ hint.style.display = 'none'; }
  }
}"""

NEW4 = """function mpDescontoValidar(el){
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

patches = [
    ("PATCH 1 - _limiteAutorizado em cfgGetDescontoMax", OLD1, NEW1),
    ("PATCH 2 - armazena limite ao autorizar",           OLD2, NEW2),
    ("PATCH 3 - reseta ao fechar modal",                 OLD3, NEW3),
    ("PATCH 4 - mpDescontoValidar com limite base",      OLD4, NEW4),
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
