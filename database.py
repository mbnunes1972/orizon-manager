"""
database.py — Conexão SQLAlchemy + modelos de dados
Orizon Manager | Dalmóbile
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, sessionmaker, relationship, validates
from datetime import datetime
import hashlib
import os
from auth import perfis

def _hash_senha(senha: str) -> str:
    """SHA-256 hex de uma senha. Fonte única de hashing (Usuario + bootstrap/seed)."""
    return hashlib.sha256(senha.encode()).hexdigest()


# ── Conexão ──────────────────────────────────────────────────────────────────
# Migração 2026-07-15 (docs/superpowers/specs/2026-07-15-migracao-postgresql.md): DATABASE_URL ausente
# = comportamento antigo (SQLite local, dev). DATABASE_URL setada (produção, pós-cutover) = Postgres,
# ex.: postgresql+psycopg2://orizon:<senha>@localhost/orizon
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))


def _resolver_config_db(database_url, default_db_path):
    """Resolve (db_path, engine_url) a partir da DATABASE_URL, para permitir banco
    SEPARADO por instância (ex.: INTEGRAÇÃO :8765 e PRÉ-HOMOLOGAÇÃO :8766 no mesmo
    servidor — ver Plano de Testes / instância B).

    `sqlite:///<arquivo>`: db_path SEGUE esse arquivo. É crucial — as migrações de
    init_db (_migrar_pre_schema/_migrar_colunas/_migrar_dados) usam `sqlite3.connect(DB_PATH)`
    direto; se db_path ficasse no orizon.db default enquanto o engine usa outro arquivo,
    a instância B mexeria no banco da instância A (contaminação cruzada).
    Postgres/None: db_path fica no default (em não-sqlite as migrações sqlite3 são puladas)."""
    if database_url and database_url.startswith("sqlite:///"):
        return database_url[len("sqlite:///"):], database_url
    return default_db_path, (database_url or f"sqlite:///{default_db_path}")


DATABASE_URL = os.environ.get("DATABASE_URL")
DB_PATH, _ENGINE_URL = _resolver_config_db(DATABASE_URL, os.path.join(BASE_DIR, "orizon.db"))
ENGINE       = create_engine(_ENGINE_URL, echo=False)
Session      = sessionmaker(bind=ENGINE)

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
    senha_provisoria = Column(Integer,  default=0)   # 1 = precisa trocar a senha no 1º login
    funcionario_id = Column(Integer,    ForeignKey("funcionarios.id"), nullable=True)  # RH (Cadastro) que esta conta representa
    # Função (cargo) da CONTA quando não há Funcionário vinculado (Perfil-4 rev2 §2): a coluna Função
    # de Usuários da Loja usa Funcionario.funcao_id se houver vínculo, senão este funcao_id.
    funcao_id     = Column(Integer,     ForeignKey("funcoes.id"), nullable=True)
    tema          = Column(String(10),  default="escuro")   # 'claro' | 'escuro'
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


class LogAcessoDelegado(Base):
    """Auditoria do step-up por senha: fulano acessou um módulo/painel fora do perfil com a
    autorização (senha) de alguém que tinha o perfil. Molde do LogAcaoGerencial."""
    __tablename__ = "log_acesso_delegado"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    solicitante_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=False)
    autorizador_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    recurso        = Column(String(40), nullable=False)   # id do módulo ou 'admin'/'config'
    contexto       = Column(Text,     nullable=True)      # JSON opcional
    criado_em      = Column(DateTime, default=datetime.utcnow)


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
    tipo_dest          = Column(Text, default="nao_contribuinte")  # contribuinte|isento|nao_contribuinte
    cnpj               = Column(String(18), nullable=True)
    inscricao_estadual = Column(Text, nullable=True)
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
    municipio_ibge = Column(String(7),  nullable=True)   # código IBGE do município (tomador NFS-e; via ViaCEP)
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
    pix                 = Column(String(140),  nullable=True)    # chave PIX p/ pagamento de comissão (v10)


class Funcao(Base):
    """Tabela de Funções (Modulos_Orizon_v10, Config): catálogo único de funções/cargos referenciado
    por Funcionário.funcao_id e Terceiro.funcao_id — substitui texto livre / listas separadas."""
    __tablename__ = "funcoes"

    id        = Column(Integer,     primary_key=True, autoincrement=True)
    loja_id   = Column(Integer,     ForeignKey("lojas.id"), nullable=True)
    nome      = Column(String(80),  nullable=False)
    status    = Column(String(10),  nullable=False, default="ativo")   # ativo | inativo
    perfil_padrao = Column(String(40), nullable=True)   # slug do perfil_acesso default da função
    atribuicoes_json   = Column(Text,        nullable=True)   # JSON: papéis (mod_escopo.PAPEIS)
    remuneracao_padrao = Column(String(20),  nullable=True)   # fixa | variavel | fixa_variavel
    regime_trabalho    = Column(String(20),  nullable=True)   # presencial | remoto | misto
    regime_contratacao = Column(String(20),  nullable=True)   # registrado | terceirizacao
    descricao          = Column(Text,        nullable=True)   # descrição livre do que a função faz
    salario_fixo        = Column(Float,   nullable=True)   # parte fixa mensal da função
    beneficios_json     = Column(Text,    nullable=True)   # {"at":{"on","valor"},"va":..,"ps":..}
    comissao_json       = Column(Text,    nullable=True)   # {"por_meta","base","pct"|"faixas"} (não-consultor)
    usa_comissao_vendas = Column(Integer, default=0)       # 1 = comissão vem do comissao_vendas da loja (Consultor)
    criado_em = Column(DateTime,    default=datetime.utcnow)


class PerfilAcesso(Base):
    """Perfil de acesso configurável POR LOJA (Regras_Funcoes_Perfis_Atribuicoes rev3 §2).
    Acesso a módulo/painel vem de `modulos_json`; capacidades finas = base perfis.PERFIS[`base`]
    com overrides opcionais em `capacidades_json`."""
    __tablename__ = "perfil_acesso"

    id           = Column(Integer,     primary_key=True, autoincrement=True)
    loja_id      = Column(Integer,     ForeignKey("lojas.id"), nullable=False)  # perfis são por loja
    slug         = Column(String(40),  nullable=False)   # único globalmente (system: master/gerencial/operador)
    nome         = Column(String(80),  nullable=False)
    base         = Column(String(20),  nullable=False)   # master | gerencial | operador (preset das caps finas)
    modulos_json = Column(Text,        nullable=False, default="[]")  # JSON: ids de módulo/painel acessíveis
    capacidades_json = Column(Text,    nullable=False, default="{}")  # JSON {cap: bool} — overrides sobre a base
    sistema      = Column(Integer,     nullable=False, default=0)     # 1 = padrão, não apagável
    criado_em    = Column(DateTime,    default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("loja_id", "slug", name="uq_perfil_loja_slug"),)


class FolhaPagamento(Base):
    """Folha de Pagamento (Modulos_Orizon_v10, §2.1): um registro por Funcionário/competência.
    Parte fixa vem do cadastro; parte variável = vendas do período × % da faixa de meta (auto-cálculo).
    Despesa lançada nas contas existentes do Plano de Contas (5.3) — motor, não digitação."""
    __tablename__ = "folha_pagamento"

    id             = Column(Integer,     primary_key=True, autoincrement=True)
    loja_id        = Column(Integer,     ForeignKey("lojas.id"), nullable=True)
    funcionario_id = Column(Integer,     ForeignKey("funcionarios.id"), nullable=False)
    competencia    = Column(String(7),   nullable=False)          # 'AAAA-MM'
    parte_fixa     = Column(Float,       nullable=True, default=0.0)
    vendas_liq     = Column(Float,       nullable=True, default=0.0)   # base da variável (valor líquido do período)
    faixa_pct      = Column(Float,       nullable=True, default=0.0)   # % da faixa de meta atingida
    parte_variavel = Column(Float,       nullable=True, default=0.0)
    base_comissao  = Column(Float,       nullable=True, default=0.0)   # base editável da comissão (recalcula variável)
    beneficios     = Column(Float,       nullable=True, default=0.0)   # Σ AT/VA/PS ativos da Função
    total          = Column(Float,       nullable=True, default=0.0)
    status         = Column(String(10),  nullable=False, default="aberta")   # aberta | paga
    ref_lancamento = Column(String(60),  nullable=True)           # ref idempotente do lançamento contábil
    gerado_em      = Column(DateTime,    default=datetime.utcnow)
    pago_em        = Column(DateTime,    nullable=True)


class ComissaoFolha(Base):
    """Item de comissão de um funcionário numa competência (Fase 4). Um funcionário pode ter vários
    (por etapa/projeto). origem='papel' vem da conclusão de etapa (Mapa); origem='venda' é a comissão
    do Consultor. A parte variável da Folha = Σ valor dos itens (status != 'cancelado')."""
    __tablename__ = "comissao_folha"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id        = Column(Integer,  ForeignKey("lojas.id"), nullable=True)
    funcionario_id = Column(Integer,  ForeignKey("funcionarios.id"), nullable=False)
    competencia    = Column(String(7), nullable=False)          # 'AAAA-MM' = mês de concluido_em
    origem         = Column(String(10), nullable=False, default="papel")  # papel | venda
    papel          = Column(String(30), nullable=True)          # projeto_executivo|medicao|montagem|assistencia|venda
    projeto_nome   = Column(Text,     nullable=True)            # nome_safe (rastreabilidade)
    etapa_codigo   = Column(String(8), nullable=True)           # etapa que disparou (papel); NULL p/ venda
    base           = Column(Float,    nullable=True, default=0.0)   # Σ order_total dos ambientes (ou vendas líq.)
    base_ajustada  = Column(Float,    nullable=True)            # override manual da base
    pct            = Column(Float,    nullable=True, default=0.0)
    valor          = Column(Float,    nullable=True, default=0.0)   # base_efetiva × pct/100
    status         = Column(String(12), nullable=False, default="previsto")  # previsto|confirmado|cancelado
    ref_etapa      = Column(String(120), nullable=True)        # idempotência: '<projeto>:<etapa>:<func>' ou 'venda:<func>:<comp>'
    criado_em      = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("ref_etapa", name="uq_comissao_ref_etapa"),)


class AdiantamentoFuncionario(Base):
    """Adiantamento/empréstimo a funcionário (Fase 5). 'oficial' = 40% do salário fixo (auto, carteira);
    'adiantamento' = adiantamento avulso; 'emprestimo' = empréstimo (pode atravessar meses). abater/
    competencia_abate controlam a dedução do líquido; quitado marca a baixa quando a folha é paga."""
    __tablename__ = "adiantamento_funcionario"
    id                = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id           = Column(Integer,  ForeignKey("lojas.id"), nullable=True)
    funcionario_id    = Column(Integer,  ForeignKey("funcionarios.id"), nullable=False)
    tipo              = Column(String(14), nullable=False, default="adiantamento")  # oficial|adiantamento|emprestimo
    competencia       = Column(String(7), nullable=False)          # 'AAAA-MM' concedido
    valor             = Column(Float,    nullable=True, default=0.0)
    abater            = Column(Integer,  nullable=False, default=1)  # 1 = deduz do líquido (editável)
    competencia_abate = Column(String(7), nullable=True)           # folha que deduz
    quitado           = Column(Integer,  nullable=False, default=0)  # 1 = baixado (folha paga)
    observacao        = Column(Text,     nullable=True)
    ref               = Column(String(120), nullable=True)         # idempotência do oficial: 'oficial:<func>:<comp>'
    criado_em         = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("ref", name="uq_adiantamento_ref"),)


class Funcionario(Base):
    """Cadastro de RH (Modulos_Orizon_v9, módulo 2). NÃO é conta de login — o Usuário (Admin/Núcleo)
    referencia o Funcionário via usuario_id/funcionario_id, sem duplicar dado pessoal."""
    __tablename__ = "funcionarios"

    id                 = Column(Integer,     primary_key=True, autoincrement=True)
    loja_id            = Column(Integer,     ForeignKey("lojas.id"), nullable=True)
    nome               = Column(String(150), nullable=False)
    cpf                = Column(String(20),  nullable=True)
    telefone           = Column(String(20),  nullable=True)
    email              = Column(String(120), nullable=True)
    cargo              = Column(String(80),  nullable=True)   # legado (texto) — ver funcao_id
    funcao_id          = Column(Integer,     ForeignKey("funcoes.id"), nullable=True)  # → Tabela de Funções (v10)
    remuneracao_tipo   = Column(String(20),  nullable=True)   # fixa | fixa_variavel
    remuneracao_fixa   = Column(Float,       nullable=True)
    remuneracao_var    = Column(Float,       nullable=True)   # parte variável (se fixa_variavel)
    # Endereço (mesmo bloco de Clientes) + Dados Bancários completos (v10)
    cep          = Column(String(9),   nullable=True)
    logradouro   = Column(String(200), nullable=True)
    numero       = Column(String(20),  nullable=True)
    complemento  = Column(String(100), nullable=True)
    bairro       = Column(String(100), nullable=True)
    cidade       = Column(String(80),  nullable=True)
    uf           = Column(String(2),   nullable=True)
    banco_nome   = Column(String(80),  nullable=True)
    banco_codigo = Column(String(6),   nullable=True)
    agencia      = Column(String(12),  nullable=True)
    conta        = Column(String(20),  nullable=True)
    pix          = Column(String(140), nullable=True)
    status             = Column(String(10),  nullable=False, default="ativo")   # ativo | inativo
    usuario_id         = Column(Integer,     ForeignKey("usuarios.id"), nullable=True)  # conta de login (se houver)
    criado_em          = Column(DateTime,    default=datetime.utcnow)


class Fornecedor(Base):
    """Fornecedor PJ/PF (Modulos_Orizon_v9). Referenciado por 'Fornecedores a Pagar' (Financeiro 2.1)."""
    __tablename__ = "fornecedores"

    id              = Column(Integer,     primary_key=True, autoincrement=True)
    loja_id         = Column(Integer,     ForeignKey("lojas.id"), nullable=True)
    tipo_pessoa     = Column(String(2),   nullable=False, default="pj")   # pj | pf
    nome            = Column(String(180), nullable=False)                 # razão social / nome
    cnpj_cpf        = Column(String(18),  nullable=True)
    telefone        = Column(String(20),  nullable=True)
    email           = Column(String(120), nullable=True)
    categoria       = Column(String(20),  nullable=True)   # materia_prima | transportadora | servicos | outro
    prazo_pagamento = Column(Integer,     nullable=True)   # dias
    dados_bancarios = Column(Text,        nullable=True)   # legado (texto livre)
    # Endereço + Dados Bancários estruturados (v10)
    cep          = Column(String(9),   nullable=True)
    logradouro   = Column(String(200), nullable=True)
    numero       = Column(String(20),  nullable=True)
    complemento  = Column(String(100), nullable=True)
    bairro       = Column(String(100), nullable=True)
    cidade       = Column(String(80),  nullable=True)
    uf           = Column(String(2),   nullable=True)
    banco_nome   = Column(String(80),  nullable=True)
    banco_codigo = Column(String(6),   nullable=True)
    agencia      = Column(String(12),  nullable=True)
    conta        = Column(String(20),  nullable=True)
    pix          = Column(String(140), nullable=True)
    status          = Column(String(10),  nullable=False, default="ativo")
    criado_em       = Column(DateTime,    default=datetime.utcnow)


class Terceiro(Base):
    """Prestador Pessoa Física (Modulos_Orizon_v9): sempre PF (PJ vira Fornecedor). O Montador é a mesma
    pessoa da 'Execução da Montagem' (Financeiro) — referência, nunca cadastro duplicado."""
    __tablename__ = "terceiros"

    id              = Column(Integer,     primary_key=True, autoincrement=True)
    loja_id         = Column(Integer,     ForeignKey("lojas.id"), nullable=True)
    nome            = Column(String(150), nullable=False)
    cpf             = Column(String(20),  nullable=True)
    telefone        = Column(String(20),  nullable=True)
    tipo_servico    = Column(String(20),  nullable=True)   # legado — ver funcao_id
    funcao_id       = Column(Integer,     ForeignKey("funcoes.id"), nullable=True)  # → Tabela de Funções (v10)
    pix             = Column(String(140), nullable=True)
    dados_bancarios = Column(Text,        nullable=True)   # legado (texto livre)
    condicao        = Column(String(12),  nullable=True)   # mei | autonomo
    # Endereço + Dados Bancários completos (v10)
    cep          = Column(String(9),   nullable=True)
    logradouro   = Column(String(200), nullable=True)
    numero       = Column(String(20),  nullable=True)
    complemento  = Column(String(100), nullable=True)
    bairro       = Column(String(100), nullable=True)
    cidade       = Column(String(80),  nullable=True)
    uf           = Column(String(2),   nullable=True)
    banco_nome   = Column(String(80),  nullable=True)
    banco_codigo = Column(String(6),   nullable=True)
    agencia      = Column(String(12),  nullable=True)
    conta        = Column(String(20),  nullable=True)
    # Conta de login OPCIONAL restrita (Regras_Funcoes_Perfis_Atribuicoes §10): com conta, o Terceiro
    # ganha visão de Montagem/Assistência dos ambientes atribuídos. Coluna só; fluxo em passe seguinte.
    usuario_id      = Column(Integer,     ForeignKey("usuarios.id"), nullable=True)
    status          = Column(String(10),  nullable=False, default="ativo")
    criado_em       = Column(DateTime,    default=datetime.utcnow)


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
    responsavel = Column(String(120), nullable=True)
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
    modulos_ativos = Column(Text, nullable=True)   # JSON: domínios ativos; NULL/"" = todos ligados (topologia)
    # Segmentação de receita Mercadoria × Serviço (default da loja; seed 65/35). Val_Cont divide-se
    # em Mercadoria (NF-e produto) + Serviço (NFS-e); override por projeto vive em parametros_json.
    pct_mercadoria = Column(Float, nullable=True, default=65.0)
    pct_servico    = Column(Float, nullable=True, default=35.0)


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
    data_entrega   = Column(DateTime,   nullable=True)   # âncora do cronograma REGRESSIVO (entrega ao cliente, def. na assinatura)
    data_inicio    = Column(DateTime,   nullable=True)   # âncora do cronograma PROGRESSIVO (início; def. assinatura + carência)
    equipe_json    = Column(Text,       nullable=True)   # Equipe do Projeto: seleções dos papéis SELETORES (medidor/finalizador/montagem[N])


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
    num_proposta    = Column(String,   nullable=True)   # nº da proposta comercial 'PV<AAAAMMDD><SEQ>' (gerado 1x)
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
    # Fatia B (resultado financeiro): ramo do custo financeiro confirmado na AF (box).
    ramo_financeiro     = Column(String,  nullable=True)   # loja|loja_antecipacao|financeira (NULL = auto pela forma de pagamento)
    ramo_financeiro_seq = Column(Integer, default=0)       # contador p/ ref idempotente de troca de ramo
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
    concluido_em   = Column(DateTime, nullable=True)   # = data_conclusao (Modulos_Orizon_v11)
    # Cronograma do Ciclo (Modulos_Orizon_v11): data prevista de conclusão (D0 + prazo padrão),
    # constituída na assinatura do contrato; editável só por reautenticação Gerente+ (auditada).
    data_prevista_conclusao = Column(DateTime, nullable=True)
    # Responsável por função (Modulos_Orizon_v12): funcao_responsavel_id é herdada do Cronograma de
    # Projeto Padrão no D0 (a FUNÇÃO que executa a fase); responsavel_funcionario_id nasce vazio e é
    # escolhido depois, restrito aos funcionários que têm essa função.
    funcao_responsavel_id       = Column(Integer, ForeignKey("funcoes.id"), nullable=True)
    responsavel_funcionario_id  = Column(Integer, ForeignKey("funcionarios.id"), nullable=True)
    observacoes    = Column(Text,     nullable=True)

    __table_args__ = (UniqueConstraint("projeto_nome", "etapa_codigo", name="uq_ciclo_etapa"),)

    responsavel = relationship("Usuario", foreign_keys=[responsavel_id])


class AtribuicaoAmbiente(Base):
    """Mapa de Atribuições (Regras_Funcoes_Perfis_Atribuicoes §4/§5): quem executa cada papel
    operacional (PE/Medição/Montagem/Assistência) por ambiente do projeto. A atribuição CONCEDE
    visibilidade escopada ao Usuário vinculado ao profissional. pool_ambiente_id NULL = 'projeto
    inteiro' (default que vale para os ambientes sem atribuição própria). Um profissional por
    papel/ambiente (UniqueConstraint). Trocas ficam em LogAcaoGerencial (sem versionar a tabela)."""
    __tablename__ = "atribuicoes_ambiente"

    id               = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id          = Column(Integer,  ForeignKey("lojas.id"), nullable=False)   # isolamento F4
    projeto_nome     = Column(Text,     nullable=False)                            # nome_safe
    pool_ambiente_id = Column(Integer,  ForeignKey("pool_ambientes.id"), nullable=True)  # NULL = projeto inteiro
    papel            = Column(Text,     nullable=False)   # projeto_executivo|medicao|montagem|assistencia
    funcionario_id   = Column(Integer,  ForeignKey("funcionarios.id"), nullable=True)
    terceiro_id      = Column(Integer,  ForeignKey("terceiros.id"), nullable=True)
    atribuido_por_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    criado_em        = Column(DateTime, default=datetime.utcnow)
    atualizado_em    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("projeto_nome", "pool_ambiente_id", "papel",
                                       name="uq_atribuicao_papel_ambiente"),)


class CicloLogistico(Base):
    """Expedição (Modulos_Orizon_v5, módulo 7): pedido produzido -> cliente com o produto.
    Estado AGREGADO + referências por ID a Projetos/Estoque/Fiscal — NUNCA duplica dado.
    Prazos (planejado) entram uma vez na criação; datas (realizado) são capturadas ao mover o card."""
    __tablename__ = "ciclo_logistico"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id        = Column(Integer,  ForeignKey("lojas.id"), nullable=True)
    projeto_nome   = Column(Text,     nullable=False)                 # ref: nome_safe do projeto
    numero_pedido  = Column(Text,     nullable=True)                  # nº do pedido na fábrica
    status_atual   = Column(Text,     nullable=False, default="Pedido Enviado")
    # Prazos (planejado — informados pela fábrica na criação)
    prazo_producao    = Column(Date, nullable=True)
    prazo_saida       = Column(Date, nullable=True)
    prazo_recebimento = Column(Date, nullable=True)
    prazo_entrega     = Column(Date, nullable=True)
    # Realizado (capturado ao mover o card, editável)
    data_producao     = Column(Date, nullable=True)
    data_saida        = Column(Date, nullable=True)
    data_recebimento  = Column(Date, nullable=True)
    data_entrega      = Column(Date, nullable=True)
    # Transporte
    transportadora = Column(Text, nullable=True)
    cte            = Column(Text, nullable=True)                      # conhecimento de transporte
    rastreio       = Column(Text, nullable=True)
    # Referências (nunca duplica): NF-e é dado do Fiscal
    nfe_id         = Column(Integer, ForeignKey("documento_fiscal.id"), nullable=True)
    criado_em      = Column(DateTime, nullable=True)
    criado_por_id  = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    # Desmembramento parcial (spec 2026-07-13, Fatia 2): 1 linha por parcela; NULL = projeto-wide legado.
    parcela_id     = Column(Integer,  ForeignKey("parcela_projeto.id"), nullable=True)


class CicloLogisticoTransicao(Base):
    """Histórico auditável de mudanças de status_atual do CicloLogistico (quem/quando)."""
    __tablename__ = "ciclo_logistico_transicao"

    id                 = Column(Integer,  primary_key=True, autoincrement=True)
    ciclo_logistico_id = Column(Integer,  ForeignKey("ciclo_logistico.id"), nullable=False)
    de_status          = Column(Text,     nullable=True)
    para_status        = Column(Text,     nullable=False)
    usuario_id         = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    quando             = Column(DateTime, nullable=True)


# ── Desmembramento parcial na Revisão de PE (spec docs/superpowers/specs/2026-07-13-...) ────────

class ParcelaProjeto(Base):
    """Parcela = grupo de ambientes que percorre o ciclo (aprovação→entrega→NF-e) de forma
    independente (decisão #1). Congela a fração do Val_Cont na criação (#5). Usada a partir da Fatia 2.
    `saldo_margem_estimado` é DERIVADO (#9), recalculável de pool_ambientes + arquivo_pe — a coluna
    existe só como cache opcional, nunca como fonte de verdade."""
    __tablename__ = "parcela_projeto"
    id                    = Column(Integer,  primary_key=True, autoincrement=True)
    projeto_nome          = Column(Text,     nullable=False, index=True)   # nome_safe
    ordem                 = Column(Integer,  nullable=False, default=1)     # maior ordem = "última" (#5)
    status                = Column(String(16), nullable=False, default="aguardando")  # aguardando|em_aprovacao|liquidada
    fracao_val_cont       = Column(Float,    nullable=False, default=0.0)   # congelada (#5)
    val_cont_congelado    = Column(Float,    nullable=False, default=0.0)   # congelado (#5)
    orcamento_id          = Column(Integer,  ForeignKey("orcamentos.id"), nullable=True)
    saldo_margem_estimado = Column(Float,    nullable=True)   # cache opcional do derivado (#9)
    criado_em             = Column(DateTime, default=datetime.utcnow)
    criado_por_id         = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    prazo_conclusao       = Column(DateTime, nullable=True)   # Fase A: prazo da fase (validado × cronograma)


class ParcelaAmbiente(Base):
    """Membership N:N parcela ↔ ambiente do pool (#1)."""
    __tablename__ = "parcela_ambiente"
    parcela_id       = Column(Integer, ForeignKey("parcela_projeto.id"), primary_key=True)
    pool_ambiente_id = Column(Integer, ForeignKey("pool_ambientes.id"),  primary_key=True)


class ArquivoPE(Base):
    """XML/Promob do Projeto Executivo — FORA do pool do orçamento (decisão #2). Documento de
    comparação/liquidação: NÃO cria PoolAmbiente, NÃO vincula a orçamento, NÃO alimenta o motor →
    não esbarra na trava `_contrato_assinado`. `valor_atualizado` = CFO/custo de fábrica extraído do
    XML (Σ order_total), NÃO valor de venda (#4)."""
    __tablename__ = "arquivo_pe"
    id               = Column(Integer,  primary_key=True, autoincrement=True)
    projeto_nome     = Column(Text,     nullable=False, index=True)   # nome_safe
    pool_ambiente_id = Column(Integer,  ForeignKey("pool_ambientes.id"), nullable=False)  # a qual ambiente o PE se refere
    formato          = Column(String(10), nullable=False)   # 'xml_pe' | 'promob_pe'
    arquivo_path     = Column(Text,     nullable=True)
    valor_atualizado = Column(Float,    nullable=True)       # CFO do PE (só p/ 'xml_pe'); null = não carregado
    carregado_em     = Column(DateTime, default=datetime.utcnow)
    carregado_por_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    __table_args__ = (UniqueConstraint("projeto_nome", "pool_ambiente_id", "formato", name="uq_arquivo_pe"),)


class AssistenciaCaso(Base):
    """Módulo Assistências (Modulos_Orizon_v5, módulo 10 / Financeiro v7 §6): atendimento pós-execução.
    Duas dimensões independentes: sub_tipo (montagem × pós-conclusão) e tipo_custo (paga/loja/fabrica),
    este DERIVADO do motivo. Realizar o caso dispara o lançamento contábil conforme o tipo de custo."""
    __tablename__ = "assistencia_caso"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id        = Column(Integer,  ForeignKey("lojas.id"), nullable=True)
    projeto_nome   = Column(Text,     nullable=True)                 # ref: nome_safe (opcional)
    sub_tipo       = Column(Text,     nullable=False)                # "montagem" | "pos_conclusao"
    motivo         = Column(Text,     nullable=False)                # chave de mod_assistencias.MOTIVOS
    tipo_custo     = Column(Text,     nullable=False)                # "paga" | "loja" | "fabrica" (derivado)
    descricao      = Column(Text,     nullable=True)
    valor          = Column(Float,    nullable=True)                 # custo do reparo / valor da venda
    status         = Column(Text,     nullable=False, default="aberto")   # aberto | realizado
    reembolsado_fabrica = Column(Integer, nullable=True)             # fase 2: fábrica reembolsou de fato
    ref_lancamento = Column(Text,     nullable=True)                 # ref idempotente do lançamento
    criado_em      = Column(DateTime, nullable=True)
    realizado_em   = Column(DateTime, nullable=True)
    criado_por_id  = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)


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
    travada_em   = Column(DateTime, nullable=True)      # Fatia C (#10): versão aprovada e travada (não reedita sem Diretor)

    __table_args__ = (UniqueConstraint("orcamento_id", "versao", name="uq_provisao_orc_versao"),)


class Conta(Base):
    """Conta do Plano de Contas (árvore hierárquica), por owner (rede|loja).
    Módulo Financeiro sub-projeto #1. Fonte: Especificacao_Financeiro_Orizon_v2.docx §2/§2.1."""
    __tablename__ = "conta"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    owner_tipo = Column(String(10), nullable=False)   # 'rede' | 'loja'
    owner_id   = Column(Integer,    nullable=False)
    codigo     = Column(String(20), nullable=False)   # hierárquico: '5', '5.4', '5.4.01'
    nome       = Column(Text,       nullable=False)
    grupo      = Column(Integer,    nullable=False)    # 1..5 (Ativo/Passivo/PL/Receita/Despesa)
    tipo       = Column(String(10), nullable=False)    # 'sintetica' (agrupa) | 'analitica' (folha)
    natureza   = Column(String(8),  nullable=False)    # 'devedora' | 'credora'
    pai_id     = Column(Integer, ForeignKey("conta.id"), nullable=True)
    ativa      = Column(Integer, default=1)
    ordem      = Column(Integer, default=0)
    criado_em     = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint("owner_tipo", "owner_id", "codigo", name="uq_conta_owner_codigo"),)


class Lancamento(Base):
    """Lançamento contábil (partida dobrada) do Livro. Módulo Financeiro sub-projeto #2.
    Carrega projeto_id (dimensão gerencial, = nome_safe). `data` = competência."""
    __tablename__ = "lancamento"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    owner_tipo       = Column(String(10), nullable=False)
    owner_id         = Column(Integer,    nullable=False)
    data             = Column(DateTime,   nullable=False, default=datetime.utcnow)
    conta_debito_id  = Column(Integer, ForeignKey("conta.id"), nullable=False)
    conta_credito_id = Column(Integer, ForeignKey("conta.id"), nullable=False)
    valor            = Column(Float,      nullable=False)
    projeto_id       = Column(String,     nullable=True)    # nome_safe (dimensão gerencial)
    origem           = Column(String(64), nullable=False, default="manual")   # 'manual' | tipo de evento
    # 2026-07-15: alargado de String(30) — SQLite nunca validou o limite, mas vários EVENTOS de
    # mod_contabil.py passam de 30 chars (ex.: 'reconhecimento_despesa_retencao_com_vendas', 42
    # chars); achado ao validar a suíte contra Postgres de verdade (Etapa 4 da migração).
    historico        = Column(Text,       nullable=True)
    ref              = Column(String(80), nullable=True)   # idempotência do wiring (ex.: 'fat:NFE-<proj>-<id>')
    motivo           = Column(String(30), nullable=True)   # dimensão do reparo em garantia: 'defeito_fabrica'|'outro' (§6.2)
    ia_sugestao      = Column(Text,       nullable=True)    # snapshot da sugestão da IA de classificação (§6.3)
    criado_em        = Column(DateTime,   default=datetime.utcnow)


class PeriodoContabil(Base):
    """Snapshot de Auditoria/Reconciliação de um período (Módulo Financeiro sub-projeto #6).
    Rateia a despesa fixa aos projetos (margem plena) e registra a divergência vs. o resultado societário."""
    __tablename__ = "periodo_contabil"
    id                   = Column(Integer, primary_key=True, autoincrement=True)
    owner_tipo           = Column(String(10), nullable=False)
    owner_id             = Column(Integer,    nullable=False)
    inicio               = Column(DateTime, nullable=True)
    fim                  = Column(DateTime, nullable=True)
    status               = Column(String(10), default="fechado")   # 'aberto' | 'fechado'
    metodologia          = Column(String(30), nullable=False)      # base de rateio (vigência)
    resultado_societario = Column(Float, default=0.0)
    soma_margem_plena    = Column(Float, default=0.0)
    divergencia_residual = Column(Float, default=0.0)
    dados_json           = Column(Text, nullable=True)             # alocacao_por_projeto serializada
    criado_em            = Column(DateTime, default=datetime.utcnow)


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
    modelo_versao_id     = Column(Integer, ForeignKey("documento_modelos.id"), nullable=True)
    # NULL = contrato legado -> cai no contrato_template/contrato.md global.
    # Preenchido = reproduz as cláusulas daquela versão, mesmo que a loja já
    # tenha trocado o modelo. Ver docs/superpowers/specs/2026-07-15-modelos-documentos-loja-design.md D6.

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


class DocumentoModelo(Base):
    """Modelo de documento de uma loja (contrato/proposta), versionado.

    IMUTÁVEL: uma versão nunca muda de corpo_md depois de criada. Editar é criar
    a versão seguinte. É o que dá sentido a Contrato.modelo_versao_id — se a linha
    fosse mutável, o ponteiro não garantiria a reprodução do contrato assinado.
    """
    __tablename__ = "documento_modelos"

    # @validates é o ÚNICO do database.py — deliberado, não desleixo: nenhuma outra
    # tabela carrega uma garantia jurídica. Aqui a imutabilidade não é preferência de
    # estilo, é o que sustenta reproduzir as cláusulas de um contrato já assinado.
    # Docstring não impede `m.corpo_md = "outra"; db.commit()`; isto impede.

    id            = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id       = Column(Integer,  ForeignKey("lojas.id"), nullable=False)
    tipo          = Column(Text,     nullable=False)   # contrato | proposta
    versao        = Column(Integer,  nullable=False)   # sequencial por (loja_id, tipo)
    nome          = Column(Text,     nullable=True)
    corpo_md      = Column(Text,     nullable=False)
    origem_nome   = Column(Text,     nullable=True)
    origem_path   = Column(Text,     nullable=True)
    origem_sha256 = Column(Text,     nullable=True)
    ativo         = Column(Integer,  nullable=False, default=0)
    criado_em     = Column(DateTime, default=datetime.utcnow)
    criado_por_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("loja_id", "tipo", "versao", name="uq_doc_modelo_versao"),
    )

    @validates("corpo_md")
    def _corpo_e_imutavel(self, key, value):
        """Barra a edição de corpo_md depois que a linha existe.

        Dispara no setattr. `self.id is not None` só vale depois do flush, então o
        construtor (id ainda None) passa e a carga do banco nem chega aqui — o loader
        do SQLAlchemy não passa pelo setattr instrumentado. Verificado por experimento.
        """
        if self.id is not None:
            raise ValueError(
                "corpo_md é imutável: um contrato pode apontar para esta versão e "
                "regerá-lo tem que reproduzir as cláusulas originais. "
                "Para mudar o modelo, crie a próxima versão (mod_documentos.criar_versao)."
            )
        return value


