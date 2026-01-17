-- Миграция: tokens → stars
-- Дата: 2025-01-17

-- 1. Таблица users
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'tokens'
    ) THEN
        EXECUTE 'ALTER TABLE users RENAME COLUMN tokens TO stars';
    END IF;
END $$;

-- 2. Таблица subscriptions
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'subscriptions' AND column_name = 'tokens_limit'
    ) THEN
        EXECUTE 'ALTER TABLE subscriptions RENAME COLUMN tokens_limit TO stars_limit';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'subscriptions' AND column_name = 'tokens_used'
    ) THEN
        EXECUTE 'ALTER TABLE subscriptions RENAME COLUMN tokens_used TO stars_used';
    END IF;
END $$;

-- 2.1 Таблица transactions (если есть колонка tokens)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'transactions' AND column_name = 'tokens'
    ) THEN
        EXECUTE 'ALTER TABLE transactions RENAME COLUMN tokens TO stars';
    END IF;
END $$;

-- 2.2 Таблица token_usage → star_usage
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'token_usage'
    ) THEN
        EXECUTE 'ALTER TABLE token_usage RENAME TO star_usage';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'star_usage' AND column_name = 'tokens_used'
    ) THEN
        EXECUTE 'ALTER TABLE star_usage RENAME COLUMN tokens_used TO stars_used';
    END IF;
END $$;

-- 2.3 Таблица referrals (tokens_earned → stars_earned)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'referrals' AND column_name = 'tokens_earned'
    ) THEN
        EXECUTE 'ALTER TABLE referrals RENAME COLUMN tokens_earned TO stars_earned';
    END IF;
END $$;

-- 3. Проверка
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'users' AND column_name IN ('tokens', 'stars');

SELECT column_name FROM information_schema.columns 
WHERE table_name = 'subscriptions' AND column_name LIKE '%stars%';

SELECT column_name FROM information_schema.columns
WHERE table_name = 'transactions' AND column_name IN ('tokens', 'stars');

SELECT column_name FROM information_schema.columns
WHERE table_name = 'referrals' AND column_name IN ('tokens_earned', 'stars_earned');
