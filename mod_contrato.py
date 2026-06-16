"""
mod_contrato.py — Geração de PDF de contrato a partir de template .docx
Usa docxtpl (Jinja2) para preencher variáveis e LibreOffice headless para converter a PDF.
"""

import os
import json
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


def _formatar_data_br(iso_date: str) -> str:
    """Converte 'YYYY-MM-DD' → 'DD/MM/AAAA'. Retorna '—' se inválido."""
    if not iso_date or len(iso_date) < 10:
        return "—"
    try:
        return datetime.strptime(iso_date[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return iso_date


def _parse_valor_float(val_str: str) -> float:
    """Converte 'R$ 4.820,00' → 4820.0."""
    if not val_str:
        return 0.0
    s = val_str.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _formatar_bloco_pagamento(
    pagamento_json_str: str,
    forma_entrada_label: str = "Pix",
) -> str:
    """
    Gera bloco de texto descritivo do pagamento para inserção no template.
    Cartão: texto livre. Demais: tabela de parcelas.
    """
    if not pagamento_json_str:
        return ""
    try:
        pag = json.loads(pagamento_json_str)
    except Exception:
        return pagamento_json_str

    tipo          = pag.get("tipo", "")
    nome_forma    = pag.get("nome_forma", "")
    parcelas      = pag.get("parcelas", [])
    entrada_valor = float(pag.get("entrada_valor", 0) or 0)
    entrada_data  = pag.get("entrada_data", "")
    texto         = pag.get("texto", "")

    linhas = [f"Forma de Pagamento: {nome_forma}"]

    if tipo == "cartao":
        linhas.append(texto)
        return "\n".join(linhas)

    # Tabela
    ent_fmt  = _formatar_valor(entrada_valor)
    ent_data = _formatar_data_br(entrada_data)
    linhas.append("")
    linhas.append(f"{'#':<5}{'Descrição':<22}{'Data':<14}{'Valor':<18}Forma")
    linhas.append("-" * 72)
    linhas.append(f"{'Ent':<5}{'Entrada':<22}{ent_data:<14}{ent_fmt:<18}{forma_entrada_label}")

    total_parcelas = 0.0
    for p in parcelas:
        seq   = str(p.get("seq", ""))
        desc  = str(p.get("descricao", ""))[:20]
        data  = _formatar_data_br(p.get("data", ""))
        val   = str(p.get("valor", ""))
        forma = str(p.get("forma", ""))
        linhas.append(f"{seq:<5}{desc:<22}{data:<14}{val:<18}{forma}")
        total_parcelas += _parse_valor_float(val)

    total_geral = entrada_valor + total_parcelas
    linhas.append("-" * 72)
    linhas.append(f"{'Total':<41}{_formatar_valor(total_geral)}")
    return "\n".join(linhas)


def montar_variaveis_contrato(
    projeto: dict,
    cliente: dict,
    orcamento: dict,
    endereco_instalacao: str,
    entrada_valor: float,
    parcelas_descricao: str,
    adendo: str | None,
    forma_entrada: str = "pix",
    forma_parcelas: str = "boleto",
    pagamento_json: str = "",      # JSON com cronograma de parcelas
) -> dict:
    """Constrói o dicionário de variáveis para renderizar o template."""
    _FORMAS = {
        "pix": "Pix", "transferencia": "Transferência Bancária",
        "boleto": "Boleto Bancário", "cartao_credito": "Cartão de Crédito",
        "cartao_debito": "Cartão de Débito", "cheque": "Cheque",
        "debito_automatico": "Débito Automático",
    }
    endereco_cliente = ", ".join(filter(None, [
        cliente.get("logradouro", ""),
        cliente.get("numero", ""),
        cliente.get("bairro", ""),
        cliente.get("cidade", ""),
        cliente.get("estado", ""),
    ]))
    ambientes = orcamento.get("ambientes", [])
    bloco_pag = _formatar_bloco_pagamento(
        pagamento_json,
        forma_entrada_label=_FORMAS.get(forma_entrada, forma_entrada),
    )
    return {
        "cliente_nome":                    cliente.get("nome", ""),
        "cliente_cpf":                     cliente.get("cpf", ""),
        "cliente_email":                   cliente.get("email", ""),
        "cliente_endereco":                endereco_cliente,
        "cliente_telefone":                cliente.get("telefone", ""),
        "cliente_endereco_correspondencia": endereco_cliente,
        "cliente_endereco_instalacao":     endereco_instalacao or endereco_cliente,
        "endereco_instalacao":             endereco_instalacao or "",
        "projeto_nome":                    projeto.get("nome_projeto", ""),
        "projeto_data":                    projeto.get("criado_em", ""),
        "orcamento_nome":                  orcamento.get("nome", ""),
        "valor_total":                     _formatar_valor(orcamento.get("valor_total", 0.0)),
        "valor_negociado":                 _formatar_valor(orcamento.get("valor_total", 0.0)),
        "valor_liquido":                   _formatar_valor(orcamento.get("valor_liquido", 0.0)),
        "forma_pagamento":                 orcamento.get("forma_pagamento", ""),
        "entrada_valor":                   _formatar_valor(entrada_valor),
        "parcelas_descricao":              parcelas_descricao or "",
        "pagamento_bloco":                 bloco_pag or parcelas_descricao or "",
        "ambientes_lista":                 "\n".join(ambientes),
        "consultor_nome":                  projeto.get("consultor", ""),
        "data_contrato":                   datetime.now().strftime("%d/%m/%Y"),
        "adendo":                          adendo or "",
        "entrada_forma":                   _FORMAS.get(forma_entrada, forma_entrada),
        "parcelas_forma":                  _FORMAS.get(forma_parcelas, forma_parcelas),
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
