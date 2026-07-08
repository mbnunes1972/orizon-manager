# Modularização — Fase 1 (Fundação) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recomendado) ou
> superpowers:executing-plans para executar tarefa-a-tarefa. Passos usam checkbox (`- [ ]`).

**Goal:** Tornar a modularização de `ARQUITETURA-MODULOS.md` **real e imposta por teste** — sem mover código —
criando um **manifesto de módulos** executável, um **teste que impõe as fronteiras** (Núcleo não importa domínio;
domínios só dependem do que declaram), a **titularidade das etapas do Ciclo** explícita, e o mecanismo de
**ligar/desligar domínio por loja** (venda por topologia). É a fundação que torna o **desmembramento físico
futuro (Fase 2+) seguro**.

**Architecture:** Um módulo puro `modulos.py` declara o manifesto (camada, arquivos, tabelas, rotas, dependências,
desligável). Um teste `tests/test_arquitetura_modulos.py` lê o manifesto + faz parse de `import` (via `ast`) e
**falha** se alguém violar a fronteira. `mod_ciclo` ganha o mapa de **faixas de titularidade**. `Loja` ganha
`modulos_ativos` (JSON) + helper em `mod_tenancy` + endpoints + um guard no dispatch (default **tudo ligado** →
zero mudança de comportamento). **Nenhum arquivo muda de lugar; nenhum schema é dividido.**

**Tech Stack:** Python 3 puro (`ast`, `http.server`), SQLAlchemy/SQLite, pytest. Base: `docs/ARQUITETURA-MODULOS.md`.

**Ler antes:** `docs/ARQUITETURA-MODULOS.md` (a taxonomia — fonte da verdade); `mod_ciclo.py` (ETAPAS_PRINCIPAIS,
ETAPAS_APROVACAO_FINANCEIRA, ETAPAS_OPERACIONAIS); `database.py` (24 modelos); `mod_tenancy.py` (escopo).
**Baseline 650 passed.** Teste: `python3 -m pytest -q` (fallback
`C:\Users\mbn19\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest -q`). `git add` só os arquivos da
mudança. Branch: `feat/modularizacao-fase1`.

---

## Escopo desta fase (e o que fica para depois)

- **Fase 1 (este plano):** fundação — manifesto + fronteira imposta + titularidade + topologia on/off. Não move
  código, não divide schema.
- **Fase 2+ (roadmap no fim deste doc, planos próprios):** extração física de módulos em pacotes, começando por um
  **piloto (Fiscal)**; e o design **interno** de cada domínio NOVO (Estoque, Financeiro completo, Pós-venda) —
  cada um seu ciclo brainstorm→spec→plano, como o doc de arquitetura manda.

**Por que a fundação primeiro:** não se desmembra um monólito com segurança sem (a) declarar o que é de cada
módulo e (b) provar por teste que as dependências obedecem à regra. O manifesto vira o **mapa de corte** e o teste
vira a **rede de segurança** da extração futura.

---

## File Structure

- **Create `modulos.py`** — manifesto declarativo (dados) + helpers puros (`modulo_de_arquivo`,
  `modulo_de_tabela`, `modulo_do_path`, `MODULOS`, `NUCLEO`, `DOMINIOS`, `desligavel`). Sem dependências do app.
- **Create `tests/test_arquitetura_modulos.py`** — impõe: cobertura de arquivos, cobertura de tabelas, pureza do
  Núcleo, dependências declaradas (ratchet).
- **Create `tests/test_modulos.py`** — testes unitários dos helpers de `modulos.py`.
- **Modify `mod_ciclo.py`** — `FAIXA_POR_ETAPA`, `faixa_da_etapa()`, `etapa_e_gate()` (reusa
  ETAPAS_APROVACAO_FINANCEIRA).
- **Create `tests/test_ciclo_faixas.py`** — testes das faixas/gates.
- **Modify `database.py`** — `Loja.modulos_ativos` (coluna) + migração em `_migrar_colunas`.
- **Modify `mod_tenancy.py`** — `modulos_ativos_da_loja(loja)`, `modulo_ativo(loja, modulo)`.
- **Create `tests/test_topologia_modulos.py`** — testes do liga/desliga (unit) + e2e do guard.
- **Modify `main.py`** — endpoints `GET/PUT /api/admin/lojas/<id>/modulos` + guard `_bloqueio_modulo(path, loja)`
  no início do dispatch de API (default tudo-ligado).
- **Modify `docs/ARQUITETURA-MODULOS.md`** — nota de que o manifesto agora é executável/imposto + roadmap de
  extração. **Modify `DEV_LOG.md`.**

---

## Task 1: Manifesto de módulos (`modulos.py`) + helpers

**Files:** Create `modulos.py`, `tests/test_modulos.py`.

