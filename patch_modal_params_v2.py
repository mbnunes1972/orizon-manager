"""
patch_modal_params_v2.py — Corrige modal de parâmetros
Omie_V3 | Dalmóbile
"""
import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

# PATCH 1 — Snapshot ao abrir modal
OLD1 = """  id('mp-desconto').value      = descontoAtual;
  id('mp-arq-ativa').checked   = !!m.comissao_arq_ativa;
  id('mp-arq-pct').value     = m.comissao_arq_pct || 0;
  id('mp-fid-ativa').checked = !!m.fidelidade_ativa;
  id('mp-fid-pct').value     = m.fidelidade_pct || 0;
  id('mp-fora-sede').checked  = !!m.fora_da_sede;
  id('mp-viagem').value       = m.custo_viagem   || 0;
  id('mp-brinde-ativo').checked = !!m.brinde_ativo;
  id('mp-brinde').value       = m.brinde || 0;
  mpToggleArq(); mpToggleFid(); mpToggleViagem(); mpToggleBrinde();
  document.getElementById('modal-params').style.display = 'flex';
  mpAtualizarApoio();
}"""

NEW1 = """  id('mp-desconto').value      = descontoAtual;
  id('mp-arq-ativa').checked   = !!m.comissao_arq_ativa;
  id('mp-arq-pct').value     = m.comissao_arq_pct || 0;
  id('mp-fid-ativa').checked = !!m.fidelidade_ativa;
  id('mp-fid-pct').value     = m.fidelidade_pct || 0;
  id('mp-fora-sede').checked  = !!m.fora_da_sede;
  id('mp-viagem').value       = m.custo_viagem   || 0;
  id('mp-brinde-ativo').checked = !!m.brinde_ativo;
  id('mp-brinde').value       = m.brinde || 0;
  mpToggleArq(); mpToggleFid(); mpToggleViagem(); mpToggleBrinde();
  _mpSnapshot = {
    desconto_pct:       descontoAtual,
    comissao_arq_ativa: !!m.comissao_arq_ativa,
    comissao_arq_pct:   m.comissao_arq_pct || 0,
    fidelidade_ativa:   !!m.fidelidade_ativa,
    fidelidade_pct:     m.fidelidade_pct || 0,
    fora_da_sede:       !!m.fora_da_sede,
    custo_viagem:       m.custo_viagem || 0,
    brinde_ativo:       !!m.brinde_ativo,
    brinde:             m.brinde || 0,
  };
  document.getElementById('modal-params').style.display = 'flex';
  mpAtualizarApoio();
}
let _mpSnapshot = null;"""

# PATCH 2 — Restaurar ao cancelar
OLD2 = """async function fecharModalParams(salvar){
  document.getElementById('modal-params').style.display = 'none';
  if(salvar && projetoAtivo){"""

NEW2 = """async function fecharModalParams(salvar){
  document.getElementById('modal-params').style.display = 'none';
  if(!salvar && _mpSnapshot){
    const id = s => document.getElementById(s);
    const s = _mpSnapshot;
    id('mp-desconto').value       = s.desconto_pct;
    id('mp-arq-ativa').checked    = s.comissao_arq_ativa;
    id('mp-arq-pct').value        = s.comissao_arq_pct;
    id('mp-fid-ativa').checked    = s.fidelidade_ativa;
    id('mp-fid-pct').value        = s.fidelidade_pct;
    id('mp-fora-sede').checked    = s.fora_da_sede;
    id('mp-viagem').value         = s.custo_viagem;
    id('mp-brinde-ativo').checked = s.brinde_ativo;
    id('mp-brinde').value         = s.brinde;
    mpToggleArq(); mpToggleFid(); mpToggleViagem(); mpToggleBrinde();
    negSyncSidebar(s.desconto_pct);
    _mpSnapshot = null;
    return;
  }
  if(salvar && projetoAtivo){"""

# PATCH 3 — hint no campo desconto do modal
OLD3 = """      <input type="number" class="toggle-input" id="mp-desconto" min="0" max="100" step="0.5" value="0"
             onfocus="this._prev=this.value"
             oninput="negSyncSidebar(this.value); agendarDiscriminacao()"
             onkeydown="mpDescontoKeydown(event,this)">"""

NEW3 = """      <input type="number" class="toggle-input" id="mp-desconto" min="0" max="100" step="0.5" value="0"
             onfocus="this._prev=this.value"
             oninput="mpDescontoValidar(this); negSyncSidebar(this.value); agendarDiscriminacao()"
             onkeydown="mpDescontoKeydown(event,this)">
      <div id="mp-desc-hint" style="display:none;font-size:10px;color:var(--err);margin-top:4px;grid-column:1/-1"></div>"""

# PATCH 4 — mpDescontoValidar
OLD4 = """function mpToggleArq(){"""

NEW4 = """function mpDescontoValidar(el){
  const val  = parseFloat(el.value) || 0;
  const max  = cfgGetDescontoMax();
  const hint = document.getElementById('mp-desc-hint');
  if(val > max){
    el.style.borderColor = 'var(--err)';
    if(hint){ hint.textContent = `Limite do seu perfil: ${max}%. Salvar solicitará autorização.`; hint.style.display = 'block'; }
  } else {
    el.style.borderColor = '';
    if(hint){ hint.style.display = 'none'; }
  }
}

function mpToggleArq(){"""

# PATCH 5 — Botão salvar com validação
OLD5 = """  <button class="btn btn-ghost btn-sm" onclick="fecharModalParams(false)" style="flex:1;justify-content:center">Voltar</button>
      <button class="btn btn-primary btn-sm" onclick="fecharModalParams(true)" style="flex:1;justify-content:center">Salvar e continuar</button>"""

