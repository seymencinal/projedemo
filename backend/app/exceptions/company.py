from uuid import UUID


class CompanyNotFoundError(Exception):
    def __init__(self, company_id: UUID) -> None:
        self.company_id = company_id
        super().__init__(f"Company with id '{company_id}' was not found.")


class CompanyAlreadyExistsError(Exception):
    def __init__(
        self,
        exchange: str,
        ticker: str,
    ) -> None:
        self.exchange = exchange
        self.ticker = ticker
        super().__init__(
            f"Company with exchange '{exchange}' and ticker '{ticker}' already exists."
        )
