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
    ctx = construir_contexto(cliente, usuario, forma)
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
    ctx = construir_contexto(cliente, usuario, forma)
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
    ctx = construir_contexto(cliente, usuario, forma)
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


# NOTA: testes removidos nesta tarefa (comportamento intencionalmente eliminado,
# agora responsabilidade do modelo modelo_contrato_mapeado.docx):
#   - test_contrato_cpf_vira_cpf_cnpj: o relabel "CPF"->"CPF/CNPJ" era feito em
#     codigo (_relabel_cpf_cnpj, removido); o modelo ja traz "CPF/CNPJ" no texto.
#   - test_contrato_tags_nomenclatura: os rotulos cinza Pt-7 (_set_cell rotulo=)
#     foram removidos; o modelo ja contem os rotulos fixos das celulas.


def test_geracao_completa_sem_marcadores_remanescentes():
    import os, json, re
    from docx import Document
    from docx.oxml.ns import qn
    from mod_contrato import preencher_contrato, construir_contexto
    ctx = construir_contexto(
        cliente={"nome": "Ana Cliente", "cpf": "111.222.333-44", "email": "a@x.com",
                 "telefone": "(12) 90000-0000", "logradouro": "Rua A", "numero": "10",
                 "complemento": "ap 1", "bairro": "Centro", "cidade": "SJC", "cep": "12000-000",
                 "estado": "SP", "inst_mesmo_residencial": True, "inst_logradouro": "",
                 "inst_numero": "", "inst_complemento": "", "inst_bairro": "", "inst_cidade": "",
                 "inst_cep": "", "inst_uf": ""},
        usuario={"nome": "Consultor Z", "telefone": "(12) 91111-1111", "email": "z@x.com"},
        forma_pagamento_json=json.dumps({
            "tipo": "aymore", "nome_forma": "Financiamento Aymoré",
            "entrada_valor": 20000, "entrada_data": "2026-06-18", "entrada_forma": "pix",
            "total_cliente": 129572.01, "texto_cartao": "",
            "parcelas": [{"num": i+1, "data": f"18/{7+i:02d}/2026", "valor": 4820.0} for i in range(3)]}))
    ctx["num_contrato"]  = "INS-2026-06-17-009"
    ctx["data_contrato"] = "17/06/2026"
    path = preencher_contrato(92001, ctx)
    doc = Document(path)
    blob = "\n".join(p.text for p in doc.paragraphs)
    for t in doc.tables:
        for row in t.rows:
            for c in row.cells:
                blob += "\n" + c.text
    for sec in doc.sections:
        for h in (sec.header,):
            blob += "\n" + "\n".join(tt.text or "" for tt in h._element.iter(qn('w:t')))
    os.remove(path)
    sobra = re.findall(r'\[[A-Za-z0-9_ ]+\]', blob)
    assert sobra == [], f"marcadores não substituídos: {sobra}"
    assert "Ana Cliente" in blob
    assert "INS-2026-06-17-009" in blob and "17/06/2026" in blob
    assert "R$ 129.572,01" in blob
    assert "R$ 4.820,00" in blob
    assert "Jaime Perinazzo" in blob and "Felipe Guizalberte" in blob


# ── Número do contrato ─────────────────────────────────────────────────────────

def test_gerar_num_contrato_formato():
    from datetime import datetime
    from mod_contrato import gerar_num_contrato
    n = gerar_num_contrato([], data=datetime(2026, 6, 17))
    assert n == "INS-2026-06-17-001"


def test_gerar_num_contrato_sequencia_continua():
    from datetime import datetime
    from mod_contrato import gerar_num_contrato
    existentes = ["INS-2026-06-15-001", "INS-2026-06-16-002", "ORZ-2026-06-16-009"]
    # máximo da loja INS é 002 → próximo 003 (sequência contínua, ignora outra loja)
    n = gerar_num_contrato(existentes, data=datetime(2026, 6, 17))
    assert n == "INS-2026-06-17-003"


