import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "rb") as f:
    raw = f.read()

replacements = [
    (b'<option value="a_vista">A Vista</option>', b'<option value="a_vista">1x</option>'),
    (b"parcel.innerHTML = '<option value=\"1\">A Vista</option>';", b"parcel.innerHTML = '<option value=\"1\">1x</option>';"),
    (b"parcel.innerHTML='<option value=\"1\">A Vista</option>';", b"parcel.innerHTML='<option value=\"1\">1x</option>';"),
]

erros = []
for old, new in replacements:
    if old in raw:
        raw = raw.replace(old, new, 1)
        print(f"  \u2713 {old.decode()[:40]}...")
    else:
        print(f"  \u2717 Trecho não encontrado: {old.decode()[:40]}...")
        erros.append(old)

if erros:
    print(f"\n  ATENÇÃO: {len(erros)} trecho(s) não encontrado(s). Arquivo não foi salvo.")
    sys.exit(1)

with open(INDEX, "wb") as f:
    f.write(raw)
print("\n  \u2713 index.html atualizado com sucesso.")
