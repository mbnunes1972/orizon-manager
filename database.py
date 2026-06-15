"""
database.py — Conexão SQLAlchemy + modelos de dados
Omie_V3 | Dalmóbile
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, relationship
from datetime import datetime
import hashlib
import os

# ── Conexão ──────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "omie.db")
ENGINE   = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Session  = sessionmaker(bind=ENGINE)

# ── Base ─────────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass

# ── Modelos ──────────────────────────────────────────────────────────────────
class Usuario(Base):
    __tablename__ = "usuarios"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    nome          = Column(String(120), nullable=False)
    login         = Column(String(60),  nullable=False, unique=True)
    senha_hash    = Column(String(64),  nullable=False)
    nivel         = Column(String(20),  nullable=False)   # diretor | gerente | consultor
    ativo         = Column(Integer,     default=1)
    criado_em     = Column(DateTime,    default=datetime.utcnow)

    sessoes       = relationship("Sessao",          back_populates="usuario", cascade="all, delete-orphan")
    autorizacoes  = relationship("LogAutorizacao",  back_populates="autorizador", foreign_keys="LogAutorizacao.autorizador_id")

    def set_senha(self, senha: str):
        self.senha_hash = hashlib.sha256(senha.encode()).hexdigest()

    def check_senha(self, senha: str) -> bool:
        return self.senha_hash == hashlib.sha256(senha.encode()).hexdigest()

    @property
    def limite_desconto(self) -> float:
        limites = {"consultor": 10.0, "gerente": 20.0, "diretor": 50.0, "admin": 50.0}
        return limites.get(self.nivel, 0.0)

    @property
    def pode_ver_parametros(self) -> bool:
        return self.nivel in ("gerente", "diretor", "admin")


class Sessao(Base):
    __tablename__ = "sessoes"

    id          = Column(Integer,  primary_key=True, autoincrement=True)
    token       = Column(String(64), nullable=False, unique=True)
    usuario_id  = Column(Integer,  ForeignKey("usuarios.id"), nullable=False)
    criada_em   = Column(DateTime, default=datetime.utcnow)
    expira_em   = Column(DateTime, nullable=False)
    ativa       = Column(Integer,  default=1)

    usuario     = relationship("Usuario", back_populates="sessoes")


class LogAutorizacao(Base):
    __tablename__ = "log_autorizacoes"

    id               = Column(Integer,  primary_key=True, autoincrement=True)
    solicitante_id   = Column(Integer,  ForeignKey("usuarios.id"), nullable=False)
    autorizador_id   = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    desconto_solicit = Column(Float,    nullable=False)
    desconto_limite  = Column(Float,    nullable=False)
    autorizado       = Column(Integer,  default=0)   # 0=negado/cancelado 1=autorizado
    contexto         = Column(Text,     nullable=True)  # JSON com detalhes da negociação
    criado_em        = Column(DateTime, default=datetime.utcnow)

    solicitante  = relationship("Usuario", foreign_keys=[solicitante_id])
    autorizador  = relationship("Usuario", back_populates="autorizacoes", foreign_keys=[autorizador_id])


class Cliente(Base):
    __tablename__ = "clientes"

    id            = Column(Integer,     primary_key=True, autoincrement=True)
    nome          = Column(String(150), nullable=False)
    cpf           = Column(String(14),  nullable=True, unique=True)
    email         = Column(String(120), nullable=True)
    telefone      = Column(String(20),  nullable=True)
    whatsapp      = Column(String(20),  nullable=True)
    cep           = Column(String(9),   nullable=True)
    logradouro    = Column(String(200), nullable=True)
    numero        = Column(String(20),  nullable=True)
    complemento   = Column(String(100), nullable=True)
    bairro        = Column(String(100), nullable=True)
    cidade        = Column(String(80),  nullable=True)
    estado        = Column(String(2),   nullable=True)
    observacoes   = Column(Text,        nullable=True)
    omie_codigo   = Column(String(40),  nullable=True)
    omie_sync_status = Column(String(20),  nullable=True)   # ok | erro | pendente
    omie_sync_erro   = Column(Text,        nullable=True)
    omie_sync_at     = Column(DateTime,    nullable=True)
    criado_em     = Column(DateTime,    default=datetime.utcnow)
    atualizado_em = Column(DateTime,    onupdate=datetime.utcnow)


class Parceiro(Base):
    __tablename__ = "parceiros"

    id                  = Column(Integer,     primary_key=True, autoincrement=True)
    nome                = Column(String(150), nullable=False)
    cpf_cnpj            = Column(String(18),  nullable=True)
    tipo                = Column(String(30),   nullable=True)   # arquiteto/designer/decorador/corretor/engenheiro/indicador
    email               = Column(String(120),  nullable=True)
    telefone            = Column(String(20),   nullable=True)
    whatsapp            = Column(String(20),   nullable=True)
    comissao_padrao_pct = Column(Float,        default=0.0)
    observacoes         = Column(Text,         nullable=True)
    criado_em           = Column(DateTime,     default=datetime.utcnow)


class Projeto(Base):
    """Metadados de pipeline por projeto. nome_safe é a chave natural (nome da pasta)."""
    __tablename__ = "projetos_meta"

    nome_safe  = Column(String,   primary_key=True)
    status     = Column(String(20), nullable=True)   # quente | morno | frio | convertido | perdido
    status_at  = Column(DateTime,   nullable=True)
    perdido_em = Column(DateTime,   nullable=True)


# ── EP-07: Versionamento de Orçamentos ───────────────────────────────────────

class PoolAmbiente(Base):
    """Pool permanente de XMLs por projeto. Registros nunca são deletados."""
    __tablename__ = "pool_ambientes"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    projeto_id     = Column(String,   nullable=False)          # nome da pasta do projeto
    nome           = Column(String,   nullable=False)          # nome base sem extensão
    versao         = Column(Integer,  default=1)
    nome_exibicao  = Column(String,   nullable=False)          # "Cozinha", "Cozinha_v1" etc.
    xml_path       = Column(String,   nullable=False)
    ambientes_json = Column(Text,     nullable=False)
    budget_total   = Column(Float,    nullable=False, default=0.0)
    order_total    = Column(Float,    nullable=False, default=0.0)
    created_by     = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow)

    criador           = relationship("Usuario", foreign_keys=[created_by])
    orcamento_links   = relationship("OrcamentoAmbiente", back_populates="pool_ambiente",
                                     cascade="all, delete-orphan")


class Orcamento(Base):
    """Versão de negociação dentro de um projeto. Nunca deletado."""
    __tablename__ = "orcamentos"

    id              = Column(Integer,  primary_key=True, autoincrement=True)
    projeto_id      = Column(String,   nullable=False)
    nome            = Column(String,   nullable=False, default="Orçamento 1")
    ordem           = Column(Integer,  nullable=False, default=1)
    margens         = Column(Text,     nullable=True)   # JSON
    desconto_pct    = Column(Float,    default=0.0)
    forma_pagamento = Column(String,   nullable=True)
    valor_total     = Column(Float,    default=0.0)
    valor_liquido   = Column(Float,    default=0.0)
    created_by      = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, nullable=True)

    criador   = relationship("Usuario", foreign_keys=[created_by])
    ambientes = relationship("OrcamentoAmbiente", back_populates="orcamento",
                             cascade="all, delete-orphan")


class OrcamentoAmbiente(Base):
    """Relação N:N entre orçamento e ambiente do pool."""
    __tablename__ = "orcamento_ambientes"

    orcamento_id     = Column(Integer, ForeignKey("orcamentos.id"),     primary_key=True)
    pool_ambiente_id = Column(Integer, ForeignKey("pool_ambientes.id"), primary_key=True)
    ordem            = Column(Integer, default=1)
    added_at         = Column(DateTime, default=datetime.utcnow)

    orcamento     = relationship("Orcamento",     back_populates="ambientes")
    pool_ambiente = relationship("PoolAmbiente",  back_populates="orcamento_links")


# ── Inicialização ─────────────────────────────────────────────────────────────
def init_db():
    Base.metadata.create_all(ENGINE)
    _migrar_colunas()

def _migrar_colunas():
    """Adiciona colunas novas em tabelas existentes sem perder dados."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(clientes)")
        existing = {row[1] for row in cur.fetchall()}
        novas = [
            ("cep",         "VARCHAR(9)"),
            ("logradouro",  "VARCHAR(200)"),
            ("numero",      "VARCHAR(20)"),
            ("complemento", "VARCHAR(100)"),
            ("bairro",      "VARCHAR(100)"),
            ("omie_sync_status", "VARCHAR(20)"),
            ("omie_sync_erro",   "TEXT"),
            ("omie_sync_at",     "DATETIME"),
        ]
        for col, tipo in novas:
            if col not in existing:
                cur.execute(f"ALTER TABLE clientes ADD COLUMN {col} {tipo}")
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

def get_session():
    return Session()


def upsert_projeto_status(nome_safe: str, status: str, perdido_em=None):
    """Cria ou atualiza o registro de status do projeto. Thread-safe via sessão própria."""
    from datetime import datetime as _dt
    db = get_session()
    try:
        p = db.get(Projeto, nome_safe)
        if not p:
            p = Projeto(nome_safe=nome_safe)
            db.add(p)
        antigo_status = p.status
        p.status    = status
        p.status_at = _dt.utcnow()
        if status == "perdido":
            p.perdido_em = perdido_em or _dt.utcnow()
        elif antigo_status == "perdido" and status != "perdido":
            p.perdido_em = None
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
