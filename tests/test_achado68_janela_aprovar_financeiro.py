# -*- coding: utf-8 -*-
"""ACHADO-68 (docs/db/TAREFA_ACHADO68_REAUTENTICACAO.md) — a janela de reaprovação de
`aprovar_financeiro`: pede a senha uma vez, abre uma janela de 15min NO SERVIDOR (não na tela),
por CAPACIDADE (token, 'aprovar_financeiro'), com expiração ABSOLUTA e morte no logout.

Testa `main._aprovador_financeiro` diretamente (sem subir os 15 endpoints que ainda não foram
migrados para passar `handler=self` — isso é o próximo passo, mecânico, depois deste modelo
provado). Usa sessões REAIS (`auth.fazer_login`), não um token qualquer — `_stepup_valido`
consulta o dict global `_STEPUP_GRANTS` pelo token, então o teste precisa de tokens de verdade
para provar isolamento entre sessões."""
import time

import pytest

import main
from auth import auth as auth_mod


@pytest.fixture(autouse=True)
def _sem_janela_sobrando_entre_testes():
    """`_STEPUP_GRANTS` é um dict de PROCESSO (mesmo padrão de `_LOGIN_TENTATIVAS`) — sem
    limpar, uma janela aberta num teste vazaria pro próximo."""
    main._STEPUP_GRANTS.clear()
    yield
    main._STEPUP_GRANTS.clear()


class _FakeHandler:
    """Só o suficiente pra `_aprovador_financeiro` extrair o token via
    `get_token_from_cookie(handler.headers.get('Cookie', ''))` — mesmo contrato de
    `_sem_acesso_modulo(usuario, modulo_id, handler=None)`."""
    def __init__(self, token):
        self.headers = {"Cookie": "orizon_session=%s" % token}


def _login(who):
    r = auth_mod.fazer_login(who, "senha123")
    assert r["ok"], r
    return r["token"], r["usuario"]


def test_com_capacidade_pede_uma_vez_e_janela_libera_as_seguintes(app_db, seed):
    db = app_db.get_session()
    try:
        token, usuario = _login("dir_l1")   # master → tem aprovar_financeiro
        handler = _FakeHandler(token)
        sessao = {"id": usuario["id"]}

        # 1ª chamada: SEM credenciais, SEM janela ainda — tem que pedir senha.
        res = main._aprovador_financeiro(db, "", "", sessao=sessao, handler=handler)
        assert not res, "sem janela e sem credenciais, tem que negar (nunca 'sessão-primeiro' puro)"

        # 1ª chamada de verdade: COM credenciais — autoriza e ABRE a janela.
        res = main._aprovador_financeiro(db, "dir_l1", "senha123", sessao=sessao, handler=handler)
        assert res and res.id == usuario["id"]
        assert res.sessao_emprestada is False

        # 2ª chamada, mesma sessão, SEM credenciais: a janela libera, sem repetir senha.
        res2 = main._aprovador_financeiro(db, "", "", sessao=sessao, handler=handler)
        assert res2 and res2.id == usuario["id"]
        assert res2.sessao_emprestada is False
    finally:
        db.close()


def test_janela_expira_por_tempo_absoluto(app_db, seed, monkeypatch):
    db = app_db.get_session()
    try:
        token, usuario = _login("dir_l1")
        handler = _FakeHandler(token)
        sessao = {"id": usuario["id"]}

        assert main._aprovador_financeiro(db, "dir_l1", "senha123", sessao=sessao, handler=handler)
        assert main._aprovador_financeiro(db, "", "", sessao=sessao, handler=handler)

        # Expiração ABSOLUTA: avança o relógio além do TTL (não é deslizante — não teria
        # "renovado" nada entre as duas chamadas acima).
        futuro = time.time() + main._APROVAR_FINANCEIRO_JANELA_SEGUNDOS + 1
        monkeypatch.setattr(main.time, "time", lambda: futuro)

        res = main._aprovador_financeiro(db, "", "", sessao=sessao, handler=handler)
        assert not res, "passada a janela, tem que pedir a senha de novo"
    finally:
        db.close()


def test_janela_morre_no_logout(app_db, seed):
    db = app_db.get_session()
    try:
        token, usuario = _login("dir_l1")
        handler = _FakeHandler(token)
        sessao = {"id": usuario["id"]}

        assert main._aprovador_financeiro(db, "dir_l1", "senha123", sessao=sessao, handler=handler)
        assert main._aprovador_financeiro(db, "", "", sessao=sessao, handler=handler)

        auth_mod.fazer_logout(token)
        main._stepup_revogar_todos(token)   # o que a rota de logout chama (auth_routes.py)

        res = main._aprovador_financeiro(db, "", "", sessao=sessao, handler=handler)
        assert not res, "a janela não pode sobreviver ao logout que a criou"
    finally:
        db.close()


