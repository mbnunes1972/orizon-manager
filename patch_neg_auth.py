import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

# PATCH 1 — negConfirmarDesconto com lógica própria de autorização e save
OLD1 = """async function negConfirmarDesconto(){
  const disc = parseFloat(document.getElementById('neg-desconto').value) || 0;
  const max  = cfgGetDescontoMax();
  if(disc <= max) return; // já dentro do limite, não precisa autorizar
  const ok = await abrirModalAutorizacao(disc, max);
  if(ok){
    // Limpa hint e botão
    const el   = document.getElementById('neg-desconto');
    const hint = document.getElementById('neg-limite-hint');
    const btn  = document.getElementById('neg-desc-confirmar');
    if(el){ el.style.borderColor=''; el.style.color=''; }
    if(hint){ hint.style.display='none'; }
    if(btn){ btn.style.display='none'; }
  }
}"""

NEW1 = """async function negConfirmarDesconto(){
  const disc = parseFloat(document.getElementById('neg-desconto').value) || 0;
  const max  = cfgGetDescontoMax();
  if(disc <= max) return;
  // Abre modal de autorização passando contexto 'sidebar' para não mexer em mp-desconto
  const ok = await abrirModalAutorizacaoSidebar(disc, max);
  if(ok){
    const el   = document.getElementById('neg-desconto');
    const hint = document.getElementById('neg-limite-hint');
    const btn  = document.getElementById('neg-desc-confirmar');
    if(el){ el.style.borderColor=''; el.style.color=''; el._prev = disc; }
    if(hint){ hint.style.display='none'; }
    if(btn){ btn.style.display='none'; }
    // Salva o desconto no backend
    agendarCalculo();
    agendarSalvarDesconto();
  }
}

// Modal de autorização exclusivo para a sidebar (não mexe em mp-desconto)
let _resolveAutorizacaoSidebar = null;
function abrirModalAutorizacaoSidebar(desconto, limite){
  return new Promise(resolve => {
    _resolveAutorizacaoSidebar = resolve;
    const nivel = _usuarioAtual?.nivel || 'consultor';
    const nivelLabel = { consultor: 'Consultor', gerente: 'Gerente', diretor: 'Diretor' }[nivel] || nivel;
    document.getElementById('auth-modal-msg').textContent =
      `Seu limite como ${nivelLabel} é ${limite}%. O desconto solicitado é ${desconto}%.`;
    document.getElementById('auth-modal-login').value = '';
    document.getElementById('auth-modal-senha').value = '';
    document.getElementById('auth-modal-erro').textContent = '';
    // Marca contexto como sidebar
    document.getElementById('modal-autorizacao').dataset.contexto = 'sidebar';
    document.getElementById('modal-autorizacao').dataset.desconto = desconto;
    document.getElementById('modal-autorizacao').style.display = 'flex';
    setTimeout(() => document.getElementById('auth-modal-login').focus(), 80);
  });
}"""

# PATCH 2 — confirmarAutorizacao distingue sidebar de modal de parâmetros
OLD2 = """async function confirmarAutorizacao(){
  const login = document.getElementById('auth-modal-login').value.trim();
  const senha = document.getElementById('auth-modal-senha').value;
  const desc  = parseFloat(document.getElementById('mp-desconto').value) || 0;
  const erro  = document.getElementById('auth-modal-erro');
  erro.textContent = '';
  if(!login || !senha){ erro.textContent = 'Preencha usuário e senha do autorizador.'; return; }
  try {
    const r = await fetch('/api/auth/autorizar_desconto', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ login_autorizador:login, senha_autorizador:senha,
                             desconto_pct:desc, contexto:{origem:'modal_params'} })
    });
    const d = await r.json();"""

NEW2 = """async function confirmarAutorizacao(){
  const login    = document.getElementById('auth-modal-login').value.trim();
  const senha    = document.getElementById('auth-modal-senha').value;
  const modal    = document.getElementById('modal-autorizacao');
  const contexto = modal.dataset.contexto || 'modal_params';
  const desc     = contexto === 'sidebar'
    ? parseFloat(modal.dataset.desconto || 0)
    : parseFloat(document.getElementById('mp-desconto').value) || 0;
  const erro  = document.getElementById('auth-modal-erro');
  erro.textContent = '';
  if(!login || !senha){ erro.textContent = 'Preencha usuário e senha do autorizador.'; return; }
  try {
    const r = await fetch('/api/auth/autorizar_desconto', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ login_autorizador:login, senha_autorizador:senha,
                             desconto_pct:desc, contexto:{origem: contexto} })
    });
    const d = await r.json();"""

# PATCH 3 — fecharModalAutorizacao resolve a promise correta (sidebar ou params)
OLD3 = """function fecharModalAutorizacao(resultado){
  document.getElementById('modal-autorizacao').style.display = 'none';
  if(_resolveAutorizacao){ _resolveAutorizacao(resultado); _resolveAutorizacao = null; }
}"""

NEW3 = """function fecharModalAutorizacao(resultado){
  const modal = document.getElementById('modal-autorizacao');
  modal.style.display = 'none';
  modal.dataset.contexto = '';
  modal.dataset.desconto = '';
  if(_resolveAutorizacaoSidebar){ _resolveAutorizacaoSidebar(resultado); _resolveAutorizacaoSidebar = null; return; }
  if(_resolveAutorizacao){ _resolveAutorizacao(resultado); _resolveAutorizacao = null; }
}"""

# PATCH 4 — após autorização sidebar, atualiza _limiteAutorizado sem mexer em mp-desconto
OLD4 = """      showToast(`Desconto de ${descontoAprovado}% autorizado por ${d.autorizador.nome}`);
      fecharModalAutorizacao(true);
      // Sincroniza sidebar após o modal fechar
      const _desc = descontoAprovado;
      setTimeout(() => {
        const negEl = document.getElementById('neg-desconto');
        if(negEl){
          negEl.blur();           // garante que onblur não vai salvar valor antigo
          negEl.value = _desc;
          negEl._prev = _desc;    // reseta referência para o novo valor
          negValidarLimiteDesconto(_desc);
          agendarCalculo();
          agendarSalvarDesconto();
        }
      }, 300);"""

NEW4 = """      showToast(`Desconto de ${descontoAprovado}% autorizado por ${d.autorizador.nome}`);
      fecharModalAutorizacao(true);
      // Se veio do modal de parâmetros, sincroniza sidebar
      if(contexto !== 'sidebar'){
        const _desc = descontoAprovado;
        setTimeout(() => {
          const negEl = document.getElementById('neg-desconto');
          if(negEl){
            negEl.blur();
            negEl.value = _desc;
            negEl._prev = _desc;
            negValidarLimiteDesconto(_desc);
            agendarCalculo();
            agendarSalvarDesconto();
          }
        }, 300);
      }"""

patches = [
    ("PATCH 1 - negConfirmarDesconto com lógica própria", OLD1, NEW1),
    ("PATCH 2 - confirmarAutorizacao distingue contexto",  OLD2, NEW2),
    ("PATCH 3 - fecharModalAutorizacao resolve correta",   OLD3, NEW3),
    ("PATCH 4 - sincroniza só se veio do modal params",    OLD4, NEW4),
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
