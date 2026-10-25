"""
SQLAlchemy Multi-Tenant Models for Blogger Auto-Pilot SaaS
Supports PostgreSQL / Supabase natively with SQLite compatibility.
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, Text, DateTime, ForeignKey, Index, func
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def generate_uuid() -> str:
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = 'users'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=True) # Nullable for Google SSO
    google_sub_id = Column(String(255), unique=True, index=True, nullable=True)
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), default='subscriber', nullable=False) # admin, subscriber, agency
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    subscription = relationship('Subscription', back_populates='user', uselist=False, cascade='all, delete-orphan')
    notification_setting = relationship('NotificationSetting', back_populates='user', uselist=False, cascade='all, delete-orphan')
    blogs = relationship('Blog', back_populates='user', cascade='all, delete-orphan')
    articles = relationship('Article', back_populates='user', cascade='all, delete-orphan')
    keywords = relationship('Keyword', back_populates='user', cascade='all, delete-orphan')

class Subscription(Base):
    __tablename__ = 'subscriptions'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)
    plan_tier = Column(String(50), default='free', nullable=False) # free, starter, pro, agency
    status = Column(String(50), default='active', nullable=False) # active, past_due, cancelled, trialing
    article_credits_limit = Column(Integer, default=3, nullable=False)
    article_credits_used = Column(Integer, default=0, nullable=False)
    billing_cycle = Column(String(20), default='monthly', nullable=False) # monthly, yearly
    current_period_start = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    midtrans_order_id = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship('User', back_populates='subscription')

class Blog(Base):
    __tablename__ = 'blogs'

    id = Column(String(100), primary_key=True) # Blogger Blog ID
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    url = Column(String(500), nullable=True)
    account_name = Column(String(255), default='Akun Google', nullable=False)
    encrypted_token = Column(Text, nullable=True) # AES-256 encrypted OAuth credentials
    token_file = Column(String(500), nullable=True)
    client_secret_file = Column(String(500), nullable=True)
    niche_description = Column(Text, nullable=True)
    is_active = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship('User', back_populates='blogs')
    articles = relationship('Article', back_populates='blog', cascade='all, delete-orphan')
    keywords = relationship('Keyword', back_populates='blog', cascade='all, delete-orphan')

class Article(Base):
    __tablename__ = 'articles'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    blog_id = Column(String(100), ForeignKey('blogs.id', ondelete='CASCADE'), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    target_keyword = Column(String(255), nullable=True)
    meta_description = Column(Text, nullable=True)
    content_html = Column(Text, nullable=False)
    labels = Column(String(500), nullable=True)
    status = Column(String(50), default='draft', nullable=False) # draft, blogger_draft, published
    blogger_post_id = Column(String(100), nullable=True)
    blogger_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship('User', back_populates='articles')
    blog = relationship('Blog', back_populates='articles')

    __table_args__ = (
        Index('idx_articles_user_status', 'user_id', 'status'),
        Index('idx_articles_blog_status', 'blog_id', 'status'),
    )

class Keyword(Base):
    __tablename__ = 'keywords'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    blog_id = Column(String(100), ForeignKey('blogs.id', ondelete='CASCADE'), nullable=False, index=True)
    keyword = Column(String(255), nullable=False)
    search_intent = Column(String(50), default='Informational', nullable=False)
    status = Column(String(50), default='planned', nullable=False) # planned, in_progress, used
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship('User', back_populates='keywords')
    blog = relationship('Blog', back_populates='keywords')

    __table_args__ = (
        Index('idx_keywords_user_blog', 'user_id', 'blog_id'),
    )

class NotificationSetting(Base):
    __tablename__ = 'notification_settings'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)
    telegram_bot_token = Column(String(255), nullable=True)
    telegram_chat_id = Column(String(100), nullable=True)
    webhook_url = Column(String(500), nullable=True)
    notify_on_draft = Column(Boolean, default=True, nullable=False)
    notify_on_publish = Column(Boolean, default=True, nullable=False)
    notify_on_credit_low = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship('User', back_populates='notification_setting')

