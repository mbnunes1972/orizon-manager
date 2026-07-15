# -*- coding: utf-8 -*-
"""mod_documentos_import.py — Importação de modelo de documento: arquivo → Markdown.

Duas responsabilidades, deliberadamente separadas:

  normalizar(path)    arquivo → texto puro. Toca subprocess (LibreOffice).
  extrair_corpo(txt)  texto → Markdown das cláusulas. Função PURA, testável
                      sem LibreOffice instalado.

POR QUE LIBREOFFICE E NÃO python-docx: o .docx do contrato usa numeração
AUTOMÁTICA do Word (numId/ilvl). Os números ("1.1", "2.3", "a)") NÃO estão no
texto do parágrafo, e python-docx não os devolve — as cláusulas sairiam sem
número. O export em texto do LibreOffice achata a numeração em literal.
Ver scripts/extrair_clausulas_docx.py (o protótipo que originou este módulo).

Sem banco. Sem estado.
"""
import os
import re
import subprocess
import tempfile

# Os dois marcos abaixo são a REDAÇÃO DO MODELO ATUAL, não uma lei da natureza: a loja
# pode subir contrato com redação própria e não tê-los. Comportamento quando faltam:
#
#   início ausente → usa o texto inteiro (nada a cortar).
#   fecho  ausente → NÃO insere [TEXTO_COMPLEMENTAR]. Deliberado: sem âncora, adivinhar
#                    a posição (ex.: anexar no fim) colocaria o adendo do ciclo em lugar
#                    arbitrário de um documento jurídico. Quem avisa o lojista é o wizard
#                    (mod_marcadores.analisar_corpo) — este módulo converte, não valida.
#                    A separação é proposital.
#
# Onde o corpo começa: tudo antes disto é capa (gerada pelo HTML, não pelo modelo).
_MARCO_INICIO = "CONTRATO DE COMPRA E VENDA"
# O adendo do ciclo entra imediatamente antes do fecho de assinaturas.
_MARCO_FECHO = "E assim, por estarem assim convencionados"

_RE_CLAUSULA = re.compile(r'^(?:\d+\.\s+)?(CLÁUSULA\b.*)$')

EXTENSOES_TEXTO = {".md", ".txt"}
EXTENSOES_OFFICE = {".docx", ".odt", ".doc", ".rtf"}


class FormatoNaoSuportado(Exception):
    pass


def extrair_corpo(texto: str) -> str:
    """Texto exportado do LibreOffice → Markdown das cláusulas.

    Corta a capa, vira 'CLÁUSULA ...' em heading '#', tira a indentação e
    insere [TEXTO_COMPLEMENTAR] antes do fecho de assinaturas.
    """
    if not (texto or "").strip():
        return ""
    linhas = texto.split("\n")
    ini = 0
    for i, l in enumerate(linhas):
        if l.strip().startswith(_MARCO_INICIO):
            ini = i
            break
    md = []
    for raw in linhas[ini:]:
        t = raw.strip()
        if not t:
            md.append("")
            continue
        m = _RE_CLAUSULA.match(t)
        md.append(f"# {m.group(1)}" if m else t)
    out = "\n".join(md).rstrip() + "\n"
    if _MARCO_FECHO in out and "[TEXTO_COMPLEMENTAR]" not in out:
        out = out.replace(_MARCO_FECHO,
                          f"[TEXTO_COMPLEMENTAR]\n\n{_MARCO_FECHO}", 1)
    return out


def normalizar(path: str) -> str:
    """Arquivo → texto puro.

    .md/.txt: leitura direta. .docx/.odt/.doc/.rtf: LibreOffice headless.
    .pdf: recusado — a extração perde a hierarquia das cláusulas.

    utf-8-sig nas leituras: o .txt do LibreOffice vem com BOM, e com utf-8 puro o
    U+FEFF invisível vazaria para o corpo (e quebraria o startswith do marco de
    início). utf-8-sig lê normalmente arquivos sem BOM.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext in EXTENSOES_TEXTO:
        with open(path, encoding="utf-8-sig") as fh:
            return fh.read()
    if ext == ".pdf":
        raise FormatoNaoSuportado(
            "PDF não pode ser convertido em modelo: a extração de texto perde a "
            "hierarquia das cláusulas (títulos, numeração, alíneas). Envie o "
            "documento em Word (.docx), LibreOffice (.odt) ou texto."
        )
    if ext not in EXTENSOES_OFFICE:
        raise FormatoNaoSuportado(f"Formato não suportado: {ext or '(sem extensão)'}")

    from mod_contrato import _libreoffice_cmd, LibreOfficeIndisponivel
    outdir = tempfile.mkdtemp(prefix="orizon_import_")
    try:
        try:
            subprocess.run(
                [_libreoffice_cmd(), "--headless", "--convert-to",
                 "txt:Text (encoded):UTF8", "--outdir", outdir, path],
                check=True, capture_output=True, timeout=120,
            )
        except FileNotFoundError:
            raise LibreOfficeIndisponivel(path)
        except subprocess.TimeoutExpired:
            raise RuntimeError("LibreOffice demorou mais de 120s na conversão")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "LibreOffice falhou:\n%s" % e.stderr.decode(errors="replace"))
        base = os.path.splitext(os.path.basename(path))[0] + ".txt"
        destino = os.path.join(outdir, base)
        if not os.path.exists(destino):
            raise RuntimeError("LibreOffice não produziu o .txt esperado: %s" % destino)
        with open(destino, encoding="utf-8-sig") as fh:
            return fh.read()
    finally:
        import shutil
        shutil.rmtree(outdir, ignore_errors=True)
