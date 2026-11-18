"""
Integration tests for Superadmin Master Console & RBAC Guard.
"""
import pytest
from fastapi.testclient import TestClient

def test_admin_metrics_and_tenants(admin_client: TestClient):
    # 1. Superadmin can fetch metrics
    res_metrics = admin_client.get("/api/admin/metrics")
    assert res_metrics.status_code == 200
    metrics = res_metrics.json()
    assert "total_tenants" in metrics
    assert "mrr_idr" in metrics
    assert "tier_breakdown" in metrics

    # 2. Superadmin can list tenants
    res_tenants = admin_client.get("/api/admin/tenants")
    assert res_tenants.status_code == 200
    tenants = res_tenants.json()
    assert "tenants" in tenants
    assert tenants["count"] >= 1

def test_non_admin_forbidden(tenant_factory):
    client_sub, user_sub = tenant_factory(role="subscriber")

    # Regular subscriber attempting to access admin endpoints MUST receive 403 Forbidden
    res_metrics = client_sub.get("/api/admin/metrics")
    assert res_metrics.status_code == 403
    assert "administrator" in res_metrics.json()["detail"].lower()

    res_tenants = client_sub.get("/api/admin/tenants")
    assert res_tenants.status_code == 403
