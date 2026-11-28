import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'

import { errorMessage } from '../api/client.js'
import { getStations } from '../api/menu.js'
import { cancelOrder, getOrder } from '../api/orders.js'
import ConfirmDialog from '../components/ConfirmDialog.jsx'
import Icon from '../components/Icon.jsx'
import LicensePlate from '../components/LicensePlate.jsx'
import ReviewBox from '../components/ReviewBox.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { formatDateTime, formatPrice, formatTime, METHOD_LABEL, minutesUntil, STATUS_LABEL } from '../format.js'
import { payForOrder } from '../payment.js'

const POLL_MS = 5000
const TERMINAL = ['COMPLETED', 'CANCELLED']
// Các bước khách thấy: đặt trước -> trạm 1 -> bếp -> trạm 2
const FLOW = [
  { key: 'HOLD', label: 'Đã đặt, giữ chỗ' },
  { key: 'AWAITING_PAYMENT', label: 'Thanh toán ở trạm 1' },
  { key: 'CONFIRMED', label: 'Chờ bếp' },
  { key: 'PREPARING', label: 'Bếp đang làm' },
  { key: 'READY', label: 'Mời ra trạm 2' },
  { key: 'COMPLETED', label: 'Đã nhận món' },
]

const STATUS_HINT = {
  HOLD: 'Lái xe tới trạm 1 của cửa hàng và đọc mã nhận món cho nhân viên.',
  AWAITING_PAYMENT: 'Nhân viên trạm 1 đã nhận đơn. Thanh toán để bếp bắt đầu làm món.',
  CONFIRMED: 'Đã thanh toán. Mời bạn vào bãi chờ, bếp sẽ làm món theo lượt.',
  PREPARING: 'Bếp đang làm món của bạn. Vui lòng chờ ở bãi xe.',
  READY: 'Món đã xong! Mời bạn lái xe ra trạm 2 và đọc mã nhận món.',
  COMPLETED: 'Bạn đã nhận món. Cảm ơn bạn!',
  CANCELLED: 'Đơn đã bị hủy.',
  PENDING_PAYMENT: 'Đơn đang chờ thanh toán.',
  ARRIVED: 'Cửa hàng đã biết bạn có mặt.',
}

/** Giờ món xong dự kiến (tính theo hàng đợi bếp của cửa hàng). */
function EstimateBox({ iso }) {
  const left = minutesUntil(iso)
  return (
    <div className="estimate-box">
      <Icon name="clock" size={22} />
      <div>
        <strong>Dự kiến xong lúc {formatTime(iso)}</strong>
        <p>
          {left !== null && left > 0
            ? `Khoảng ${left} phút nữa. Khi món xong, trang này sẽ mời bạn ra trạm 2.`
            : 'Món sắp xong, bếp đang hoàn tất đơn của bạn.'}
        </p>
      </div>
    </div>
  )
}

