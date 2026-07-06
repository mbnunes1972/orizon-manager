"""mod_fiscal.py — lógica fiscal pura (perfil-padrão de teste, validação, guarda de produção)
e a fiação com o emissor (focus_client_para_loja). Config real vem do PerfilFiscal (banco)."""

REGIMES = {"simples", "simples_excesso", "normal", "mei"}
PAPEIS = {"central_produto", "loja_servico", "loja_produto_servico", "avulso"}
AMBIENTES = {"homologacao", "producao"}

_CNAE_PLACEHOLDER = "4330404"   # instalação/montagem de móveis (genérico — NÃO confirmado)
_CAMPOS_PADRAO = ["regime_tributario", "csosn_padrao", "cfop_dentro_uf", "cfop_fora_uf",
                  "cnae_servico", "aliquota_iss", "papel_cnpj"]


def perfil_padrao_teste():
    """Valores de teste p/ desbloquear (Simples, CFOP 5102/6102, CNAE placeholder, ISS 5%).
    `placeholders` lista os campos defaultados (dirige os badges da UI na Sub-frente II)."""
    return {
        "razao_social": None, "inscricao_estadual": None, "inscricao_municipal": None,
        "regime_tributario": "simples", "csosn_padrao": "101",
        "cfop_dentro_uf": "5102", "cfop_fora_uf": "6102",
        "serie_nfe": None, "discrimina_impostos": 1,
        "cnae_servico": _CNAE_PLACEHOLDER, "cod_servico_municipio": None,
        "aliquota_iss": 5.0, "retencao_json": None, "municipio_ibge": None,
        "papel_cnpj": "loja_produto_servico",
        "placeholders": list(_CAMPOS_PADRAO),
    }


def validar_config(req):
    """(ok, erro) para os campos não-secretos do PUT de config."""
    reg = req.get("regime_tributario")
    if reg is not None and reg not in REGIMES:
        return (False, "regime_tributario inválido")
    papel = req.get("papel_cnpj")
    if papel is not None and papel not in PAPEIS:
        return (False, "papel_cnpj inválido")
    iss = req.get("aliquota_iss")
    if iss is not None:
        try:
            v = float(iss)
        except (TypeError, ValueError):
            return (False, "aliquota_iss inválida")
        if not (0 <= v <= 100):
            return (False, "aliquota_iss fora da faixa (0-100)")
    return (True, "")


def pode_ativar_producao(placeholders):
    """False se restar qualquer placeholder — bloqueia produção com dado de teste."""
    return not placeholders


def focus_client_para_loja(db, loja_id):
    """Monta um FocusClient a partir do PerfilFiscal da loja: token do ambiente_ativo, decriptado,
    e base_url do ambiente. ValueError se não há perfil ou token para o ambiente."""
    import fiscal_cripto
    import focus_config
    from focus_client import FocusClient
    from database import PerfilFiscal
    pf = db.query(PerfilFiscal).filter_by(loja_id=loja_id).first()
    if not pf:
        raise ValueError("Loja %s sem PerfilFiscal configurado" % (loja_id,))
    amb = pf.ambiente_ativo or "homologacao"
    enc = pf.focus_token_homolog_enc if amb == "homologacao" else pf.focus_token_prod_enc
    if not enc:
        raise ValueError("Loja %s sem token Focus para o ambiente %s" % (loja_id, amb))
    return FocusClient(token=fiscal_cripto.decrypt(enc), base_url=focus_config.base_url_de(amb))


def resolver_emitente(db, loja, tipo_doc):
    """Resolve qual Emitente assina `tipo_doc` para `loja`.
    Precedência: override da loja (PerfilEmissao owner="loja") → default da rede
    (owner="rede") → self (loja.emitente_id). ValueError se nada resolver."""
    from database import Emitente, PerfilEmissao

    def _busca(owner_tipo, owner_id):
        if owner_id is None:
            return None
        pe = (db.query(PerfilEmissao)
                .filter_by(owner_tipo=owner_tipo, owner_id=owner_id, tipo_doc=tipo_doc)
                .first())
        return pe.emitente_id if pe else None

    emitente_id = _busca("loja", loja.id)
    if emitente_id is None:
        emitente_id = _busca("rede", loja.rede_id)
    if emitente_id is None:
        emitente_id = loja.emitente_id
    if emitente_id is None:
        raise ValueError(
            "Loja %s sem emitente para tipo_doc=%s (sem override, sem default de rede, "
            "sem emitente próprio)" % (loja.id, tipo_doc))
    emitente = db.get(Emitente, emitente_id)
    if emitente is None:
        raise ValueError("Emitente %s (resolvido p/ loja %s, tipo_doc=%s) não existe"
                         % (emitente_id, loja.id, tipo_doc))
    return emitente


def resolver_plano(db, projeto, tem_produto=True, tem_servico=False):
    """Plano de faturamento do projeto: lista de {tipo_doc, emitente} conforme o que
    o projeto tem (produto/serviço). Resolve o emitente de cada tipo via resolver_emitente."""
    from database import Loja
    loja = db.get(Loja, projeto.loja_id)
    if loja is None:
        raise ValueError("Projeto %s sem loja (loja_id=%s)"
                         % (getattr(projeto, "nome_safe", projeto), projeto.loja_id))
    plano = []
    if tem_produto:
        plano.append({"tipo_doc": "produto", "emitente": resolver_emitente(db, loja, "produto")})
    if tem_servico:
        plano.append({"tipo_doc": "servico", "emitente": resolver_emitente(db, loja, "servico")})
    return plano


def focus_client_para_emitente(db, emitente_id):
    """Monta um FocusClient a partir do Emitente: token do ambiente_ativo, decriptado,
    e base_url do ambiente. ValueError se não há emitente ou token para o ambiente."""
    import fiscal_cripto
    import focus_config
    from focus_client import FocusClient
    from database import Emitente
    em = db.get(Emitente, emitente_id)
    if not em:
        raise ValueError("Emitente %s inexistente" % (emitente_id,))
    amb = em.ambiente_ativo or "homologacao"
    enc = em.focus_token_homolog_enc if amb == "homologacao" else em.focus_token_prod_enc
    if not enc:
        raise ValueError("Emitente %s sem token Focus para o ambiente %s" % (emitente_id, amb))
    return FocusClient(token=fiscal_cripto.decrypt(enc), base_url=focus_config.base_url_de(amb))
