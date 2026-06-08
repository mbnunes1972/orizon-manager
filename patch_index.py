"""
patch_index.py — Aplica mudanças de autenticação no static/index.html
Omie_V3 | Dalmóbile

Uso: python patch_index.py
"""
import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

original = html  # backup para comparar

# ═══════════════════════════════════════════════════════════════
# PATCH 1 — Botão de perfil no rodapé da sidebar
# ═══════════════════════════════════════════════════════════════
OLD1 = '''  <div style="padding:12px 14px;border-top:1px solid var(--border)">
    <div class="nav-item" id="nav-cfg" onclick="goPage(9)" style="opacity:.6;padding:6px 8px">&#x2699; Config</div>
  </div>
</aside>'''

NEW1 = '''  <div style="padding:12px 14px;border-top:1px solid var(--border)">
    <div class="nav-item" id="nav-cfg" onclick="goPage(9)" style="opacity:.6;padding:6px 8px">&#x2699; Config</div>
    <!-- Botão de perfil do usuário -->
    <div id="sb-user-btn" onclick="abrirModalPerfil()"
         style="display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:8px;
                cursor:pointer;margin-top:4px;transition:.15s;border:1px solid var(--border)"
         onmouseover="this.style.borderColor='var(--accent)'"
         onmouseout="this.style.borderColor='var(--border)'">
      <div id="sb-user-avatar"
           style="width:30px;height:30px;border-radius:50%;background:var(--accent);
                  display:flex;align-items:center;justify-content:center;
                  font-family:\'Epilogue\',sans-serif;font-weight:700;font-size:12px;
                  color:#0d160d;flex-shrink:0;overflow:hidden">
        <span id="sb-user-inicial">?</span>
        <img id="sb-user-foto" src="" alt="" style="display:none;width:100%;height:100%;object-fit:cover;border-radius:50%">
      </div>
      <div style="flex:1;min-width:0">
        <div id="sb-user-nome" style="font-family:\'Epilogue\',sans-serif;font-size:11px;font-weight:700;
                                       color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">—</div>
        <div id="sb-user-nivel" style="font-size:9px;color:var(--muted);letter-spacing:.5px;text-transform:uppercase">—</div>
      </div>
    </div>
  </div>
</aside>

<!-- MODAL PERFIL ─────────────────────────────────────────────── -->
<div id="modal-perfil" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);
     z-index:9000;display:none;align-items:center;justify-content:center">
  <div style="background:#111d11;border:1px solid #1e2e1e;border-radius:16px;
              padding:32px;width:100%;max-width:420px;position:relative">
    <!-- Fechar -->
    <button onclick="fecharModalPerfil()"
            style="position:absolute;top:16px;right:16px;background:transparent;border:none;
                   color:var(--muted);font-size:18px;cursor:pointer;line-height:1">✕</button>
    <div style="font-family:\'Epilogue\',sans-serif;font-weight:700;font-size:16px;margin-bottom:24px">
      Meu Perfil
    </div>
    <!-- Avatar -->
    <div style="display:flex;align-items:center;gap:16px;margin-bottom:24px">
      <div style="position:relative;width:64px;height:64px;flex-shrink:0">
        <div id="mp-avatar-circle"
             style="width:64px;height:64px;border-radius:50%;background:var(--accent);
                    display:flex;align-items:center;justify-content:center;
                    font-family:\'Epilogue\',sans-serif;font-weight:700;font-size:22px;
                    color:#0d160d;overflow:hidden">
          <span id="mp-avatar-inicial">?</span>
          <img id="mp-avatar-foto" src="" alt=""
               style="display:none;width:100%;height:100%;object-fit:cover;border-radius:50%">
        </div>
        <label for="mp-foto-input"
               style="position:absolute;bottom:0;right:0;width:22px;height:22px;
                      background:var(--border2);border-radius:50%;display:flex;
                      align-items:center;justify-content:center;cursor:pointer;
                      font-size:11px;border:2px solid #111d11" title="Trocar foto">📷</label>
        <input type="file" id="mp-foto-input" accept="image/*" style="display:none"
               onchange="mpTrocarFoto(event)">
      </div>
      <div>
        <div id="mp-nome-display" style="font-family:\'Epilogue\',sans-serif;font-weight:700;
                                          font-size:15px;color:var(--text)">—</div>
        <div id="mp-nivel-display" style="font-size:10px;color:var(--muted);
                                           text-transform:uppercase;letter-spacing:.8px;margin-top:2px">—</div>
        <div id="mp-limite-display" style="font-size:10px;color:var(--accent);margin-top:4px">—</div>
      </div>
    </div>
    <!-- Campos editáveis -->
    <div style="display:grid;gap:14px">
      <div>
        <label style="font-size:10px;color:var(--muted);letter-spacing:.8px;text-transform:uppercase;
                       display:block;margin-bottom:5px">Telefone</label>
        <input type="tel" id="mp-telefone" placeholder="(11) 99999-9999"
               style="width:100%;background:#0a120a;border:1px solid var(--border);border-radius:8px;
                      padding:10px 12px;color:var(--text);font-family:\'IBM Plex Mono\',monospace;
                      font-size:13px;outline:none"
               onfocus="this.style.borderColor=\'var(--accent)\'"
               onblur="this.style.borderColor=\'var(--border)\'">
      </div>
      <div>
        <label style="font-size:10px;color:var(--muted);letter-spacing:.8px;text-transform:uppercase;
                       display:block;margin-bottom:5px">WhatsApp</label>
        <input type="tel" id="mp-whatsapp" placeholder="(11) 99999-9999"
               style="width:100%;background:#0a120a;border:1px solid var(--border);border-radius:8px;
                      padding:10px 12px;color:var(--text);font-family:\'IBM Plex Mono\',monospace;
                      font-size:13px;outline:none"
               onfocus="this.style.borderColor=\'var(--accent)\'"
               onblur="this.style.borderColor=\'var(--border)\'">
      </div>
      <div>
        <label style="font-size:10px;color:var(--muted);letter-spacing:.8px;text-transform:uppercase;
                       display:block;margin-bottom:5px">E-mail</label>
        <input type="email" id="mp-email" placeholder="seu@email.com"
               style="width:100%;background:#0a120a;border:1px solid var(--border);border-radius:8px;
                      padding:10px 12px;color:var(--text);font-family:\'IBM Plex Mono\',monospace;
                      font-size:13px;outline:none"
               onfocus="this.style.borderColor=\'var(--accent)\'"
               onblur="this.style.borderColor=\'var(--border)\'">
      </div>
    </div>
    <!-- Botões -->
    <div style="display:flex;gap:10px;margin-top:24px">
      <button onclick="mpSalvarPerfil()"
              style="flex:1;padding:11px;background:var(--accent);color:#0d160d;border:none;
                     border-radius:9px;font-family:\'Epilogue\',sans-serif;font-weight:700;
                     font-size:13px;cursor:pointer;transition:.15s"
              onmouseover="this.style.opacity=\'.85\'" onmouseout="this.style.opacity=\'1\'">
        Salvar
      </button>
      <button onclick="mpLogout()"
              style="padding:11px 18px;background:transparent;border:1px solid var(--border);
                     border-radius:9px;color:var(--muted);font-family:\'Epilogue\',sans-serif;
                     font-weight:700;font-size:13px;cursor:pointer;transition:.15s"
              onmouseover="this.style.borderColor=\'var(--err)\';this.style.color=\'var(--err)\'"
              onmouseout="this.style.borderColor=\'var(--border)\';this.style.color=\'var(--muted)\'">
        Sair
      </button>
    </div>
    <div id="mp-save-hint" style="font-size:11px;color:var(--ok);text-align:center;
                                   height:16px;margin-top:10px"></div>
  </div>
</div>'''

