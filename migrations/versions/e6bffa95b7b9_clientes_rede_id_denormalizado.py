"""clientes.rede_id denormalizado — schema (unicidade por rede, decisão 2026-09-16)

Decisão do Marcelo (16/09/2026), achado durante a investigação do vazamento de tenancy em
Homologação (pdm2026 alcançando a Loja Teste via Fórum Orizon/Parceiro de rede — ver
`docs/db/TAREFA_LOJA_TESTE.md`, "O que 'pertencer a uma rede' implica"): a unicidade de CPF do
`Cliente` passa a ser POR REDE (loja de rede que acha o CPF em outra loja da mesma rede
compartilha o cadastro) — não mais global, não por loja. Loja avulsa (`rede_id IS NULL`)
continua duplicando por loja, como sempre.

`clientes` não tem `rede_id` próprio hoje — só alcançável via `loja_id → Loja.rede_id` (join).
Um índice único do Postgres não enxerga join, então é preciso DENORMALIZAR `rede_id` na própria
linha antes de trocar a constraint. Esta migration só adiciona a coluna (schema puro, R6) — o
backfill dos dados existentes é a próxima revisão (`499cc8325e92`), e a troca da constraint de
`UNIQUE(cpf)` global pra composta por rede/loja é a revisão depois dessa (`d2544ffcba33`) — as
três em revisões separadas de propósito (R6: schema e dado nunca compartilham revisão).

Revision ID: e6bffa95b7b9
Revises: 11cee0a345a3
Create Date: 2026-09-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6bffa95b7b9'
down_revision: Union[str, Sequence[str], None] = '11cee0a345a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('clientes', sa.Column('rede_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_clientes_rede_id', 'clientes', 'redes', ['rede_id'], ['id'])
    op.create_index('ix_clientes_rede_id', 'clientes', ['rede_id'])


def downgrade() -> None:
    op.drop_index('ix_clientes_rede_id', table_name='clientes')
    op.drop_constraint('fk_clientes_rede_id', 'clientes', type_='foreignkey')
    op.drop_column('clientes', 'rede_id')
