"""
patch_sync_auth.py — Após autorização, sincroniza a sidebar chamando negValidarLimiteDesconto
"""
import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

OLD = """    if(d.ok){
      // Salva o desconto específico aprovado como novo limite (não o limite do perfil)
      const descontoAprovado = parseFloat(document.getElementById('mp-desconto').value) || 0;
      _limiteAutorizado = descontoAprovado;
      // Limpa hint e borda vermelha do campo
      const el = document.getElementById('mp-desconto');
      const hint = document.getElementById('mp-desc-hint');
      if(el) el.style.borderColor = '';
      if(hint) hint.style.display = 'none';
      showToast(`Desconto de ${descontoAprovado}% autorizado por ${d.autorizador.nome}`);
      fecharModalAutorizacao(true);
    }"""

NEW = """    if(d.ok){
      // Salva o desconto específico aprovado como novo limite (não o limite do perfil)
      const descontoAprovado = parseFloat(document.getElementById('mp-desconto').value) || 0;
      _limiteAutorizado = descontoAprovado;
      // Limpa hint e borda vermelha do campo do modal
      const el = document.getElementById('mp-desconto');
      const hint = document.getElementById('mp-desc-hint');
      if(el) el.style.borderColor = '';
      if(hint) hint.style.display = 'none';
      // Sincroniza sidebar — atualiza neg-desconto com o mesmo valor e revalida
      const negEl = document.getElementById('neg-desconto');
      if(negEl) negValidarLimiteDesconto(negEl.value);
      showToast(`Desconto de ${descontoAprovado}% autorizado por ${d.autorizador.nome}`);
      fecharModalAutorizacao(true);
    }"""

if OLD in html:
    html = html.replace(OLD, NEW, 1)
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(html)
    print("  ✓ PATCH - sincroniza sidebar após autorização")
    print("  ✓ index.html atualizado com sucesso.")
else:
    print("  ✗ Trecho não encontrado")
    sys.exit(1)
