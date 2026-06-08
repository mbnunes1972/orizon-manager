import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

OLD = """      if(el) el.style.borderColor = '';
      if(hint) hint.style.display = 'none';
      showToast(`Desconto de ${descontoAprovado}% autorizado por ${d.autorizador.nome}`);
      fecharModalAutorizacao(true);"""

NEW = """      if(el) el.style.borderColor = '';
      if(hint) hint.style.display = 'none';
      // Sincroniza sidebar com o valor autorizado
      const negEl = document.getElementById('neg-desconto');
      if(negEl){ negEl.value = descontoAprovado; negSyncModal(descontoAprovado); negValidarLimiteDesconto(descontoAprovado); }
      showToast(`Desconto de ${descontoAprovado}% autorizado por ${d.autorizador.nome}`);
      fecharModalAutorizacao(true);"""

if OLD in html:
    html = html.replace(OLD, NEW, 1)
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(html)
    print("  ✓ PATCH - sincroniza neg-desconto com valor autorizado")
else:
    print("  ✗ Trecho não encontrado")
    sys.exit(1)