- [ ] **Step 1: Descoberta — confirmar a lotação dos arquivos ambíguos.** Rode e anote a que módulo pertencem
  (o teste da Task 2 vai exigir que TODO `.py` esteja no manifesto ou na allowlist de shell):

```bash
python3 - <<'PY'
import pathlib
raiz = pathlib.Path('.')
print("PY na raiz:", sorted(p.name for p in raiz.glob('*.py')))
for amb in ('mod_arvore.py','_ler_aymore.py','contrato_editar.py','reset_ep07.py','promob_grupos.py'):
    t = pathlib.Path(amb).read_text(encoding='utf-8')[:400]
    print("\n===", amb, "===\n", t)
PY
```
Regra de lotação (do doc §"Convenções"): decidir por *(a) quem é dono do dado* e *(b) qual etapa dispara*.
Defaults deste plano (ajuste se a descoberta contradizer): `mod_arvore`→comercial, `_ler_aymore`→comercial,
`contrato_editar`→comercial, `reset_ep07`→shell (tool), `promob_grupos`→nucleo/integracoes.

- [ ] **Step 2: Teste primeiro** — `tests/test_modulos.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import modulos as m


def test_camadas_e_conjuntos():
    assert m.NUCLEO and m.DOMINIOS
    assert m.NUCLEO.isdisjoint(m.DOMINIOS)
    for nome in m.NUCLEO | m.DOMINIOS:
        assert nome in m.MODULOS
        assert m.MODULOS[nome]["camada"] in ("nucleo", "dominio")


def test_nucleo_nao_e_desligavel():
    for nome in m.NUCLEO:
        assert m.desligavel(nome) is False
    # ao menos um domínio é desligável
    assert any(m.desligavel(d) for d in m.DOMINIOS)


def test_modulo_de_arquivo():
    assert m.modulo_de_arquivo("mod_fiscal.py") == "fiscal"
    assert m.modulo_de_arquivo("perfis.py") == "auth"
    assert m.modulo_de_arquivo("mod_tenancy.py") == "tenancy"
    assert m.modulo_de_arquivo("main.py") is None          # shell não é módulo
    assert m.modulo_de_arquivo("inexistente.py") is None


def test_modulo_de_tabela():
    assert m.modulo_de_tabela("clientes") == "cadastro"
    assert m.modulo_de_tabela("documento_fiscal") == "fiscal"
    assert m.modulo_de_tabela("lojas") == "tenancy"
    assert m.modulo_de_tabela("ciclo_etapas") == "ciclo"


def test_modulo_do_path():
    assert m.modulo_do_path("/api/projetos/X/ciclo/15/emitir-nfe") == "fiscal"
    assert m.modulo_do_path("/api/admin/lojas/1/perfil-fiscal") == "fiscal"
    assert m.modulo_do_path("/api/clientes") == "cadastro"
    assert m.modulo_do_path("/api/orcamentos/9/margens") == "comercial"
    assert m.modulo_do_path("/api/login") is None          # núcleo/sem módulo desligável
```

- [ ] **Step 3: Rodar → falha** (`ModuleNotFoundError: modulos`).

- [ ] **Step 4: Implementar `modulos.py`** — manifesto completo + helpers:

