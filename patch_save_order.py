import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

OLD = """      if(d.ok){
        projetoAtivo.margens = d.margens;
        showToast('Parametros salvos!');
        // Sincroniza desconto
        const elDesc = document.getElementById('neg-desconto');
        if(elDesc) elDesc.value = d.margens.desconto_pct || 0;
        // Recarrega negociação para recalcular valor bruto (incluir_custos pode ter mudado)
        await carregarMargensSalvas();
      }"""

NEW = """      if(d.ok){
        // Garante que incluir_custos foi salvo corretamente
        if(novoIncluirCustos !== undefined) d.margens.incluir_custos = novoIncluirCustos;
        projetoAtivo.margens = d.margens;
        showToast('Parametros salvos!');
        // Sincroniza desconto
        const elDesc = document.getElementById('neg-desconto');
        if(elDesc) elDesc.value = d.margens.desconto_pct || 0;
        // Recarrega negociação para recalcular valor bruto (incluir_custos pode ter mudado)
        await carregarMargensSalvas();
      }"""

if OLD in html:
    html = html.replace(OLD, NEW, 1)
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(html)
    print("  ✓ PATCH - garante incluir_custos no projetoAtivo antes de recarregar")
else:
    print("  ✗ Trecho não encontrado")
    sys.exit(1)
