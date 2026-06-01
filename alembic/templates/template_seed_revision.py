"""<seed title>

Revision ID: <revision_id>
Revises: <down_revision>
Create Date: <YYYY-MM-DD HH:MM:SS>
"""

from typing import Sequence, Union

from alembic import op


revision: str = "<revision_id>"
down_revision: Union[str, Sequence[str], None] = "<down_revision>"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use idempotent inserts to avoid duplicates.
    op.execute(
        """
        INSERT INTO <table> (<unique_col>, ...)
        VALUES
            (...)
        ON CONFLICT (<unique_col>)
        DO UPDATE SET ...;
        """
    )


def downgrade() -> None:
    # Remove only seeded data by deterministic keys.
    op.execute(
        """
        DELETE FROM <table>
        WHERE <unique_col> IN (...);
        """
    )
