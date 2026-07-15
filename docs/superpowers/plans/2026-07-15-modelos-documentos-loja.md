# Modelos de documentos da loja — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A aba Config › Documentos vira um registro de modelos por loja: o lojista sobe um Word/ODT/texto, o sistema converte para Markdown com marcadores, pede os dados complementares, mostra o preview e ativa a versão — sem nunca alterar as cláusulas de um contrato já assinado.

**Architecture:** Três módulos novos e sem sobreposição — `mod_marcadores` (catálogo de marcadores, sem I/O), `mod_documentos_import` (arquivo → Markdown, sem banco), `mod_documentos` (registro versionado, único que fala com o banco). O contrato passa a apontar para a versão de modelo que o gerou (`contratos.modelo_versao_id`); quem não aponta cai no `contrato_template/contrato.md` global de hoje. Sem IA, sem dependência nova.

**Tech Stack:** Python 3 puro (`http.server`), SQLAlchemy + SQLite, WeasyPrint, LibreOffice headless (só na importação), pytest. Frontend: `static/index.html` (arquivo único, HTML+CSS+JS inline).

**Spec:** `docs/superpowers/specs/2026-07-15-modelos-documentos-loja-design.md`

---

## Contexto que o executor precisa antes do Task 1

Leia isto. Cada item já custou retrabalho a alguém.

**1. `python3`, nunca `python`.** Suíte: `python3 -m pytest -q`. Tem que ficar verde antes de cada commit.

**2. Todo `.py` da raiz precisa estar em `modulos.py`.** `tests/test_arquitetura_modulos.py::test_todo_py_esta_classificado` falha se um `.py` da raiz não estiver em `MODULOS[*]["arquivos"]` nem em `SHELL`. **Criar módulo e registrar em `modulos.py` vão no MESMO commit**, senão a suíte fica vermelha. Os módulos novos entram em `MODULOS["comercial"]["arquivos"]` (é onde `mod_contrato.py` e `mod_proposta.py` já vivem).

**3. Marcador sem correspondência sobrevive no texto.** `_aplica_mark()` (`mod_contrato.py:244-248`) devolve `m.group(0)` quando a chave não está no mapping — ou seja, `[FOO]` desconhecido é **impresso literalmente no PDF**. É por isso que o Task 4 bloqueia marcador desconhecido.

**4. A numeração das cláusulas não está no `.docx`.** O Word numera automaticamente (`numId/ilvl`); `python-docx` não devolve os números. **Não use `python-docx` para importar** — use o export em texto do LibreOffice, que achata a numeração. Ver `scripts/extrair_clausulas_docx.py:4-7`.

**5. Restart do servidor.** Mudança em `.py` exige restart. Mudança em `static/index.html` é lida do disco a cada request → só Ctrl+F5.

**6. Git.** Branch `main`. Commits em pt-BR. **`git add` só os arquivos da mudança, nunca `git add .`** — o working tree tem muito ruído não versionado (`orizon.db`, `perfis_config.json`, `XML/`, `.docx`, logs).

**7. Não existe teste JS.** O Task 9 (frontend) é verificado no navegador + `node --check` no `<script>` extraído.

---

## Estrutura de arquivos

| Arquivo | Responsabilidade | Task |
|---|---|---|
| `mod_marcadores.py` | **Criar.** Catálogo `{MARCADOR: {rotulo, escopo}}` + análise de um corpo contra o catálogo. Sem I/O, sem banco. | 1, 4 |
| `mod_documentos_import.py` | **Criar.** `normalizar()` (arquivo → texto, via LibreOffice) e `extrair_corpo()` (texto → Markdown). Sem banco. | 2, 3 |
| `mod_documentos.py` | **Criar.** Registro versionado: `criar_versao`, `ativar`, `listar`, `resolver_modelo`. Único com acesso ao banco. | 5 |
| `database.py` | **Modificar.** Tabela `DocumentoModelo` + coluna `contratos.modelo_versao_id` + `_migrar_colunas`. | 5, 6 |
| `mod_contrato.py` | **Modificar.** `_montar_mapping` ganha os `LOJA_*`; `_montar_html_contrato`/`montar_html_proposta` passam a resolver o corpo pelo modelo. | 1, 6, 10 |
| `perfis.py` | **Modificar.** Capacidade `gerir_documentos`. | 7 |
| `main.py` | **Modificar.** 5 endpoints `/api/documentos/*`. | 8 |
| `static/index.html` | **Modificar.** `cfgDocumentosRender()` vira painel; modal do wizard. | 9 |
| `modulos.py` | **Modificar.** Registrar arquivos, tabela e rotas novas. | 1, 2, 5, 8 |

---

### Task 1: Catálogo de marcadores

O catálogo diz **quais marcadores existem**; `_montar_mapping` sabe **calcular os valores**. Sem catálogo, a tela não tem o que mostrar e o wizard não tem contra o que validar.

`_montar_mapping` hoje **não** produz nenhum marcador de endereço da loja — por isso o preâmbulo do contrato tem "INSPIRIUM ... São José dos Campos ... CNPJ 19.152.134/0001-56" cravado no texto (`contrato_template/contrato.md:3`). Este task cria os `LOJA_*` que o Task 4 vai propor no lugar dos literais.

**Files:**
- Create: `mod_marcadores.py`
- Create: `tests/test_marcadores.py`
- Modify: `mod_contrato.py:588-633` (dict de `_montar_mapping`)
- Modify: `modulos.py:41-50` (lista `arquivos` de `comercial`)

- [ ] **Step 1: Escrever o teste anti-drift (falhando)**

Este é o teste que impede o catálogo de apodrecer. `TEXTO_COMPLEMENTAR` não sai de `_montar_mapping` (é injetado depois, em `_montar_html_contrato:735`), então é exceção explícita.

Criar `tests/test_marcadores.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mod_marcadores
import mod_contrato


def _mapping_real():
    """Chaves que _montar_mapping realmente produz, com um ctx mínimo."""
    ctx = {"loja": {"nome": "L", "cnpj": "1", "cidade": "C"}}
    return set(mod_contrato._montar_mapping(ctx, {}).keys())


def test_catalogo_cobre_todo_marcador_do_mapping():
    faltando = _mapping_real() - set(mod_marcadores.CATALOGO)
    assert not faltando, f"marcadores sem verbete no catálogo: {sorted(faltando)}"


def test_catalogo_nao_inventa_marcador():
    # TEXTO_COMPLEMENTAR é injetado em _montar_html_contrato, não em _montar_mapping.
    sobrando = set(mod_marcadores.CATALOGO) - _mapping_real() - {"TEXTO_COMPLEMENTAR"}
    assert not sobrando, f"catálogo promete marcador que ninguém preenche: {sorted(sobrando)}"


def test_todo_verbete_tem_rotulo_e_escopo():
    for chave, v in mod_marcadores.CATALOGO.items():
        assert v.get("rotulo"), f"{chave} sem rótulo"
        assert v.get("escopo") in ("cliente", "loja", "pagamento", "projeto", "documento"), \
            f"{chave} com escopo inválido: {v.get('escopo')}"


def test_marcadores_de_endereco_da_loja_existem():
    """Sem estes, o preâmbulo do contrato não tem como ser parametrizado (spec §6)."""
    for c in ("LOJA_LOGRADOURO", "LOJA_NUMERO", "LOJA_BAIRRO",
              "LOJA_CIDADE", "LOJA_UF", "LOJA_CEP"):
        assert c in mod_marcadores.CATALOGO, f"faltou {c}"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_marcadores.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'mod_marcadores'`

- [ ] **Step 3: Acrescentar os `LOJA_*` ao `_montar_mapping`**

Em `mod_contrato.py`, dentro do `return {` de `_montar_mapping` (após a linha `"CNPJ_EMPRESA": loja.get("cnpj", "") or "",`, hoje linha 629), acrescentar:

```python
        "LOJA_LOGRADOURO":   loja.get("logradouro", "") or "",
        "LOJA_NUMERO":       loja.get("numero", "") or "",
        "LOJA_COMPLEMENTO":  loja.get("complemento", "") or "",
        "LOJA_BAIRRO":       loja.get("bairro", "") or "",
        "LOJA_CIDADE":       loja.get("cidade", "") or "",
        "LOJA_UF":           loja.get("estado", "") or "",
        "LOJA_CEP":          loja.get("cep", "") or "",
        "LOJA_TELEFONE":     loja.get("telefone", "") or "",
        "LOJA_EMAIL":        loja.get("email", "") or "",
```

Os nomes de campo vêm da tabela `lojas` (`database.py:379-387`) — repare que a coluna é `estado`, mas o marcador é `LOJA_UF` (consistente com `RES_UF`/`INST_UF` já existentes).

- [ ] **Step 4: Criar `mod_marcadores.py`**

```python
# -*- coding: utf-8 -*-
"""mod_marcadores.py — Catálogo dos [MARCADORES] aceitos nos modelos de documento.

Fonte única do que EXISTE. Quem calcula os VALORES é mod_contrato._montar_mapping();
tests/test_marcadores.py trava os dois juntos — se um ganhar chave que o outro não
tem, a suíte quebra. Ao acrescentar marcador, mexa nos DOIS.
"""

CATALOGO = {
    # ── documento ────────────────────────────────────────────────────────────
    "NUM_CONTRATO":       {"rotulo": "Número do contrato",      "escopo": "documento"},
    "DATA_CONTRATO":      {"rotulo": "Data do contrato",        "escopo": "documento"},
    "TEXTO_COMPLEMENTAR": {"rotulo": "Adendo (texto livre)",    "escopo": "documento"},
    "REDE_IDENTIFICADOR": {"rotulo": "Identificador da rede",   "escopo": "documento"},

    # ── cliente ──────────────────────────────────────────────────────────────
    "NOME_CLIENTE":     {"rotulo": "Nome do cliente",           "escopo": "cliente"},
    "CPF":              {"rotulo": "CPF do cliente",            "escopo": "cliente"},
    "CPF_CLIENTE":      {"rotulo": "CPF do cliente (alias)",    "escopo": "cliente"},
    "EMAIL":            {"rotulo": "E-mail do cliente",         "escopo": "cliente"},
    "TELEFONE":         {"rotulo": "Telefone do cliente",       "escopo": "cliente"},
    "RES_LOGRADOURO":   {"rotulo": "Residencial — logradouro",  "escopo": "cliente"},
    "RES_NUMERO":       {"rotulo": "Residencial — número",      "escopo": "cliente"},
    "RES_COMPLEMENTO":  {"rotulo": "Residencial — complemento", "escopo": "cliente"},
    "RES_BAIRRO":       {"rotulo": "Residencial — bairro",      "escopo": "cliente"},
    "RES_CIDADE":       {"rotulo": "Residencial — cidade",      "escopo": "cliente"},
    "RES_CEP":          {"rotulo": "Residencial — CEP",         "escopo": "cliente"},
    "RES_UF":           {"rotulo": "Residencial — UF",          "escopo": "cliente"},
    "INST_LOGRADOURO":  {"rotulo": "Instalação — logradouro",   "escopo": "cliente"},
    "INST_NUMERO":      {"rotulo": "Instalação — número",       "escopo": "cliente"},
    "INST_COMPLEMENTO": {"rotulo": "Instalação — complemento",  "escopo": "cliente"},
    "INST_BAIRRO":      {"rotulo": "Instalação — bairro",       "escopo": "cliente"},
    "INST_CIDADE":      {"rotulo": "Instalação — cidade",       "escopo": "cliente"},
    "INST_CEP":         {"rotulo": "Instalação — CEP",          "escopo": "cliente"},
    "INST_UF":          {"rotulo": "Instalação — UF",           "escopo": "cliente"},

    # ── loja (CONTRATADA) ────────────────────────────────────────────────────
    "NOME_EMPRESA":      {"rotulo": "Razão social da loja",     "escopo": "loja"},
    "CNPJ_EMPRESA":      {"rotulo": "CNPJ da loja",             "escopo": "loja"},
    "LOJA_LOGRADOURO":   {"rotulo": "Loja — logradouro",        "escopo": "loja"},
    "LOJA_NUMERO":       {"rotulo": "Loja — número",            "escopo": "loja"},
    "LOJA_COMPLEMENTO":  {"rotulo": "Loja — complemento",       "escopo": "loja"},
    "LOJA_BAIRRO":       {"rotulo": "Loja — bairro",            "escopo": "loja"},
    "LOJA_CIDADE":       {"rotulo": "Loja — cidade",            "escopo": "loja"},
    "LOJA_UF":           {"rotulo": "Loja — UF",                "escopo": "loja"},
    "LOJA_CEP":          {"rotulo": "Loja — CEP",               "escopo": "loja"},
    "LOJA_TELEFONE":     {"rotulo": "Loja — telefone",          "escopo": "loja"},
    "LOJA_EMAIL":        {"rotulo": "Loja — e-mail",            "escopo": "loja"},
    "CONSULTOR_NOME":     {"rotulo": "Consultor — nome",        "escopo": "loja"},
    "CONSULTOR_TELEFONE": {"rotulo": "Consultor — telefone",    "escopo": "loja"},
    # Testemunhas: cadastro da loja (lojas.testemunha1_nome/cpf, testemunha2_nome/cpf).
    # Os aliases abaixo existem porque o template atual usa [NOME_TESTEMUNHA_1]/[CPF_TESTEMUNHA_1]
    # enquanto o mapping também expõe TESTEMUNHA_1_NOME/_DOC. Manter os dois — remover
    # qualquer um quebraria contrato_template/contrato.md:105-110.
    "TESTEMUNHA_1_NOME": {"rotulo": "Testemunha 1 — nome",      "escopo": "loja"},
    "TESTEMUNHA_1_DOC":  {"rotulo": "Testemunha 1 — CPF",       "escopo": "loja"},
    "TESTEMUNHA_2_NOME": {"rotulo": "Testemunha 2 — nome",      "escopo": "loja"},
    "TESTEMUNHA_2_DOC":  {"rotulo": "Testemunha 2 — CPF",       "escopo": "loja"},
    "NOME_TESTEMUNHA_1": {"rotulo": "Testemunha 1 — nome",      "escopo": "loja"},
    "CPF_TESTEMUNHA_1":  {"rotulo": "Testemunha 1 — CPF",       "escopo": "loja"},
    "NOME_TESTEMUNHA_2": {"rotulo": "Testemunha 2 — nome",      "escopo": "loja"},
    "CPF_TESTEMUNHA_2":  {"rotulo": "Testemunha 2 — CPF",       "escopo": "loja"},
    "NOME_TESTEMUNHA2":  {"rotulo": "Testemunha 2 — nome",      "escopo": "loja"},

    # ── pagamento ────────────────────────────────────────────────────────────
    "VALOR_ENTRADA":  {"rotulo": "Valor da entrada",   "escopo": "pagamento"},
    "FORMA_ENTRADA":  {"rotulo": "Forma da entrada",   "escopo": "pagamento"},
    "DATA_ENTRADA":   {"rotulo": "Data da entrada",    "escopo": "pagamento"},
    "MODALIDADE":     {"rotulo": "Modalidade",         "escopo": "pagamento"},
    "NUM_PARCELAS":   {"rotulo": "Nº de parcelas",     "escopo": "pagamento"},
    "TIPO":           {"rotulo": "Tipo da parcela",    "escopo": "pagamento"},
    "TOTAL_CONTRATO": {"rotulo": "Valor total",        "escopo": "pagamento"},
}
```

