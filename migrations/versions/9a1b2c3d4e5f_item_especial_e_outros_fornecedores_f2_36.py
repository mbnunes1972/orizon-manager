"""item especial e outros fornecedores — separação (F2-36, ACHADO-65/66)

DECIDIDO (Marcelo, 07/09): o F2-35 reusou `orcamentos.out_forn` pra duas coisas que não são a
mesma — Item Especial (mercadoria de terceiro vendida NA VENDA, markup 1, nunca toca o CFO) e
Outros Fornecedores (SUBSTITUIÇÃO do Custo de Fábrica, nasce só na AF/etapa 12, por
reclassificação 2.1.04.06→2.1.04.14). Corrige o desenho: coluna nova `item_especial`, e o que já
estava em `out_forn` migra pra lá (medido: `orc.out_forn` só era gravado pela rota da negociação
— a AF e a etapa 12 nunca escreveram nesta coluna, elas gravam no razão e no `itens_json` — então
tudo que está em `out_forn` hoje é de origem VENDA e pertence ao Item Especial).

`out_forn` é MANTIDA (não dropada) só por histórico — nada mais escreve nela a partir desta
migration (a rota que a alimentava virou `/item-especial`, gravando `item_especial`).

Contas novas 1.1.06.22/2.1.04.22 (Item Especial): PLANO_PADRAO + `seed_plano` já bastam pros
owners REAIS (seed-on-first-access, lazy, roda antes de qualquer operação de razão ou até só ao
abrir a tela de Plano de Contas — `mod_contabil.listar_contas`) — grupo 1/2 não precisa de
centro_custo/natureza_custo (isso é só do grupo 5, via `aplicar_gabarito_completo`), então
`seed_plano` sozinho é suficiente, sem precisar re-rodar o gabarito dinâmico aqui (diferente de
`655716ac5fd8`, que era grupo 5). MAS os 3 owners históricos fixos (`orizon_baseline_teste` —
`tests/test_gabarito_migration_x_seed.py`/`test_gabarito_migration_por_owner_dinamico.py`) não
têm NENHUM dado de instância (Rede/Loja) pra `seed_plano` alcançar num banco construído só por
`alembic upgrade head` — precisam do INSERT literal, mesmo padrão de `655716ac5fd8`.

Revision ID: 9a1b2c3d4e5f
Revises: 655716ac5fd8
Create Date: 2026-09-07 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a1b2c3d4e5f'
down_revision: Union[str, Sequence[str], None] = '655716ac5fd8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_OWNERS_FIXOS = [("rede", 1), ("loja", 1), ("loja", 3)]

_CONTAS_NOVAS = [
    # (codigo, nome, grupo, tipo, natureza, pai_codigo)
    ("1.1.06.22", "Item Especial a Apropriar", 1, "analitica", "devedora", "1.1.06"),
    ("2.1.04.22", "Provisão de Item Especial", 2, "analitica", "credora", "2.1.04"),
]


def upgrade() -> None:
    # Sem server_default (mesmo padrão de `out_forn`) — `test_schema_boot_estavel.py` exige que
    # o schema do Alembic bata byte a byte com `database.init_db()` (só o model tem `default=0.0`,
    # do lado Python; um server_default aqui divergiria do model).
    op.add_column('orcamentos', sa.Column('item_especial', sa.Float(), nullable=True))
    conn = op.get_bind()
    afetados = conn.execute(sa.text(
        "SELECT count(*) FROM orcamentos WHERE out_forn IS NOT NULL AND out_forn != 0"
    )).scalar_one()
    print("F2-36: %d orçamento(s) com out_forn != 0 — migrando pra item_especial." % afetados)
    conn.execute(sa.text(
        "UPDATE orcamentos SET item_especial = out_forn, out_forn = 0 "
        "WHERE out_forn IS NOT NULL AND out_forn != 0"
    ))

    # 3 owners fixos históricos — literal, idempotente por chave natural (mesmo padrão de 655716ac5fd8).
    for owner_tipo, owner_id in _OWNERS_FIXOS:
        for codigo, nome, grupo, tipo, natureza, pai_codigo in _CONTAS_NOVAS:
            ja = conn.execute(sa.text(
                "SELECT 1 FROM conta WHERE owner_tipo = :ot AND owner_id = :oid AND codigo = :codigo"
            ), {"ot": owner_tipo, "oid": owner_id, "codigo": codigo}).scalar_one_or_none()
            if ja is not None:
                continue
            pai = conn.execute(sa.text(
                "SELECT id FROM conta WHERE owner_tipo = :ot AND owner_id = :oid AND codigo = :codigo"
            ), {"ot": owner_tipo, "oid": owner_id, "codigo": pai_codigo}).scalar_one_or_none()
            if pai is None:
                continue   # owner sem plano de contas nenhum (ou sem o pai) — nada a estender
            conn.execute(sa.text(
                "INSERT INTO conta (owner_tipo, owner_id, codigo, nome, grupo, tipo, natureza, "
                "pai_id, ativa, ordem) VALUES "
                "(:ot, :oid, :codigo, :nome, :grupo, :tipo, :natureza, :pai_id, 1, 999)"
            ), {"ot": owner_tipo, "oid": owner_id, "codigo": codigo, "nome": nome, "grupo": grupo,
                "tipo": tipo, "natureza": natureza, "pai_id": pai})


def downgrade() -> None:
    # As contas 1.1.06.22/2.1.04.22 NÃO são removidas (mesma razão de 655716ac5fd8: podem já ter
    # Lancamento apontando pra elas) — só a coluna/dado da negociação volta.
    conn = op.get_bind()
    conn.execute(sa.text(
        "UPDATE orcamentos SET out_forn = item_especial "
        "WHERE item_especial IS NOT NULL AND item_especial != 0"
    ))
    op.drop_column('orcamentos', 'item_especial')
