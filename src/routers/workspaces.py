"""
Workspace & Team RBAC Router for Blogger Auto-Pilot SaaS
Supports organizational team collaboration, client management, granular blog assignments,
shared credit pool telemetry, audit logging, and role-based permissions: Owner, Admin, Editor, Writer, Viewer.
"""

from typing import Optional, List
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.core.database import get_saas_db
from src.models.models import User, Workspace, WorkspaceMembership, WorkspaceBlogAssignment, Blog
from src.core.dependencies import get_current_user, check_feature_access
from src.services.audit import record_audit_log

router = APIRouter(prefix="/api/workspaces", tags=["Workspaces & RBAC"])

class WorkspaceCreateReq(BaseModel):
    name: str

class MemberAddReq(BaseModel):
    email: str
    role: str = "writer" # admin, editor, writer, viewer
    assigned_blog_ids: Optional[List[str]] = None

class MemberUpdateRoleReq(BaseModel):
    role: str

class MemberBlogsUpdateReq(BaseModel):
    assigned_blog_ids: List[str]

@router.get("")
def api_get_workspaces(user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    # Workspaces owned
    owned = db.query(Workspace).filter(Workspace.owner_id == user.id).all()
    # Memberships
    memberships = db.query(WorkspaceMembership).filter(WorkspaceMembership.user_id == user.id).all()

    result = []
    seen_ids = set()

    for w in owned:
        seen_ids.add(w.id)
        result.append({
            "id": w.id,
            "name": w.name,
            "role": "owner",
            "is_owner": True,
            "created_at": w.created_at.isoformat() if w.created_at else None,
            "member_count": len(w.memberships) + 1
        })

    for m in memberships:
        if m.workspace_id not in seen_ids and m.workspace:
            seen_ids.add(m.workspace_id)
            result.append({
                "id": m.workspace.id,
                "name": m.workspace.name,
                "role": m.role,
                "is_owner": False,
                "created_at": m.workspace.created_at.isoformat() if m.workspace.created_at else None,
                "member_count": len(m.workspace.memberships) + 1
            })

    return {"success": True, "workspaces": result}

@router.post("")
def api_create_workspace(req: WorkspaceCreateReq, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    if not check_feature_access(user, 'workspaces'):
        raise HTTPException(
            status_code=403,
            detail="Fitur Multi-Workspace dan Kolaborasi Tim memerlukan paket Agency & Media Network. Silakan upgrade paket Anda."
        )

    clean_name = req.name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Nama workspace tidak boleh kosong.")

    ws = Workspace(
        name=clean_name,
        owner_id=user.id
    )
    db.add(ws)
    db.commit()
    db.refresh(ws)

    record_audit_log(
        db=db,
        event_type="workspace.created",
        user_id=user.id,
        workspace_id=ws.id,
        entity_id=ws.id,
        metadata={"name": ws.name},
        ip_address=request.client.host if request and request.client else None
    )

    return {
        "success": True,
        "workspace": {
            "id": ws.id,
            "name": ws.name,
            "owner_id": ws.owner_id,
            "created_at": ws.created_at.isoformat() if ws.created_at else None
        }
    }

@router.get("/{workspace_id}/available-blogs")
def api_get_workspace_available_blogs(workspace_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace tidak ditemukan.")

    if ws.owner_id != user.id and user.role != 'admin':
        raise HTTPException(status_code=403, detail="Hanya pemilik workspace yang dapat melihat daftar blog.")

    blogs = db.query(Blog).filter(Blog.user_id == ws.owner_id).all()
    return {
        "success": True,
        "blogs": [{"id": b.id, "name": b.name, "url": b.url} for b in blogs]
    }

@router.get("/{workspace_id}/members")
def api_get_workspace_members(workspace_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace tidak ditemukan.")

    is_owner = (ws.owner_id == user.id)
    membership = db.query(WorkspaceMembership).filter(
        WorkspaceMembership.workspace_id == workspace_id,
        WorkspaceMembership.user_id == user.id
    ).first()

    if not is_owner and not membership and user.role != 'admin':
        raise HTTPException(status_code=403, detail="Anda bukan anggota workspace ini.")

    members = []
    # Add owner
    owner_user = db.query(User).filter(User.id == ws.owner_id).first()
    shared_used = 0
    shared_limit = 600
    if owner_user:
        if owner_user.subscription:
            shared_used = owner_user.subscription.article_credits_used
            shared_limit = owner_user.subscription.article_credits_limit
        members.append({
            "user_id": owner_user.id,
            "email": owner_user.email,
            "full_name": owner_user.full_name or owner_user.email.split('@')[0],
            "role": "owner",
            "is_owner": True,
            "assigned_blogs": []
        })

    # Add other members
    for m in ws.memberships:
        if m.user_id != ws.owner_id and m.user:
            assigned = []
            for a in m.blog_assignments:
                if a.blog:
                    assigned.append({"id": a.blog.id, "name": a.blog.name})

            members.append({
                "user_id": m.user.id,
                "membership_id": m.id,
                "email": m.user.email,
                "full_name": m.user.full_name or m.user.email.split('@')[0],
                "role": m.role,
                "is_owner": False,
                "assigned_blogs": assigned
            })

    return {
        "success": True,
        "workspace_name": ws.name,
        "is_current_user_owner": bool(is_owner or user.role == 'admin'),
        "shared_credits_used": shared_used,
        "shared_credits_limit": shared_limit,
        "members": members
    }

@router.post("/{workspace_id}/members")
def api_add_workspace_member(workspace_id: str, req: MemberAddReq, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace tidak ditemukan.")

    if ws.owner_id != user.id and user.role != 'admin':
        raise HTTPException(status_code=403, detail="Hanya pemilik workspace yang dapat mengundang anggota tim.")

    if not check_feature_access(user, 'workspaces'):
        raise HTTPException(
            status_code=403,
            detail="Undangan anggota tim memerlukan paket Agency & Media Network aktif. Silakan upgrade paket Anda."
        )

    clean_email = req.email.strip().lower()
    target_user = db.query(User).filter(User.email == clean_email).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"Pengguna dengan email '{clean_email}' belum terdaftar di platform.")

    if target_user.id == ws.owner_id:
        raise HTTPException(status_code=400, detail="Pengguna adalah pemilik workspace.")

    existing_m = db.query(WorkspaceMembership).filter(
        WorkspaceMembership.workspace_id == workspace_id,
        WorkspaceMembership.user_id == target_user.id
    ).first()

    valid_roles = ['admin', 'editor', 'writer', 'viewer']
    clean_role = req.role.lower().strip()
    if clean_role not in valid_roles:
        clean_role = 'writer'

    if existing_m:
        existing_m.role = clean_role
        m_obj = existing_m
    else:
        new_m = WorkspaceMembership(
            workspace_id=workspace_id,
            user_id=target_user.id,
            role=clean_role
        )
        db.add(new_m)
        db.flush()
        m_obj = new_m

    assigned_ids = []
    if req.assigned_blog_ids is not None:
        db.query(WorkspaceBlogAssignment).filter(
            WorkspaceBlogAssignment.membership_id == m_obj.id
        ).delete()

        for b_id in req.assigned_blog_ids:
            valid_b = db.query(Blog).filter(Blog.id == b_id, Blog.user_id == ws.owner_id).first()
            if valid_b:
                assign = WorkspaceBlogAssignment(
                    membership_id=m_obj.id,
                    blog_id=valid_b.id
                )
                db.add(assign)
                assigned_ids.append(valid_b.id)

    db.commit()

    record_audit_log(
        db=db,
        event_type="member.added",
        user_id=user.id,
        workspace_id=ws.id,
        entity_id=target_user.id,
        metadata={"email": clean_email, "role": clean_role, "assigned_blogs": assigned_ids},
        ip_address=request.client.host if request and request.client else None
    )

    return {"success": True, "message": f"Anggota {clean_email} berhasil ditambahkan dengan peran '{clean_role}'."}

@router.post("/{workspace_id}/members/{member_user_id}/blogs")
def api_update_member_blogs(workspace_id: str, member_user_id: str, req: MemberBlogsUpdateReq, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace tidak ditemukan.")

    if ws.owner_id != user.id and user.role != 'admin':
        raise HTTPException(status_code=403, detail="Hanya pemilik workspace yang dapat mengubah pembagian blog.")

    membership = db.query(WorkspaceMembership).filter(
        WorkspaceMembership.workspace_id == workspace_id,
        WorkspaceMembership.user_id == member_user_id
    ).first()

    if not membership:
        raise HTTPException(status_code=404, detail="Anggota tidak ditemukan di workspace ini.")

    db.query(WorkspaceBlogAssignment).filter(
        WorkspaceBlogAssignment.membership_id == membership.id
    ).delete()

    assigned_ids = []
    for b_id in req.assigned_blog_ids:
        valid_b = db.query(Blog).filter(Blog.id == b_id, Blog.user_id == ws.owner_id).first()
        if valid_b:
            assign = WorkspaceBlogAssignment(
                membership_id=membership.id,
                blog_id=valid_b.id
            )
            db.add(assign)
            assigned_ids.append(valid_b.id)

    db.commit()

    record_audit_log(
        db=db,
        event_type="member.blogs_updated",
        user_id=user.id,
        workspace_id=ws.id,
        entity_id=member_user_id,
        metadata={"assigned_blogs": assigned_ids},
        ip_address=request.client.host if request and request.client else None
    )

    return {"success": True, "message": "Pembagian blog anggota berhasil diperbarui."}

@router.delete("/{workspace_id}/members/{member_user_id}")
def api_remove_workspace_member(workspace_id: str, member_user_id: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace tidak ditemukan.")

    if ws.owner_id != user.id and user.role != 'admin' and user.id != member_user_id:
        raise HTTPException(status_code=403, detail="Tidak memiliki akses untuk menghapus anggota.")

    membership = db.query(WorkspaceMembership).filter(
        WorkspaceMembership.workspace_id == workspace_id,
        WorkspaceMembership.user_id == member_user_id
    ).first()

    if not membership:
        raise HTTPException(status_code=404, detail="Anggota tidak ditemukan di workspace ini.")

    removed_role = membership.role
    db.delete(membership)
    db.commit()

    record_audit_log(
        db=db,
        event_type="member.removed",
        user_id=user.id,
        workspace_id=ws.id,
        entity_id=member_user_id,
        metadata={"removed_role": removed_role},
        ip_address=request.client.host if request and request.client else None
    )

    return {"success": True, "message": "Anggota berhasil dihapus dari workspace."}
