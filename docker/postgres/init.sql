-- IIStudio — PostgreSQL инициализация
-- Таблицы пользователей, токенов, баланса, транзакций

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Пользователи ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email       VARCHAR(255) UNIQUE NOT NULL,
    username    VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active   BOOLEAN DEFAULT TRUE,
    is_admin    BOOLEAN DEFAULT FALSE,
    plan        VARCHAR(50) DEFAULT 'free',  -- free / pro / enterprise
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    last_login  TIMESTAMPTZ
);

-- ── API токены ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_tokens (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL DEFAULT 'Default',
    token       VARCHAR(255) UNIQUE NOT NULL,  -- sk-iis-xxxx формат
    prefix      VARCHAR(20) NOT NULL,           -- первые 8 символов для отображения
    is_active   BOOLEAN DEFAULT TRUE,
    last_used   TIMESTAMPTZ,
    requests_count BIGINT DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    expires_at  TIMESTAMPTZ  -- NULL = бессрочный
);

-- ── Баланс ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS balances (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    balance_usd DECIMAL(10,6) DEFAULT 0.000000,  -- баланс в USD
    free_tokens BIGINT DEFAULT 50000,             -- бесплатные токены (50K при регистрации)
    total_spent DECIMAL(10,6) DEFAULT 0.000000,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Транзакции / история пополнений ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS transactions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type        VARCHAR(50) NOT NULL,  -- topup / usage / refund / bonus
    amount_usd  DECIMAL(10,6) NOT NULL,
    tokens      BIGINT DEFAULT 0,
    description TEXT,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── История использования API ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_usage (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_id        UUID REFERENCES api_tokens(id),
    model           VARCHAR(100) NOT NULL,
    prompt_tokens   INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens    INTEGER DEFAULT 0,
    cost_usd        DECIMAL(10,8) DEFAULT 0,
    mode            VARCHAR(50) DEFAULT 'text',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Тарифные планы и цены ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pricing (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_id    VARCHAR(100) UNIQUE NOT NULL,
    model_name  VARCHAR(200) NOT NULL,
    provider    VARCHAR(100) NOT NULL,
    mode        VARCHAR(50) DEFAULT 'text',
    input_price_per_1m  DECIMAL(10,4) NOT NULL,  -- USD за 1M input токенов
    output_price_per_1m DECIMAL(10,4) NOT NULL,  -- USD за 1M output токенов
    is_free     BOOLEAN DEFAULT FALSE,
    is_active   BOOLEAN DEFAULT TRUE,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Индексы ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_api_tokens_token ON api_tokens(token);
CREATE INDEX IF NOT EXISTS idx_api_tokens_user_id ON api_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_api_usage_user_id ON api_usage(user_id);
CREATE INDEX IF NOT EXISTS idx_api_usage_created_at ON api_usage(created_at);
CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id);

-- ── Функции ───────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_balances_updated_at BEFORE UPDATE ON balances
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── Начальные данные: цены на модели ─────────────────────────────────────────
INSERT INTO pricing (model_id, model_name, provider, mode, input_price_per_1m, output_price_per_1m, is_free) VALUES
-- Бесплатные (через arena.ai анонимный аккаунт)
('gpt-4o',            'GPT-4o',                'OpenAI',    'text',   2.50,  10.00, false),
('gpt-4o-mini',       'GPT-4o mini',           'OpenAI',    'text',   0.15,   0.60, false),
('claude-3-5-sonnet', 'Claude 3.5 Sonnet',     'Anthropic', 'text',   3.00,  15.00, false),
('claude-3-5-haiku',  'Claude 3.5 Haiku',      'Anthropic', 'text',   0.80,   4.00, false),
('gemini-2-flash',    'Gemini 2.0 Flash',      'Google',    'text',   0.10,   0.40, false),
('gemini-1-5-pro',    'Gemini 1.5 Pro',        'Google',    'text',   1.25,   5.00, false),
('deepseek-r1',       'DeepSeek R1',           'DeepSeek',  'text',   0.55,   2.19, false),
('deepseek-v3',       'DeepSeek V3',           'DeepSeek',  'text',   0.14,   0.28, false),
('llama-3-3-70b',     'Llama 3.3 70B',         'Meta',      'text',   0.00,   0.00, true),
('mistral-large',     'Mistral Large',         'Mistral',   'text',   2.00,   6.00, false),
('o1-mini',           'o1-mini',               'OpenAI',    'text',   1.10,   4.40, false),
-- Изображения
('dall-e-3',          'DALL-E 3',              'OpenAI',    'images', 0.00,  40.00, false),
('flux-1-1-pro',      'FLUX 1.1 Pro',          'Black Forest','images',0.00,  4.00, false)
ON CONFLICT (model_id) DO NOTHING;

-- ── Демо-пользователь (admin) ──────────────────────────────────────────────────
-- Пароль: admin123 (bcrypt hash)
INSERT INTO users (email, username, password_hash, is_admin, plan) VALUES
('admin@iistudio.dev', 'admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMEbI.5aCn5hJKKpUa8bnIMiu.', true, 'enterprise')
ON CONFLICT (email) DO NOTHING;

-- Баланс для admin
INSERT INTO balances (user_id, balance_usd, free_tokens)
SELECT id, 100.00, 999999999 FROM users WHERE email = 'admin@iistudio.dev'
ON CONFLICT (user_id) DO NOTHING;
