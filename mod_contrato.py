"""
mod_contrato.py — Geração de PDF de contrato a partir de template .docx
Usa docxtpl (Jinja2) para preencher variáveis e LibreOffice headless para converter a PDF.
"""

import os
import platform
import subprocess
import hashlib
from datetime import datetime
from docxtpl import DocxTemplate

TEMPLATE_PATH = os.path.join("config", "contrato_template.docx")
CONTRATOS_DIR = "CONTRATOS"


def _libreoffice_cmd() -> str:
    """Retorna o caminho do executável LibreOffice conforme o SO."""
    if platform.system() == "Windows":
        candidatos = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]
        for p in candidatos:
            if os.path.exists(p):
                return p
    return "libreoffice"


def calcular_hash_assinatura(nome: str, cpf: str, contrato_id: int, timestamp: str) -> str:
    """SHA-256 de nome|cpf|contrato_id|timestamp — identifica a assinatura de forma única."""
    dados = f"{nome}|{cpf}|{contrato_id}|{timestamp}"
    return hashlib.sha256(dados.encode("utf-8")).hexdigest()


def _formatar_valor(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def montar_variaveis_contrato(
    projeto: dict,
    cliente: dict,
    orcamento: dict,
    endereco_instalacao: str,
    entrada_valor: float,
    parcelas_descricao: str,
    adendo: str | None,
) -> dict:
    """Constrói o dicionário de variáveis para renderizar o template."""
    endereco_cliente = ", ".join(filter(None, [
        cliente.get("logradouro", ""),
        cliente.get("numero", ""),
        cliente.get("bairro", ""),
        cliente.get("cidade", ""),
        cliente.get("estado", ""),
    ]))
    ambientes = orcamento.get("ambientes", [])
    return {
        "cliente_nome":        cliente.get("nome", ""),
        "cliente_cpf":         cliente.get("cpf", ""),
        "cliente_endereco":    endereco_cliente,
        "cliente_telefone":    cliente.get("telefone", ""),
        "endereco_instalacao": endereco_instalacao or "",
        "projeto_nome":        projeto.get("nome_projeto", ""),
        "projeto_data":        projeto.get("criado_em", ""),
        "orcamento_nome":      orcamento.get("nome", ""),
        "valor_total":         _formatar_valor(orcamento.get("valor_total", 0.0)),
        "forma_pagamento":     orcamento.get("forma_pagamento", ""),
        "entrada_valor":       _formatar_valor(entrada_valor),
        "parcelas_descricao":  parcelas_descricao or "",
        "ambientes_lista":     "\n".join(ambientes),
        "consultor_nome":      projeto.get("consultor", ""),
        "data_contrato":       datetime.now().strftime("%d/%m/%Y"),
        "adendo":              adendo or "",
    }


def gerar_pdf_contrato(contrato_id: int, variaveis: dict) -> str:
    """
    Preenche o template .docx, salva o .docx e converte para PDF.
    Retorna o caminho do PDF gerado.
    Lança FileNotFoundError se o template não existir.
    """
    os.makedirs(CONTRATOS_DIR, exist_ok=True)

    if not os.path.exists(TEMPLATE_PATH):
        raise FileNotFoundError(f"Template não encontrado: {TEMPLATE_PATH}")

    doc = DocxTemplate(TEMPLATE_PATH)
    doc.render(variaveis)

    docx_path = os.path.join(CONTRATOS_DIR, f"contrato_{contrato_id}.docx")
    doc.save(docx_path)

    subprocess.run(
        [_libreoffice_cmd(), "--headless", "--convert-to", "pdf",
         "--outdir", CONTRATOS_DIR, docx_path],
        check=True,
        capture_output=True,
    )

    return os.path.join(CONTRATOS_DIR, f"contrato_{contrato_id}.pdf")