class Emitente(Base):
    """Identidade fiscal de 1 CNPJ. Emite documentos; NÃO é a loja vendedora."""
    __tablename__ = "emitente"
    id = Column(Integer, primary_key=True, autoincrement=True)
    cnpj = Column(String(18), nullable=True)
    razao_social = Column(Text, nullable=True)
    nome_fantasia = Column(Text, nullable=True)
    inscricao_estadual = Column(Text, nullable=True)
    inscricao_municipal = Column(Text, nullable=True)
    regime_tributario = Column(Text, nullable=True)
    csosn_padrao = Column(Text, nullable=True)
    csosn_contribuinte = Column(Text, nullable=True)
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


class PerfilEmissao(Base):
    """Política: qual Emitente assina cada tipo de documento, por owner (loja|rede).
    Unicidade (owner_tipo, owner_id, tipo_doc) — um único emitente por política (auditoria A12).
    Para DBs existentes, o índice único é criado em `_migrar_colunas`."""
    __tablename__ = "perfil_emissao"
    __table_args__ = (UniqueConstraint("owner_tipo", "owner_id", "tipo_doc", name="uq_perfil_emissao"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_tipo = Column(Text, nullable=False)   # "loja" | "rede"
    owner_id = Column(Integer, nullable=False)
    tipo_doc = Column(Text, nullable=False)      # "produto" | "servico"
    emitente_id = Column(Integer, ForeignKey("emitente.id"), nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)


class DocumentoFiscal(Base):
    """Rastreio de um documento fiscal emitido (NF-e produto / NFS-e serviço via Focus).
    `ref` = idempotência. XML/DANFE ficam em CicloDocumento (etapa 15) referenciados por
    xml_doc_id/danfe_doc_id. `loja_id` = escopo da venda; `emitente_id` = emitente resolvido."""
    __tablename__ = "documento_fiscal"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    ref            = Column(Text, nullable=False, unique=True)
    projeto_nome   = Column(Text, nullable=True)
    tipo_documento = Column(Text, default="produto")   # "produto" | "servico"
    etapa_codigo   = Column(Text, default="15")
    loja_id        = Column(Integer, ForeignKey("lojas.id"), nullable=True)
    emitente_id    = Column(Integer, ForeignKey("emitente.id"), nullable=True)
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
    # As migrações abaixo (_migrar_pre_schema/_migrar_colunas/_migrar_dados) usam sqlite3.connect(DB_PATH)
    # + PRAGMA diretamente — só fazem sentido pra upgradar um orizon.db SQLite já existente. Num banco
    # Postgres novo o schema já nasce correto via create_all(); rodar essas funções contra Postgres
    # criaria um orizon.db SQLite vazio e órfão do lado (sqlite3.connect cria o arquivo se não existir).
    if ENGINE.dialect.name == "sqlite":
        _migrar_pre_schema()   # renames de TABELA antes do create_all (senão ele cria a nova vazia)
    Base.metadata.create_all(ENGINE)
    if ENGINE.dialect.name == "sqlite":
        _migrar_colunas()
        _migrar_dados()
    else:
        _migrar_colunas_pg()  # Postgres: ADD COLUMN das colunas novas (create_all não altera existentes)
        _seed_loja_padrao()   # equivalente portável da tenancy_v1_2026 (loja seed + backfill)
    _backfill_funcao_flags()  # liga usa_comissao_vendas na função Consultor de Vendas (idempotente)
    try:
        from auth import perfis
        perfis.recarregar()   # invalida o cache do registro de perfis (perfil_acesso pode ter mudado)
    except Exception:
        pass


def _backfill_funcao_flags():
    """Garante que a função 'Consultor de Vendas' tenha usa_comissao_vendas=1 (motor da Folha e
    identificação do consultor). Idempotente; funções antigas nascidas antes do flag são corrigidas."""
    db = Session()
    try:
        for fn in db.query(Funcao).filter(Funcao.nome.ilike("consultor de vendas")).all():
            if not fn.usa_comissao_vendas:
                fn.usa_comissao_vendas = 1
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _migrar_pre_schema():
    """Renomeações de tabela que DEVEM ocorrer ANTES do create_all — senão o create_all cria a tabela
    nova vazia e a renomeação (que moveria os dados) nunca acontece. Idempotente."""
    import sqlite3
    if not os.path.exists(DB_PATH):
        return   # banco novo: create_all já nasce com o schema atual
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        def _existe(t):
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (t,))
            return cur.fetchone() is not None
        # 2026-07-06: nfe_emissao -> documento_fiscal (preserva as emissões existentes)
        if _existe("nfe_emissao") and not _existe("documento_fiscal"):
            cur.execute("ALTER TABLE nfe_emissao RENAME TO documento_fiscal")
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()

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
            ("tipo_dest",              "VARCHAR DEFAULT 'nao_contribuinte'"),
            ("cnpj",                   "VARCHAR(18)"),
            ("inscricao_estadual",     "TEXT"),
            ("municipio_ibge",         "VARCHAR(7)"),
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
        if "tema" not in usr_cols:
            cur.execute("ALTER TABLE usuarios ADD COLUMN tema VARCHAR(10) DEFAULT 'escuro'")
        if "funcionario_id" not in usr_cols:
            cur.execute("ALTER TABLE usuarios ADD COLUMN funcionario_id INTEGER")   # boundary Funcionário↔Usuário (v9)
        if "senha_provisoria" not in usr_cols:
            cur.execute("ALTER TABLE usuarios ADD COLUMN senha_provisoria INTEGER DEFAULT 0")

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

        # ── ciclo_logistico (desmembramento parcial, spec 2026-07-13) ──────────
        # Guarda contra a tabela ainda não existir (PRAGMA vazio): senão o ALTER lança
        # "no such table" e, engolido pelo except: pass do fim, abortaria as migrações seguintes.
        cur.execute("PRAGMA table_info(ciclo_logistico)")
        _cl_cols = {row[1] for row in cur.fetchall()}
        if _cl_cols and "parcela_id" not in _cl_cols:
            cur.execute("ALTER TABLE ciclo_logistico ADD COLUMN parcela_id INTEGER")

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
            ("modelo_versao_id", "INTEGER"),
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
            ("num_proposta",    "TEXT"),
            ("ramo_financeiro",     "TEXT"),            # Fatia B: ramo do custo financeiro (box da AF)
            ("ramo_financeiro_seq", "INTEGER DEFAULT 0"),
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

        # ── provisao_registro: trava da versão aprovada (Fatia C) ──
        if _tabela_existe(cur, "provisao_registro"):
            pr_cols = {c[1] for c in cur.execute("PRAGMA table_info(provisao_registro)").fetchall()}
            if pr_cols and "travada_em" not in pr_cols:
                cur.execute("ALTER TABLE provisao_registro ADD COLUMN travada_em DATETIME")

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

        # ── emitente: CSOSN próprio p/ destinatário contribuinte (default no código = 101) ──
        if _tabela_existe(cur, "emitente"):
            emit_cols = {c[1] for c in cur.execute("PRAGMA table_info(emitente)").fetchall()}
            if "csosn_contribuinte" not in emit_cols:
                cur.execute("ALTER TABLE emitente ADD COLUMN csosn_contribuinte TEXT")

        # ── fiscal multi-CNPJ: vínculo loja/rede -> emitente (tabela emitente via create_all) ──
        if _tabela_existe(cur, "lojas"):
            loja_cols = {c[1] for c in cur.execute("PRAGMA table_info(lojas)").fetchall()}
            if "emitente_id" not in loja_cols:
                cur.execute("ALTER TABLE lojas ADD COLUMN emitente_id INTEGER")
            if "modulos_ativos" not in loja_cols:
                cur.execute("ALTER TABLE lojas ADD COLUMN modulos_ativos TEXT")
            if "responsavel" not in loja_cols:
                cur.execute("ALTER TABLE lojas ADD COLUMN responsavel VARCHAR(120)")
            # Segmentação Mercadoria × Serviço: colunas + seed 65/35 nas lojas existentes (backfill).
            if "pct_mercadoria" not in loja_cols:
                cur.execute("ALTER TABLE lojas ADD COLUMN pct_mercadoria REAL")
                cur.execute("UPDATE lojas SET pct_mercadoria = 65.0 WHERE pct_mercadoria IS NULL")
            if "pct_servico" not in loja_cols:
                cur.execute("ALTER TABLE lojas ADD COLUMN pct_servico REAL")
                cur.execute("UPDATE lojas SET pct_servico = 35.0 WHERE pct_servico IS NULL")
        if _tabela_existe(cur, "redes"):
            rede_cols = {c[1] for c in cur.execute("PRAGMA table_info(redes)").fetchall()}
            if "emitente_central_id" not in rede_cols:
                cur.execute("ALTER TABLE redes ADD COLUMN emitente_central_id INTEGER")

        # ── perfil_emissao: unicidade (owner_tipo, owner_id, tipo_doc) — auditoria A12 ──
        # Dedup defensivo (mantém a linha mais recente por chave) + índice único p/ DBs existentes.
        if _tabela_existe(cur, "perfil_emissao"):
            cur.execute("DELETE FROM perfil_emissao WHERE id NOT IN "
                        "(SELECT MAX(id) FROM perfil_emissao GROUP BY owner_tipo, owner_id, tipo_doc)")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_perfil_emissao "
                        "ON perfil_emissao(owner_tipo, owner_id, tipo_doc)")

        # ── lancamento: ref (idempotência wiring) + motivo (§6.2) + ia_sugestao (§6.3) ──
        if _tabela_existe(cur, "lancamento"):
            cur.execute("PRAGMA table_info(lancamento)")
            lanc_cols = {row[1] for row in cur.fetchall()}
            for col, tipo in [("ref", "VARCHAR(80)"), ("motivo", "VARCHAR(30)"), ("ia_sugestao", "TEXT")]:
                if col not in lanc_cols:
                    cur.execute(f"ALTER TABLE lancamento ADD COLUMN {col} {tipo}")

        # ── Cadastro v10: Endereço + Dados Bancários + funcao_id + PIX ──────────
        _ENDERECO = [("cep","VARCHAR(9)"), ("logradouro","VARCHAR(200)"), ("numero","VARCHAR(20)"),
                     ("complemento","VARCHAR(100)"), ("bairro","VARCHAR(100)"), ("cidade","VARCHAR(80)"),
                     ("uf","VARCHAR(2)")]
        _BANCO = [("banco_nome","VARCHAR(80)"), ("banco_codigo","VARCHAR(6)"), ("agencia","VARCHAR(12)"),
                  ("conta","VARCHAR(20)"), ("pix","VARCHAR(140)")]
        def _add_cols(tabela, cols):
            existentes = {r[1] for r in cur.execute(f"PRAGMA table_info({tabela})")}
            if not existentes:   # tabela ainda não existe (será criada pelo create_all)
                return
            for col, tipo in cols:
                if col not in existentes:
                    cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {col} {tipo}")
        _add_cols("funcionarios", [("funcao_id","INTEGER")] + _ENDERECO + _BANCO)
        _add_cols("fornecedores", _ENDERECO + _BANCO)
        _add_cols("terceiros",    [("funcao_id","INTEGER")] + _ENDERECO + _BANCO)
        _add_cols("parceiros",    [("pix","VARCHAR(140)")])
        # Mapa de Atribuições (Regras_Funcoes_Perfis §5): conta opcional do Terceiro
        _add_cols("terceiros",    [("usuario_id","INTEGER")])
        # Perfil-4 (rev2 §2): Função (cargo) da conta quando não há Funcionário vinculado
        _add_cols("usuarios",     [("funcao_id","INTEGER")])
        # Perfis configuráveis por loja (rev3 §2): slug do perfil_acesso default da função
        _add_cols("funcoes",      [("perfil_padrao", "VARCHAR(40)"),
                                   ("atribuicoes_json", "TEXT"),
                                   ("remuneracao_padrao", "VARCHAR(20)"),
                                   ("regime_trabalho", "VARCHAR(20)"),
                                   ("regime_contratacao", "VARCHAR(20)"),
                                   ("descricao", "TEXT"),
                                   ("salario_fixo", "REAL"),
                                   ("beneficios_json", "TEXT"),
                                   ("comissao_json", "TEXT"),
                                   ("usa_comissao_vendas", "INTEGER")])
        # Folha Fase 3: base da comissão editável + soma de benefícios no registro da folha
        _add_cols("folha_pagamento", [("base_comissao", "REAL"), ("beneficios", "REAL")])
        # Cronograma do Ciclo (Modulos_Orizon_v11): data prevista de conclusão por etapa
        # + Responsável por função (Modulos_Orizon_v12): função exigida + funcionário escolhido
        _add_cols("ciclo_etapas", [("data_prevista_conclusao","DATETIME"),
                                   ("funcao_responsavel_id","INTEGER"),
                                   ("responsavel_funcionario_id","INTEGER")])
        _add_cols("parcela_projeto", [("prazo_conclusao","DATETIME")])   # Fase A: prazo da fase
        _add_cols("projetos_meta", [("data_entrega","DATETIME"), ("data_inicio","DATETIME")])   # âncoras do cronograma
        _add_cols("projetos_meta", [("equipe_json","TEXT")])   # Equipe do Projeto (seleções dos papéis seletores)

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

