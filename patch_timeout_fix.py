import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

OLD = """      // Sincroniza sidebar com o valor autorizado
      const negEl = document.getElementById('neg-desconto');
      if(negEl){
        negEl.value    = descontoAprovado;
        negEl._prev    = descontoAprovado; // evita reset pelo onblur/Escape
        negValidarLimiteDesconto(descontoAprovado);
        agendarCalculo();
        agendarSalvarDesconto();
      }
      showToast(`Desconto de ${descontoAprovado}% autorizado por ${d.autorizador.nome}`);
      fecharModalAutorizacao(true);"""

NEW = """      showToast(`Desconto de ${descontoAprovado}% autorizado por ${d.autorizador.nome}`);
      fecharModalAutorizacao(true);
      // Sincroniza sidebar após o modal fechar (setTimeout evita conflito com onfocus/_prev)
      setTimeout(() => {
        const negEl = document.getElementById('neg-desconto');
        if(negEl){
          negEl.value = descontoAprovado;
          negEl._prev = descontoAprovado;
          negValidarLimiteDesconto(descontoAprovado);
          agendarCalculo();
          agendarSalvarDesconto();
        }
      }, 100);"""

if OLD in html:
    html = html.replace(OLD, NEW, 1)
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(html)
    print("  ✓ PATCH - setTimeout para sincronizar após modal fechar")
else:
    print("  ✗ Trecho não encontrado")
    sys.exit(1)
