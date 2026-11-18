import { useEffect, useState } from 'react'

import { errorMessage } from '../api/client.js'
import { getStationStats } from '../api/reviews.js'
import { getStationReviews } from '../api/staff.js'
import { formatDateTime } from '../format.js'
import Icon, { StarRow } from './Icon.jsx'

/** Điểm trung bình, phân bổ sao và danh sách đánh giá của một cửa hàng. */
export default function ReviewsPanel({ stationId }) {
  const [stats, setStats] = useState(null)
  const [reviews, setReviews] = useState(null)
  const [rating, setRating] = useState(0)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setError('')
    getStationStats(stationId)
      .then((s) => !cancelled && setStats(s))
      .catch((err) => !cancelled && setError(errorMessage(err)))
    return () => {
      cancelled = true
    }
  }, [stationId])

  useEffect(() => {
    let cancelled = false
    setReviews(null)
    getStationReviews(stationId, rating || undefined)
      .then((r) => !cancelled && setReviews(r))
      .catch((err) => !cancelled && setError(errorMessage(err)))
    return () => {
      cancelled = true
    }
  }, [stationId, rating])

  if (error) return <p className="form-error">{error}</p>
  if (!stats) return <div className="state">Đang tải đánh giá...</div>

  const max = Math.max(1, ...Object.values(stats.rating_breakdown))

  return (
    <div>
      <div className="review-summary">
        <div className="review-score">
          <strong>{stats.total_reviews ? stats.average_rating.toFixed(1) : '–'}</strong>
          <StarRow value={Math.round(stats.average_rating)} size={16} />
          <small>{stats.total_reviews} lượt đánh giá</small>
        </div>
        <ul className="review-bars">
          {[5, 4, 3, 2, 1].map((n) => {
            const count = stats.rating_breakdown[n] || 0
            return (
              <li key={n}>
                <span className="with-icon">
                  {n} <Icon name="star" size={13} filled className="star-fill" />
                </span>
                <span className="bar">
                  <span style={{ width: `${(count / max) * 100}%` }} />
                </span>
                <span>{count}</span>
              </li>
            )
          })}
        </ul>
      </div>

      <div className="category-tabs" role="tablist">
        {[0, 5, 4, 3, 2, 1].map((n) => (
          <button
            key={n}
            type="button"
            className={rating === n ? 'tab active' : 'tab'}
            onClick={() => setRating(n)}
          >
            {n === 0 ? 'Tất cả' : `${n} sao`}
          </button>
        ))}
      </div>

      {reviews === null ? (
        <div className="state">Đang tải...</div>
      ) : reviews.length === 0 ? (
        <p className="board-empty">Chưa có đánh giá nào.</p>
      ) : (
        <ul className="review-list">
          {reviews.map((r) => (
            <li key={r.id} className={r.rating <= 2 ? 'review-bad' : ''}>
              <div className="review-list-head">
                <StarRow value={r.rating} size={15} />
                <span className="muted">
                  Đơn #{r.order_id} · {formatDateTime(r.created_at)} · {r.source === 'telegram' ? 'Telegram' : 'Web'}
                </span>
              </div>
              {r.comment && <p>{r.comment}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
