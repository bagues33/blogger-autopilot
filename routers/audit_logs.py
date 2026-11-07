"""
Enterprise Audit Logging Router for Blogger Auto-Pilot SaaS
Provides tenants and agency teams access to compliance activity trails.
"""

import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc

from db_saas import get_saas_db
from models_saas import User, AuditLog, WorkspaceMembership
from dependencies import get_session_user

router = APIRouter(tags=["Audit Logs"])

@router.get('/api/audit-logs')
def get_audit_logs(
    request: Request,
    workspace_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_saas_db)
):
    user = get_session_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Sesi telah berakhir. Silakan login kembali.")

    query = db.query(AuditLog)

    if workspace_id:
        # Verify user is a member of this workspace
        membership = db.query(WorkspaceMembership).filter(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user.id
        ).first()
        if not membership and user.role != 'admin':
            raise HTTPException(status_code=403, detail="Akses ditolak: Anda bukan anggota workspace ini.")
        query = query.filter(AuditLog.workspace_id == workspace_id)
    else:
        query = query.filter(AuditLog.user_id == user.id)

    if event_type:
        query = query.filter(AuditLog.event_type == event_type)

    total_count = query.count()
    logs = query.order_by(desc(AuditLog.created_at)).offset(offset).limit(limit).all()

    results = []
    for l in logs:
        meta = {}
        if l.metadata_json:
            try:
                meta = json.loads(l.metadata_json)
            except Exception:
                meta = {"raw": l.metadata_json}
        results.append({
            "id": l.id,
            "event_type": l.event_type,
            "entity_id": l.entity_id,
            "metadata": meta,
            "ip_address": l.ip_address,
            "created_at": l.created_at.isoformat() if l.created_at else None
        })

    return {
        "success": True,
        "total": total_count,
        "count": len(results),
        "logs": results
    }