**Se um teste do Step 1 falhar por chave sobrando/faltando, a verdade é o `_montar_mapping`** — ajuste o catálogo para casar com ele, não o contrário. A lista acima foi derivada de `mod_contrato.py:588-633`, mas o código é a fonte.

- [ ] **Step 5: Registrar em `modulos.py`**

Em `modulos.py`, na lista `MODULOS["comercial"]["arquivos"]` (linhas 41-50), acrescentar `"mod_marcadores.py"` junto de `"mod_contrato.py"`.

- [ ] **Step 6: Rodar os testes**

Run: `python3 -m pytest tests/test_marcadores.py tests/test_arquitetura_modulos.py tests/test_contrato.py -q`
Expected: PASS em tudo. `test_contrato.py` tem que continuar verde — os `LOJA_*` são chaves novas, não mexem nas antigas.

- [ ] **Step 7: Suíte inteira**

Run: `python3 -m pytest -q`
Expected: tudo verde.

- [ ] **Step 8: Commit**

```bash
git add mod_marcadores.py tests/test_marcadores.py mod_contrato.py modulos.py
git commit -m "feat(documentos): catálogo de marcadores + LOJA_* no mapping

mod_marcadores.CATALOGO é a fonte única do que EXISTE; _montar_mapping
calcula os valores. Teste anti-drift trava os dois juntos.

LOJA_LOGRADOURO/NUMERO/BAIRRO/CIDADE/UF/CEP/TELEFONE/EMAIL são novos: sem
eles o preâmbulo do contrato (INSPIRIUM/endereço/foro cravados) não tem
como ser parametrizado por loja."
```

---

### Task 2: `extrair_corpo` — texto → Markdown

Função **pura**: recebe o texto exportado pelo LibreOffice, devolve o Markdown das cláusulas. Testa sem LibreOffice instalado. A lógica é a de `scripts/extrair_clausulas_docx.py:24-49`, promovida a módulo testável.

**Files:**
- Create: `mod_documentos_import.py`
- Create: `tests/test_documentos_import.py`
- Modify: `modulos.py:41-50`

- [ ] **Step 1: Escrever os testes (falhando)**

Criar `tests/test_documentos_import.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
import mod_documentos_import as imp

# Export de texto do LibreOffice: capa antes, numeração já achatada em literal.
TXT_EXEMPLO = """MODELO DE CONTRATO
Capa gerada pelo Word — não faz parte do corpo
Cliente: ____________

CONTRATO DE COMPRA E VENDA DE PRODUTOS E DE PRESTAÇÃO DE SERVIÇOS

Pelo presente instrumento particular, de um lado, O CONTRATANTE.

1. CLÁUSULA PRIMEIRA – DO OBJETO E PREÇO
    1.1. A CONTRATADA se obriga a fornecer o material.
    1.1.1. O esboço será considerado aprovado.
    a) MEDIÇÃO: conferência de medidas;

2. CLÁUSULA SEGUNDA – DOS PAGAMENTOS
    2.1. Os pagamentos deverão ser feitos nas datas estipuladas.

E assim, por estarem assim convencionados, firmam as PARTES.
"""


def test_corta_a_capa():
    md = imp.extrair_corpo(TXT_EXEMPLO)
    assert "Capa gerada pelo Word" not in md
    assert md.startswith("CONTRATO DE COMPRA E VENDA")


def test_clausula_vira_heading_sem_o_numero_da_lista():
    md = imp.extrair_corpo(TXT_EXEMPLO)
    assert "# CLÁUSULA PRIMEIRA – DO OBJETO E PREÇO" in md
    assert "# CLÁUSULA SEGUNDA – DOS PAGAMENTOS" in md
    # o "1. " que o LibreOffice achatou antes de "CLÁUSULA" não sobrevive
    assert "# 1. CLÁUSULA" not in md


def test_preserva_a_numeracao_das_clausulas():
    """O motivo de existir o caminho LibreOffice: python-docx perderia estes números."""
    md = imp.extrair_corpo(TXT_EXEMPLO)
    assert "1.1. A CONTRATADA se obriga" in md
    assert "1.1.1. O esboço" in md
    assert "a) MEDIÇÃO" in md
    assert "2.1. Os pagamentos" in md


def test_tira_a_indentacao():
    md = imp.extrair_corpo(TXT_EXEMPLO)
    assert "\n1.1. A CONTRATADA" in md
    assert "    1.1." not in md


def test_insere_texto_complementar_antes_do_fecho():
    md = imp.extrair_corpo(TXT_EXEMPLO)
    assert "[TEXTO_COMPLEMENTAR]" in md
    assert md.index("[TEXTO_COMPLEMENTAR]") < md.index("E assim, por estarem")


def test_texto_sem_o_marco_de_inicio_e_usado_inteiro():
    """Documento que não tem 'CONTRATO DE COMPRA E VENDA' não pode virar string vazia."""
    md = imp.extrair_corpo("# CLÁUSULA ÚNICA\n1.1. Vale tudo.\n")
    assert "1.1. Vale tudo." in md


def test_corpo_vazio_nao_explode():
    assert imp.extrair_corpo("") == ""
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_documentos_import.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'mod_documentos_import'`

- [ ] **Step 3: Implementar**

Criar `mod_documentos_import.py`:

```python
# -*- coding: utf-8 -*-
"""mod_documentos_import.py — Importação de modelo de documento: arquivo → Markdown.

Duas responsabilidades, deliberadamente separadas:

  normalizar(path)    arquivo → texto puro. Toca subprocess (LibreOffice).
  extrair_corpo(txt)  texto → Markdown das cláusulas. Função PURA, testável
                      sem LibreOffice instalado.

POR QUE LIBREOFFICE E NÃO python-docx: o .docx do contrato usa numeração
AUTOMÁTICA do Word (numId/ilvl). Os números ("1.1", "2.3", "a)") NÃO estão no
texto do parágrafo, e python-docx não os devolve — as cláusulas sairiam sem
número. O export em texto do LibreOffice achata a numeração em literal.
Ver scripts/extrair_clausulas_docx.py (o protótipo que originou este módulo).

Sem banco. Sem estado.
"""
import os
import re
import subprocess
import tempfile

# Onde o corpo começa: tudo antes disto é capa (gerada pelo HTML, não pelo modelo).
_MARCO_INICIO = "CONTRATO DE COMPRA E VENDA"
# O adendo do ciclo entra imediatamente antes do fecho de assinaturas.
_MARCO_FECHO = "E assim, por estarem assim convencionados"

_RE_CLAUSULA = re.compile(r'^(?:\d+\.\s+)?(CLÁUSULA\b.*)$')

EXTENSOES_TEXTO = {".md", ".txt"}
EXTENSOES_OFFICE = {".docx", ".odt", ".doc", ".rtf"}


class FormatoNaoSuportado(Exception):
    pass


def extrair_corpo(texto: str) -> str:
    """Texto exportado do LibreOffice → Markdown das cláusulas.

    Corta a capa, vira 'CLÁUSULA ...' em heading '#', tira a indentação e
    insere [TEXTO_COMPLEMENTAR] antes do fecho de assinaturas.
    """
    if not (texto or "").strip():
        return ""
    linhas = texto.split("\n")
    ini = 0
    for i, l in enumerate(linhas):
        if l.strip().startswith(_MARCO_INICIO):
            ini = i
            break
    md = []
    for raw in linhas[ini:]:
        t = raw.strip()
        if not t:
            md.append("")
            continue
        m = _RE_CLAUSULA.match(t)
        md.append(f"# {m.group(1)}" if m else t)
    out = "\n".join(md).rstrip() + "\n"
    if _MARCO_FECHO in out and "[TEXTO_COMPLEMENTAR]" not in out:
        out = out.replace(_MARCO_FECHO,
                          f"[TEXTO_COMPLEMENTAR]\n\n{_MARCO_FECHO}", 1)
    return out


def normalizar(path: str) -> str:
    """Arquivo → texto puro.

    .md/.txt: leitura direta. .docx/.odt/.doc/.rtf: LibreOffice headless.
    .pdf: recusado — a extração perde a hierarquia das cláusulas.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext in EXTENSOES_TEXTO:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    if ext == ".pdf":
        raise FormatoNaoSuportado(
            "PDF não pode ser convertido em modelo: a extração de texto perde a "
            "hierarquia das cláusulas (títulos, numeração, alíneas). Envie o "
            "documento em Word (.docx), LibreOffice (.odt) ou texto."
        )
    if ext not in EXTENSOES_OFFICE:
        raise FormatoNaoSuportado(f"Formato não suportado: {ext or '(sem extensão)'}")

    from mod_contrato import _libreoffice_cmd, LibreOfficeIndisponivel
    outdir = tempfile.mkdtemp(prefix="orizon_import_")
    try:
        try:
            subprocess.run(
                [_libreoffice_cmd(), "--headless", "--convert-to",
                 "txt:Text (encoded):UTF8", "--outdir", outdir, path],
                check=True, capture_output=True, timeout=120,
            )
        except FileNotFoundError:
            raise LibreOfficeIndisponivel(path)
        except subprocess.TimeoutExpired:
            raise RuntimeError("LibreOffice demorou mais de 120s na conversão")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "LibreOffice falhou:\n%s" % e.stderr.decode(errors="replace"))
        base = os.path.splitext(os.path.basename(path))[0] + ".txt"
        destino = os.path.join(outdir, base)
        if not os.path.exists(destino):
            raise RuntimeError("LibreOffice não produziu o .txt esperado: %s" % destino)
        with open(destino, encoding="utf-8") as fh:
            return fh.read()
    finally:
        import shutil
        shutil.rmtree(outdir, ignore_errors=True)
```

- [ ] **Step 4: Registrar em `modulos.py`**

Acrescentar `"mod_documentos_import.py"` em `MODULOS["comercial"]["arquivos"]`.

- [ ] **Step 5: Rodar os testes**

Run: `python3 -m pytest tests/test_documentos_import.py tests/test_arquitetura_modulos.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add mod_documentos_import.py tests/test_documentos_import.py modulos.py
git commit -m "feat(documentos): extrair_corpo — texto do LibreOffice -> Markdown

Promove a lógica de scripts/extrair_clausulas_docx.py a módulo testável.
Função pura: testa sem LibreOffice instalado.

extrair_corpo preserva a numeração literal das cláusulas — é todo o motivo
de a importação passar pelo LibreOffice e não pelo python-docx."
```