```python
"""modulos.py — manifesto declarativo dos módulos (ARQUITETURA-MODULOS.md tornado executável).
Puro (sem dependências do app). Fonte da verdade de: qual arquivo/tabela/rota pertence a qual módulo,
a camada (nucleo|dominio), as dependências permitidas e se o módulo é desligável por loja (topologia)."""

# camada: "nucleo" (transversal, sempre ligado) | "dominio" (ligável/desligável por cliente)
# depende_de: módulos que ESTE pode importar além do próprio núcleo (ratchet do teste de fronteira)
# arquivos/tabelas/rotas: prefixos que identificam o dono. rotas = prefixos de path (match por startswith).
MODULOS = {
    # ── NÚCLEO / PLATAFORMA ────────────────────────────────────────────────
    "auth":        {"camada": "nucleo", "depende_de": [],
                    "arquivos": ["auth.py", "auth_routes.py", "perfis.py"],
                    "tabelas": ["usuarios", "sessoes"], "rotas": []},
    "tenancy":     {"camada": "nucleo", "depende_de": ["auth"],
                    "arquivos": ["mod_tenancy.py"],
                    "tabelas": ["redes", "lojas", "usuario_lojas", "parceiro_lojas"], "rotas": []},
    "auditoria":   {"camada": "nucleo", "depende_de": [],
                    "arquivos": [],
                    "tabelas": ["log_autorizacoes", "log_acoes_gerenciais"], "rotas": []},
    "ciclo":       {"camada": "nucleo", "depende_de": [],
                    "arquivos": ["mod_ciclo.py"],
                    "tabelas": ["ciclo_etapas", "ciclo_documentos", "ciclo_revisoes"], "rotas": []},
    "integracoes": {"camada": "nucleo", "depende_de": [],
                    "arquivos": ["emissor_fiscal.py", "focus_client.py", "focus_config.py",
                                 "mod_omie.py", "promob_grupos.py"],
                    "tabelas": [], "rotas": []},
    "plataforma":  {"camada": "nucleo", "depende_de": [],
                    "arquivos": ["database.py", "storage.py"],
                    "tabelas": [], "rotas": []},
    # ── DOMÍNIOS ───────────────────────────────────────────────────────────
    "cadastro":    {"camada": "dominio", "depende_de": [],
                    "arquivos": ["validacao_doc.py"],
                    "tabelas": ["clientes", "parceiros"],
                    "rotas": ["/api/clientes", "/api/parceiros"]},
    "comercial":   {"camada": "dominio", "depende_de": ["cadastro"],
                    "arquivos": ["mod_orcamento_params.py", "mod_margens.py", "mod_negociacao.py",
                                 "mod_proposta.py", "mod_contrato.py", "mod_arvore.py",
                                 "contrato_editar.py", "_ler_aymore.py", "mod_fin"],
                    "tabelas": ["projetos_meta", "briefings", "pool_ambientes", "orcamentos",
                                "orcamento_ambientes", "contratos", "contratos_assinaturas"],
                    "rotas": ["/api/orcamentos", "/api/contratos"]},
    "producao":    {"camada": "dominio", "depende_de": ["cadastro", "comercial"],
                    "arquivos": ["mod_medicao.py", "mod_qualidade_xml.py"],
                    "tabelas": ["medicoes"],
                    "rotas": ["/api/medicoes"]},
    "fiscal":      {"camada": "dominio", "depende_de": ["cadastro", "comercial"],
                    "arquivos": ["mod_fiscal.py", "mapa_fiscal.py", "emissor_focus.py",
                                 "fiscal_cripto.py", "nfe_emissao.py", "mod_nfe.py"],
                    "tabelas": ["emitente", "perfil_emissao", "documento_fiscal"],
                    "rotas": ["/api/projetos/", "/api/admin/lojas/", "/api/admin/redes/"]},
    "financeiro":  {"camada": "dominio", "depende_de": ["comercial"],
                    "arquivos": ["mod_provisoes.py"],
                    "tabelas": ["provisao_registro"],
                    "rotas": ["/api/provisoes"]},
    # domínios NOVOS — fronteira só (stub, sem código/tabela hoje)
    "estoque":     {"camada": "dominio", "depende_de": ["cadastro", "producao"],
                    "arquivos": [], "tabelas": [], "rotas": []},
    "posvenda":    {"camada": "dominio", "depende_de": ["cadastro", "fiscal", "estoque"],
                    "arquivos": [], "tabelas": [], "rotas": []},
    "expedicao":   {"camada": "dominio", "depende_de": ["producao", "estoque", "fiscal"],
                    "arquivos": [], "tabelas": [], "rotas": []},
}

# Arquivos que NÃO são módulo (shell/compositor e utilitários). O teste de cobertura os ignora.
SHELL = {"main.py", "seed.py", "reset_ep07.py"}

# mod_nfe é COMPARTILHADO (parser=produção, pricing=fiscal): lotado em 'fiscal' no manifesto, mas
# 'producao' também pode importá-lo. Declarado aqui para o teste de fronteira aceitar ambos.
COMPARTILHADOS = {"mod_nfe.py": ["fiscal", "producao"]}

NUCLEO = frozenset(n for n, v in MODULOS.items() if v["camada"] == "nucleo")
DOMINIOS = frozenset(n for n, v in MODULOS.items() if v["camada"] == "dominio")


def desligavel(modulo):
    """True se o módulo pode ser desligado por loja (só domínios)."""
    return MODULOS.get(modulo, {}).get("camada") == "dominio"


def modulo_de_arquivo(arquivo):
    """Nome do módulo dono do arquivo (.py ou pacote), ou None se for shell/desconhecido."""
    base = arquivo[:-3] if arquivo.endswith(".py") else arquivo
    for nome, v in MODULOS.items():
        for a in v["arquivos"]:
            if a == arquivo or (a == base):
                return nome
    return None


def modulo_de_tabela(tabela):
    for nome, v in MODULOS.items():
        if tabela in v["tabelas"]:
            return nome
    return None


def modulo_do_path(path):
    """Módulo DESLIGÁVEL dono da rota (por prefixo), ou None. Só retorna domínios — rotas de núcleo
    (login, admin de tenancy) nunca são desligáveis. Prefixos mais específicos vencem (ordem por tamanho)."""
    candidatos = []
    for nome, v in MODULOS.items():
        if v["camada"] != "dominio":
            continue
        for pref in v["rotas"]:
            if path.startswith(pref):
                candidatos.append((len(pref), nome))
    if not candidatos:
        return None
    candidatos.sort(reverse=True)
    return candidatos[0][1]
```

