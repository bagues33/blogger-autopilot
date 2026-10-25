-- ==============================================================================
-- BLOGGER AUTO-PILOT SAAS: SUPABASE / POSTGRESQL PRODUCTION SCHEMA
-- Ready for Supabase SQL Editor with Row-Level Security (RLS) & Indexes
-- ==============================================================================

-- 1. Enable UUID Extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Users Table
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255),
    google_sub_id VARCHAR(255) UNIQUE,
    full_name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'subscriber', -- admin, subscriber, agency
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_google_sub ON users(google_sub_id);

-- 3. Subscriptions & Billing Table
CREATE TABLE IF NOT EXISTS subscriptions (
    id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    user_id VARCHAR(36) UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_tier VARCHAR(50) NOT NULL DEFAULT 'free', -- free, starter, pro, agency
    status VARCHAR(50) NOT NULL DEFAULT 'active', -- active, past_due, cancelled, trialing
    article_credits_limit INT NOT NULL DEFAULT 3,
    article_credits_used INT NOT NULL DEFAULT 0,
    billing_cycle VARCHAR(20) NOT NULL DEFAULT 'monthly', -- monthly, yearly
    current_period_start TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    current_period_end TIMESTAMP WITH TIME ZONE,
    midtrans_order_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);

-- 4. Blogs Table (Blogger Sites)
CREATE TABLE IF NOT EXISTS blogs (
    id VARCHAR(100) PRIMARY KEY, -- Google Blogger Blog ID
    user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    url VARCHAR(500),
    account_name VARCHAR(255) NOT NULL DEFAULT 'Akun Google',
    encrypted_token TEXT, -- AES-256 encrypted OAuth token
    token_file VARCHAR(500),
    client_secret_file VARCHAR(500),
    niche_description TEXT,
    is_active INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_blogs_user ON blogs(user_id);

-- 5. Articles Table
CREATE TABLE IF NOT EXISTS articles (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blog_id VARCHAR(100) NOT NULL REFERENCES blogs(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    target_keyword VARCHAR(255),
    meta_description TEXT,
    content_html TEXT NOT NULL,
    labels VARCHAR(500),
    status VARCHAR(50) NOT NULL DEFAULT 'draft', -- draft, blogger_draft, published
    blogger_post_id VARCHAR(100),
    blogger_url VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_articles_user_status ON articles(user_id, status);
CREATE INDEX IF NOT EXISTS idx_articles_blog_status ON articles(blog_id, status);

-- 6. Keywords Bank Table
CREATE TABLE IF NOT EXISTS keywords (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blog_id VARCHAR(100) NOT NULL REFERENCES blogs(id) ON DELETE CASCADE,
    keyword VARCHAR(255) NOT NULL,
    search_intent VARCHAR(50) NOT NULL DEFAULT 'Informational', -- Informational, Commercial, Navigational
    status VARCHAR(50) NOT NULL DEFAULT 'planned', -- planned, in_progress, used
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_keywords_user_blog ON keywords(user_id, blog_id);
CREATE INDEX IF NOT EXISTS idx_keywords_status ON keywords(status);

-- 7. Notification Settings Table
CREATE TABLE IF NOT EXISTS notification_settings (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    telegram_bot_token VARCHAR(255),
    telegram_chat_id VARCHAR(100),
    webhook_url VARCHAR(500),
    notify_on_draft BOOLEAN DEFAULT TRUE NOT NULL,
    notify_on_publish BOOLEAN DEFAULT TRUE NOT NULL,
    notify_on_credit_low BOOLEAN DEFAULT TRUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- ==============================================================================
-- ROW-LEVEL SECURITY (RLS) FOR SUPABASE
-- Ensures complete isolation: each tenant can only view & modify their own data
-- ==============================================================================

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE blogs ENABLE ROW LEVEL SECURITY;
ALTER TABLE articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE keywords ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_settings ENABLE ROW LEVEL SECURITY;

-- Note: In a SaaS environment where FastAPI manages JWT sessions, 
-- connection pooling uses the service_role key to bypass RLS, 
-- while FastAPI's auth middleware guarantees user_id filtering in code.
