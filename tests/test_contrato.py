import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from mod_contrato import calcular_hash_assinatura


@pytest.fixture(autouse=True)
def _isola_contratos_dir(tmp_path):
    """Isola CONTRATOS_DIR num diretório temporário para que a geração de contratos nos testes
    não escreva na pasta CONTRATOS do repositório (era a origem dos contrato_99/8888/9999.docx)."""
    import mod_contrato
    orig = mod_contrato.CONTRATOS_DIR
    mod_contrato.CONTRATOS_DIR = str(tmp_path / "contratos")
    os.makedirs(mod_contrato.CONTRATOS_DIR, exist_ok=True)
    yield
    mod_contrato.CONTRATOS_DIR = orig


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
    # Estrutura NOVA (_capturarPagamento): parcelas com valor numérico, total_cliente
    forma = json.dumps({
        "tipo": "aymore",
        "nome_forma": "Financiamento Aymoré",
        "entrada_valor": 5000.0,
        "entrada_forma": "Boleto",
        "entrada_data": "2026-07-15",
        "total_cliente": 3000.0,
        "texto_cartao": "",
        "parcelas": [
            {"num": 1, "data": "15/08/2026", "valor": 1000.0},
            {"num": 2, "data": "15/09/2026", "valor": 1000.0},
            {"num": 3, "data": "15/10/2026", "valor": 1000.0},
        ]
    })
    ctx = construir_contexto(cliente, usuario, forma, {"telefone": "(12) 3341-8777", "email": "sac@dalmobilesjc.com.br"})
    assert ctx["consultor_nome"] == "Pedro"
    assert ctx["consultor_tel"] == "(12) 3341-8777"   # fallback
    assert ctx["consultor_email"] == "pedro@loja.com"
    assert ctx["cliente_nome"] == "João Silva"
    assert ctx["inst_logradouro"] == "Rua A"           # mesmo endereço residencial
    pag = ctx["_pag"]
    assert pag["entrada_valor"] == "R$ 5.000,00"
    assert pag["valor_contrato"] == "R$ 3.000,00"
    assert pag["num_parcelas_int"] == 3
    assert pag["valores"][0] == "R$ 1.000,00"
    assert pag["datas"][0] == "15/08/2026"
    assert pag["datas"][1] == "15/09/2026"
    assert pag["datas"][3] == ""                       # parcelas além de 3 = ""
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
        "texto_cartao": "12x R$ 10.000,00", "total_cliente": 120000,
    })
    ctx = construir_contexto(cliente, usuario, forma, {"telefone": "(12) 3341-8777", "email": "sac@dalmobilesjc.com.br"})
    assert ctx["consultor_tel"] == "12988880000"
    assert ctx["consultor_email"] == "sac@dalmobilesjc.com.br"   # fallback email
    pag = ctx["_pag"]
    assert pag["num_parcelas_int"] == 0
    assert pag["texto_cartao"] == "12x R$ 10.000,00"
    assert pag["valor_contrato"] == "R$ 120.000,00"
    assert pag["datas"] == [""] * 24
    assert pag["valores"] == [""] * 24


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
        "total_cliente": 10000.0, "texto_cartao": "",
        "parcelas": [
            {"num": i, "data": f"10/{6+i:02d}/2026", "valor": 2000.0}
            for i in range(1, 6)
        ]
    })
    ctx = construir_contexto(cliente, usuario, forma, {"telefone": "(12) 3341-8777", "email": "sac@dalmobilesjc.com.br"})
    assert ctx["consultor_tel"] == "(12) 3341-8777"
    assert ctx["inst_logradouro"] == "Rua C"
    assert ctx["res_logradouro"] == "Av B"
    pag = ctx["_pag"]
    assert pag["num_parcelas_int"] == 5
    assert pag["datas"][0] == "10/07/2026"
    assert pag["datas"][4] == "10/11/2026"
    assert pag["datas"][5] == ""
    assert pag["valores"][0] == "R$ 2.000,00"


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


def test_validar_contribuinte_sem_cnpj_barra():
    """Cliente contribuinte precisa de CNPJ (CPF não substitui)."""
    from mod_contrato import validar_cliente_para_contrato
    c = _cliente_completo()
    c["tipo_dest"] = "contribuinte"
    c["cnpj"] = ""            # sem CNPJ → deve barrar
    c["cpf"] = "123.456.789-00"  # CPF preenchido não conta para contribuinte
    faltando = validar_cliente_para_contrato(c)
    joined = " ".join(faltando).lower()
    assert "cnpj" in joined
    # CPF não deve ser cobrado quando o tipo é contribuinte
    assert not any(rot.strip().lower() == "cpf" for rot in faltando)


