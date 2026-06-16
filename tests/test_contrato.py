import sys, os
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
    projeto = {
        "nome_projeto": "Cozinha Silva",
        "criado_em": "2026-06-15",
        "consultor": "Pedro",
    }
    cliente = {
        "nome": "Ana Silva",
        "cpf": "123.456.789-00",
        "telefone": "(11) 99999-9999",
        "logradouro": "Rua A",
        "numero": "100",
        "bairro": "Centro",
        "cidade": "SP",
        "estado": "SP",
    }
    orcamento = {
        "nome": "Orçamento 1",
        "valor_total": 48200.0,
        "forma_pagamento": "Boleto 12x",
        "ambientes": ["Cozinha", "Sala"],
    }
    variaveis = montar_variaveis_contrato(
        projeto=projeto,
        cliente=cliente,
        orcamento=orcamento,
        endereco_instalacao="Rua B, 200 - Centro - SP",
        entrada_valor=5000.0,
        parcelas_descricao="11x de R$ 3.927,27",
        adendo="",
    )
    assert variaveis["cliente_nome"] == "Ana Silva"
    assert variaveis["cliente_cpf"] == "123.456.789-00"
    assert variaveis["projeto_nome"] == "Cozinha Silva"
    assert variaveis["orcamento_nome"] == "Orçamento 1"
    assert "R$ 48.200,00" in variaveis["valor_total"]
    assert variaveis["endereco_instalacao"] == "Rua B, 200 - Centro - SP"
    assert variaveis["ambientes_lista"] == "Cozinha\nSala"
    assert variaveis["adendo"] == ""


def test_montar_variaveis_sem_adendo_retorna_string_vazia():
    variaveis = montar_variaveis_contrato(
        projeto={"nome_projeto": "P", "criado_em": "2026-01-01", "consultor": "X"},
        cliente={"nome": "C", "cpf": "", "telefone": "", "logradouro": "",
                 "numero": "", "bairro": "", "cidade": "", "estado": ""},
        orcamento={"nome": "O", "valor_total": 0.0, "forma_pagamento": "", "ambientes": []},
        endereco_instalacao="",
        entrada_valor=0.0,
        parcelas_descricao="",
        adendo=None,
    )
    assert variaveis["adendo"] == ""


def test_gerar_pdf_chama_libreoffice():
    variaveis = {
        "cliente_nome": "Teste", "cliente_cpf": "000", "cliente_endereco": "",
        "cliente_telefone": "", "endereco_instalacao": "", "projeto_nome": "P",
        "projeto_data": "2026-01-01", "orcamento_nome": "O1", "valor_total": "R$ 0,00",
        "forma_pagamento": "", "entrada_valor": "R$ 0,00", "parcelas_descricao": "",
        "ambientes_lista": "", "consultor_nome": "X", "data_contrato": "15/06/2026",
        "adendo": "",
    }
    with patch("mod_contrato.DocxTemplate") as mock_tpl, \
         patch("mod_contrato.subprocess.run") as mock_run, \
         patch("mod_contrato.os.path.exists", return_value=True):
        mock_doc = MagicMock()
        mock_tpl.return_value = mock_doc
        mock_run.return_value = MagicMock(returncode=0)

        resultado = gerar_pdf_contrato(contrato_id=99, variaveis=variaveis)

    mock_doc.render.assert_called_once_with(variaveis)
    saved_path = mock_doc.save.call_args[0][0]
    assert saved_path.endswith(os.path.join("CONTRATOS", "contrato_99.docx"))
    run_args = mock_run.call_args[0][0]
    assert "--convert-to" in run_args
    assert "pdf" in run_args
    assert "99" in resultado


def test_construir_contexto_aymore():
    from mod_contrato import construir_contexto
    import json
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
    forma = json.dumps({
        "tipo": "aymore",
        "nome_forma": "Financiamento Aymoré",
        "entrada_valor": 5000.0,
        "entrada_tipo": "Boleto",
        "entrada_data": "2026-07-15",
        "num_parcelas": 3,
        "data_primeira_parcela": "2026-08-15",
        "parcelas": [
            {"numero": 1, "data": "2026-08-15", "valor": 1000.0},
            {"numero": 2, "data": "2026-09-15", "valor": 1000.0},
            {"numero": 3, "data": "2026-10-15", "valor": 1000.0}
        ]
    })
    ctx = construir_contexto(cliente, usuario, forma)
    assert ctx["consultor_nome"] == "Pedro"
    assert ctx["consultor_tel"] == "(12) 3341-8777"  # fallback
    assert ctx["cliente_nome"] == "João Silva"
    assert ctx["inst_logradouro"] == "Rua A"          # mesmo endereço residencial
    assert ctx["pgto_entrada_valor"] == "R$ 5.000,00"
    assert ctx["p01_data"] == "15/08/2026"
    assert ctx["p02_data"] == "15/09/2026"
    assert ctx["p04_data"] == "—"                     # parcelas além de 3 = "—"
    assert "data_contrato" in ctx


def test_construir_contexto_cartao():
    from mod_contrato import construir_contexto
    import json
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
        "tipo": "cartao",
        "nome_forma": "Cartão de Crédito",
        "entrada_valor": 0,
        "entrada_tipo": "",
        "entrada_data": "",
        "num_parcelas": 12,
        "data_primeira_parcela": ""
    })
    ctx = construir_contexto(cliente, usuario, forma)
    assert ctx["consultor_tel"] == "12988880000"       # sem fallback, tem telefone
    assert ctx["p01_data"] == "—"
    assert ctx["p12_data"] == "—"
    assert ctx["p24_data"] == "—"


def test_construir_contexto_total_flex():
    from mod_contrato import construir_contexto
    import json
    cliente = {
        "nome": "Carlos", "cpf": "", "email": "", "telefone": "",
        "logradouro": "Av B", "numero": "5", "complemento": "", "bairro": "Vila",
        "cidade": "SP", "cep": "01000-000", "estado": "SP",
        "inst_mesmo_residencial": False,
        "inst_logradouro": "Rua C", "inst_numero": "20", "inst_complemento": "Ap 1",
        "inst_bairro": "Jardim", "inst_cidade": "SP", "inst_cep": "02000-000", "inst_uf": "SP",
    }
    usuario = {"nome": "Marcia", "telefone": "", "email": ""}
    parcelas_tf = [
        {"numero": i, "data": f"2026-{(6+i):02d}-10", "valor": 2000.0}
        for i in range(1, 6)
    ]
    forma = json.dumps({
        "tipo": "total_flex",
        "nome_forma": "Total Flex",
        "entrada_valor": 3000.0,
        "entrada_tipo": "Pix",
        "entrada_data": "2026-07-01",
        "num_parcelas": 5,
        "data_primeira_parcela": "",
        "parcelas": parcelas_tf
    })
    ctx = construir_contexto(cliente, usuario, forma)
    assert ctx["consultor_tel"] == "(12) 3341-8777"   # fallback (vazio)
    assert ctx["inst_logradouro"] == "Rua C"           # endereço diferente
    assert ctx["res_logradouro"] == "Av B"
    assert ctx["p01_data"] == "10/07/2026"
    assert ctx["p05_data"] == "10/11/2026"
    assert ctx["p06_data"] == "—"                      # só 5 parcelas
