from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PaymentCreate(BaseModel):
    order_id: int = Field(gt=0)


class CashConfirm(BaseModel):
    order_id: int = Field(gt=0)


class CreatePaymentOut(BaseModel):
    payment_id: int
    txn_ref: str
    amount: int
    payment_url: str


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    customer_id: int
    method: str
    amount: int
    status: str
    txn_ref: str
    vnp_transaction_no: str | None
    bank_code: str | None
    note: str | None
    created_at: datetime
    paid_at: datetime | None