import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

# PATCH 1 — margem sempre usa valor bruto original dos XMLs
OLD1 = """  const liquido = saldo;
  // Desconto Total% = (bruto - liquido) / bruto * 100
  // Representa quanto o negócio foi descontado em relação ao valor bruto original
  const margem = bruto > 0 ? rnd((bruto - liquido) / bruto * 100) : 0;"""

NEW1 = """  const liquido = saldo;
  // Desconto Total% usa sempre o valor bruto ORIGINAL dos XMLs (sem gross-up de custos)
  const bruto_original = rnd(ambsNeg.reduce((s,a)=>s+(a.total||0),0));
  const margem = bruto_original > 0 ? rnd((bruto_original - liquido) / bruto_original * 100) : 0;"""

# PATCH 2 — renomear label "Desconto total s/ bruto" para "Desconto Total"
OLD2 = """<span style="color:var(--muted)">Desconto total s/ bruto</span>"""
NEW2 = """<span style="color:var(--muted)">Desconto Total</span>"""

patches = [
    ("PATCH 1 - margem usa bruto original",    OLD1, NEW1),
    ("PATCH 2 - renomeia label Desconto Total", OLD2, NEW2),
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
