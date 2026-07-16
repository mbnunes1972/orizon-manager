import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from fiscal import mod_fiscal as mf


def test_emitente_padrao_teste():
    p = mf.emitente_padrao_teste()
    assert p["regime_tributario"] == "simples" and p["csosn_padrao"] == "102"
    assert p["cfop_dentro_uf"] == "5102" and p["cfop_fora_uf"] == "6102"
    assert p["aliquota_iss"] == 5.0 and p["papel_cnpj"] == "loja_produto_servico"
    for chave in ("regime_tributario", "csosn_padrao", "cfop_dentro_uf", "cfop_fora_uf",
                  "cnae_servico", "aliquota_iss"):
        assert chave in p["placeholders"]


def test_validar_config_ok():
    ok, erro = mf.validar_config({"regime_tributario": "simples", "papel_cnpj": "avulso",
                                  "aliquota_iss": 5})
    assert ok is True and erro == ""


def test_validar_config_regime_invalido():
    ok, erro = mf.validar_config({"regime_tributario": "lucro_marciano"})
    assert ok is False and "regime" in erro


def test_validar_config_papel_invalido():
    ok, erro = mf.validar_config({"papel_cnpj": "imperador"})
    assert ok is False and "papel" in erro


def test_validar_config_iss_fora_faixa():
    ok, erro = mf.validar_config({"aliquota_iss": 150})
    assert ok is False and "iss" in erro.lower()
    ok2, _ = mf.validar_config({"aliquota_iss": "abc"})
    assert ok2 is False


def test_pode_ativar_producao():
    assert mf.pode_ativar_producao([]) is True
    assert mf.pode_ativar_producao(["regime_tributario"]) is False


# ── prontidao_emitente (US-42 / auditoria A2/A3/A5) ───────────────────────────
from types import SimpleNamespace


def _emit_pronto_produto(**kw):
    base = dict(regime_tributario="simples", uf="SP", inscricao_estadual="123")
    base.update(kw); return SimpleNamespace(**base)


def _emit_pronto_servico(**kw):
    base = dict(regime_tributario="simples", inscricao_municipal="322176",
                municipio_ibge="3549904", cod_servico_municipio="14.13.03", aliquota_iss=5.0)
    base.update(kw); return SimpleNamespace(**base)


def test_prontidao_produto_ok():
    assert mf.prontidao_emitente(_emit_pronto_produto(), "produto") is None


def test_prontidao_produto_regime_nao_simples_barra():
    e = mf.prontidao_emitente(_emit_pronto_produto(regime_tributario="normal"), "produto")
    assert e and "Simples" in e


def test_prontidao_produto_uf_vazia_barra():
    for uf in (None, "", "  "):
        e = mf.prontidao_emitente(_emit_pronto_produto(uf=uf), "produto")
        assert e and "UF" in e


def test_prontidao_servico_ok():
    assert mf.prontidao_emitente(_emit_pronto_servico(), "servico") is None


def test_prontidao_servico_sem_im_barra():
    e = mf.prontidao_emitente(_emit_pronto_servico(inscricao_municipal=None), "servico")
    assert e and "Inscrição Municipal" in e


def test_prontidao_servico_sem_ibge_ou_cod_ou_iss_barra():
    assert mf.prontidao_emitente(_emit_pronto_servico(municipio_ibge=""), "servico")
    assert mf.prontidao_emitente(_emit_pronto_servico(cod_servico_municipio=None), "servico")
    assert mf.prontidao_emitente(_emit_pronto_servico(aliquota_iss=None), "servico")
