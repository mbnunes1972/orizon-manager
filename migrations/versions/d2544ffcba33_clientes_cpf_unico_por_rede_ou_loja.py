"""clientes: CPF único por rede (ou por loja se avulsa) — schema (decisão 2026-09-16)

Terceira e última revisão do pacote (schema `e6bffa95b7b9` → dado `499cc8325e92` → esta, R6).
Derruba `UNIQUE(cpf)` global (`clientes_cpf_key`, criada sem `name=` explícito na baseline —
`migrations/versions/0001_baseline_orizon_one.py`, nome padrão do Postgres pra
`UniqueConstraint('cpf')` sem nome) e instala dois índices únicos PARCIAIS, mesmo padrão já usado
em `AtribuicaoAmbiente.uq_atribuicao_papel_ambiente`:

  - `uq_clientes_cpf_rede`        UNIQUE (rede_id, cpf) WHERE rede_id IS NOT NULL
  - `uq_clientes_cpf_loja_avulsa` UNIQUE (loja_id, cpf) WHERE rede_id IS NULL

Sem risco de violação ao trocar: a constraint que está caindo é MAIS restritiva (global) que as
duas que entram (escopadas) — nenhuma linha existente pode ferir a nova regra por ser mais larga
que a antiga. O backfill da revisão anterior já garante `rede_id` preenchido pra todo cliente de
loja de rede antes desta migration rodar.

Modelo (`database.py`, `Cliente.__table_args__`) atualizado no MESMO commit desta migration —
R10/R11: índice fora do modelo é dívida que o autogenerate propõe desfazer.

Revision ID: d2544ffcba33
Revises: 499cc8325e92
Create Date: 2026-09-16 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2544ffcba33'
down_revision: Union[str, Sequence[str], None] = '499cc8325e92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('clientes_cpf_key', 'clientes', type_='unique')
    op.create_index('uq_clientes_cpf_rede', 'clientes', ['rede_id', 'cpf'],
                     unique=True, postgresql_where=sa.text('rede_id IS NOT NULL'))
    op.create_index('uq_clientes_cpf_loja_avulsa', 'clientes', ['loja_id', 'cpf'],
                     unique=True, postgresql_where=sa.text('rede_id IS NULL'))


def downgrade() -> None:
    op.drop_index('uq_clientes_cpf_loja_avulsa', table_name='clientes')
    op.drop_index('uq_clientes_cpf_rede', table_name='clientes')
    op.create_unique_constraint('clientes_cpf_key', 'clientes', ['cpf'])
