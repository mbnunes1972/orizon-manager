import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

OLD = """      // Sincroniza sidebar com o valor autorizado
      const negEl = document.getElementById('neg-desconto');
      if(negEl){ negEl.value = descontoAprovado; negSyncModal(descontoAprovado); negValidarLimiteDesconto(descontoAprovado); }"""

NEW = """      // Sincroniza sidebar com o valor autorizado
      const negEl = document.getElementById('neg-desconto');
      if(negEl){
        negEl.value    = descontoAprovado;
        negEl._prev    = descontoAprovado; // evita reset pelo onblur/Escape
        negValidarLimiteDesconto(descontoAprovado);
        agendarCalculo();
        agendarSalvarDesconto();
      }"""

if OLD in html:
    html = html.replace(OLD, NEW, 1)
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(html)
    print("  ✓ PATCH - fix sincronização sidebar após autorização")
else:
    print("  ✗ Trecho não encontrado")
    sys.exit(1)
