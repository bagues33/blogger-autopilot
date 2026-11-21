"""
Integration tests for Superadmin Master Console, Security Locks, Workspaces Monitor,
Accurate MRR Calculation, Global Audit Trail, and RBAC Guard.
"""
import pytest
from fastapi.testclient import TestClient

def test_admin_metrics_and_tenants(admin_client: TestClient):
    # 1. Superadmin can fetch metrics including workspaces count
    res_metrics = admin_client.get("/api/admin/metrics")
    assert res_metrics.status_code == 200
    metrics = res_metrics.json()
    assert "total_tenants" in metrics
    assert "mrr_idr" in metrics
    assert "tier_breakdown" in metrics
    assert "total_workspaces" in metrics
    assert "total_team_members" in metrics

    # 2. Superadmin can list tenants
    res_tenants = admin_client.get("/api/admin/tenants")
    assert res_tenants.status_code == 200
    tenants = res_tenants.json()
    assert "tenants" in tenants
    assert tenants["count"] >= 1

    # 3. Superadmin can access scheduler status, workspaces monitor & global audit trail
    res_sched = admin_client.get("/api/saas/scheduler/status")
    assert res_sched.status_code == 200
    assert res_sched.json()["status"] == "ready"

    res_ws = admin_client.get("/api/admin/workspaces")
    assert res_ws.status_code == 200
    assert res_ws.json()["success"] is True

    res_audit = admin_client.get("/api/admin/audit-logs")
    assert res_audit.status_code == 200
    assert res_audit.json()["success"] is True

def test_non_admin_forbidden(client: TestClient, tenant_factory):
    # Unauthenticated guest MUST be rejected from scheduler status
    res_guest_sched = client.get("/api/saas/scheduler/status")
    assert res_guest_sched.status_code == 401

    client_sub, user_sub = tenant_factory(role="subscriber")

    # Regular subscriber attempting to access admin endpoints MUST receive 403 Forbidden
    for path in [
        "/api/admin/metrics",
        "/api/admin/tenants",
        "/api/admin/workspaces",
        "/api/admin/audit-logs",
        "/api/saas/scheduler/status"
    ]:
        res = client_sub.get(path)
        assert res.status_code == 403, f"Expected 403 on {path}, got {res.status_code}"

def test_admin_mutations_audit_logs_and_mrr_exclusion(admin_client: TestClient, tenant_factory):
    client_sub, user_sub = tenant_factory(plan="free", role="subscriber", name="MRR Test Tenant")

    mrr_before = admin_client.get("/api/admin/metrics").json()["mrr_idr"]

    # 1. Admin upgrades tenant to Pro (+349,000 MRR)
    res_plan = admin_client.post(f"/api/admin/tenants/{user_sub.id}/plan", json={"plan_tier": "pro"})
    assert res_plan.status_code == 200
    mrr_after_pro = admin_client.get("/api/admin/metrics").json()["mrr_idr"]
    assert mrr_after_pro == mrr_before + 349000

    # 2. Admin adds credits + resets password
    res_cred = admin_client.post(f"/api/admin/tenants/{user_sub.id}/credits", json={"amount": 25})
    assert res_cred.status_code == 200
    res_pw = admin_client.post(f"/api/admin/tenants/{user_sub.id}/reset-password", json={"new_password": "NewSecure2026!"})
    assert res_pw.status_code == 200

    # 3. Admin suspends tenant -> MUST be excluded from active MRR!
    res_susp = admin_client.post(f"/api/admin/tenants/{user_sub.id}/toggle-status")
    assert res_susp.status_code == 200
    assert res_susp.json()["is_active"] is False

    mrr_after_suspend = admin_client.get("/api/admin/metrics").json()["mrr_idr"]
    assert mrr_after_suspend == mrr_before

    # 4. Verify all 4 admin actions appear in Global Audit Trail
    res_audit = admin_client.get("/api/admin/audit-logs?limit=20")
    assert res_audit.status_code == 200
    events = {l["event_type"] for l in res_audit.json()["logs"]}
    assert "admin.plan_changed" in events
    assert "admin.credits_added" in events
    assert "admin.password_reset" in events
    assert "admin.status_toggled" in events

def test_multi_admin_role_promotion_and_self_lockout_guard(admin_client: TestClient, tenant_factory):
    client_staff, user_staff = tenant_factory(plan="free", role="subscriber", name="Ops Staff")

    # Initially staff gets 403 on admin endpoints
    assert client_staff.get("/api/admin/metrics").status_code == 403

    # 1. Primary admin promotes staff to 'admin'
    res_prom = admin_client.post(f"/api/admin/tenants/{user_staff.id}/role", json={"role": "admin"})
    assert res_prom.status_code == 200
    assert res_prom.json()["role"] == "admin"

    # 2. Newly promoted admin CAN now access Admin Console!
    assert client_staff.get("/api/admin/metrics").status_code == 200

    # 3. Self-lockout guard: staff admin CANNOT demote themselves
    res_self = client_staff.post(f"/api/admin/tenants/{user_staff.id}/role", json={"role": "subscriber"})
    assert res_self.status_code == 400
    assert "sendiri" in res_self.json()["detail"].lower()

    # 4. Primary admin demotes staff back to 'subscriber' -> immediately loses admin access
    res_dem = admin_client.post(f"/api/admin/tenants/{user_staff.id}/role", json={"role": "subscriber"})
    assert res_dem.status_code == 200
    assert res_dem.json()["role"] == "subscriber"
    assert client_staff.get("/api/admin/metrics").status_code == 403

    # 5. Verify role change logged in audit trail
    events = {l["event_type"] for l in admin_client.get("/api/admin/audit-logs?limit=20").json()["logs"]}
    assert "admin.role_changed" in events
