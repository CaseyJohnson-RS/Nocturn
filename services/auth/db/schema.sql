-- ===============================
-- SCHEMA.SQL FOR AUTH SERVICE
-- ===============================

-- Создаём схему
CREATE SCHEMA IF NOT EXISTS auth AUTHORIZATION auth_service;

-- -------------------------------
-- Users
-- -------------------------------
CREATE TABLE IF NOT EXISTS auth.users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    is_email_verified BOOLEAN DEFAULT FALSE NOT NULL,
    password_hash TEXT NOT NULL,
    username TEXT UNIQUE NOT NULL,
    status TEXT DEFAULT 'active' NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- -------------------------------
-- Refresh Tokens
-- -------------------------------
CREATE TABLE IF NOT EXISTS auth.refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(user_id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    replaced_by_token_id UUID REFERENCES auth.refresh_tokens(id),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    user_agent TEXT
);

-- -------------------------------
-- Security Events
-- -------------------------------
CREATE TABLE IF NOT EXISTS auth.security_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(user_id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    ip_address INET,
    user_agent TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- -------------------------------
-- Email Verification Tokens
-- -------------------------------
CREATE TABLE IF NOT EXISTS auth.email_verification_tokens (
    token UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(user_id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    used BOOLEAN DEFAULT FALSE NOT NULL
);

-- -------------------------------
-- Password Reset Tokens
-- -------------------------------
CREATE TABLE IF NOT EXISTS auth.password_reset_tokens (
    token UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(user_id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    used BOOLEAN DEFAULT FALSE NOT NULL
);

-- -------------------------------
-- Индексы для ускорения запросов
-- -------------------------------
CREATE INDEX IF NOT EXISTS idx_users_email ON auth.users(email);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON auth.refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_security_events_user_id ON auth.security_events(user_id);
CREATE INDEX IF NOT EXISTS idx_email_tokens_user_id ON auth.email_verification_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_password_tokens_user_id ON auth.password_reset_tokens(user_id);
