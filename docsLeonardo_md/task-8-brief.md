### Task 8: Frontend — aba "Financeiro" no nível Loja (editar config)

**Files:**
- Modify: `static/index.html` (nível Loja do Painel Admin — `adminRenderLoja`/`adminLojaTab`; novas funções de carregar/salvar)

**Interfaces:**
- Consumes: `GET/PUT /api/admin/lojas/<id>/config-financeira`.
- Produces: 4ª aba "Financeiro" no nível Loja, com campos de `defaults_negociacao` + `provisoes` e botão Salvar.

- [ ] **Step 1: Adicionar a aba e o painel**

Em `adminRenderLoja` (a função que monta as abas Dados/Usuários/Projetos), acrescentar o botão de aba e o painel:
```javascript
// no <div> das abas:
'<button class="home-tab" id="loja-tab-financeiro" onclick="adminLojaTab(\'financeiro\')">Financeiro</button>'
// após os panels existentes:
'<div id="loja-panel-financeiro" style="display:none"><em style="color:var(--muted);font-size:12px">Carregando…</em></div>'
```
E em `adminLojaTab`, incluir `'financeiro'` na lista de abas e chamar `adminFinanceiroCarregar()` quando `qual==='financeiro'` (mesmo padrão da aba Projetos).

- [ ] **Step 2: Loader + saver da config financeira**

Adicionar:
```javascript
let _cfgFin = null;
async function adminFinanceiroCarregar(){
  const panel = document.getElementById('loja-panel-financeiro');
  const lid = _adminNav.loja?.id || (_usuarioAtual && _usuarioAtual.loja_id);
  if (!panel || !lid) return;
  const r = await fetch('/api/admin/lojas/'+lid+'/config-financeira', {credentials:'same-origin'});
  if (r.status === 403){ panel.innerHTML = '<em style="color:var(--muted)">Sem acesso.</em>'; return; }
  const d = await r.json().catch(()=>({}));
  _cfgFin = d.config || {};
  const prov = _cfgFin.provisoes || {};
  const dn = _cfgFin.defaults_negociacao || {};
  const campo = (id,lbl,val)=>`<div><label class="field-label">${lbl}</label>
    <input id="${id}" type="number" step="0.01" value="${val||0}"
     style="width:100%;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:9px 13px;color:var(--text);font-size:12px"></div>`;
  panel.innerHTML = `
    <div class="grid2" style="gap:14px;margin-bottom:14px">
      ${campo('fin-com-arq','% Comissão arquiteto (default)',dn.comissao_arq_pct)}
      ${campo('fin-fid','% Fidelidade (default)',dn.fidelidade_pct)}
      ${campo('fin-trib','% Carga tributária',dn.carga_trib_pct)}
      ${campo('fin-frete-fab','% Frete fábrica→loja',prov.frete_fab_pct)}
      ${campo('fin-com-adm','% Comissões administrativas',prov.com_adm_pct)}
      ${campo('fin-com-med','% Comissão de medidor',prov.com_med_pct)}
      ${campo('fin-com-pe','% Comissão projeto executivo',prov.com_proj_exec_pct)}
      ${campo('fin-frete-loc','% Frete local',prov.frete_loc_pct)}
      ${campo('fin-assist','% Assistências',prov.assist_pct)}
      ${campo('fin-ins','% Insumos locais',prov.ins_loc_pct)}
    </div>
    <button class="btn btn-primary btn-sm" onclick="adminFinanceiroSalvar(${lid})">Salvar config financeira</button>`;
}
async function adminFinanceiroSalvar(lid){
  const n = id => parseFloat(document.getElementById(id).value || '0') || 0;
  _cfgFin.defaults_negociacao = {comissao_arq_pct:n('fin-com-arq'), fidelidade_pct:n('fin-fid'), carga_trib_pct:n('fin-trib')};
  _cfgFin.provisoes = {frete_fab_pct:n('fin-frete-fab'), com_adm_pct:n('fin-com-adm'), com_med_pct:n('fin-com-med'),
    com_proj_exec_pct:n('fin-com-pe'), frete_loc_pct:n('fin-frete-loc'), assist_pct:n('fin-assist'), ins_loc_pct:n('fin-ins')};
  const r = await fetch('/api/admin/lojas/'+lid+'/config-financeira', {method:'PUT', credentials:'same-origin',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify(_cfgFin)});
  const d = await r.json();
  if(!d.ok){ await avisoPopup(d.erro||'Erro', {titulo:'Config financeira'}); return; }
  showToast('Config financeira salva.', false);
}
```

- [ ] **Step 3: Verificação manual**

```bash
python3 main.py
```
Como diretor/gerente adm/fin (ou super_admin): Painel Admin → loja → aba **Financeiro** → editar percentuais → Salvar → recarregar a aba e conferir que persistiu.

- [ ] **Step 4: Commit**

```bash
git add static/index.html
git commit -m "feat(financeira): aba Financeiro no nivel Loja (edita config)"
```

---

