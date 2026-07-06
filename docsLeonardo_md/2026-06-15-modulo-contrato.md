# Módulo de Contrato — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o módulo de geração, visualização e assinatura interna de contratos (etapa 7 do pipeline), incluindo a infraestrutura mínima da aba "Ciclo" em page-02.

**Architecture:** `mod_contrato.py` cuida da geração de PDF via `docxtpl` + LibreOffice headless. `database.py` ganha três novos modelos (`CicloEtapa`, `Contrato`, `ContratoAssinatura`). `main.py` ganha seis rotas novas para ciclo e contrato. O frontend (SPA em `static/index.html`) ganha uma aba "Ciclo" em page-02 com card do contrato, viewer de PDF via iframe e modal de assinatura interna.

**Tech Stack:** `docxtpl` (template .docx com Jinja2), LibreOffice headless (conversão .docx→PDF), SQLAlchemy (modelos), Python http.server (rotas), HTML/CSS/JS puro (frontend).

**Plano 2 separado:** A emissão da NFe do cliente (etapa 15) será implementada em `docs/superpowers/plans/2026-06-15-modulo-nfe-cliente.md` após este plano estar completo.

---

## File Map

| Arquivo | Ação | Responsabilidade |
|---------|------|-----------------|
| `database.py` | Modificar | Adicionar modelos `CicloEtapa`, `Contrato`, `ContratoAssinatura` + migração |
| `mod_contrato.py` | Criar | Geração de PDF + cálculo de hash de assinatura |
| `main.py` | Modificar | 6 novas rotas: GET/PATCH ciclo, POST/GET/PATCH contrato, POST assinar |
| `static/index.html` | Modificar | Aba "Ciclo" em page-02, cards do pipeline, viewer PDF, modal assinatura |
| `tests/test_contrato.py` | Criar | Testes de `calcular_hash_assinatura` e `montar_variaveis_contrato` |
| `config/contrato_template.docx` | Criar | Template placeholder gerado por script |
| `scripts/criar_template_placeholder.py` | Criar | Gera o .docx de teste com todas as variáveis |

---

## Task 1: Instalar dependências e criar template placeholder

**Files:**
- Create: `scripts/criar_template_placeholder.py`
- Create: `config/contrato_template.docx` (gerado pelo script)

- [ ] **Step 1.1: Instalar docxtpl**

```bash
pip install docxtpl
```

Verificar instalação:
```bash
python -c "from docxtpl import DocxTemplate; print('ok')"
```
Expected: `ok`

- [ ] **Step 1.2: Instalar LibreOffice (servidor Ubuntu)**

No servidor Ubuntu:
```bash
sudo apt-get install -y libreoffice
libreoffice --version
```
Expected: `LibreOffice 7.x.x ...`

No Windows (desenvolvimento local): baixar em https://www.libreoffice.org/download/download/ — necessário apenas para testar a conversão PDF localmente.

- [ ] **Step 1.3: Criar script de template placeholder**

Criar `scripts/criar_template_placeholder.py`:

```python
"""Gera config/contrato_template.docx com todas as variáveis do sistema."""
import os
from docx import Document
from docx.shared import Pt

os.makedirs("config", exist_ok=True)

doc = Document()
doc.add_heading("CONTRATO DE COMPRA E VENDA", 0)

doc.add_paragraph("Cliente: {{ cliente_nome }}")
doc.add_paragraph("CPF: {{ cliente_cpf }}")
doc.add_paragraph("Endereço do Cliente: {{ cliente_endereco }}")
doc.add_paragraph("Telefone: {{ cliente_telefone }}")
doc.add_paragraph()
doc.add_paragraph("Endereço de Instalação: {{ endereco_instalacao }}")
doc.add_paragraph()
doc.add_heading("Projeto", level=1)
doc.add_paragraph("Projeto: {{ projeto_nome }}")
doc.add_paragraph("Data do Projeto: {{ projeto_data }}")
doc.add_paragraph("Orçamento: {{ orcamento_nome }}")
doc.add_paragraph()
doc.add_heading("Condições Comerciais", level=1)
doc.add_paragraph("Valor Total: {{ valor_total }}")
doc.add_paragraph("Forma de Pagamento: {{ forma_pagamento }}")
doc.add_paragraph("Entrada: {{ entrada_valor }}")
doc.add_paragraph("Parcelas: {{ parcelas_descricao }}")
doc.add_paragraph()
doc.add_heading("Ambientes", level=1)
doc.add_paragraph("{{ ambientes_lista }}")
doc.add_paragraph()
doc.add_heading("Assinaturas", level=1)
doc.add_paragraph("Consultor: {{ consultor_nome }}")
doc.add_paragraph("Data: {{ data_contrato }}")
doc.add_paragraph()
doc.add_heading("Adendo", level=1)
doc.add_paragraph("{{ adendo }}")

doc.save("config/contrato_template.docx")
print("Template criado em config/contrato_template.docx")
```

- [ ] **Step 1.4: Executar o script**

```bash
python scripts/criar_template_placeholder.py
```
Expected: `Template criado em config/contrato_template.docx`

Verificar: `config/contrato_template.docx` existe e tem ~5KB.

- [ ] **Step 1.5: Commit**

```bash
git add scripts/criar_template_placeholder.py config/contrato_template.docx
git commit -m "feat: template placeholder de contrato e dependência docxtpl"
```

---

## Task 2: Database — CicloEtapa, Contrato, ContratoAssinatura

**Files:**
- Modify: `database.py`

- [ ] **Step 2.1: Adicionar os três modelos ao final de `database.py`**

Inserir antes da linha `# ── Inicialização ─`:

