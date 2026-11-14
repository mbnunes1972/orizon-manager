import sys, os, ast, pathlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import modulos as m

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PY_RAIZ = {p.name for p in RAIZ.glob("*.py")}

# Pacotes locais (dir com __init__.py) detectados, não hardcoded: antes havia um
# `| {"mod_fin"}` na mão, que só o mod_fin ganhava — qualquer pacote novo ficava
# invisível para os testes de dependência abaixo.
PACOTES_LOCAIS = {d.name for d in RAIZ.iterdir()
                  if d.is_dir() and (d / "__init__.py").exists()}
NOMES_LOCAIS = {p.stem for p in RAIZ.glob("*.py")} | PACOTES_LOCAIS


def _arquivos_do_modulo(nome):
    """Arquivos do módulo. Entrada que é PACOTE (diretório) expande para os .py de dentro.

    Sem essa expansão, os testes de dependência (que fazem `if not
    arquivo.endswith(".py"): continue`) PULAVAM o pacote inteiro — o ratchet ficava
    verde sem checar uma linha do que está lá dentro. Era o caso do mod_fin desde
    que virou pacote: nunca foi verificado.
    """
    out = set()
    for a in m.MODULOS[nome]["arquivos"]:
        p = RAIZ / a
        if p.is_dir():
            out |= {f.relative_to(RAIZ).as_posix() for f in p.rglob("*.py")}
        else:
            out.add(a)
    return out


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
    """Regra de dependência: Núcleo NÃO pode importar módulo de domínio.

    Reconhece o domínio pelo nome do arquivo da raiz (`import mod_folha`) E pelo nome do pacote
    (`from folha import mod_folha`). Sem a segunda parte, a trava só funcionava enquanto existissem
    shims na raiz — e deixaria de funcionar quando eles fossem aposentados (Fase 6 do plano de
    organização, 13/11/2026)."""
    arqs_dominio = {a for d in m.DOMINIOS for a in _arquivos_do_modulo(d)}
    pacotes_dominio = {pathlib.Path(a).name for d in m.DOMINIOS for a in m.MODULOS[d]["arquivos"]
                       if (RAIZ / a).is_dir()}
    violacoes = []
    for nome in m.NUCLEO:
        for arquivo in _arquivos_do_modulo(nome):
            if not arquivo.endswith(".py"):
                continue
            for imp in _imports_locais(arquivo):
                if (imp + ".py") in arqs_dominio or imp in pacotes_dominio:
                    violacoes.append(f"{arquivo} (núcleo/{nome}) importa {imp} (domínio)")
    assert not violacoes, "Núcleo importando domínio:\n" + "\n".join(violacoes)


def test_dominios_so_importam_o_que_declaram():
    """Ratchet: um módulo de domínio só importa arquivos do próprio módulo, do Núcleo, dos módulos
    em depende_de, dos compartilhados, ou shell. Qualquer import cruzado NÃO declarado falha."""
    dono = {}
    for nome, v in m.MODULOS.items():
        for a in v["arquivos"]:
            dono[a] = nome
            # Pacote: registra também o nome-base, porque um `from fiscal import X`
            # chega aqui como o import de "fiscal", não de "fiscal.py".
            if (RAIZ / a).is_dir():
                dono[pathlib.Path(a).name] = nome
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


def test_chat_pacote_nao_importa_host():
    """Ratchet do MÓDULO DESTACÁVEL (spec _geral/2026-07-31-chat-modulo-destacavel-portas):
    dentro de chat/ só entram stdlib, libs e o SCHEMA compartilhado (database) — nenhum módulo
    do host (mod_*, auth, main, storage, fiscal, …). O host fala com o chat importando-o
    (direção host→chat é livre); o chat fala com o host SÓ pelas portas (chat/ports.py,
    adaptadores registrados em chat_host.py). Sem este ratchet o desacoplamento regride em
    três commits."""
    PERMITIDOS = {"chat", "database"}
    violacoes = []
    for f in sorted((RAIZ / "chat").rglob("*.py")):
        rel = f.relative_to(RAIZ).as_posix()
        for imp in _imports_locais(rel):
            if imp not in PERMITIDOS:
                violacoes.append(f"{rel} importa {imp} — use uma porta (chat/ports.py)")
    assert not violacoes, "chat/ acoplado ao host:\n" + "\n".join(violacoes)


# --- Shims de compatibilidade (empacotamento) -------------------------------------------------
# Um shim é um .py da raiz que entrega o módulo real de um pacote no lugar dele, via
# `sys.modules[__name__] = <módulo real>` (padrão do mod_chat.py, 31/07/2026). Os dois testes
# abaixo são as travas do plano de organização (Fase 5, 13/11/2026).

def _shims_da_raiz():
    """{nome do shim: nome completo do módulo real}, lidos do código de cada shim."""
    shims = {}
    for p in sorted(RAIZ.glob("*.py")):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        # Shim = atribuição de TOPO `<x>.modules[__name__] = <nome>` (lida pela estrutura, não
        # pelo texto: o main.py cita "sys.modules[__name__]" num comentário e não é shim).
        alvo = None
        for node in tree.body:
            if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Name)):
                continue
            t = node.targets[0]
            if (isinstance(t, ast.Subscript) and isinstance(t.value, ast.Attribute)
                    and t.value.attr == "modules" and isinstance(t.slice, ast.Name)
                    and t.slice.id == "__name__"):
                alvo = node.value.id
        if alvo is None:
            continue
        # … e de onde ele veio (ex.: `from folha import mod_folha as _real` → folha.mod_folha)
        real = None
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                for a in node.names:
                    if (a.asname or a.name) == alvo:
                        real = f"{node.module}.{a.name}"
        assert real, f"{p.name}: shim sem `from <pacote> import <módulo> as <nome>` reconhecível"
        shims[p.stem] = real
    return shims


