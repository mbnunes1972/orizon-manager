# -*- coding: utf-8 -*-
"""mod_documentos.py — Registro versionado dos modelos de documento por loja.

Único módulo da frente que fala com o banco (mod_marcadores e
mod_documentos_import são puros).

Regra central: uma versão é IMUTÁVEL. Editar = criar a próxima. Contrato aponta
para a versão que o gerou (Contrato.modelo_versao_id), então regerar um contrato
antigo reproduz as cláusulas originais mesmo que a loja já tenha trocado o modelo.

Fallback: loja sem modelo ativo cai no arquivo global de hoje
(contrato_template/contrato.md) — nada quebra para quem não subiu nada.
"""
import os
import hashlib

from database import DocumentoModelo

TIPOS = ("contrato", "proposta")

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_LOJA_DIR = os.path.join(_THIS_DIR, "documentos_loja")


def _validar(tipo, corpo_md):
    if tipo not in TIPOS:
        raise ValueError("tipo inválido: %r (aceitos: %s)" % (tipo, ", ".join(TIPOS)))
    if not (corpo_md or "").strip():
        raise ValueError("corpo do modelo vazio")


def _proxima_versao(db, loja_id, tipo):
    ultima = (db.query(DocumentoModelo)
                .filter(DocumentoModelo.loja_id == loja_id,
                        DocumentoModelo.tipo == tipo)
                .order_by(DocumentoModelo.versao.desc())
                .first())
    return (ultima.versao + 1) if ultima else 1


def guardar_staging(loja_id, tipo, origem_nome, conteudo_bytes):
    """Guarda o arquivo subido ANTES de a versão existir.

    A importação analisa sem salvar a versão, então o original fica no staging
    até o lojista ativar; criar_versao o promove para v<N>/. Devolve (caminho, sha256).
    """
    d = os.path.join(DOCS_LOJA_DIR, str(loja_id), tipo, "_staging")
    os.makedirs(d, exist_ok=True)
    sha = hashlib.sha256(conteudo_bytes).hexdigest()
    caminho = os.path.join(d, sha[:16] + os.path.splitext(origem_nome or "")[1].lower())
    with open(caminho, "wb") as fh:
        fh.write(conteudo_bytes)
    return caminho, sha


def _promover_original(staging_path, loja_id, tipo, versao, origem_nome):
    """Move o original do staging para v<N>/. Devolve o caminho final, ou None."""
    if not staging_path or not os.path.exists(staging_path):
        return None
    import shutil
    destino_dir = os.path.join(DOCS_LOJA_DIR, str(loja_id), tipo, "v%d" % versao)
    os.makedirs(destino_dir, exist_ok=True)
    destino = os.path.join(destino_dir, os.path.basename(origem_nome or "original"))
    shutil.move(staging_path, destino)
    return destino


def criar_versao(db, loja_id, tipo, corpo_md, origem_nome, usuario_id,
                 nome=None, staging_path=None, origem_sha256=None):
    """Cria a próxima versão (inativa). Ativar é passo à parte — ver ativar().

    staging_path: original vindo de guardar_staging(); é promovido para v<N>/
    aqui, quando o número da versão finalmente existe.
    """
    _validar(tipo, corpo_md)
    versao = _proxima_versao(db, loja_id, tipo)
    origem_path = _promover_original(staging_path, loja_id, tipo, versao, origem_nome)
    m = DocumentoModelo(
        loja_id=loja_id, tipo=tipo, versao=versao,
        nome=nome or os.path.splitext(os.path.basename(origem_nome or ""))[0] or None,
        corpo_md=corpo_md, origem_nome=origem_nome, origem_path=origem_path,
        origem_sha256=origem_sha256, ativo=0, criado_por_id=usuario_id,
    )
    db.add(m)
    db.commit()
    return m


def ativar(db, modelo_id):
    """Liga esta versão e desliga a anterior do mesmo (loja, tipo)."""
    m = db.get(DocumentoModelo, modelo_id)
    if m is None:
        raise ValueError("modelo não encontrado: %s" % modelo_id)
    (db.query(DocumentoModelo)
       .filter(DocumentoModelo.loja_id == m.loja_id,
               DocumentoModelo.tipo == m.tipo,
               DocumentoModelo.id != m.id)
       .update({"ativo": 0}))
    m.ativo = 1
    db.commit()
    return m


def ativo_de(db, loja_id, tipo):
    return (db.query(DocumentoModelo)
              .filter(DocumentoModelo.loja_id == loja_id,
                      DocumentoModelo.tipo == tipo,
                      DocumentoModelo.ativo == 1)
              .first())


def corpo_da_versao(db, modelo_versao_id):
    """Corpo de uma versão específica — o caminho de reprodução do contrato antigo."""
    m = db.get(DocumentoModelo, modelo_versao_id)
    return m.corpo_md if m else None


def resolver_modelo(db, loja_id, tipo):
    """Corpo vigente para (loja, tipo).

    Sem modelo ativo: contrato cai no arquivo global (comportamento de hoje);
    proposta devolve "" (hoje ela é capa-só).
    """
    m = ativo_de(db, loja_id, tipo)
    if m is not None:
        return m.corpo_md
    if tipo == "contrato":
        import mod_contrato
        return mod_contrato._carregar_md()
    return ""


def listar(db, loja_id):
    """Modelos da loja, mais novo primeiro. Escopado por loja (tenancy)."""
    return (db.query(DocumentoModelo)
              .filter(DocumentoModelo.loja_id == loja_id)
              .order_by(DocumentoModelo.tipo, DocumentoModelo.versao.desc())
              .all())