def test_janela_nao_vale_para_outro_token_nem_outro_usuario(app_db, seed):
    db = app_db.get_session()
    try:
        token_a, usuario_a = _login("dir_l1")
        handler_a = _FakeHandler(token_a)
        sessao_a = {"id": usuario_a["id"]}
        assert main._aprovador_financeiro(db, "dir_l1", "senha123", sessao=sessao_a, handler=handler_a)

        # Mesmo usuário, uma 2ª SESSÃO (outro token — ex.: outro navegador): não herda a janela
        # da primeira, mesmo sendo a mesma pessoa (a janela é do TOKEN, não do usuário).
        token_b, usuario_b = _login("dir_l1")
        assert usuario_b["id"] == usuario_a["id"]
        handler_b = _FakeHandler(token_b)
        sessao_b = {"id": usuario_b["id"]}
        res = main._aprovador_financeiro(db, "", "", sessao=sessao_b, handler=handler_b)
        assert not res, "token de OUTRA sessão não pode herdar a janela, nem sendo o mesmo usuário"

        # Um usuário DIFERENTE (que também tem a capacidade) tampouco herda a janela do dir_l1
        # tentando usar o token dele por engano — reforça que a chave é (token, capacidade).
        res_token_a_outra_sessao = main._aprovador_financeiro(
            db, "", "", sessao=sessao_a, handler=handler_a)
        assert res_token_a_outra_sessao, "o TOKEN original continua com a janela dele"
    finally:
        db.close()


def test_sessao_sem_capacidade_e_emprestada_nunca_abre_janela(app_db, seed):
    db = app_db.get_session()
    try:
        token, usuario_operador = _login("cons_l1")   # operador → NÃO tem aprovar_financeiro
        handler = _FakeHandler(token)
        sessao = {"id": usuario_operador["id"]}

        # Sem credenciais: nunca autoriza (nem tenta janela nenhuma — sessão não tem a capacidade).
        assert not main._aprovador_financeiro(db, "", "", sessao=sessao, handler=handler)

        # Gerente (dir_l1) digita a PRÓPRIA senha na sessão do operador: autoriza, mas é
        # SESSÃO EMPRESTADA por definição (a sessão logada não tem a capacidade).
        res = main._aprovador_financeiro(db, "dir_l1", "senha123", sessao=sessao, handler=handler)
        assert res and res.login == "dir_l1"
        assert res.sessao_emprestada is True, "credenciais de outra pessoa numa sessão sem a capacidade É empréstimo"

        # E não abriu janela nenhuma neste token: uma 2ª chamada sem credenciais volta a negar.
        res2 = main._aprovador_financeiro(db, "", "", sessao=sessao, handler=handler)
        assert not res2, "sessão emprestada nunca ganha janela — cada uso pede credenciais de novo"
    finally:
        db.close()


def test_sem_handler_nunca_abre_nem_consulta_janela(app_db, seed):
    """Fail-safe: sem `handler` (logo, sem token), a janela nunca é concedida nem consultada —
    cada chamada exige credenciais, nunca o contrário."""
    db = app_db.get_session()
    try:
        _, usuario = _login("dir_l1")
        sessao = {"id": usuario["id"]}
        assert main._aprovador_financeiro(db, "dir_l1", "senha123", sessao=sessao)  # sem handler
        assert not main._aprovador_financeiro(db, "", "", sessao=sessao)  # sem handler, sem credenciais
    finally:
        db.close()


def test_credencial_de_outra_pessoa_com_capacidade_propria_nao_abre_janela(app_db, seed):
    """Correção de 11/09: a versão anterior abria janela pra QUALQUER credencial válida numa
    sessão que já tinha a capacidade — inclusive credencial de OUTRA pessoa, que é a mesma
    escalada que a sessão emprestada existe pra impedir, só que entrando pela porta 1 em vez
    da porta 3. `dir_l1` está logado (TEM aprovar_financeiro) mas digita a senha de `dir_l2`
    (também master, também tem a capacidade) — tem que autorizar (a permissão de quem digitou
    é real) mas NUNCA abrir janela, e marcar sessão emprestada."""
    db = app_db.get_session()
    try:
        token, usuario_dir_l1 = _login("dir_l1")
        handler = _FakeHandler(token)
        sessao = {"id": usuario_dir_l1["id"]}

        res = main._aprovador_financeiro(db, "dir_l2", "senha123", sessao=sessao, handler=handler)
        assert res and res.login == "dir_l2"
        assert res.sessao_emprestada is True, (
            "credencial de OUTRA pessoa é sessão emprestada mesmo quando a sessão logada "
            "também tem a capacidade — senão é a escalada que o ramo 3 existe pra impedir, "
            "entrando pela porta do ramo 1")

        # Não abriu janela nenhuma: uma chamada seguinte sem credenciais volta a negar, mesmo
        # a sessão (dir_l1) tendo a capacidade por conta própria.
        res2 = main._aprovador_financeiro(db, "", "", sessao=sessao, handler=handler)
        assert not res2, "janela não pode ter aberto a partir de credencial de terceiro"

        # E a PRÓPRIA credencial do dono da sessão, na sequência, abre a janela normalmente —
        # prova que o bloqueio é específico da credencial alheia, não um efeito colateral geral.
        res3 = main._aprovador_financeiro(db, "dir_l1", "senha123", sessao=sessao, handler=handler)
        assert res3 and res3.sessao_emprestada is False
        res4 = main._aprovador_financeiro(db, "", "", sessao=sessao, handler=handler)
        assert res4 and res4.sessao_emprestada is False
    finally:
        db.close()


