"""
Workspace & Team RBAC Router for Blogger Auto-Pilot SaaS
Supports organizational team collaboration, client management, and role-based permissions:
Owner, Admin, Editor, Writer, Viewer.
"""

from typing import Optional, List
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db_saas import get_saas_db
from models_saas import User, Workspace, WorkspaceMembership
from dependencies import get_session_user, get_or_create_default_admin

router = APIRouter(prefix="/api/workspaces", tags=["Workspaces & RBAC"])

class WorkspaceCreateReq(BaseModel):
    name: str

class MemberAddReq(BaseModel):
    email: str
    role: str = "writer" # admin, editor, writer, viewer

class MemberUpdateRoleReq(BaseModel):
    role: str

@router.get("")
def api_get_workspaces(request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    
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
def api_create_workspace(req: WorkspaceCreateReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    clean_name = req.name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Nama workspace tidak boleh kosong.")

    # Check plan tier blog / workspace limits if applicable
    ws = Workspace(
        name=clean_name,
        owner_id=user.id
    )
    db.add(ws)
    db.commit()
    db.refresh(ws)

    return {
        "success": True,
        "workspace": {
            "id": ws.id,
            "name": ws.name,
            "owner_id": ws.owner_id,
            "created_at": ws.created_at.isoformat() if ws.created_at else None
        }
    }

@router.get("/{workspace_id}/members")
def api_get_workspace_members(workspace_id: str, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace tidak ditemukan.")

    # Check membership
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
    if owner_user:
        members.append({
            "user_id": owner_user.id,
            "email": owner_user.email,
            "full_name": owner_user.full_name or owner_user.email.split('@')[0],
            "role": "owner",
            "is_owner": True
        })

    # Add other members
    for m in ws.memberships:
        if m.user_id != ws.owner_id and m.user:
            members.append({
                "user_id": m.user.id,
                "email": m.user.email,
                "full_name": m.user.full_name or m.user.email.split('@')[0],
                "role": m.role,
                "is_owner": False
            })

    return {"success": True, "workspace_name": ws.name, "members": members}

@router.post("/{workspace_id}/members")
def api_add_workspace_member(workspace_id: str, req: MemberAddReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace tidak ditemukan.")

    if ws.owner_id != user.id and user.role != 'admin':
        raise HTTPException(status_code=403, detail="Hanya pemilik workspace yang dapat mengundang anggota tim.")

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
    else:
        new_m = WorkspaceMembership(
            workspace_id=workspace_id,
            user_id=target_user.id,
            role=clean_role
        )
        db.add(new_m)

    db.commit()
    return {"success": True, "message": f"Anggota {clean_email} berhasil ditambahkan dengan peran '{clean_role}'."}

@router.delete("/{workspace_id}/members/{member_user_id}")
def api_remove_workspace_member(workspace_id: str, member_user_id: str, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
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

    db.delete(membership)
    db.commit()
    return {"success": True, "message": "Anggota berhasil dihapus dari workspace."}