def test_validar_isento_sem_cnpj_barra():
    """Cliente isento (indicador IE 2) também exige CNPJ."""
    from mod_contrato import validar_cliente_para_contrato
    c = _cliente_completo()
    c["tipo_dest"] = "isento"
    c["cnpj"] = ""
    faltando = validar_cliente_para_contrato(c)
    assert "cnpj" in " ".join(faltando).lower()


def test_validar_nao_contribuinte_sem_cpf_barra():
    """Não-contribuinte sem CPF barra (comportamento atual, mantido)."""
    from mod_contrato import validar_cliente_para_contrato
    c = _cliente_completo()
    c["tipo_dest"] = "nao_contribuinte"
    c["cpf"] = ""
    faltando = validar_cliente_para_contrato(c)
    assert any(rot.strip().lower() == "cpf" for rot in faltando)


def test_validar_contribuinte_com_cnpj_sem_ie_nao_barra():
    """IE não bloqueia o contrato: contribuinte com CNPJ e sem IE passa."""
    from mod_contrato import validar_cliente_para_contrato
    c = _cliente_completo()
    c["tipo_dest"] = "contribuinte"
    c["cnpj"] = "19.152.134/0001-56"
    c["inscricao_estadual"] = ""   # IE ausente não deve barrar
    assert validar_cliente_para_contrato(c) == []


def test_email_fallback_consultor():
    from mod_contrato import construir_contexto
    cliente = {"nome": "X", "cpf": "", "email": "", "telefone": "",
               "logradouro": "", "numero": "", "complemento": "", "bairro": "",
               "cidade": "", "cep": "", "estado": "",
               "inst_mesmo_residencial": True,
               "inst_logradouro": "", "inst_numero": "", "inst_complemento": "",
               "inst_bairro": "", "inst_cidade": "", "inst_cep": "", "inst_uf": ""}
    loja = {"telefone": "(12) 3341-8777", "email": "sac@dalmobilesjc.com.br"}
    ctx = construir_contexto(cliente, {"nome": "X", "telefone": "", "email": ""}, "", loja)
    assert ctx["consultor_email"] == "sac@dalmobilesjc.com.br"
    assert ctx["consultor_tel"]   == "(12) 3341-8777"


# ── Número do contrato ─────────────────────────────────────────────────────────

def test_gerar_num_contrato_formato():
    from datetime import datetime
    from mod_contrato import gerar_num_contrato
    # sigla (3 letras) + AAAAMMDD + 5 dígitos sequenciais
    n = gerar_num_contrato([], "INS", data=datetime(2026, 6, 17))
    assert n == "INS2026061700001"


def test_gerar_num_contrato_sequencia_continua():
    from datetime import datetime
    from mod_contrato import gerar_num_contrato
    existentes = ["INS2026061500001", "INS2026061600002", "ORZ2026061600009"]
    n = gerar_num_contrato(existentes, "INS", data=datetime(2026, 6, 17))
    assert n == "INS2026061700003"   # contínuo por prefixo INS (ignora ORZ)


def test_gerar_num_contrato_loja_customizada():
    from datetime import datetime
    from mod_contrato import gerar_num_contrato
    n = gerar_num_contrato([], "ORZ", data=datetime(2026, 1, 5))
    assert n == "ORZ2026010500001"


def test_gerar_num_contrato_ignora_formato_antigo():
    from datetime import datetime
    from mod_contrato import gerar_num_contrato
    # números no formato antigo (com traços) não contaminam o novo sequencial
    n = gerar_num_contrato(["INS-2026-06-15-050"], "INS", data=datetime(2026, 6, 17))
    assert n == "INS2026061700001"


def test_gerar_num_proposta_prefixo_pv():
    from datetime import datetime
    from mod_contrato import gerar_num_proposta
    assert gerar_num_proposta([], data=datetime(2026, 6, 17)) == "PV2026061700001"
    # a data é sempre a da emissão; só o SEQ continua (contínuo por 'PV')
    assert gerar_num_proposta(["PV2026061500007"], data=datetime(2026, 6, 17)) == "PV2026061700008"


def test_proposta_html_e_capa_do_contrato_com_pv():
    from mod_contrato import construir_contexto, montar_html_proposta
    cliente = {"nome": "Fulano", "cpf": "111.111.111-11", "logradouro": "Rua X",
               "numero": "10", "cidade": "São Paulo", "estado": "SP"}
    ctx = construir_contexto(cliente, {"nome": "Consultor"}, "", {"nome": "Loja", "codigo": "INS"})
    ctx["_ambientes"] = [("Cozinha", 1000.0)]
    ctx["num_contrato"] = "PV2026071000001"     # nº da proposta ocupa o marcador da capa
    html = montar_html_proposta(ctx)
    assert "PV2026071000001" in html            # numeração PV aparece
    assert "[NUM_CONTRATO]" not in html         # marcador foi substituído
    assert "Identificação do Cliente" in html   # é a capa (primeira página) do contrato
    assert "quebra-capa" not in html            # sem quebra -> uma página só
    assert "<!--CORPO-->" not in html and "Cozinha" in html