---

### Task 3: `normalizar` — os formatos de entrada

O código de `normalizar` já foi escrito no Task 2. Aqui vão os testes que o cobrem — separados porque tocam o disco e o LibreOffice.

**Files:**
- Modify: `tests/test_documentos_import.py`

- [ ] **Step 1: Escrever os testes**

Acrescentar ao fim de `tests/test_documentos_import.py`:

```python
def test_normalizar_le_txt_direto(tmp_path):
    p = tmp_path / "modelo.txt"
    p.write_text("CONTRATO DE COMPRA E VENDA\n1.1. Teste.\n", encoding="utf-8")
    assert "1.1. Teste." in imp.normalizar(str(p))


def test_normalizar_le_md_direto(tmp_path):
    p = tmp_path / "modelo.md"
    p.write_text("# CLÁUSULA ÚNICA\n1.1. Teste.\n", encoding="utf-8")
    assert "1.1. Teste." in imp.normalizar(str(p))


def test_normalizar_recusa_pdf(tmp_path):
    p = tmp_path / "contrato.pdf"
    p.write_bytes(b"%PDF-1.4 fake")
    with pytest.raises(imp.FormatoNaoSuportado) as e:
        imp.normalizar(str(p))
    assert "PDF" in str(e.value)
    assert ".docx" in str(e.value), "a mensagem tem que dizer o que fazer"


def test_normalizar_recusa_extensao_desconhecida(tmp_path):
    p = tmp_path / "planilha.xlsx"
    p.write_bytes(b"fake")
    with pytest.raises(imp.FormatoNaoSuportado):
        imp.normalizar(str(p))


def test_formatos_office_aceitos_incluem_libreoffice():
    """O usuário pediu explicitamente .odt e outros formatos de texto."""
    assert {".docx", ".odt", ".doc", ".rtf"} <= imp.EXTENSOES_OFFICE
    assert ".pdf" not in imp.EXTENSOES_OFFICE
```

- [ ] **Step 2: Rodar**

Run: `python3 -m pytest tests/test_documentos_import.py -q`
Expected: PASS — o código já existe do Task 2.

Nenhum teste chama o LibreOffice de verdade: o caminho `.docx` depende de binário externo e não pode travar a suíte numa máquina sem ele. É verificado à mão no Task 9.

- [ ] **Step 3: Commit**

```bash
git add tests/test_documentos_import.py
git commit -m "test(documentos): normalizar — .txt/.md diretos, .odt/.doc/.rtf via LibreOffice, .pdf recusado"
```

---

### Task 4: Análise do corpo — marcadores e dados cravados

O que o wizard chama de "dados complementares". Três perguntas determinísticas.

**Files:**
- Modify: `mod_marcadores.py`
- Modify: `tests/test_marcadores.py`

- [ ] **Step 1: Escrever os testes (falhando)**

Acrescentar ao fim de `tests/test_marcadores.py`:

```python
LOJA_EXEMPLO = {
    "nome": "INSPIRIUM MÓVEIS PLANEJADOS E DECORAÇÃO LTDA",
    "cnpj": "19.152.134/0001-56",
    "cidade": "São José dos Campos",
    "logradouro": "Avenida Barão do Rio Branco",
}


def test_detecta_marcador_conhecido_usado():
    r = mod_marcadores.analisar_corpo("Cliente: [NOME_CLIENTE], CPF [CPF].", {})
    assert set(r["conhecidos_usados"]) == {"NOME_CLIENTE", "CPF"}


def test_detecta_marcador_desconhecido():
    """[FOO] sem verbete seria IMPRESSO literalmente no PDF (_aplica_mark
    devolve m.group(0) quando a chave não existe) — tem que bloquear."""
    r = mod_marcadores.analisar_corpo("Olá [FOO] e [NOME_CLIENTE].", {})
    assert r["desconhecidos"] == ["FOO"]
    assert r["bloqueia_ativacao"] is True


def test_sem_desconhecido_nao_bloqueia():
    r = mod_marcadores.analisar_corpo("Olá [NOME_CLIENTE].", {})
    assert r["desconhecidos"] == []
    assert r["bloqueia_ativacao"] is False


def test_aponta_marcador_essencial_ausente():
    r = mod_marcadores.analisar_corpo("Contrato sem nada.", {})
    assert "NOME_CLIENTE" in r["ausentes"]
    assert "NOME_TESTEMUNHA_1" in r["ausentes"]


def test_essencial_presente_sai_dos_ausentes():
    corpo = " ".join("[%s]" % c for c in mod_marcadores.ESSENCIAIS)
    assert mod_marcadores.analisar_corpo(corpo, {})["ausentes"] == []


def test_detecta_cnpj_da_loja_cravado_com_pontuacao_diferente():
    corpo = "inscrita no CNPJ/MF sob o n. 19152134000156, doravante CONTRATADA"
    cravados = mod_marcadores.analisar_corpo(corpo, LOJA_EXEMPLO)["cravados"]
    assert any(c["marcador"] == "CNPJ_EMPRESA" for c in cravados), \
        "CNPJ tem que casar sem pontuação"


def test_detecta_nome_e_cidade_da_loja_cravados():
    corpo = ("INSPIRIUM MÓVEIS PLANEJADOS E DECORAÇÃO LTDA, com sede em "
             "São José dos Campos, elegem o Foro da Comarca de São José dos Campos.")
    marcs = {c["marcador"] for c in mod_marcadores.analisar_corpo(corpo, LOJA_EXEMPLO)["cravados"]}
    assert "NOME_EMPRESA" in marcs
    assert "LOJA_CIDADE" in marcs


def test_cravado_traz_o_literal_para_a_tela_mostrar():
    corpo = "Foro da Comarca de São José dos Campos."
    c = [x for x in mod_marcadores.analisar_corpo(corpo, LOJA_EXEMPLO)["cravados"]
         if x["marcador"] == "LOJA_CIDADE"][0]
    assert c["literal"] == "São José dos Campos"
    assert c["ocorrencias"] == 1


def test_nao_inventa_cravado_quando_o_campo_da_loja_e_vazio():
    r = mod_marcadores.analisar_corpo("Texto qualquer.", {"nome": "", "cnpj": None})
    assert r["cravados"] == []


def test_campo_curto_da_loja_nao_gera_falso_positivo():
    """Cidade 'Sé' (2 letras) casaria dentro de mil palavras — ignorar."""
    r = mod_marcadores.analisar_corpo("A CONTRATADA se obriga.", {"cidade": "Sé"})
    assert r["cravados"] == []


def test_aplicar_cravados_troca_o_literal_pelo_marcador():
    corpo = "Foro da Comarca de São José dos Campos."
    novo = mod_marcadores.aplicar_cravados(corpo, LOJA_EXEMPLO, ["LOJA_CIDADE"])
    assert novo == "Foro da Comarca de [LOJA_CIDADE]."


def test_aplicar_cravados_ignora_o_que_nao_foi_aprovado():
    corpo = "INSPIRIUM MÓVEIS PLANEJADOS E DECORAÇÃO LTDA em São José dos Campos."
    novo = mod_marcadores.aplicar_cravados(corpo, LOJA_EXEMPLO, ["LOJA_CIDADE"])
    assert "[LOJA_CIDADE]" in novo
    assert "INSPIRIUM MÓVEIS PLANEJADOS E DECORAÇÃO LTDA" in novo, "não aprovado, não troca"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_marcadores.py -q`
Expected: FAIL — `AttributeError: module 'mod_marcadores' has no attribute 'analisar_corpo'`

- [ ] **Step 3: Implementar**

Acrescentar ao fim de `mod_marcadores.py`:

```python
import re as _re

# Reusa o regex do motor de substituição — se divergirem, a análise validaria
# um marcador que o renderizador não reconhece (ou o contrário).
from mod_contrato import _MARK_RE

# Sem estes, o documento sai quebrado: cliente sem nome, contrato sem data,
# fecho sem testemunha. O wizard avisa; não bloqueia (pode ser um modelo parcial).
ESSENCIAIS = ["NOME_CLIENTE", "CPF_CLIENTE", "DATA_CONTRATO",
              "NOME_EMPRESA", "CNPJ_EMPRESA",
              "NOME_TESTEMUNHA_1", "NOME_TESTEMUNHA_2"]

# Campos da loja que valem procurar cravados no texto → marcador correspondente.
_CRAVAVEIS = [
    ("cnpj",       "CNPJ_EMPRESA"),
    ("nome",       "NOME_EMPRESA"),
    ("logradouro", "LOJA_LOGRADOURO"),
    ("bairro",     "LOJA_BAIRRO"),
    ("cidade",     "LOJA_CIDADE"),
    ("cep",        "LOJA_CEP"),
]

# Abaixo disto, o valor casa por acidente ("Sé", "SP", nº "12").
_MIN_LITERAL = 4


def _so_digitos(s):
    return _re.sub(r"\D", "", s or "")


def _chaves_usadas(corpo_md):
    return [m.group(1).strip().upper().replace(" ", "_")
            for m in _MARK_RE.finditer(corpo_md or "")]


def analisar_corpo(corpo_md, loja):
    """Analisa um corpo importado contra o catálogo e o cadastro da loja.

    Devolve:
      conhecidos_usados  marcadores do catálogo presentes no corpo
      desconhecidos      [FOO] sem verbete — seria impresso literal no PDF
      ausentes           essenciais que o corpo não tem
      cravados           dados da loja literais no texto, candidatos a marcador
      bloqueia_ativacao  True se há desconhecido
    """
    loja = loja or {}
    usadas = _chaves_usadas(corpo_md)
    conhecidos = [c for c in dict.fromkeys(usadas) if c in CATALOGO]
    desconhecidos = [c for c in dict.fromkeys(usadas) if c not in CATALOGO]
    ausentes = [c for c in ESSENCIAIS if c not in usadas]

    cravados = []
    for campo, marcador in _CRAVAVEIS:
        valor = (loja.get(campo) or "").strip()
        if len(valor) < _MIN_LITERAL:
            continue
        n = (corpo_md or "").count(valor)
        if n:
            cravados.append({"marcador": marcador, "literal": valor,
                             "ocorrencias": n, "campo": campo})
            continue
        # CNPJ/CEP: o documento pode usar pontuação diferente do cadastro.
        if campo in ("cnpj", "cep"):
            nus = _so_digitos(valor)
            if len(nus) >= _MIN_LITERAL and nus in _so_digitos(corpo_md):
                cravados.append({"marcador": marcador, "literal": valor,
                                 "ocorrencias": 1, "campo": campo,
                                 "so_digitos": True})
    return {"conhecidos_usados": conhecidos, "desconhecidos": desconhecidos,
            "ausentes": ausentes, "cravados": cravados,
            "bloqueia_ativacao": bool(desconhecidos)}


def aplicar_cravados(corpo_md, loja, marcadores_aprovados):
    """Troca pelo marcador só os literais que o lojista aprovou."""
    loja = loja or {}
    aprovados = set(marcadores_aprovados or [])
    out = corpo_md or ""
    for campo, marcador in _CRAVAVEIS:
        if marcador not in aprovados:
            continue
        valor = (loja.get(campo) or "").strip()
        if len(valor) < _MIN_LITERAL:
            continue
        out = out.replace(valor, "[%s]" % marcador)
    return out
```

**Nota sobre `so_digitos`:** quando o CNPJ casa só sem pontuação, `aplicar_cravados` **não** troca (o literal do documento difere do cadastro). A tela mostra o achado para o lojista corrigir à mão. Trocar por regex de dígitos arriscaria pegar outro CNPJ do texto — num contrato, não vale o risco.

- [ ] **Step 4: Rodar**

Run: `python3 -m pytest tests/test_marcadores.py -q`
Expected: PASS.

- [ ] **Step 5: Suíte inteira e commit**

Run: `python3 -m pytest -q` → tudo verde.

```bash
git add mod_marcadores.py tests/test_marcadores.py
git commit -m "feat(documentos): análise do corpo — ausentes, desconhecidos e dados da loja cravados

Marcador desconhecido bloqueia ativação: _aplica_mark mantém no texto o que
não tem chave, então [FOO] sairia impresso literal no PDF.

Cravados: varre o corpo atrás do CNPJ/nome/endereço da própria loja e propõe
virar marcador — é o que parametriza o preâmbulo (INSPIRIUM/foro) por loja.
Só troca o que o lojista aprovar."
```

---

### Task 5: Tabela e registro versionado

**Files:**
- Modify: `database.py` (classe nova + `_migrar_colunas`)
- Create: `mod_documentos.py`
- Create: `tests/test_documentos_registro.py`
- Modify: `modulos.py` (arquivos + tabelas)

- [ ] **Step 1: Escrever os testes (falhando)**

