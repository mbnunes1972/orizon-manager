"""
database.py — Conexão SQLAlchemy + modelos de dados
Omie_V3 | Dalmóbile
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, sessionmaker, relationship
from datetime import datetime
import hashlib
import os
import perfis

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
    telefone      = Column(String(20),  nullable=True)
    ativo         = Column(Integer,     default=1)
    criado_em     = Column(DateTime,    default=datetime.utcnow)
    loja_id       = Column(Integer,     ForeignKey("lojas.id"), nullable=True)  # usuário de loja
    rede_id       = Column(Integer,     ForeignKey("redes.id"), nullable=True)  # admin de rede (loja_id NULL)

    sessoes       = relationship("Sessao",          back_populates="usuario", cascade="all, delete-orphan")
    autorizacoes  = relationship("LogAutorizacao",  back_populates="autorizador", foreign_keys="LogAutorizacao.autorizador_id")

    def set_senha(self, senha: str):
        self.senha_hash = hashlib.sha256(senha.encode()).hexdigest()

    def check_senha(self, senha: str) -> bool:
        return self.senha_hash == hashlib.sha256(senha.encode()).hexdigest()

    @property
    def limite_desconto(self) -> float:
        return perfis.desconto_max(self.nivel)

    @property
    def pode_ver_parametros(self) -> bool:
        return perfis.pode(self.nivel, "ver_parametros")


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


class LogAcaoGerencial(Base):
    """Auditoria de ações destrutivas autorizadas por gerente (ex.: reabrir cascata)."""
    __tablename__ = "log_acoes_gerenciais"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    solicitante_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    autorizador_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=False)
    acao           = Column(Text,     nullable=False)   # ex.: "reabrir_cascata"
    projeto_nome   = Column(Text,     nullable=True)
    etapa_alvo     = Column(Text,     nullable=True)
    contexto       = Column(Text,     nullable=True)    # JSON
    criado_em      = Column(DateTime, default=datetime.utcnow)

    solicitante = relationship("Usuario", foreign_keys=[solicitante_id])
    autorizador = relationship("Usuario", foreign_keys=[autorizador_id])


class Medicao(Base):
    """Dados de medição por projeto (etapas 9 e 10 do ciclo)."""
    __tablename__ = "medicoes"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    projeto_nome        = Column(String(200), nullable=False, unique=True)
    # Etapa 9 — solicitação
    solicitacao_arquivo = Column(String(255), nullable=True)
    solicitacao_por     = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    solicitacao_em      = Column(DateTime, nullable=True)
    # Etapa 10 — parecer + planta
    parecer             = Column(String(20), nullable=True)   # aprovado|reprovado|parcial
    ambientes_aprovados = Column(Text, nullable=True)
    planta_arquivo      = Column(String(255), nullable=True)
    medidor_id          = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    medicao_em          = Column(DateTime, nullable=True)
    # Reprovado — decisão comercial
    doc_cliente_arquivo = Column(String(255), nullable=True)
    excecao_por         = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    excecao_em          = Column(DateTime, nullable=True)


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
    inst_mesmo_residencial = Column(Integer,     default=1)   # 1=True, 0=False
    inst_logradouro        = Column(String(200), nullable=True)
    inst_numero            = Column(String(20),  nullable=True)
    inst_complemento       = Column(String(100), nullable=True)
    inst_bairro            = Column(String(100), nullable=True)
    inst_cidade            = Column(String(80),  nullable=True)
    inst_cep               = Column(String(9),   nullable=True)
    inst_uf                = Column(String(2),   nullable=True)
    omie_codigo   = Column(String(40),  nullable=True)
    omie_sync_status = Column(String(20),  nullable=True)   # ok | erro | pendente
    omie_sync_erro   = Column(Text,        nullable=True)
    omie_sync_at     = Column(DateTime,    nullable=True)
    criado_em     = Column(DateTime,    default=datetime.utcnow)
    atualizado_em = Column(DateTime,    onupdate=datetime.utcnow)
    loja_id       = Column(Integer,     ForeignKey("lojas.id"), nullable=True)


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
    rede_id             = Column(Integer,      ForeignKey("redes.id"), nullable=True)
    abrangencia         = Column(String(10),   default="loja")   # loja | rede


class Rede(Base):
    """Rede (franquia) que agrupa lojas. Loja avulsa tem rede_id NULL."""
    __tablename__ = "redes"

    id        = Column(Integer,     primary_key=True, autoincrement=True)
    nome      = Column(String(150), nullable=False)
    cnpj      = Column(String(18),  nullable=True)
    ativo     = Column(Integer,     default=1)
    criado_em = Column(DateTime,    default=datetime.utcnow)


class Loja(Base):
    """Loja (tenant). Pertence a uma rede ou é avulsa (rede_id NULL)."""
    __tablename__ = "lojas"

    id          = Column(Integer,     primary_key=True, autoincrement=True)
    rede_id     = Column(Integer,     ForeignKey("redes.id"), nullable=True)  # NULL = avulsa
    nome        = Column(String(150), nullable=False)
    cnpj        = Column(String(18),  nullable=True)
    codigo      = Column(String(8),   nullable=True, unique=True)   # 3 letras p/ num contrato
    telefone    = Column(String(20),  nullable=True)
    email       = Column(String(120), nullable=True)
    cep         = Column(String(9),   nullable=True)
    logradouro  = Column(String(200), nullable=True)
    numero      = Column(String(20),  nullable=True)
    complemento = Column(String(100), nullable=True)
    bairro      = Column(String(100), nullable=True)
    cidade      = Column(String(80),  nullable=True)
    estado      = Column(String(2),   nullable=True)
    testemunha1_nome = Column(String(120), nullable=True)
    testemunha1_cpf  = Column(String(14),  nullable=True)
    testemunha2_nome = Column(String(120), nullable=True)
    testemunha2_cpf  = Column(String(14),  nullable=True)
    ativo       = Column(Integer,  default=1)
    criado_em   = Column(DateTime, default=datetime.utcnow)


class ParceiroLoja(Base):
    """Vínculo M:N parceiro × loja, com comissão própria por loja."""
    __tablename__ = "parceiro_lojas"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    parceiro_id         = Column(Integer, ForeignKey("parceiros.id"), nullable=False)
    loja_id             = Column(Integer, ForeignKey("lojas.id"),     nullable=False)
    comissao_padrao_pct = Column(Float,   default=0.0)
    ativo               = Column(Integer, default=1)


class Projeto(Base):
    """Metadados de pipeline por projeto. nome_safe é a chave natural (nome da pasta)."""
    __tablename__ = "projetos_meta"

    nome_safe  = Column(String,   primary_key=True)
    cliente_id = Column(Integer,  ForeignKey("clientes.id"), nullable=True)
    status     = Column(String(20), nullable=True)   # quente | morno | frio | convertido | perdido
    status_at  = Column(DateTime,   nullable=True)
    perdido_em     = Column(DateTime,   nullable=True)
    parametros_json = Column(Text, nullable=True)   # parâmetros estruturais da negociação (JSON, projeto-wide)
    loja_id        = Column(Integer,    ForeignKey("lojas.id"), nullable=True)


class Briefing(Base):
    __tablename__ = "briefings"

    id                    = Column(Integer,  primary_key=True, autoincrement=True)
    cliente_id            = Column(Integer,  ForeignKey("clientes.id"), nullable=False)
    projeto_nome          = Column(Text,     nullable=True)
    criado_em             = Column(DateTime, default=datetime.utcnow)
    atualizado_em         = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    # Obrigatórios (gate etapa 2)
    data_atendimento      = Column(DateTime, nullable=False)
    consultor_id          = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    tipo_imovel           = Column(Text,     nullable=False)
    budget_declarado      = Column(Float,    nullable=False)
    categoria_proposta    = Column(Text,     nullable=False)
    data_entrega_desejada = Column(Text,     nullable=False)
    flexibilidade_prazo   = Column(Text,     nullable=False)

    # Opcionais
    condicao_imovel       = Column(Text,     nullable=True)
    metragem_m2           = Column(Float,    nullable=True)
    num_ambientes         = Column(Integer,  nullable=True)
    ambientes_prioritarios = Column(Text,    nullable=True)
    tem_arquiteto         = Column(Text,     nullable=True)
    nome_arquiteto        = Column(Text,     nullable=True)
    tem_gerente_obra      = Column(Integer,  nullable=True)
    end_empreendimento    = Column(Text,     nullable=True)
    estilo_decisao        = Column(Text,     nullable=True)
    estilo_vida           = Column(Text,     nullable=True)
    relacao_projeto       = Column(Text,     nullable=True)
    decisor               = Column(Text,     nullable=True)
    referencias_visuais   = Column(Text,     nullable=True)
    obs_referencias       = Column(Text,     nullable=True)
    experiencia_anterior  = Column(Text,     nullable=True)
    obs_experiencia       = Column(Text,     nullable=True)
    tem_budget            = Column(Text,     nullable=True)
    forma_pagamento_pref  = Column(Text,     nullable=True)
    data_entrega_limite   = Column(Text,     nullable=True)
    motivo_prazo          = Column(Text,     nullable=True)
    nao_abre_mao          = Column(Text,     nullable=True)
    restricoes            = Column(Text,     nullable=True)
    obs_livres            = Column(Text,     nullable=True)

    cliente   = relationship("Cliente", foreign_keys=[cliente_id])
    consultor = relationship("Usuario", foreign_keys=[consultor_id])


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
    negociacao_json = Column(Text,     nullable=True)   # snapshot das entradas da negociação (JSON)
    valor_total     = Column(Float,    default=0.0)
    valor_liquido   = Column(Float,    default=0.0)
    created_by      = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, nullable=True)
    loja_id         = Column(Integer,  ForeignKey("lojas.id"), nullable=True)

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
    desconto_individual_pct = Column(Float, nullable=False, default=0.0, server_default="0")

    orcamento     = relationship("Orcamento",     back_populates="ambientes")
    pool_ambiente = relationship("PoolAmbiente",  back_populates="orcamento_links")


# ── Ciclo do Projeto ──────────────────────────────────────────────────────────

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
    num_contrato         = Column(Text,     nullable=True)   # LOJA-AAAA-MM-DD-SEQ
    projeto_nome         = Column(Text,     nullable=False)
    orcamento_id         = Column(Integer,  ForeignKey("orcamentos.id"), nullable=False)
    template_path        = Column(Text,     nullable=False, default="config/contrato_template.docx")
    pdf_path             = Column(Text,     nullable=True)
    endereco_instalacao  = Column(Text,     nullable=True)
    pagamento_json       = Column(Text,     nullable=True)   # JSON com cronograma de parcelas
    status               = Column(Text,     nullable=False, default="rascunho")
    # status: rascunho | gerado | assinado_loja | assinado_cliente | vigente
    adendo               = Column(Text,     nullable=True)
    gerado_em            = Column(DateTime, nullable=True)
    gerado_por_id        = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    d4sign_uuid          = Column(Text,     nullable=True)   # fase futura D4Sign
    loja_id              = Column(Integer,  ForeignKey("lojas.id"), nullable=True)

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


# ── Inicialização ─────────────────────────────────────────────────────────────
def init_db():
    Base.metadata.create_all(ENGINE)
    _migrar_colunas()
    _migrar_dados()

def _migrar_colunas():
    """Adiciona colunas novas em tabelas existentes sem perder dados."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()

        # ── clientes ─────────────────────────────────────────────────────────
        cur.execute("PRAGMA table_info(clientes)")
        cli_cols = {row[1] for row in cur.fetchall()}
        for col, tipo in [
            ("cep",                    "VARCHAR(9)"),
            ("logradouro",             "VARCHAR(200)"),
            ("numero",                 "VARCHAR(20)"),
            ("complemento",            "VARCHAR(100)"),
            ("bairro",                 "VARCHAR(100)"),
            ("omie_sync_status",       "VARCHAR(20)"),
            ("omie_sync_erro",         "TEXT"),
            ("omie_sync_at",           "DATETIME"),
            ("inst_mesmo_residencial", "INTEGER DEFAULT 1"),
            ("inst_logradouro",        "VARCHAR(200)"),
            ("inst_numero",            "VARCHAR(20)"),
            ("inst_complemento",       "VARCHAR(100)"),
            ("inst_bairro",            "VARCHAR(100)"),
            ("inst_cidade",            "VARCHAR(80)"),
            ("inst_cep",               "VARCHAR(9)"),
            ("inst_uf",                "VARCHAR(2)"),
        ]:
            if col not in cli_cols:
                cur.execute(f"ALTER TABLE clientes ADD COLUMN {col} {tipo}")

        # ── usuarios ─────────────────────────────────────────────────────────
        cur.execute("PRAGMA table_info(usuarios)")
        usr_cols = {row[1] for row in cur.fetchall()}
        if "telefone" not in usr_cols:
            cur.execute("ALTER TABLE usuarios ADD COLUMN telefone VARCHAR(20)")

        # ── projetos_meta ─────────────────────────────────────────────────────
        cur.execute("PRAGMA table_info(projetos_meta)")
        prj_cols = {row[1] for row in cur.fetchall()}
        if "cliente_id" not in prj_cols:
            cur.execute("ALTER TABLE projetos_meta ADD COLUMN cliente_id INTEGER")
        if "parametros_json" not in prj_cols:
            cur.execute("ALTER TABLE projetos_meta ADD COLUMN parametros_json TEXT")

        # ── contratos ─────────────────────────────────────────────────────────
        cur.execute("PRAGMA table_info(contratos)")
        con_cols = {row[1] for row in cur.fetchall()}
        for col, tipo in [
            ("pagamento_json",  "TEXT"),
            ("endereco_instalacao", "TEXT"),
            ("adendo",          "TEXT"),
            ("d4sign_uuid",     "TEXT"),
            ("gerado_por_id",   "INTEGER"),
            ("num_contrato",    "VARCHAR(30)"),
        ]:
            if col not in con_cols:
                cur.execute(f"ALTER TABLE contratos ADD COLUMN {col} {tipo}")

        # ── orcamentos ────────────────────────────────────────────────────────
        cur.execute("PRAGMA table_info(orcamentos)")
        orc_cols = {row[1] for row in cur.fetchall()}
        for col, tipo in [
            ("valor_liquido",   "REAL DEFAULT 0"),
            ("forma_pagamento", "TEXT"),
            ("updated_at",      "DATETIME"),
            ("negociacao_json", "TEXT"),
        ]:
            if col not in orc_cols:
                cur.execute(f"ALTER TABLE orcamentos ADD COLUMN {col} {tipo}")

        # ── orcamento_ambientes ───────────────────────────────────────────────
        cur.execute("PRAGMA table_info(orcamento_ambientes)")
        oa_cols = {row[1] for row in cur.fetchall()}
        if "desconto_individual_pct" not in oa_cols:
            cur.execute("ALTER TABLE orcamento_ambientes "
                        "ADD COLUMN desconto_individual_pct REAL NOT NULL DEFAULT 0")

        # ── briefings ─────────────────────────────────────────────────────────
        cur.execute("PRAGMA table_info(briefings)")
        bf_cols = {row[1] for row in cur.fetchall()}
        if "projeto_nome" not in bf_cols:
            cur.execute("ALTER TABLE briefings ADD COLUMN projeto_nome TEXT")

        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

