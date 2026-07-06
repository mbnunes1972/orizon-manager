### Task 7: Capa e HTML final

**Files:**
- Modify: `mod_contrato.py`
- Test: `tests/test_contrato_pdf.py`

**Interfaces:**
- Consumes: `_html_ambientes_linhas`, `_html_parcelas_linhas`, `_html_corpo`, `_substituir_marcadores_html`, `_montar_mapping`, `CONTRATO_TEMPLATE_DIR`.
- Produces:
  - `_html_capa(ctx: dict) -> str` — HTML das 5 seções (identificação/endereços com rótulos+`[MARCADORES]`; ambientes e parcelas com linhas dinâmicas; termina com `<div class="quebra-capa"></div>`).
  - `_montar_html_contrato(ctx: dict) -> str` — injeta capa+corpo no shell e substitui `[MARCADORES]` (inclui `TEXTO_COMPLEMENTAR = ctx.get("adendo","")`).

- [ ] **Step 1: Teste que falha**

```python
def test_montar_html_contrato_substitui_e_inclui_secoes():
    import json
    from mod_contrato import construir_contexto, _montar_html_contrato
    loja = {"nome": "L", "cnpj": "1", "codigo": "INS",
            "testemunha1_nome": "J", "testemunha1_cpf": "1",
            "testemunha2_nome": "F", "testemunha2_cpf": "2"}
    ctx = construir_contexto(
        {"nome": "Ana Paula", "cpf": "111.222.333-44", "email": "a@x.com",
         "telefone": "(12)9", "logradouro": "Rua A", "numero": "10", "complemento": "",
         "bairro": "Jardim Aquarius", "cidade": "SJC", "cep": "12000", "estado": "SP",
         "inst_mesmo_residencial": True},
        {"nome": "Z", "telefone": "(12)9", "email": "z@x.com"},
        json.dumps({"tipo": "aymore", "nome_forma": "Aymoré", "total_cliente": 26445.67,
                    "parcelas": [{"num": i + 1, "data": f"18/0{7+i}/2026", "valor": 4820.0}
                                 for i in range(3)]}),
        loja)
    ctx["num_contrato"] = "INS-1"
    ctx["adendo"] = "Acordo especial de entrega."
    ctx["_ambientes"] = [("Cozinha", 12345.67), ("Sala", 14100.0)]
    html = _montar_html_contrato(ctx)
    assert "Ana Paula" in html and "Jardim Aquarius" in html
    assert "Cozinha" in html and "R$ 12.345,67" in html
    assert "R$ 4.820,00" in html                     # parcela
    assert "Acordo especial de entrega." in html     # TEXTO_COMPLEMENTAR
    assert "[" not in html.split("contrato-corpo")[0] or "NOME_" not in html  # marcadores da capa consumidos
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_contrato_pdf.py -k montar_html -q`
Expected: FAIL.

- [ ] **Step 3: Implementar**

Adicione em `mod_contrato.py` (ajuste os rótulos/estrutura das seções 1–3 conforme o `.docx` atual — Nome/CPF/Email/Telefone; endereço residencial e de instalação):