# ═══════════════════════════════════════════════════════════════
# PATCH 2 — Integrar usuário autenticado + corrigir limites
# Substitui a função carregarPerfil e cfgGetDescontoMax
# ═══════════════════════════════════════════════════════════════
OLD2 = '''let _perfilAtivo = {
  perfil_ativo: 'consultor',
  config: { nome:'Consultor de Vendas', desconto_max_pct:10,
            pode_editar_total:true, pode_ver_margens:false }
};
let _perfisConfig = null;

async function carregarPerfil(){
  try {
    const r = await fetch('/perfis/ativo');
    const d = await r.json();
    _perfilAtivo = d;
    const rp = await fetch('/perfis');
    _perfisConfig = await rp.json();
    aplicarRestricoesPerfil();
  } catch(e){ console.warn('[PERFIL] Erro ao carregar:', e); }
}'''

NEW2 = '''let _perfilAtivo = {
  perfil_ativo: 'consultor',
  config: { nome:'Consultor de Vendas', desconto_max_pct:10,
            pode_editar_total:true, pode_ver_margens:false }
};
let _perfisConfig = null;

// ── Usuário autenticado ───────────────────────────────────────
let _usuarioAtual = null;

const _LIMITES_NIVEL = { consultor: 10, gerente: 20, diretor: 50 };

async function carregarUsuarioAutenticado(){
  try {
    const r = await fetch('/api/auth/me');
    if(!r.ok){ window.location.href = '/login'; return; }
    const d = await r.json();
    if(!d.ok){ window.location.href = '/login'; return; }
    _usuarioAtual = d.usuario;
    _atualizarUIUsuario();
    _carregarDadosExtrasUsuario();
  } catch(e){ console.warn('[AUTH] Erro ao carregar usuário:', e); }
}

function _atualizarUIUsuario(){
  if(!_usuarioAtual) return;
  const u = _usuarioAtual;
  const inicial = u.nome ? u.nome.charAt(0).toUpperCase() : '?';
  const nivel   = u.nivel || 'consultor';

  // Sidebar
  const elNome   = document.getElementById('sb-user-nome');
  const elNivel  = document.getElementById('sb-user-nivel');
  const elInicial= document.getElementById('sb-user-inicial');
  if(elNome)    elNome.textContent    = u.nome;
  if(elNivel)   elNivel.textContent   = nivel;
  if(elInicial) elInicial.textContent = inicial;

  // Modal perfil
  const mpNome  = document.getElementById('mp-nome-display');
  const mpNivel = document.getElementById('mp-nivel-display');
  const mpLim   = document.getElementById('mp-limite-display');
  const mpIni   = document.getElementById('mp-avatar-inicial');
  if(mpNome)  mpNome.textContent  = u.nome;
  if(mpNivel) mpNivel.textContent = nivel;
  if(mpLim)   mpLim.textContent   = `Limite de desconto: ${_LIMITES_NIVEL[nivel] || 10}%`;
  if(mpIni)   mpIni.textContent   = inicial;
}

function _carregarDadosExtrasUsuario(){
  const saved = localStorage.getItem('omie_user_extras_' + (_usuarioAtual?.id || ''));
  if(!saved) return;
  try {
    const extras = JSON.parse(saved);
    const tel = document.getElementById('mp-telefone');
    const wpp = document.getElementById('mp-whatsapp');
    const eml = document.getElementById('mp-email');
    if(tel) tel.value = extras.telefone || '';
    if(wpp) wpp.value = extras.whatsapp || '';
    if(eml) eml.value = extras.email    || '';
    // Foto
    if(extras.foto){
      _aplicarFotoUsuario(extras.foto);
    }
  } catch(e){}
}

function _aplicarFotoUsuario(dataUrl){
  ['sb-user-foto','mp-avatar-foto'].forEach(id => {
    const img = document.getElementById(id);
    const ini = document.getElementById(id === 'sb-user-foto' ? 'sb-user-inicial' : 'mp-avatar-inicial');
    if(img){ img.src = dataUrl; img.style.display = 'block'; }
    if(ini){ ini.style.display = 'none'; }
  });
}

// ── Modal perfil ──────────────────────────────────────────────
function abrirModalPerfil(){
  _carregarDadosExtrasUsuario();
  const m = document.getElementById('modal-perfil');
  if(m){ m.style.display = 'flex'; }
}

function fecharModalPerfil(){
  const m = document.getElementById('modal-perfil');
  if(m){ m.style.display = 'none'; }
}

function mpTrocarFoto(event){
  const file = event.target.files[0];
  if(!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    _aplicarFotoUsuario(e.target.result);
    const key = 'omie_user_extras_' + (_usuarioAtual?.id || '');
    const saved = JSON.parse(localStorage.getItem(key) || '{}');
    saved.foto = e.target.result;
    localStorage.setItem(key, JSON.stringify(saved));
  };
  reader.readAsDataURL(file);
}

function mpSalvarPerfil(){
  const tel = document.getElementById('mp-telefone')?.value || '';
  const wpp = document.getElementById('mp-whatsapp')?.value || '';
  const eml = document.getElementById('mp-email')?.value    || '';
  const key = 'omie_user_extras_' + (_usuarioAtual?.id || '');
  const saved = JSON.parse(localStorage.getItem(key) || '{}');
  saved.telefone = tel;
  saved.whatsapp = wpp;
  saved.email    = eml;
  localStorage.setItem(key, JSON.stringify(saved));
  const hint = document.getElementById('mp-save-hint');
  if(hint){ hint.textContent = '✓ Salvo'; setTimeout(() => hint.textContent = '', 2000); }
}

function mpLogout(){
  fetch('/api/auth/logout', {method:'POST'}).finally(() => {
    window.location.href = '/login';
  });
}

async function carregarPerfil(){
  try {
    const r = await fetch('/perfis/ativo');
    const d = await r.json();
    _perfilAtivo = d;
    const rp = await fetch('/perfis');
    _perfisConfig = await rp.json();
    aplicarRestricoesPerfil();
  } catch(e){ console.warn('[PERFIL] Erro ao carregar:', e); }
}'''

