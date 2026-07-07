"""nfe_emissao.py — serviço de emissão da NF-e da loja via Focus (Fase 4).
Emite, acompanha (polling), guarda XML/DANFE (CicloDocumento) e rastreia (DocumentoFiscal).
Testável offline: `emissor` é injetável. Nenhuma UI/rota aqui."""
import os
import json
import uuid
from datetime import datetime

import storage
from database import DocumentoFiscal, Emitente, CicloDocumento
from emissor_fiscal import StatusNota, ResultadoEmissao, resultado_de_focus

_TIPO_XML = "nfe_loja_xml"
_TIPO_DANFE = "nfe_loja_danfe"
_TIPO_CANC = "nfe_loja_cancelamento_xml"
_TIPO_NFSE_XML = "nfse_loja_xml"
_TIPO_NFSE_PDF = "nfse_loja_pdf"
_NOME_DEST_HOMOLOG = "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL"


def _emissor_para(db, emitente_id):
    import mod_fiscal
    from emissor_focus import EmissorFocusNfe
    return EmissorFocusNfe(mod_fiscal.focus_client_para_emitente(db, emitente_id))


def _guardar_doc(db, projeto_nome, tipo, caminho_focus, client):
    if not projeto_nome or not caminho_focus:
        return None
    data = client.baixar(caminho_focus)
    base = os.path.basename(caminho_focus) or (tipo + ".bin")
    unico = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:8] + "_" + base
    rel = os.path.join("ciclo", "15", unico)
    doc = CicloDocumento(projeto_nome=projeto_nome, etapa_codigo="15", tipo=tipo,
                         arquivo_path=rel, nome_original=base)
    db.add(doc)
    db.flush()
    storage.storage_salvar_binario(os.path.join(storage.PROJETOS_DIR, projeto_nome, rel), data)
    return doc


def _aplicar_resultado(reg, res):
    reg.status = res.status.value if hasattr(res.status, "value") else res.status
    reg.chave_nfe = res.chave
    reg.numero = res.numero
    reg.serie = res.serie
    reg.mensagem_sefaz = res.mensagem_sefaz
    reg.erros_json = json.dumps(res.erros, ensure_ascii=False) if res.erros else None


def _resultado_de_registro(reg):
    st = StatusNota(reg.status) if reg.status else StatusNota.DESCONHECIDO
    return ResultadoEmissao(ref=reg.ref, status=st, chave=reg.chave_nfe, numero=reg.numero,
                            serie=reg.serie, mensagem_sefaz=reg.mensagem_sefaz)


def _tipos_docs(tipo_documento):
    """(tipo XML, tipo PDF/DANFE) do CicloDocumento conforme o documento (NF-e produto vs NFS-e serviço)."""
    if tipo_documento == "servico":
        return _TIPO_NFSE_XML, _TIPO_NFSE_PDF
    return _TIPO_XML, _TIPO_DANFE


def _guardar_docs_autorizado(db, reg, res, client):
    tipo_xml, tipo_pdf = _tipos_docs(reg.tipo_documento)
    xml_doc = _guardar_doc(db, reg.projeto_nome, tipo_xml, res.xml_url, client)
    danfe_doc = _guardar_doc(db, reg.projeto_nome, tipo_pdf, res.danfe_url, client)
    if xml_doc:
        reg.xml_doc_id = xml_doc.id
    if danfe_doc:
        reg.danfe_doc_id = danfe_doc.id


def emitir(db, loja_id, projeto_nome, nota, tipo_documento="produto", emitente_id=None,
           permitir_producao=False, emissor=None, fabrica_doc_id=None):
    """Emite (ou devolve idempotente), acompanha até o status final e guarda XML/DANFE.
    O ambiente (guarda de produção + carimbo SEFAZ de homologação) vem do `Emitente` resolvido."""
    ref = nota["ref"]
    reg = db.query(DocumentoFiscal).filter_by(ref=ref).first()
    if reg and reg.status == "autorizado":
        return _resultado_de_registro(reg)
    em = db.get(Emitente, emitente_id) if emitente_id is not None else None
    ambiente = (em.ambiente_ativo if em else "homologacao") or "homologacao"
    if ambiente == "producao" and not permitir_producao:
        raise ValueError("Emissão em produção bloqueada (use permitir_producao=True).")
    # Carimbo SEFAZ de homologação é regra do NF-e (produto); a NFS-e não tem `destinatario`.
    if ambiente == "homologacao" and tipo_documento != "servico":
        nota["destinatario"]["nome"] = _NOME_DEST_HOMOLOG
    if emissor is None:
        emissor = _emissor_para(db, emitente_id)
    if tipo_documento == "servico":
        res = emissor.emitir_nfse_servico(nota)
        aguardar = emissor.client.aguardar_processamento_nfse
    else:
        res = emissor.emitir_nfe_produto(nota)
        aguardar = emissor.client.aguardar_processamento
    if res.status == StatusNota.PROCESSANDO:
        res = resultado_de_focus(aguardar(ref))
    if not reg:
        reg = DocumentoFiscal(ref=ref, projeto_nome=projeto_nome, loja_id=loja_id, etapa_codigo="15",
                              tipo_documento=tipo_documento, emitente_id=emitente_id,
                              fabrica_doc_id=fabrica_doc_id)
        db.add(reg)
    _aplicar_resultado(reg, res)
    if res.status == StatusNota.AUTORIZADO:
        _guardar_docs_autorizado(db, reg, res, emissor.client)
    db.commit()
    return res


def consultar(db, ref, emissor=None):
    """Reconsulta o status e atualiza o registro (baixa docs se recém-autorizado)."""
    reg = db.query(DocumentoFiscal).filter_by(ref=ref).first()
    if not reg:
        raise ValueError("DocumentoFiscal %s não encontrada" % (ref,))
    if emissor is None:
        emissor = _emissor_para(db, reg.emitente_id)
    res = (emissor.consultar_status_nfse(ref) if reg.tipo_documento == "servico"
           else emissor.consultar_status(ref))
    ja_tinha = reg.xml_doc_id is not None
    _aplicar_resultado(reg, res)
    if res.status == StatusNota.AUTORIZADO and not ja_tinha:
        _guardar_docs_autorizado(db, reg, res, emissor.client)
    db.commit()
    return res


def cancelar(db, ref, justificativa, emissor=None):
    """Cancela na Focus e atualiza o registro (guarda o XML de cancelamento)."""
    reg = db.query(DocumentoFiscal).filter_by(ref=ref).first()
    if not reg:
        raise ValueError("DocumentoFiscal %s não encontrada" % (ref,))
    if emissor is None:
        emissor = _emissor_para(db, reg.emitente_id)
    res = (emissor.cancelar_nfse(ref, justificativa) if reg.tipo_documento == "servico"
           else emissor.cancelar(ref, justificativa))
    _aplicar_resultado(reg, res)
    if res.xml_cancelamento_url:
        _guardar_doc(db, reg.projeto_nome, _TIPO_CANC, res.xml_cancelamento_url, emissor.client)
    db.commit()
    return res
