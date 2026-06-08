import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "rb") as f:
    raw = f.read()

# Remove a linha que atualiza projetoAtivo.margens ao restaurar snapshot
OLD = b"if(incEl2) incEl2.checked = !!s.incluir_custos;\r\n    if(projetoAtivo && projetoAtivo.margens) projetoAtivo.margens.incluir_custos = !!s.incluir_custos;\r\n    mpToggleArq(); mpToggleFid(); mpToggleViagem(); mpToggleBrinde();\r\n    mpRecalcularEstruturalModal();\r\n    negSyncSidebar(s.desconto_pct);\r\n    _mpSnapshot = null;\r\n    return;"

NEW = b"if(incEl2) incEl2.checked = !!s.incluir_custos;\r\n    mpToggleArq(); mpToggleFid(); mpToggleViagem(); mpToggleBrinde();\r\n    mpRecalcularEstruturalModal();\r\n    negSyncSidebar(s.desconto_pct);\r\n    _mpSnapshot = null;\r\n    return;"

if OLD in raw:
    raw = raw.replace(OLD, NEW, 1)
    with open(INDEX, "wb") as f:
        f.write(raw)
    print("  \u2713 PATCH - remove atualização de projetoAtivo.margens no snapshot restore")
else:
    print("  \u2717 Trecho não encontrado")
    sys.exit(1)
