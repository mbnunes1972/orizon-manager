import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

OLD = """function abrirModalAutorizacao(desconto, limite){
  return new Promise(resolve => {
    _resolveAutorizacao = resolve;
    const nivel = _usuarioAtual?.nivel || 'consultor';
    const nivelLabel = { consultor: 'Consultor', gerente: 'Gerente', diretor: 'Diretor' }[nivel] || nivel;"""

NEW = """function abrirModalAutorizacao(desconto, limite){
  return new Promise(resolve => {
    _resolveAutorizacao = resolve;
    _resolveAutorizacaoSidebar = null; // garante que não resolve a promise errada
    const modal = document.getElementById('modal-autorizacao');
    modal.dataset.contexto = 'modal_params'; // contexto explícito
    modal.dataset.desconto = desconto;
    const nivel = _usuarioAtual?.nivel || 'consultor';
    const nivelLabel = { consultor: 'Consultor', gerente: 'Gerente', diretor: 'Diretor' }[nivel] || nivel;"""

if OLD in html:
    html = html.replace(OLD, NEW, 1)
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(html)
    print("  ✓ PATCH - fix contexto modal autorização")
else:
    print("  ✗ Trecho não encontrado")
    sys.exit(1)
