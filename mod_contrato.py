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

_THIS_DIR     = os.path.dirname(os.path.abspath(__file__))
CONTRATOS_DIR = os.path.join(_THIS_DIR, "CONTRATOS")

_TEMPLATE_CANDIDATOS = [
    os.path.join(_THIS_DIR, "Modelo de Contrato.docx"),
    os.path.join(_THIS_DIR, "config", "contrato_template.docx"),
]

def _encontrar_template() -> str:
    for p in _TEMPLATE_CANDIDATOS:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(
        "Template de contrato não encontrado.\n"
        "Adicione 'Modelo de Contrato.docx' na raiz do projeto."
    )


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
        "valor_liquido":       _formatar_valor(orcamento.get("valor_liquido", 0.0)),
        "forma_pagamento":     orcamento.get("forma_pagamento", ""),
        "entrada_valor":       _formatar_valor(entrada_valor),
        "parcelas_descricao":  parcelas_descricao or "",
        "ambientes_lista":     "\n".join(ambientes),
        "consultor_nome":      projeto.get("consultor", ""),
        "data_contrato":       datetime.now().strftime("%d/%m/%Y"),
        "adendo":              adendo or "",
    }


class LibreOfficeIndisponivel(Exception):
    """LibreOffice não encontrado — .docx gerado mas PDF pendente."""
    def __init__(self, docx_path: str):
        self.docx_path = docx_path
        super().__init__(
            "LibreOffice não encontrado no servidor.\n"
            "O arquivo Word (.docx) foi gerado e está disponível para download.\n"
            "Instale o LibreOffice no servidor para gerar PDF automaticamente."
        )


def gerar_pdf_contrato(contrato_id: int, variaveis: dict) -> str:
    """
    Preenche o template .docx, salva o .docx e converte para PDF.
    Retorna o caminho do PDF gerado.
    Lança FileNotFoundError se o template não existir.
    Lança LibreOfficeIndisponivel se o LibreOffice não estiver instalado (com docx_path).
    Lança RuntimeError se a conversão LibreOffice falhar por outro motivo.
    """
    template_path = _encontrar_template()
    os.makedirs(CONTRATOS_DIR, exist_ok=True)

    doc = DocxTemplate(template_path)
    doc.render(variaveis)

    docx_path = os.path.join(CONTRATOS_DIR, f"contrato_{contrato_id}.docx")
    doc.save(docx_path)

    try:
        subprocess.run(
            [_libreoffice_cmd(), "--headless", "--convert-to", "pdf",
             "--outdir", CONTRATOS_DIR, docx_path],
            check=True,
            capture_output=True,
            timeout=120,
        )
    except FileNotFoundError:
        raise LibreOfficeIndisponivel(docx_path)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"LibreOffice falhou ao converter PDF:\n{e.stderr.decode(errors='replace')}") from e
    except subprocess.TimeoutExpired:
        raise RuntimeError("LibreOffice demorou mais de 120s — possível travamento na conversão")

    return os.path.join(CONTRATOS_DIR, f"contrato_{contrato_id}.pdf")