```python
# ── Ciclo do Projeto ──────────────────────────────────────────────────────────

from sqlalchemy import UniqueConstraint

class CicloEtapa(Base):
    """Estado de cada etapa do pipeline por projeto."""
    __tablename__ = "ciclo_etapas"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    projeto_nome   = Column(Text,     nullable=False)   # nome_safe
    etapa_codigo   = Column(Text,     nullable=False)   # "7", "11b", "17a" etc.
    status         = Column(Text,     nullable=False, default="pendente")
    responsavel_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    iniciado_em    = Column(DateTime, nullable=True)
    concluido_em   = Column(DateTime, nullable=True)
    observacoes    = Column(Text,     nullable=True)

    __table_args__ = (UniqueConstraint("projeto_nome", "etapa_codigo", name="uq_ciclo_etapa"),)

    responsavel = relationship("Usuario", foreign_keys=[responsavel_id])


class Contrato(Base):
    """Contrato gerado a partir do orçamento aprovado."""
    __tablename__ = "contratos"

    id                   = Column(Integer,  primary_key=True, autoincrement=True)
    projeto_nome         = Column(Text,     nullable=False)
    orcamento_id         = Column(Integer,  ForeignKey("orcamentos.id"), nullable=False)
    template_path        = Column(Text,     nullable=False, default="config/contrato_template.docx")
    pdf_path             = Column(Text,     nullable=True)
    endereco_instalacao  = Column(Text,     nullable=True)
    status               = Column(Text,     nullable=False, default="rascunho")
    # status: rascunho | gerado | assinado_loja | assinado_cliente | vigente
    adendo               = Column(Text,     nullable=True)
    gerado_em            = Column(DateTime, nullable=True)
    gerado_por_id        = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    d4sign_uuid          = Column(Text,     nullable=True)   # fase futura D4Sign

    gerado_por   = relationship("Usuario",  foreign_keys=[gerado_por_id])
    orcamento    = relationship("Orcamento", foreign_keys=[orcamento_id])
    assinaturas  = relationship("ContratoAssinatura", back_populates="contrato",
                                cascade="all, delete-orphan")


class ContratoAssinatura(Base):
    """Registro de assinatura interna (MVP) ou confirmação D4Sign (futuro)."""
    __tablename__ = "contratos_assinaturas"

    id           = Column(Integer,  primary_key=True, autoincrement=True)
    contrato_id  = Column(Integer,  ForeignKey("contratos.id"), nullable=False)
    parte        = Column(Text,     nullable=False)   # loja | cliente
    nome         = Column(Text,     nullable=False)
    cpf          = Column(Text,     nullable=False)
    assinado_em  = Column(DateTime, nullable=False, default=datetime.utcnow)
    ip_origem    = Column(Text,     nullable=True)
    hash_sha256  = Column(Text,     nullable=False)

    contrato = relationship("Contrato", back_populates="assinaturas")
```

- [ ] **Step 2.2: Verificar que `init_db()` cria as tabelas**

`Base.metadata.create_all(ENGINE)` em `init_db()` já cobre tabelas novas — nenhuma mudança necessária nessa função.

- [ ] **Step 2.3: Testar criação das tabelas**

```bash
python -c "
from database import init_db, get_session, CicloEtapa, Contrato, ContratoAssinatura
init_db()
db = get_session()
# Verificar que as tabelas existem fazendo query
print('CicloEtapa:', db.query(CicloEtapa).count())
print('Contrato:', db.query(Contrato).count())
print('ContratoAssinatura:', db.query(ContratoAssinatura).count())
db.close()
print('OK - tabelas criadas')
"
```
Expected:
```
CicloEtapa: 0
Contrato: 0
ContratoAssinatura: 0
OK - tabelas criadas
```

- [ ] **Step 2.4: Commit**

```bash
git add database.py
git commit -m "feat: modelos CicloEtapa, Contrato e ContratoAssinatura"
```

---

## Task 3: mod_contrato.py — geração de PDF e hash de assinatura (TDD)

**Files:**
- Create: `tests/test_contrato.py`
- Create: `mod_contrato.py`

- [ ] **Step 3.1: Escrever os testes**

Criar `tests/test_contrato.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch, MagicMock
from mod_contrato import calcular_hash_assinatura, montar_variaveis_contrato, gerar_pdf_contrato


def test_hash_assinatura_determinístico():
    h1 = calcular_hash_assinatura("João Silva", "123.456.789-00", 42, "2026-06-15T10:00:00")
    h2 = calcular_hash_assinatura("João Silva", "123.456.789-00", 42, "2026-06-15T10:00:00")
    assert h1 == h2


def test_hash_assinatura_muda_com_dados_diferentes():
    h1 = calcular_hash_assinatura("João Silva", "123.456.789-00", 42, "2026-06-15T10:00:00")
    h2 = calcular_hash_assinatura("Maria Silva", "123.456.789-00", 42, "2026-06-15T10:00:00")
    assert h1 != h2


def test_hash_assinatura_formato_sha256():
    h = calcular_hash_assinatura("João", "000.000.000-00", 1, "2026-01-01T00:00:00")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_montar_variaveis_contrato_campos_obrigatorios():
    projeto = {
        "nome_projeto": "Cozinha Silva",
        "criado_em": "2026-06-15",
        "consultor": "Pedro",
    }
    cliente = {
        "nome": "Ana Silva",
        "cpf": "123.456.789-00",
        "telefone": "(11) 99999-9999",
        "logradouro": "Rua A",
        "numero": "100",
        "bairro": "Centro",
        "cidade": "SP",
        "estado": "SP",
    }
    orcamento = {
        "nome": "Orçamento 1",
        "valor_total": 48200.0,
        "forma_pagamento": "Boleto 12x",
        "ambientes": ["Cozinha", "Sala"],
    }
    variaveis = montar_variaveis_contrato(
        projeto=projeto,
        cliente=cliente,
        orcamento=orcamento,
        endereco_instalacao="Rua B, 200 - Centro - SP",
        entrada_valor=5000.0,
        parcelas_descricao="11x de R$ 3.927,27",
        adendo="",
    )
    assert variaveis["cliente_nome"] == "Ana Silva"
    assert variaveis["cliente_cpf"] == "123.456.789-00"
    assert variaveis["projeto_nome"] == "Cozinha Silva"
    assert variaveis["orcamento_nome"] == "Orçamento 1"
    assert "R$ 48.200,00" in variaveis["valor_total"]
    assert variaveis["endereco_instalacao"] == "Rua B, 200 - Centro - SP"
    assert variaveis["ambientes_lista"] == "Cozinha\nSala"
    assert variaveis["adendo"] == ""


def test_montar_variaveis_sem_adendo_retorna_string_vazia():
    variaveis = montar_variaveis_contrato(
        projeto={"nome_projeto": "P", "criado_em": "2026-01-01", "consultor": "X"},
        cliente={"nome": "C", "cpf": "", "telefone": "", "logradouro": "",
                 "numero": "", "bairro": "", "cidade": "", "estado": ""},
        orcamento={"nome": "O", "valor_total": 0.0, "forma_pagamento": "", "ambientes": []},
        endereco_instalacao="",
        entrada_valor=0.0,
        parcelas_descricao="",
        adendo=None,
    )
    assert variaveis["adendo"] == ""


def test_gerar_pdf_chama_libreoffice():
    variaveis = {
        "cliente_nome": "Teste", "cliente_cpf": "000", "cliente_endereco": "",
        "cliente_telefone": "", "endereco_instalacao": "", "projeto_nome": "P",
        "projeto_data": "2026-01-01", "orcamento_nome": "O1", "valor_total": "R$ 0,00",
        "forma_pagamento": "", "entrada_valor": "R$ 0,00", "parcelas_descricao": "",
        "ambientes_lista": "", "consultor_nome": "X", "data_contrato": "15/06/2026",
        "adendo": "",
    }
    with patch("mod_contrato.DocxTemplate") as mock_tpl, \
         patch("mod_contrato.subprocess.run") as mock_run, \
         patch("mod_contrato.os.path.exists", return_value=True):
        mock_doc = MagicMock()
        mock_tpl.return_value = mock_doc
        mock_run.return_value = MagicMock(returncode=0)

        resultado = gerar_pdf_contrato(contrato_id=99, variaveis=variaveis)

    assert mock_doc.render.called
    assert mock_doc.save.called
    assert mock_run.called
    assert "99" in resultado
```

