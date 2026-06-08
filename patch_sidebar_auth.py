"""
patch_sidebar_auth.py — Adiciona botão de confirmação de desconto na sidebar
com fluxo de autorização delegada integrado ao novo sistema de autenticação.
"""
import os, sys

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

# PATCH 1 — substitui cadeado antigo + campo + hint por novo layout com botão confirmar
OLD1 = """      <span>Desconto (%)</span>
      <span id="sb-desc-lock" class="lock-btn" onclick="tfAbrirModalSenha('desconto')" title="Liberar desconto sem limite (gerente)">&#x1F512;</span>
    </label>
    <div style="display:flex;align-items:center;gap:4px;margin-bottom:8px">
      <input type="number" id="neg-desconto" min="0" max="100" step="0.5" value="0"
             onfocus="this._prev=this.value"
             oninput="negValidarLimiteDesconto(this.value); negSyncModal(this.value); agendarCalculo(); agendarSalvarDesconto()"
             onkeydown="negDescontoKeydown(event,this)"
             onblur="salvarDescontoAutomatico()"
             class="sb-input-sm" style="width:60px;text-align:right">
      <span style="color:var(--muted);font-size:12px">%</span>
    </div>
    <div id="neg-limite-hint" style="display:none;font-size:10px;color:var(--err);margin-bottom:8px"></div>"""

NEW1 = """      <span>Desconto (%)</span>
    </label>
    <div style="display:flex;align-items:center;gap:4px;margin-bottom:4px">
      <input type="number" id="neg-desconto" min="0" max="100" step="0.5" value="0"
             onfocus="this._prev=this.value"
             oninput="negValidarLimiteDesconto(this.value); negSyncModal(this.value); agendarCalculo(); agendarSalvarDesconto()"
             onkeydown="negDescontoKeydown(event,this)"
             onblur="salvarDescontoAutomatico()"
             class="sb-input-sm" style="width:60px;text-align:right">
      <span style="color:var(--muted);font-size:12px">%</span>
      <button id="neg-desc-confirmar" onclick="negConfirmarDesconto()"
              style="display:none;padding:3px 7px;background:var(--err);color:#fff;border:none;
                     border-radius:5px;font-family:'Epilogue',sans-serif;font-weight:700;
                     font-size:9px;cursor:pointer;letter-spacing:.3px;transition:.15s;white-space:nowrap"
              title="Solicitar autorização para este desconto">
        ✓ OK
      </button>
    </div>
    <div id="neg-limite-hint" style="display:none;font-size:10px;color:var(--err);margin-bottom:8px"></div>"""

# PATCH 2 — negValidarLimiteDesconto mostra/esconde botão confirmar
OLD2 = """function negValidarLimiteDesconto(val){
  const disc = parseFloat(val) || 0;
  const max  = cfgGetDescontoMax(); // respeita _limiteAutorizado se existir
  const el   = document.getElementById('neg-desconto');
  const hint = document.getElementById('neg-limite-hint');
  if(disc > max){
    if(el){ el.style.borderColor='var(--err)'; el.style.color='var(--err)'; }
    if(hint){
      const limiteBase = _usuarioAtual ? (_LIMITES_NIVEL[_usuarioAtual.nivel] || 10) : 10;
      hint.textContent = '⚠ Limite do perfil: ' + limiteBase + '%';
      hint.style.display = 'block';
    }
  } else {
    if(el){ el.style.borderColor=''; el.style.color=''; }
    if(hint){ hint.style.display='none'; }
  }
}"""

NEW2 = """function negValidarLimiteDesconto(val){
  const disc = parseFloat(val) || 0;
  const max  = cfgGetDescontoMax(); // respeita _limiteAutorizado se existir
  const el   = document.getElementById('neg-desconto');
  const hint = document.getElementById('neg-limite-hint');
  const btn  = document.getElementById('neg-desc-confirmar');
  if(disc > max){
    if(el){ el.style.borderColor='var(--err)'; el.style.color='var(--err)'; }
    if(hint){
      const limiteBase = _usuarioAtual ? (_LIMITES_NIVEL[_usuarioAtual.nivel] || 10) : 10;
      const limiteVigente = _limiteAutorizado !== null ? _limiteAutorizado : limiteBase;
      hint.textContent = '⚠ Limite: ' + limiteVigente + '% — clique OK para autorizar';
      hint.style.display = 'block';
    }
    if(btn){ btn.style.display = 'block'; }
  } else {
    if(el){ el.style.borderColor=''; el.style.color=''; }
    if(hint){ hint.style.display='none'; }
    if(btn){ btn.style.display = 'none'; }
  }
}

async function negConfirmarDesconto(){
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

patches = [
    ("PATCH 1 - botão confirmar na sidebar",          OLD1, NEW1),
    ("PATCH 2 - negValidarLimiteDesconto com botão",  OLD2, NEW2),
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
