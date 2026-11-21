import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'

import { errorMessage } from '../api/client.js'
import { getStations } from '../api/menu.js'
import { cancelOrder, changePaymentMethod, getOrder, markArrived } from '../api/orders.js'
import ConfirmDialog from '../components/ConfirmDialog.jsx'
import Icon from '../components/Icon.jsx'
import ReviewBox from '../components/ReviewBox.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { formatDateTime, formatPrice, formatTime, METHOD_LABEL, minutesUntil, STATUS_LABEL } from '../format.js'
import { payForOrder } from '../payment.js'

const POLL_MS = 5000
const TERMINAL = ['COMPLETED', 'CANCELLED']
const FLOW = ['PENDING_PAYMENT', 'CONFIRMED', 'PREPARING', 'READY', 'COMPLETED']

/** Giờ món xong dự kiến (tính từ thời gian làm từng món và số đơn đang chờ ở cửa hàng). */
function EstimateBox({ iso }) {
  const left = minutesUntil(iso)
  return (
    <div className="estimate-box">
      <Icon name="clock" size={22} />
      <div>
        <strong>Dự kiến xong lúc {formatTime(iso)}</strong>
        <p>
          {left !== null && left > 0
            ? `Khoảng ${left} phút nữa. Bạn canh giờ này để tới nhận món nhé.`
            : 'Món sắp xong, cửa hàng đang hoàn tất đơn của bạn.'}
        </p>
      </div>
    </div>
  )
}