- [ ] **Step 3.2: Executar os testes para verificar que falham**

```bash
python -m pytest tests/test_contrato.py -v
```
Expected: `ModuleNotFoundError: No module named 'mod_contrato'` ou `ImportError`.

- [ ] **Step 3.3: Implementar mod_contrato.py**

Criar `mod_contrato.py`:

```python
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
```

- [ ] **Step 3.4: Executar os testes para verificar que passam**

```bash
python -m pytest tests/test_contrato.py -v
```
Expected: todos os testes `PASSED`.

- [ ] **Step 3.5: Commit**

```bash
git add mod_contrato.py tests/test_contrato.py
git commit -m "feat: mod_contrato — geração de PDF e hash de assinatura (TDD)"
```

---

## Task 4: main.py — rotas do pipeline (GET/PATCH ciclo_etapas)

**Files:**
- Modify: `main.py`

- [ ] **Step 4.1: Adicionar imports necessários no topo de main.py**

Localizar a linha de imports do `database.py` (buscar por `from database import`) e adicionar `CicloEtapa, Contrato, ContratoAssinatura` à lista:

```python
from database import (
    init_db, get_session,
    Usuario, Sessao, LogAutorizacao, Cliente, Parceiro,
    Projeto, PoolAmbiente, Orcamento, OrcamentoAmbiente,
    CicloEtapa, Contrato, ContratoAssinatura,          # ← adicionar
    upsert_projeto_status,
)
```

Adicionar também na seção de imports do topo:

```python
from mod_contrato import calcular_hash_assinatura, montar_variaveis_contrato, gerar_pdf_contrato
```

- [ ] **Step 4.2: Adicionar rota GET /api/projetos/\<nome\>/ciclo em do_GET**

Localizar o bloco que termina com `self.send_json({"ok": False, "erro": "Rota nao encontrada"})` no final do `do_GET` (antes do `except`) e inserir antes dele:

```python
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo$', path)
            if m:
                nome_safe = unquote(m.group(1))
                db = get_session()
                try:
                    etapas = db.query(CicloEtapa)\
                               .filter_by(projeto_nome=nome_safe)\
                               .order_by(CicloEtapa.etapa_codigo)\
                               .all()
                    resultado = [{
                        "etapa_codigo":  e.etapa_codigo,
                        "status":        e.status,
                        "responsavel_id": e.responsavel_id,
                        "iniciado_em":   e.iniciado_em.isoformat() if e.iniciado_em else None,
                        "concluido_em":  e.concluido_em.isoformat() if e.concluido_em else None,
                        "observacoes":   e.observacoes or "",
                    } for e in etapas]
                    self.send_json({"ok": True, "ciclo": resultado})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/contrato/pdf$', path)
            if m:
                nome_safe = unquote(m.group(1))
                db = get_session()
                try:
                    contrato = db.query(Contrato)\
                                 .filter_by(projeto_nome=nome_safe)\
                                 .order_by(Contrato.id.desc())\
                                 .first()
                    if not contrato or not contrato.pdf_path or not os.path.exists(contrato.pdf_path):
                        self.send_json({"ok": False, "erro": "PDF não encontrado"}, code=404)
                        return
                    with open(contrato.pdf_path, 'rb') as f:
                        pdf_data = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/pdf")
                    self.send_header("Content-Length", len(pdf_data))
                    self.send_header("Content-Disposition",
                                     f'inline; filename="contrato_{nome_safe}.pdf"')
                    self.end_headers()
                    self.wfile.write(pdf_data)
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/contrato$', path)
            if m:
                nome_safe = unquote(m.group(1))
                db = get_session()
                try:
                    contrato = db.query(Contrato)\
                                 .filter_by(projeto_nome=nome_safe)\
                                 .order_by(Contrato.id.desc())\
                                 .first()
                    if not contrato:
                        self.send_json({"ok": True, "contrato": None})
                        return
                    assinaturas = [{
                        "parte":       a.parte,
                        "nome":        a.nome,
                        "assinado_em": a.assinado_em.isoformat(),
                    } for a in contrato.assinaturas]
                    self.send_json({"ok": True, "contrato": {
                        "id":                   contrato.id,
                        "status":               contrato.status,
                        "endereco_instalacao":  contrato.endereco_instalacao or "",
                        "adendo":               contrato.adendo or "",
                        "gerado_em":            contrato.gerado_em.isoformat() if contrato.gerado_em else None,
                        "tem_pdf":              bool(contrato.pdf_path and os.path.exists(contrato.pdf_path)),
                        "assinaturas":          assinaturas,
                    }})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return
```

- [ ] **Step 4.3: Adicionar rota PATCH /api/projetos/\<nome\>/ciclo/\<etapa\> em do_PATCH**

Localizar `do_PATCH` e adicionar antes do `self.send_json({"ok": False, "erro": "Rota não encontrada"})` final:

```python
            m = re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)$', path)
            if m:
                nome_safe   = unquote(m.group(1))
                etapa_cod   = unquote(m.group(2))
                usuario     = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                req = json.loads(body)
                novo_status = req.get("status", "").strip()
                obs         = req.get("observacoes")
                db = get_session()
                try:
                    etapa = db.query(CicloEtapa).filter_by(
                        projeto_nome=nome_safe, etapa_codigo=etapa_cod
                    ).first()
                    if not etapa:
                        etapa = CicloEtapa(projeto_nome=nome_safe, etapa_codigo=etapa_cod)
                        db.add(etapa)
                    if novo_status:
                        if etapa.status == "pendente" and novo_status != "pendente":
                            etapa.iniciado_em = datetime.utcnow()
                        etapa.status = novo_status
                        if novo_status in ("concluido", "aprovado", "vigente", "implantado",
                                           "realizado", "entregue", "emitida"):
                            etapa.concluido_em  = datetime.utcnow()
                            etapa.responsavel_id = usuario.id
                    if obs is not None:
                        etapa.observacoes = obs
                    db.commit()
                    self.send_json({"ok": True, "etapa_codigo": etapa_cod, "status": etapa.status})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return
```

- [ ] **Step 4.4: Testar rotas do ciclo manualmente**

Iniciar o servidor: `python main.py`

```bash
# GET ciclo de um projeto existente (substitua "MeuProjeto" por nome real)
curl http://127.0.0.1:8765/api/projetos/MeuProjeto/ciclo \
  -H "Cookie: sessao=<token_valido>"
```
Expected: `{"ok": true, "ciclo": []}`

```bash
# PATCH para criar etapa 7 como pendente
curl -X PATCH http://127.0.0.1:8765/api/projetos/MeuProjeto/ciclo/7 \
  -H "Cookie: sessao=<token_valido>" \
  -H "Content-Type: application/json" \
  -d '{"status": "em_andamento"}'
```
Expected: `{"ok": true, "etapa_codigo": "7", "status": "em_andamento"}`

