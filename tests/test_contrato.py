import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch, MagicMock
from mod_contrato import calcular_hash_assinatura, montar_variaveis_contrato, gerar_pdf_contrato


def test_hash_assinatura_determinístico():
    h1 = calcular_hash_assinatura("João Silva", "123.456.789-00", 42, "2026-06-15T10:00:00")
    h2 = calcular_hash_assinatura("João Silva", "123.456.789-00", 42, "2026-06-15T10:00:00")
    assert h1 == h2


def test_hash_assinatura_muda_com_dados_diferentes():
    h1 = calcular_hash_assinatura("João Silva", "123.456.789-00", 42, "2026-06-15T10:00:00")
    h2 = calcular_hash_assinatura("Maria Silva", "123.456.789-00", 42, "2026-06-15T10:00:00")
    assert h1 != h2


def test_hash_assinatura_formato_sha256():
    h = calcular_hash_assinatura("João", "000.000.000-00", 1, "2026-01-01T00:00:00")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_montar_variaveis_contrato_campos_obrigatorios():
    variaveis = montar_variaveis_contrato(
        projeto={"nome_projeto": "Cozinha Silva", "criado_em": "2026-06-15", "consultor": "Pedro"},
        cliente={"nome": "Ana Silva", "cpf": "123.456.789-00", "telefone": "(11) 99999-9999",
                 "logradouro": "Rua A", "numero": "100", "bairro": "Centro", "cidade": "SP", "estado": "SP"},
        orcamento={"nome": "Orçamento 1", "valor_total": 48200.0, "forma_pagamento": "", "ambientes": []},
        endereco_instalacao="Rua B, 200 - Centro - SP",
        entrada_valor=5000.0,
        parcelas_descricao="11x",
        adendo="",
    )
    assert variaveis["cliente_nome"] == "Ana Silva"
    assert variaveis["cliente_cpf"]  == "123.456.789-00"
    assert variaveis["consultor_nome"] == "Pedro"
    assert variaveis["adendo"] == ""


def test_montar_variaveis_sem_adendo_retorna_string_vazia():
    variaveis = montar_variaveis_contrato(
        projeto={"nome_projeto": "P", "criado_em": "2026-01-01", "consultor": "X"},
        cliente={"nome": "C", "cpf": "", "telefone": "", "logradouro": "",
                 "numero": "", "bairro": "", "cidade": "", "estado": ""},
        orcamento={"nome": "O", "valor_total": 0.0, "forma_pagamento": "", "ambientes": []},
        endereco_instalacao="", entrada_valor=0.0, parcelas_descricao="", adendo=None,
    )
    assert variaveis["adendo"] == ""


