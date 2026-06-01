"""initial schema for in-game purchases"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


user_status = postgresql.ENUM("active", "blocked", name="user_status")
purchase_status = postgresql.ENUM("pending", "completed", "failed", "refunded", name="purchase_status")
topup_status = postgresql.ENUM("pending", "applied", "canceled", name="topup_status")
refund_status = postgresql.ENUM("pending", "applied", "rejected", name="refund_status")


def upgrade() -> None:
    bind = op.get_bind()

    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    user_status.create(bind, checkfirst=True)
    purchase_status.create(bind, checkfirst=True)
    topup_status.create(bind, checkfirst=True)
    refund_status.create(bind, checkfirst=True)

    op.create_table(
        "roles",
        sa.Column("id", sa.SmallInteger(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_roles_code"),
        sa.CheckConstraint("code ~ '^[a-z_]{2,32}$'", name="ck_roles_code_format"),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role_id", sa.SmallInteger(), nullable=False),
        sa.Column("status", user_status, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], onupdate="CASCADE", ondelete="RESTRICT"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.CheckConstraint("username ~ '^[A-Za-z0-9_]{3,50}$'", name="ck_users_username_format"),
        sa.CheckConstraint("position('@' in email) > 1", name="ck_users_email_format"),
        sa.CheckConstraint("char_length(password_hash) >= 60", name="ck_users_password_hash_len"),
    )
    op.create_index("uq_users_email_ci", "users", [sa.text("lower(email)")], unique=True)
    op.create_index("idx_users_role_id", "users", ["role_id"], unique=False)

    op.create_table(
        "wallets",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False, server_default="GLD"),
        sa.Column("balance", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], onupdate="CASCADE", ondelete="RESTRICT"),
        sa.UniqueConstraint("user_id", name="uq_wallets_user_id"),
        sa.UniqueConstraint("id", "user_id", name="uq_wallets_id_user"),
        sa.CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name="ck_wallets_currency"),
        sa.CheckConstraint("balance >= 0", name="ck_wallets_balance_non_negative"),
    )

    op.create_table(
        "items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(18, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("stock", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("sku", name="uq_items_sku"),
        sa.CheckConstraint("price >= 0", name="ck_items_price_non_negative"),
        sa.CheckConstraint("stock IS NULL OR stock >= 0", name="ck_items_stock_non_negative"),
    )
    op.create_index(
        "idx_items_active_price",
        "items",
        ["is_active", "price"],
        unique=False,
        postgresql_where=sa.text("is_active = true"),
    )

    op.create_table(
        "purchases",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("wallet_id", sa.BigInteger(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 2), nullable=False),
        sa.Column(
            "total_amount",
            sa.Numeric(18, 2),
            sa.Computed("quantity * unit_price", persisted=True),
            nullable=False,
        ),
        sa.Column("status", purchase_status, nullable=False, server_default="pending"),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], onupdate="CASCADE", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], onupdate="CASCADE", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["wallet_id", "user_id"],
            ["wallets.id", "wallets.user_id"],
            onupdate="CASCADE",
            ondelete="RESTRICT",
            name="fk_purchases_wallet_owner",
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_purchases_idempotency_key"),
        sa.CheckConstraint("quantity > 0", name="ck_purchases_quantity_positive"),
        sa.CheckConstraint("unit_price >= 0", name="ck_purchases_unit_price_non_negative"),
        sa.CheckConstraint(
            "((status IN ('pending', 'failed') AND completed_at IS NULL) OR "
            "(status IN ('completed', 'refunded') AND completed_at IS NOT NULL))",
            name="ck_purchases_status_completed_at",
        ),
    )
    op.create_index("idx_purchases_user_created_at_desc", "purchases", ["user_id", "created_at"], unique=False)
    op.create_index("idx_purchases_status_created_at_desc", "purchases", ["status", "created_at"], unique=False)
    op.create_index("idx_purchases_item_created_at_desc", "purchases", ["item_id", "created_at"], unique=False)

    op.create_table(
        "inventory",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], onupdate="CASCADE", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], onupdate="CASCADE", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("user_id", "item_id", name="pk_inventory"),
        sa.CheckConstraint("quantity >= 0", name="ck_inventory_quantity_non_negative"),
    )
    op.create_index("idx_inventory_item_id", "inventory", ["item_id"], unique=False)

    op.create_table(
        "topups",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("wallet_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", topup_status, nullable=False, server_default="pending"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("external_ref", sa.String(length=128), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"], onupdate="CASCADE", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], onupdate="CASCADE", ondelete="SET NULL"),
        sa.UniqueConstraint("external_ref", name="uq_topups_external_ref"),
        sa.CheckConstraint("amount > 0", name="ck_topups_amount_positive"),
        sa.CheckConstraint(
            "((status = 'applied' AND applied_at IS NOT NULL) OR "
            "(status IN ('pending', 'canceled') AND applied_at IS NULL))",
            name="ck_topups_status_applied_at",
        ),
    )
    op.create_index("idx_topups_wallet_created_at_desc", "topups", ["wallet_id", "created_at"], unique=False)
    op.create_index("idx_topups_status_created_at_desc", "topups", ["status", "created_at"], unique=False)

    op.create_table(
        "refunds",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("purchase_id", sa.BigInteger(), nullable=False),
        sa.Column("wallet_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", refund_status, nullable=False, server_default="pending"),
        sa.Column("external_ref", sa.String(length=128), nullable=True),
        sa.Column("processed_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["purchase_id"], ["purchases.id"], onupdate="CASCADE", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"], onupdate="CASCADE", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["processed_by"], ["users.id"], onupdate="CASCADE", ondelete="SET NULL"),
        sa.UniqueConstraint("purchase_id", name="uq_refunds_purchase_id"),
        sa.UniqueConstraint("external_ref", name="uq_refunds_external_ref"),
        sa.CheckConstraint("amount > 0", name="ck_refunds_amount_positive"),
        sa.CheckConstraint(
            "((status = 'applied' AND processed_at IS NOT NULL) OR "
            "(status IN ('pending', 'rejected') AND processed_at IS NULL))",
            name="ck_refunds_status_processed_at",
        ),
    )
    op.create_index("idx_refunds_wallet_created_at_desc", "refunds", ["wallet_id", "created_at"], unique=False)
    op.create_index("idx_refunds_status_created_at_desc", "refunds", ["status", "created_at"], unique=False)

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=True),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("payload_before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("payload_after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], onupdate="CASCADE", ondelete="SET NULL"),
    )
    op.create_index(
        "idx_audit_entity_created_at_desc",
        "audit_log",
        ["entity_type", "entity_id", "created_at"],
        unique=False,
    )
    op.create_index("idx_audit_actor_created_at_desc", "audit_log", ["actor_user_id", "created_at"], unique=False)

    op.execute(
        """
        CREATE OR REPLACE FUNCTION fn_set_updated_at()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$;
        """
    )

    for table_name in ("users", "wallets", "items", "purchases", "inventory"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table_name}_set_updated_at
            BEFORE UPDATE ON {table_name}
            FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
            """
        )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION fn_validate_refund()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_total_amount NUMERIC(18,2);
            v_wallet_id BIGINT;
        BEGIN
            SELECT p.total_amount, p.wallet_id
            INTO v_total_amount, v_wallet_id
            FROM purchases p
            WHERE p.id = NEW.purchase_id
            FOR UPDATE;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'Purchase % not found', NEW.purchase_id;
            END IF;

            IF NEW.wallet_id <> v_wallet_id THEN
                RAISE EXCEPTION 'Refund wallet % does not match purchase wallet %', NEW.wallet_id, v_wallet_id;
            END IF;

            IF NEW.amount <> v_total_amount THEN
                RAISE EXCEPTION 'MVP supports full refund only. Amount % must equal purchase total %', NEW.amount, v_total_amount;
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_refunds_validate
        BEFORE INSERT OR UPDATE OF purchase_id, wallet_id, amount
        ON refunds
        FOR EACH ROW EXECUTE FUNCTION fn_validate_refund();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_refunds_validate ON refunds")
    op.execute("DROP FUNCTION IF EXISTS fn_validate_refund")

    for table_name in ("users", "wallets", "items", "purchases", "inventory"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_set_updated_at ON {table_name}")

    op.execute("DROP FUNCTION IF EXISTS fn_set_updated_at")

    op.drop_index("idx_audit_actor_created_at_desc", table_name="audit_log")
    op.drop_index("idx_audit_entity_created_at_desc", table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_index("idx_refunds_status_created_at_desc", table_name="refunds")
    op.drop_index("idx_refunds_wallet_created_at_desc", table_name="refunds")
    op.drop_table("refunds")

    op.drop_index("idx_topups_status_created_at_desc", table_name="topups")
    op.drop_index("idx_topups_wallet_created_at_desc", table_name="topups")
    op.drop_table("topups")

    op.drop_index("idx_inventory_item_id", table_name="inventory")
    op.drop_table("inventory")

    op.drop_index("idx_purchases_item_created_at_desc", table_name="purchases")
    op.drop_index("idx_purchases_status_created_at_desc", table_name="purchases")
    op.drop_index("idx_purchases_user_created_at_desc", table_name="purchases")
    op.drop_table("purchases")

    op.drop_index("idx_items_active_price", table_name="items")
    op.drop_table("items")

    op.drop_table("wallets")

    op.drop_index("idx_users_role_id", table_name="users")
    op.drop_index("uq_users_email_ci", table_name="users")
    op.drop_table("users")

    op.drop_table("roles")

    refund_status.drop(op.get_bind(), checkfirst=True)
    topup_status.drop(op.get_bind(), checkfirst=True)
    purchase_status.drop(op.get_bind(), checkfirst=True)
    user_status.drop(op.get_bind(), checkfirst=True)