NEW5 = """  <button class="btn btn-ghost btn-sm" onclick="fecharModalParams(false)" style="flex:1;justify-content:center">Voltar</button>
      <button class="btn btn-primary btn-sm" onclick="mpSalvarComValidacao()" style="flex:1;justify-content:center">Salvar e continuar</button>"""

# PATCH 6 — mpSalvarComValidacao + abrirModalAutorizacao
OLD6 = """function mpToggleBrinde(){"""

NEW6 = """async function mpSalvarComValidacao(){
  const desc = parseFloat(document.getElementById('mp-desconto').value) || 0;
  const max  = cfgGetDescontoMax();
  if(desc > max){
    const ok = await abrirModalAutorizacao(desc, max);
    if(!ok) return;
  }
  fecharModalParams(true);
}

let _resolveAutorizacao = null;
function abrirModalAutorizacao(desconto, limite){
  return new Promise(resolve => {
    _resolveAutorizacao = resolve;
    const nivel = _usuarioAtual?.nivel || 'consultor';
    const nivelLabel = { consultor: 'Consultor', gerente: 'Gerente', diretor: 'Diretor' }[nivel] || nivel;
    document.getElementById('auth-modal-msg').textContent =
      `Seu limite como ${nivelLabel} é ${limite}%. O desconto solicitado é ${desconto}%.`;
    document.getElementById('auth-modal-login').value = '';
    document.getElementById('auth-modal-senha').value = '';
    document.getElementById('auth-modal-erro').textContent = '';
    document.getElementById('modal-autorizacao').style.display = 'flex';
    setTimeout(() => document.getElementById('auth-modal-login').focus(), 80);
  });
}
function fecharModalAutorizacao(resultado){
  document.getElementById('modal-autorizacao').style.display = 'none';
  if(_resolveAutorizacao){ _resolveAutorizacao(resultado); _resolveAutorizacao = null; }
}
async function confirmarAutorizacao(){
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
    const d = await r.json();
    if(d.ok){ showToast(`Desconto autorizado por ${d.autorizador.nome}`); fecharModalAutorizacao(true); }
    else { erro.textContent = d.erro || 'Autorização negada.'; }
  } catch(e){ erro.textContent = 'Erro de conexão.'; }
}

function mpToggleBrinde(){"""

# PATCH 7 — HTML do modal de autorização
OLD7 = """<div class="toast" id="toast"></div>"""

NEW7 = """<div id="modal-autorizacao" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.78);z-index:9500;align-items:center;justify-content:center">
  <div style="background:#111d11;border:1px solid #1e2e1e;border-radius:14px;padding:28px;width:100%;max-width:380px">
    <div style="font-family:'Epilogue',sans-serif;font-weight:700;font-size:15px;margin-bottom:8px">Autorização Necessária</div>
    <div id="auth-modal-msg" style="font-size:12px;color:var(--muted);margin-bottom:16px;line-height:1.6"></div>
    <div style="font-size:11px;color:var(--text);margin-bottom:14px">Informe as credenciais de um Gerente ou Diretor:</div>
    <div style="display:grid;gap:12px;margin-bottom:16px">
      <div>
        <label style="font-size:10px;color:var(--muted);letter-spacing:.8px;text-transform:uppercase;display:block;margin-bottom:5px">Usuário autorizador</label>
        <input type="text" id="auth-modal-login" placeholder="login.autorizador"
               style="width:100%;background:#0a120a;border:1px solid var(--border);border-radius:8px;padding:10px 12px;color:var(--text);font-family:'IBM Plex Mono',monospace;font-size:13px;outline:none"
               onfocus="this.style.borderColor='var(--accent)'" onblur="this.style.borderColor='var(--border)'"
               onkeydown="if(event.key==='Enter') document.getElementById('auth-modal-senha').focus()">
      </div>
      <div>
        <label style="font-size:10px;color:var(--muted);letter-spacing:.8px;text-transform:uppercase;display:block;margin-bottom:5px">Senha</label>
        <input type="password" id="auth-modal-senha" placeholder="••••••••"
               style="width:100%;background:#0a120a;border:1px solid var(--border);border-radius:8px;padding:10px 12px;color:var(--text);font-family:'IBM Plex Mono',monospace;font-size:13px;outline:none"
               onfocus="this.style.borderColor='var(--accent)'" onblur="this.style.borderColor='var(--border)'"
               onkeydown="if(event.key==='Enter') confirmarAutorizacao()">
      </div>
    </div>
    <div id="auth-modal-erro" style="font-size:12px;color:var(--err);min-height:18px;margin-bottom:12px"></div>
    <div style="display:flex;gap:10px">
      <button onclick="fecharModalAutorizacao(false)" style="flex:1;padding:11px;background:transparent;border:1px solid var(--border);border-radius:9px;color:var(--muted);font-family:'Epilogue',sans-serif;font-weight:700;font-size:13px;cursor:pointer">Cancelar</button>
      <button onclick="confirmarAutorizacao()" style="flex:1;padding:11px;background:var(--accent);color:#0d160d;border:none;border-radius:9px;font-family:'Epilogue',sans-serif;font-weight:700;font-size:13px;cursor:pointer">Autorizar</button>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>"""

patches = [
    ("PATCH 1 - snapshot ao abrir",        OLD1, NEW1),
    ("PATCH 2 - restaurar ao cancelar",    OLD2, NEW2),
    ("PATCH 3 - hint desconto modal",      OLD3, NEW3),
    ("PATCH 4 - mpDescontoValidar",        OLD4, NEW4),
    ("PATCH 5 - botão salvar validação",   OLD5, NEW5),
    ("PATCH 6 - mpSalvarComValidacao",     OLD6, NEW6),
    ("PATCH 7 - HTML modal autorização",   OLD7, NEW7),
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