Criar `tests/test_documentos_registro.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
import mod_documentos


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Banco isolado por teste."""
    import database
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "t.db"))
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    eng = create_engine("sqlite:///" + str(tmp_path / "t.db"))
    database.Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng)
    s = S()
    yield s
    s.close()


def test_criar_versao_comeca_em_1(db):
    m = mod_documentos.criar_versao(db, loja_id=1, tipo="contrato",
                                    corpo_md="# CLÁUSULA\n1.1. Ok.\n",
                                    origem_nome="c.docx", usuario_id=1)
    assert m.versao == 1


def test_versoes_sao_sequenciais_por_loja_e_tipo(db):
    mod_documentos.criar_versao(db, 1, "contrato", "a", "c.docx", 1)
    m2 = mod_documentos.criar_versao(db, 1, "contrato", "b", "c.docx", 1)
    outra_loja = mod_documentos.criar_versao(db, 2, "contrato", "c", "c.docx", 1)
    outro_tipo = mod_documentos.criar_versao(db, 1, "proposta", "d", "p.docx", 1)
    assert m2.versao == 2
    assert outra_loja.versao == 1, "loja 2 tem sequência própria"
    assert outro_tipo.versao == 1, "proposta tem sequência própria"


def test_ativar_desliga_a_anterior(db):
    m1 = mod_documentos.criar_versao(db, 1, "contrato", "a", "c.docx", 1)
    m2 = mod_documentos.criar_versao(db, 1, "contrato", "b", "c.docx", 1)
    mod_documentos.ativar(db, m1.id)
    mod_documentos.ativar(db, m2.id)
    db.refresh(m1)
    assert m1.ativo == 0
    assert m2.ativo == 1


def test_ativar_nao_mexe_em_outro_tipo(db):
    c = mod_documentos.criar_versao(db, 1, "contrato", "a", "c.docx", 1)
    p = mod_documentos.criar_versao(db, 1, "proposta", "b", "p.docx", 1)
    mod_documentos.ativar(db, c.id)
    mod_documentos.ativar(db, p.id)
    db.refresh(c)
    assert c.ativo == 1, "ativar proposta não pode desligar o contrato"


def test_resolver_modelo_devolve_a_versao_ativa(db):
    m = mod_documentos.criar_versao(db, 1, "contrato", "CORPO DA LOJA", "c.docx", 1)
    mod_documentos.ativar(db, m.id)
    assert mod_documentos.resolver_modelo(db, 1, "contrato") == "CORPO DA LOJA"


def test_resolver_modelo_cai_no_global_quando_a_loja_nao_tem(db):
    """Loja sem modelo próprio continua igual a hoje — migração zero."""
    import mod_contrato
    assert mod_documentos.resolver_modelo(db, 99, "contrato") == mod_contrato._carregar_md()


def test_resolver_modelo_de_proposta_sem_modelo_e_vazio(db):
    """Proposta é capa-só hoje: sem modelo, corpo vazio (spec §8.2)."""
    assert mod_documentos.resolver_modelo(db, 99, "proposta") == ""


def test_resolver_modelo_ignora_versao_inativa(db):
    mod_documentos.criar_versao(db, 1, "contrato", "RASCUNHO", "c.docx", 1)
    import mod_contrato
    assert mod_documentos.resolver_modelo(db, 1, "contrato") == mod_contrato._carregar_md()


def test_listar_e_escopado_por_loja(db):
    mod_documentos.criar_versao(db, 1, "contrato", "a", "c.docx", 1)
    mod_documentos.criar_versao(db, 2, "contrato", "b", "c.docx", 1)
    assert len(mod_documentos.listar(db, 1)) == 1, "loja A não pode ver modelo da loja B"


def test_tipo_invalido_e_recusado(db):
    with pytest.raises(ValueError):
        mod_documentos.criar_versao(db, 1, "custom", "a", "x.docx", 1)


def test_corpo_vazio_e_recusado(db):
    with pytest.raises(ValueError):
        mod_documentos.criar_versao(db, 1, "contrato", "   ", "c.docx", 1)


def test_original_do_staging_e_promovido_para_a_versao(db, tmp_path, monkeypatch):
    """Auditoria (spec §3): o arquivo subido tem que sobreviver ao lado da versão."""
    monkeypatch.setattr(mod_documentos, "DOCS_LOJA_DIR", str(tmp_path / "docs"))
    caminho, sha = mod_documentos.guardar_staging(1, "contrato", "meu.docx", b"conteudo-x")
    assert os.path.exists(caminho)
    m = mod_documentos.criar_versao(db, 1, "contrato", "# C\n1.1. Ok.\n", "meu.docx", 1,
                                    staging_path=caminho, origem_sha256=sha)
    assert m.origem_sha256 == sha
    assert m.origem_path and os.path.exists(m.origem_path)
    assert "v1" in m.origem_path
    assert not os.path.exists(caminho), "o staging foi movido, não copiado"
    assert open(m.origem_path, "rb").read() == b"conteudo-x"


def test_criar_versao_sem_staging_nao_explode(db):
    m = mod_documentos.criar_versao(db, 1, "contrato", "# C\n1.1. Ok.\n", "c.docx", 1)
    assert m.origem_path is None
```

O `import os` no topo do arquivo de teste é necessário para estes dois — já está lá.

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_documentos_registro.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'mod_documentos'`

- [ ] **Step 3: Criar a tabela em `database.py`**

Acrescentar após a classe `CicloDocumento` (que termina por volta da linha 880):

```python
class DocumentoModelo(Base):
    """Modelo de documento de uma loja (contrato/proposta), versionado.

    IMUTÁVEL: uma versão nunca muda de corpo_md depois de criada. Editar é criar
    a versão seguinte. É o que dá sentido a Contrato.modelo_versao_id — se a linha
    fosse mutável, o ponteiro não garantiria a reprodução do contrato assinado.
    """
    __tablename__ = "documento_modelos"

    id            = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id       = Column(Integer,  ForeignKey("lojas.id"), nullable=False)
    tipo          = Column(Text,     nullable=False)   # contrato | proposta
    versao        = Column(Integer,  nullable=False)   # sequencial por (loja_id, tipo)
    nome          = Column(Text,     nullable=True)
    corpo_md      = Column(Text,     nullable=False)
    origem_nome   = Column(Text,     nullable=True)
    origem_path   = Column(Text,     nullable=True)
    origem_sha256 = Column(Text,     nullable=True)
    ativo         = Column(Integer,  nullable=False, default=0)
    criado_em     = Column(DateTime, default=datetime.utcnow)
    criado_por_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("loja_id", "tipo", "versao", name="uq_doc_modelo_versao"),
    )
```

`UniqueConstraint` precisa estar importado no topo de `database.py`. Verifique com `grep -n "UniqueConstraint" database.py`; se não estiver, acrescente ao `from sqlalchemy import (...)` existente.

- [ ] **Step 4: Criar `mod_documentos.py`**

```python
# -*- coding: utf-8 -*-
"""mod_documentos.py — Registro versionado dos modelos de documento por loja.

Único módulo da frente que fala com o banco (mod_marcadores e
mod_documentos_import são puros).

Regra central: uma versão é IMUTÁVEL. Editar = criar a próxima. Contrato aponta
para a versão que o gerou (Contrato.modelo_versao_id), então regerar um contrato
antigo reproduz as cláusulas originais mesmo que a loja já tenha trocado o modelo.

Fallback: loja sem modelo ativo cai no arquivo global de hoje
(contrato_template/contrato.md) — nada quebra para quem não subiu nada.
"""
import os
import hashlib

from database import DocumentoModelo

TIPOS = ("contrato", "proposta")

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_LOJA_DIR = os.path.join(_THIS_DIR, "documentos_loja")


def _validar(tipo, corpo_md):
    if tipo not in TIPOS:
        raise ValueError("tipo inválido: %r (aceitos: %s)" % (tipo, ", ".join(TIPOS)))
    if not (corpo_md or "").strip():
        raise ValueError("corpo do modelo vazio")


def _proxima_versao(db, loja_id, tipo):
    ultima = (db.query(DocumentoModelo)
                .filter(DocumentoModelo.loja_id == loja_id,
                        DocumentoModelo.tipo == tipo)
                .order_by(DocumentoModelo.versao.desc())
                .first())
    return (ultima.versao + 1) if ultima else 1


def guardar_staging(loja_id, tipo, origem_nome, conteudo_bytes):
    """Guarda o arquivo subido ANTES de a versão existir.

    A importação analisa sem salvar a versão, então o original fica no staging
    até o lojista ativar; criar_versao o promove para v<N>/. Devolve (caminho, sha256).
    """
    d = os.path.join(DOCS_LOJA_DIR, str(loja_id), tipo, "_staging")
    os.makedirs(d, exist_ok=True)
    sha = hashlib.sha256(conteudo_bytes).hexdigest()
    caminho = os.path.join(d, sha[:16] + os.path.splitext(origem_nome or "")[1].lower())
    with open(caminho, "wb") as fh:
        fh.write(conteudo_bytes)
    return caminho, sha


def _promover_original(staging_path, loja_id, tipo, versao, origem_nome):
    """Move o original do staging para v<N>/. Devolve o caminho final, ou None."""
    if not staging_path or not os.path.exists(staging_path):
        return None
    import shutil
    destino_dir = os.path.join(DOCS_LOJA_DIR, str(loja_id), tipo, "v%d" % versao)
    os.makedirs(destino_dir, exist_ok=True)
    destino = os.path.join(destino_dir, os.path.basename(origem_nome or "original"))
    shutil.move(staging_path, destino)
    return destino


def criar_versao(db, loja_id, tipo, corpo_md, origem_nome, usuario_id,
                 nome=None, staging_path=None, origem_sha256=None):
    """Cria a próxima versão (inativa). Ativar é passo à parte — ver ativar().

    staging_path: original vindo de guardar_staging(); é promovido para v<N>/
    aqui, quando o número da versão finalmente existe.
    """
    _validar(tipo, corpo_md)
    versao = _proxima_versao(db, loja_id, tipo)
    origem_path = _promover_original(staging_path, loja_id, tipo, versao, origem_nome)
    m = DocumentoModelo(
        loja_id=loja_id, tipo=tipo, versao=versao,
        nome=nome or os.path.splitext(os.path.basename(origem_nome or ""))[0] or None,
        corpo_md=corpo_md, origem_nome=origem_nome, origem_path=origem_path,
        origem_sha256=origem_sha256, ativo=0, criado_por_id=usuario_id,
    )
    db.add(m)
    db.commit()
    return m


def ativar(db, modelo_id):
    """Liga esta versão e desliga a anterior do mesmo (loja, tipo)."""
    m = db.query(DocumentoModelo).get(modelo_id)
    if m is None:
        raise ValueError("modelo não encontrado: %s" % modelo_id)
    (db.query(DocumentoModelo)
       .filter(DocumentoModelo.loja_id == m.loja_id,
               DocumentoModelo.tipo == m.tipo,
               DocumentoModelo.id != m.id)
       .update({"ativo": 0}))
    m.ativo = 1
    db.commit()
    return m


def ativo_de(db, loja_id, tipo):
    return (db.query(DocumentoModelo)
              .filter(DocumentoModelo.loja_id == loja_id,
                      DocumentoModelo.tipo == tipo,
                      DocumentoModelo.ativo == 1)
              .first())


def corpo_da_versao(db, modelo_versao_id):
    """Corpo de uma versão específica — o caminho de reprodução do contrato antigo."""
    m = db.query(DocumentoModelo).get(modelo_versao_id)
    return m.corpo_md if m else None


def resolver_modelo(db, loja_id, tipo):
    """Corpo vigente para (loja, tipo).

    Sem modelo ativo: contrato cai no arquivo global (comportamento de hoje);
    proposta devolve "" (hoje ela é capa-só — spec §8.2).
    """
    m = ativo_de(db, loja_id, tipo)
    if m is not None:
        return m.corpo_md
    if tipo == "contrato":
        import mod_contrato
        return mod_contrato._carregar_md()
    return ""


def listar(db, loja_id):
    """Modelos da loja, mais novo primeiro. Escopado por loja (tenancy)."""
    return (db.query(DocumentoModelo)
              .filter(DocumentoModelo.loja_id == loja_id)
              .order_by(DocumentoModelo.tipo, DocumentoModelo.versao.desc())
              .all())
```

- [ ] **Step 5: Registrar em `modulos.py`**

Em `MODULOS["comercial"]`: acrescentar `"mod_documentos.py"` em `arquivos` e `"documento_modelos"` em `tabelas`.

- [ ] **Step 6: `.gitignore`**

Acrescentar ao `.gitignore`:

```
documentos_loja/
```

- [ ] **Step 7: Rodar**

Run: `python3 -m pytest tests/test_documentos_registro.py tests/test_arquitetura_modulos.py -q`
Expected: PASS.

- [ ] **Step 8: Suíte inteira e commit**

Run: `python3 -m pytest -q` → verde.

```bash
git add database.py mod_documentos.py tests/test_documentos_registro.py modulos.py .gitignore
git commit -m "feat(documentos): tabela documento_modelos + registro versionado por loja