def test_gerar_pdf_usa_modelo_e_chama_libreoffice(tmp_path):
    from mod_contrato import construir_contexto, _MODELO
    # Cria um modelo fake se não existir no ambiente de teste
    if not os.path.exists(_MODELO):
        pytest_mark = "skip"
        return  # pula se não há modelo no ambiente de CI
    ctx = construir_contexto(
        cliente={"nome": "Teste", "cpf": "000", "email": "", "telefone": "",
                 "logradouro": "", "numero": "", "complemento": "", "bairro": "",
                 "cidade": "", "cep": "", "estado": "",
                 "inst_mesmo_residencial": True,
                 "inst_logradouro": "", "inst_numero": "", "inst_complemento": "",
                 "inst_bairro": "", "inst_cidade": "", "inst_cep": "", "inst_uf": ""},
        usuario={"nome": "Consultor X", "telefone": "", "email": ""},
        forma_pagamento_json="",
    )
    with patch("mod_contrato.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = gerar_pdf_contrato(contrato_id=99, variaveis=ctx)
    assert "99" in result
    mock_run.assert_called_once()
    run_args = mock_run.call_args[0][0]
    assert "--convert-to" in run_args


def test_construir_contexto_aymore():
    from mod_contrato import construir_contexto
    cliente = {
        "nome": "João Silva", "cpf": "123.456.789-00",
        "email": "joao@test.com", "telefone": "12999990000",
        "logradouro": "Rua A", "numero": "10", "complemento": "",
        "bairro": "Centro", "cidade": "SJC", "cep": "12200-000", "estado": "SP",
        "inst_mesmo_residencial": True,
        "inst_logradouro": "", "inst_numero": "", "inst_complemento": "",
        "inst_bairro": "", "inst_cidade": "", "inst_cep": "", "inst_uf": "",
    }
    usuario = {"nome": "Pedro", "telefone": None, "email": "pedro@loja.com"}
    # Formato _capturarPagamento (datas já em DD/MM/YYYY)
    forma = json.dumps({
        "tipo": "aymore",
        "nome_forma": "Financiamento Aymoré",
        "entrada_valor": 5000.0,
        "entrada_forma": "Boleto",
        "entrada_data": "2026-07-15",
        "parcelas": [
            {"seq": 1, "descricao": "Parcela 01", "data": "15/08/2026", "valor": "R$ 1.000,00", "forma": "Boleto"},
            {"seq": 2, "descricao": "Parcela 02", "data": "15/09/2026", "valor": "R$ 1.000,00", "forma": "Boleto"},
            {"seq": 3, "descricao": "Parcela 03", "data": "15/10/2026", "valor": "R$ 1.000,00", "forma": "Boleto"},
        ]
    })
    ctx = construir_contexto(cliente, usuario, forma)
    assert ctx["consultor_nome"] == "Pedro"
    assert ctx["consultor_tel"] == "(12) 3341-8777"   # fallback
    assert ctx["consultor_email"] == "pedro@loja.com"
    assert ctx["cliente_nome"] == "João Silva"
    assert ctx["inst_logradouro"] == "Rua A"           # mesmo endereço residencial
    assert ctx["pgto_entrada_valor"] == "R$ 5.000,00"
    assert ctx["p01_data"] == "15/08/2026"
    assert ctx["p02_data"] == "15/09/2026"
    assert ctx["p04_data"] == "—"                      # parcelas além de 3 = "—"
    assert "data_contrato" in ctx


def test_construir_contexto_cartao():
    from mod_contrato import construir_contexto
    cliente = {
        "nome": "Ana", "cpf": "", "email": "", "telefone": "",
        "logradouro": "", "numero": "", "complemento": "", "bairro": "",
        "cidade": "", "cep": "", "estado": "",
        "inst_mesmo_residencial": True,
        "inst_logradouro": "", "inst_numero": "", "inst_complemento": "",
        "inst_bairro": "", "inst_cidade": "", "inst_cep": "", "inst_uf": "",
    }
    usuario = {"nome": "Luiz", "telefone": "12988880000", "email": ""}
    forma = json.dumps({
        "tipo": "cartao", "nome_forma": "Cartão de Crédito",
        "entrada_valor": 0, "entrada_data": "", "parcelas": [],
    })
    ctx = construir_contexto(cliente, usuario, forma)
    assert ctx["consultor_tel"] == "12988880000"
    assert ctx["consultor_email"] == "sac@dalmobilesjc.com.br"   # fallback email
    assert ctx["p01_data"] == "—"
    assert ctx["p12_data"] == "—"
    assert ctx["p24_data"] == "—"


def test_construir_contexto_total_flex():
    from mod_contrato import construir_contexto
    cliente = {
        "nome": "Carlos", "cpf": "", "email": "", "telefone": "",
        "logradouro": "Av B", "numero": "5", "complemento": "", "bairro": "Vila",
        "cidade": "SP", "cep": "01000-000", "estado": "SP",
        "inst_mesmo_residencial": False,
        "inst_logradouro": "Rua C", "inst_numero": "20", "inst_complemento": "Ap 1",
        "inst_bairro": "Jardim", "inst_cidade": "SP", "inst_cep": "02000-000", "inst_uf": "SP",
    }
    usuario = {"nome": "Marcia", "telefone": "", "email": ""}
    forma = json.dumps({
        "tipo": "tf", "nome_forma": "Total Flex",
        "entrada_valor": 3000.0, "entrada_data": "01/07/2026",
        "parcelas": [
            {"seq": i, "descricao": f"Parcela {i:02d}", "data": f"10/{6+i:02d}/2026",
             "valor": "R$ 2.000,00", "forma": "Boleto"}
            for i in range(1, 6)
        ]
    })
    ctx = construir_contexto(cliente, usuario, forma)
    assert ctx["consultor_tel"] == "(12) 3341-8777"
    assert ctx["inst_logradouro"] == "Rua C"
    assert ctx["res_logradouro"] == "Av B"
    assert ctx["p01_data"] == "10/07/2026"
    assert ctx["p05_data"] == "10/11/2026"
    assert ctx["p06_data"] == "—"


def _cliente_completo():
    """Cliente com todos os campos obrigatórios para gerar contrato."""
    return {
        "nome": "Ana Silva", "cpf": "123.456.789-00",
        "email": "ana@test.com", "telefone": "(12) 99999-0000",
        "logradouro": "Rua A", "numero": "100", "complemento": "",
        "bairro": "Centro", "cidade": "SJC", "cep": "12200-000", "estado": "SP",
        "inst_mesmo_residencial": True,
        "inst_logradouro": "", "inst_numero": "", "inst_complemento": "",
        "inst_bairro": "", "inst_cidade": "", "inst_cep": "", "inst_uf": "",
    }


def test_validar_cliente_completo_sem_faltas():
    from mod_contrato import validar_cliente_para_contrato
    assert validar_cliente_para_contrato(_cliente_completo()) == []


def test_validar_cliente_sem_endereco_residencial():
    from mod_contrato import validar_cliente_para_contrato
    c = _cliente_completo()
    for campo in ("logradouro", "numero", "bairro", "cidade", "cep", "estado"):
        c[campo] = ""
    faltando = validar_cliente_para_contrato(c)
    # Todos os 6 campos residenciais devem ser apontados como faltando
    assert len(faltando) == 6
    joined = " ".join(faltando).lower()
    for termo in ("logradouro", "número", "bairro", "cidade", "cep", "estado"):
        assert termo in joined


def test_validar_cliente_sem_contato():
    from mod_contrato import validar_cliente_para_contrato
    c = _cliente_completo()
    c["email"] = ""
    c["telefone"] = None
    faltando = validar_cliente_para_contrato(c)
    joined = " ".join(faltando).lower()
    assert "e-mail" in joined
    assert "telefone" in joined


def test_validar_inst_diferente_exige_endereco_instalacao():
    from mod_contrato import validar_cliente_para_contrato
    c = _cliente_completo()
    c["inst_mesmo_residencial"] = False
    # inst_* vazios → devem ser cobrados
    faltando = validar_cliente_para_contrato(c)
    joined = " ".join(faltando).lower()
    assert "instalação" in joined
    # Preenchendo inst_* → sem faltas
    c.update({"inst_logradouro": "Rua C", "inst_numero": "20", "inst_bairro": "Jardim",
              "inst_cidade": "SP", "inst_cep": "02000-000", "inst_uf": "SP"})
    assert validar_cliente_para_contrato(c) == []


def test_validar_inst_mesma_nao_exige_inst_fields():
    from mod_contrato import validar_cliente_para_contrato
    c = _cliente_completo()  # inst_mesmo_residencial=True, inst_* vazios
    assert validar_cliente_para_contrato(c) == []


def test_email_fallback_consultor():
    from mod_contrato import construir_contexto
    cliente = {"nome": "X", "cpf": "", "email": "", "telefone": "",
               "logradouro": "", "numero": "", "complemento": "", "bairro": "",
               "cidade": "", "cep": "", "estado": "",
               "inst_mesmo_residencial": True,
               "inst_logradouro": "", "inst_numero": "", "inst_complemento": "",
               "inst_bairro": "", "inst_cidade": "", "inst_cep": "", "inst_uf": ""}
    ctx = construir_contexto(cliente, {"nome": "X", "telefone": "", "email": ""}, "")
    assert ctx["consultor_email"] == "sac@dalmobilesjc.com.br"
    assert ctx["consultor_tel"]   == "(12) 3341-8777"


def test_preencher_signatario_e_testemunhas(tmp_path):
    import os
    from mod_contrato import preencher_contrato, _MODELO, construir_contexto
    if not os.path.exists(_MODELO):
        return
    from docx import Document
    ctx = construir_contexto(
        cliente={"nome": "Ana Cliente", "cpf": "111.222.333-44", "email": "a@x.com",
                 "telefone": "(12) 9", "logradouro": "Rua A", "numero": "1", "complemento": "",
                 "bairro": "Centro", "cidade": "SJC", "cep": "12000", "estado": "SP",
                 "inst_mesmo_residencial": True, "inst_logradouro": "", "inst_numero": "",
                 "inst_complemento": "", "inst_bairro": "", "inst_cidade": "", "inst_cep": "", "inst_uf": ""},
        usuario={"nome": "Consultor Z", "telefone": "", "email": ""},
        forma_pagamento_json="",
    )
    path = preencher_contrato(91001, ctx)
    full = "\n".join(p.text for p in Document(path).paragraphs)
    os.remove(path)
    assert "Ana Cliente CPF/CNPJ:" in full   # cliente é o 2º signatário (par. 128)
    assert "Consultor Z" in full             # consultor PERMANECE no cabeçalho (par. 0)
    assert "Jaime Perinazzo" in full
    assert "Felipe Guizalberte" in full
