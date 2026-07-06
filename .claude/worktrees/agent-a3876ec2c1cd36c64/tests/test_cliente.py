import main


def test_cadastro_minimo_completo_sem_faltas():
    assert main.validar_cadastro_minimo(
        {"nome": "Ana", "email": "ana@x.com", "telefone": "(12) 99999-0000"}) == []


def test_cadastro_minimo_falta_email_e_telefone():
    faltando = main.validar_cadastro_minimo({"nome": "Ana"})
    assert "E-mail" in faltando
    assert "Telefone" in faltando
    assert "Nome" not in faltando


def test_cadastro_minimo_cpf_nao_exigido():
    faltando = main.validar_cadastro_minimo(
        {"nome": "Ana", "email": "ana@x.com", "telefone": "1"})
    assert faltando == []


def test_cadastro_minimo_strip():
    faltando = main.validar_cadastro_minimo(
        {"nome": "Ana", "email": "  ", "telefone": "1"})
    assert faltando == ["E-mail"]
