import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

import { errorMessage } from '../api/client.js'
import { getMomoResult } from '../api/payments.js'
import { formatPrice } from '../format.js'

const MAX_TRIES = 5 // PENDING thì hỏi lại vài lần, chờ MoMo gọi IPN

/** Trang MoMo chuyển khách về sau khi thanh toán: /payment/result?partnerCode=...&signature=... */
export default function PaymentResultPage() {
  const { search } = useLocation()
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    let timer

    async function check(tries) {
      try {
        const data = await getMomoResult(search)
        if (cancelled) return
        setResult(data)
        if (data.payment_status === 'PENDING' && tries < MAX_TRIES) {
          timer = setTimeout(() => check(tries + 1), 2000)
        }
      } catch (err) {
        if (!cancelled) setError(errorMessage(err))
      }
    }

    check(1)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [search])

  if (error) {
    return (
      <div className="state">
        <p>{error}</p>
        <Link to="/" className="btn">Về trang chủ</Link>
      </div>
    )
  }
  if (!result) {
    return (
      <div className="state">
        <p>Đang kiểm tra kết quả thanh toán...</p>
      </div>
    )
  }

  return (
    <div className="state">
      <h1>{result.message}</h1>
      <p>
        Đơn #{result.order_id} · {formatPrice(result.amount)}
      </p>
      <Link to={`/orders/${result.order_id}`} className="btn">
        Xem đơn hàng
      </Link>
    </div>
  )
}