> **Nota sobre `rotas` do fiscal:** os prefixos `/api/projetos/`, `/api/admin/lojas/`, `/api/admin/redes/` são
> **largos** e capturam também rotas não-fiscais desses namespaces. Isso é aceitável na Fase 1 porque o guard
> (Task 5) só **bloqueia** quando o módulo está **explicitamente desligado** (default tudo-ligado → nada bloqueia).
> A precisão fina de rota→módulo é refinada quando cada módulo for extraído (Fase 2+). O teste `test_modulo_do_path`
> cobre os casos que importam agora (fiscal/cadastro/comercial).

- [ ] **Step 5: Rodar** `python3 -m pytest tests/test_modulos.py -q` → verde. **Commit:**
```bash
git add modulos.py tests/test_modulos.py
git commit -m "feat(arq): manifesto declarativo de modulos (modulos.py) + helpers"
```

---

## Task 2: Teste que IMPÕE a fronteira (`tests/test_arquitetura_modulos.py`)

**Files:** Create `tests/test_arquitetura_modulos.py`.

- [ ] **Step 1: Escrever o teste** — cobertura + pureza do núcleo + dependências declaradas:

```python
import sys, os, ast, pathlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import modulos as m

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PY_RAIZ = {p.name for p in RAIZ.glob("*.py")}
NOMES_LOCAIS = {p.stem for p in RAIZ.glob("*.py")} | {"mod_fin"}


def _arquivos_do_modulo(nome):
    return set(m.MODULOS[nome]["arquivos"])


def _imports_locais(arquivo):
    """Módulos-locais (nome-base) importados por `arquivo`, top-level e dentro de funções."""
    tree = ast.parse((RAIZ / arquivo).read_text(encoding="utf-8"))
    achados = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                b = a.name.split(".")[0]
                if b in NOMES_LOCAIS:
                    achados.add(b)
        elif isinstance(node, ast.ImportFrom) and node.module:
            b = node.module.split(".")[0]
            if b in NOMES_LOCAIS:
                achados.add(b)
    return achados


def test_todo_py_esta_classificado():
    """Todo .py da raiz pertence a um módulo OU está na allowlist de shell — sem órfãos."""
    classificados = set()
    for v in m.MODULOS.values():
        for a in v["arquivos"]:
            if a.endswith(".py"):
                classificados.add(a)
    orfaos = PY_RAIZ - classificados - m.SHELL
    assert not orfaos, f"arquivos sem módulo (classifique em modulos.py ou SHELL): {sorted(orfaos)}"


def test_todo_arquivo_do_manifesto_existe():
    for nome, v in m.MODULOS.items():
        for a in v["arquivos"]:
            alvo = RAIZ / a
            assert alvo.exists(), f"{nome}: arquivo inexistente no manifesto: {a}"


def test_nucleo_nao_importa_dominio():
    """Regra de dependência: Núcleo NÃO pode importar módulo de domínio."""
    arqs_dominio = {a for d in m.DOMINIOS for a in _arquivos_do_modulo(d)}
    violacoes = []
    for nome in m.NUCLEO:
        for arquivo in _arquivos_do_modulo(nome):
            if not arquivo.endswith(".py"):
                continue
            for imp in _imports_locais(arquivo):
                if (imp + ".py") in arqs_dominio:
                    violacoes.append(f"{arquivo} (núcleo/{nome}) importa {imp} (domínio)")
    assert not violacoes, "Núcleo importando domínio:\n" + "\n".join(violacoes)


def test_dominios_so_importam_o_que_declaram():
    """Ratchet: um módulo de domínio só importa arquivos do próprio módulo, do Núcleo, dos módulos
    em depende_de, dos compartilhados, ou shell. Qualquer import cruzado NÃO declarado falha."""
    dono = {}
    for nome, v in m.MODULOS.items():
        for a in v["arquivos"]:
            dono[a if a.endswith(".py") else a] = nome
    violacoes = []
    for nome in m.DOMINIOS:
        permitidos = set(m.MODULOS[nome]["depende_de"]) | m.NUCLEO | {nome}
        for arquivo in _arquivos_do_modulo(nome):
            if not arquivo.endswith(".py"):
                continue
            for imp in _imports_locais(arquivo):
                impfile = imp + ".py"
                mod_imp = dono.get(impfile) or dono.get(imp)
                if mod_imp is None:
                    continue  # shell/tool/local não-modular
                if mod_imp in permitidos:
                    continue
                if impfile in m.COMPARTILHADOS and nome in m.COMPARTILHADOS[impfile]:
                    continue
                violacoes.append(f"{arquivo} ({nome}) importa {imp} ({mod_imp}) — não declarado em depende_de")
    assert not violacoes, "Import cruzado não declarado:\n" + "\n".join(violacoes)


def test_tabelas_batem_com_o_schema():
    """Toda tabela do manifesto existe em database.py e toda tabela do schema está classificada."""
    import database
    tabelas_schema = set(database.Base.metadata.tables.keys())
    tabelas_manifesto = {t for v in m.MODULOS.values() for t in v["tabelas"]}
    faltando_no_schema = tabelas_manifesto - tabelas_schema
    assert not faltando_no_schema, f"manifesto cita tabela inexistente: {sorted(faltando_no_schema)}"
    nao_classificadas = tabelas_schema - tabelas_manifesto
    assert not nao_classificadas, f"tabela sem módulo no manifesto: {sorted(nao_classificadas)}"
```

