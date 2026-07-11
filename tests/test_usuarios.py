# -*- coding: utf-8 -*-
import mod_usuarios as mu


def test_validar_novo_usuario_ok():
    erros = mu.validar_novo_usuario(
        {"nome": "Ana", "login": "ana", "senha": "12345", "nivel": "operador"},
        logins_existentes=["pedro"])
    assert erros == []


def test_validar_novo_usuario_campos_obrigatorios():
    erros = mu.validar_novo_usuario({"nome": "", "login": "", "senha": "", "nivel": ""},
                                    logins_existentes=[])
    j = " ".join(erros).lower()
    assert "nome" in j and "login" in j and "senha" in j and "perfil" in j


def test_validar_novo_usuario_login_duplicado():
    erros = mu.validar_novo_usuario(
        {"nome": "Ana", "login": "Ana", "senha": "123", "nivel": "consultor"},
        logins_existentes=["ana"])           # case-insensitive
    assert any("login" in e.lower() and "exist" in e.lower() for e in erros)


def test_validar_novo_usuario_perfil_invalido():
    erros = mu.validar_novo_usuario(
        {"nome": "Ana", "login": "ana", "senha": "123", "nivel": "rei"},
        logins_existentes=[])
    assert any("perfil" in e.lower() for e in erros)


def test_validar_edicao_usuario():
    assert mu.validar_edicao_usuario({"nivel": "gerencial"}) == []
    assert mu.validar_edicao_usuario({}) == []                 # nada a validar
    erros = mu.validar_edicao_usuario({"nivel": "rei"})
    assert any("perfil" in e.lower() for e in erros)


def test_email_invalido_acusa():
    erros = mu.validar_novo_usuario(
        {"nome": "Ana", "login": "ana", "senha": "1", "nivel": "consultor", "email": "errado"},
        logins_existentes=[])
    assert any("mail" in e.lower() for e in erros)

def test_email_valido_ou_vazio_passa():
    base = {"nome": "Ana", "login": "ana", "senha": "1", "nivel": "operador"}
    assert mu.validar_novo_usuario({**base, "email": "a@b.com"}, []) == []
    assert mu.validar_novo_usuario({**base, "email": ""}, []) == []

def test_edicao_email_invalido_acusa():
    assert any("mail" in e.lower() for e in mu.validar_edicao_usuario({"email": "x"}))
