"""usuarios senha_provisoria default 1 - li-3

docs/db/LISTA_IMEDIATA.md, LI-3 (LP-35): esquecer o parâmetro `senha_provisoria` na criação de
um Usuario produzia conta insegura por omissão (default 0 = "senha definitiva", já aconteceu na
tela de Admin) — inverter o default para 1 troca a omissão segura: esquecer passa a produzir
conta que força troca de senha no 1º login. SÓ o default muda; nenhuma linha existente é tocada
(migração de SCHEMA, não de dado — R6) — quem já tem `senha_provisoria=0` continua 0.

Revision ID: c64d026c88e5
Revises: a518e96c1cee
Create Date: 2026-09-25 04:58:09.373031

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c64d026c88e5'
down_revision: Union[str, Sequence[str], None] = 'a518e96c1cee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('usuarios', 'senha_provisoria', server_default='1')


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('usuarios', 'senha_provisoria', server_default='0')
