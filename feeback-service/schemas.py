from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, model_validator


class ReviewCreate(BaseModel):
    order_id: int = Field(..., description="Mã đơn hàng đã hoàn thành")
    station_id: Optional[int] = Field(default=1, description="Mã cửa hàng")
    rating: int = Field(..., ge=1, le=5, description="Số sao từ 1 đến 5")
    comment: Optional[str] = Field(None, description="Ý kiến đóng góp")

    @model_validator(mode="after")
    def validate_negative_rating(self):
        """Bắt buộc nêu lý do khi đánh giá 1 hoặc 2 sao"""
        if self.rating in [1, 2]:
            if not self.comment or not self.comment.strip():
                raise ValueError(
                    "Vui lòng nêu rõ lý do khi đánh giá 1 hoặc 2 sao để cửa hàng cải thiện dịch vụ."
                )
        return self


class TelegramReviewCreate(BaseModel):
    order_id: int
    customer_id: Optional[int] = 1
    station_id: Optional[int] = 1
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


class ReviewResponse(BaseModel):
    id: int
    order_id: int
    customer_id: int
    station_id: int
    rating: int
    comment: Optional[str]
    source: str
    created_at: datetime

    class Config:
        from_attributes = True


class StationStatsResponse(BaseModel):
    station_id: int
    total_reviews: int
    average_rating: float
    rating_breakdown: Dict[int, int]
    negative_reviews: List[ReviewResponse]