# Catálogo padrão da Tabela de Funções (Regras_Funcoes_Perfis_Atribuicoes §0b / §7). Cargos, não
# perfis de acesso: os rótulos de cargo de perfis.py + "Montador" (Terceiro, sem perfil próprio).
FUNCOES_PADRAO = [
    "Consultor de Vendas", "Gerente de Vendas", "Gerente Administrativo/Financeiro", "Diretor",
    "Assistente Logístico", "Conferente", "Supervisor de Montagem", "Assistente Administrativo",
    "Projetista Executivo", "Medidor", "Montador", "SAC",
]

def _tabela_existe(cur, nome):
    """True se a tabela existe (migração de tabela ausente é no-op — robusto a DBs parciais)."""
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nome,))
    return cur.fetchone() is not None


def _cols_de(cur, nome):
    """Set das colunas de `nome`, ou vazio se a tabela não existe (guarda idempotente)."""
    cur.execute("PRAGMA table_info(%s)" % nome)
    return {r[1] for r in cur.fetchall()}


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

    # 2026-07-10: semeia a Tabela de Funções (Regras_Funcoes_Perfis §0b) nas lojas existentes,
    # idempotente por (loja_id, nome). Backfill único; lojas novas semeiam na criação (follow-up).
    if "funcoes_seed_v1" not in aplicadas and _tabela_existe(cur, "funcoes") and _tabela_existe(cur, "lojas"):
        for (lid,) in cur.execute("SELECT id FROM lojas").fetchall():
            existentes = {r[0] for r in cur.execute("SELECT nome FROM funcoes WHERE loja_id=?", (lid,)).fetchall()}
            for nome in FUNCOES_PADRAO:
                if nome not in existentes:
                    cur.execute("INSERT INTO funcoes(loja_id, nome, status) VALUES(?,?,'ativo')", (lid, nome))
        cur.execute("INSERT INTO schema_migrations(id) VALUES('funcoes_seed_v1')")

    # 2026-07-17: backfill da flag usa_comissao_vendas no Consultor de Vendas (F1.2) — a comissão
    # dele vem do comissao_vendas da loja, não do comissao_json genérico das demais funções.
    if "comissao_vendas_flag_v1" not in aplicadas and _tabela_existe(cur, "funcoes") \
            and "usa_comissao_vendas" in _cols_de(cur, "funcoes"):
        cur.execute("UPDATE funcoes SET usa_comissao_vendas=1 WHERE nome='Consultor de Vendas'")
        cur.execute("INSERT INTO schema_migrations(id) VALUES('comissao_vendas_flag_v1')")

    # 2026-07-10: Perfil-4 (rev2 §2) — colapsa os ~13 níveis-cargo em 4 perfis de acesso; o cargo
    # antigo vira Função (usuarios.funcao_id, só p/ contas sem Funcionário vinculado). Idempotente.
    if "perfis_v3_2026" not in aplicadas and _tabela_existe(cur, "usuarios"):
        _CARGO = {"diretor": "Diretor", "gerente_vendas": "Gerente de Vendas",
                  "gerente_adm_fin": "Gerente Administrativo/Financeiro", "consultor": "Consultor",
                  "medidor": "Medidor", "projetista_executivo": "Projetista Executivo",
                  "conferente": "Conferente", "supervisor_montagem": "Supervisor de Montagem",
                  "assistente_logistico": "Assistente Logístico",
                  "assistente_administrativo": "Assistente Administrativo"}
        _PERFIL = {"diretor": "diretoria", "gerente_vendas": "gerencial",
                   "gerente_adm_fin": "diretoria", "consultor": "consultor", "medidor": "consultor",
                   "projetista_executivo": "consultor", "conferente": "consultor",
                   "supervisor_montagem": "consultor", "assistente_logistico": "consultor",
                   "assistente_administrativo": "consultor"}
        if {"funcao_id", "loja_id", "funcionario_id"} <= _cols_de(cur, "usuarios") \
                and _tabela_existe(cur, "funcoes"):
            for uid, niv, loja_id, fnid in cur.execute(
                    "SELECT id, nivel, loja_id, funcionario_id FROM usuarios").fetchall():
                if fnid:                       # tem Funcionário → função vem de lá
                    continue
                nome = _CARGO.get(niv)
                if nome and loja_id:
                    row = cur.execute("SELECT id FROM funcoes WHERE loja_id=? AND nome=?",
                                      (loja_id, nome)).fetchone()
                    if row:
                        cur.execute("UPDATE usuarios SET funcao_id=? WHERE id=?", (row[0], uid))
        for antigo, novo in _PERFIL.items():
            if antigo != novo:
                cur.execute("UPDATE usuarios SET nivel=? WHERE nivel=?", (novo, antigo))
        cur.execute("INSERT INTO schema_migrations(id) VALUES('perfis_v3_2026')")

    # 2026-07-10: RESET rev3 — perfis viram configuráveis por loja; nivel passa a referenciar a BASE.
    if "perfis_v4_2026" not in aplicadas and _tabela_existe(cur, "usuarios"):
        _MAP = {"diretoria": "master", "consultor": "operador", "suporte": "operador"}
        for antigo, novo in _MAP.items():
            cur.execute("UPDATE usuarios SET nivel=? WHERE nivel=?", (novo, antigo))
        cur.execute("INSERT INTO schema_migrations(id) VALUES('perfis_v4_2026')")

    # 2026-07-10: semeia os 3 perfis padrão nas lojas existentes (rev3 §2). Idempotente por (loja_id, slug).
    if "perfil_acesso_seed_v1" not in aplicadas and _tabela_existe(cur, "perfil_acesso") and _tabela_existe(cur, "lojas"):
        import json as _json
        _OP = ["captacao", "cadastro", "comercial", "estoque", "expedicao", "montagem", "assistencias"]
        _SPEC = [("master", "Master", "master", _OP + ["fiscal", "financeiro", "folha", "admin", "config"]),
                 ("gerencial", "Gerencial", "gerencial", _OP + ["fiscal", "financeiro", "folha"]),
                 ("operador", "Operador", "operador", _OP + ["fiscal"])]
        for (lid,) in cur.execute("SELECT id FROM lojas").fetchall():
            tem = {r[0] for r in cur.execute("SELECT slug FROM perfil_acesso WHERE loja_id=?", (lid,)).fetchall()}
            for slug, nome, base, mods in _SPEC:
                if slug not in tem:
                    cur.execute("INSERT INTO perfil_acesso(loja_id, slug, nome, base, modulos_json, capacidades_json, sistema) "
                                "VALUES(?,?,?,?,?,'{}',1)", (lid, slug, nome, base, _json.dumps(mods)))
        cur.execute("INSERT INTO schema_migrations(id) VALUES('perfil_acesso_seed_v1')")

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

    # 2026-07-06: nfe_emissao -> documento_fiscal (rename + tipo_documento + emitente_id + backfill).
    # Idempotente via PRAGMA table_info (não usa schema_migrations: guardas de existência bastam).
    _tem_nfe = bool(_cols_de(cur, "nfe_emissao"))
    _cols_df = _cols_de(cur, "documento_fiscal")
    if _tem_nfe and not _cols_df:
        cur.execute("ALTER TABLE nfe_emissao RENAME TO documento_fiscal")
        _cols_df = _cols_de(cur, "documento_fiscal")
    if _cols_df:
        if "tipo_documento" not in _cols_df:
            cur.execute("ALTER TABLE documento_fiscal ADD COLUMN tipo_documento TEXT DEFAULT 'produto'")
        if "emitente_id" not in _cols_df:
            cur.execute("ALTER TABLE documento_fiscal ADD COLUMN emitente_id INTEGER")
        if "fabrica_doc_id" not in _cols_df:   # DB legado sem a coluna (senão o INSERT de emissão falharia)
            cur.execute("ALTER TABLE documento_fiscal ADD COLUMN fabrica_doc_id INTEGER")
        if _tabela_existe(cur, "lojas"):
            cur.execute(
                "UPDATE documento_fiscal SET emitente_id="
                "(SELECT emitente_id FROM lojas WHERE lojas.id=documento_fiscal.loja_id) "
                "WHERE emitente_id IS NULL")

    # 2026-07-12 (FASE D2): 2.1.06 "Adiantamento de Clientes" -> "Receita a Realizar" (passa a receber o
    # Val_Cont cheio no contrato). Migração PONTUAL: só renomeia onde o nome ainda é o default antigo —
    # preserva contas que o owner renomeou pelo painel (editar_conta permite renomear qualquer conta).
    if "conta_2106_receita_a_realizar_2026" not in aplicadas and _tabela_existe(cur, "conta"):
        cur.execute("UPDATE conta SET nome='Receita a Realizar' "
                    "WHERE codigo='2.1.06' AND nome='Adiantamento de Clientes'")
        cur.execute("INSERT INTO schema_migrations(id) VALUES('conta_2106_receita_a_realizar_2026')")

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


