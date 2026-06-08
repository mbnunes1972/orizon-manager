import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "rb") as f:
    raw = f.read()

OLD = b"    if(incEl2) incEl2.checked = !!s.incluir_custos;\n    mpToggleArq(); mpToggleFid(); mpToggleViagem(); mpToggleBrinde();\n    negSyncSidebar(s.desconto_pct);\n    _mpSnapshot = null;\n    return;"

NEW = b"    if(incEl2) incEl2.checked = !!s.incluir_custos;\n    // Atualiza projetoAtivo.margens para refletir estado restaurado\n    if(projetoAtivo && projetoAtivo.margens) projetoAtivo.margens.incluir_custos = !!s.incluir_custos;\n    mpToggleArq(); mpToggleFid(); mpToggleViagem(); mpToggleBrinde();\n    mpRecalcularEstruturalModal();\n    negSyncSidebar(s.desconto_pct);\n    _mpSnapshot = null;\n    return;"

if OLD in raw:
    raw = raw.replace(OLD, NEW, 1)
    with open(INDEX, "wb") as f:
        f.write(raw)
    print("  \u2713 PATCH - snapshot restaura incluir_custos em projetoAtivo")
else:
    print("  \u2717 Trecho não encontrado")
    sys.exit(1)