Versão imutável, sequencial por (loja, tipo), uma ativa por vez.
resolver_modelo cai no contrato_template/contrato.md global quando a loja
não tem modelo próprio — migração zero para quem já usa o sistema.

documentos_loja/ (originais subidos) fora do git: é dado de cliente."
```

---

### Task 6: O contrato fixa a versão que usou

**O task que justifica a frente inteira.** Hoje `gerar_pdf_contrato()` regenera `CONTRATOS/contrato_<id>.pdf` sobrescrevendo pelo id e lê o modelo do disco na hora — trocar o modelo reescreveria, em silêncio, as cláusulas de um contrato **já assinado**.

**Files:**
- Modify: `database.py` (coluna + `_migrar_colunas`)
- Modify: `mod_contrato.py:730-752` (`_montar_html_contrato`)
- Create: `tests/test_documentos_versionamento.py`

- [ ] **Step 1: Escrever o teste (falhando)**

Criar `tests/test_documentos_versionamento.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
import mod_documentos
import mod_contrato


@pytest.fixture
def db(tmp_path, monkeypatch):
    import database
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "t.db"))
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    eng = create_engine("sqlite:///" + str(tmp_path / "t.db"))
    database.Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


# _montar_html_contrato chama _html_capa(ctx), que espera um contexto COMPLETO.
# Monte-o com construir_contexto, como faz tests/test_contrato.py:303-309 — ctx
# montado na mão quebra na capa, não no que estamos testando.
CLIENTE = {"nome": "CLIENTE TESTE", "cpf": "000.000.000-00",
           "email": "t@t.com", "telefone": "(12) 90000-0000",
           "logradouro": "Rua X", "numero": "1", "bairro": "Centro",
           "cidade": "São José dos Campos", "estado": "SP", "cep": "12200-000",
           "inst_mesmo_residencial": True}
USUARIO = {"nome": "Consultor", "telefone": "", "email": ""}
LOJA = {"id": 1, "nome": "LOJA TESTE", "cnpj": "00.000.000/0001-00",
        "cidade": "São José dos Campos"}


def _ctx(**extra):
    ctx = mod_contrato.construir_contexto(CLIENTE, USUARIO, "", LOJA)
    ctx.update(extra)
    return ctx


def test_contrato_tem_a_coluna_modelo_versao_id():
    from database import Contrato
    assert hasattr(Contrato, "modelo_versao_id")


def test_corpo_da_versao_devolve_o_corpo_congelado(db):
    m = mod_documentos.criar_versao(db, 1, "contrato", "# CLÁUSULA V1\n1.1. Original.\n",
                                    "c.docx", 1)
    mod_documentos.ativar(db, m.id)
    m2 = mod_documentos.criar_versao(db, 1, "contrato", "# CLÁUSULA V2\n1.1. Nova.\n",
                                     "c2.docx", 1)
    mod_documentos.ativar(db, m2.id)
    assert "Original" in mod_documentos.corpo_da_versao(db, m.id), \
        "a versão 1 é imutável — ativar a 2 não pode alterá-la"
    assert "Nova" in mod_documentos.corpo_da_versao(db, m2.id)


def test_regerar_contrato_antigo_reproduz_as_clausulas_originais(db):
    """A garantia jurídica da frente. Sem este verde, o versionamento é decorativo."""
    v1 = mod_documentos.criar_versao(db, 1, "contrato",
                                     "# CLÁUSULA PRIMEIRA\n1.1. Texto ORIGINAL assinado.\n",
                                     "c.docx", 1)
    mod_documentos.ativar(db, v1.id)

    ctx_assinado = _ctx(_db=db, _modelo_versao_id=v1.id)
    html_na_assinatura = mod_contrato._montar_html_contrato(ctx_assinado)
    assert "Texto ORIGINAL assinado." in html_na_assinatura

    # a loja troca o modelo depois da assinatura
    v2 = mod_documentos.criar_versao(db, 1, "contrato",
                                     "# CLÁUSULA PRIMEIRA\n1.1. Texto NOVO da loja.\n",
                                     "c2.docx", 1)
    mod_documentos.ativar(db, v2.id)

    html_regerado = mod_contrato._montar_html_contrato(ctx_assinado)
    assert "Texto ORIGINAL assinado." in html_regerado, \
        "regerar contrato assinado NÃO pode trazer a cláusula nova"
    assert "Texto NOVO da loja." not in html_regerado


def test_contrato_sem_versao_cai_no_template_global(db):
    """Contrato legado (sem _db no ctx) segue idêntico a hoje."""
    html = mod_contrato._montar_html_contrato(_ctx())
    global_md = mod_contrato._carregar_md()
    if global_md.strip():
        primeira = [l for l in global_md.split("\n") if l.strip()][0]
        assert primeira[:20] in html


def test_contrato_com_db_mas_sem_versao_nem_modelo_cai_no_global(db):
    """Loja sem modelo próprio: mesmo com _db, usa o template global."""
    html = mod_contrato._montar_html_contrato(_ctx(_db=db))
    global_md = mod_contrato._carregar_md()
    if global_md.strip():
        primeira = [l for l in global_md.split("\n") if l.strip()][0]
        assert primeira[:20] in html
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_documentos_versionamento.py -q`
Expected: FAIL — `AttributeError: type object 'Contrato' has no attribute 'modelo_versao_id'`

- [ ] **Step 3: Coluna em `database.py`**

Na classe `Contrato` (linha ~825), após `loja_snapshot_json`:

```python
    modelo_versao_id     = Column(Integer, ForeignKey("documento_modelos.id"), nullable=True)
    # NULL = contrato legado -> cai no contrato_template/contrato.md global.
    # Preenchido = reproduz as cláusulas daquela versão, mesmo que a loja já
    # tenha trocado o modelo. Ver docs/superpowers/specs/2026-07-15-modelos-documentos-loja-design.md D6.
```

Em `_migrar_colunas()` (`database.py:1003`), acrescentar um bloco no mesmo padrão dos existentes:

```python
        # ── contratos ────────────────────────────────────────────────────────
        cur.execute("PRAGMA table_info(contratos)")
        ctr_cols = {row[1] for row in cur.fetchall()}
        if "modelo_versao_id" not in ctr_cols:
            cur.execute("ALTER TABLE contratos ADD COLUMN modelo_versao_id INTEGER")
```

Se já existir um bloco `# ── contratos ──` em `_migrar_colunas`, acrescente só o `if` dentro dele em vez de duplicar o `PRAGMA`.

- [ ] **Step 4: `_montar_html_contrato` resolve o corpo**

Em `mod_contrato.py`, trocar a linha 746 (`corpo = _html_corpo(_carregar_md())`) por:

```python
    corpo = _html_corpo(_resolver_corpo_contrato(ctx))
```

E acrescentar, logo antes de `_montar_html_contrato` (linha ~730):

```python
def _resolver_corpo_contrato(ctx):
    """Markdown das cláusulas deste contrato.

    Ordem: versão fixada no contrato (reproduz o assinado) > modelo ativo da
    loja > contrato_template/contrato.md global (contrato legado / loja sem
    modelo próprio). ctx['_db'] e ctx['_modelo_versao_id'] vêm do chamador;
    sem eles o comportamento é o de hoje.
    """
    db = ctx.get("_db")
    if db is None:
        return _carregar_md()
    import mod_documentos
    versao_id = ctx.get("_modelo_versao_id")
    if versao_id:
        corpo = mod_documentos.corpo_da_versao(db, versao_id)
        if corpo is not None:
            return corpo
    loja_id = (ctx.get("loja") or {}).get("id")
    if loja_id:
        return mod_documentos.resolver_modelo(db, loja_id, "contrato")
    return _carregar_md()
```

**Sem `_db` no ctx, nada muda** — todo chamador atual continua no caminho do arquivo global. É o que mantém `tests/test_contrato.py` verde.

- [ ] **Step 5: Rodar**

Run: `python3 -m pytest tests/test_documentos_versionamento.py tests/test_contrato.py -q`
Expected: PASS. Se `test_contrato.py` quebrar, `_resolver_corpo_contrato` está caindo no caminho novo sem `_db` — revise o `if db is None`.

- [ ] **Step 6: A regra de qual versão vale para cada contrato**

Cuidado aqui — é onde a frente inteira pode ser anulada por uma linha.

`modelo_versao_id is None` significa **duas coisas diferentes**:
- contrato **novo**, nunca gerado → deve adotar o modelo ativo e fixá-lo;
- contrato **legado**, gerado antes desta feature → **não pode** adotar modelo nenhum. Adotar reescreveria as cláusulas de um contrato possivelmente já assinado — o exato problema que o D6 existe para impedir.

O que separa os dois é `gerado_em`. Acrescentar em `mod_documentos.py`:

```python
def versao_para_contrato(db, contrato, loja_id):
    """Qual versão de modelo vale para ESTE contrato. Fixa, se for o caso.

    - já fixada          -> ela (reproduz o assinado, mesmo com modelo novo ativo)
    - nunca gerado       -> modelo ativo da loja, e FIXA em contrato.modelo_versao_id
    - legado (já gerado, -> None: cai no template global. NUNCA adotar modelo novo
      sem versão)           num contrato já gerado — reescreveria cláusula assinada.

    Devolve o id da versão, ou None para 'usar o template global'.
    """
    if contrato.modelo_versao_id:
        return contrato.modelo_versao_id
    if contrato.gerado_em is not None:
        return None
    m = ativo_de(db, loja_id, "contrato")
    if m is None:
        return None
    contrato.modelo_versao_id = m.id
    db.commit()
    return m.id
```

Acrescentar o teste em `tests/test_documentos_versionamento.py`:

```python
class _ContratoFake:
    """Só o que versao_para_contrato lê — evita montar um Contrato completo."""
    def __init__(self, modelo_versao_id=None, gerado_em=None):
        self.modelo_versao_id = modelo_versao_id
        self.gerado_em = gerado_em


def test_contrato_novo_adota_e_fixa_o_modelo_ativo(db):
    m = mod_documentos.criar_versao(db, 1, "contrato", "# C\n1.1. Ok.\n", "c.docx", 1)
    mod_documentos.ativar(db, m.id)
    c = _ContratoFake(gerado_em=None)
    assert mod_documentos.versao_para_contrato(db, c, 1) == m.id
    assert c.modelo_versao_id == m.id, "tem que FIXAR, não só devolver"


def test_contrato_legado_nunca_adota_modelo_novo(db):
    """O contrato já foi gerado (e talvez assinado) antes de a loja ter modelo.
    Regerar NÃO pode trazer as cláusulas novas."""
    from datetime import datetime
    m = mod_documentos.criar_versao(db, 1, "contrato", "# NOVO\n1.1. Cláusula nova.\n", "c.docx", 1)
    mod_documentos.ativar(db, m.id)
    legado = _ContratoFake(gerado_em=datetime(2026, 1, 1))
    assert mod_documentos.versao_para_contrato(db, legado, 1) is None
    assert legado.modelo_versao_id is None


def test_contrato_ja_fixado_ignora_o_modelo_ativo(db):
    v1 = mod_documentos.criar_versao(db, 1, "contrato", "# V1\n1.1. Original.\n", "c.docx", 1)
    v2 = mod_documentos.criar_versao(db, 1, "contrato", "# V2\n1.1. Nova.\n", "c2.docx", 1)
    mod_documentos.ativar(db, v2.id)
    c = _ContratoFake(modelo_versao_id=v1.id, gerado_em=None)
    assert mod_documentos.versao_para_contrato(db, c, 1) == v1.id


def test_contrato_novo_sem_modelo_na_loja_fica_no_global(db):
    c = _ContratoFake(gerado_em=None)
    assert mod_documentos.versao_para_contrato(db, c, 1) is None
```

Run: `python3 -m pytest tests/test_documentos_versionamento.py -q` → PASS.

- [ ] **Step 7: Ligar nos DOIS call sites**

`gerar_pdf_contrato` é chamado em **dois lugares** (`main.py:6070` e `main.py:7532`) — os dois passam `variaveis` como ctx. **Ligar em só um deixa metade dos contratos sem versão.**

Confirme: `grep -n "gerar_pdf_contrato" main.py` → espere as linhas 54 (import), 6070 e 7532.

Em **ambos**, imediatamente antes do `pdf_path = gerar_pdf_contrato(contrato.id, variaveis)`:

```python
                    # Fixa a versão do modelo que gerou este contrato: regerar
                    # depois reproduz estas cláusulas mesmo que a loja troque o
                    # modelo. Contrato legado (já gerado, sem versão) fica no
                    # template global. (spec D6)
                    import mod_documentos as _mdoc
                    variaveis["_db"] = db
                    variaveis["_modelo_versao_id"] = _mdoc.versao_para_contrato(
                        db, contrato, contrato.loja_id or loja_id)
```

