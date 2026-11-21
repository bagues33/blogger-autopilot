"""
Role-Based Access Control (RBAC) & Permission Engine for Blogger Auto-Pilot SaaS
Supports contextual workspace-scoped roles, granular blog assignments, and atomic capability checks.
"""

from enum import Enum
from typing import Set, List, Optional
from sqlalchemy.orm import Session
from src.models.models import User, Blog, Workspace, WorkspaceMembership, WorkspaceBlogAssignment, Article

class Permission(str, Enum):
    # Workspace & Team
    WORKSPACE_MANAGE = "workspace:manage"
    TEAM_INVITE      = "team:invite"
    TEAM_MANAGE      = "team:manage"

    # Blog Operations
    BLOG_CONNECT     = "blog:connect"
    BLOG_DELETE      = "blog:delete"
    BLOG_CONFIGURE   = "blog:configure"

    # Article Lifecycle
    ARTICLE_VIEW     = "article:view"
    ARTICLE_CREATE   = "article:create"
    ARTICLE_EDIT     = "article:edit"
    ARTICLE_DELETE   = "article:delete"
    ARTICLE_REVIEW   = "article:review"        # Submit draft for review
    ARTICLE_APPROVE  = "article:approve"       # Approve draft for publishing
    ARTICLE_PUBLISH  = "article:publish_live"  # Direct publish / live send to Blogger

    # Billing & System
    BILLING_MANAGE   = "billing:manage"
    BYOK_MANAGE      = "byok:manage"

# Explicit capability mappings per role
ROLE_PERMISSIONS: dict[str, Set[Permission]] = {
    "owner": {
        Permission.WORKSPACE_MANAGE,
        Permission.TEAM_INVITE,
        Permission.TEAM_MANAGE,
        Permission.BLOG_CONNECT,
        Permission.BLOG_DELETE,
        Permission.BLOG_CONFIGURE,
        Permission.ARTICLE_VIEW,
        Permission.ARTICLE_CREATE,
        Permission.ARTICLE_EDIT,
        Permission.ARTICLE_DELETE,
        Permission.ARTICLE_REVIEW,
        Permission.ARTICLE_APPROVE,
        Permission.ARTICLE_PUBLISH,
        Permission.BILLING_MANAGE,
        Permission.BYOK_MANAGE,
    },
    "admin": {
        Permission.TEAM_INVITE,
        Permission.BLOG_CONNECT,
        Permission.BLOG_DELETE,
        Permission.BLOG_CONFIGURE,
        Permission.ARTICLE_VIEW,
        Permission.ARTICLE_CREATE,
        Permission.ARTICLE_EDIT,
        Permission.ARTICLE_DELETE,
        Permission.ARTICLE_REVIEW,
        Permission.ARTICLE_APPROVE,
        Permission.ARTICLE_PUBLISH,
        Permission.BYOK_MANAGE,
    },
    "editor": {
        Permission.ARTICLE_VIEW,
        Permission.ARTICLE_CREATE,
        Permission.ARTICLE_EDIT,
        Permission.ARTICLE_DELETE,
        Permission.ARTICLE_REVIEW,
        Permission.ARTICLE_APPROVE,
        Permission.ARTICLE_PUBLISH,
    },
    "writer": {
        Permission.ARTICLE_VIEW,
        Permission.ARTICLE_CREATE,
        Permission.ARTICLE_EDIT,
        Permission.ARTICLE_REVIEW,  # Can submit draft for review, CANNOT approve or publish live
    },
    "viewer": {
        Permission.ARTICLE_VIEW,
    }
}

def get_user_role_for_blog(user: User, blog: Blog, db: Session) -> str:
    """
    Resolves the user's effective role for a specific blog.
    - If user is direct blog owner -> 'owner'
    - If user is SaaS Superadmin -> 'admin'
    - Otherwise, checks workspace memberships and blog assignments.
    - If not assigned -> 'none'
    """
    if not user or not blog:
        return "none"

    # 1. Direct blog owner
    if blog.user_id == user.id:
        return "owner"

    # 2. SaaS Superadmin
    if user.role == "admin" or user.email == "admin@bagustech.id":
        return "admin"

    # 3. Check workspace memberships under the blog's owner
    # Find all workspaces owned by the blog owner
    owner_workspaces = db.query(Workspace).filter(Workspace.owner_id == blog.user_id).all()
    if not owner_workspaces:
        return "none"

    ws_ids = [w.id for w in owner_workspaces]
    memberships = db.query(WorkspaceMembership).filter(
        WorkspaceMembership.workspace_id.in_(ws_ids),
        WorkspaceMembership.user_id == user.id
    ).all()

    if not memberships:
        return "none"

    for m in memberships:
        # Workspace owner or admin has access to all blogs under this owner
        if m.role in ("owner", "admin"):
            return m.role

        # For editor or writer, check granular blog assignment
        assignment = db.query(WorkspaceBlogAssignment).filter(
            WorkspaceBlogAssignment.membership_id == m.id,
            WorkspaceBlogAssignment.blog_id == blog.id
        ).first()

        if assignment:
            return m.role

    return "none"

def has_blog_permission(user: User, blog: Blog, permission: Permission, db: Session) -> bool:
    """
    Checks if a user has a specific permission for a given blog.
    """
    role = get_user_role_for_blog(user, blog, db)
    if role == "none":
        return False
    allowed = ROLE_PERMISSIONS.get(role, set())
    return permission in allowed

def get_accessible_blogs(user: User, db: Session) -> List[Blog]:
    """
    Returns all blogs accessible to the user:
    1. Blogs directly owned by the user.
    2. Blogs assigned to the user via workspace memberships.
    """
    if not user:
        return []

    # If superadmin, return all blogs
    if user.role == "admin" or user.email == "admin@bagustech.id":
        return db.query(Blog).order_by(Blog.created_at.asc()).all()

    # 1. Directly owned blogs
    owned_blogs = db.query(Blog).filter(Blog.user_id == user.id).all()
    seen_ids = {b.id for b in owned_blogs}
    result = list(owned_blogs)

    # 2. Blogs via Workspace Memberships
    memberships = db.query(WorkspaceMembership).filter(WorkspaceMembership.user_id == user.id).all()
    for m in memberships:
        ws = m.workspace
        if not ws:
            continue
        if m.role in ("owner", "admin"):
            # Has access to all blogs of workspace owner
            ws_blogs = db.query(Blog).filter(Blog.user_id == ws.owner_id).all()
            for b in ws_blogs:
                if b.id not in seen_ids:
                    seen_ids.add(b.id)
                    result.append(b)
        else:
            # Granular assignments for editor / writer / viewer
            assignments = db.query(WorkspaceBlogAssignment).filter(
                WorkspaceBlogAssignment.membership_id == m.id
            ).all()
            for a in assignments:
                if a.blog and a.blog_id not in seen_ids:
                    seen_ids.add(a.blog_id)
                    result.append(a.blog)

    return result

def get_blog_effective_owner(blog: Blog, db: Session) -> Optional[User]:
    """
    Returns the user who owns the blog (and whose subscription quota should be consumed).
    """
    if not blog:
        return None
    return db.query(User).filter(User.id == blog.user_id).first()

