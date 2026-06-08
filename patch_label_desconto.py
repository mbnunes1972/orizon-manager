import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "rb") as f:
    raw = f.read()

OLD = b'<span style="color:var(--muted)">Desconto total s/ bruto</span>'
NEW = b'<span style="color:var(--muted)">Desconto Total</span>'

if OLD in raw:
    raw = raw.replace(OLD, NEW, 1)
    with open(INDEX, "wb") as f:
        f.write(raw)
    print("  \u2713 PATCH - label renomeado para Desconto Total")
else:
    print("  \u2717 Trecho não encontrado")
    sys.exit(1)
