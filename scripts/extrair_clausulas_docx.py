#!/usr/bin/env python3
"""Migra o corpo do contrato (após a capa) do .docx para Markdown com números literais.

O modelo .docx usa numeração AUTOMÁTICA do Word (numId/ilvl) — os números ("1.1",
"2.3", "a)") NÃO estão no texto dos parágrafos (python-docx `paragraph.text` não os
inclui). Por isso a fonte da migração é o export em TEXTO do LibreOffice, que
"achata" a numeração automática em texto literal. Gere o .txt antes:

    soffice --headless --convert-to "txt:Text (encoded):UTF8" \
        --outdir CONTRATOS modelo_contrato_mapeado.docx

Este script lê esse .txt, corta a capa (mantém do 'CONTRATO DE COMPRA E VENDA' em
diante), transforma títulos 'CLÁUSULA ...' em headings `#`, tira a indentação das
cláusulas/alíneas e insere o marcador [TEXTO_COMPLEMENTAR] antes do fecho.

REVISAR o resultado — documento jurídico (números, quebras de linha, alíneas).
"""
import re
import os

TXT = "CONTRATOS/modelo_contrato_mapeado.txt"
OUT = "contrato_template/contrato.md"

linhas = open(TXT, encoding="utf-8").read().split("\n")
ini = next(i for i, l in enumerate(linhas)
           if l.strip().startswith("CONTRATO DE COMPRA E VENDA"))
corpo = linhas[ini:]

md = []
for raw in corpo:
    t = raw.strip()
    if not t:
        md.append("")
        continue
    # título "CLÁUSULA ..." -> heading (removendo prefixo "N. " da lista, se houver)
    m = re.match(r'^(?:\d+\.\s+)?(CLÁUSULA\b.*)$', t)
    if m:
        md.append(f"# {m.group(1)}")
        continue
    md.append(t)

texto = "\n".join(md).rstrip() + "\n"

# marcador de texto complementar (adendo do ciclo) antes do fecho de assinaturas
texto = texto.replace(
    "E assim, por estarem assim convencionados",
    "[TEXTO_COMPLEMENTAR]\n\nE assim, por estarem assim convencionados",
    1,
)

os.makedirs("contrato_template", exist_ok=True)
open(OUT, "w", encoding="utf-8").write(texto)
print(f"{OUT}: {texto.count(chr(10))} linhas, {len(texto)} chars")
