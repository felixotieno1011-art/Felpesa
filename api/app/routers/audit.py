import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import AdminUser, SessionDep
from app.schemas.audit import AuditListResponse, AuditLogOut
from app.schemas.common import PageMeta
from app.services import audit_service

router = APIRouter(tags=["audit"])


@router.get("/audit", response_model=AuditListResponse)
async def list_audit(
    admin: AdminUser,
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    actor_id: Annotated[uuid.UUID | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    entity_type: Annotated[str | None, Query()] = None,
    entity_id: Annotated[uuid.UUID | None, Query()] = None,
) -> AuditListResponse:
    items, total = await audit_service.list_audit_logs(
        db,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
        offset=offset,
    )
    return AuditListResponse(
        items=[AuditLogOut.model_validate(a) for a in items],
        meta=PageMeta(total=total, limit=limit, offset=offset),
    )