- [ ] **Step 2: Rodar** `python3 -m pytest tests/test_arquitetura_modulos.py -q`.
Expected: os testes de cobertura (`test_todo_py_esta_classificado`, `test_tabelas_batem_com_o_schema`) podem
**falhar** se algum `.py`/tabela ficou fora do manifesto — **isso é o teste funcionando**. Corrija classificando
o arquivo/tabela em `modulos.py` (Task 1) até verde. `test_nucleo_nao_importa_dominio` e
`test_dominios_so_importam_o_que_declaram` **devem passar** (o Núcleo já é limpo — verificado). Se
`test_dominios...` acusar um import cruzado real, **adicione-o a `depende_de`** do módulo (registra a dívida
existente, torna-a visível) — NÃO refatore código nesta fase.

- [ ] **Step 3: Rodar a suíte inteira** `python3 -m pytest -q` → verde (baseline 650 + novos). **Commit:**
```bash
git add tests/test_arquitetura_modulos.py modulos.py
git commit -m "test(arq): impoe fronteira de modulos (cobertura + pureza do nucleo + deps declaradas)"
```

---

## Task 3: Titularidade do Ciclo (faixas) explícita

**Files:** Modify `mod_ciclo.py`; Create `tests/test_ciclo_faixas.py`.

- [ ] **Step 1: Teste primeiro** — `tests/test_ciclo_faixas.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mod_ciclo as mc


def test_faixa_por_etapa_cobre_principais():
    # toda etapa principal tem uma faixa (titularidade)
    for cod in [c for c in mc.ETAPAS_PRINCIPAIS]:
        assert mc.faixa_da_etapa(cod) is not None, f"etapa {cod} sem faixa"


def test_faixas_conhecidas():
    assert mc.faixa_da_etapa("1") == "vendas"
    assert mc.faixa_da_etapa("7") == "vendas"
    assert mc.faixa_da_etapa("8") == "gate_financeiro_1"
    assert mc.faixa_da_etapa("11d") == "gate_financeiro_2"
    assert mc.faixa_da_etapa("11a") == "execucao_projeto"
    assert mc.faixa_da_etapa("13") == "expedicao"
    assert mc.faixa_da_etapa("18") == "montagem"


def test_gates_sao_faixas_de_gate():
    for g in mc.ETAPAS_APROVACAO_FINANCEIRA:
        assert mc.faixa_da_etapa(g).startswith("gate_")


def test_faixa_desconhecida_none():
    assert mc.faixa_da_etapa("999") is None
```

- [ ] **Step 2: Rodar → falha** (`AttributeError: faixa_da_etapa`).

- [ ] **Step 3: Implementar em `mod_ciclo.py`** (após `ETAPAS_APROVACAO_FINANCEIRA`, ~linha 143):

```python
# Faixas de titularidade do Ciclo (ARQUITETURA-MODULOS.md §Governança). Cada trecho de etapas pertence
# a uma faixa/equipe; as transições entre faixas são os gates de controle (8, 11d). Mapa explícito —
# antes a titularidade estava só implícita nas capabilities/constantes.
FAIXA_POR_ETAPA = {
    "1": "vendas", "2": "vendas", "3": "vendas", "4": "vendas", "7": "vendas",
    "8": "gate_financeiro_1",
    "9": "execucao_projeto", "10": "execucao_projeto",
    "11": "execucao_projeto", "11a": "execucao_projeto", "11b": "execucao_projeto",
    "11c": "execucao_projeto", "11e": "execucao_projeto",
    "11d": "gate_financeiro_2",
    "12": "expedicao", "13": "expedicao", "14": "expedicao", "15": "expedicao", "16": "expedicao",
    "17": "montagem", "18": "montagem", "19": "montagem", "20": "montagem",
}


def faixa_da_etapa(codigo):
    """Faixa de titularidade (dono operacional) da etapa, ou None se desconhecida.
    Faixas 'gate_*' são transições de controle (aprovação financeira). Ver Governança do Ciclo."""
    return FAIXA_POR_ETAPA.get(str(codigo))
```

