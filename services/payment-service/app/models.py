from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(index=True)      # orders.id bên order_db
    customer_id: Mapped[int] = mapped_column(index=True)   # users.id bên auth_db
    method: Mapped[str] = mapped_column(String(10))        # VNPAY | CASH
    amount: Mapped[int]                                    # VND
    status: Mapped[str] = mapped_column(String(10), default="PENDING", index=True)
    # PENDING | SUCCESS | FAILED
    txn_ref: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    vnp_transaction_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
    bank_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    collected_by: Mapped[int | None] = mapped_column(nullable=True)  # nhân viên thu tiền mặt
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PaymentCallback(Base):
    __tablename__ = "payment_callbacks"

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int | None] = mapped_column(
        ForeignKey("payments.id"), nullable=True, index=True
    )
    txn_ref: Mapped[str] = mapped_column(String(60), index=True)
    raw_params: Mapped[str] = mapped_column(Text)          # nguyên văn query VNPay gửi
    signature_valid: Mapped[bool]
    response_code: Mapped[str | None] = mapped_column(String(5), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )