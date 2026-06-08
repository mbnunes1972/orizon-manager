import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

OLD = """  // Popula _negBaseValues com TODOS os ambientes + base estrutural
  window._negBaseValues = _negBaseValues = baseResults.map((res, i) => ({
    arquivo:    allAmbs[i].arquivo,
    nome:       allAmbs[i].ambiente||allAmbs[i].projeto||allAmbs[i].arquivo,
    val_bruto:  allAmbs[i].total,
    estrutural: rnd(res.valor_liquido_avista),  // base sem desconto e sem financeiro
  }));"""

NEW = """  // Popula _negBaseValues com TODOS os ambientes + base estrutural
  window._negBaseValues = _negBaseValues = baseResults.map((res, i) => ({
    arquivo:    allAmbs[i].arquivo,
    nome:       allAmbs[i].ambiente||allAmbs[i].projeto||allAmbs[i].arquivo,
    val_bruto:  allAmbs[i].total,
    estrutural: allAmbs[i].total,  // valor bruto original do XML — parâmetros internos não afetam o cliente
    margem_interna: rnd(res.valor_liquido_avista),  // valor líquido da loja (uso interno)
  }));"""

if OLD in html:
    html = html.replace(OLD, NEW, 1)
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(html)
    print("  ✓ PATCH - estrutural usa valor bruto original")
else:
    print("  ✗ Trecho não encontrado")
    sys.exit(1)
