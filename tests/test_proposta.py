import os
import mod_proposta


def test_contexto_proposta_marcadores():
    cliente = {"nome": "Ana", "cpf": "111", "email": "a@x.com", "telefone": "9999",
               "logradouro": "", "numero": "", "complemento": "", "bairro": "",
               "cidade": "", "cep": "", "estado": "", "inst_mesmo_residencial": True,
               "inst_logradouro": "", "inst_numero": "", "inst_complemento": "",
               "inst_bairro": "", "inst_cidade": "", "inst_cep": "", "inst_uf": ""}
    usuario = {"nome": "Consultor X", "telefone": "", "email": ""}
    loja = {"nome": "Loja Z", "cnpj": "00.000.000/0001-00", "codigo": "LJZ"}
    orcamento_dict = {"ambientes": ["Cozinha", "Dormitório"]}
    breakdown = {"VBVO": 100000.0, "VAVO": 90000.0}
    m = mod_proposta.contexto_proposta(cliente, usuario, loja, orcamento_dict, breakdown, "")
    assert m["NOME_CLIENTE"] == "Ana"
    assert m["NOME_EMPRESA"] == "Loja Z"
    assert "Cozinha" in m["AMBIENTES_LISTA"] and "Dormitório" in m["AMBIENTES_LISTA"]
    assert m["VALOR_BRUTO"].replace(".", "").replace(",", "").startswith("R") or "100" in m["VALOR_BRUTO"]
    assert "%" in m["DESCONTO_PCT"]          # 10% (1 - 90000/100000)
    assert m["VALIDADE"]


def test_gerar_proposta_em_outdir(tmp_path):
    variaveis = {"NOME_CLIENTE": "Ana", "NOME_EMPRESA": "Loja Z", "AMBIENTES_LISTA": "Cozinha",
                 "VALOR_BRUTO": "R$ 100.000,00", "DESCONTO_PCT": "10,0%",
                 "VALOR_TOTAL": "R$ 90.000,00", "MODALIDADE": "A Vista", "VALIDADE": "Válida 10 dias."}
    caminho, eh_pdf = mod_proposta.gerar_proposta(variaveis, str(tmp_path))
    assert os.path.exists(caminho)
    # sem LibreOffice no ambiente: cai no .docx
    assert caminho.endswith(".pdf") or caminho.endswith(".docx")
    # o arquivo ficou DENTRO do outdir (não em CONTRATOS_DIR)
    assert os.path.dirname(os.path.abspath(caminho)) == os.path.abspath(str(tmp_path))