def _tabela_existe(cur, nome):
    """True se a tabela existe (migração de tabela ausente é no-op — robusto a DBs parciais)."""
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nome,))
    return cur.fetchone() is not None


def _run_migracoes(conn):
    """Migrações de DADOS (não de schema), idempotentes, rastreadas em schema_migrations.
    Recebe uma conexão sqlite3 (facilita teste com :memory:)."""
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
        id          TEXT PRIMARY KEY,
        aplicada_em DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute("SELECT id FROM schema_migrations")
    aplicadas = {r[0] for r in cur.fetchall()}

    # 2026-06-17: trocar etapa_codigo 2<->3 (Briefing <-> Criação do projeto).
    # A troca direta colidiria com UNIQUE(projeto_nome, etapa_codigo); usa código temporário.
    if "etapas_swap_2_3" not in aplicadas and _tabela_existe(cur, "ciclo_etapas"):
        cur.execute("UPDATE ciclo_etapas SET etapa_codigo='_swap2' WHERE etapa_codigo='2'")
        cur.execute("UPDATE ciclo_etapas SET etapa_codigo='2'      WHERE etapa_codigo='3'")
        cur.execute("UPDATE ciclo_etapas SET etapa_codigo='3'      WHERE etapa_codigo='_swap2'")
        cur.execute("INSERT INTO schema_migrations(id) VALUES('etapas_swap_2_3')")

    # 2026-06-18: 10 perfis — renomeia níveis antigos.
    if "perfis_v2_2026" not in aplicadas and _tabela_existe(cur, "usuarios"):
        cur.execute("UPDATE usuarios SET nivel='gerente_vendas' WHERE nivel='gerente'")
        cur.execute("UPDATE usuarios SET nivel='diretor'        WHERE nivel='admin'")
        cur.execute("INSERT INTO schema_migrations(id) VALUES('perfis_v2_2026')")

    conn.commit()