def test_gerar_num_contrato_loja_customizada():
    from datetime import datetime
    from mod_contrato import gerar_num_contrato
    n = gerar_num_contrato([], loja="ORZ", data=datetime(2026, 1, 5))
    assert n == "ORZ-2026-01-05-001"


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


# ── Grade de parcelas: ordinais, valores, traços, linhas removidas ─────────────

def _ctx_parcelas(n):
    from mod_contrato import construir_contexto
    parcelas = [{"seq": i + 1, "data": f"2026-{7+i:02d}-10", "valor": f"R$ {i+1}00,00"}
                for i in range(n)]
    return construir_contexto(
        cliente={"nome": "Ana", "cpf": "1", "email": "a@x.com", "telefone": "(12)9",
                 "logradouro": "Rua A", "numero": "10", "complemento": "", "bairro": "Centro",
                 "cidade": "SJC", "cep": "12000", "estado": "SP", "inst_mesmo_residencial": True,
                 "inst_logradouro": "", "inst_numero": "", "inst_complemento": "",
                 "inst_bairro": "", "inst_cidade": "", "inst_cep": "", "inst_uf": ""},
        usuario={"nome": "Y", "telefone": "", "email": ""},
        forma_pagamento_json=json.dumps({"tipo": "aymore", "nome_forma": "Aymoré",
                                          "parcelas": parcelas}))


# NOTA: testes removidos nesta tarefa (comportamento intencionalmente eliminado):
#   - test_grade_ordinais_valores_tracos_e_linhas_removidas: a grade nao usa mais
#     ordinais ("Nª") e nao remove linhas; _preencher_grade preenche por posicao
#     (valor+data, _TRACO nos slots vazios) preservando as 11 linhas da tabela.
#   - test_grade_a_vista_remove_todas_as_linhas: idem; linhas nao sao mais removidas.
#     Cobertura atual: test_preencher_grade_* e test_geracao_completa_*.


# ── Cabeçalho: num_contrato e data_contrato ───────────────────────────────────

def test_cabecalho_num_contrato_substituido():
    import os
    from mod_contrato import preencher_contrato, _MODELO
    if not os.path.exists(_MODELO):
        return
    from docx import Document
    from docx.oxml.ns import qn
    ctx = _ctx_parcelas(2)
    ctx["num_contrato"]  = "INS-2026-06-17-007"
    ctx["data_contrato"] = "17/06/2026"
    path = preencher_contrato(91006, ctx)
    doc = Document(path)
    hdr_text = []
    for sec in doc.sections:
        for h in (sec.header, sec.first_page_header, sec.even_page_header):
            hdr_text += [t.text for t in h._element.iter(qn('w:t')) if t.text]
    os.remove(path)
    blob = " ".join(hdr_text)
    assert "INS-2026-06-17-007" in blob
    assert "17/06/2026" in blob
    assert "[Num_Contrato]" not in blob
    assert "Data_contrato" not in blob


def test_template_oficial_tem_marcadores():
    import os
    from docx import Document
    from mod_contrato import _MODELO
    assert os.path.basename(_MODELO) == "modelo_contrato_mapeado.docx"
    assert os.path.exists(_MODELO)
    d = Document(_MODELO)
    blob = "\n".join(p.text for p in d.paragraphs)
    for t in d.tables:
        for row in t.rows:
            for c in row.cells:
                blob += "\n" + c.text
    assert "[NOME_CLIENTE]" in blob
    assert "[TOTAL_CONTRATO]" in blob
    assert "[DATA_PARCELA_1]" in blob
    assert "[VALOR_PARCELA]" in blob


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


def test_substituir_marcadores_basico():
    from docx import Document
    from mod_contrato import _substituir_marcadores
    d = Document()
    d.add_paragraph("Cliente: [NOME_CLIENTE] CPF/CNPJ: [CPF]")
    d.add_paragraph("Desconhecido: [NAO_EXISTE]")
    _substituir_marcadores(d, {"NOME_CLIENTE": "Ana Lima", "CPF": "111.222.333-44"})
    txt = "\n".join(p.text for p in d.paragraphs)
    assert "Cliente: Ana Lima CPF/CNPJ: 111.222.333-44" in txt
    assert "[NAO_EXISTE]" in txt          # desconhecido permanece


