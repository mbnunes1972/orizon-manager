"""
database.py — Conexão SQLAlchemy + modelos de dados
Orizon Manager | Dalmóbile
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, sessionmaker, relationship
from datetime import datetime
import hashlib
import os
import perfis

def _hash_senha(senha: str) -> str:
    """SHA-256 hex de uma senha. Fonte única de hashing (Usuario + bootstrap/seed)."""
    return hashlib.sha256(senha.encode()).hexdigest()


# ── Conexão ──────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "orizon.db")
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
    email         = Column(String(120), nullable=True)
    cpf           = Column(String(20),  nullable=True)
    whatsapp      = Column(String(20),  nullable=True)
    ativo         = Column(Integer,     default=1)
    criado_em     = Column(DateTime,    default=datetime.utcnow)
    loja_id       = Column(Integer,     ForeignKey("lojas.id"), nullable=True)  # usuário de loja
    rede_id       = Column(Integer,     ForeignKey("redes.id"), nullable=True)  # admin de rede (loja_id NULL)

    sessoes       = relationship("Sessao",          back_populates="usuario", cascade="all, delete-orphan")
    autorizacoes  = relationship("LogAutorizacao",  back_populates="autorizador", foreign_keys="LogAutorizacao.autorizador_id")

    def set_senha(self, senha: str):
        self.senha_hash = _hash_senha(senha)

    def check_senha(self, senha: str) -> bool:
        return self.senha_hash == _hash_senha(senha)

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
    emitente_central_id = Column(Integer, ForeignKey("emitente.id"), nullable=True)
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
    emitente_id = Column(Integer, ForeignKey("emitente.id"), nullable=True)
    ativo       = Column(Integer,  default=1)
    criado_em   = Column(DateTime, default=datetime.utcnow)
    config_financeira_json = Column(Text, nullable=True)   # config financeira da loja (JSON)


class ParceiroLoja(Base):
    """Vínculo M:N parceiro × loja, com comissão própria por loja."""
    __tablename__ = "parceiro_lojas"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    parceiro_id         = Column(Integer, ForeignKey("parceiros.id"), nullable=False)
    loja_id             = Column(Integer, ForeignKey("lojas.id"),     nullable=False)
    comissao_padrao_pct = Column(Float,   default=0.0)
    ativo               = Column(Integer, default=1)


class UsuarioLoja(Base):
    """Vínculo M:N usuário × loja (lojas acessíveis). loja_id em usuarios = loja primária/default."""
    __tablename__ = "usuario_lojas"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    loja_id    = Column(Integer, ForeignKey("lojas.id"),    nullable=False)

    __table_args__ = (UniqueConstraint("usuario_id", "loja_id", name="uq_usuario_loja"),)


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
    criado_por_id  = Column(Integer,    ForeignKey("usuarios.id"), nullable=True)   # usuário que criou o projeto (escopo por projetista)


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
    # ── qualidade do XML (spec §8) ──
    qa_selo               = Column(String,  nullable=True)
    qa_pct_sem_acrescimo  = Column(Float,   nullable=True)
    qa_markup_xml         = Column(Float,   nullable=True)
    qa_custo_sem_venda    = Column(Integer, nullable=True)
    qa_override_por_id    = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    qa_override_motivo    = Column(String,  nullable=True)
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
    desconto_pct    = Column(Float,    default=0.0)
    forma_pagamento = Column(String,   nullable=True)
    negociacao_json = Column(Text,     nullable=True)   # snapshot das entradas da negociação (JSON)
    valor_total     = Column(Float,    default=0.0)
    valor_liquido   = Column(Float,    default=0.0)
    # ── derivados do motor de negociação (modo sombra — spec §5) ──
    vbvo         = Column(Float, default=0.0)
    cfo          = Column(Float, default=0.0)
    vbno         = Column(Float, default=0.0)
    vavo         = Column(Float, default=0.0)
    cust_ad      = Column(Float, default=0.0)
    com_arq_orc  = Column(Float, default=0.0)
    pro_fid_orc  = Column(Float, default=0.0)
    val_liq      = Column(Float, default=0.0)
    desc_tot_pct = Column(Float, default=0.0)
    markup       = Column(Float, default=0.0)
    cust_fin     = Column(Float, default=0.0)
    val_cont     = Column(Float, default=0.0)
    prov_imp     = Column(Float, default=0.0)
    out_forn     = Column(Float, default=0.0)   # Outros Fornecedores (editável Gerente Adm/Fin)
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


class ProvisaoRegistro(Base):
    """Provisões registradas por versão (venda/rev1/rev2) de um orçamento.
    venda = snapshot na geração do contrato; rev1/rev2 = aprovação financeira I/II."""
    __tablename__ = "provisao_registro"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    orcamento_id = Column(Integer, ForeignKey("orcamentos.id"), nullable=False)
    versao       = Column(String(8), nullable=False)   # 'venda' | 'rev1' | 'rev2'
    itens_json   = Column(Text,      nullable=False)    # {rubrica: valor_R$}
    cfo          = Column(Float, default=0.0)           # base congelada p/ recalcular margem
    val_liq      = Column(Float, default=0.0)
    cust_var     = Column(Float, default=0.0)
    marg_cont    = Column(Float, default=0.0)
    decisao      = Column(String(10), nullable=True)    # 'concorda' | 'revisa' | None (venda)
    por_id       = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    criado_em    = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("orcamento_id", "versao", name="uq_provisao_orc_versao"),)


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
    loja_snapshot_json   = Column(Text,     nullable=True)   # snapshot dos dados da loja (F3)

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


class CicloDocumento(Base):
    """Documento carregado numa subfase do ciclo. Append-only: nunca sobrescreve."""
    __tablename__ = "ciclo_documentos"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    projeto_nome   = Column(Text,     nullable=False)   # nome_safe
    etapa_codigo   = Column(Text,     nullable=False)   # "11a","11b","11c","11e"
    tipo           = Column(Text,     nullable=False)   # pe_planta_pontos, ...
    arquivo_path   = Column(Text,     nullable=False)   # relativo a PROJETOS/<nome>/
    nome_original  = Column(Text,     nullable=False)
    enviado_por_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    enviado_em     = Column(DateTime, nullable=False, default=datetime.utcnow)

    enviado_por = relationship("Usuario", foreign_keys=[enviado_por_id])


class CicloRevisao(Base):
    """Revisão aberta numa subfase (reabertura em cascata)."""
    __tablename__ = "ciclo_revisoes"

    id               = Column(Integer,  primary_key=True, autoincrement=True)
    projeto_nome     = Column(Text,     nullable=False)
    etapa_codigo     = Column(Text,     nullable=False)
    aberta_por_id    = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    aberta_em        = Column(DateTime, nullable=False, default=datetime.utcnow)
    relatorio_doc_id = Column(Integer,  ForeignKey("ciclo_documentos.id"), nullable=True)
    motivo           = Column(Text,     nullable=True)

    aberta_por = relationship("Usuario", foreign_keys=[aberta_por_id])


class PerfilFiscal(Base):
    """Perfil fiscal por CNPJ/loja (1:1 com Loja). Complementa Loja.cnpj/endereço.
    Segredos (tokens Focus) ficam CIFRADOS (fiscal_cripto); o certificado A1 NÃO fica aqui
    (vive no painel da Focus) — só validade + CNPJ de referência."""
    __tablename__ = "perfil_fiscal"

    id      = Column(Integer, primary_key=True, autoincrement=True)
    loja_id = Column(Integer, ForeignKey("lojas.id"), nullable=False, unique=True)

    razao_social        = Column(Text, nullable=True)
    inscricao_estadual  = Column(Text, nullable=True)
    inscricao_municipal = Column(Text, nullable=True)

    regime_tributario   = Column(Text, nullable=True)   # simples|simples_excesso|normal|mei
    csosn_padrao        = Column(Text, nullable=True)

    cfop_dentro_uf      = Column(Text, nullable=True)
    cfop_fora_uf        = Column(Text, nullable=True)
    serie_nfe           = Column(Text, nullable=True)
    discrimina_impostos = Column(Integer, default=1)

    cnae_servico          = Column(Text,  nullable=True)
    cod_servico_municipio = Column(Text,  nullable=True)
    aliquota_iss          = Column(Float, nullable=True)
    retencao_json         = Column(Text,  nullable=True)
    municipio_ibge        = Column(Text,  nullable=True)

    cert_validade = Column(DateTime, nullable=True)
    cert_cnpj     = Column(Text,     nullable=True)

    papel_cnpj    = Column(Text, nullable=True)   # central_produto|loja_servico|loja_produto_servico|avulso

    focus_token_homolog_enc = Column(Text, nullable=True)
    focus_token_prod_enc    = Column(Text, nullable=True)
    ambiente_ativo          = Column(Text, default="homologacao")

    placeholders_json = Column(Text, nullable=True)

    criado_em     = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Emitente(Base):
    """Identidade fiscal de 1 CNPJ (absorve PerfilFiscal). Emite documentos; NÃO é a loja vendedora."""
    __tablename__ = "emitente"
    id = Column(Integer, primary_key=True, autoincrement=True)
    cnpj = Column(String(18), nullable=True)
    razao_social = Column(Text, nullable=True)
    nome_fantasia = Column(Text, nullable=True)
    inscricao_estadual = Column(Text, nullable=True)
    inscricao_municipal = Column(Text, nullable=True)
    regime_tributario = Column(Text, nullable=True)
    csosn_padrao = Column(Text, nullable=True)
    cfop_dentro_uf = Column(Text, nullable=True)
    cfop_fora_uf = Column(Text, nullable=True)
    serie_nfe = Column(Text, nullable=True)
    discrimina_impostos = Column(Integer, default=1)
    cnae_servico = Column(Text, nullable=True)
    cod_servico_municipio = Column(Text, nullable=True)
    aliquota_iss = Column(Float, nullable=True)
    retencao_json = Column(Text, nullable=True)
    municipio_ibge = Column(Text, nullable=True)
    logradouro = Column(Text, nullable=True)
    numero = Column(Text, nullable=True)
    bairro = Column(Text, nullable=True)
    cidade = Column(Text, nullable=True)
    uf = Column(Text, nullable=True)
    cep = Column(Text, nullable=True)
    cert_validade = Column(DateTime, nullable=True)
    cert_cnpj = Column(Text, nullable=True)
    papel_cnpj = Column(Text, nullable=True)
    focus_token_homolog_enc = Column(Text, nullable=True)
    focus_token_prod_enc = Column(Text, nullable=True)
    ambiente_ativo = Column(Text, default="homologacao")
    placeholders_json = Column(Text, nullable=True)
    rede_id = Column(Integer, ForeignKey("redes.id"), nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NfeEmissao(Base):
    """Rastreio de uma NF-e emitida pela loja (Focus). `ref` = idempotência. XML/DANFE ficam
    em CicloDocumento (etapa 15) referenciados por xml_doc_id/danfe_doc_id."""
    __tablename__ = "nfe_emissao"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    ref            = Column(Text, nullable=False, unique=True)
    projeto_nome   = Column(Text, nullable=True)
    etapa_codigo   = Column(Text, default="15")
    loja_id        = Column(Integer, ForeignKey("lojas.id"), nullable=True)
    status         = Column(Text, nullable=True)
    chave_nfe      = Column(Text, nullable=True)
    numero         = Column(Text, nullable=True)
    serie          = Column(Text, nullable=True)
    mensagem_sefaz = Column(Text, nullable=True)
    erros_json     = Column(Text, nullable=True)
    xml_doc_id     = Column(Integer, ForeignKey("ciclo_documentos.id"), nullable=True)
    danfe_doc_id   = Column(Integer, ForeignKey("ciclo_documentos.id"), nullable=True)
    fabrica_doc_id = Column(Integer, ForeignKey("ciclo_documentos.id"), nullable=True)
    emitido_em     = Column(DateTime, default=datetime.utcnow)
    atualizado_em  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
            ("loja_id",                "INTEGER"),
        ]:
            if col not in cli_cols:
                cur.execute(f"ALTER TABLE clientes ADD COLUMN {col} {tipo}")

        # ── usuarios ─────────────────────────────────────────────────────────
        cur.execute("PRAGMA table_info(usuarios)")
        usr_cols = {row[1] for row in cur.fetchall()}
        if "telefone" not in usr_cols:
            cur.execute("ALTER TABLE usuarios ADD COLUMN telefone VARCHAR(20)")
        for col in ("loja_id", "rede_id"):
            if col not in usr_cols:
                cur.execute(f"ALTER TABLE usuarios ADD COLUMN {col} INTEGER")
        for col, tipo in [("email", "VARCHAR(120)"), ("cpf", "VARCHAR(20)"),
                          ("whatsapp", "VARCHAR(20)")]:
            if col not in usr_cols:
                cur.execute(f"ALTER TABLE usuarios ADD COLUMN {col} {tipo}")

        # ── projetos_meta ─────────────────────────────────────────────────────
        cur.execute("PRAGMA table_info(projetos_meta)")
        prj_cols = {row[1] for row in cur.fetchall()}
        if "cliente_id" not in prj_cols:
            cur.execute("ALTER TABLE projetos_meta ADD COLUMN cliente_id INTEGER")
        if "parametros_json" not in prj_cols:
            cur.execute("ALTER TABLE projetos_meta ADD COLUMN parametros_json TEXT")
        if "loja_id" not in prj_cols:
            cur.execute("ALTER TABLE projetos_meta ADD COLUMN loja_id INTEGER")
        if "criado_por_id" not in prj_cols:
            cur.execute("ALTER TABLE projetos_meta ADD COLUMN criado_por_id INTEGER")

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
            ("loja_id",         "INTEGER"),
            ("loja_snapshot_json", "TEXT"),
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
            ("loja_id",         "INTEGER"),
        ]:
            if col not in orc_cols:
                cur.execute(f"ALTER TABLE orcamentos ADD COLUMN {col} {tipo}")

        # ── orcamentos: derivados do motor de negociação (modo sombra) ──
        cur.execute("PRAGMA table_info(orcamentos)")
        orc_cols = {row[1] for row in cur.fetchall()}
        for col in ("vbvo", "cfo", "vbno", "vavo", "cust_ad", "com_arq_orc", "pro_fid_orc",
                    "val_liq", "desc_tot_pct", "markup", "cust_fin", "val_cont", "prov_imp"):
            if col not in orc_cols:
                cur.execute(f"ALTER TABLE orcamentos ADD COLUMN {col} REAL DEFAULT 0")

        # 2026-06-24: config financeira da loja + Out_Forn por orçamento
        if _tabela_existe(cur, "lojas"):
            loja_cols = [c[1] for c in cur.execute("PRAGMA table_info(lojas)").fetchall()]
            if "config_financeira_json" not in loja_cols:
                cur.execute("ALTER TABLE lojas ADD COLUMN config_financeira_json TEXT")

        if _tabela_existe(cur, "orcamentos"):
            orc_cols = [c[1] for c in cur.execute("PRAGMA table_info(orcamentos)").fetchall()]
            if "out_forn" not in orc_cols:
                cur.execute("ALTER TABLE orcamentos ADD COLUMN out_forn REAL DEFAULT 0")

        # ── pool_ambientes: qualidade do XML ──
        cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='pool_ambientes'")
        if cur.fetchone() is not None:
            cur.execute("PRAGMA table_info(pool_ambientes)")
            pa_cols = {row[1] for row in cur.fetchall()}
            for col, tipo in [("qa_selo", "VARCHAR(20)"), ("qa_pct_sem_acrescimo", "REAL"),
                              ("qa_markup_xml", "REAL"), ("qa_custo_sem_venda", "INTEGER"),
                              ("qa_override_por_id", "INTEGER"), ("qa_override_motivo", "TEXT")]:
                if col not in pa_cols:
                    cur.execute(f"ALTER TABLE pool_ambientes ADD COLUMN {col} {tipo}")

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

        # ── parceiros (tenant) ────────────────────────────────────────────────
        cur.execute("PRAGMA table_info(parceiros)")
        par_cols = {row[1] for row in cur.fetchall()}
        if "rede_id" not in par_cols:
            cur.execute("ALTER TABLE parceiros ADD COLUMN rede_id INTEGER")
        if "abrangencia" not in par_cols:
            cur.execute("ALTER TABLE parceiros ADD COLUMN abrangencia VARCHAR(10) DEFAULT 'loja'")

        # ── nfe_emissao: doc da NF-e da fábrica (etapa 15) ────────────────────
        cur.execute("PRAGMA table_info(nfe_emissao)")
        nfe_cols = [r[1] for r in cur.fetchall()]
        if nfe_cols and "fabrica_doc_id" not in nfe_cols:
            cur.execute("ALTER TABLE nfe_emissao ADD COLUMN fabrica_doc_id INTEGER")

        # ── fiscal multi-CNPJ: vínculo loja/rede -> emitente (tabela emitente via create_all) ──
        if _tabela_existe(cur, "lojas"):
            loja_cols = {c[1] for c in cur.execute("PRAGMA table_info(lojas)").fetchall()}
            if "emitente_id" not in loja_cols:
                cur.execute("ALTER TABLE lojas ADD COLUMN emitente_id INTEGER")
        if _tabela_existe(cur, "redes"):
            rede_cols = {c[1] for c in cur.execute("PRAGMA table_info(redes)").fetchall()}
            if "emitente_central_id" not in rede_cols:
                cur.execute("ALTER TABLE redes ADD COLUMN emitente_central_id INTEGER")

        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

# ── Loja seed (F1 multi-tenant) ───────────────────────────────────────────────
# Espelha as constantes de mod_contrato.py (evita import circular database<->mod_contrato).
# Os CPFs das testemunhas são placeholders — corrigidos no configurador de lojas (F2).
_SEED_LOJA_NOME   = "INSPIRIUM MOVEIS PLANEJADOS E DECORACAO LTDA"
_SEED_LOJA_CNPJ   = "19.152.134/0001-56"
_SEED_LOJA_CODIGO = "INS"
_SEED_LOJA_TEL    = "(12) 3341-8777"
_SEED_LOJA_EMAIL  = "sac@dalmobilesjc.com.br"
_SEED_TEST1_NOME  = "Jaime Perinazzo"
_SEED_TEST1_CPF   = "xxx.xxx.xxx-xx"
_SEED_TEST2_NOME  = "Felipe Guizalberte"
_SEED_TEST2_CPF   = "yyy.yyy.yyy-yy"

# ── super_admin de bootstrap (F2 multi-tenant) ────────────────────────────────
# Hash SHA-256 igual ao Usuario.set_senha. Senha de exemplo ("trocar123") —
# TROCAR antes de produção. loja_id/rede_id NULL = plataforma.
_SEED_SA_NOME  = "Administrador da Plataforma"
_SEED_SA_LOGIN = "sad2026"
_SEED_SA_SENHA = "trocar123"

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

    # 2026-06-20: F1 multi-tenant — loja seed (das constantes do contrato) + backfill.
    if "tenancy_v1_2026" not in aplicadas and _tabela_existe(cur, "lojas"):
        cur.execute("SELECT id FROM lojas ORDER BY id LIMIT 1")
        row = cur.fetchone()
        if row is None:
            cur.execute(
                """INSERT INTO lojas
                   (nome, cnpj, codigo, telefone, email,
                    testemunha1_nome, testemunha1_cpf,
                    testemunha2_nome, testemunha2_cpf, ativo)
                   VALUES (?,?,?,?,?,?,?,?,?,1)""",
                (_SEED_LOJA_NOME, _SEED_LOJA_CNPJ, _SEED_LOJA_CODIGO,
                 _SEED_LOJA_TEL, _SEED_LOJA_EMAIL,
                 _SEED_TEST1_NOME, _SEED_TEST1_CPF,
                 _SEED_TEST2_NOME, _SEED_TEST2_CPF))
            loja_id = cur.lastrowid
        else:
            loja_id = row[0]

        for tbl in ("usuarios", "clientes", "projetos_meta", "orcamentos", "contratos"):
            if _tabela_existe(cur, tbl):
                cur.execute(f"UPDATE {tbl} SET loja_id=? WHERE loja_id IS NULL", (loja_id,))

        if _tabela_existe(cur, "parceiros") and _tabela_existe(cur, "parceiro_lojas"):
            cur.execute("UPDATE parceiros SET abrangencia='loja' WHERE abrangencia IS NULL")
            cur.execute("SELECT id, comissao_padrao_pct FROM parceiros")
            for pid, com in cur.fetchall():
                cur.execute("SELECT 1 FROM parceiro_lojas WHERE parceiro_id=? AND loja_id=?",
                            (pid, loja_id))
                if cur.fetchone() is None:
                    cur.execute(
                        """INSERT INTO parceiro_lojas
                           (parceiro_id, loja_id, comissao_padrao_pct, ativo)
                           VALUES (?,?,?,1)""",
                        (pid, loja_id, com or 0.0))

        cur.execute("INSERT INTO schema_migrations(id) VALUES('tenancy_v1_2026')")

    # 2026-06-21: F2 multi-tenant — super_admin de bootstrap (plataforma).
    # Só insere se a tabela usuarios tiver as colunas reais (pula schemas parciais de teste
    # sem mascarar erros reais: em produção a tabela vem completa do ORM).
    if "tenancy_v2_2026" not in aplicadas and _tabela_existe(cur, "usuarios"):
        cur.execute("PRAGMA table_info(usuarios)")
        _ucols = {r[1] for r in cur.fetchall()}
        if {"nome", "login", "senha_hash", "ativo"} <= _ucols:
            cur.execute("SELECT COUNT(*) FROM usuarios WHERE nivel='super_admin'")
            if cur.fetchone()[0] == 0:
                cur.execute(
                    """INSERT INTO usuarios (nome, login, senha_hash, nivel, ativo, loja_id, rede_id)
                       VALUES (?,?,?, 'super_admin', 1, NULL, NULL)""",
                    (_SEED_SA_NOME, _SEED_SA_LOGIN, _hash_senha(_SEED_SA_SENHA)))
            # marca aplicada só quando o schema real permitiu agir (não em schemas parciais de teste)
            cur.execute("INSERT INTO schema_migrations(id) VALUES('tenancy_v2_2026')")

    # 2026-06-24: backfill de usuario_lojas a partir de usuarios.loja_id (multi-loja)
    if "usuario_lojas_backfill_2026" not in aplicadas and _tabela_existe(cur, "usuario_lojas"):
        _backfill_usuario_lojas(cur)
        cur.execute("INSERT INTO schema_migrations(id) VALUES('usuario_lojas_backfill_2026')")

    # 2026-07-06: fiscal multi-CNPJ — backfill perfil_fiscal -> emitente (1 por loja/CNPJ);
    # loja.emitente_id = self. Idempotente: pula loja que já tem emitente_id.
    if _tabela_existe(cur, "emitente") and _tabela_existe(cur, "perfil_fiscal") \
            and _tabela_existe(cur, "lojas"):
        cur.execute("SELECT id, loja_id, razao_social, inscricao_estadual, inscricao_municipal, "
                    "regime_tributario, csosn_padrao, cfop_dentro_uf, cfop_fora_uf, serie_nfe, "
                    "discrimina_impostos, cnae_servico, cod_servico_municipio, aliquota_iss, "
                    "retencao_json, municipio_ibge, cert_validade, cert_cnpj, papel_cnpj, "
                    "focus_token_homolog_enc, focus_token_prod_enc, ambiente_ativo, "
                    "placeholders_json FROM perfil_fiscal")
        for row in cur.fetchall():
            loja_id = row[1]
            cur.execute("SELECT emitente_id FROM lojas WHERE id=?", (loja_id,))
            lj = cur.fetchone()
            if lj is None:
                continue   # perfil órfão (loja inexistente) — sem loja para receber o vínculo, ignora
            if lj[0]:
                continue   # já migrado
            cur.execute("SELECT cnpj, logradouro, numero, bairro, cidade, estado, cep "
                        "FROM lojas WHERE id=?", (loja_id,))
            lo = cur.fetchone() or (None,) * 7
            cur.execute(
                "INSERT INTO emitente (cnpj, razao_social, inscricao_estadual, inscricao_municipal, "
                "regime_tributario, csosn_padrao, cfop_dentro_uf, cfop_fora_uf, serie_nfe, "
                "discrimina_impostos, cnae_servico, cod_servico_municipio, aliquota_iss, "
                "retencao_json, municipio_ibge, logradouro, numero, bairro, cidade, uf, cep, "
                "cert_validade, cert_cnpj, papel_cnpj, focus_token_homolog_enc, "
                "focus_token_prod_enc, ambiente_ativo, placeholders_json) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (lo[0], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[10],
                 row[11], row[12], row[13], row[14], row[15],
                 lo[1], lo[2], lo[3], lo[4], lo[5], lo[6],
                 row[16], row[17], row[18], row[19], row[20], row[21], row[22]))
            cur.execute("UPDATE lojas SET emitente_id=? WHERE id=?", (cur.lastrowid, loja_id))

    conn.commit()


def _backfill_loja_operacional():
    """F4: nenhuma linha operacional pode ficar sem loja (senão some no filtro de escopo).
    Backfill defensivo NULL -> loja-semente (id=1). Idempotente."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        for tbl in ("clientes", "projetos_meta", "orcamentos", "contratos"):
            cur.execute(f"UPDATE {tbl} SET loja_id=1 WHERE loja_id IS NULL")
        conn.commit()
    finally:
        conn.close()