```python
def _html_capa(ctx):
    amb = _html_ambientes_linhas(ctx.get("_ambientes") or [])
    parc = _html_parcelas_linhas(ctx.get("_pag") or {})
    return f"""
<div id="cabecalho">
  <img class="logo" src="logo_dalmobile.png">
  <span class="num">[NUM_CONTRATO]<br>[DATA_CONTRATO]</span>
</div>

<div class="secao">
  <div class="titulo">1. Identificação do Cliente</div>
  <table><tr>
    <td><span class="rotulo">Nome</span><span class="valor">[NOME_CLIENTE]</span></td>
    <td><span class="rotulo">CPF/CNPJ</span><span class="valor">[CPF]</span></td>
  </tr><tr>
    <td><span class="rotulo">E-mail</span><span class="valor">[EMAIL]</span></td>
    <td><span class="rotulo">Telefone</span><span class="valor">[TELEFONE]</span></td>
  </tr></table>
</div>

<div class="secao">
  <div class="titulo">2. Endereço Residencial</div>
  <table><tr>
    <td colspan="3"><span class="rotulo">Logradouro</span><span class="valor">[RES_LOGRADOURO]</span></td>
  </tr><tr>
    <td><span class="rotulo">Número</span><span class="valor">[RES_NUMERO]</span></td>
    <td><span class="rotulo">Complemento</span><span class="valor">[RES_COMPLEMENTO]</span></td>
    <td><span class="rotulo">Bairro</span><span class="valor">[RES_BAIRRO]</span></td>
  </tr><tr>
    <td><span class="rotulo">Cidade</span><span class="valor">[RES_CIDADE]</span></td>
    <td><span class="rotulo">CEP</span><span class="valor">[RES_CEP]</span></td>
    <td><span class="rotulo">Estado/UF</span><span class="valor">[RES_UF]</span></td>
  </tr></table>
</div>

<div class="secao">
  <div class="titulo">3. Endereço de Instalação</div>
  <table><tr>
    <td colspan="3"><span class="rotulo">Logradouro</span><span class="valor">[INST_LOGRADOURO]</span></td>
  </tr><tr>
    <td><span class="rotulo">Número</span><span class="valor">[INST_NUMERO]</span></td>
    <td><span class="rotulo">Complemento</span><span class="valor">[INST_COMPLEMENTO]</span></td>
    <td><span class="rotulo">Bairro</span><span class="valor">[INST_BAIRRO]</span></td>
  </tr><tr>
    <td><span class="rotulo">Cidade</span><span class="valor">[INST_CIDADE]</span></td>
    <td><span class="rotulo">CEP</span><span class="valor">[INST_CEP]</span></td>
    <td><span class="rotulo">Estado/UF</span><span class="valor">[INST_UF]</span></td>
  </tr></table>
</div>

<div class="secao">
  <div class="titulo">4. Ambientes do Projeto</div>
  <table>
    {amb}
    <tr><td class="total-lbl" colspan="2">VALOR DO CONTRATO</td>
        <td class="total-val" colspan="2">[TOTAL_CONTRATO]</td></tr>
  </table>
</div>

<div class="secao">
  <div class="titulo">5. Forma de Pagamento</div>
  <table><tr>
    <td><span class="rotulo">Entrada</span><span class="valor">[VALOR_ENTRADA]</span></td>
    <td><span class="rotulo">Tipo</span><span class="valor">[FORMA_ENTRADA]</span></td>
    <td><span class="rotulo">Data</span><span class="valor">[DATA_ENTRADA]</span></td>
  </tr><tr>
    <td><span class="rotulo">Modalidade</span><span class="valor">[MODALIDADE]</span></td>
    <td><span class="rotulo">Parcelas</span><span class="valor">[NUM_PARCELAS] / [TIPO]</span></td>
    <td><span class="rotulo">Valor do Contrato</span><span class="valor">[TOTAL_CONTRATO]</span></td>
  </tr></table>
  <table>{parc}</table>
</div>

<div class="quebra-capa"></div>
"""

def _montar_html_contrato(ctx):
    pag = ctx.get("_pag", {})
    mapping = _montar_mapping(ctx, pag)
    mapping["TEXTO_COMPLEMENTAR"] = ctx.get("adendo", "") or ""
    shell = open(os.path.join(CONTRATO_TEMPLATE_DIR, "contrato.html"),
                 encoding="utf-8").read()
    capa = _html_capa(ctx)
    corpo = _html_corpo(_carregar_md())
    html = shell.replace("<!--CAPA-->", capa).replace("<!--CORPO-->", corpo)
    return _substituir_marcadores_html(html, mapping)

def _carregar_md():
    p = os.path.join(CONTRATO_TEMPLATE_DIR, "contrato.md")
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""
```

Nota: `_montar_mapping` continua com assinatura `(ctx, pag)`. Se `[TEXTO_COMPLEMENTAR]` deve aparecer no corpo, incluir o marcador no `contrato.md` (Task 8).

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_contrato_pdf.py -k montar_html -q`
Expected: PASS. (o `contrato.md` pode estar vazio nesta etapa — o corpo fica vazio; o teste só checa capa/marcadores.)

- [ ] **Step 5: Commit**

```bash
git add mod_contrato.py tests/test_contrato_pdf.py
git commit -m "feat(contrato): montagem da capa HTML + HTML final com marcadores"
```

---

