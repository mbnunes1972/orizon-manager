"""Trava os caminhos relativos a __file__ dos módulos que viraram PACOTE.

Por que existe: na reorganização de 2026-07-15, mover auth_routes.py da raiz para
auth/ quebrou `_LOGIN_HTML = join(dirname(__file__), "static", "login.html")` — ele
passou a apontar para auth/static/login.html. O `except FileNotFoundError` de
_serve_login devolvia 404 em SILÊNCIO: a PÁGINA DE ENTRADA sumiu, sem erro no log,
e os 1181 testes continuaram verdes. O usuário achou antes da suíte.

Import quebrado explode alto; caminho quebrado devolve 404 educado. Por isso estes
testes olham o CAMINHO, não o import.
"""
import os
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent


def test_login_html_resolve_da_raiz():
    """O regressor: a página de entrada tem que ser encontrável de dentro de auth/."""
    from auth import auth_routes
    assert os.path.exists(auth_routes._LOGIN_HTML), \
        "login.html não encontrado em %s — a página de entrada volta a dar 404" % auth_routes._LOGIN_HTML
    assert pathlib.Path(auth_routes._LOGIN_HTML).resolve() == (RAIZ / "static" / "login.html").resolve()


def test_caminhos_dos_pacotes_apontam_para_a_raiz():
    """Todo caminho de config/dado montado dentro de um pacote resolve na RAIZ."""
    from fiscal import fiscal_cripto
    from integracoes import focus_config
    for rotulo, caminho, esperado in [
        ("fiscal.key", fiscal_cripto._KEYFILE, RAIZ / "config" / "fiscal.key"),
        ("focus_config.json", focus_config.FOCUS_CONFIG_FILE, RAIZ / "focus_config.json"),
    ]:
        assert pathlib.Path(caminho).resolve() == esperado.resolve(), \
            "%s aponta para %s, esperado %s" % (rotulo, caminho, esperado)


def test_nenhum_pacote_usa_um_dirname_so_para_alcancar_a_raiz():
    """Ratchet: dentro de pacote, `dirname(__file__)` é a pasta do PACOTE, não a raiz.

    Quem precisa da raiz sobe um nível. DOIS idiomas fazem isso e ambos valem:
      1. os.path.dirname(os.path.dirname(__file__))        (mod_fin/base.py)
      2. os.path.join(os.path.dirname(__file__), "..", X)  (mod_fin/__init__.py)
    O bug que derrubou a página de entrada foi um dirname SOZINHO, sem nenhum dos
    dois. Este teste pega a próxima ocorrência antes de virar 404 em produção.

    (A 1ª versão deste teste só aceitava o idioma 1 e acusou o mod_fin, que está
    correto — falso positivo que teria bloqueado código bom.)"""
    import re
    suspeitos = []
    for pkg in ("auth", "fiscal", "integracoes", "mod_fin"):
        d = RAIZ / pkg
        if not d.is_dir():
            continue
        for f in d.rglob("*.py"):
            for i, ln in enumerate(f.read_text(encoding="utf-8").split("\n"), 1):
                if "__file__" not in ln or ln.strip().startswith("#"):
                    continue
                if not re.search(r'os\.path\.dirname\(\s*(os\.path\.abspath\()?\s*__file__', ln):
                    continue
                compacta = ln.replace(" ", "")
                sobe_dois_dirname = "dirname(os.path.dirname" in compacta
                sobe_com_pontopoint = '".."' in compacta or "'..'" in compacta
                if not (sobe_dois_dirname or sobe_com_pontopoint):
                    suspeitos.append("%s:%d  %s" % (f.relative_to(RAIZ).as_posix(), i, ln.strip()[:70]))
    assert not suspeitos, (
        "dentro de pacote, um dirname() só chega na pasta do pacote — não na raiz.\n"
        "Suba um nível (dirname(dirname(__file__)) ou join(dirname(__file__), '..', X)):\n  "
        + "\n  ".join(suspeitos))
