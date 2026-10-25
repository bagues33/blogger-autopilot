"""
Tenant Isolation & Webhook Verification Test
Proves that User A's data is strictly isolated from User B, and Midtrans webhook only modifies the intended tenant.
"""

from db_saas import SessionLocal
from models_saas import User, Subscription, Blog, Article, Keyword
from midtrans_service import handle_midtrans_webhook, PLAN_TIERS
import uuid

def test_tenant_isolation():
    db = SessionLocal()
    try:
        # Create User A
        email_a = f"tenant_a_{uuid.uuid4().hex[:6]}@example.com"
        user_a = User(email=email_a, role='subscriber')
        db.add(user_a)
        db.flush()
        sub_a = Subscription(user_id=user_a.id, plan_tier='free', article_credits_limit=3, article_credits_used=1)
        db.add(sub_a)

        # Create User B
        email_b = f"tenant_b_{uuid.uuid4().hex[:6]}@example.com"
        user_b = User(email=email_b, role='subscriber')
        db.add(user_b)
        db.flush()
        sub_b = Subscription(user_id=user_b.id, plan_tier='free', article_credits_limit=3, article_credits_used=0)
        db.add(sub_b)
        db.commit()

        # Simulate Midtrans payment webhook for User A to 'pro'
        order_id = f"BAP-{user_a.id[:8]}-PRO-999999"
        webhook_event = {
            'order_id': order_id,
            'status_code': '200',
            'gross_amount': '249000',
            'transaction_status': 'settlement',
            'fraud_status': 'accept',
            'custom_field1': user_a.id,
            'custom_field2': 'pro'
        }

        res = handle_midtrans_webhook(webhook_event, db)
        assert res['success'] is True, f"Webhook failed: {res}"

        # Refresh objects
        db.refresh(sub_a)
        db.refresh(sub_b)

        # User A MUST be upgraded to pro (120 credits)
        assert sub_a.plan_tier == 'pro', f"Expected User A to be pro, got {sub_a.plan_tier}"
        assert sub_a.article_credits_limit == 120, f"Expected 120 credits, got {sub_a.article_credits_limit}"

        # User B MUST NOT be modified at all (still free with 3 credits)
        assert sub_b.plan_tier == 'free', f"Expected User B to be free, got {sub_b.plan_tier}"
        assert sub_b.article_credits_limit == 3, f"Expected 3 credits, got {sub_b.article_credits_limit}"

        print("✓ Multi-tenant isolation verified: User A was upgraded to PRO (120 credits), User B remained on FREE (3 credits).")
        print("✓ Midtrans webhook targeting verified: 0 leakages.")
    finally:
        db.close()

if __name__ == '__main__':
    test_tenant_isolation()
