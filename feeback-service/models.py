from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from database import Base


class Review(Base):
    """Bảng 'reviews' lưu đánh giá từ Web và từ Telegram Bot trong feedback_db"""
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Mỗi đơn hàng chỉ được đánh giá 1 lần duy nhất
    order_id = Column(Integer, unique=True, index=True, nullable=False)

    # ID của khách hàng (tham chiếu logic tới auth_db.users.id)
    customer_id = Column(Integer, index=True, nullable=False)

    # ID cửa hàng phục vụ đơn hàng
    station_id = Column(Integer, index=True, nullable=False)

    # Số sao đánh giá: 1 đến 5
    rating = Column(Integer, nullable=False)

    # Nội dung góp ý (Bắt buộc nếu rating là 1 hoặc 2 sao)
    comment = Column(Text, nullable=True)

    # Nguồn đánh giá: "web" hoặc "telegram"
    source = Column(String(20), default="web", nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
