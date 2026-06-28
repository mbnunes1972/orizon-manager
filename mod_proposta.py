"""Geração da Proposta comercial (PDF/docx) — reaproveita o motor de marcadores de mod_contrato.
Sob demanda, sem persistência: gera num diretório informado pelo chamador."""
import os
from docx import Document
import mod_contrato

_MODELO_PROPOSTA = os.path.join(os.path.dirname(__file__), "modelo_proposta.docx")


def contexto_proposta(cliente, usuario, loja, orcamento_dict, breakdown, forma_pagamento_json):
    """Monta o {MARCADOR: valor} da proposta (chaves MAIÚSCULAS, sem colchetes)."""
    ctx = mod_contrato.construir_contexto(cliente, usuario, forma_pagamento_json or "", loja)
    mapping = mod_contrato._montar_mapping(ctx, ctx.get("_pag", {}))
    f = mod_contrato._formatar_valor
    vbvo = float(breakdown.get("VBVO") or 0)
    vavo = float(breakdown.get("VAVO") or 0)
    desc = (1 - vavo / vbvo) * 100 if vbvo else 0.0
    mapping.update({
        "AMBIENTES_LISTA": "\n".join(orcamento_dict.get("ambientes") or []),
        "VALOR_BRUTO":  f(vbvo),
        "DESCONTO_PCT": f"{desc:.1f}%".replace(".", ","),
        "VALOR_TOTAL":  f(vavo),
        "VALIDADE":     "Proposta válida por 10 dias a partir da emissão.",
    })
    return mapping


def gerar_proposta(variaveis, outdir):
    """Preenche modelo_proposta.docx em outdir; tenta PDF (no mesmo outdir).
    Retorna (caminho, eh_pdf). Não persiste fora de outdir."""
    if not os.path.exists(_MODELO_PROPOSTA):
        raise FileNotFoundError("Modelo de proposta não encontrado: %s" % _MODELO_PROPOSTA)
    os.makedirs(outdir, exist_ok=True)
    doc = Document(_MODELO_PROPOSTA)
    mod_contrato._substituir_marcadores(doc, variaveis)
    docx_path = os.path.join(outdir, "proposta.docx")
    doc.save(docx_path)
    try:
        pdf_path = mod_contrato._converter_pdf(docx_path, outdir=outdir)
        return pdf_path, True
    except mod_contrato.LibreOfficeIndisponivel:
        return docx_path, False