- [ ] **Step 4.5: Commit**

```bash
git add main.py
git commit -m "feat: rotas GET/PATCH ciclo_etapas e GET contrato + PDF"
```

---

## Task 5: main.py — rotas de geração, adendo e assinatura do contrato

**Files:**
- Modify: `main.py`

- [ ] **Step 5.1: Adicionar helper `_montar_dados_projeto_para_contrato`**

Adicionar no bloco de helpers no final de `main.py` (após `_orcamento_dict`):

```python
def _montar_dados_projeto_para_contrato(nome_safe: str, orcamento_id: int, db) -> tuple:
    """
    Retorna (projeto_dict, cliente_dict, orcamento_dict) para geração do contrato.
    Lança ValueError se dados essenciais estiverem faltando.
    """
    import json as _json
    proj_path = os.path.join("PROJETOS", nome_safe, "projeto.json")
    if not os.path.exists(proj_path):
        raise ValueError(f"Projeto não encontrado: {nome_safe}")
    with open(proj_path, encoding="utf-8") as f:
        proj = _json.load(f)

    orcamento = db.get(Orcamento, orcamento_id)
    if not orcamento or orcamento.projeto_id != nome_safe:
        raise ValueError(f"Orçamento {orcamento_id} não pertence ao projeto {nome_safe}")

    ambientes_orc = db.query(OrcamentoAmbiente)\
                      .filter_by(orcamento_id=orcamento_id)\
                      .join(PoolAmbiente)\
                      .all()
    nomes_ambientes = [oa.pool_ambiente.nome_exibicao for oa in ambientes_orc]

    cliente_id = proj.get("cliente_id")
    cliente = db.get(Cliente, cliente_id) if cliente_id else None

    projeto_dict = {
        "nome_projeto": proj.get("nome_projeto", nome_safe),
        "criado_em":    proj.get("criado_em", ""),
        "consultor":    proj.get("consultor_nome", ""),
    }
    cliente_dict = {
        "nome":       cliente.nome       if cliente else proj.get("nome_cliente", ""),
        "cpf":        cliente.cpf        if cliente else "",
        "telefone":   cliente.telefone   if cliente else "",
        "logradouro": cliente.logradouro if cliente else "",
        "numero":     cliente.numero     if cliente else "",
        "bairro":     cliente.bairro     if cliente else "",
        "cidade":     cliente.cidade     if cliente else "",
        "estado":     cliente.estado     if cliente else "",
    } if cliente else {
        "nome": proj.get("nome_cliente", ""), "cpf": "", "telefone": "",
        "logradouro": "", "numero": "", "bairro": "", "cidade": "", "estado": "",
    }
    orcamento_dict = {
        "nome":            orcamento.nome,
        "valor_total":     orcamento.valor_total or 0.0,
        "forma_pagamento": orcamento.forma_pagamento or "",
        "ambientes":       nomes_ambientes,
    }
    return projeto_dict, cliente_dict, orcamento_dict
```

- [ ] **Step 5.2: Adicionar rotas POST e PATCH /contrato em do_POST e do_PATCH**

Em `do_POST`, antes do `self.send_json({"ok": False, "erro": "Rota não encontrada"})` final:

```python
            # POST /api/projetos/<nome>/contrato — gera PDF do contrato
            m = _re.match(r'^/api/projetos/([^/]+)/contrato$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario   = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                req                  = json.loads(body)
                orcamento_id         = req.get("orcamento_id")
                endereco_instalacao  = (req.get("endereco_instalacao") or "").strip()
                entrada_valor        = float(req.get("entrada_valor") or 0)
                parcelas_descricao   = req.get("parcelas_descricao") or ""
                adendo               = req.get("adendo") or ""
                if not orcamento_id:
                    self.send_json({"ok": False, "erro": "orcamento_id obrigatório"}, code=400)
                    return
                db = get_session()
                try:
                    projeto_dict, cliente_dict, orcamento_dict = \
                        _montar_dados_projeto_para_contrato(nome_safe, orcamento_id, db)
                    variaveis = montar_variaveis_contrato(
                        projeto=projeto_dict,
                        cliente=cliente_dict,
                        orcamento=orcamento_dict,
                        endereco_instalacao=endereco_instalacao,
                        entrada_valor=entrada_valor,
                        parcelas_descricao=parcelas_descricao,
                        adendo=adendo,
                    )
                    contrato = db.query(Contrato).filter_by(projeto_nome=nome_safe)\
                                 .order_by(Contrato.id.desc()).first()
                    if not contrato:
                        contrato = Contrato(projeto_nome=nome_safe, orcamento_id=orcamento_id)
                        db.add(contrato)
                        db.flush()
                    contrato.endereco_instalacao = endereco_instalacao
                    contrato.adendo              = adendo
                    contrato.gerado_em           = datetime.utcnow()
                    contrato.gerado_por_id       = usuario.id
                    contrato.status              = "rascunho"
                    db.commit()
                    pdf_path = gerar_pdf_contrato(contrato.id, variaveis)
                    contrato.pdf_path = pdf_path
                    contrato.status   = "gerado"
                    db.commit()
                    self.send_json({"ok": True, "contrato_id": contrato.id, "status": "gerado"})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/contrato/assinar — registra assinatura
            m = _re.match(r'^/api/projetos/([^/]+)/contrato/assinar$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario   = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                req   = json.loads(body)
                parte = (req.get("parte") or "").strip()   # loja | cliente
                nome  = (req.get("nome")  or "").strip()
                cpf   = (req.get("cpf")   or "").strip()
                if parte not in ("loja", "cliente"):
                    self.send_json({"ok": False, "erro": "parte deve ser 'loja' ou 'cliente'"}, code=400)
                    return
                if not nome or not cpf:
                    self.send_json({"ok": False, "erro": "nome e cpf são obrigatórios"}, code=400)
                    return
                db = get_session()
                try:
                    contrato = db.query(Contrato).filter_by(projeto_nome=nome_safe)\
                                 .order_by(Contrato.id.desc()).first()
                    if not contrato:
                        self.send_json({"ok": False, "erro": "Contrato não encontrado"}, code=404)
                        return
                    if contrato.status == "vigente":
                        self.send_json({"ok": False, "erro": "Contrato já está vigente"}, code=400)
                        return
                    ja_assinou = any(a.parte == parte for a in contrato.assinaturas)
                    if ja_assinou:
                        self.send_json({"ok": False, "erro": f"Parte '{parte}' já assinou"}, code=400)
                        return
                    timestamp = datetime.utcnow().isoformat()
                    ip        = self.client_address[0] if self.client_address else ""
                    hash_sig  = calcular_hash_assinatura(nome, cpf, contrato.id, timestamp)
                    assinatura = ContratoAssinatura(
                        contrato_id=contrato.id,
                        parte=parte,
                        nome=nome,
                        cpf=cpf,
                        assinado_em=datetime.utcnow(),
                        ip_origem=ip,
                        hash_sha256=hash_sig,
                    )
                    db.add(assinatura)
                    partes_assinadas = {a.parte for a in contrato.assinaturas} | {parte}
                    if "loja" in partes_assinadas and "cliente" in partes_assinadas:
                        contrato.status = "vigente"
                        # Avança etapa 7 do ciclo para concluída
                        etapa7 = db.query(CicloEtapa).filter_by(
                            projeto_nome=nome_safe, etapa_codigo="7"
                        ).first()
                        if not etapa7:
                            etapa7 = CicloEtapa(projeto_nome=nome_safe, etapa_codigo="7")
                            db.add(etapa7)
                        etapa7.status       = "vigente"
                        etapa7.concluido_em = datetime.utcnow()
                        etapa7.responsavel_id = usuario.id
                    elif parte == "loja":
                        contrato.status = "assinado_loja"
                    else:
                        contrato.status = "assinado_cliente"
                    db.commit()
                    self.send_json({"ok": True, "status": contrato.status, "parte": parte})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return
```