- [ ] **Step 4: Rodar** `python3 -m pytest tests/test_ciclo_faixas.py -q` → verde; suíte inteira → verde. **Commit:**
```bash
git add mod_ciclo.py tests/test_ciclo_faixas.py
git commit -m "feat(ciclo): titularidade explicita (faixa_da_etapa) — governanca do ciclo"
```

---

## Task 4: Topologia — `Loja.modulos_ativos` + helpers

**Files:** Modify `database.py`, `mod_tenancy.py`; Create `tests/test_topologia_modulos.py`.

- [ ] **Step 1: Teste primeiro (unit dos helpers)** — `tests/test_topologia_modulos.py`:

```python
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mod_tenancy as mt
from types import SimpleNamespace


def _loja(modulos_ativos=None):
    return SimpleNamespace(id=1, modulos_ativos=modulos_ativos)


def test_default_tudo_ligado():
    # sem config (None/"") -> todos os domínios ativos
    loja = _loja(None)
    assert mt.modulo_ativo(loja, "fiscal") is True
    assert mt.modulo_ativo(loja, "comercial") is True


def test_nucleo_sempre_ativo():
    loja = _loja(json.dumps(["comercial"]))   # só comercial listado
    assert mt.modulo_ativo(loja, "auth") is True       # núcleo ignora a lista
    assert mt.modulo_ativo(loja, "tenancy") is True


def test_dominio_desligado():
    loja = _loja(json.dumps(["cadastro", "comercial", "financeiro"]))  # sem 'fiscal'
    assert mt.modulo_ativo(loja, "fiscal") is False
    assert mt.modulo_ativo(loja, "comercial") is True


def test_lista_ativa_resolve():
    loja = _loja(json.dumps(["cadastro"]))
    assert "cadastro" in mt.modulos_ativos_da_loja(loja)
    assert "fiscal" not in mt.modulos_ativos_da_loja(loja)
```

- [ ] **Step 2: Rodar → falha** (`AttributeError: modulo_ativo`).

- [ ] **Step 3a: `database.py` — coluna** (no modelo `Loja`, junto das outras colunas):
```python
    modulos_ativos = Column(Text, nullable=True)   # JSON: domínios ativos; NULL/"" = todos ligados (topologia)
```
E em `_migrar_colunas`, no bloco de `lojas` (onde já há `emitente_id`):
```python
            if "modulos_ativos" not in loja_cols:
                cur.execute("ALTER TABLE lojas ADD COLUMN modulos_ativos TEXT")
```

- [ ] **Step 3b: `mod_tenancy.py` — helpers** (usa o manifesto):
```python
def modulos_ativos_da_loja(loja):
    """Conjunto de módulos de DOMÍNIO ativos na loja. NULL/"" em `modulos_ativos` = todos ligados.
    O Núcleo é sempre ativo (não entra na lista). Topologia por cliente (ARQUITETURA-MODULOS.md)."""
    import json as _json
    import modulos as _mod
    bruto = getattr(loja, "modulos_ativos", None)
    if not (bruto or "").strip():
        return set(_mod.DOMINIOS)
    try:
        lista = _json.loads(bruto)
    except (ValueError, TypeError):
        return set(_mod.DOMINIOS)
    return {d for d in _mod.DOMINIOS if d in set(lista)}


def modulo_ativo(loja, modulo):
    """True se o módulo está ativo para a loja. Núcleo é sempre True; domínio depende da topologia."""
    import modulos as _mod
    if not _mod.desligavel(modulo):   # núcleo (ou desconhecido tratado como sempre-ligado)
        return True
    return modulo in modulos_ativos_da_loja(loja)
```

- [ ] **Step 4: Rodar** `python3 -m pytest tests/test_topologia_modulos.py -q` → verde; suíte inteira → verde
(reiniciar não é preciso p/ teste; a coluna nova é aditiva). **Commit:**
```bash
git add database.py mod_tenancy.py tests/test_topologia_modulos.py
git commit -m "feat(topologia): Loja.modulos_ativos + modulo_ativo/modulos_ativos_da_loja (default tudo-ligado)"
```

---

## Task 5: Endpoints de topologia + guard no dispatch

**Files:** Modify `main.py`; Test: adicionar a `tests/test_topologia_modulos.py`.

