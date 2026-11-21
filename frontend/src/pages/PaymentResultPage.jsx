import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

import { errorMessage } from '../api/client.js'
import { getMomoResult } from '../api/payments.js'
import Icon from '../components/Icon.jsx'
import { formatPrice } from '../format.js'

export default function PaymentResultPage() {
  const { search } = useLocation()
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!search) return undefined
    let cancelled = false
    let timer
    let tries = 0

    const check = async () => {
      try {
        const data = await getMomoResult(search)
        if (cancelled) return
        setResult(data)
        if (data.payment_status === 'PENDING' && tries < 5) {
          tries += 1
          timer = setTimeout(check, 3000)
        }
      } catch (err) {
        if (!cancelled) setError(errorMessage(err))
      }
    }
    check()

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [search])

  if (!search) {
    return (
      <div className="state">
        <p>Không có thông tin thanh toán.</p>
        <Link to="/" className="btn">Về trang chủ</Link>
      </div>
    )
  }
  if (error) {
    return (
      <div className="state">
        <p>{error}</p>
        <Link to="/orders" className="btn">Xem đơn của tôi</Link>
      </div>
    )
  }
  if (!result) {
    return (
      <div className="state">
        <p>Đang xác nhận kết quả thanh toán...</p>
      </div>
    )
  }

  const tone = result.success ? 'ok' : result.payment_status === 'PENDING' ? 'wait' : 'fail'

  return (
    <div className="auth-card pay-result">
      <div className={`pay-icon pay-${tone}`} aria-hidden="true">
        <Icon name={tone === 'ok' ? 'check' : tone === 'wait' ? 'hourglass' : 'x'} size={32} strokeWidth={2.4} />
      </div>
      <h1>{result.message}</h1>
      <p className="auth-sub">
        Đơn #{result.order_id} · {formatPrice(result.amount)}
      </p>
      {tone === 'wait' && (
        <p className="auth-sub">
          MoMo chưa gửi xác nhận về hệ thống. Đơn sẽ tự chuyển sang "Đã xác nhận" khi MoMo báo
          về; bạn không cần thanh toán lại.
        </p>
      )}
      <Link to={`/orders/${result.order_id}`} className="btn btn-block">
        Xem đơn hàng
      </Link>
    </div>
  )
}