def _drop_coluna_margens_orcamentos():
    """Faxina: remove a coluna legada/duplicada Orcamento.margens (dados já em
    Projeto.parametros_json + Orcamento.desconto_pct). Idempotente — só dropa se existir
    (sqlite >= 3.35)."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cols = {r[1] for r in cur.execute("PRAGMA table_info(orcamentos)")}
        if "margens" in cols:
            cur.execute("ALTER TABLE orcamentos DROP COLUMN margens")
            conn.commit()
    except Exception as e:
        print("[FAXINA] drop coluna margens:", e)
    finally:
        conn.close()


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
    _backfill_loja_operacional()
    _drop_coluna_margens_orcamentos()


def get_session():
    return Session()


def loja_seed_id(db):
    """Id da loja seed (a 1ª loja por id), ou None se ainda não houver loja."""
    loja = db.query(Loja).order_by(Loja.id).first()
    return loja.id if loja else None


def upsert_projeto_status(nome_safe: str, status: str, perdido_em=None):
    """Cria ou atualiza o registro de status do projeto. Thread-safe via sessão própria."""
    db = get_session()
    try:
        p = db.get(Projeto, nome_safe)
        if not p:
            p = Projeto(nome_safe=nome_safe)
            p.loja_id = loja_seed_id(db)   # F4: nunca criar projeto sem loja (evita 404 fantasma)
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


def membership_loja_ids(db, usuario_id):
    """IDs das lojas acessíveis do usuário (via usuario_lojas)."""
    rows = (db.query(UsuarioLoja.loja_id)
              .filter(UsuarioLoja.usuario_id == usuario_id).all())
    return [r[0] for r in rows]


def _backfill_usuario_lojas(cur):
    """Idempotente: cria 1 membership para cada usuário com loja_id e sem vínculo ainda."""
    cur.execute("""
        INSERT INTO usuario_lojas (usuario_id, loja_id)
        SELECT u.id, u.loja_id FROM usuarios u
        WHERE u.loja_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM usuario_lojas ul
                          WHERE ul.usuario_id = u.id AND ul.loja_id = u.loja_id)
    """)