# ── Valores das parcelas ───────────────────────────────────────────────────────

def test_parse_pagamento_valores_alinhados():
    from mod_contrato import _parse_pagamento
    pag = json.dumps({
        "tipo": "aymore", "nome_forma": "Aymoré",
        "parcelas": [
            {"seq": 1, "data": "2026-07-10", "valor": "R$ 100,00"},
            {"seq": 2, "data": "2026-08-10", "valor": "R$ 200,00"},
        ],
    })
    d = _parse_pagamento(pag)
    assert d["num_parcelas_int"] == 2
    assert d["valores"][0] == "R$ 100,00"
    assert d["valores"][1] == "R$ 200,00"
    assert d["valores"][2] == ""        # preenchido até 24
    assert len(d["valores"]) == 24


def test_parse_pagamento_cartao_sem_valores():
    from mod_contrato import _parse_pagamento
    d = _parse_pagamento(json.dumps({"tipo": "cartao", "nome_forma": "Cartão"}))
    assert d["valores"] == [""] * 24
    assert d["num_parcelas_int"] == 0


def test_parse_pagamento_estrutura_real():
    import json
    from mod_contrato import _parse_pagamento
    pag = json.dumps({
        "tipo": "aymore", "nome_forma": "Financiamento Aymoré",
        "entrada_valor": 20000, "entrada_data": "2026-06-18", "entrada_forma": "pix",
        "total_cliente": 129572.01, "texto_cartao": "",
        "parcelas": [
            {"num": 1, "data": "18/07/2026", "valor": 4820.00},
            {"num": 2, "data": "17/08/2026", "valor": 4820.00},
        ],
    })
    d = _parse_pagamento(pag)
    assert d["num_parcelas_int"] == 2
    assert d["valores"][0] == "R$ 4.820,00"
    assert d["valores"][1] == "R$ 4.820,00"
    assert d["valores"][2] == ""
    assert d["datas"][0] == "18/07/2026"
    assert d["datas"][2] == ""
    assert d["valor_contrato"] == "R$ 129.572,01"
    assert len(d["valores"]) == 24 and len(d["datas"]) == 24


def test_parse_pagamento_cartao_texto():
    import json
    from mod_contrato import _parse_pagamento
    d = _parse_pagamento(json.dumps({
        "tipo": "cartao", "nome_forma": "Cartão de Crédito",
        "texto_cartao": "12x R$ 10.000,00", "total_cliente": 120000, "parcelas": []}))
    assert d["texto_cartao"] == "12x R$ 10.000,00"
    assert d["num_parcelas_int"] == 0
    assert d["valores"] == [""] * 24
    assert d["valor_contrato"] == "R$ 120.000,00"


def test_parse_pagamento_cartao_avista_num_parcelas():
    import json
    from mod_contrato import _parse_pagamento
    d = _parse_pagamento(json.dumps({"tipo": "cartao", "nome_forma": "Cartão de Crédito",
        "total_cliente": 5000, "parcelas": [{"num": 1, "valor": 5000, "data": ""}]}))
    assert d["num_parcelas"] == "à vista"
    assert d["num_parcelas_int"] == 1


def test_parse_pagamento_cartao_parcelado_num_parcelas_e_datas_vazias():
    import json
    from mod_contrato import _parse_pagamento
    d = _parse_pagamento(json.dumps({"tipo": "cartao", "nome_forma": "Cartão de Crédito",
        "total_cliente": 12000, "parcelas": [{"num": i+1, "valor": 1000, "data": ""} for i in range(12)]}))
    assert d["num_parcelas"] == "12"
    assert d["num_parcelas_int"] == 12
    assert all(x == "" for x in d["datas"][:12])   # cartão: parcelas sem data


# ── Forma de pagamento: rótulos pt-BR + forma_parcela + marcador TIPO ──────────

def test_forma_label_mapeia_codigos():
    from mod_contrato import _forma_label
    assert _forma_label("pix") == "Pix"
    assert _forma_label("ted") == "TED"
    assert _forma_label("transferencia") == "TED"
    assert _forma_label("boleto") == "Boleto"
    assert _forma_label("cheque") == "Cheque"
    assert _forma_label("dinheiro") == "Dinheiro"
    assert _forma_label("cartao_credito") == "Cartão de Crédito"
    assert _forma_label("") == ""
    assert _forma_label("Boleto") == "Boleto"   # já-rótulo passa adiante