def _migrar_colunas_pg():
    """Postgres: ADD COLUMN IF NOT EXISTS das colunas novas do modelo. `create_all()` não altera
    tabelas já existentes, e o caminho de `_migrar_colunas()` é só-SQLite (PRAGMA). Idempotente.
    Espelha as colunas adicionadas via `_migrar_colunas` que precisam existir no Postgres já povoado."""
    if ENGINE.dialect.name == "sqlite":
        return
    stmts = [
        "ALTER TABLE lojas ADD COLUMN IF NOT EXISTS responsavel VARCHAR(120)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS senha_provisoria INTEGER DEFAULT 0",
        "ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS atribuicoes_json TEXT",
        "ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS remuneracao_padrao VARCHAR(20)",
        "ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS regime_trabalho VARCHAR(20)",
        "ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS regime_contratacao VARCHAR(20)",
        "ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS descricao TEXT",
        "ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS salario_fixo DOUBLE PRECISION",
        "ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS beneficios_json TEXT",
        "ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS comissao_json TEXT",
        "ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS usa_comissao_vendas INTEGER DEFAULT 0",
        "ALTER TABLE folha_pagamento ADD COLUMN IF NOT EXISTS base_comissao DOUBLE PRECISION",
        "ALTER TABLE folha_pagamento ADD COLUMN IF NOT EXISTS beneficios DOUBLE PRECISION",
    ]
    with ENGINE.begin() as conn:
        for s in stmts:
            conn.exec_driver_sql(s)