Em `do_PATCH`, adicionar rota PATCH /api/projetos/\<nome\>/contrato (atualizar adendo e regenerar PDF):

```python
            m = re.match(r'^/api/projetos/([^/]+)/contrato$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario   = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                req    = json.loads(body)
                adendo = req.get("adendo") or ""
                db = get_session()
                try:
                    contrato = db.query(Contrato).filter_by(projeto_nome=nome_safe)\
                                 .order_by(Contrato.id.desc()).first()
                    if not contrato:
                        self.send_json({"ok": False, "erro": "Contrato não encontrado"}, code=404)
                        return
                    if contrato.status == "vigente":
                        self.send_json({"ok": False,
                                        "erro": "Contrato vigente não pode ser editado"}, code=400)
                        return
                    contrato.adendo = adendo
                    db.commit()
                    projeto_dict, cliente_dict, orcamento_dict = \
                        _montar_dados_projeto_para_contrato(nome_safe, contrato.orcamento_id, db)
                    variaveis = montar_variaveis_contrato(
                        projeto=projeto_dict, cliente=cliente_dict,
                        orcamento=orcamento_dict,
                        endereco_instalacao=contrato.endereco_instalacao or "",
                        entrada_valor=0.0, parcelas_descricao="",
                        adendo=adendo,
                    )
                    pdf_path = gerar_pdf_contrato(contrato.id, variaveis)
                    contrato.pdf_path = pdf_path
                    db.commit()
                    self.send_json({"ok": True, "status": contrato.status})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return
```

- [ ] **Step 5.3: Testar geração de contrato via curl**

Com o servidor rodando e um projeto com orçamento existente:

```bash
curl -X POST http://127.0.0.1:8765/api/projetos/MeuProjeto/contrato \
  -H "Cookie: sessao=<token_valido>" \
  -H "Content-Type: application/json" \
  -d '{
    "orcamento_id": 1,
    "endereco_instalacao": "Rua das Flores, 100 - Centro - SP",
    "entrada_valor": 5000,
    "parcelas_descricao": "11x de R$ 3.927,27"
  }'
```
Expected: `{"ok": true, "contrato_id": 1, "status": "gerado"}`

Verificar que `CONTRATOS/contrato_1.pdf` foi criado.

```bash
curl http://127.0.0.1:8765/api/projetos/MeuProjeto/contrato \
  -H "Cookie: sessao=<token_valido>"
```
Expected: `{"ok": true, "contrato": {"id": 1, "status": "gerado", "tem_pdf": true, ...}}`

- [ ] **Step 5.4: Commit**

```bash
git add main.py
git commit -m "feat: rotas POST/PATCH contrato e POST contrato/assinar"
```

---

## Task 6: Frontend — aba "Ciclo" em page-02

**Files:**
- Modify: `static/index.html`

- [ ] **Step 6.1: Adicionar botão "Ciclo" no cabeçalho de page-02**

Localizar em `static/index.html` o cabeçalho de page-02 (buscar por `id="page-02"` ou pelo botão de status do projeto). Adicionar o botão "Ciclo" ao lado dos controles existentes do projeto:

```html
<!-- Adicionar junto aos controles de navegação do projeto em page-02 -->
<button id="btn-abrir-ciclo" class="btn-ciclo" onclick="abrirCiclo()" title="Ciclo do Projeto">
  ⟳ Ciclo
</button>
```

- [ ] **Step 6.2: Adicionar CSS para a aba Ciclo**

Localizar a seção `<style>` em `index.html` e adicionar:

```css
/* ── Ciclo do Projeto ── */
.btn-ciclo {
  background: var(--section, #1a2a1a);
  color: var(--ok, #4caf82);
  border: 1px solid var(--ok, #4caf82);
  border-radius: 4px;
  padding: 4px 12px;
  font-size: .85rem;
  cursor: pointer;
  margin-left: 8px;
}
.btn-ciclo:hover { background: var(--ok, #4caf82); color: #000; }

#ciclo-panel {
  display: none;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  max-width: 720px;
  margin: 0 auto;
}
#ciclo-panel.ativo { display: flex; }

.ciclo-card {
  background: var(--card, #132013);
  border: 1px solid var(--border, #2a3a2a);
  border-radius: 6px;
  padding: 12px 16px;
}
.ciclo-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}
.ciclo-card-header .etapa-num {
  font-size: .75rem;
  color: var(--muted, #6a7a6a);
  min-width: 28px;
}
.ciclo-card-header .etapa-nome { flex: 1; font-weight: 500; }
.ciclo-card-header .etapa-badge {
  font-size: .75rem;
  padding: 2px 8px;
  border-radius: 10px;
}
.badge-pendente    { background: #2a2a1a; color: var(--warn, #c8a84b); }
.badge-em_andamento{ background: #1a2a2a; color: var(--section, #4b8bc8); }
.badge-vigente,
.badge-concluido,
.badge-aprovado    { background: #1a2a1a; color: var(--ok, #4caf82); }
.badge-bloqueado   { background: #1a1a1a; color: var(--muted, #6a7a6a); }

.ciclo-card-body {
  display: none;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border, #2a3a2a);
}
.ciclo-card-body.aberto { display: block; }
```

- [ ] **Step 6.3: Adicionar div #ciclo-panel no HTML de page-02**

Logo após o elemento que contém a barra de orçamentos em page-02, adicionar:

```html
<div id="ciclo-panel">
  <!-- preenchido por renderCiclo() -->
</div>
```

- [ ] **Step 6.4: Adicionar JS para ciclo**

Localizar a seção de scripts JS no final do `index.html` e adicionar:

