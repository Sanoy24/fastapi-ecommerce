from fastapi import APIRouter, Depends, Query
from typing import Annotated, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from datetime import datetime

from app.dependencies import require_admin, get_db
from app.models.audit_log import AuditLog
from app.schema.user_schema import UserPublic
from pydantic import BaseModel, ConfigDict
from typing import Any

router = APIRouter(tags=["Audit"])

class AuditLogResponse(BaseModel):
    id: int
    admin_user_id: Optional[int]
    action: str
    resource_type: str
    resource_id: int
    old_value: Optional[Any]
    new_value: Optional[Any]
    ip_address: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AuditLogPaginatedResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int

@router.get(
    "/admin/audit-logs",
    response_model=AuditLogPaginatedResponse,
    summary="Get audit logs",
    description="Retrieve a paginated list of administrative audit logs.",
)
def get_audit_logs(
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[UserPublic, Depends(require_admin)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    admin_user_id: Optional[int] = Query(None, description="Filter by admin user ID"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    action: Optional[str] = Query(None, description="Filter by action"),
):
    stmt = select(AuditLog)

    if admin_user_id:
        stmt = stmt.where(AuditLog.admin_user_id == admin_user_id)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if action:
        stmt = stmt.where(AuditLog.action == action)

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))

    offset = (page - 1) * page_size
    stmt = stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size)

    logs = db.scalars(stmt).all()

    return AuditLogPaginatedResponse(
        items=[AuditLogResponse.model_validate(log) for log in logs],
        total=total or 0,
        page=page,
        page_size=page_size
    )