def _seed_loja_padrao():
    """Loja seed (dados reais da INSPIRIUM/Dalmóbile) + backfill de loja_id — equivalente em SQLAlchemy
    puro (funciona em qualquer dialeto) da migração 'tenancy_v1_2026' que só roda em SQLite via
    _migrar_dados/_run_migracoes (raw sqlite3 + placeholders '?', não portável). Idempotente: só cria
    a loja se ainda não existir nenhuma. Chamada pelo init_db() para bancos que não são SQLite."""
    db = Session()
    try:
        loja = db.query(Loja).order_by(Loja.id).first()
        if loja is None:
            loja = Loja(nome=_SEED_LOJA_NOME, cnpj=_SEED_LOJA_CNPJ, codigo=_SEED_LOJA_CODIGO,
                        telefone=_SEED_LOJA_TEL, email=_SEED_LOJA_EMAIL,
                        testemunha1_nome=_SEED_TEST1_NOME, testemunha1_cpf=_SEED_TEST1_CPF,
                        testemunha2_nome=_SEED_TEST2_NOME, testemunha2_cpf=_SEED_TEST2_CPF,
                        ativo=1)
            db.add(loja)
            db.commit()
        loja_id = loja.id

        # Usuario à parte: super_admin/admin_rede são papéis de plataforma/rede, SEM loja própria
        # por desenho (loja_id NULL de propósito) — não entram no backfill.
        (db.query(Usuario)
           .filter(Usuario.loja_id.is_(None))
           .filter(Usuario.nivel.notin_(("super_admin", "admin_rede")))
           .update({"loja_id": loja_id}, synchronize_session=False))
        for modelo in (Cliente, Projeto, Orcamento, Contrato):
            db.query(modelo).filter(modelo.loja_id.is_(None)).update({"loja_id": loja_id})
        db.commit()

        for p in db.query(Parceiro).all():
            if p.abrangencia is None:
                p.abrangencia = "loja"
            vinculo = db.query(ParceiroLoja).filter_by(parceiro_id=p.id, loja_id=loja_id).first()
            if vinculo is None:
                db.add(ParceiroLoja(parceiro_id=p.id, loja_id=loja_id,
                                    comissao_padrao_pct=p.comissao_padrao_pct or 0.0, ativo=1))
        db.commit()
    finally:
        db.close()


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