**Atenção no call site 6070:** a linha `contrato.gerado_em = datetime.utcnow()` (≈6056) roda **antes** desse ponto, o que faria todo contrato parecer legado. Capture o estado **no topo do handler**, antes daquela atribuição:

```python
                    _primeira_geracao = contrato.gerado_em is None
```

e passe um objeto com o valor original — ou, mais simples, mova a atribuição de `gerado_em` para **depois** do bloco de binding. Prefira mover: menos estado a carregar.

Verifique qual variável de loja existe em cada handler (`loja_id` vs `contrato.loja_id`) — o `or` acima cobre os dois.

`_loja_dict_para_contrato()` **já devolve `"id"`** (`main.py:8760`), então `ctx["loja"]["id"]` funciona sem mudança.

- [ ] **Step 8: Restart e verificação manual**

```bash
python3 main.py
```

Gerar um contrato pela tela. Esperado: PDF idêntico ao de antes (nenhuma loja tem modelo ainda → cai no global). Regerar o mesmo contrato: idêntico de novo.

- [ ] **Step 9: Suíte e commit**

Run: `python3 -m pytest -q` → verde.

```bash
git add database.py mod_contrato.py mod_documentos.py main.py tests/test_documentos_versionamento.py
git commit -m "feat(documentos): contrato fixa a versão do modelo que o gerou

gerar_pdf_contrato regenera o PDF pelo id lendo o modelo do disco na hora —
trocar o modelo reescreveria as cláusulas de um contrato JÁ ASSINADO.

Agora Contrato.modelo_versao_id congela a versão; regerar reproduz o corpo
original. NULL (contrato legado) cai no template global: backfill zero.

versao_para_contrato distingue 'novo, nunca gerado' (adota e fixa o modelo
ativo) de 'legado, já gerado sem versão' (fica no global) — os dois têm
modelo_versao_id NULL, e tratar igual reescreveria cláusula de contrato
legado já assinado.

Ligado nos DOIS call sites de gerar_pdf_contrato (main.py:6070 e 7532).

Teste: regerar contrato antigo com modelo novo ativo reproduz as cláusulas
originais."
```

---

### Task 7: Capacidade `gerir_documentos`

**Files:**
- Modify: `perfis.py:11-53` (PERFIS + `_DEFAULT`), `:148` (CAPACIDADES), `:252` (CAPS_SELECIONAVEIS)
- Create: `tests/test_perfis_gerir_documentos.py`

- [ ] **Step 1: Escrever os testes (falhando)**

Criar `tests/test_perfis_gerir_documentos.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import perfis


def test_master_pode():
    assert perfis.pode("master", "gerir_documentos") is True


def test_gerencial_e_operador_nao_podem():
    """Trocar cláusula de contrato não vem de brinde com o perfil gerencial."""
    assert perfis.pode("gerencial", "gerir_documentos") is False
    assert perfis.pode("operador", "gerir_documentos") is False


def test_e_selecionavel_por_perfil():
    assert "gerir_documentos" in perfis.CAPS_SELECIONAVEIS


def test_tem_verbete_no_catalogo_de_capacidades():
    v = perfis.CAPACIDADES["gerir_documentos"]
    assert v["rotulo"] and v["descricao"] and v["grupo"]


def test_perfil_desconhecido_nao_pode():
    assert perfis.pode("perfil_que_nao_existe", "gerir_documentos") is False
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_perfis_gerir_documentos.py -q`
Expected: FAIL — `pode("master", "gerir_documentos")` devolve False (cai no `_DEFAULT`).

- [ ] **Step 3: Implementar**

Em `perfis.py`, quatro edições:

1. `PERFIS["master"]` (linha ~17) — acrescentar ao dict: `"gerir_documentos": True,`
2. `PERFIS["gerencial"]` (linha ~23) — acrescentar: `"gerir_documentos": False,`
3. `PERFIS["operador"]` (linha ~29) — acrescentar: `"gerir_documentos": False,`
4. `_DEFAULT` (linha ~50) — acrescentar: `"gerir_documentos": False,`

Em `CAPACIDADES` (linha 148), acrescentar o verbete:

```python
    "gerir_documentos":          {"rotulo": "Gerir modelos de documento", "grupo": "Config",
        "descricao": "Importar e ativar os modelos de contrato/proposta da loja (altera as cláusulas dos documentos gerados)."},
```

Em `CAPS_SELECIONAVEIS` (linha 252), acrescentar `"gerir_documentos"`:

```python
CAPS_SELECIONAVEIS = ["ver_parametros", "autorizar", "aprovar_financeiro", "gerir_usuarios",
                      "gerir_perfis", "editar_dados_loja", "gerir_documentos",
                      "registrar_medicao", "aprovar_medicao_reprovada", "executar_pe", "revisar_pe"]
```

`super_admin`/`admin_rede` **não** ganham a capacidade: são perfis de plataforma/rede, e o modelo é da loja.

- [ ] **Step 4: Rodar**

Run: `python3 -m pytest tests/test_perfis_gerir_documentos.py tests/test_perfil_migracao_nivel.py -q`
Expected: PASS.

- [ ] **Step 5: Suíte e commit**

Run: `python3 -m pytest -q` → verde.

`perfis_config.json` **não** entra no commit (é ruído, ver CLAUDE.md).

```bash
git add perfis.py tests/test_perfis_gerir_documentos.py
git commit -m "feat(documentos): capacidade gerir_documentos (só master por padrão)

Trocar cláusula de contrato não é o mesmo risco que editar o telefone da
loja — por isso capacidade própria, e não reuso de editar_dados_loja."
```

Se `docs/USUARIOS.md` existir, atualize a tabela de capacidades (`perfis.py:4` manda).

---

### Task 8: Endpoints

**Files:**
- Modify: `main.py`
- Modify: `modulos.py` (rotas)
- Create: `tests/test_documentos_api.py`

- [ ] **Step 1: Escrever o teste de gate (falhando)**

O projeto não tem harness de HTTP nos testes; o gate é testado na função de permissão. Criar `tests/test_documentos_api.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
import mod_documentos


def test_tipos_expostos_sao_so_contrato_e_proposta():
    """'custom' fica para o spec seguinte — a API não pode aceitar ainda."""
    assert mod_documentos.TIPOS == ("contrato", "proposta")


def test_criar_versao_recusa_tipo_fora_da_lista():
    with pytest.raises(ValueError):
        mod_documentos.criar_versao(None, 1, "termo_medicao", "a", "x.docx", 1)
```

- [ ] **Step 2: Rodar**

Run: `python3 -m pytest tests/test_documentos_api.py -q`
Expected: PASS (o Task 5 já garante). Serve de trava contra alguém liberar `custom` cedo demais.

- [ ] **Step 3: Implementar os endpoints**

Em `main.py`, seguindo o padrão dos handlers existentes (veja o de proposta em `main.py:1817-1870` para o formato de rota/sessão/escopo).

**GET** — junto dos outros GET `/api/...`:

```python
            # ── GET /api/documentos/marcadores — catálogo p/ a tela ──
            if path == "/api/documentos/marcadores":
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                import mod_marcadores
                itens = [{"chave": k, "rotulo": v["rotulo"], "escopo": v["escopo"]}
                         for k, v in sorted(mod_marcadores.CATALOGO.items())]
                self.send_json({"ok": True, "marcadores": itens,
                                "essenciais": mod_marcadores.ESSENCIAIS})
                return

            # ── GET /api/documentos/modelos — modelos da loja ──
            if path == "/api/documentos/modelos":
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    import mod_documentos as _mdoc
                    itens = [{"id": m.id, "tipo": m.tipo, "versao": m.versao,
                              "nome": m.nome, "ativo": bool(m.ativo),
                              "origem_nome": m.origem_nome,
                              "criado_em": m.criado_em.isoformat() if m.criado_em else None,
                              "criado_por_id": m.criado_por_id}
                             for m in _mdoc.listar(db, loja_id)]
                    self.send_json({"ok": True, "modelos": itens,
                                    "pode_gerir": perfis.pode(ator.get("perfil"), "gerir_documentos")})
                finally:
                    db.close()
                return
```

**POST** — junto dos outros POST:

```python
            # ── POST /api/documentos/modelos/importar — converte e analisa; NÃO salva ──
            if path == "/api/documentos/modelos/importar":
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    if not perfis.pode(ator.get("perfil"), "gerir_documentos"):
                        self.send_json({"ok": False, "erro": "Sem permissão para gerir modelos de documento"}, code=403)
                        return
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    arquivos, campos = _parse_multipart_arquivos(
                        body, self.headers.get("Content-Type", ""))
                    if not arquivos:
                        self.send_json({"ok": False, "erro": "Nenhum arquivo enviado"}, code=400)
                        return
                    nome_arq, conteudo = arquivos[0][0], arquivos[0][1]
                    tipo = (campos.get("tipo") or "contrato").strip()
                    if tipo not in ("contrato", "proposta"):
                        self.send_json({"ok": False, "erro": "Tipo inválido"}, code=400)
                        return

                    import mod_documentos_import as _imp
                    import mod_marcadores as _mk
                    import mod_documentos as _mdoc
                    # Guarda o original no staging: a versão ainda não existe (o
                    # lojista pode desistir na revisão), mas o arquivo tem que
                    # sobreviver para virar origem_path na ativação (auditoria).
                    staging_path, sha = _mdoc.guardar_staging(loja_id, tipo, nome_arq, conteudo)
                    try:
                        texto = _imp.normalizar(staging_path)
                    except _imp.FormatoNaoSuportado as e:
                        os.remove(staging_path)
                        self.send_json({"ok": False, "erro": str(e)}, code=400)
                        return
                    except Exception as e:
                        os.remove(staging_path)
                        self.send_json({"ok": False, "erro": "Falha ao converter: %s" % e}, code=500)
                        return
                    corpo_md = _imp.extrair_corpo(texto)
                    if not corpo_md.strip():
                        os.remove(staging_path)
                        self.send_json({"ok": False, "erro": "O documento não produziu conteúdo — confira se tem as cláusulas."}, code=400)
                        return
                    loja_dict = _loja_dict_para_contrato(db, loja_id)
                    analise = _mk.analisar_corpo(corpo_md, loja_dict)
                    self.send_json({"ok": True, "corpo_md": corpo_md,
                                    "origem_nome": nome_arq, "tipo": tipo,
                                    "staging": os.path.basename(staging_path),
                                    "origem_sha256": sha, "analise": analise})
                finally:
                    db.close()
                return

            # ── POST /api/documentos/modelos/preview — PDF de exemplo ──
            if path == "/api/documentos/modelos/preview":
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    if not perfis.pode(ator.get("perfil"), "gerir_documentos"):
                        self.send_json({"ok": False, "erro": "Sem permissão"}, code=403)
                        return
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    dados = json.loads(body.decode("utf-8"))
                    corpo_md = dados.get("corpo_md") or ""
                    import mod_contrato as _mc
                    cliente_exemplo = {
                        "nome": "CLIENTE DE EXEMPLO", "cpf": "000.000.000-00",
                        "email": "exemplo@exemplo.com", "telefone": "(00) 00000-0000",
                        "logradouro": "Rua de Exemplo", "numero": "100",
                        "bairro": "Centro", "cidade": "Cidade", "estado": "SP",
                        "cep": "00000-000", "inst_mesmo_residencial": True,
                    }
                    loja_dict = _loja_dict_para_contrato(db, loja_id)
                    ctx = _mc.construir_contexto(
                        cliente_exemplo,
                        {"nome": usuario.get("nome", ""), "telefone": "", "email": ""},
                        "", loja_dict)
                    ctx["num_contrato"] = "PREVIEW"
                    ctx["_corpo_md_preview"] = corpo_md
                    html = _mc._montar_html_contrato(ctx)
                    from weasyprint import HTML as _WHTML
                    pdf = _WHTML(string=html, base_url=_mc.CONTRATO_TEMPLATE_DIR).write_pdf()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/pdf")
                    self.send_header("Content-Length", len(pdf))
                    self.send_header("Content-Disposition", 'inline; filename="preview.pdf"')
                    self.end_headers()
                    self.wfile.write(pdf)
                finally:
                    db.close()
                return

            # ── POST /api/documentos/modelos — cria a versão e ativa ──
            if path == "/api/documentos/modelos":
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    if not perfis.pode(ator.get("perfil"), "gerir_documentos"):
                        self.send_json({"ok": False, "erro": "Sem permissão"}, code=403)
                        return
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    dados = json.loads(body.decode("utf-8"))
                    corpo_md = dados.get("corpo_md") or ""
                    tipo = (dados.get("tipo") or "contrato").strip()
                    import mod_marcadores as _mk
                    import mod_documentos as _mdoc
                    loja_dict = _loja_dict_para_contrato(db, loja_id)
                    corpo_md = _mk.aplicar_cravados(corpo_md, loja_dict,
                                                    dados.get("cravados_aprovados") or [])
                    analise = _mk.analisar_corpo(corpo_md, loja_dict)
                    if analise["bloqueia_ativacao"]:
                        self.send_json({"ok": False,
                                        "erro": "Marcador desconhecido no documento: %s. "
                                                "Seria impresso literalmente no PDF."
                                                % ", ".join(analise["desconhecidos"])},
                                       code=400)
                        return
                    # Recompõe o caminho do staging a partir do BASENAME que o
                    # cliente devolveu — nunca aceite o caminho pronto (path traversal).
                    staging_path = None
                    if dados.get("staging"):
                        staging_path = os.path.join(
                            _mdoc.DOCS_LOJA_DIR, str(loja_id), tipo, "_staging",
                            os.path.basename(dados["staging"]))
                        if not os.path.exists(staging_path):
                            staging_path = None
                    try:
                        m = _mdoc.criar_versao(db, loja_id, tipo, corpo_md,
                                               dados.get("origem_nome") or "",
                                               usuario["id"], nome=dados.get("nome"),
                                               staging_path=staging_path,
                                               origem_sha256=dados.get("origem_sha256"))
                    except ValueError as e:
                        self.send_json({"ok": False, "erro": str(e)}, code=400)
                        return
                    _mdoc.ativar(db, m.id)
                    self.send_json({"ok": True, "id": m.id, "versao": m.versao})
                finally:
                    db.close()
                return
```

