from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header


def get_temporary_organization_id(
    organization_id: Annotated[UUID, Header(alias="X-Organization-ID")],
) -> UUID:
    return organization_id


TemporaryOrganizationId = Annotated[
    UUID,
    Depends(get_temporary_organization_id),
]
