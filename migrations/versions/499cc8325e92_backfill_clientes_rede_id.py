"""backfill clientes.rede_id a partir de lojas.rede_id — dado (decisão 2026-09-16)

Revisão de DADO, separada da revisão de schema anterior (`e6bffa95b7b9`) e da próxima que troca
a constraint (`d2544ffcba33`) — R6. Preenche `clientes.rede_id` para todo cliente já existente,
lendo a rede da PRÓPRIA loja dele no momento em que esta migration roda (join simples,
`clientes.loja_id → lojas.id → lojas.rede_id`). Cliente sem `loja_id` (não deveria existir hoje,
mas a coluna é nullable) fica com `rede_id` NULL, mesmo tratamento de loja avulsa.

Sem risco de colisão: a constraint antiga (`UNIQUE(cpf)` global, ainda viva nesta revisão — só
cai na próxima) já garante que não existem dois clientes com o mesmo CPF hoje, então o backfill
não pode criar duplicata nenhuma sob a constraint nova (mais permissiva) que a próxima revisão
instala.

Revision ID: 499cc8325e92
Revises: e6bffa95b7b9
Create Date: 2026-09-16 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '499cc8325e92'
down_revision: Union[str, Sequence[str], None] = 'e6bffa95b7b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    res = conn.execute(sa.text("""
        UPDATE clientes AS c
        SET rede_id = l.rede_id
        FROM lojas AS l
        WHERE c.loja_id = l.id AND l.rede_id IS NOT NULL AND c.rede_id IS NULL
    """))
    print("backfill clientes.rede_id: %d linha(s) atualizada(s)." % res.rowcount)


def downgrade() -> None:
    # Reversível de propósito: zera de volta o que esta revisão preencheu. Não distingue um
    # rede_id preenchido por esta migration de um preenchido depois por código vivo (a coluna
    # não guarda origem) — aceitável porque o downgrade só é usado para desfazer esta cadeia
    # em ambiente de teste/rollback, nunca em produção com dado real por cima.
    op.execute("UPDATE clientes SET rede_id = NULL")
