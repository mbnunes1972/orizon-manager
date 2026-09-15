"""Lead — captação provisória

docs/db/PLANO_SEMANA_1.md (14/09/2026): o lead nasce antes do cliente e do projeto, entidade
própria — NÃO é o módulo de Captação definitivo (esse nasce depois da 1.0, ver
LISTA_PARALELA.md § FRONTEIRA). Três mudanças de schema, uma tarefa só:

  1. Tabela `leads` nova. Núcleo fixo (nome/telefone/whatsapp/email/canal/loja/responsável/
     situação/data de entrada) + `template`/`dados_json` para o que varia por formulário de
     captação, sem migration a cada campo novo (mesmo espírito de `funcoes.beneficios_json`/
     `lojas.config_financeira_json`). `cliente_id` fica NULL até a conversão — histórico de
     pra onde o lead foi, nunca preenchido na criação.
  2. `clientes.origem` — COMO o cliente chegou ("porta", "arquiteto", "indicação", ou
     "lead/<canal>" quando vem de um lead convertido). Deliberadamente um campo DIFERENTE de
     `leads.canal` (DE ONDE o lead veio) — um campo só pras duas perguntas seria mais uma
     instância da Causa B do MAPA_MODULOS.md ("um campo, dois significados"), a mesma família
     do LP-23.
  3. `conversas.lead_id` — terceira âncora opcional do Chat (ao lado de `projeto_nome`/
     `cliente_id`), pra a conversa do lead sobreviver à conversão com o histórico intacto.

Índices em toda FK nova (`leads.loja_id`, `leads.responsavel_usuario_id`, `leads.cliente_id`,
`conversas.lead_id`) — revisão de banco de agosto/2026: coluna filha ganha índice.

Revision ID: 11cee0a345a3
Revises: 5325ac7badfa
Create Date: 2026-09-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '11cee0a345a3'
down_revision: Union[str, Sequence[str], None] = '5325ac7badfa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'leads',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('nome', sa.String(length=150), nullable=False),
        sa.Column('telefone', sa.String(length=20), nullable=True),
        sa.Column('whatsapp', sa.String(length=20), nullable=True),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('canal', sa.String(length=40), nullable=True),
        sa.Column('loja_id', sa.Integer(), nullable=False),
        sa.Column('responsavel_usuario_id', sa.Integer(), nullable=True),
        sa.Column('situacao', sa.String(length=15), nullable=False, server_default='novo'),
        sa.Column('template', sa.String(length=40), nullable=True),
        sa.Column('dados_json', sa.Text(), nullable=True),
        sa.Column('cliente_id', sa.Integer(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['loja_id'], ['lojas.id']),
        sa.ForeignKeyConstraint(['responsavel_usuario_id'], ['usuarios.id']),
        sa.ForeignKeyConstraint(['cliente_id'], ['clientes.id']),
    )
    op.create_index('ix_leads_loja_id', 'leads', ['loja_id'])
    op.create_index('ix_leads_responsavel_usuario_id', 'leads', ['responsavel_usuario_id'])
    op.create_index('ix_leads_cliente_id', 'leads', ['cliente_id'])

    op.add_column('clientes', sa.Column('origem', sa.String(length=40), nullable=True))

    op.add_column('conversas', sa.Column('lead_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_conversas_lead_id', 'conversas', 'leads', ['lead_id'], ['id'])
    op.create_index('ix_conversas_lead_id', 'conversas', ['lead_id'])


def downgrade() -> None:
    op.drop_index('ix_conversas_lead_id', table_name='conversas')
    op.drop_constraint('fk_conversas_lead_id', 'conversas', type_='foreignkey')
    op.drop_column('conversas', 'lead_id')

    op.drop_column('clientes', 'origem')

    op.drop_index('ix_leads_cliente_id', table_name='leads')
    op.drop_index('ix_leads_responsavel_usuario_id', table_name='leads')
    op.drop_index('ix_leads_loja_id', table_name='leads')
    op.drop_table('leads')
