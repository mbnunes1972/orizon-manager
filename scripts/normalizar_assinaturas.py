"""Normaliza o bloco de assinaturas do modelo_contrato_mapeado.docx para que as
quatro linhas de NOME (empresa, cliente, testemunha 1, testemunha 2) tenham a
mesma formatação e alinhamento: estilo 'Heading 2', sem overrides de fonte/negrito
no run (herda o estilo) e sem quebra de linha extra no início. Idempotente.

Uso: python scripts/normalizar_assinaturas.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from docx import Document          # noqa: E402
from docx.oxml.ns import qn        # noqa: E402

MODELO = os.path.join(os.path.dirname(__file__), "..", "modelo_contrato_mapeado.docx")

# Identifica as linhas de NOME das assinaturas pelo conteúdo.
ALVOS = ["INSPIRIUM MOVEIS PLANEJADOS", "[NOME_CLIENTE]",
         "[NOME_TESTEMUNHA_1]", "[NOME_TESTEMUNHA_2]"]


def _limpar_rpr(run):
    """Remove overrides explícitos de negrito/fonte/tamanho do run (passa a herdar
    do estilo do parágrafo). Retorna True se algum override foi removido."""
    rpr = run._r.find(qn("w:rPr"))
    if rpr is None:
        return False
    removeu = False
    for tag in ("w:b", "w:bCs", "w:rFonts", "w:sz", "w:szCs"):
        el = rpr.find(qn(tag))
        if el is not None:
            rpr.remove(el)
            removeu = True
    return removeu


def _normalizar(par, estilos):
    mudou = False
    # remove runs iniciais vazios/quebra de linha (desalinham o nome)
    while par.runs and not (par.runs[0].text or "").strip():
        r = par.runs[0]
        r._r.getparent().remove(r._r)
        mudou = True
    # estilo uniforme
    if par.style is None or par.style.name != "Heading 2":
        par.style = estilos["Heading 2"]
        mudou = True
    # herança limpa da formatação — só conta como mudança se algum override foi removido
    for r in par.runs:
        if _limpar_rpr(r):
            mudou = True
    return mudou


def main():
    doc = Document(MODELO)
    estilos = doc.styles
    mudou = False
    for par in doc.paragraphs:
        t = par.text or ""
        if any(a in t for a in ALVOS):
            mudou = _normalizar(par, estilos) or mudou
    if mudou:
        doc.save(MODELO)
        print("[OK] Bloco de assinaturas normalizado.")
    else:
        print("[OK] Nada a fazer (assinaturas já normalizadas).")


if __name__ == "__main__":
    main()
