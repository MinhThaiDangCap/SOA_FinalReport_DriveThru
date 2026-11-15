import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'

import { errorMessage } from '../api/client.js'
import { getOrder } from '../api/orders.js'
import { formatPrice, METHOD_LABEL, STATUS_LABEL } from '../format.js'
import { payForOrder } from '../payment.js'

export default function OrderPage() {
  const { orderId } = useParams()
  const location = useLocation()
  const [order, setOrder] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState(location.state?.notice || '')
  const [busy, setBusy] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    getOrder(orderId)
      .then((data) => !cancelled && setOrder(data))
      .catch((err) => !cancelled && setError(errorMessage(err)))
    return () => {
      cancelled = true
    }
  }, [orderId, reloadKey])

  async function handlePay() {
    setBusy(true)
    setNotice('')
    try {
      const next = await payForOrder(order.id)
      if (next) setReloadKey((k) => k + 1) // chế độ giả lập: tải lại để thấy trạng thái mới
    } catch (err) {
      setNotice(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  if (error) {
    return (
      <div className="state">
        <p>{error}</p>
        <Link to="/" className="btn">Về trang chủ</Link>
      </div>
    )
  }
  if (!order) {
    return (
      <div className="state">
        <p>Đang tải đơn hàng...</p>
      </div>
    )
  }

  const needsPayment = order.status === 'PENDING_PAYMENT' && order.payment_method === 'MOMO'

  return (
    <div className="checkout order-detail">
      <h1>Đơn #{order.id}</h1>
      <p className="order-status">
        <span className={`status-pill status-${order.status.toLowerCase()}`}>
          {STATUS_LABEL[order.status] || order.status}
        </span>
      </p>

      {notice && <div className="form-error" role="alert">{notice}</div>}

      <p className="checkout-station">
        Biển số: <strong>{order.license_plate}</strong> · Thanh toán:{' '}
        <strong>{METHOD_LABEL[order.payment_method] || order.payment_method}</strong>
      </p>

      <ul className="cart-list">
        {order.items.map((item) => (
          <li key={item.menu_item_id} className="cart-row">
            <span>{item.quantity} × {item.item_name}</span>
            <span>{formatPrice(item.unit_price * item.quantity)}</span>
          </li>
        ))}
      </ul>

      {order.discount_amount > 0 && (
        <div className="cart-row">
          <span>Giảm giá{order.coupon_code ? ` (${order.coupon_code})` : ''}</span>
          <span>-{formatPrice(order.discount_amount)}</span>
        </div>
      )}
      <div className="cart-total">
        <span>Tổng cộng</span>
        <strong>{formatPrice(order.total_amount)}</strong>
      </div>

      {needsPayment && (
        <button type="button" className="btn btn-block order-pay" onClick={handlePay} disabled={busy}>
          {busy ? 'Đang xử lý...' : 'Thanh toán ngay'}
        </button>
      )}

      <p className="order-links">
        <Link to="/">Về trang chủ</Link>
      </p>
    </div>
  )
}