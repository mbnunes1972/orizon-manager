# tests/test_contrato_loja.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import database


def _loja_completa():
    return {
        # LI-4b (docs/db/LISTA_IMEDIATA.md, 25/09): "nome" é o Nome Fantasia -- diferente de
        # propósito de razao_social/cnpj_fiscal (Emitente), que agora também são obrigatórios
        # pra gerar contrato.
        "nome": "Dalmóbile SJC", "cnpj": "19.152.134/0001-56", "codigo": "INS",
        "razao_social": "INSPIRIUM MOVEIS LTDA", "cnpj_fiscal": "19.152.134/0001-56",
        "telefone": "(12) 3341-8777", "email": "sac@dalmobilesjc.com.br",
        "cep": "12200-000", "logradouro": "Rua A", "numero": "100",
        "complemento": "", "bairro": "Centro", "cidade": "SJC", "estado": "SP",
        "testemunha1_nome": "Jaime Perinazzo", "testemunha1_cpf": "123.456.789-00",
        "testemunha2_nome": "Felipe Guizalberte", "testemunha2_cpf": "987.654.321-00",
    }


def test_validar_loja_completa():
    from mod_contrato import validar_loja_para_contrato
    assert validar_loja_para_contrato(_loja_completa()) == []


def test_validar_loja_complemento_opcional():
    from mod_contrato import validar_loja_para_contrato
    loja = _loja_completa(); loja["complemento"] = ""
    assert validar_loja_para_contrato(loja) == []


def test_validar_loja_cpf_placeholder_conta_como_faltando():
    from mod_contrato import validar_loja_para_contrato
    loja = _loja_completa()
    loja["testemunha1_cpf"] = "xxx.xxx.xxx-xx"
    loja["testemunha2_cpf"] = "yyy.yyy.yyy-yy"
    faltando = validar_loja_para_contrato(loja)
    j = " ".join(faltando).lower()
    assert "testemunha 1" in j and "testemunha 2" in j


def test_validar_loja_telefone_email_endereco_obrigatorios():
    from mod_contrato import validar_loja_para_contrato
    loja = _loja_completa()
    for c in ("telefone", "email", "cep", "logradouro", "numero", "bairro", "cidade", "estado"):
        loja[c] = ""
    faltando = " ".join(validar_loja_para_contrato(loja)).lower()
    for termo in ("telefone", "e-mail", "cep", "logradouro", "número", "bairro", "cidade", "estado"):
        assert termo in faltando


def test_validar_loja_vazia_acusa_tudo():
    from mod_contrato import validar_loja_para_contrato
    assert len(validar_loja_para_contrato({})) >= 13


def test_loja_dict_para_contrato_mapeia_campos():
    import main

    class _FakeLoja:
        id = 1; nome = "INSPIRIUM"; cnpj = "19.152.134/0001-56"; codigo = "INS"
        telefone = "(12) 3341-8777"; email = "sac@x.com"; cep = "12200-000"
        logradouro = "Rua A"; numero = "100"; complemento = ""; bairro = "Centro"
        cidade = "SJC"; estado = "SP"
        testemunha1_nome = "Jaime"; testemunha1_cpf = "123.456.789-00"
        testemunha1_email = "jaime@teste.com"
        testemunha2_nome = "Felipe"; testemunha2_cpf = "987.654.321-00"
        testemunha2_email = "felipe@teste.com"
        logo_arquivo = None
        loja_mae_id = None
        emitente_id = None   # sem Emitente: razao_social/cnpj_fiscal ficam vazios (LI-4b)

    class _FakeDB:
        def get(self, model, pk):
            return _FakeLoja() if pk == 1 else None

    d = main._loja_dict_para_contrato(_FakeDB(), 1)
    assert d["codigo"] == "INS"
    assert d["nome"] == "INSPIRIUM"
    assert d["testemunha1_cpf"] == "123.456.789-00"
    assert d["testemunha1_email"] == "jaime@teste.com"
    assert d["cidade"] == "SJC"
    assert d["razao_social"] == "" and d["cnpj_fiscal"] == ""


def test_loja_dict_para_contrato_razao_social_vem_do_emitente():
    """LI-4b (docs/db/LISTA_IMEDIATA.md, 25/09): razao_social/cnpj_fiscal vêm do Emitente
    PRÓPRIO da loja (`emitente_id`), não de `loja.nome`/`loja.cnpj` (Nome Fantasia)."""
    import main
    from database import Emitente

    class _FakeLoja:
        id = 1; nome = "Dalmóbile SJC"; cnpj = "48.346.497/0001-20"; codigo = "DSJ"
        telefone = "(12) 3341-8777"; email = "sac@x.com"; cep = "12200-000"
        logradouro = "Rua A"; numero = "100"; complemento = ""; bairro = "Centro"
        cidade = "SJC"; estado = "SP"
        testemunha1_nome = "Jaime"; testemunha1_cpf = "123.456.789-00"
        testemunha1_email = "jaime@teste.com"
        testemunha2_nome = "Felipe"; testemunha2_cpf = "987.654.321-00"
        testemunha2_email = "felipe@teste.com"
        logo_arquivo = None
        loja_mae_id = None
        emitente_id = 7

    class _FakeEmitente:
        id = 7; razao_social = "INSPIRIUM MOVEIS PLANEJADOS LTDA"; cnpj = "19.152.134/0001-56"

    class _FakeDB:
        def get(self, model, pk):
            if model is Emitente:
                return _FakeEmitente() if pk == 7 else None
            return _FakeLoja() if pk == 1 else None

    d = main._loja_dict_para_contrato(_FakeDB(), 1)
    assert d["nome"] == "Dalmóbile SJC"                              # Nome Fantasia, intocado
    assert d["razao_social"] == "INSPIRIUM MOVEIS PLANEJADOS LTDA"    # vem do Emitente
    assert d["cnpj_fiscal"] == "19.152.134/0001-56"                   # vem do Emitente
    assert d["cnpj"] == "48.346.497/0001-20"                          # CNPJ da loja, intocado


def test_loja_dict_para_contrato_sem_loja():
    import main
    class _FakeDB:
        def get(self, model, pk): return None
    assert main._loja_dict_para_contrato(_FakeDB(), None) == {}
    assert main._loja_dict_para_contrato(_FakeDB(), 999) == {}
