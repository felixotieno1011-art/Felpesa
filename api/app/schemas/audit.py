import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.common import Paginated


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: uuid.UUID | None
    action: str
    entity_type: str | None
    entity_id: uuid.UUID | None
    metadata_json: dict | None = None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime

    # Pydantic will map ORM attribute `metadata_json` → field name as-is;
    # the DB column is named "metadata". We expose it as "metadata" in JSON
    # by using a serialization alias.
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AuditListResponse(Paginated[AuditLogOut]):
    pass