- [ ] **Step 1: Testes e2e primeiro** — adicionar a `tests/test_topologia_modulos.py` (usa `http_client_factory`,
`seed`, `app_db`; um usuário com `gerir_lojas`, ex.: `super`):

```python
def test_get_put_modulos_da_loja(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("super", "senha123")
    lid = seed["loja1_id"]
    st, d = c.get(f"/api/admin/lojas/{lid}/modulos")
    assert st == 200 and "fiscal" in d["ativos"]                 # default tudo-ligado
    st2, d2 = c.post(f"/api/admin/lojas/{lid}/modulos", {"ativos": ["cadastro", "comercial"]})
    assert st2 == 200
    st3, d3 = c.get(f"/api/admin/lojas/{lid}/modulos")
    assert "fiscal" not in d3["ativos"] and "comercial" in d3["ativos"]


def test_guard_bloqueia_modulo_desligado(http_client_factory, seed, app_db):
    # desliga o fiscal da loja1 → rota fiscal responde 403; religa → volta
    c = http_client_factory(); c.login("super", "senha123")
    lid = seed["loja1_id"]
    c.post(f"/api/admin/lojas/{lid}/modulos", {"ativos": ["cadastro", "comercial", "producao", "financeiro"]})
    dc = http_client_factory(); dc.login("dir_l1", "senha123")     # usuário operacional da loja1
    proj = seed["projeto_l1"]
    st, d = dc.get(f"/api/projetos/{proj}/ciclo/15/nfe")
    assert st == 403 and "módulo" in (d.get("erro", "")).lower()
    # religa
    c.post(f"/api/admin/lojas/{lid}/modulos", {"ativos": None})
    st2, _ = dc.get(f"/api/projetos/{proj}/ciclo/15/nfe")
    assert st2 in (200, 404)     # 200 (ok) ou 404 (projeto sem estado) — mas NÃO 403
```

- [ ] **Step 2: Rodar → falha** (endpoints/guard inexistentes).

- [ ] **Step 3a: `main.py` — guard no início do dispatch de API.** Localize o ponto onde o path das rotas
`/api/...` começa a ser tratado (após resolver `usuario`/`ator` e a loja ativa). Adicione um helper de módulo e a
checagem. Helper (junto de outros helpers, ex.: perto de `_cliente_dict`):
```python
def _bloqueio_modulo(path, loja):
    """Retorna (True, msg) se o path pertence a um módulo de domínio DESLIGADO para a loja; senão (False, None).
    Default tudo-ligado → nunca bloqueia sem config explícita. Topologia (ARQUITETURA-MODULOS.md)."""
    import modulos as _mod
    mod = _mod.modulo_do_path(path)
    if mod is None or loja is None:
        return (False, None)
    if mod_tenancy.modulo_ativo(loja, mod):
        return (False, None)
    return (True, "Módulo '%s' não está habilitado para esta loja." % mod)
```
Na cadeia de tratamento das rotas de domínio (onde já se resolve `loja_id`/`loja` via `escopo_operacional`),
antes de despachar a ação, adicionar:
```python
                    _bloq, _msg = _bloqueio_modulo(path, db.get(Loja, loja_id) if loja_id else None)
                    if _bloq:
                        self.send_json({"ok": False, "erro": _msg}, code=403); return
```
> **Onde exatamente:** aplique o guard nas rotas de domínio que já têm `loja`/`loja_id` resolvido (fiscal da
> etapa 15, clientes, orçamentos). Para a Fase 1, é suficiente cobrir o **fiscal** (o teste exercita a etapa 15);
> os demais domínios recebem o mesmo guard quando forem extraídos (Fase 2+). Não force o guard em rotas de núcleo.

- [ ] **Step 3b: `main.py` — endpoints GET/PUT `/api/admin/lojas/<id>/modulos`** (gated por `gerir_lojas` +
escopo, como os outros de loja; espelhe o padrão de `pode_editar_dados_loja`):
```python
            # GET /api/admin/lojas/<id>/modulos — domínios ativos (topologia)
            m = _re.match(r'^/api/admin/lojas/(\d+)/modulos$', path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja = db.get(Loja, int(m.group(1)))
                    if not loja:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if not mod_tenancy.pode_editar_dados_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                        self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                    self.send_json({"ok": True, "ativos": sorted(mod_tenancy.modulos_ativos_da_loja(loja))})
                finally:
                    db.close()
                return
```
E o **PUT/POST** análogo que grava `loja.modulos_ativos = json.dumps(lista)` (ou `None` para religar tudo),
validando que cada item ∈ `modulos.DOMINIOS`.

