from datetime import datetime
from pydantic import BaseModel, Field


class SmsPurchaseCreate(BaseModel):
    phone: str = Field(min_length=10, max_length=20)


class SmsPurchaseOut(BaseModel):
    id: str
    amount: int
    tokens: int
    status: str
    checkout_request_id: str | None = None
    result_description: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}
