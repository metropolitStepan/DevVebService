BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_status') THEN
        CREATE TYPE user_status AS ENUM ('active', 'blocked');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'purchase_status') THEN
        CREATE TYPE purchase_status AS ENUM ('pending', 'completed', 'failed', 'refunded');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'topup_status') THEN
        CREATE TYPE topup_status AS ENUM ('pending', 'applied', 'canceled');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'refund_status') THEN
        CREATE TYPE refund_status AS ENUM ('pending', 'applied', 'rejected');
    END IF;
END$$;

CREATE TABLE IF NOT EXISTS roles (
    id SMALLSERIAL PRIMARY KEY,
    code VARCHAR(32) NOT NULL UNIQUE,
    name VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_roles_code_format CHECK (code ~ '^[a-z_]{2,32}$')
);

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(254) NOT NULL,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role_id SMALLINT NOT NULL REFERENCES roles(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    status user_status NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ NULL,
    CONSTRAINT ck_users_username_format CHECK (username ~ '^[A-Za-z0-9_]{3,50}$'),
    CONSTRAINT ck_users_email_format CHECK (position('@' in email) > 1),
    CONSTRAINT ck_users_password_hash_len CHECK (char_length(password_hash) >= 60)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_ci ON users (lower(email));
CREATE INDEX IF NOT EXISTS idx_users_role_id ON users(role_id);

CREATE TABLE IF NOT EXISTS wallets (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    currency_code CHAR(3) NOT NULL DEFAULT 'GLD',
    balance NUMERIC(18,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_wallets_id_user UNIQUE (id, user_id),
    CONSTRAINT ck_wallets_currency CHECK (currency_code ~ '^[A-Z]{3}$'),
    CONSTRAINT ck_wallets_balance_non_negative CHECK (balance >= 0)
);

CREATE TABLE IF NOT EXISTS items (
    id BIGSERIAL PRIMARY KEY,
    sku VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(120) NOT NULL,
    description TEXT NULL,
    price NUMERIC(18,2) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    stock INTEGER NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ NULL,
    CONSTRAINT ck_items_price_non_negative CHECK (price >= 0),
    CONSTRAINT ck_items_stock_non_negative CHECK (stock IS NULL OR stock >= 0)
);

CREATE INDEX IF NOT EXISTS idx_items_active_price
    ON items (is_active, price)
    WHERE is_active = TRUE;

CREATE TABLE IF NOT EXISTS purchases (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    wallet_id BIGINT NOT NULL,
    item_id BIGINT NOT NULL REFERENCES items(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(18,2) NOT NULL,
    total_amount NUMERIC(18,2) GENERATED ALWAYS AS (quantity * unit_price) STORED,
    status purchase_status NOT NULL DEFAULT 'pending',
    idempotency_key UUID NOT NULL DEFAULT gen_random_uuid(),
    failure_reason TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_purchases_wallet_owner
        FOREIGN KEY (wallet_id, user_id)
        REFERENCES wallets (id, user_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT uq_purchases_idempotency_key UNIQUE (idempotency_key),
    CONSTRAINT ck_purchases_quantity_positive CHECK (quantity > 0),
    CONSTRAINT ck_purchases_unit_price_non_negative CHECK (unit_price >= 0),
    CONSTRAINT ck_purchases_status_completed_at CHECK (
        (status IN ('pending', 'failed') AND completed_at IS NULL)
        OR (status IN ('completed', 'refunded') AND completed_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_purchases_user_created_at_desc ON purchases(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_purchases_status_created_at_desc ON purchases(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_purchases_item_created_at_desc ON purchases(item_id, created_at DESC);

CREATE TABLE IF NOT EXISTS inventory (
    user_id BIGINT NOT NULL REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    item_id BIGINT NOT NULL REFERENCES items(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    quantity BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, item_id),
    CONSTRAINT ck_inventory_quantity_non_negative CHECK (quantity >= 0)
);

CREATE INDEX IF NOT EXISTS idx_inventory_item_id ON inventory(item_id);

CREATE TABLE IF NOT EXISTS topups (
    id BIGSERIAL PRIMARY KEY,
    wallet_id BIGINT NOT NULL REFERENCES wallets(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    amount NUMERIC(18,2) NOT NULL,
    status topup_status NOT NULL DEFAULT 'pending',
    reason TEXT NOT NULL,
    external_ref VARCHAR(128) NULL UNIQUE,
    created_by BIGINT NULL REFERENCES users(id) ON UPDATE CASCADE ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    applied_at TIMESTAMPTZ NULL,
    CONSTRAINT ck_topups_amount_positive CHECK (amount > 0),
    CONSTRAINT ck_topups_status_applied_at CHECK (
        (status = 'applied' AND applied_at IS NOT NULL)
        OR (status IN ('pending', 'canceled') AND applied_at IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_topups_wallet_created_at_desc ON topups(wallet_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_topups_status_created_at_desc ON topups(status, created_at DESC);

CREATE TABLE IF NOT EXISTS refunds (
    id BIGSERIAL PRIMARY KEY,
    purchase_id BIGINT NOT NULL UNIQUE REFERENCES purchases(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    wallet_id BIGINT NOT NULL REFERENCES wallets(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    amount NUMERIC(18,2) NOT NULL,
    reason TEXT NOT NULL,
    status refund_status NOT NULL DEFAULT 'pending',
    external_ref VARCHAR(128) NULL UNIQUE,
    processed_by BIGINT NULL REFERENCES users(id) ON UPDATE CASCADE ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ NULL,
    CONSTRAINT ck_refunds_amount_positive CHECK (amount > 0),
    CONSTRAINT ck_refunds_status_processed_at CHECK (
        (status = 'applied' AND processed_at IS NOT NULL)
        OR (status IN ('pending', 'rejected') AND processed_at IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_refunds_wallet_created_at_desc ON refunds(wallet_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_refunds_status_created_at_desc ON refunds(status, created_at DESC);

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    actor_user_id BIGINT NULL REFERENCES users(id) ON UPDATE CASCADE ON DELETE SET NULL,
    action VARCHAR(64) NOT NULL,
    entity_type VARCHAR(64) NOT NULL,
    entity_id BIGINT NULL,
    request_id UUID NULL,
    ip INET NULL,
    user_agent TEXT NULL,
    payload_before JSONB NULL,
    payload_after JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_entity_created_at_desc ON audit_log(entity_type, entity_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_actor_created_at_desc ON audit_log(actor_user_id, created_at DESC);

CREATE OR REPLACE FUNCTION fn_set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_users_set_updated_at ON users;
CREATE TRIGGER trg_users_set_updated_at
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

DROP TRIGGER IF EXISTS trg_wallets_set_updated_at ON wallets;
CREATE TRIGGER trg_wallets_set_updated_at
BEFORE UPDATE ON wallets
FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

DROP TRIGGER IF EXISTS trg_items_set_updated_at ON items;
CREATE TRIGGER trg_items_set_updated_at
BEFORE UPDATE ON items
FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

DROP TRIGGER IF EXISTS trg_purchases_set_updated_at ON purchases;
CREATE TRIGGER trg_purchases_set_updated_at
BEFORE UPDATE ON purchases
FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

DROP TRIGGER IF EXISTS trg_inventory_set_updated_at ON inventory;
CREATE TRIGGER trg_inventory_set_updated_at
BEFORE UPDATE ON inventory
FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

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

DROP TRIGGER IF EXISTS trg_refunds_validate ON refunds;
CREATE TRIGGER trg_refunds_validate
BEFORE INSERT OR UPDATE OF purchase_id, wallet_id, amount
ON refunds
FOR EACH ROW EXECUTE FUNCTION fn_validate_refund();

COMMIT;
