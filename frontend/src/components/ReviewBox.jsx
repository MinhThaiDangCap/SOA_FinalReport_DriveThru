import { useEffect, useState } from 'react'

import { errorMessage } from '../api/client.js'
import { createReview, getOrderReview } from '../api/reviews.js'

function Stars({ value, onChange, readOnly }) {
  return (
    <div className="stars" aria-label={`${value} trên 5 sao`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          className={n <= value ? 'star star-on' : 'star'}
          onClick={() => onChange?.(n)}
          disabled={readOnly}
          aria-label={`${n} sao`}
        >
          ★
        </button>
      ))}
    </div>
  )
}

export default function ReviewBox({ orderId, stationId }) {
  const [review, setReview] = useState(undefined) // undefined: đang tải, null: chưa đánh giá
  const [rating, setRating] = useState(0)
  const [comment, setComment] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    getOrderReview(orderId)
      .then((data) => !cancelled && setReview(data))
      .catch(() => !cancelled && setReview(null))
    return () => {
      cancelled = true
    }
  }, [orderId])

  const needReason = rating === 1 || rating === 2

  async function handleSubmit(e) {
    e.preventDefault()
    if (rating === 0) return setError('Vui lòng chọn số sao.')
    if (needReason && !comment.trim()) {
      return setError('Vui lòng nêu lý do khi đánh giá 1 hoặc 2 sao.')
    }
    setBusy(true)
    setError('')
    try {
      const created = await createReview({
        order_id: Number(orderId),
        station_id: stationId,
        rating,
        comment: comment.trim() || null,
      })
      setReview(created)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  if (review === undefined) return null

  if (review) {
    return (
      <section className="review-box">
        <h2>Đánh giá của bạn</h2>
        <Stars value={review.rating} readOnly />
        {review.comment && <p className="review-comment">{review.comment}</p>}
      </section>
    )
  }

  return (
    <section className="review-box">
      <h2>Bạn thấy đơn hàng này thế nào?</h2>
      <form className="form" onSubmit={handleSubmit}>
        {error && <div className="form-error" role="alert">{error}</div>}
        <Stars value={rating} onChange={setRating} />
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder={needReason ? 'Bắt buộc: cho cửa hàng biết lý do' : 'Góp ý thêm (không bắt buộc)'}
          maxLength={500}
        />
        <button type="submit" className="btn btn-block" disabled={busy}>
          {busy ? 'Đang gửi...' : 'Gửi đánh giá'}
        </button>
      </form>
    </section>
  )
}