def migrar_margens_para_orcamentos(session, projetos_dir):
    """Copia margens de cada PROJETOS/<nome>/projeto.json para os Orcamentos do projeto
    que ainda estão sem margens. Idempotente: só preenche margens vazias/nulas.
    Retorna o nº de orçamentos atualizados."""
    import glob, json, os
    atualizados = 0
    for pj in glob.glob(os.path.join(projetos_dir, "*", "projeto.json")):
        try:
            data = json.loads(open(pj, encoding="utf-8").read())
        except Exception:
            continue
        margens = data.get("margens")
        if not margens:
            continue
        nome_safe = data.get("nome_safe") or os.path.basename(os.path.dirname(pj))
        for o in session.query(Orcamento).filter_by(projeto_id=nome_safe).all():
            if not o.margens:
                o.margens = json.dumps(margens, ensure_ascii=False)
                atualizados += 1
    if atualizados:
        session.commit()
    return atualizados


def migrar_parametros_para_projeto(session):
    """Copia os parâmetros estruturais de um orçamento existente para
    projetos_meta.parametros_json, para projetos que ainda não têm. Idempotente.
    Retorna o nº de projetos atualizados."""
    import json
    from mod_orcamento_params import PARAMETROS_DEFAULT
    atualizados = 0
    projetos = session.query(Projeto).filter(
        (Projeto.parametros_json.is_(None)) | (Projeto.parametros_json == "")
    ).all()
    for p in projetos:
        orc = (session.query(Orcamento)
                      .filter_by(projeto_id=p.nome_safe)
                      .order_by(Orcamento.id.desc())
                      .first())
        if not orc or not orc.margens:
            continue
        try:
            m = json.loads(orc.margens)
        except Exception:
            continue
        par = {k: m[k] for k in PARAMETROS_DEFAULT if k in m}
        if not par:
            continue
        p.parametros_json = json.dumps({**PARAMETROS_DEFAULT, **par}, ensure_ascii=False)
        atualizados += 1
    if atualizados:
        session.commit()
    return atualizados


def _migrar_dados():
    """Abre a conexão real e roda as migrações de dados idempotentes."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    try:
        _run_migracoes(conn)
    except Exception:
        pass
    finally:
        conn.close()

def get_session():
    return Session()


def upsert_projeto_status(nome_safe: str, status: str, perdido_em=None):
    """Cria ou atualiza o registro de status do projeto. Thread-safe via sessão própria."""
    db = get_session()
    try:
        p = db.get(Projeto, nome_safe)
        if not p:
            p = Projeto(nome_safe=nome_safe)
            db.add(p)
        antigo_status = p.status
        p.status    = status
        p.status_at = datetime.utcnow()
        if status == "perdido":
            p.perdido_em = perdido_em or datetime.utcnow()
        elif antigo_status == "perdido" and status != "perdido":
            p.perdido_em = None
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