# ═══════════════════════════════════════════════════════════════
# PATCH 3 — cfgGetDescontoMax lê do usuário autenticado
# ═══════════════════════════════════════════════════════════════
OLD3 = '''function cfgGetDescontoMax(){
  return parseFloat((_perfilAtivo.config && _perfilAtivo.config.desconto_max_pct) || 100);
}'''

NEW3 = '''function cfgGetDescontoMax(){
  if(_usuarioAtual && _usuarioAtual.nivel){
    return _LIMITES_NIVEL[_usuarioAtual.nivel] || 10;
  }
  return parseFloat((_perfilAtivo.config && _perfilAtivo.config.desconto_max_pct) || 100);
}'''

# ═══════════════════════════════════════════════════════════════
# PATCH 4 — Chamar carregarUsuarioAutenticado no init
# ═══════════════════════════════════════════════════════════════
OLD4 = '''loadConfig();
</script>'''
NEW4 = '''carregarUsuarioAutenticado();
loadConfig();
</script>'''

# ── Aplicar patches ───────────────────────────────────────────
patches = [
    ("PATCH 1 - botão perfil sidebar", OLD1, NEW1),
    ("PATCH 2 - usuário autenticado",  OLD2, NEW2),
    ("PATCH 3 - cfgGetDescontoMax",    OLD3, NEW3),
    ("PATCH 4 - init call",            OLD4, NEW4),
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