/** Mã nhận món thật to: khách đọc mã này ở trạm 1 và trạm 2. */
function PickupCode({ order }) {
  const left = order.hold_expires_at ? minutesUntil(order.hold_expires_at) : null
  return (
    <div className={`pickup-code-box${order.status === 'READY' ? ' pickup-ready' : ''}`}>
      <span className="pickup-label">Mã nhận món</span>
      <strong className="pickup-code">{order.pickup_code}</strong>
      {order.status === 'HOLD' && order.hold_expires_at && (
        <p className={order.is_overdue ? 'pickup-late' : ''}>
          {order.is_overdue
            ? `Đã quá giờ giữ đơn (${formatTime(order.hold_expires_at)}). Cửa hàng có thể hủy đơn, vui lòng tới sớm.`
            : `Hẹn tới trạm 1 lúc ${formatTime(order.expected_arrival_at)} · giữ đơn tới ${formatTime(order.hold_expires_at)} (còn ${left} phút)`}
        </p>
      )}
      {order.status === 'READY' && <p>Đọc mã này ở trạm 2 để nhận món.</p>}
    </div>
  )
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
  const [askCancel, setAskCancel] = useState(false)

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

  // Tự làm mới cho tới khi đơn hoàn thành hoặc bị hủy (trạm 1 nhận đơn, bếp làm xong...)
  useEffect(() => {
    if (!status || finished) return undefined
    const timer = setInterval(() => {
      if (document.visibilityState === 'visible') setReloadKey((k) => k + 1)
    }, POLL_MS)
    return () => clearInterval(timer)
  }, [status, finished])

  useEffect(() => {
    if (!stationId) return
    getStations()
      .then((list) => setStationName(list.find((s) => s.id === stationId)?.name || ''))
      .catch(() => {})
  }, [stationId])

  async function handleCancel() {
    setBusy(true)
    setNotice('')
    try {
      setOrder(await cancelOrder(order.id))
    } catch (err) {
      setNotice(errorMessage(err))
      setReloadKey((k) => k + 1)
    } finally {
      setBusy(false)
      setAskCancel(false)
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

  const currentIndex = FLOW.findIndex((s) => s.key === status)
  const needsZaloPay = isCustomer && status === 'AWAITING_PAYMENT' && order.payment_method === 'ZALOPAY'
  const payingCash = status === 'AWAITING_PAYMENT' && order.payment_method === 'CASH'
  const canCancel = isCustomer && ['HOLD', 'AWAITING_PAYMENT'].includes(status)

  return (
    <div className="checkout order-detail">
      <Link to={isCustomer ? '/orders' : '/'} className="back-link">
        <Icon name="arrowLeft" size={16} /> {isCustomer ? 'Đơn của tôi' : 'Trang chủ'}
      </Link>
      <h1>Đơn #{order.id}</h1>
      <p className="order-status">
        <span className={`status-pill status-${status.toLowerCase()}`}>
          {STATUS_LABEL[status] || status}
        </span>
      </p>

      {order.pickup_code && !finished && <PickupCode order={order} />}
      <p className="order-hint">{STATUS_HINT[status]}</p>

      {needsZaloPay && (
        <button type="button" className="btn btn-block order-action" onClick={handlePay} disabled={busy}>
          {busy ? 'Đang xử lý...' : `Thanh toán ${formatPrice(order.total_amount)} bằng ZaloPay`}
        </button>
      )}
      {payingCash && (
        <div className="cash-box">
          <Icon name="cash" size={22} />
          <div>
            <strong>Trả {formatPrice(order.total_amount)} tiền mặt cho nhân viên trạm 1</strong>
            <p>Nhân viên xác nhận đã thu tiền thì đơn tự chuyển vào bếp.</p>
          </div>
        </div>
      )}
      {order.estimated_ready_at && ['CONFIRMED', 'PREPARING'].includes(status) && (
        <EstimateBox iso={order.estimated_ready_at} />
      )}

      {notice && <div className="form-error" role="alert">{notice}</div>}

      {status !== 'CANCELLED' && currentIndex >= 0 && (
        <ol className="progress">
          {FLOW.map((s, i) => {
            const done = i < currentIndex || status === 'COMPLETED'
            const now = i === currentIndex && status !== 'COMPLETED'
            return (
              <li key={s.key} className={done ? 'progress-done' : now ? 'progress-now' : ''}>
                <span className="progress-dot">{done ? <Icon name="check" size={15} strokeWidth={2.6} /> : i + 1}</span>
                <span className="progress-label">{s.label}</span>
              </li>
            )
          })}
        </ol>
      )}

      <p className="checkout-station">
        Cửa hàng: <strong>{stationName || `#${order.station_id}`}</strong> · Biển số:{' '}
        <LicensePlate value={order.license_plate} size="sm" />
        {order.payment_method && (
          <>
            {' '}· Thanh toán: <strong>{METHOD_LABEL[order.payment_method] || order.payment_method}</strong>
          </>
        )}
      </p>
      <p className="order-time">
        Đặt lúc {formatDateTime(order.created_at)}
        {order.contact_phone && ` · SĐT liên hệ ${order.contact_phone}`}
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

      {canCancel && (
        <>
          <button
            type="button"
            className="btn btn-ghost btn-block order-action"
            onClick={() => setAskCancel(true)}
            disabled={busy}
          >
            Hủy đơn
          </button>
          <p className="order-hint cancel-hint">
            Bạn hủy được cho tới khi thanh toán ở trạm 1. Đã thanh toán thì bếp làm món ngay nên
            không hủy được nữa.
          </p>
        </>
      )}

      {askCancel && (
        <ConfirmDialog
          title={`Hủy đơn #${order.id}?`}
          confirmLabel="Hủy đơn"
          cancelLabel="Giữ đơn"
          busy={busy}
          onConfirm={handleCancel}
          onCancel={() => setAskCancel(false)}
        >
          <p>Đơn chưa thanh toán nên bạn không mất tiền. Mã {order.pickup_code} sẽ hết tác dụng.</p>
        </ConfirmDialog>
      )}

      {isCustomer && status === 'COMPLETED' && (
        <ReviewBox orderId={order.id} stationId={order.station_id} />
      )}

      <h2 className="timeline-title">Lịch sử đơn hàng</h2>
      <ul className="timeline">
        {order.history.map((h, i) => {
          // Sự kiện không đổi trạng thái (sửa biển số, đổi cách trả): lấy ghi chú làm tiêu đề
          const event = h.from_status === h.to_status && h.note
          return (
            <li key={i}>
              <strong>{event ? h.note : STATUS_LABEL[h.to_status] || h.to_status}</strong>
              <span>{formatDateTime(h.changed_at)}</span>
              {!event && h.note && <small>{h.note}</small>}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
