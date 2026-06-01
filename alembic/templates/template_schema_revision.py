"""<short migration title>

Revision ID: <revision_id>
Revises: <down_revision>
Create Date: <YYYY-MM-DD HH:MM:SS>
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "<revision_id>"
down_revision: Union[str, Sequence[str], None] = "<down_revision>"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) create table/column/constraint/index
    # op.create_table(...)
    # op.add_column(...)
    # op.create_index(...)
    pass


def downgrade() -> None:
    # reverse order for objects created in upgrade
    # op.drop_index(...)
    # op.drop_column(...)
    # op.drop_table(...)
    pass
