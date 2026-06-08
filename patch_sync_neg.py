"""
patch_sync_neg.py — Após autorização no modal, atualiza neg-desconto da sidebar
com o mesmo valor autorizado
"""
import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

OLD = """      // Sincroniza sidebar — atualiza neg-desconto com o mesmo valor e revalida
      const negEl = document.getElementById('neg-desconto');
      if(negEl) negValidarLimiteDesconto(negEl.value);"""

NEW = """      // Sincroniza sidebar — atualiza neg-desconto com o valor autorizado e revalida
      const negEl = document.getElementById('neg-desconto');
      if(negEl){
        negEl.value = descontoAprovado;
        negSyncModal(descontoAprovado);
        negValidarLimiteDesconto(descontoAprovado);
      }"""

if OLD in html:
    html = html.replace(OLD, NEW, 1)
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(html)
    print("  ✓ PATCH - sincroniza neg-desconto com valor autorizado")
    print("  ✓ index.html atualizado com sucesso.")
else:
    print("  ✗ Trecho não encontrado")
    sys.exit(1)
