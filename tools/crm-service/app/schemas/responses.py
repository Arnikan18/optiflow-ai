from pydantic import BaseModel, ConfigDict


class CustomerResponse(BaseModel):
    id: int
    customer_id: str
    name: str
    tier: str
    arr: float
    renewal_date: str
    active: bool

    model_config = ConfigDict(from_attributes=True)