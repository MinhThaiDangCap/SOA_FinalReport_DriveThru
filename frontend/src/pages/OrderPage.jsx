import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'

import { errorMessage } from '../api/client.js'
import { getStations } from '../api/menu.js'
import { cancelOrder, getOrder, markArrived } from '../api/orders.js'
import ReviewBox from '../components/ReviewBox.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { formatDateTime, formatPrice, METHOD_LABEL, STATUS_LABEL } from '../format.js'
import { payForOrder } from '../payment.js'

const POLL_MS = 5000
const TERMINAL = ['COMPLETED', 'CANCELLED']
const FLOW = ['PENDING_PAYMENT', 'CONFIRMED', 'PREPARING', 'READY', 'COMPLETED']

const STATUS_HINT = {
  PENDING_PAYMENT: 'Đơn đang chờ thanh toán. Hoàn tất thanh toán để cửa hàng bắt đầu chuẩn bị.',
  CONFIRMED: 'Cửa hàng đã nhận đơn và sẽ sớm chuẩn bị món cho bạn.',
  PREPARING: 'Món của bạn đang được chuẩn bị.',
  READY: 'Món đã sẵn sàng. Hãy chạy xe tới quầy và bấm "Tôi đã đến".',
  ARRIVED: 'Cửa hàng đã biết bạn có mặt, nhân viên sẽ giao món ngay.',
  COMPLETED: 'Đơn đã hoàn thành. Cảm ơn bạn!',
  CANCELLED: 'Đơn đã bị hủy.',
}

export default function OrderPage() {
  const { orderId } = useParams()
  const location = useLocation()
  const { user } = useAuth()
  const [order, setOrder] = useState(null)
  const [stationName, setStationName] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState(location.state?.notice || '')
  const [busy, setBusy] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

  const status = order?.status
  const stationId = order?.station_id
  const finished = !!status && TERMINAL.includes(status)
  const isCustomer = user?.role === 'CUSTOMER'

  // Tải đơn (lần đầu, và mỗi khi reloadKey đổi)
  useEffect(() => {
    let cancelled = false
    getOrder(orderId)
      .then((data) => {
        if (cancelled) return
        setOrder(data)
        setError('')
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err))
      })
    return () => {
      cancelled = true
    }
  }, [orderId, reloadKey])

  // Tự làm mới cho tới khi đơn hoàn thành hoặc bị hủy
  useEffect(() => {
    if (!status || finished) return undefined
    const timer = setInterval(() => {
      if (document.visibilityState === 'visible') setReloadKey((k) => k + 1)
    }, POLL_MS)
    return () => clearInterval(timer)
  }, [status, finished])

  // Lấy tên cửa hàng
  useEffect(() => {
    if (!stationId) return
    getStations()
      .then((list) => {
        const found = list.find((s) => s.id === stationId)
        setStationName(found ? found.name : '')
      })
      .catch(() => {})
  }, [stationId])

  async function runAction(action, confirmText) {
    if (confirmText && !window.confirm(confirmText)) return
    setBusy(true)
    setNotice('')
    try {
      setOrder(await action(order.id))
    } catch (err) {
      setNotice(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

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

  if (error && !order) {
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

  const steps = order.payment_method === 'CASH' ? FLOW.filter((s) => s !== 'PENDING_PAYMENT') : FLOW
  const currentKey = status === 'ARRIVED' ? 'READY' : status
  const currentIndex = steps.indexOf(currentKey)

  const needsPayment = status === 'PENDING_PAYMENT' && order.payment_method === 'MOMO'
  const canCancel = isCustomer && ['PENDING_PAYMENT', 'CONFIRMED'].includes(status)
  const canArrive = isCustomer && ['PREPARING', 'READY'].includes(status)

  return (
    <div className="checkout order-detail">
      <Link to={isCustomer ? '/orders' : '/'} className="back-link">
        ← {isCustomer ? 'Đơn của tôi' : 'Trang chủ'}
      </Link>
      <h1>Đơn #{order.id}</h1>
      <p className="order-status">
        <span className={`status-pill status-${status.toLowerCase()}`}>
          {STATUS_LABEL[status] || status}
        </span>
      </p>
      <p className="order-hint">{STATUS_HINT[status]}</p>
      {order.payment_method === 'CASH' && !finished && (
        <p className="order-hint">Bạn thanh toán tiền mặt tại quầy khi nhận món.</p>
      )}

      {notice && <div className="form-error" role="alert">{notice}</div>}

      {status !== 'CANCELLED' && (
        <ol className="progress">
          {steps.map((s, i) => {
            const done = i < currentIndex || status === 'COMPLETED'
            const now = i === currentIndex && status !== 'COMPLETED'
            return (
              <li key={s} className={done ? 'progress-done' : now ? 'progress-now' : ''}>
                <span className="progress-dot">{done ? '✓' : i + 1}</span>
                <span className="progress-label">
                  {s === 'READY' && status === 'ARRIVED' ? 'Khách đã đến' : STATUS_LABEL[s]}
                </span>
              </li>
            )
          })}
        </ol>
      )}

      <p className="checkout-station">
        Cửa hàng: <strong>{stationName || `#${order.station_id}`}</strong> · Biển số:{' '}
        <strong>{order.license_plate}</strong> · Thanh toán:{' '}
        <strong>{METHOD_LABEL[order.payment_method] || order.payment_method}</strong>
      </p>
      <p className="order-time">Đặt lúc {formatDateTime(order.created_at)}</p>

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
        <button type="button" className="btn btn-block order-action" onClick={handlePay} disabled={busy}>
          {busy ? 'Đang xử lý...' : 'Thanh toán ngay'}
        </button>
      )}
      {canArrive && (
        <button
          type="button"
          className="btn btn-block order-action"
          onClick={() => runAction(markArrived)}
          disabled={busy || status === 'ARRIVED'}
        >
          Tôi đã đến
        </button>
      )}
      {canCancel && (
        <button
          type="button"
          className="btn btn-ghost btn-block order-action"
          onClick={() =>
            runAction(
              cancelOrder,
              order.payment_method === 'MOMO' && status === 'CONFIRMED'
                ? 'Bạn chắc chắn muốn hủy đơn này? Tiền sẽ được hoàn về ví MoMo của bạn.'
                : 'Bạn chắc chắn muốn hủy đơn này?',
            )
          }
          disabled={busy}
        >
          Hủy đơn
        </button>
      )}

      {isCustomer && status === 'COMPLETED' && (
        <ReviewBox orderId={order.id} stationId={order.station_id} />
      )}

      <h2 className="timeline-title">Lịch sử đơn hàng</h2>
      <ul className="timeline">
        {order.history.map((h, i) => (
          <li key={i}>
            <strong>{STATUS_LABEL[h.to_status] || h.to_status}</strong>
            <span>{formatDateTime(h.changed_at)}</span>
            {h.note && <small>{h.note}</small>}
          </li>
        ))}
      </ul>
    </div>
  )
}