def test_substituir_marcadores_case_e_duplo_colchete():
    from docx import Document
    from mod_contrato import _substituir_marcadores
    d = Document()
    d.add_paragraph("N: [Num_Contrato]  D: [[Data_contrato]")
    _substituir_marcadores(d, {"NUM_CONTRATO": "INS-2026-06-17-001", "DATA_CONTRATO": "17/06/2026"})
    txt = d.paragraphs[0].text
    assert "INS-2026-06-17-001" in txt and "17/06/2026" in txt
    assert "[" not in txt


def test_substituir_marcadores_em_tabela():
    from docx import Document
    from mod_contrato import _substituir_marcadores
    d = Document()
    t = d.add_table(rows=1, cols=1)
    t.rows[0].cells[0].paragraphs[0].add_run("Nome\n[NOME_CLIENTE]")
    _substituir_marcadores(d, {"NOME_CLIENTE": "Bia"})
    assert "Bia" in t.rows[0].cells[0].text
    assert "[NOME_CLIENTE]" not in t.rows[0].cells[0].text


# ── Grade de parcelas por posição (valor+data, traços, cartão) ─────────────────

def test_preencher_grade_valores_datas_e_tracos():
    from docx import Document
    from mod_contrato import _MODELO, _preencher_grade, _TRACO
    d = Document(_MODELO)
    pag = {"tipo": "aymore", "num_parcelas_int": 2,
           "valores": ["R$ 4.820,00", "R$ 4.820,00"] + [""] * 22,
           "datas":   ["18/07/2026", "17/08/2026"] + [""] * 22,
           "texto_cartao": ""}
    _preencher_grade(d, pag)
    t3 = d.tables[3]
    blob = " ".join(c.text for row in t3.rows for c in row.cells)
    assert "R$ 4.820,00" in blob
    assert "18/07/2026" in blob and "17/08/2026" in blob
    assert _TRACO in blob
    assert "[VALOR_PARCELA]" not in blob
    assert "[DATA_PARCELA_3]" not in blob
    assert len(t3.rows) == 11


def test_preencher_grade_cartao_primeiro_campo():
    from docx import Document
    from mod_contrato import _MODELO, _preencher_grade, _TRACO
    d = Document(_MODELO)
    _preencher_grade(d, {"tipo": "cartao", "num_parcelas_int": 0,
                         "valores": [""] * 24, "datas": [""] * 24,
                         "texto_cartao": "12x R$ 10.000,00"})
    t3 = d.tables[3]
    c0 = t3.rows[3].cells[0].text
    blob = " ".join(c.text for row in t3.rows for c in row.cells)
    assert "12x R$ 10.000,00" in c0
    assert _TRACO in blob


def test_protegido_tem_documentprotection_e_regioes():
    import json, os
    from docx import Document
    from docx.oxml.ns import qn
    from mod_contrato import preencher_contrato, construir_contexto
    ctx = construir_contexto(
        cliente={"nome":"Ana","cpf":"111","email":"a@x.com","telefone":"(12)9","logradouro":"R",
                 "numero":"1","complemento":"","bairro":"C","cidade":"SJC","cep":"1","estado":"SP",
                 "inst_mesmo_residencial":True,"inst_logradouro":"","inst_numero":"","inst_complemento":"",
                 "inst_bairro":"","inst_cidade":"","inst_cep":"","inst_uf":""},
        usuario={"nome":"Z","telefone":"","email":""},
        forma_pagamento_json=json.dumps({"tipo":"aymore","nome_forma":"Aymoré","total_cliente":1000,
            "texto_cartao":"","parcelas":[{"num":1,"data":"18/07/2026","valor":500.0}]}))
    ctx["num_contrato"]="INS-1"; ctx["data_contrato"]="18/06/2026"
    p = preencher_contrato(97001, ctx, protegido=True)
    d = Document(p)
    prot = d.settings.element.find(qn('w:documentProtection'))
    body_xml = d.element.body.xml
    os.remove(p)
    assert prot is not None and prot.get(qn('w:edit')) == "readOnly"
    assert "permStart" in body_xml and "permEnd" in body_xml
    assert "Ana" in body_xml

