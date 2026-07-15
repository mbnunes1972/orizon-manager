import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mod_marcadores
import mod_contrato


def _mapping_real():
    """Chaves que _montar_mapping realmente produz, com um ctx mínimo."""
    ctx = {"loja": {"nome": "L", "cnpj": "1", "cidade": "C"}}
    return set(mod_contrato._montar_mapping(ctx, {}).keys())


def test_catalogo_cobre_todo_marcador_do_mapping():
    faltando = _mapping_real() - set(mod_marcadores.CATALOGO)
    assert not faltando, f"marcadores sem verbete no catálogo: {sorted(faltando)}"


def test_catalogo_nao_inventa_marcador():
    # TEXTO_COMPLEMENTAR é injetado em _montar_html_contrato, não em _montar_mapping.
    sobrando = set(mod_marcadores.CATALOGO) - _mapping_real() - {"TEXTO_COMPLEMENTAR"}
    assert not sobrando, f"catálogo promete marcador que ninguém preenche: {sorted(sobrando)}"


def test_todo_verbete_tem_rotulo_e_escopo():
    # "projeto" é reserva: seria o escopo dos marcadores da proposta (AMBIENTES_LISTA,
    # VALOR_BRUTO, DESCONTO_PCT, VALOR_TOTAL, VALIDADE — hoje em mod_proposta.py:18-24)
    # se um dia entrarem; _montar_mapping não os produz, então nenhum verbete o usa ainda.
    for chave, v in mod_marcadores.CATALOGO.items():
        assert v.get("rotulo"), f"{chave} sem rótulo"
        assert v.get("escopo") in ("cliente", "loja", "pagamento", "projeto", "documento"), \
            f"{chave} com escopo inválido: {v.get('escopo')}"


def test_marcadores_de_endereco_da_loja_existem():
    """Sem estes, o preâmbulo do contrato não tem como ser parametrizado."""
    for c in ("LOJA_LOGRADOURO", "LOJA_NUMERO", "LOJA_BAIRRO",
              "LOJA_CIDADE", "LOJA_UF", "LOJA_CEP"):
        assert c in mod_marcadores.CATALOGO, f"faltou {c}"
