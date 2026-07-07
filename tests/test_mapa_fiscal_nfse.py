import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from types import SimpleNamespace
import mapa_fiscal as mp


def _emit(**kw):
    base = dict(cnpj="19.152.134/0001-56", razao_social="LOJA X LTDA",
                inscricao_municipal="123456", municipio_ibge="3549904",
                cnae_servico="4330404", cod_servico_municipio="1401",
                aliquota_iss=5.0, retencao_json=None,
                logradouro="Rua A", numero="1", bairro="Centro",
                cidade="Sao Jose dos Campos", uf="SP", cep="12000-000")
    base.update(kw)
    return SimpleNamespace(**base)


def _cli(tipo="nao_contribuinte", **kw):
    base = dict(nome="Cliente Y", tipo_dest=tipo, cpf="111.444.777-35",
                cnpj="11.222.333/0001-44", inscricao_estadual="ISE123",
                logradouro="Rua B", numero="2", bairro="Jd",
                cidade="Rio", estado="RJ", cep="20000-000")
    base.update(kw)
    return SimpleNamespace(**base)


def test_montar_nota_nfse():
    emit = _emit()
    nota = mp.montar_nota_nfse(emit, _cli(), valor_servico=500.0, ref="NFSE-P1",
                               data_emissao="2026-07-06T10:00:00-03:00",
                               discriminacao="Montagem de moveis planejados")
    assert nota["ref"] == "NFSE-P1"
    assert nota["data_emissao"] == "2026-07-06T10:00:00-03:00"
    # prestador (do Emitente), docs só-dígitos
    pr = nota["prestador"]
    assert pr["cnpj"] == "19152134000156"
    assert pr["inscricao_municipal"] == "123456"
    assert pr["codigo_municipio"] == "3549904"
    assert pr["razao_social"] == "LOJA X LTDA"
    # tomador (do cliente via _dest_fiscal) — nao_contribuinte -> cpf
    to = nota["tomador"]
    assert to["doc_tipo"] == "cpf" and to["doc"] == "11144477735"
    assert to["razao_social"] == "Cliente Y"
    assert to["cep"] == "20000000"
    # servico
    sv = nota["servico"]
    assert sv["valor_servicos"] == 500.0
    assert sv["aliquota"] == 5.0
    assert sv["discriminacao"] == "Montagem de moveis planejados"
    assert sv["iss_retido"] is False
    assert sv["item_lista_servico"] == "1401"
    assert sv["codigo_tributario_municipio"] == "4330404"


def test_montar_nota_nfse_tomador_contribuinte_cnpj():
    nota = mp.montar_nota_nfse(_emit(), _cli("contribuinte"), 100.0, "NFSE-P2", "D", "svc")
    to = nota["tomador"]
    assert to["doc_tipo"] == "cnpj" and to["doc"] == "11222333000144"


def test_montar_payload_nfse():
    emit = _emit()
    nota = mp.montar_nota_nfse(emit, _cli(), valor_servico=500.0, ref="NFSE-P1",
                               data_emissao="2026-07-06T10:00:00-03:00",
                               discriminacao="Montagem de moveis planejados")
    p = mp.montar_payload_nfse(nota)
    assert p["data_emissao"] == "2026-07-06T10:00:00-03:00"
    # prestador achatado
    assert p["prestador"]["cnpj"] == "19152134000156"
    assert p["prestador"]["inscricao_municipal"] == "123456"
    assert p["prestador"]["codigo_municipio"] == "3549904"
    # servico achatado
    assert p["servico"]["valor_servicos"] == 500.0
    assert p["servico"]["aliquota"] == 5.0
    assert p["servico"]["iss_retido"] is False
    assert p["servico"]["item_lista_servico"] == "1401"
    assert p["servico"]["codigo_tributario_municipio"] == "4330404"
    assert p["servico"]["discriminacao"] == "Montagem de moveis planejados"
    # tomador — cpf por doc_tipo
    assert p["tomador"]["cpf"] == "11144477735" and "cnpj" not in p["tomador"]
    assert p["tomador"]["razao_social"] == "Cliente Y"
    assert p["tomador"]["endereco"]["cep"] == "20000000"
    assert p["tomador"]["endereco"]["uf"] == "RJ"


def test_montar_payload_nfse_tomador_cnpj():
    nota = mp.montar_nota_nfse(_emit(), _cli("contribuinte"), 100.0, "NFSE-P2", "D", "svc")
    p = mp.montar_payload_nfse(nota)
    assert p["tomador"]["cnpj"] == "11222333000144" and "cpf" not in p["tomador"]


def test_montar_payload_nfse_iss_retido_por_retencao():
    # retencao_json com iss_retido -> servico.iss_retido True
    emit = _emit(retencao_json='{"iss_retido": true}')
    nota = mp.montar_nota_nfse(emit, _cli(), 200.0, "NFSE-P3", "D", "svc")
    p = mp.montar_payload_nfse(nota)
    assert p["servico"]["iss_retido"] is True
