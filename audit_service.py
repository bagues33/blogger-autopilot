"""
Enterprise Audit Logging Service for Blogger Auto-Pilot SaaS
Provides compliant, tamper-evident audit trails for all tenant, article, and integration activities.
"""

import json
import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from models_saas import AuditLog

logger = logging.getLogger("AuditService")

def record_audit_log(
    db: Session,
    event_type: str,
    user_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None
) -> Optional[AuditLog]:
    """
    Safely records a structured audit log entry to the database.
    Catches exceptions so audit logging failures never break primary user operations.
    """
    try:
        meta_str = json.dumps(metadata) if metadata is not None else None
        log_entry = AuditLog(
            user_id=user_id,
            workspace_id=workspace_id,
            event_type=event_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            metadata_json=meta_str,
            ip_address=ip_address
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        return log_entry
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning(f"Failed to record audit log for {event_type}: {e}")
        return None
