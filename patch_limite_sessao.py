"""
patch_limite_sessao.py — Limite autorizado é o desconto específico aprovado,
persiste durante toda a negociação e só reseta ao trocar de projeto ou logout.
"""
import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

# PATCH 1 — ao autorizar, salva o desconto específico (não o limite do autorizador)
OLD1 = """    if(d.ok){
      // Armazena limite do autorizador temporariamente
      _limiteAutorizado = _LIMITES_NIVEL[d.autorizador.nivel] || 50;
      // Limpa hint e borda vermelha do campo
      const el = document.getElementById('mp-desconto');
      const hint = document.getElementById('mp-desc-hint');
      if(el) el.style.borderColor = '';
      if(hint) hint.style.display = 'none';
      showToast(`Desconto autorizado por ${d.autorizador.nome} (limite ${_limiteAutorizado}%)`);
      fecharModalAutorizacao(true);
    }"""

NEW1 = """    if(d.ok){
      // Salva o desconto específico aprovado como novo limite (não o limite do perfil)
      const descontoAprovado = parseFloat(document.getElementById('mp-desconto').value) || 0;
      _limiteAutorizado = descontoAprovado;
      // Limpa hint e borda vermelha do campo
      const el = document.getElementById('mp-desconto');
      const hint = document.getElementById('mp-desc-hint');
      if(el) el.style.borderColor = '';
      if(hint) hint.style.display = 'none';
      showToast(`Desconto de ${descontoAprovado}% autorizado por ${d.autorizador.nome}`);
      fecharModalAutorizacao(true);
    }"""

# PATCH 2 — NÃO reseta _limiteAutorizado ao fechar o modal — persiste na negociação
OLD2 = """async function fecharModalParams(salvar){
  document.getElementById('modal-params').style.display = 'none';
  _limiteAutorizado = null; // reseta limite temporário ao fechar modal
  if(!salvar && _mpSnapshot){"""

NEW2 = """async function fecharModalParams(salvar){
  document.getElementById('modal-params').style.display = 'none';
  // _limiteAutorizado NÃO é resetado — persiste durante toda a negociação
  if(!salvar && _mpSnapshot){"""

# PATCH 3 — reseta _limiteAutorizado ao trocar de projeto
# Procura onde o projeto é carregado/trocado
OLD3 = """async function carregarMargensSalvas(){
  if(!projetoAtivo) return;
  _descAdicional  = {};
  _descIndividual = {};"""

NEW3 = """async function carregarMargensSalvas(){
  if(!projetoAtivo) return;
  _limiteAutorizado = null; // reseta ao trocar de projeto
  _descAdicional  = {};
  _descIndividual = {};"""

patches = [
    ("PATCH 1 - salva desconto específico aprovado", OLD1, NEW1),
    ("PATCH 2 - não reseta ao fechar modal",         OLD2, NEW2),
    ("PATCH 3 - reseta ao trocar de projeto",        OLD3, NEW3),
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
