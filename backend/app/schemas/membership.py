from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.membership import MembershipRole


class MembershipRead(BaseModel):
    id: UUID
    organization_id: UUID
    user_id: UUID
    role: MembershipRole
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
