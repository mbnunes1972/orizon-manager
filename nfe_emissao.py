"""nfe_emissao.py — serviço de emissão da NF-e da loja via Focus (Fase 4).
Emite, acompanha (polling), guarda XML/DANFE (CicloDocumento) e rastreia (DocumentoFiscal).
Testável offline: `emissor` é injetável. Nenhuma UI/rota aqui."""
import os
import json
import uuid
from datetime import datetime

import storage
from database import DocumentoFiscal, PerfilFiscal, CicloDocumento
from emissor_fiscal import StatusNota, ResultadoEmissao, resultado_de_focus

_TIPO_XML = "nfe_loja_xml"
_TIPO_DANFE = "nfe_loja_danfe"
_TIPO_CANC = "nfe_loja_cancelamento_xml"
_NOME_DEST_HOMOLOG = "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL"


def _emissor_para(db, loja_id):
    import mod_fiscal
    from emissor_focus import EmissorFocusNfe
    return EmissorFocusNfe(mod_fiscal.focus_client_para_loja(db, loja_id))


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


def _guardar_docs_autorizado(db, reg, res, client):
    xml_doc = _guardar_doc(db, reg.projeto_nome, _TIPO_XML, res.xml_url, client)
    danfe_doc = _guardar_doc(db, reg.projeto_nome, _TIPO_DANFE, res.danfe_url, client)
    if xml_doc:
        reg.xml_doc_id = xml_doc.id
    if danfe_doc:
        reg.danfe_doc_id = danfe_doc.id


def emitir(db, loja_id, projeto_nome, nota, permitir_producao=False, emissor=None,
           fabrica_doc_id=None):
    """Emite (ou devolve idempotente), acompanha até o status final e guarda XML/DANFE."""
    ref = nota["ref"]
    reg = db.query(DocumentoFiscal).filter_by(ref=ref).first()
    if reg and reg.status == "autorizado":
        return _resultado_de_registro(reg)
    pf = db.query(PerfilFiscal).filter_by(loja_id=loja_id).first()
    ambiente = (pf.ambiente_ativo if pf else "homologacao") or "homologacao"
    if ambiente == "producao" and not permitir_producao:
        raise ValueError("Emissão em produção bloqueada (use permitir_producao=True).")
    if ambiente == "homologacao":
        nota["destinatario"]["nome"] = _NOME_DEST_HOMOLOG
    if emissor is None:
        emissor = _emissor_para(db, loja_id)
    res = emissor.emitir_nfe_produto(nota)
    if res.status == StatusNota.PROCESSANDO:
        res = resultado_de_focus(emissor.client.aguardar_processamento(ref))
    if not reg:
        reg = DocumentoFiscal(ref=ref, projeto_nome=projeto_nome, loja_id=loja_id, etapa_codigo="15",
                              tipo_documento="produto", fabrica_doc_id=fabrica_doc_id)
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
        emissor = _emissor_para(db, reg.loja_id)
    res = emissor.consultar_status(ref)
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
        emissor = _emissor_para(db, reg.loja_id)
    res = emissor.cancelar(ref, justificativa)
    _aplicar_resultado(reg, res)
    if res.xml_cancelamento_url:
        _guardar_doc(db, reg.projeto_nome, _TIPO_CANC, res.xml_cancelamento_url, emissor.client)
    db.commit()
    return res
