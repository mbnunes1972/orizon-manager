import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "rb") as f:
    raw = f.read()

OLD = b"""    if(incEl2) incEl2.checked = !!s.incluir_custos;
    mpToggleArq(); mpToggleFid(); mpToggleViagem(); mpToggleBrinde();
    negSyncSidebar(s.desconto_pct);
    _mpSnapshot = null;
    return;"""

NEW = b"""    if(incEl2) incEl2.checked = !!s.incluir_custos;
    // Atualiza projetoAtivo.margens para refletir o estado restaurado
    if(projetoAtivo && projetoAtivo.margens){
      projetoAtivo.margens.incluir_custos = !!s.incluir_custos;
    }
    mpToggleArq(); mpToggleFid(); mpToggleViagem(); mpToggleBrinde();
    mpRecalcularEstruturalModal();
    negSyncSidebar(s.desconto_pct);
    _mpSnapshot = null;
    return;"""

if OLD in raw:
    raw = raw.replace(OLD, NEW, 1)
    with open(INDEX, "wb") as f:
        f.write(raw)
    print("  \u2713 PATCH - snapshot restaura projetoAtivo.margens.incluir_custos")
else:
    print("  \u2717 Trecho não encontrado")
    sys.exit(1)
