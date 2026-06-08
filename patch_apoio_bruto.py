import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

OLD = """function mpAtualizarApoio(){
  const rnd = v => Math.round(v*100)/100;
  const ambs = (projetoAtivo && projetoAtivo.ambientes) || [];
  const ambsNeg = ambs.filter(a => a.selecionado && _negSelLocal[a.arquivo] !== false);
  const bruto = rnd(ambsNeg.reduce((s,a)=>s+(a.total||0),0));"""

NEW = """function mpAtualizarApoio(){
  const rnd = v => Math.round(v*100)/100;
  const ambs = (projetoAtivo && projetoAtivo.ambientes) || [];
  const ambsNeg = ambs.filter(a => a.selecionado && _negSelLocal[a.arquivo] !== false);
  // Usa estrutural de _negBaseValues que já considera incluir_custos
  const bruto = (_negBaseValues && _negBaseValues.length)
    ? rnd(_negBaseValues.filter(b => _negSelLocal[b.arquivo] !== false).reduce((s,b)=>s+(b.estrutural||0),0))
    : rnd(ambsNeg.reduce((s,a)=>s+(a.total||0),0));"""

if OLD in html:
    html = html.replace(OLD, NEW, 1)
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(html)
    print("  ✓ PATCH - mpAtualizarApoio usa estrutural com gross-up")
else:
    print("  ✗ Trecho não encontrado")
    sys.exit(1)
