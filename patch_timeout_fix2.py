import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

OLD = """      // Sincroniza sidebar após o modal fechar (setTimeout evita conflito com onfocus/_prev)
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

NEW = """      // Sincroniza sidebar após o modal fechar
      const _desc = descontoAprovado;
      setTimeout(() => {
        const negEl = document.getElementById('neg-desconto');
        if(negEl){
          negEl.blur();           // garante que onblur não vai salvar valor antigo
          negEl.value = _desc;
          negEl._prev = _desc;    // reseta referência para o novo valor
          negValidarLimiteDesconto(_desc);
          agendarCalculo();
          agendarSalvarDesconto();
        }
      }, 300);"""

if OLD in html:
    html = html.replace(OLD, NEW, 1)
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(html)
    print("  ✓ PATCH - timeout 300ms com blur antes de setar valor")
else:
    print("  ✗ Trecho não encontrado")
    sys.exit(1)
