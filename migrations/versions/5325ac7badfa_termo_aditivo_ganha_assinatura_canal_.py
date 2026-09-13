"""termo aditivo ganha assinatura_canal e campos clicksign — ACHADO-69

docs/db/ACHADOS_CONTABEIS.md, ACHADO-69: unificação da assinatura ClickSign — o Termo Aditivo
entra como quarto caso do mecanismo comum (mod_assinatura.py), depois de Contrato, Aprovação do
PE e Solicitação de Medição. Quatro colunas novas em `aditivos`, mesmos nomes dos três irmãos:
  - assinatura_canal (server_default='interno' — aditivo existente continua no canal de sempre,
    sem migração de dado; ver a nota C1 em Contrato.assinatura_canal no database.py sobre o
    caminho ERRADO que os dois primeiros tomaram, `_migrar_colunas_pg` sem DEFAULT — não repetido
    aqui, R1: `_migrar_colunas_pg` está congelado, DDL só entra por migration)
  - clicksign_envelope_id / clicksign_enviado_em / clicksign_signatarios_json

Revision ID: 5325ac7badfa
Revises: 9a1b2c3d4e5f
Create Date: 2026-09-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5325ac7badfa'
down_revision: Union[str, Sequence[str], None] = '9a1b2c3d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('aditivos', sa.Column('assinatura_canal', sa.String(length=16),
                                        nullable=True, server_default='interno'))
    op.add_column('aditivos', sa.Column('clicksign_envelope_id', sa.Text(), nullable=True))
    op.add_column('aditivos', sa.Column('clicksign_enviado_em', sa.DateTime(), nullable=True))
    op.add_column('aditivos', sa.Column('clicksign_signatarios_json', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('aditivos', 'clicksign_signatarios_json')
    op.drop_column('aditivos', 'clicksign_enviado_em')
    op.drop_column('aditivos', 'clicksign_envelope_id')
    op.drop_column('aditivos', 'assinatura_canal')
