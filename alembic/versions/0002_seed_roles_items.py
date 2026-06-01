"""seed base roles and initial items"""

from typing import Sequence, Union

from alembic import op


revision: str = "0002_seed_roles_items"
down_revision: Union[str, Sequence[str], None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO roles (code, name)
        VALUES
            ('admin', 'Administrator'),
            ('player', 'Player')
        ON CONFLICT (code)
        DO UPDATE SET name = EXCLUDED.name;
        """
    )

    op.execute(
        """
        INSERT INTO items (sku, name, description, price, is_active, stock)
        VALUES
            (
                'starter_skin_red',
                'Starter Red Skin',
                'Basic cosmetic skin for new players',
                199.00,
                TRUE,
                NULL
            ),
            (
                'booster_x2_24h',
                'Booster x2 (24h)',
                'Doubles rewards for 24 hours',
                299.00,
                TRUE,
                NULL
            )
        ON CONFLICT (sku)
        DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            price = EXCLUDED.price,
            is_active = EXCLUDED.is_active,
            stock = EXCLUDED.stock,
            updated_at = now();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM items
        WHERE sku IN ('starter_skin_red', 'booster_x2_24h');
        """
    )

    op.execute(
        """
        DELETE FROM roles r
        WHERE r.code IN ('admin', 'player')
          AND NOT EXISTS (
              SELECT 1
              FROM users u
              WHERE u.role_id = r.id
          );
        """
    )
