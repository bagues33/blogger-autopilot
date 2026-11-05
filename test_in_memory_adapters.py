"""
Test Suite for External Seams & In-Memory Adapters
Verifies that Blogger, Midtrans, and Notification seams have real, testable in-memory adapters.
"""

from blogger_client import (
    BaseBloggerAdapter,
    InMemoryBloggerAdapter,
    GoogleBloggerLiveAdapter,
    get_blogger_adapter,
    set_blogger_adapter,
    create_post,
    update_post,
    get_post,
    fetch_blogger_posts_sync,
    delete_post
)
from midtrans_service import (
    BasePaymentGatewayAdapter,
    InMemoryPaymentAdapter,
    MidtransLiveAdapter,
    get_payment_adapter,
    set_payment_adapter,
    create_snap_transaction,
    verify_signature
)
from notification_service import (
    BaseNotificationAdapter,
    InMemoryNotificationAdapter,
    LiveNetworkNotificationAdapter,
    get_notification_adapter,
    set_notification_adapter,
    send_telegram_message,
    send_webhook_event,
    dispatch_notification
)
from models_saas import User

def test_blogger_in_memory_adapter():
    print("--- 1. Testing Blogger Seam & InMemoryBloggerAdapter ---")
    mock_adapter = InMemoryBloggerAdapter()
    set_blogger_adapter(mock_adapter)

    # 1. Create post
    post = create_post(
        title="Testing In Memory Blogger Adapter",
        content_html="<p>Konten artikel pengujian adapter in-memory.</p>",
        labels="Test, Architecture, Seam",
        is_draft=False,
        blog_id="mock_blog_123"
    )
    assert post['id'] is not None
    assert post['title'] == "Testing In Memory Blogger Adapter"
    assert post['status'] == 'LIVE'
    post_id = post['id']
    print(f"✓ Created mock post: ID={post_id}, URL={post['url']}")

    # 2. Fetch posts
    posts = fetch_blogger_posts_sync(blog_id="mock_blog_123")
    assert len(posts) == 1
    assert posts[0]['id'] == post_id
    print("✓ Fetched posts from in-memory adapter successfully.")

    # 3. Update post
    updated = update_post(
        post_id=post_id,
        title="Updated Title Post",
        content_html="<p>Updated content.</p>",
        blog_id="mock_blog_123"
    )
    assert updated['title'] == "Updated Title Post"
    print("✓ Updated post in-memory successfully.")

    # 4. Get post
    fetched = get_post(post_id, blog_id="mock_blog_123")
    assert fetched['title'] == "Updated Title Post"
    print("✓ Retrieved post in-memory successfully.")

    # 5. Delete post
    delete_post(post_id, blog_id="mock_blog_123")
    remaining = fetch_blogger_posts_sync(blog_id="mock_blog_123")
    assert len(remaining) == 0
    print("✓ Deleted post from in-memory adapter successfully.")

def test_payment_in_memory_adapter():
    print("--- 2. Testing Payment Gateway Seam & InMemoryPaymentAdapter ---")
    mock_adapter = InMemoryPaymentAdapter()
    set_payment_adapter(mock_adapter)

    mock_user = User(
        id="usr-mock-12345",
        email="test_subscriber@example.id",
        full_name="Subscriber Test"
    )

    # 1. Create Snap transaction
    res = create_snap_transaction(user=mock_user, plan_tier="starter")
    assert res['success'] is True
    assert 'MOCK_SNAP_TOKEN' in res['token']
    assert res['amount'] == 99000
    print(f"✓ Created mock Snap transaction: OrderID={res['order_id']}, Token={res['token']}")

    # 2. Verify signature
    is_valid = verify_signature(
        order_id=res['order_id'],
        status_code="200",
        gross_amount="99000",
        signature_key="MOCK_SIGNATURE"
    )
    assert is_valid is True
    print("✓ Verified signature with InMemoryPaymentAdapter successfully.")

def test_notification_in_memory_adapter():
    print("--- 3. Testing Notification Seam & InMemoryNotificationAdapter ---")
    mock_adapter = InMemoryNotificationAdapter()
    set_notification_adapter(mock_adapter)

    # 1. Send Telegram message
    res_tg = send_telegram_message("test_bot_token", "12345678", "<b>Test Message</b>")
    assert res_tg['success'] is True
    assert len(mock_adapter.sent_telegrams) == 1
    assert mock_adapter.sent_telegrams[0]['chat_id'] == "12345678"
    print("✓ Captured Telegram notification in-memory successfully.")

    # 2. Send Webhook event
    res_wh = send_webhook_event("https://webhook.site/mock-test", "article_published", {"title": "Test Title"})
    assert res_wh['success'] is True
    assert len(mock_adapter.sent_webhooks) == 1
    assert mock_adapter.sent_webhooks[0]['event_type'] == "article_published"
    print("✓ Captured Webhook event in-memory successfully.")

if __name__ == '__main__':
    test_blogger_in_memory_adapter()
    test_payment_in_memory_adapter()
    test_notification_in_memory_adapter()
    print("\n🎉 ALL EXTERNAL SEAMS & IN-MEMORY TEST ADAPTERS VERIFIED 100%!")
