import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "rb") as f:
    raw = f.read()

OLD = b"  const margem = bruto > 0 ? rnd((bruto - liquido) / bruto * 100) : 0;"

NEW = b"""  // Desconto Total usa sempre o bruto original dos XMLs (sem gross-up)
  const bruto_original = rnd(ambsNeg.reduce((s,a)=>s+(a.total||0),0));
  const margem = bruto_original > 0 ? rnd((bruto_original - liquido) / bruto_original * 100) : 0;"""

if OLD in raw:
    raw = raw.replace(OLD, NEW, 1)
    with open(INDEX, "wb") as f:
        f.write(raw)
    print("  ✓ PATCH - margem usa bruto original dos XMLs")
else:
    print("  ✗ Trecho não encontrado")
    sys.exit(1)