- [ ] **Step 4: Rodar** `python3 -m pytest tests/test_topologia_modulos.py -q` → verde; suíte inteira → verde.
**Reinicie o servidor** (mudança em Python) se for testar manualmente. **Commit:**
```bash
git add main.py tests/test_topologia_modulos.py
git commit -m "feat(topologia): endpoints /lojas/<id>/modulos + guard de modulo desligado no dispatch"
```

---

## Task 6: Documentação — manifesto imposto + roadmap de extração

**Files:** Modify `docs/ARQUITETURA-MODULOS.md`, `DEV_LOG.md`.

- [ ] **Step 1:** No topo de `ARQUITETURA-MODULOS.md`, trocar a nota "Não é um plano de refatoração" por uma que
reflita a Fase 1: o mapa agora tem um **manifesto executável** (`modulos.py`) e um **teste que impõe as
fronteiras** (`tests/test_arquitetura_modulos.py`); a titularidade do Ciclo virou `mod_ciclo.faixa_da_etapa`; e
a topologia (ligar/desligar domínio por loja) está implementada (`Loja.modulos_ativos`). Continua **sem split
físico** (isso é Fase 2+).

- [ ] **Step 2:** Adicionar seção **"Roadmap de extração física (Fase 2+)"** ao doc:
  - **Fase 2 (piloto):** extrair **Fiscal** para um pacote `fiscal/` (é o cluster mais isolado: `mod_fiscal`,
    `mapa_fiscal`, `emissor_focus`, `fiscal_cripto`, `nfe_emissao`, `mod_nfe` pricing). Pré-condição já satisfeita:
    o teste de fronteira garante que só `cadastro`/`comercial`/núcleo entram. **Plano próprio** (brainstorm→spec→plano).
  - **Fase 3+:** demais domínios existentes (Comercial, Produção, Financeiro) na ordem de menor acoplamento; cada
    um só depois que o ratchet de `depende_de` estiver mínimo.
  - **Domínios NOVOS** (Estoque, Pós-venda, Financeiro completo, Expedição): **cada um seu ciclo
    brainstorm→spec→plano** — a fronteira/stub já existe no manifesto.
  - **Regra de saída da Fase 1→2:** um módulo só é candidato a extração quando seu `depende_de` no manifesto está
    minimizado e o teste de fronteira está verde há tempo (sem exceções acumuladas).

- [ ] **Step 3:** `DEV_LOG.md` — nova nota: Fase 1 da modularização (manifesto + fronteira imposta + titularidade
+ topologia), suíte nova contagem, pendências = fases de extração. **Commit:**
```bash
git add docs/ARQUITETURA-MODULOS.md DEV_LOG.md
git commit -m "docs(arq): modularizacao Fase 1 implementada (manifesto imposto) + roadmap de extracao"
```

---

## Roadmap resumido (fora desta fase)
- **Fase 2:** extração-piloto do **Fiscal** em pacote (plano próprio).
- **Fase 3+:** extração dos demais domínios existentes, por ordem de acoplamento.
- **Domínios novos** (Estoque, Financeiro completo, Pós-venda, Expedição): cada um brainstorm→spec→plano próprio.
- **Reconciliação 38↔20 etapas** (conflito aberto do doc): tarefa própria, pré-requisito de amadurecer as faixas.

---

## Self-review do plano
- **Cobertura do spec (`ARQUITETURA-MODULOS.md`):** dois níveis Núcleo/Domínio → manifesto (T1) · regra de
  dependência → teste de fronteira (T2) · Governança/faixas → `faixa_da_etapa` (T3) · "ligar/desligar por
  cliente" → topologia (T4/T5) · "onde mora código novo" → manifesto+cobertura força classificação (T1/T2) ·
  "zero split físico / zero rewrite" → respeitado (nada move) · domínios NOVOS ficam como stub/fronteira (T1) e
  cada um vira plano próprio (roadmap).
- **Sem placeholders:** todo passo tem código completo (manifesto, helpers, teste de `ast`, faixas, topologia,
  endpoints, guard). Os pontos "localize onde no main.py" são verificações com o padrão exato a espelhar, não TODOs.
- **Consistência de nomes:** `modulos.MODULOS/NUCLEO/DOMINIOS/desligavel/modulo_de_arquivo/modulo_de_tabela/
  modulo_do_path`; `mod_tenancy.modulo_ativo/modulos_ativos_da_loja`; `mod_ciclo.faixa_da_etapa/FAIXA_POR_ETAPA`;
  `Loja.modulos_ativos`; `_bloqueio_modulo`. Usados igualzinho entre tarefas.
- **Ratchet, não big-bang:** o teste de fronteira nasce verde (Núcleo já é limpo) e registra o acoplamento atual
  como `depende_de` — impede regressão sem exigir refatoração agora. É a rede de segurança da extração futura.