```js
// ── Ciclo do Projeto ──────────────────────────────────────────────────────────

const ETAPAS_CICLO = [
  { codigo: "1",   nome: "Captação do cliente",               sub: false },
  { codigo: "2",   nome: "Briefing",                          sub: false },
  { codigo: "3",   nome: "Criação do projeto",                sub: false },
  { codigo: "4",   nome: "Primeiro orçamento",                sub: false },
  { codigo: "5",   nome: "Revisão de projeto",                sub: false },
  { codigo: "6",   nome: "Aprovação do orçamento pelo cliente", sub: false },
  { codigo: "7",   nome: "Contrato",                          sub: false, acao: "contrato" },
  { codigo: "8",   nome: "Aprovação financeira I",            sub: false },
  { codigo: "9",   nome: "Solicitação de medição",            sub: false },
  { codigo: "10",  nome: "Planta de pontos medidos",          sub: false },
  { codigo: "11",  nome: "Projeto executivo",                 sub: false },
  { codigo: "11a", nome: "Planta de pontos de PE",            sub: true },
  { codigo: "11b", nome: "Reunião de alinhamento",            sub: true },
  { codigo: "11c", nome: "Revisão de PE",                     sub: true },
  { codigo: "11d", nome: "Aprovação financeira II",           sub: true },
  { codigo: "11e", nome: "Aprovação do PE pelo cliente",      sub: true },
  { codigo: "12",  nome: "Implantação do pedido",             sub: false },
  { codigo: "13",  nome: "Produção",                          sub: false },
  { codigo: "14",  nome: "Entrega no depósito",               sub: false },
  { codigo: "15",  nome: "Emissão da NFe do cliente",         sub: false },
  { codigo: "16",  nome: "Entrega no cliente",                sub: false },
  { codigo: "17",  nome: "Montagem",                          sub: false },
  { codigo: "17a", nome: "Pendências de montagem",            sub: true },
  { codigo: "18",  nome: "Assistência pós Montagem",          sub: false },
  { codigo: "19",  nome: "Vistoria final",                    sub: false },
  { codigo: "20",  nome: "Aprovação final",                   sub: false },
];

let _cicloAberto = false;
let _cicloData   = {};

function abrirCiclo() {
  _cicloAberto = true;
  document.getElementById('ciclo-panel').classList.add('ativo');
  // oculta área de negociação
  const negArea = document.getElementById('neg-area') || document.querySelector('.neg-container');
  if (negArea) negArea.style.display = 'none';
  carregarCiclo();
}

function fecharCiclo() {
  _cicloAberto = false;
  document.getElementById('ciclo-panel').classList.remove('ativo');
  const negArea = document.getElementById('neg-area') || document.querySelector('.neg-container');
  if (negArea) negArea.style.display = '';
}

async function carregarCiclo() {
  if (!_projetoAtivo) return;
  try {
    const r = await fetch(`/api/projetos/${encodeURIComponent(_projetoAtivo)}/ciclo`,
                          { credentials: 'same-origin' });
    const d = await r.json();
    if (!d.ok) return;
    _cicloData = {};
    for (const e of (d.ciclo || [])) _cicloData[e.etapa_codigo] = e;
    renderCiclo();
  } catch(e) { console.error('Erro ao carregar ciclo:', e); }
}

function renderCiclo() {
  const panel = document.getElementById('ciclo-panel');
  if (!panel) return;
  panel.innerHTML = `
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
      <h3 style="margin:0;color:var(--ok)">Ciclo do Projeto</h3>
      <button onclick="fecharCiclo()" style="margin-left:auto;background:none;border:none;
        color:var(--muted);cursor:pointer;font-size:1.1rem">✕ Negociação</button>
    </div>
  `;
  for (const etapa of ETAPAS_CICLO) {
    const dados  = _cicloData[etapa.codigo] || {};
    const status = dados.status || (etapa.codigo <= "6" ? "concluido" : "bloqueado");
    const badge  = `<span class="etapa-badge badge-${status}">${status}</span>`;
    const indent = etapa.sub ? 'margin-left:24px;' : '';
    const card   = document.createElement('div');
    card.className = 'ciclo-card';
    card.style.cssText = indent;
    card.innerHTML = `
      <div class="ciclo-card-header" onclick="toggleCicloCard('${etapa.codigo}')">
        <span class="etapa-num">${etapa.codigo}</span>
        <span class="etapa-nome">${etapa.nome}</span>
        ${badge}
      </div>
      <div class="ciclo-card-body" id="ciclo-body-${etapa.codigo}">
        ${etapa.acao === 'contrato' ? _renderCardContrato() : _renderCardGenerico(etapa, dados)}
      </div>
    `;
    panel.appendChild(card);
  }
}

function toggleCicloCard(codigo) {
  const body = document.getElementById(`ciclo-body-${codigo}`);
  if (body) body.classList.toggle('aberto');
  if (codigo === '7' && !document.getElementById('ciclo-body-7').classList.contains('aberto')) return;
  if (codigo === '7') carregarDadosContrato();
}

function _renderCardGenerico(etapa, dados) {
  return `<p style="color:var(--muted);font-size:.85rem;margin:0">
    ${dados.observacoes || 'Nenhuma informação registrada.'}
  </p>`;
}

function _renderCardContrato() {
  return `<div id="contrato-ui">
    <p style="color:var(--muted);font-size:.85rem">Carregando...</p>
  </div>`;
}

async function carregarDadosContrato() {
  if (!_projetoAtivo) return;
  const r = await fetch(`/api/projetos/${encodeURIComponent(_projetoAtivo)}/contrato`,
                        { credentials: 'same-origin' });
  const d = await r.json();
  renderContratoUI(d.contrato);
}

function renderContratoUI(contrato) {
  const ui = document.getElementById('contrato-ui');
  if (!ui) return;
  if (!contrato) {
    ui.innerHTML = `
      <p style="color:var(--muted);font-size:.85rem;margin-bottom:8px">
        Nenhum contrato gerado. Preencha os dados e gere o contrato.
      </p>
      ${_formGerarContrato()}
    `;
    return;
  }
  const temPdf = contrato.tem_pdf;
  const status = contrato.status;
  ui.innerHTML = `
    <div style="display:flex;gap:8px;align-items:center;margin-bottom:12px">
      <strong>Status:</strong>
      <span class="etapa-badge badge-${status}">${status}</span>
    </div>
    ${temPdf ? `
      <div style="margin-bottom:12px">
        <iframe src="/api/projetos/${encodeURIComponent(_projetoAtivo)}/contrato/pdf"
                style="width:100%;height:480px;border:1px solid var(--border);border-radius:4px"></iframe>
        <div style="display:flex;gap:8px;margin-top:8px">
          <a href="/api/projetos/${encodeURIComponent(_projetoAtivo)}/contrato/pdf"
             target="_blank" class="btn-ciclo" style="text-decoration:none">
            ⬇ Baixar PDF
          </a>
          ${status !== 'vigente' ? `<button onclick="abrirModalAdendo()" class="btn-ciclo">Editar Adendo</button>` : ''}
        </div>
      </div>
    ` : ''}
    ${status !== 'vigente' ? `
      <div style="margin-top:12px">
        <strong style="font-size:.85rem">Assinaturas:</strong>
        ${_renderAssinaturas(contrato.assinaturas)}
      </div>
    ` : '<p style="color:var(--ok)">✓ Contrato vigente — ambas as partes assinaram.</p>'}
  `;
}

function _formGerarContrato() {
  return `
    <div style="display:flex;flex-direction:column;gap:8px;max-width:480px">
      <label style="font-size:.85rem">Endereço de instalação</label>
      <div style="display:flex;gap:6px;align-items:center">
        <input id="ctrt-end-instalacao" type="text" placeholder="Rua, nº - Bairro - Cidade/UF"
          style="flex:1;background:var(--input,#0d1a0d);border:1px solid var(--border);
          color:var(--fg);padding:6px;border-radius:4px;font-size:.85rem">
        <button onclick="copiarEnderecoCliente()" title="Copiar endereço do cliente"
          style="background:none;border:1px solid var(--border);color:var(--muted);
          padding:4px 8px;border-radius:4px;cursor:pointer;font-size:.8rem">= Cliente</button>
      </div>
      <label style="font-size:.85rem">Entrada (R$)</label>
      <input id="ctrt-entrada" type="number" value="0" min="0" step="100"
        style="background:var(--input,#0d1a0d);border:1px solid var(--border);
        color:var(--fg);padding:6px;border-radius:4px;font-size:.85rem">
      <label style="font-size:.85rem">Descrição das parcelas</label>
      <input id="ctrt-parcelas" type="text" placeholder="ex: 10x de R$ 4.820,00"
        style="background:var(--input,#0d1a0d);border:1px solid var(--border);
        color:var(--fg);padding:6px;border-radius:4px;font-size:.85rem">
      <label style="font-size:.85rem">Adendo (opcional)</label>
      <textarea id="ctrt-adendo" rows="3"
        style="background:var(--input,#0d1a0d);border:1px solid var(--border);
        color:var(--fg);padding:6px;border-radius:4px;font-size:.85rem;resize:vertical"></textarea>
      <button onclick="gerarContrato()" class="btn-ciclo" style="align-self:flex-start">
        Gerar Contrato
      </button>
    </div>
  `;
}

function _renderAssinaturas(lista) {
  const partes = ['loja', 'cliente'];
  return partes.map(parte => {
    const ass = (lista || []).find(a => a.parte === parte);
    return ass
      ? `<div style="color:var(--ok);font-size:.85rem">✓ ${parte}: ${ass.nome} — ${ass.assinado_em.slice(0,10)}</div>`
      : `<div style="display:flex;gap:8px;align-items:center;margin-top:6px">
           <span style="color:var(--muted);font-size:.85rem">⬜ ${parte}</span>
           <button onclick="abrirModalAssinatura('${parte}')" class="btn-ciclo" style="padding:2px 8px;font-size:.8rem">
             Assinar como ${parte}
           </button>
         </div>`;
  }).join('');
}

function copiarEnderecoCliente() {
  // Tenta buscar endereço do cliente do projeto ativo
  fetch(`/api/projetos/${encodeURIComponent(_projetoAtivo)}`, { credentials: 'same-origin' })
    .then(r => r.json())
    .then(d => {
      const c = d.projeto?.cliente;
      if (!c) return;
      const end = [c.logradouro, c.numero, c.bairro, c.cidade, c.estado].filter(Boolean).join(', ');
      const input = document.getElementById('ctrt-end-instalacao');
      if (input && end) { input.value = end; }
    });
}

async function gerarContrato() {
  const endInstalacao = (document.getElementById('ctrt-end-instalacao')?.value || '').trim();
  const entrada       = parseFloat(document.getElementById('ctrt-entrada')?.value || '0');
  const parcelas      = (document.getElementById('ctrt-parcelas')?.value || '').trim();
  const adendo        = (document.getElementById('ctrt-adendo')?.value || '').trim();
  if (!_orcamentoAtivoId) { mostrarToast('Selecione um orçamento antes de gerar o contrato.', 'erro'); return; }
  if (!endInstalacao) {
    if (!confirm('Endereço de instalação não preenchido. Usar endereço do cliente?')) return;
    await copiarEnderecoCliente();
  }
  mostrarToast('Gerando contrato...', 'info');
  try {
    const r = await fetch(`/api/projetos/${encodeURIComponent(_projetoAtivo)}/contrato`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        orcamento_id:        _orcamentoAtivoId,
        endereco_instalacao: endInstalacao,
        entrada_valor:       entrada,
        parcelas_descricao:  parcelas,
        adendo:              adendo,
      }),
    });
    const d = await r.json();
    if (!d.ok) { mostrarToast('Erro: ' + d.erro, 'erro'); return; }
    mostrarToast('Contrato gerado com sucesso!', 'ok');
    carregarDadosContrato();
  } catch(e) { mostrarToast('Erro de rede: ' + e.message, 'erro'); }
}

function abrirModalAssinatura(parte) {
  const overlay = document.createElement('div');
  overlay.id = 'modal-assinatura-overlay';
  overlay.style.cssText = `position:fixed;inset:0;background:rgba(0,0,0,.7);
    z-index:9999;display:flex;align-items:center;justify-content:center`;
  overlay.innerHTML = `
    <div style="background:var(--card,#132013);border:1px solid var(--border);
      border-radius:8px;padding:24px;min-width:360px;max-width:480px">
      <h4 style="margin:0 0 16px">Assinar como: <strong>${parte}</strong></h4>
      <label style="font-size:.85rem">Nome completo</label>
      <input id="sig-nome" type="text" placeholder="Nome completo"
        style="width:100%;box-sizing:border-box;background:var(--input,#0d1a0d);
        border:1px solid var(--border);color:var(--fg);padding:8px;
        border-radius:4px;margin:4px 0 12px;font-size:.85rem">
      <label style="font-size:.85rem">CPF</label>
      <input id="sig-cpf" type="text" placeholder="000.000.000-00"
        style="width:100%;box-sizing:border-box;background:var(--input,#0d1a0d);
        border:1px solid var(--border);color:var(--fg);padding:8px;
        border-radius:4px;margin:4px 0 12px;font-size:.85rem">
      <label style="display:flex;gap:8px;align-items:center;margin-bottom:16px;font-size:.85rem">
        <input type="checkbox" id="sig-aceite">
        Li e aceito os termos do contrato
      </label>
      <div style="display:flex;gap:8px;justify-content:flex-end">
        <button onclick="fecharModalAssinatura()" class="btn-ciclo"
          style="border-color:var(--muted);color:var(--muted)">Cancelar</button>
        <button onclick="confirmarAssinatura('${parte}')" class="btn-ciclo">Confirmar Assinatura</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);
}