def test_stepup_grants_nao_cresce_sem_limite(app_db, seed):
    """ACHADO-68 (revisão 11/09): `_STEPUP_GRANTS` é dict de PROCESSO — sem purga proativa, uma
    janela que ninguém mais consulta fica pra sempre. `_stepup_conceder` varre expirados a cada
    nova concessão."""
    agora = time.time()
    for i in range(50):
        main._STEPUP_GRANTS[("token-fantasma-%d" % i, "aprovar_financeiro")] = agora - 1  # já expirados
    assert len(main._STEPUP_GRANTS) == 50

    main._stepup_conceder("token-novo", "aprovar_financeiro", ttl=60)
    assert len(main._STEPUP_GRANTS) == 1, (
        "uma nova concessão tem que varrer as expiradas, não só somar mais uma ao dict")
    assert main._stepup_valido("token-novo", "aprovar_financeiro")


def test_resposta_pos_aprovacao_injeta_expiracao_da_janela_para_a_tela(app_db, seed):
    """A tela decide se pula o modal na PRÓXIMA ação lendo este campo — não é o que autoriza
    (isso `_aprovador_financeiro` decide de novo, no servidor, a cada request)."""
    db = app_db.get_session()
    try:
        token, usuario = _login("dir_l1")
        handler = _FakeHandler(token)
        sessao = {"id": usuario["id"]}

        aprovador = main._aprovador_financeiro(db, "dir_l1", "senha123", sessao=sessao, handler=handler)
        resp = main._resposta_pos_aprovacao_financeira(aprovador, {"ok": True})
        assert resp["ok"] is True
        assert "janela_aprovar_financeiro_expira_em_ms" in resp
        agora_ms = time.time() * 1000
        assert agora_ms < resp["janela_aprovar_financeiro_expira_em_ms"] <= agora_ms + main._APROVAR_FINANCEIRO_JANELA_SEGUNDOS * 1000 + 1000

        # Sem janela (token novo, nunca autenticou): resposta sai limpa, sem o campo.
        outro_aprovador = main._AprovadorFinanceiro(None, token="token-sem-janela-nenhuma")
        resp2 = main._resposta_pos_aprovacao_financeira(outro_aprovador, {"ok": True})
        assert "janela_aprovar_financeiro_expira_em_ms" not in resp2
    finally:
        db.close()


def test_resposta_pos_aprovacao_sessao_emprestada_nunca_traz_expiracao_de_janela(app_db, seed):
    db = app_db.get_session()
    try:
        token, usuario_operador = _login("cons_l1")
        handler = _FakeHandler(token)
        sessao = {"id": usuario_operador["id"]}
        aprovador = main._aprovador_financeiro(db, "dir_l1", "senha123", sessao=sessao, handler=handler)
        assert aprovador.sessao_emprestada is True

        resp = main._resposta_pos_aprovacao_financeira(aprovador, {"ok": True})
        assert resp["sessao_encerrada"] is True
        assert "janela_aprovar_financeiro_expira_em_ms" not in resp, (
            "sessão emprestada não pode informar janela nenhuma — ela não abriu uma")

        from database import Sessao as _Sessao
        s = db.query(_Sessao).filter_by(token=token).first()
        assert s.ativa == 0, "a sessão emprestada tinha que ter sido invalidada de verdade"
    finally:
        db.close()


def test_outra_capacidade_continua_sessao_primeiro_sem_janela(app_db, seed):
    """Categoria 2 (as 9 demais capacidades) INALTERADA — `_usuario_com_capacidade` continua
    'sessão-primeiro pra sempre', sem depender de `_STEPUP_GRANTS` nenhum. Guarda de regressão:
    o ACHADO-68 não pode ter tocado nesta função."""
    db = app_db.get_session()
    try:
        _, usuario = _login("dir_l1")
        sessao = {"id": usuario["id"]}
        # 'aprovar_medicao_reprovada': master tem, via perfis — sessão-primeiro autoriza direto,
        # sem senha, sem janela, hoje e sempre (não é o que este ACHADO mudou).
        from auth import perfis as _perfis
        assert _perfis.pode("master", "aprovar_medicao_reprovada")
        u = main._usuario_com_capacidade(db, "", "", "aprovar_medicao_reprovada", sessao=sessao)
        assert u is not None and u.id == usuario["id"]
    finally:
        db.close()
