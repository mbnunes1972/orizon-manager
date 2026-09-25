"""triagem_entradas dialogo_json - tarefa a

docs/db/TAREFA_TRIAGEM_CLIENTE_CONHECIDO.md — o estado do diálogo de reconhecimento de Cliente
(P1/P2/P3, TAREFA-A) RAMIFICA (P1 → P2 ou P3 ou menu de segmentos); `ja_reformulou`
(TAREFA_TRIAGEM_E_CONTADOR.md, Item 1) deriva por CONTAGEM de EnvioExterno.triagem_id, o que só
funciona quando a sequência é única — aqui contar não diz QUAL pergunta foi feita. Uma coluna
só, sem backfill: `NULL` já significa "entrada anterior a esta tarefa, ou fluxo de desconhecido
— comportamento de hoje, intacto".

Revision ID: a518e96c1cee
Revises: d2544ffcba33
Create Date: 2026-09-24 23:54:43.312746

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a518e96c1cee'
down_revision: Union[str, Sequence[str], None] = 'd2544ffcba33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('triagem_entradas', sa.Column('dialogo_json', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('triagem_entradas', 'dialogo_json')
