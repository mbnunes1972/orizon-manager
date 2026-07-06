# Task 8 Report — aba "Financeiro" no nível Loja (editar config financeira)

## Status
DONE — sem divergências do brief. Código verbatim inserido.

## Edições em `static/index.html`

| # | Linhas (pós-edição) | Descrição |
|---|---------------------|-----------|
| 1 | 6608 | Botão `loja-tab-financeiro` adicionado no bloco de abas de `adminRenderLoja` |
| 2 | 6616 | Painel `loja-panel-financeiro` adicionado após `loja-panel-projetos` em `adminRenderLoja` |
| 3 | 6622 | `'financeiro'` incluído no array da lista de `adminLojaTab` |
| 4 | 6629 | `if (qual==='financeiro') adminFinanceiroCarregar();` adicionado em `adminLojaTab` |
| 5 | 6657–6696 | `let _cfgFin = null` + `adminFinanceiroCarregar` + `adminFinanceiroSalvar` inseridas antes de `adminRenderProjeto` |

## `adminLojaTab` final (linhas 6619–6630)

```javascript
function adminLojaTab(qual){
  ['dados','usuarios','projetos','financeiro'].forEach(q => {
    const tab   = document.getElementById('loja-tab-'+q);
    const panel = document.getElementById('loja-panel-'+q);
    if (tab)   tab.classList.toggle('ativo', q===qual);
    if (panel) panel.style.display = q===qual ? '' : 'none';
  });
  if (qual==='projetos') adminLojaProjetosCarregar();
  if (qual==='financeiro') adminFinanceiroCarregar();
}
```

## Funções novas (linhas 6657–6696)

```javascript
let _cfgFin = null;
async function adminFinanceiroCarregar(){
  // ... GET /api/admin/lojas/<lid>/config-financeira → renderiza 10 campos
}
async function adminFinanceiroSalvar(lid){
  // ... coleta campos → PUT com JSON.stringify(_cfgFin)
}
```

## Sanity estático

- [x] `loja-tab-financeiro` e `loja-panel-financeiro` presentes em `adminRenderLoja`
- [x] `adminLojaTab` trata `'financeiro'` (lista forEach + loader condicional)
- [x] `adminFinanceiroCarregar` definida 1 vez (linha 6658), chamada 1 vez (linha 6629)
- [x] `adminFinanceiroSalvar` definida 1 vez (linha 6686), chamada 1 vez via onclick inline
- [x] `defaults_negociacao`: `comissao_arq_pct`, `fidelidade_pct`, `carga_trib_pct` — presentes no GET e no PUT
- [x] `provisoes`: `frete_fab_pct`, `com_adm_pct`, `com_med_pct`, `com_proj_exec_pct`, `frete_loc_pct`, `assist_pct`, `ins_loc_pct` — presentes no GET e no PUT
- [x] PUT envia `JSON.stringify(_cfgFin)` com mesma estrutura lida no GET
- [x] Template literals balanceados (backtick de `campo` fechado na L6670; backtick de `panel.innerHTML` fechado na L6684)

## Verificação no browser (adiada ao usuário)

Painel Admin → loja → aba **Financeiro** → editar percentuais → Salvar → recarregar aba e confirmar persistência.

## Concerns

Nenhum. O brief casou exatamente com o código real; padrão da aba Projetos replicado fielmente.