def test_nao_protegido_sem_documentprotection():
    import json, os
    from docx import Document
    from docx.oxml.ns import qn
    from mod_contrato import preencher_contrato, construir_contexto
    ctx = construir_contexto(
        cliente={"nome":"Ana","cpf":"1","email":"","telefone":"","logradouro":"","numero":"",
                 "complemento":"","bairro":"","cidade":"","cep":"","estado":"","inst_mesmo_residencial":True,
                 "inst_logradouro":"","inst_numero":"","inst_complemento":"","inst_bairro":"",
                 "inst_cidade":"","inst_cep":"","inst_uf":""},
        usuario={"nome":"Z","telefone":"","email":""},
        forma_pagamento_json=json.dumps({"tipo":"aymore","nome_forma":"Aymoré","total_cliente":0,
            "texto_cartao":"","parcelas":[]}))
    p = preencher_contrato(97002, ctx, protegido=False)
    d = Document(p)
    has = d.settings.element.find(qn('w:documentProtection')) is not None
    body = d.element.body.xml
    os.remove(p)
    assert has is False
    assert "permStart" not in body

def test_protegido_mantem_texto_e_valores():
    # proteção não altera o conteúdo: mesmos valores que protegido=False
    import json, os, re
    from docx import Document
    from docx.oxml.ns import qn
    from mod_contrato import preencher_contrato, construir_contexto
    def gen(protegido):
        ctx = construir_contexto(
            cliente={"nome":"Ana Cliente","cpf":"111.222.333-44","email":"a@x.com","telefone":"(12)9",
                     "logradouro":"Rua A","numero":"10","complemento":"","bairro":"Centro","cidade":"SJC",
                     "cep":"12000","estado":"SP","inst_mesmo_residencial":True,"inst_logradouro":"",
                     "inst_numero":"","inst_complemento":"","inst_bairro":"","inst_cidade":"","inst_cep":"","inst_uf":""},
            usuario={"nome":"Z","telefone":"(12)9","email":"z@x.com"},
            forma_pagamento_json=json.dumps({"tipo":"aymore","nome_forma":"Aymoré","total_cliente":129572.01,
                "texto_cartao":"","parcelas":[{"num":i+1,"data":f"18/{7+i:02d}/2026","valor":4820.0} for i in range(3)]}))
        ctx["num_contrato"]="INS-9"; ctx["data_contrato"]="18/06/2026"
        p = preencher_contrato(97003, ctx, protegido=protegido)
        d = Document(p)
        blob = "\n".join(par.text for par in d.paragraphs)
        for t in d.tables:
            for row in t.rows:
                for c in row.cells: blob += "\n"+c.text
        os.remove(p)
        return blob
    a = gen(True); b = gen(False)
    assert "Ana Cliente" in a and "R$ 4.820,00" in a and "R$ 129.572,01" in a
    assert sorted(re.findall(r'\[[A-Za-z0-9_ ]+\]', a)) == []   # nenhum marcador sobra
    assert a == b   # proteção não muda o texto


def test_converter_pdf_nao_regenera_docx(monkeypatch):
    import mod_contrato
    chamou = {"preencher": False, "convert_path": None}
    monkeypatch.setattr(mod_contrato, "preencher_contrato",
                        lambda *a, **k: chamou.__setitem__("preencher", True) or "X")
    def fake_run(cmd, **kw):
        chamou["convert_path"] = cmd[-1]
        class R: pass
        return R()
    monkeypatch.setattr(mod_contrato.subprocess, "run", fake_run)
    out = mod_contrato._converter_pdf("/tmp/contrato_5.docx")
    assert chamou["preencher"] is False
    assert chamou["convert_path"] == "/tmp/contrato_5.docx"
    assert out.endswith("contrato_5.pdf")


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