function fecharModalAssinatura() {
  const el = document.getElementById('modal-assinatura-overlay');
  if (el) el.remove();
}

async function confirmarAssinatura(parte) {
  const nome   = (document.getElementById('sig-nome')?.value || '').trim();
  const cpf    = (document.getElementById('sig-cpf')?.value || '').trim();
  const aceite = document.getElementById('sig-aceite')?.checked;
  if (!nome || !cpf) { mostrarToast('Nome e CPF são obrigatórios.', 'erro'); return; }
  if (!aceite) { mostrarToast('É necessário aceitar os termos.', 'erro'); return; }
  try {
    const r = await fetch(`/api/projetos/${encodeURIComponent(_projetoAtivo)}/contrato/assinar`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ parte, nome, cpf }),
    });
    const d = await r.json();
    if (!d.ok) { mostrarToast('Erro: ' + d.erro, 'erro'); return; }
    mostrarToast(`✓ Assinatura da ${parte} registrada.`, 'ok');
    fecharModalAssinatura();
    carregarDadosContrato();
    carregarCiclo();
  } catch(e) { mostrarToast('Erro de rede: ' + e.message, 'erro'); }
}

function abrirModalAdendo() {
  fetch(`/api/projetos/${encodeURIComponent(_projetoAtivo)}/contrato`, { credentials: 'same-origin' })
    .then(r => r.json())
    .then(d => {
      const adendo = d.contrato?.adendo || '';
      const overlay = document.createElement('div');
      overlay.id = 'modal-adendo-overlay';
      overlay.style.cssText = `position:fixed;inset:0;background:rgba(0,0,0,.7);
        z-index:9999;display:flex;align-items:center;justify-content:center`;
      overlay.innerHTML = `
        <div style="background:var(--card,#132013);border:1px solid var(--border);
          border-radius:8px;padding:24px;min-width:400px;max-width:560px">
          <h4 style="margin:0 0 12px">Editar Adendo</h4>
          <textarea id="adendo-texto" rows="6" style="width:100%;box-sizing:border-box;
            background:var(--input,#0d1a0d);border:1px solid var(--border);color:var(--fg);
            padding:8px;border-radius:4px;font-size:.85rem;resize:vertical">${adendo}</textarea>
          <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px">
            <button onclick="document.getElementById('modal-adendo-overlay').remove()"
              class="btn-ciclo" style="border-color:var(--muted);color:var(--muted)">Cancelar</button>
            <button onclick="salvarAdendo()" class="btn-ciclo">Salvar e Regenerar PDF</button>
          </div>
        </div>
      `;
      document.body.appendChild(overlay);
    });
}