- [ ] **Step 4: `_montar_html_contrato` aceita o corpo do preview**

Em `_resolver_corpo_contrato` (Task 6), acrescentar como **primeira** condição:

```python
    if ctx.get("_corpo_md_preview") is not None:
        return ctx["_corpo_md_preview"]
```

- [ ] **Step 5: Registrar as rotas em `modulos.py`**

Em `MODULOS["comercial"]["rotas"]`, acrescentar `"/api/documentos"`.

- [ ] **Step 6: Restart e testar à mão**

```bash
python3 main.py
curl -s http://localhost:8765/api/documentos/marcadores
```
Expected: 401 sem sessão. Logado no navegador, devolve o catálogo.

- [ ] **Step 7: Suíte e commit**

Run: `python3 -m pytest -q` → verde.

```bash
git add main.py modulos.py mod_contrato.py tests/test_documentos_api.py
git commit -m "feat(documentos): endpoints /api/documentos/* (catálogo, modelos, importar, preview, ativar)

importar converte e analisa sem salvar; ativar recusa marcador desconhecido
(sairia impresso literal no PDF). Todos escopados por loja e sob a capacidade
gerir_documentos."
```

---

### Task 9: Painel e wizard

Sem teste JS no projeto → verificação no navegador + `node --check`.

**Files:**
- Modify: `static/index.html:1970` (declarar o modal, junto dos outros)
- Modify: `static/index.html:2915-2929` (`cfgDocumentosRender`)

**Padrão de modal do projeto** (não invente outro): o modal é declarado no HTML e alternado por função própria. Referência: `modal-novo-ambiente` (`static/index.html:1970-1973`) + `abrirModalNovoAmbiente`/`fecharModalNovoAmbiente` (`:3757-3765`). **Não existe `abrirModalGenerico`.**

- [ ] **Step 1: Declarar o modal no HTML**

Ao lado de `<div id="modal-novo-ambiente" ...>` (linha 1970), acrescentar:

```html
<div id="modal-doc-modelo" class="modal-overlay" style="display:none">
  <div class="modal-box" style="animation:mIn .18s ease;max-width:720px">
    <div class="modal-hdr">
      <div class="modal-title" id="doc-modal-title">Modelo de documento</div>
      <span class="modal-close" onclick="fecharModalDocModelo()">&#x2715;</span>
    </div>
    <div id="doc-modal-body" style="padding:16px"></div>
  </div>
</div>
```

Estrutura e classes copiadas de `modal-novo-ambiente` (`static/index.html:1970-1975`) — `modal-overlay` / `modal-box` / `modal-hdr` / `modal-title` / `modal-close`, com o `&#x2715;` como X.

- [ ] **Step 2: Substituir `cfgDocumentosRender`**

Trocar a função inteira (linhas 2915-2929) por:

```javascript
let _docModelos = [];
let _docPodeGerir = false;
let _docImport = null;   // {corpo_md, origem_nome, tipo, analise}

async function cfgDocumentosRender(){
  const box = document.getElementById('cfg-panel-documentos'); if(!box) return;
  box.innerHTML = '<em style="color:var(--muted);font-size:12px">Carregando…</em>';
  const d = await (await fetch('/api/documentos/modelos',{credentials:'same-origin'})).json().catch(()=>({}));
  if(!d.ok){ box.innerHTML = '<em style="color:var(--err);font-size:12px">'+esc(d.erro||'Sem acesso.')+'</em>'; return; }
  _docModelos = d.modelos || []; _docPodeGerir = !!d.pode_gerir;
  const TIPOS = [
    ['contrato','Contrato','ti-file-text','Cláusulas do contrato de compra e venda'],
    ['proposta','Proposta comercial','ti-file-invoice','Condições da proposta']
  ];
  box.innerHTML =
     '<div style="font-size:12px;color:var(--muted);margin-bottom:12px;max-width:640px">'
    +'Modelos dos documentos da loja. Suba o documento em Word (.docx), LibreOffice (.odt) ou texto — '
    +'o sistema extrai as cláusulas e aplica o modelo Orizon.</div>'
    +'<div style="display:grid;grid-template-columns:repeat(auto-fill,260px);gap:12px">'
    + TIPOS.map(t => {
        const vs = _docModelos.filter(m => m.tipo===t[0]);
        const at = vs.find(m => m.ativo);
        return '<div style="background:var(--surface-2);box-shadow:var(--shadow);border-radius:12px;padding:14px 16px;'
          +(_docPodeGerir?'cursor:pointer':'')+'"'
          +(_docPodeGerir?' onclick="docAbrirTipo(\''+t[0]+'\')"':'')+'>'
          +'<i class="ti '+t[2]+'" style="font-size:20px;color:var(--muted)"></i>'
          +'<div style="font-weight:600;font-size:13px;color:var(--text);margin-top:6px">'+t[1]+'</div>'
          +'<div style="font-size:11px;color:var(--muted);margin-top:2px">'+t[3]+'</div>'
          +'<div style="font-size:11px;margin-top:8px;color:'+(at?'var(--ok)':'var(--muted)')+'">'
          + (at ? ('Versão '+at.versao+' ativa'+(at.nome?' — '+esc(at.nome):'')) : 'Modelo padrão do sistema')
          +'</div>'
          + (vs.length ? '<div style="font-size:10px;color:var(--muted);margin-top:2px">'+vs.length+' versão(ões)</div>' : '')
          +'</div>';
      }).join('')
    +'</div>'
    + (_docPodeGerir ? '' : '<div style="font-size:11px;color:var(--muted);margin-top:12px">'
        +'Você não tem a capacidade <b>Gerir modelos de documento</b> — visualização apenas.</div>');
}

function docAbrirTipo(tipo){
  const vs = _docModelos.filter(m => m.tipo===tipo);
  const rotulo = tipo==='contrato' ? 'Contrato' : 'Proposta comercial';
  const hist = vs.length
    ? '<table style="width:100%;font-size:12px;margin-top:8px"><tr style="color:var(--muted);text-align:left">'
      +'<th>Versão</th><th>Nome</th><th>Origem</th><th>Quando</th><th></th></tr>'
      + vs.map(m => '<tr><td>v'+m.versao+(m.ativo?' <b style="color:var(--ok)">• ativa</b>':'')+'</td>'
          +'<td>'+esc(m.nome||'—')+'</td><td>'+esc(m.origem_nome||'—')+'</td>'
          +'<td>'+(m.criado_em? esc(m.criado_em.slice(0,10)) : '—')+'</td><td></td></tr>').join('')
      +'</table>'
    : '<div style="font-size:12px;color:var(--muted);margin-top:8px">'
      +'Nenhum modelo próprio. O sistema usa o modelo padrão.</div>';
  document.getElementById('doc-modal-title').textContent = 'Modelo — ' + rotulo;
  document.getElementById('doc-modal-body').innerHTML = hist
    +'<div style="margin-top:16px;display:flex;gap:8px">'
    +'<input type="file" id="doc-file" accept=".docx,.odt,.doc,.rtf,.md,.txt" style="font-size:12px">'
    +'<button class="btn btn-primary btn-sm" onclick="docImportar(\''+tipo+'\')">Importar modelo</button>'
    +'</div>'
    +'<div style="font-size:11px;color:var(--muted);margin-top:6px">'
    +'Word, LibreOffice ou texto. PDF não é aceito: a extração perde a numeração das cláusulas.</div>'
    +'<div id="doc-wizard" style="margin-top:16px"></div>';
  document.getElementById('modal-doc-modelo').style.display = 'flex';
}

function fecharModalDocModelo(){
  document.getElementById('modal-doc-modelo').style.display = 'none';
  _docImport = null;
}

async function docImportar(tipo){
  const inp = document.getElementById('doc-file');
  if(!inp || !inp.files.length){ showToast('Escolha um arquivo.', true); return; }
  const fd = new FormData(); fd.append('arquivo', inp.files[0]); fd.append('tipo', tipo);
  const alvo = document.getElementById('doc-wizard');
  alvo.innerHTML = '<em style="color:var(--muted);font-size:12px">Convertendo…</em>';
  const d = await (await fetch('/api/documentos/modelos/importar',
    {method:'POST', body:fd, credentials:'same-origin'})).json().catch(()=>({}));
  if(!d.ok){ alvo.innerHTML = '<div style="color:var(--err);font-size:12px">'+esc(d.erro||'Falha.')+'</div>'; return; }
  _docImport = d;
  docRenderRevisao();
}

function docRenderRevisao(){
  const a = _docImport.analise, alvo = document.getElementById('doc-wizard');
  const bloco = (titulo, cor, itens) => itens.length
    ? '<div style="margin-top:12px"><div style="font-size:12px;font-weight:600;color:'+cor+'">'+titulo+'</div>'
      +'<div style="font-size:11px;color:var(--muted);margin-top:4px">'+itens.join('<br>')+'</div></div>' : '';
  alvo.innerHTML =
     '<div style="font-size:12px;color:var(--text)">Convertido: <b>'+esc(_docImport.origem_nome)+'</b> — '
    + _docImport.corpo_md.split('\n').length + ' linhas, '
    + a.conhecidos_usados.length + ' marcador(es) reconhecido(s).</div>'
    + bloco('Marcadores desconhecidos — impedem a ativação', 'var(--err)',
        a.desconhecidos.map(x => '<code>['+esc(x)+']</code> não existe no catálogo — sairia impresso literal no PDF.'))
    + bloco('Marcadores essenciais ausentes', 'var(--warn)',
        a.ausentes.map(x => '<code>['+esc(x)+']</code> não está no documento.'))
    + (a.cravados.length
        ? '<div style="margin-top:12px"><div style="font-size:12px;font-weight:600;color:var(--text)">'
          +'Dados da loja cravados no texto</div>'
          +'<div style="font-size:11px;color:var(--muted);margin:4px 0 6px">'
          +'Marque para trocar pelo marcador — assim o modelo serve a qualquer loja.</div>'
          + a.cravados.map((c,i) =>
              '<label style="display:block;font-size:11px;margin:3px 0">'
              +'<input type="checkbox" class="doc-cravado" value="'+esc(c.marcador)+'"'
              + (c.so_digitos ? ' disabled' : ' checked') + '> '
              +'"<b>'+esc(c.literal)+'</b>" → <code>['+esc(c.marcador)+']</code> '
              +'<span style="color:var(--muted)">('+c.ocorrencias+'×'
              + (c.so_digitos ? ' — casou só sem pontuação; corrija à mão' : '') + ')</span></label>').join('')
          +'</div>' : '')
    +'<div style="margin-top:16px;display:flex;gap:8px;align-items:center">'
    +'<button class="btn btn-sm" onclick="docPreview()">Ver PDF de exemplo</button>'
    +'<button class="btn btn-primary btn-sm"'+(a.bloqueia_ativacao?' disabled':'')
    +' onclick="docAtivar()">Ativar como novo modelo</button>'
    + (a.bloqueia_ativacao ? '<span style="font-size:11px;color:var(--err)">Resolva os marcadores desconhecidos.</span>' : '')
    +'</div>';
}

function _docCravadosAprovados(){
  return Array.from(document.querySelectorAll('.doc-cravado:checked')).map(c => c.value);
}

async function docPreview(){
  const r = await fetch('/api/documentos/modelos/preview', {
    method:'POST', credentials:'same-origin',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({corpo_md:_docImport.corpo_md, tipo:_docImport.tipo})
  });
  if(!r.ok){ showToast('Falha ao gerar o preview.', true); return; }
  window.open(URL.createObjectURL(await r.blob()), '_blank');
}

async function docAtivar(){
  const d = await (await fetch('/api/documentos/modelos', {
    method:'POST', credentials:'same-origin',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({corpo_md:_docImport.corpo_md, tipo:_docImport.tipo,
                          origem_nome:_docImport.origem_nome,
                          staging:_docImport.staging,
                          origem_sha256:_docImport.origem_sha256,
                          cravados_aprovados:_docCravadosAprovados()})
  })).json().catch(()=>({}));
  if(!d.ok){ showToast('Erro: '+(d.erro||'falha'), true); return; }
  showToast('Modelo v'+d.versao+' ativado.');
  fecharModalDocModelo();
  cfgDocumentosRender();
}
```

