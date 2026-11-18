"""
End-to-End Multi-Tenant Isolation & Plan Limits Verification Suite
Proves complete isolation across Blogs, Articles, and Keywords between multiple tenants.
"""

import urllib.request
import urllib.parse
import json
import http.cookiejar
import uuid

BASE_URL = "http://127.0.0.1:8090"

def create_tenant_session(email, password, name):
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    reg_payload = {"email": email, "password": password, "full_name": name}
    req = urllib.request.Request(
        f"{BASE_URL}/api/saas/auth/register",
        data=json.dumps(reg_payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    with opener.open(req) as res:
        data = json.loads(res.read().decode())
    return opener, data['user']['id']

def run_tests():
    print("=== STARTING FULL END-TO-END MULTI-TENANT ISOLATION TESTS ===")

    # 1. Register Tenant A
    uid_a_str = uuid.uuid4().hex[:6]
    email_a = f"alice_{uid_a_str}@saas.id"
    opener_a, user_a_id = create_tenant_session(email_a, "AlicePass123!", "Alice SaaS")
    print(f"✓ Tenant A Created: {email_a}")

    # 2. Register Tenant B
    uid_b_str = uuid.uuid4().hex[:6]
    email_b = f"bob_{uid_b_str}@saas.id"
    opener_b, user_b_id = create_tenant_session(email_b, "BobPass123!", "Bob SaaS")
    print(f"✓ Tenant B Created: {email_b}")

    # 3. Tenant A adds a Blog
    blog_a_id = f"blog_alice_{uid_a_str}"
    add_blog_payload = {
        "id": blog_a_id,
        "name": "Alice Tech Blog",
        "url": "https://alice.blogspot.com",
        "account_name": "Alice Google"
    }
    req = urllib.request.Request(
        f"{BASE_URL}/api/blogs/add",
        data=json.dumps(add_blog_payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    with opener_a.open(req) as res:
        res_data = json.loads(res.read().decode())
        assert res_data['success'] is True
    print(f"✓ Tenant A added blog: '{blog_a_id}'")

    # 4. Tenant A adds a Keyword
    add_kw_payload = {
        "keyword": "tips seo autopilot alice",
        "search_intent": "Informational",
        "blog_id": blog_a_id
    }
    req = urllib.request.Request(
        f"{BASE_URL}/api/keywords/add",
        data=json.dumps(add_kw_payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    with opener_a.open(req) as res:
        res_data = json.loads(res.read().decode())
        assert res_data['success'] is True
    print("✓ Tenant A added keyword: 'tips seo autopilot alice'")

    # 5. Tenant A saves an Article
    save_art_payload = {
        "title": "Panduan SEO Modern Alice 2026",
        "target_keyword": "tips seo autopilot alice",
        "content_html": "<p>Halo dari draf privat Alice.</p>",
        "blog_id": blog_a_id
    }
    req = urllib.request.Request(
        f"{BASE_URL}/api/articles/save",
        data=json.dumps(save_art_payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    with opener_a.open(req) as res:
        res_data = json.loads(res.read().decode())
        assert res_data['success'] is True
    print("✓ Tenant A saved draft article")

    # 6. Tenant B inspects Blogs: MUST BE EMPTY!
    req = urllib.request.Request(f"{BASE_URL}/api/blogs")
    with opener_b.open(req) as res:
        blogs_b = json.loads(res.read().decode())
        print(f"✓ Tenant B Blogs count: {len(blogs_b)} (Must be 0)")
        assert len(blogs_b) == 0, f"Leakage! Tenant B saw blogs: {blogs_b}"

    # 7. Tenant B inspects Articles: MUST BE EMPTY!
    req = urllib.request.Request(f"{BASE_URL}/api/articles?blog_id={blog_a_id}")
    with opener_b.open(req) as res:
        arts_b = json.loads(res.read().decode())
        print(f"✓ Tenant B Articles count: {len(arts_b)} (Must be 0)")
        assert len(arts_b) == 0, f"Leakage! Tenant B saw articles: {arts_b}"

    # 8. Tenant B inspects Keywords: MUST BE EMPTY!
    req = urllib.request.Request(f"{BASE_URL}/api/keywords?blog_id={blog_a_id}")
    with opener_b.open(req) as res:
        kws_b = json.loads(res.read().decode())
        print(f"✓ Tenant B Keywords count: {len(kws_b)} (Must be 0)")
        assert len(kws_b) == 0, f"Leakage! Tenant B saw keywords: {kws_b}"

    # 9. Tenant B attempts to delete Tenant A's blog: MUST FAIL (404)!
    req = urllib.request.Request(f"{BASE_URL}/api/blogs/{blog_a_id}/delete", data=b'', method='POST')
    try:
        with opener_b.open(req) as res:
            assert False, "Security violation: Tenant B was able to delete Tenant A's blog!"
    except urllib.error.HTTPError as he:
        assert he.code == 404
        print("✓ Security verified: Tenant B cannot delete Tenant A's blog (HTTP 404).")

    # 10. Test Free Plan Limit: Free user cannot add more than 1 blog
    blog_b_1 = f"blog_bob_1_{uid_b_str}"
    req = urllib.request.Request(
        f"{BASE_URL}/api/blogs/add",
        data=json.dumps({"id": blog_b_1, "name": "Bob Blog 1"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with opener_b.open(req) as res:
        assert json.loads(res.read().decode())['success'] is True
    print("✓ Tenant B successfully added 1st blog (Free quota limit: 1).")

    blog_b_2 = f"blog_bob_2_{uid_b_str}"
    req2 = urllib.request.Request(
        f"{BASE_URL}/api/blogs/add",
        data=json.dumps({"id": blog_b_2, "name": "Bob Blog 2"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    try:
        with opener_b.open(req2) as res:
            assert False, "Quota violation: Free user exceeded 1 blog limit!"
    except urllib.error.HTTPError as he:
        assert he.code == 400
        print("✓ Quota limit verified: Free user attempting to add 2nd blog rejected with HTTP 400.")

    # 11. Test Scheduler Status
    req = urllib.request.Request(f"{BASE_URL}/api/saas/scheduler/status")
    with opener_a.open(req) as res:
        sched_data = json.loads(res.read().decode())
        print(f"✓ Autopilot Scheduler status: {sched_data['status']} ({sched_data['message']})")
        assert sched_data['status'] == 'ready'

    print("\n🎉 ALL E2E MULTI-TENANT ISOLATION & PLAN LIMIT TESTS PASSED 100%!")

if __name__ == '__main__':
    run_tests()