async function salvarAdendo() {
  const adendo = document.getElementById('adendo-texto')?.value || '';
  const r = await fetch(`/api/projetos/${encodeURIComponent(_projetoAtivo)}/contrato`, {
    method: 'PATCH',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ adendo }),
  });
  const d = await r.json();
  document.getElementById('modal-adendo-overlay')?.remove();
  if (d.ok) { mostrarToast('Adendo salvo e PDF regenerado.', 'ok'); carregarDadosContrato(); }
  else mostrarToast('Erro: ' + d.erro, 'erro');
}
```

- [ ] **Step 6.5: Testar a aba Ciclo no browser**

1. Abrir `http://127.0.0.1:8765` e fazer login
2. Abrir um projeto → confirmar que botão "⟳ Ciclo" aparece no cabeçalho de page-02
3. Clicar em "⟳ Ciclo" → painel de ciclo aparece com todos os cards das 26 etapas
4. Clicar no card "7 — Contrato" → expande mostrando o formulário de geração
5. Clicar "✕ Negociação" → painel fecha, tela de negociação volta
6. Verificar que cards das etapas 1-6 aparecem como "concluido"

- [ ] **Step 6.6: Commit**

```bash
git add static/index.html
git commit -m "feat: aba Ciclo em page-02 com pipeline de 20 etapas e UI do contrato"
```

---

## Task 7: Teste de ponta a ponta e ajustes finais

**Files:**
- Nenhum arquivo novo — verificação funcional

- [ ] **Step 7.1: Executar todos os testes**

```bash
python -m pytest tests/ -v
```
Expected: todos os testes passando.

- [ ] **Step 7.2: Teste do fluxo completo de contrato**

Com o servidor rodando:

1. Login como consultor ou gerente
2. Abrir projeto com orçamento ativo
3. Clicar em "⟳ Ciclo" → abrir card 7
4. Preencher endereço de instalação (ou usar "= Cliente"), entrada e parcelas
5. Clicar "Gerar Contrato" → toast "Contrato gerado com sucesso!"
6. Verificar que o PDF aparece no iframe
7. Clicar "Baixar PDF" → PDF abre em nova aba
8. Clicar "Assinar como loja" → preencher nome + CPF + aceite → confirmar
9. Verificar badge "assinado_loja" e que assinatura aparece na lista
10. Clicar "Assinar como cliente" → repetir
11. Verificar status "vigente" e mensagem "✓ Contrato vigente — ambas as partes assinaram."
12. Verificar que na lista de etapas a etapa 7 aparece com badge "vigente"

- [ ] **Step 7.3: Testar edição de adendo**

1. Gerar novo contrato (rascunho)
2. Clicar "Editar Adendo" → escrever texto → "Salvar e Regenerar PDF"
3. Verificar que o iframe recarrega com o adendo no PDF
4. Verificar que adendo NÃO pode ser editado após status "vigente"

- [ ] **Step 7.4: Commit final**

```bash
git add -A
git commit -m "feat: módulo de contrato completo — geração PDF, assinatura interna, aba Ciclo"
```

---

## Self-Review

**Cobertura do spec:**
- ✓ Pipeline de 20 etapas documentado e renderizado na aba Ciclo
- ✓ Contrato gerado a partir de template .docx com `{{variáveis}}`
- ✓ Campo `endereco_instalacao` com prompt "= Cliente"
- ✓ Adendo textual editável (mas bloqueado após vigente)
- ✓ Download/impressão do PDF
- ✓ Assinatura interna MVP: nome + CPF + aceite + hash SHA-256 + timestamp + IP
- ✓ Status avança para `vigente` após ambas as partes assinar
- ✓ `vigente` avança automaticamente etapa 7 do `ciclo_etapas`
- ✓ Arquitetura preparada para D4Sign: campo `d4sign_uuid` na tabela, sem mais mudanças
- ✓ LibreOffice funciona em Windows (múltiplos caminhos) e Ubuntu

**Gaps identificados e aceitos:**
- A variável `_projetoAtivo` é assumida como existente no frontend (ela existe — é a variável de estado do projeto ativo em page-02). Confirmar o nome exato ao integrar.
- `mostrarToast` é assumido como função existente no frontend (existe — padrão do sistema).
- O helper `_montar_dados_projeto_para_contrato` lê `projeto.json` do disco — padrão atual do sistema enquanto migração para banco não ocorre.

---

*Plano criado em 2026-06-15. Plano 2 (NFe do cliente) em `docs/superpowers/plans/2026-06-15-modulo-nfe-cliente.md`.*