const STATUS_HINT = {
  PENDING_PAYMENT: 'Đơn đang chờ thanh toán. Hoàn tất thanh toán để cửa hàng bắt đầu chuẩn bị.',
  CONFIRMED: 'Cửa hàng đã nhận đơn và sẽ sớm chuẩn bị món cho bạn.',
  PREPARING: 'Món của bạn đang được chuẩn bị.',
  READY: 'Món đã sẵn sàng. Khi tới làn nhận món, bấm "Tôi đã đến" để nhân viên mang món ra.',
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
  // Hộp thoại đang mở: 'cancel' | 'method' | null
  const [dialog, setDialog] = useState(null)

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

  async function runAction(action) {
    setBusy(true)
    setNotice('')
    try {
      const updated = await action(order.id)
      setOrder(updated)
      return updated
    } catch (err) {
      setNotice(errorMessage(err))
      // Trạng thái có thể đã đổi (vd. cửa hàng vừa bắt đầu làm): tải lại để ẩn nút không còn dùng được
      setReloadKey((k) => k + 1)
      return null
    } finally {
      setBusy(false)
      setDialog(null)
    }
  }

  // Chỉ đổi được đơn ZaloPay (chưa trả) -> trả tại quầy. Đơn trả tại quầy đã gửi tới cửa hàng
  // nên không đổi sang ZaloPay (tránh rút đơn khỏi hàng đợi của quầy).
  function handleChangeToCash() {
    return runAction((id) => changePaymentMethod(id, 'CASH'))
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

  const isZaloPay = order.payment_method === 'ZALOPAY'
  const needsPayment = status === 'PENDING_PAYMENT' && isZaloPay
  // Đơn ZaloPay đã trả (CONFIRMED) không hủy trên ứng dụng: khách gọi hotline cửa hàng
  const paidZaloPay = isZaloPay && status === 'CONFIRMED'
  const canCancel =
    isCustomer && (status === 'PENDING_PAYMENT' || (status === 'CONFIRMED' && !isZaloPay))
  // Xe tới quầy là cờ riêng (arrived_at): báo được từ lúc quán nhận đơn, không đổi tiến độ bếp
  const arrived = !!order.arrived_at || status === 'ARRIVED'
  const canArrive = isCustomer && !arrived && ['CONFIRMED', 'PREPARING', 'READY'].includes(status)
  const arrivedNote =
    status === 'READY' || status === 'ARRIVED'
      ? 'Món đã xong, nhân viên đang mang ra xe cho bạn.'
      : 'Món đang được chuẩn bị, cửa hàng sẽ ưu tiên đơn của bạn. Vui lòng chờ tại làn nhận món.'
  // Chỉ đơn ZaloPay chưa trả tiền mới đổi được (sang trả tại quầy)
  const canChangeToCash = isCustomer && isZaloPay && status === 'PENDING_PAYMENT'
  const cashPaidAt =
    order.payment_method === 'CASH' && status === 'COMPLETED'
      ? order.history.find((h) => h.to_status === 'COMPLETED')?.changed_at
      : null

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
      <p className="order-hint">{STATUS_HINT[status]}</p>
      {order.estimated_ready_at && ['CONFIRMED', 'PREPARING'].includes(status) && (
        <EstimateBox iso={order.estimated_ready_at} />
      )}
      {order.payment_method === 'CASH' && !finished && (
        <div className="cash-box">
          <Icon name="card" size={22} />
          <div>
            <strong>Chuẩn bị {formatPrice(order.total_amount)} tiền mặt</strong>
            <p>
              Bạn thanh toán cho nhân viên tại quầy khi nhận món. Nhân viên sẽ xác nhận đã thu tiền
              rồi mới giao món.
            </p>
          </div>
        </div>
      )}
      {cashPaidAt && (
        <div className="cash-box cash-box-done">
          <Icon name="check" size={22} strokeWidth={2.4} />
          <div>
            <strong>Đã thanh toán {formatPrice(order.total_amount)} tiền mặt</strong>
            <p>Nhân viên đã xác nhận thu tiền lúc {formatDateTime(cashPaidAt)}.</p>
          </div>
        </div>
      )}

      {arrived && !finished && (
        <div className="cash-box cash-box-done">
          <Icon name="car" size={22} />
          <div>
            <strong>
              Cửa hàng đã nhận được thông báo bạn đã tới
              {order.arrived_at && ` lúc ${formatDateTime(order.arrived_at)}`}
            </strong>
            <p>{arrivedNote}</p>
          </div>
        </div>
      )}

      {notice && <div className="form-error" role="alert">{notice}</div>}

      {status !== 'CANCELLED' && (
        <ol className="progress">
          {steps.map((s, i) => {
            const done = i < currentIndex || status === 'COMPLETED'
            const now = i === currentIndex && status !== 'COMPLETED'
            return (
              <li key={s} className={done ? 'progress-done' : now ? 'progress-now' : ''}>
                <span className="progress-dot">{done ? <Icon name="check" size={15} strokeWidth={2.6} /> : i + 1}</span>
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
        <button
          type="button"
          className="btn btn-block order-action"
          onClick={handlePay}
          disabled={busy}
        >
          {busy ? 'Đang xử lý...' : 'Thanh toán ngay bằng ZaloPay'}
        </button>
      )}
      {canArrive && (
        <button
          type="button"
          className="btn btn-block order-action"
          onClick={() => runAction(markArrived)}
          disabled={busy}
        >
          Tôi đã đến
        </button>
      )}
      {canChangeToCash && (
        <button
          type="button"
          className="btn btn-ghost btn-block order-action"
          onClick={() => setDialog('method')}
          disabled={busy}
        >
          Đổi sang trả tại quầy
        </button>
      )}
      {canCancel && (
        <button
          type="button"
          className="btn btn-ghost btn-block order-action"
          onClick={() => setDialog('cancel')}
          disabled={busy}
        >
          Hủy đơn
        </button>
      )}
      {canCancel && (
        <p className="order-hint cancel-hint">
          Bạn có thể hủy đơn cho tới khi cửa hàng bắt đầu làm món.
          {needsPayment &&
            ' Sau khi thanh toán ZaloPay thành công, đơn sẽ không hủy được trên ứng dụng nữa.'}
          {order.payment_method === 'CASH' &&
            ' Đơn trả tại quầy đã gửi tới cửa hàng nên không đổi được phương thức thanh toán; muốn trả online, hãy hủy đơn và đặt lại.'}
        </p>
      )}
      {isCustomer && paidZaloPay && (
        <p className="order-hint cancel-hint">
          Đơn đã thanh toán qua ZaloPay nên không thể hủy trên ứng dụng. Nếu muốn hủy đơn, vui
          lòng liên hệ hotline cửa hàng <strong>1900 6868</strong> để được hỗ trợ hủy đơn và
          hoàn tiền.
        </p>
      )}

      {dialog === 'cancel' && (
        <ConfirmDialog
          title={`Hủy đơn #${order.id}?`}
          confirmLabel="Hủy đơn"
          cancelLabel="Giữ đơn"
          busy={busy}
          onConfirm={() => runAction(cancelOrder)}
          onCancel={() => setDialog(null)}
        >
          <p>Đơn sẽ bị hủy và cửa hàng không chuẩn bị món nữa.</p>
        </ConfirmDialog>
      )}

      {dialog === 'method' && (
        <ConfirmDialog
          title="Đổi sang trả tại quầy?"
          confirmLabel="Đổi sang trả tại quầy"
          cancelLabel="Giữ ZaloPay"
          busy={busy}
          onConfirm={handleChangeToCash}
          onCancel={() => setDialog(null)}
        >
          <p>
            Đơn #{order.id} sẽ được gửi ngay tới cửa hàng. Bạn trả {formatPrice(order.total_amount)} tiền
            mặt khi nhận món. Sau khi đổi sẽ không chuyển lại sang ZaloPay được.
          </p>
        </ConfirmDialog>
      )}

      {isCustomer && status === 'COMPLETED' && (
        <ReviewBox orderId={order.id} stationId={order.station_id} />
      )}

      <h2 className="timeline-title">Lịch sử đơn hàng</h2>
      <ul className="timeline">
        {order.history.map((h, i) => {
          // Sự kiện không đổi trạng thái (khách tới quầy, ghi chú thanh toán): lấy ghi chú làm tiêu đề
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