def test_shims_sao_importados_no_topo_do_main():
    """Todo shim tem que ser importado no NÍVEL DE MÓDULO do main.py (no boot, thread única).

    Por quê (main.py, comentário dos shims do chat): se a PRIMEIRA importação de um shim acontece
    dentro de um handler, duas requisições simultâneas podem disputar o lock de import e uma delas
    pega o shim vazio, antes da troca no sys.modules. Aconteceu em produção:
    `AttributeError: module 'mod_chat_externo' has no attribute 'varrer_triagem_vencida'`."""
    tree = ast.parse((RAIZ / "main.py").read_text(encoding="utf-8"))
    no_topo = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            no_topo |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            no_topo.add(node.module.split(".")[0])
    faltando = sorted(set(_shims_da_raiz()) - no_topo)
    assert not faltando, ("shim(s) sem import no topo do main.py (risco de corrida de import entre "
                          "threads): " + ", ".join(faltando))


def test_shim_e_o_mesmo_objeto_do_modulo_real():
    """`import mod_X` e `from <pacote> import mod_X` têm que devolver o MESMO objeto de módulo.

    Um shim escrito como `from pacote.mod_X import *` cria uma CÓPIA: o monkeypatch dos testes
    passa a valer na cópia, o código real não é afetado, e o teste fica verde testando nada."""
    import importlib
    diferentes = []
    for shim, real in _shims_da_raiz().items():
        if importlib.import_module(shim) is not importlib.import_module(real):
            diferentes.append(f"{shim} → {real}")
    assert not diferentes, "shim e módulo real são objetos diferentes: " + ", ".join(diferentes)


# Teto de imports PELO NOME DO SHIM, por shim. Só pode BAIXAR: import novo pelo nome antigo
# reprova; quem aposenta usos baixa o número no mesmo commit; shim que chega a zero é apagado e
# sai daqui. Medido em 13/11/2026, depois de aposentar os shims da Onda A (expedicao, assistencias,
# folha). Plano de organização, Fase 6 (feita aos pedaços, junto de cada onda).
TETO_IMPORTS_POR_SHIM = {"mod_chat": 103, "mod_chat_externo": 69,
                         # Fase 4 — comercial (empacotado em 14/11/2026; aposentar em seguida).
                         # Pontos cegos conhecidos: __import__("mod_negociacao") em
                         # tests/test_negociacao.py (2x) — trocar à mão na aposentadoria.
                         "mod_arvore": 2, "mod_assinatura": 1, "mod_clicksign": 45,
                         "mod_comercial_dash": 3, "mod_contrato": 119, "mod_documentos": 48,
                         "mod_documentos_import": 4, "mod_equipe": 14, "mod_marcadores": 7,
                         "mod_margens": 1, "mod_medicao": 2, "mod_negociacao": 9,
                         "mod_orcamento_params": 24, "mod_parcelas": 8, "mod_pe_comparacao": 4,
                         "mod_qualidade_xml": 3, "mod_retido": 12}
# Ponto cego desta contagem: `__import__("mod_x")` / `importlib.import_module("mod_x")` com o nome
# como TEXTO não é import para o ast. Ao aposentar um shim, procure também por isso (foi o caso de
# `__import__("mod_ciclo")` em tests/test_conciliacao_pe_e2e.py, na Onda B).


def _usos_pelo_nome_do_shim(shims):
    """Quantas vezes cada nome de shim aparece num import absoluto, em todo o repositório."""
    cont = {s: 0 for s in shims}
    for f in RAIZ.rglob("*.py"):
        rel = f.relative_to(RAIZ)
        if rel.parts[0] in (".venv", "venv", "node_modules") or rel.parts[0].startswith("wt-"):
            continue
        if len(rel.parts) == 1 and f.stem in cont:
            continue  # o próprio shim
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name in cont:
                        cont[a.name] += 1
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module in cont:
                cont[node.module] += 1
    return cont


def test_shims_so_diminuem():
    """Catraca: o número de imports pelo nome de cada shim só pode cair, até o shim ser apagado."""
    shims = set(_shims_da_raiz())
    assert shims == set(TETO_IMPORTS_POR_SHIM), (
        "TETO_IMPORTS_POR_SHIM desatualizado — shim sem teto: %s; teto sem shim (apague a entrada): %s"
        % (sorted(shims - set(TETO_IMPORTS_POR_SHIM)), sorted(set(TETO_IMPORTS_POR_SHIM) - shims)))
    problemas = []
    for shim, n in sorted(_usos_pelo_nome_do_shim(shims).items()):
        teto = TETO_IMPORTS_POR_SHIM[shim]
        if n > teto:
            problemas.append(f"{shim}: {n} imports > teto {teto} — importe pelo pacote, não pelo shim")
        elif n < teto:
            problemas.append(f"{shim}: {n} imports < teto {teto} — baixe o teto para {n} neste commit")
    assert not problemas, "\n".join(problemas)