def test_parse_pagamento_forma_parcela_de_parcelas():
    import json
    from mod_contrato import _parse_pagamento
    pag = json.dumps({
        "tipo": "venda_programada", "nome_forma": "Venda Programada",
        "entrada_valor": 1000, "entrada_forma": "pix", "total_cliente": 5000,
        "parcelas": [
            {"num": 1, "data": "10/07/2026", "valor": 2000.0, "forma": "cheque"},
            {"num": 2, "data": "10/08/2026", "valor": 2000.0, "forma": "cheque"},
        ],
    })
    d = _parse_pagamento(pag)
    assert d["entrada_tipo"] == "Pix"
    assert d["forma_parcela"] == "Cheque"


def test_parse_pagamento_forma_parcela_cartao():
    import json
    from mod_contrato import _parse_pagamento
    d = _parse_pagamento(json.dumps({
        "tipo": "cartao", "nome_forma": "Cartão de Crédito",
        "texto_cartao": "12x R$ 10.000,00", "total_cliente": 120000, "parcelas": []}))
    assert d["forma_parcela"] == "Cartão de Crédito"


def test_montar_mapping_inclui_tipo():
    from mod_contrato import _montar_mapping
    ctx = {}
    pag = {"forma_parcela": "Boleto", "entrada_tipo": "Pix", "num_parcelas": "3"}
    m = _montar_mapping(ctx, pag)
    assert m["TIPO"] == "Boleto"
    assert m["FORMA_ENTRADA"] == "Pix"


def test_montar_mapping_inclui_empresa_e_cpfs():
    from mod_contrato import _montar_mapping
    loja = {"nome": "INSPIRIUM MOVEIS LTDA", "cnpj": "19.152.134/0001-56",
            "testemunha1_nome": "Jaime", "testemunha1_cpf": "123.456.789-00",
            "testemunha2_nome": "Felipe", "testemunha2_cpf": "987.654.321-00"}
    ctx = {"cliente_cpf": "111.222.333-44", "loja": loja}
    m = _montar_mapping(ctx, {})
    assert m["NOME_EMPRESA"] == "INSPIRIUM MOVEIS LTDA"
    assert m["CNPJ_EMPRESA"] == "19.152.134/0001-56"
    assert m["CPF_CLIENTE"] == "111.222.333-44"
    assert m["CPF_TESTEMUNHA_1"] == "123.456.789-00"
    assert m["CPF_TESTEMUNHA_2"] == "987.654.321-00"
    assert m["NOME_TESTEMUNHA_1"] == "Jaime"
    assert m["NOME_TESTEMUNHA_2"] == "Felipe"


# ── Valor por ambiente no contrato (rateio do financeiro) ──────────────────────

def test_ambientes_valor_proporcional_ao_vava():
    from mod_contrato import ambientes_valor_contrato
    out = ambientes_valor_contrato([("Cozinha", 100.0), ("Sala", 300.0)],
                                   vavo=400.0, val_cont=440.0)
    assert out == [("Cozinha", 110.0), ("Sala", 330.0)]
    assert round(sum(v for _, v in out), 2) == 440.0


def test_ambientes_reconciliacao_residuo_no_ultimo():
    from mod_contrato import ambientes_valor_contrato
    out = ambientes_valor_contrato(
        [("A", 33.33), ("B", 33.33), ("C", 33.34)], vavo=100.0, val_cont=100.01)
    assert round(sum(v for _, v in out), 2) == 100.01
    # o resíduo de arredondamento cai no último ambiente
    assert out[-1][0] == "C"
    assert out[0][1] == 33.33 and out[1][1] == 33.33


def test_ambientes_sem_financeiro_valor_igual_vava():
    from mod_contrato import ambientes_valor_contrato
    out = ambientes_valor_contrato([("A", 100.0), ("B", 300.0)],
                                   vavo=400.0, val_cont=400.0)
    assert out == [("A", 100.0), ("B", 300.0)]


def test_ambientes_vavo_zero_nao_divide():
    from mod_contrato import ambientes_valor_contrato
    out = ambientes_valor_contrato([("A", 0.0), ("B", 0.0)], vavo=0.0, val_cont=0.0)
    assert out == [("A", 0.0), ("B", 0.0)]


def test_ambientes_lista_vazia():
    from mod_contrato import ambientes_valor_contrato
    assert ambientes_valor_contrato([], vavo=0.0, val_cont=0.0) == []
