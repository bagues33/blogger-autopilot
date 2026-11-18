"""
Unit tests for Content Generator Deep Module & InMemoryLLMAdapter.
"""
import uuid
import pytest
from sqlalchemy.orm import Session

from src.models.models import User, Subscription, Blog, Keyword, Article
from src.services.content_generator import (
    generate_article,
    InMemoryLLMAdapter,
    ArticleGenerationResult
)

def test_content_generator_full_flow(db_session: Session):
    unique_suffix = uuid.uuid4().hex[:6]
    test_email = f"writer_{unique_suffix}@testdomain.id"

    # 1. Setup Tenant with Pro subscription
    user = User(
        id=str(uuid.uuid4()),
        email=test_email,
        hashed_password="mock_hash",
        full_name="Writer Tester",
        role="subscriber",
        is_active=True
    )
    db_session.add(user)

    sub = Subscription(
        user_id=user.id,
        plan_tier="pro",
        status="active",
        article_credits_limit=5,
        article_credits_used=0
    )
    db_session.add(sub)

    blog = Blog(
        id=f"blog_{unique_suffix}",
        user_id=user.id,
        name="Writer Test Blog",
        url="https://writertest.blogspot.com",
        token_file="tokens/test.json",
        is_active=1
    )
    db_session.add(blog)

    kw = Keyword(
        user_id=user.id,
        blog_id=blog.id,
        keyword="arsitektur deep module python modern",
        search_intent="Informational",
        status="planned"
    )
    db_session.add(kw)
    db_session.commit()

    # 2. Test In-Memory Generation
    mock_adapter = InMemoryLLMAdapter(canned_response={
        "title": "Panduan Lengkap Arsitektur Deep Module Python",
        "meta_description": "Pelajari prinsip perancangan deep module dan seam adapter.",
        "labels": "Software Engineering, Python, Architecture",
        "content_html": "<p>Pembahasan mendalam perancangan deep module dengan interface ringkas.</p><h2>FAQ</h2><p>Tanya jawab seputar seam adapter.</p>"
    })

    result: ArticleGenerationResult = generate_article(
        tenant_id=user.id,
        blog_id=blog.id,
        keyword_id=kw.id,
        llm_adapter=mock_adapter,
        db=db_session
    )

    assert result.success is True, f"Expected success but got: {result.error}"
    assert result.article_id is not None
    assert result.keyword == "arsitektur deep module python modern"
    assert result.credits_remaining == 4

    # 3. Verify Database State
    db_session.refresh(kw)
    db_session.refresh(sub)
    assert kw.status == "in_progress"
    assert sub.article_credits_used == 1

    created_article = db_session.query(Article).filter(Article.id == result.article_id).first()
    assert created_article is not None
    assert created_article.user_id == user.id
    assert created_article.blog_id == blog.id
    assert "schema.org" in created_article.content_html

    # 4. Test Quota Exhaustion
    sub.article_credits_used = 5
    db_session.commit()

    exhausted_result = generate_article(
        tenant_id=user.id,
        blog_id=blog.id,
        keyword_id=kw.id,
        llm_adapter=mock_adapter,
        db=db_session
    )
    assert exhausted_result.success is False
    assert "habis" in exhausted_result.error.lower()