`showToast(msg, isErr)` existe em `static/index.html:3795`. `esc()` é usado por todo o arquivo — confirme a assinatura com `grep -n "function esc" static/index.html` antes de usar.

- [ ] **Step 3: Checar a sintaxe**

```bash
python3 - <<'EOF'
import re
h = open('static/index.html', encoding='utf-8').read()
partes = re.findall(r'<script[^>]*>(.*?)</script>', h, re.DOTALL)
open('/tmp/_check.js','w',encoding='utf-8').write("\n".join(partes))
print("ok, %d bloco(s)" % len(partes))
EOF
node --check /tmp/_check.js
```
Expected: sem erro.

- [ ] **Step 4: Verificação no navegador**

Ctrl+F5. Config › Documentos. Confirmar, como master:
1. Os cards aparecem com "Modelo padrão do sistema".
2. Clicar em "Contrato" abre o modal com o histórico vazio.
3. Subir um `.docx` real de contrato → aparece a revisão com os marcadores e os cravados.
4. "Ver PDF de exemplo" abre o PDF com o cliente de exemplo.
5. "Ativar" → toast, card mostra "Versão 1 ativa".
6. Subir um `.pdf` → erro explicando que precisa ser Word.
7. Logar como **gerencial** → cards não clicáveis + aviso de capacidade.

**Este é o passo que exercita o LibreOffice de verdade** (nenhum teste o faz). Se o `.docx` vier com as cláusulas sem número, o `normalizar` não passou pelo LibreOffice — reveja o Task 2.

- [ ] **Step 5: Commit**

```bash
git add static/index.html
git commit -m "feat(documentos): painel de modelos da loja + wizard de importação

Card Contrato/Proposta deixa de ser tela-morta: abre histórico de versões,
importa .docx/.odt/.doc/.rtf/.md/.txt, mostra marcadores ausentes/desconhecidos
e dados da loja cravados, gera PDF de exemplo e ativa a versão.

Sem a capacidade gerir_documentos: só leitura."
```

---

### Task 10: Corpo da proposta

Hoje a proposta é capa-só: `montar_html_proposta` faz `shell.replace("<!--CORPO-->", "")` (`mod_contrato.py:841`). Sem modelo, tem que continuar **byte-a-byte igual**.

**Files:**
- Modify: `mod_contrato.py:834-842`
- Modify: `main.py:1817-1870`
- Create: `tests/test_documentos_proposta.py`

- [ ] **Step 1: Escrever os testes (falhando)**

Criar `tests/test_documentos_proposta.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
import mod_contrato
import mod_documentos


@pytest.fixture
def db(tmp_path, monkeypatch):
    import database
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "t.db"))
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    eng = create_engine("sqlite:///" + str(tmp_path / "t.db"))
    database.Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


# montar_html_proposta chama _html_capa(ctx) — use construir_contexto, como
# tests/test_contrato.py:303-309. ctx montado na mão quebra na capa.
CLIENTE = {"nome": "CLIENTE TESTE", "cpf": "000.000.000-00",
           "email": "t@t.com", "telefone": "(12) 90000-0000",
           "logradouro": "Rua X", "numero": "1", "bairro": "Centro",
           "cidade": "São José dos Campos", "estado": "SP", "cep": "12200-000",
           "inst_mesmo_residencial": True}
USUARIO = {"nome": "Consultor", "telefone": "", "email": ""}
LOJA = {"id": 1, "nome": "LOJA TESTE", "cnpj": "00.000.000/0001-00"}


def _ctx(**extra):
    ctx = mod_contrato.construir_contexto(CLIENTE, USUARIO, "", LOJA)
    ctx["num_contrato"] = "PV000000001"
    ctx.update(extra)
    return ctx


def test_proposta_sem_db_e_capa_so_como_hoje():
    """Regressão zero: chamador que não passa _db não muda de comportamento."""
    html = mod_contrato.montar_html_proposta(_ctx())
    assert "<!--CORPO-->" not in html
    assert "CLÁUSULA" not in html


def test_proposta_sem_modelo_e_capa_so(db):
    html = mod_contrato.montar_html_proposta(_ctx(_db=db))
    assert "CLÁUSULA" not in html


def test_proposta_com_modelo_ativo_ganha_o_corpo(db):
    m = mod_documentos.criar_versao(db, 1, "proposta",
                                    "# CLÁUSULA ÚNICA\n1.1. Proposta válida por 10 dias.\n",
                                    "p.docx", 1)
    mod_documentos.ativar(db, m.id)
    html = mod_contrato.montar_html_proposta(_ctx(_db=db))
    assert "CLÁUSULA ÚNICA" in html
    assert "Proposta válida por 10 dias." in html


def test_modelo_de_contrato_nao_vaza_para_a_proposta(db):
    m = mod_documentos.criar_versao(db, 1, "contrato",
                                    "# CLÁUSULA DO CONTRATO\n1.1. Não é da proposta.\n",
                                    "c.docx", 1)
    mod_documentos.ativar(db, m.id)
    html = mod_contrato.montar_html_proposta(_ctx(_db=db))
    assert "CLÁUSULA DO CONTRATO" not in html
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_documentos_proposta.py -q`
Expected: FAIL em `test_proposta_com_modelo_ativo_ganha_o_corpo` — o corpo é sempre `""`.

- [ ] **Step 3: Implementar**

Em `mod_contrato.py`, trocar `montar_html_proposta` (linhas 834-842) por:

```python
def montar_html_proposta(ctx):
    """HTML da proposta comercial = capa do contrato + (opcional) corpo do modelo da loja.

    O número no canto superior direito usa ctx['num_contrato'] (deve conter o num_proposta 'PV...').
    O corpo vem do modelo 'proposta' da loja quando ctx['_db'] é fornecido; sem
    modelo (ou sem _db) a proposta é capa-só, como sempre foi.
    """
    from html import escape
    mapping = {k: escape(str(v)) for k, v in _montar_mapping(ctx, ctx.get("_pag", {})).items()}
    shell = open(os.path.join(CONTRATO_TEMPLATE_DIR, "contrato.html"), encoding="utf-8").read()
    capa = _html_capa(ctx).replace('<div class="quebra-capa"></div>', "")   # capa sem quebra
    corpo_md = _resolver_corpo_proposta(ctx)
    corpo = _html_corpo(corpo_md) if corpo_md.strip() else ""
    html = shell.replace("<!--CAPA-->", capa).replace("<!--CORPO-->", corpo)
    return _substituir_marcadores_html(html, mapping)


def _resolver_corpo_proposta(ctx):
    """Markdown do corpo da proposta. Sem _db/sem modelo → "" (capa-só, como hoje)."""
    db = ctx.get("_db")
    loja_id = (ctx.get("loja") or {}).get("id")
    if db is None or not loja_id:
        return ""
    import mod_documentos
    return mod_documentos.resolver_modelo(db, loja_id, "proposta")
```

Repare que a capa mantinha o `<div class="quebra-capa">` removido — com corpo, a quebra de página **passa a fazer falta**. Se o preview mostrar o corpo colado na capa, troque a linha da capa por:

```python
    capa = _html_capa(ctx) if corpo_md.strip() else \
           _html_capa(ctx).replace('<div class="quebra-capa"></div>', "")
```

(precisa mover `corpo_md = _resolver_corpo_proposta(ctx)` para antes da linha da capa).

- [ ] **Step 4: Rodar**

Run: `python3 -m pytest tests/test_documentos_proposta.py tests/test_contrato.py -q`
Expected: PASS.

- [ ] **Step 5: Ligar no handler da proposta**

Em `main.py`, no handler `GET /api/orcamentos/<id>/proposta/pdf`, após `ctx["num_contrato"] = orc.num_proposta` (linha ~1855):

```python
                    ctx["_db"] = db   # corpo da proposta vem do modelo da loja (se houver)
```

`_loja_dict_para_contrato` já devolve `"id"` (`main.py:8760`) — nada a fazer.

Aproveite e remova o `import mod_proposta as _mprop` da linha 1821 — é importado e nunca usado no handler.

- [ ] **Step 6: Restart e verificação manual**

```bash
python3 main.py
```
Gerar a proposta de um orçamento. Sem modelo de proposta: PDF de uma página, igual ao de antes. Depois importe um modelo de proposta pelo painel e gere de novo: o corpo aparece na sequência.

- [ ] **Step 7: Suíte e commit**

Run: `python3 -m pytest -q` → verde.

```bash
git add mod_contrato.py main.py tests/test_documentos_proposta.py
git commit -m "feat(documentos): proposta ganha corpo vindo do modelo da loja

A proposta era capa-só (<!--CORPO--> recebia \"\"), então não havia onde um
documento importado aterrissar. Agora o corpo vem do modelo 'proposta' da loja.

Sem modelo (ou sem _db no ctx): capa-só, PDF igual ao de hoje.

Remove o import morto de mod_proposta no handler."
```

---

### Task 11: Documentação

**Files:**
- Modify: `CLAUDE.md:51-53`
- Modify: `DEV_LOG.md`

- [ ] **Step 1: Corrigir o CLAUDE.md**

`CLAUDE.md:53` afirma "a **proposta** ainda usa docx/LibreOffice" — **falso**, e foi essa frase que induziu o spec ao erro corrigido em §8.1. Trocar o item **Contrato** de "Áreas sensíveis" por:

```markdown
- **Contrato/Proposta:** HTML (capa) + Markdown (cláusulas) → **PDF via WeasyPrint** (assets em
  `contrato_template/`). `weasyprint` 69 no user-site do `python3.14`. O caminho `.docx`/LibreOffice
  foi **aposentado nos dois** — a proposta usa `mod_contrato.gerar_pdf_proposta` (capa + corpo do
  modelo da loja). `mod_proposta.py`/`modelo_proposta.docx` são **código morto** (nada em produção os
  lê); não os use de referência. O **LibreOffice segue necessário** para IMPORTAR modelo
  (`mod_documentos_import.normalizar`): é o único que achata a numeração automática do Word.
- **Modelos de documento por loja:** `documento_modelos` (versão imutável, uma ativa por loja+tipo).
  `Contrato.modelo_versao_id` congela a versão que gerou o contrato → regerar um assinado reproduz as
  cláusulas originais. `NULL` = legado → `contrato_template/contrato.md` global. Catálogo de
  marcadores em `mod_marcadores.CATALOGO`, travado contra `mod_contrato._montar_mapping` por teste.
  Spec: `docs/superpowers/specs/2026-07-15-modelos-documentos-loja-design.md`.
```

- [ ] **Step 2: DEV_LOG**

Acrescentar uma `## Sessão N` (N = última + 1) narrando: o que entrou, a premissa falsa da proposta e como foi descoberta, e a dívida do código docx morto (spec §11).

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md DEV_LOG.md
git commit -m "docs: CLAUDE.md + DEV_LOG — modelos de documento por loja

Corrige a afirmação errada de que a proposta ainda usa docx/LibreOffice (ela
usa WeasyPrint desde a migração da capa) — foi essa frase que induziu o spec
ao erro corrigido em §8.1."
```

- [ ] **Step 4: Fechar a frente**

Conforme CLAUDE.md: suíte verde → `git push origin main` → re-ingerir o grafo MCP (`ingerir` com `fonte: "all"`, ou `POST http://localhost:8767/ingest/all`).

Antes do push, vale chamar a **Vera** (`.claude/agents/vera.md`): a frente toca área sensível (contrato, escopo/tenancy, capacidade nova).

---

## Fora de escopo

**"+documentos" — tipos novos.** Pergunta em aberto: *o que dispara um documento custom?* Um "Termo de Medição" no painel não serve se nada no ciclo o emite. `tipo` já aceita a string; a validação (`mod_documentos.TIPOS`) é o único gate a abrir.

**Aposentar o caminho docx morto.** `mod_proposta.py`, `modelo_proposta.docx`, `_substituir_marcadores`, `_subst_paragrafo`, `_converter_pdf`, `tests/test_proposta.py`, `tests/test_proposta_template.py`. **Cuidado:** `_libreoffice_cmd()` continua necessário (base da importação) e `contrato_editar.py:48-50` também o usa.
