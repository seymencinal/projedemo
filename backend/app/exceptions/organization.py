from uuid import UUID


class OrganizationNotFoundError(Exception):
    def __init__(self, organization_id: UUID) -> None:
        self.organization_id = organization_id
        super().__init__(f"Organization with id '{organization_id}' was not found.")


class OrganizationAlreadyExistsError(Exception):
    def __init__(self, slug: str) -> None:
        self.slug = slug
        super().__init__(f"Organization with slug '{slug}' already exists.")
