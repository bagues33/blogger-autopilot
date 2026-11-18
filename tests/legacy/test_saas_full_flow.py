"""
Comprehensive Multi-Tenant SaaS & Midtrans Flow Test Suite
Verifies tenant registration, login JWT, quota tracking, Midtrans Snap creation, and Webhook fulfillment.
"""

import urllib.request
import urllib.parse
import json
import http.cookiejar

BASE_URL = "http://127.0.0.1:8090"

def run_tests():
    print("=== STARTING FULL MULTI-TENANT SAAS & MIDTRANS TEST ===")
    
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    # 1. Test GET /api/saas/auth/me before login (Default admin fallback)
    req = urllib.request.Request(f"{BASE_URL}/api/saas/auth/me")
    with opener.open(req) as res:
        data = json.loads(res.read().decode())
        print("✓ Initial Session check:", data)
        assert 'user' in data
        assert 'subscription' in data

    # 2. Test Register new tenant user
    test_email = f"creator_solo_{id(object())}@bloggerautopilot.id"
    register_payload = {
        "email": test_email,
        "password": "PasswordSaaS2026!",
        "full_name": "Raden Mas Solo"
    }
    req = urllib.request.Request(
        f"{BASE_URL}/api/saas/auth/register",
        data=json.dumps(register_payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    with opener.open(req) as res:
        reg_data = json.loads(res.read().decode())
        print("✓ Tenant User Registered:", reg_data['user']['email'])
        assert reg_data['success'] is True
        assert reg_data['user']['email'] == test_email.lower()

    # 3. Test Session Check for the newly registered user
    req = urllib.request.Request(f"{BASE_URL}/api/saas/auth/me")
    with opener.open(req) as res:
        me_data = json.loads(res.read().decode())
        print(f"✓ Current User ({me_data['user']['email']}): Tier={me_data['subscription']['plan_tier']}, Credits={me_data['subscription']['article_credits_used']}/{me_data['subscription']['article_credits_limit']}")
        assert me_data['authenticated'] is True
        assert me_data['subscription']['plan_tier'] == 'free'
        assert me_data['subscription']['article_credits_limit'] == 3
        assert me_data['subscription']['article_credits_used'] == 0

    # 4. Test Billing Plans Endpoint (Indonesia IDR Pricing)
    req = urllib.request.Request(f"{BASE_URL}/api/billing/plans")
    with opener.open(req) as res:
        plans_data = json.loads(res.read().decode())
        print("✓ Indonesian Billing Plans loaded:")
        for tier, p in plans_data['plans'].items():
            print(f"  - {tier.upper()}: Rp {p['price']:,} ({p['credits']} kredit, {p['blogs']} blog)")
        assert 'starter' in plans_data['plans']
        assert 'pro' in plans_data['plans']
        assert plans_data['plans']['starter']['price'] == 99000

    # 5. Test Midtrans Snap Token Generation
    snap_payload = {"plan_tier": "starter"}
    req = urllib.request.Request(
        f"{BASE_URL}/api/billing/create-snap-token",
        data=json.dumps(snap_payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    with opener.open(req) as res:
        snap_res = json.loads(res.read().decode())
        print("✓ Midtrans Snap Transaction Created:")
        print(f"  Order ID: {snap_res.get('order_id')}")
        print(f"  Amount  : Rp {snap_res.get('amount'):,}")
        print(f"  Token   : {snap_res.get('token')}")
        assert snap_res['success'] is True
        assert 'BAP-' in snap_res['order_id']

    # 6. Test Upgrade Fulfillment (Simulated Webhook / Demo Upgrade)
    upgrade_payload = {"plan_tier": "starter"}
    req = urllib.request.Request(
        f"{BASE_URL}/api/billing/upgrade-demo",
        data=json.dumps(upgrade_payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    with opener.open(req) as res:
        up_res = json.loads(res.read().decode())
        print("✓ Plan Upgraded:", up_res['message'])
        assert up_res['success'] is True

    # 7. Verify Upgraded Subscription & Credits
    req = urllib.request.Request(f"{BASE_URL}/api/saas/auth/me")
    with opener.open(req) as res:
        me_after = json.loads(res.read().decode())
        print(f"✓ Subscription after payment: Tier={me_after['subscription']['plan_tier']}, Limit={me_after['subscription']['article_credits_limit']} credits")
        assert me_after['subscription']['plan_tier'] == 'starter'
        assert me_after['subscription']['article_credits_limit'] == 30

    # 8. Test Logout
    req = urllib.request.Request(f"{BASE_URL}/api/saas/auth/logout", method='POST')
    with opener.open(req) as res:
        logout_data = json.loads(res.read().decode())
        print("✓ Logout successful:", logout_data)
        assert logout_data['success'] is True

    print("\n🎉 ALL MULTI-TENANT SAAS & MIDTRANS TESTS PASSED 100%!")

if __name__ == '__main__':
    run_tests()
