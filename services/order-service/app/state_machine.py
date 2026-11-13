from fastapi import HTTPException
from prometheus_client import Counter

from app.models import Order, OrderStatus, OrderStatusHistory

S = OrderStatus

# Bảng chuyển trạng thái hợp lệ: từ trạng thái nào được sang trạng thái nào
ALLOWED: dict[OrderStatus, set[OrderStatus]] = {
    S.PENDING_PAYMENT: {S.CONFIRMED, S.CANCELLED},
    S.CONFIRMED: {S.PREPARING, S.CANCELLED},
    S.PREPARING: {S.READY, S.ARRIVED},
    S.READY: {S.ARRIVED, S.COMPLETED},
    S.ARRIVED: {S.READY, S.COMPLETED},
    S.COMPLETED: set(),
    S.CANCELLED: set(),
}

STATUS_CHANGES = Counter(
    "order_status_changes_total", "Số lần đổi trạng thái đơn", ["to_status"]
)


def change_status(
    order: Order,
    new_status: OrderStatus,
    changed_by: int | None,
    note: str | None = None,
) -> None:
    """Đổi trạng thái nếu hợp lệ và ghi vào order_status_history.

    Không commit ở đây, nơi gọi tự commit.
    """
    current = OrderStatus(order.status)
    if new_status not in ALLOWED[current]:
        raise HTTPException(
            status_code=409,
            detail=f"Không thể chuyển đơn từ {current.value} sang {new_status.value}",
        )

    old = order.status
    order.status = new_status.value
    order.history.append(
        OrderStatusHistory(
            from_status=old,
            to_status=new_status.value,
            changed_by=changed_by,
            note=note,
        )
    )
    STATUS_CHANGES.labels(to_status=new_status.value).inc()