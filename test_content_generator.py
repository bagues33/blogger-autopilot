"""
Test Suite for Content Generator Deep Module & In-Memory LLM Seam Adapter
Verifies deterministic article generation, schema injection, quota deduction,
and error handling without external network dependencies.
"""

import uuid
from db_saas import SessionLocal
from models_saas import User, Subscription, Blog, Keyword, Article
from content_generator import (
    generate_article,
    InMemoryLLMAdapter,
    ArticleGenerationResult
)

def test_content_generator_full_flow():
    db = SessionLocal()
    unique_suffix = uuid.uuid4().hex[:6]
    test_email = f"writer_{unique_suffix}@testdomain.id"

    print("=== Testing Content Generator Deep Module ===")

    try:
        # 1. Setup Tenant with Pro subscription
        user = User(
            id=str(uuid.uuid4()),
            email=test_email,
            hashed_password="mock_hash",
            full_name="Writer Tester",
            role="subscriber",
            is_active=True
        )
        db.add(user)

        sub = Subscription(
            user_id=user.id,
            plan_tier="pro",
            status="active",
            article_credits_limit=5,
            article_credits_used=0
        )
        db.add(sub)

        blog = Blog(
            id=f"blog_{unique_suffix}",
            user_id=user.id,
            name="Writer Test Blog",
            url="https://writertest.blogspot.com",
            token_file="tokens/test.json",
            is_active=1
        )
        db.add(blog)

        kw = Keyword(
            user_id=user.id,
            blog_id=blog.id,
            keyword="arsitektur deep module python modern",
            search_intent="Informational",
            status="planned"
        )
        db.add(kw)
        db.commit()

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
            db=db
        )

        assert result.success is True, f"Expected success but got: {result.error}"
        assert result.article_id is not None
        assert result.keyword == "arsitektur deep module python modern"
        assert result.credits_remaining == 4
        print(f"✓ Article generated successfully: ID={result.article_id}, Title='{result.title}'")

        # 3. Verify Database State
        db.refresh(kw)
        db.refresh(sub)
        assert kw.status == "in_progress", f"Expected keyword status 'in_progress', got '{kw.status}'"
        assert sub.article_credits_used == 1, f"Expected 1 credit used, got {sub.article_credits_used}"

        created_article = db.query(Article).filter(Article.id == result.article_id).first()
        assert created_article is not None
        assert created_article.user_id == user.id
        assert created_article.blog_id == blog.id
        assert "schema.org" in created_article.content_html
        print(f"✓ Database state verified: Keyword in_progress, Quota used=1/5, Schema injected.")

        # 4. Test Quota Exhaustion
        sub.article_credits_used = 5
        db.commit()

        exhausted_result = generate_article(
            tenant_id=user.id,
            blog_id=blog.id,
            keyword_id=kw.id,
            llm_adapter=mock_adapter,
            db=db
        )
        assert exhausted_result.success is False
        assert "habis" in exhausted_result.error.lower()
        print(f"✓ Quota exhaustion protection verified: {exhausted_result.error}")

        print("\n🎉 ALL CONTENT GENERATOR & IN-MEMORY SEAM TESTS PASSED 100%!")

    finally:
        db.close()

if __name__ == '__main__':
    test_content_generator_full_flow()
