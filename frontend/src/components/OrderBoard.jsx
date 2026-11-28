import { useCallback, useEffect, useRef, useState } from 'react'

import { errorMessage } from '../api/client.js'
import { getQueue, getRecentOrders, updateOrderStatus } from '../api/staff.js'
import { formatDateTime, formatDuration, formatPrice, formatTime, METHOD_LABEL, minutesUntil, STATUS_LABEL } from '../format.js'
import ConfirmDialog from './ConfirmDialog.jsx'
import Icon from './Icon.jsx'
import LicensePlate, { formatPlate } from './LicensePlate.jsx'
import NotificationBell from './NotificationBell.jsx'

const POLL_MS = 5000

// Bảng tổng quan của admin theo mô hình 2 trạm
const COLUMNS = [
  { key: 'station1', title: 'Trạm 1 · chờ xác nhận / thanh toán', statuses: ['HOLD', 'AWAITING_PAYMENT', 'PENDING_PAYMENT'] },
  { key: 'kitchen', title: 'Bếp · đã trả tiền / đang làm', statuses: ['CONFIRMED', 'PREPARING'] },
  { key: 'station2', title: 'Trạm 2 · chờ giao', statuses: ['READY', 'ARRIVED'] },
]

function minutesSince(iso) {
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return 0
  return Math.max(0, Math.floor((Date.now() - t) / 60000))
}

/** Xe đã tới trạm 1 chưa (trạm 1 đã nhận đơn; đơn cũ dùng arrived_at / ARRIVED). */
export function hasArrived(order) {
  return !!order.checked_in_at || !!order.arrived_at || order.status === 'ARRIVED'
}

// Trong mỗi cột: xe đã tới lên đầu (tới trước đứng trước), rồi tới đơn đặt trước
function byPriority(a, b) {
  const aa = hasArrived(a)
  const ba = hasArrived(b)
  if (aa !== ba) return aa ? -1 : 1
  const ta = new Date((aa && a.arrived_at) || a.created_at).getTime()
  const tb = new Date((ba && b.arrived_at) || b.created_at).getTime()
  return ta - tb
}

/** Hành động kế tiếp admin bấm hộ được: bếp (bắt đầu / xong) và trạm 2 (giao).
 * Bước trạm 1 (đọc mã, thu tiền) làm ở màn hình nhân viên trạm 1. */
function nextAction(order) {
  switch (order.status) {
    case 'CONFIRMED':
      return { label: 'Bắt đầu làm', run: () => updateOrderStatus(order.id, 'PREPARING') }
    case 'PREPARING':
      return { label: 'Món đã xong', run: () => updateOrderStatus(order.id, 'READY') }
    case 'READY':
    case 'ARRIVED':
      return { label: 'Đã giao', run: () => updateOrderStatus(order.id, 'COMPLETED') }
    default:
      return null
  }
}

// Mệnh giá hay gặp để bấm nhanh số tiền khách đưa
const NOTES = [50000, 100000, 200000, 500000]

/** Hộp xác nhận thu tiền mặt: xem lại đơn, nhập tiền khách đưa để tính tiền thối. */
export function CashDialog({ order, busy, onConfirm, onCancel, confirmLabel }) {
  const total = order.total_amount
  const [given, setGiven] = useState('')
  const givenNum = Number(given.replace(/\D/g, '')) || 0
  const short = givenNum > 0 && givenNum < total
  const quick = [total, ...NOTES.filter((n) => n > total)].slice(0, 4)

  return (
    <ConfirmDialog
      title="Xác nhận thu tiền mặt"
      confirmLabel={confirmLabel || `Đã thu ${formatPrice(total)}`}
      confirmDisabled={short}
      tone="success"
      busy={busy}
      onConfirm={onConfirm}
      onCancel={onCancel}
    >
      <div className="cash-summary">
        <div>
          <span className="muted">Xe</span>
          <LicensePlate value={order.license_plate} size="lg" />
        </div>
        <div>
          <span className="muted">{order.pickup_code ? 'Mã' : 'Đơn'}</span>
          <strong>{order.pickup_code || `#${order.id}`}</strong>
        </div>
      </div>
      <ul className="cash-items">
        {order.items.map((i) => (
          <li key={i.menu_item_id}>
            <span>{i.quantity} × {i.item_name}</span>
            <span>{formatPrice(i.unit_price * i.quantity)}</span>
          </li>
        ))}
        {order.discount_amount > 0 && (
          <li className="muted">
            <span>Giảm giá{order.coupon_code ? ` (${order.coupon_code})` : ''}</span>
            <span>-{formatPrice(order.discount_amount)}</span>
          </li>
        )}
      </ul>
      <div className="cash-total">
        <span>Cần thu</span>
        <strong>{formatPrice(total)}</strong>
      </div>

      <label className="field">
        Khách đưa (không bắt buộc)
        <input
          inputMode="numeric"
          value={givenNum ? givenNum.toLocaleString('vi-VN') : ''}
          onChange={(e) => setGiven(e.target.value)}
          placeholder="Nhập số tiền để tính tiền thối"
        />
      </label>
      <div className="cash-quick">
        {quick.map((n) => (
          <button key={n} type="button" className="chip" onClick={() => setGiven(String(n))}>
            {n === total ? 'Vừa đủ' : formatPrice(n)}
          </button>
        ))}
      </div>
      {givenNum > 0 && (
        <p className={short ? 'error-text' : 'cash-change'}>
          {short
            ? `Còn thiếu ${formatPrice(total - givenNum)}`
            : `Tiền thối lại cho khách: ${formatPrice(givenNum - total)}`}
        </p>
      )}
    </ConfirmDialog>
  )
}

function Ticket({ order, stationName, flash, busy, onAction }) {
  const action = nextAction(order)
  const waited = minutesSince(order.created_at)
  const arrived = hasArrived(order)
  const carWait = order.arrived_at ? minutesSince(order.arrived_at) : null
  // Giờ xong đã hứa với khách: chỉ còn ý nghĩa khi bếp chưa làm xong
  const showEstimate = order.estimated_ready_at && ['CONFIRMED', 'PREPARING'].includes(order.status)
  const overdue = showEstimate && minutesUntil(order.estimated_ready_at) <= 0

  return (
    <li
      id={`ticket-${order.id}`}
      className={`ticket${arrived ? ' ticket-arrived' : ''}${flash ? ' ticket-flash' : ''}`}
    >
      {stationName && (
        <div className="station-tag">
          <Icon name="store" size={14} /> {stationName}
        </div>
      )}
      <div className="ticket-head">
        <LicensePlate value={order.license_plate} size="md" />
        <span className="ticket-id">
          {order.pickup_code ? `Mã ${order.pickup_code}` : `#${order.id}`}
        </span>
      </div>
      {arrived && (
        <div className="ticket-flag">
          <Icon name="car" size={18} /> Xe đã tới trạm 1
          {carWait !== null && ` · chờ ${formatDuration(carWait)}`}
          {order.status === 'PREPARING' && ' · làm nhanh'}
        </div>
      )}
      <ul className="ticket-items">
        {order.items.map((i) => (
          <li key={i.menu_item_id}>
            <strong>{i.quantity}×</strong> {i.item_name}
          </li>
        ))}
      </ul>
      <div className="ticket-meta">
        {order.payment_method ? METHOD_LABEL[order.payment_method] : STATUS_LABEL[order.status]} · {formatPrice(order.total_amount)}
        {' · '}
        <span className={`with-icon${waited >= 15 ? ' ticket-late' : ''}`}>
          <Icon name="clock" size={14} /> chờ {formatDuration(waited)}
        </span>
        {showEstimate && (
          <>
            {' · '}
            <span className={overdue ? 'ticket-late' : ''}>
              {overdue ? 'Trễ hẹn ' : 'Hẹn xong '}
              {formatTime(order.estimated_ready_at)}
            </span>
          </>
        )}
      </div>
      {action && (
        <button
          type="button"
          className="btn btn-block btn-small"
          disabled={busy}
          onClick={() => onAction(order, action)}
        >
          {busy ? 'Đang xử lý...' : action.label}
        </button>
      )}
    </li>
  )
}

/**
 * Bảng đơn hàng cho quầy. stationId bỏ trống = mọi cửa hàng (chỉ admin).
 * stationNames: {id: name} để hiện tên cửa hàng trên thẻ khi xem nhiều cửa hàng.
 */
export default function OrderBoard({ stationId, stationNames }) {
  const [orders, setOrders] = useState(null)
  const [recent, setRecent] = useState([])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [updatedAt, setUpdatedAt] = useState(null)
  const seen = useRef(null)
  const [cashFor, setCashFor] = useState(null) // { order, action } khi đang mở hộp thu tiền
  const [done, setDone] = useState('')
  // Thông báo trong nút chuông: đơn mới và xe đã tới. Mỗi đơn chỉ báo xe tới một lần.
  const announced = useRef(new Set())
  const [events, setEvents] = useState([])
  const [filter, setFilter] = useState('') // admin: lọc theo cửa hàng ('' = tất cả)
  const [flashId, setFlashId] = useState(null)

  const nameOf = useCallback(
    (id) => (stationNames ? stationNames[id] || `Cửa hàng #${id}` : ''),
    [stationNames],
  )

  const load = useCallback(async () => {
    try {
      const [queue, done] = await Promise.all([getQueue(stationId), getRecentOrders(stationId, 30)])
      const now = new Date()
      const fresh = []

      // Đơn mới xuất hiện kể từ lần tải trước (lần đầu mở màn hình thì không báo)
      if (seen.current) {
        queue
          .filter((o) => !seen.current.has(o.id))
          .forEach((o) =>
            fresh.push({
              key: `new-${o.id}`,
              type: 'new',
              orderId: o.id,
              stationId: o.station_id,
              title: `Đơn mới #${o.id} · ${formatPlate(o.license_plate)}`,
              detail: [nameOf(o.station_id), METHOD_LABEL[o.payment_method]].filter(Boolean).join(' · '),
              at: now,
              read: false,
            }),
          )
      }
      seen.current = new Set(queue.map((o) => o.id))

      // Xe báo tới quầy (kể cả xe đã chờ sẵn lúc mở màn hình)
      queue
        .filter((o) => hasArrived(o) && !announced.current.has(o.id))
        .forEach((o) => {
          announced.current.add(o.id)
          fresh.push({
            key: `arrived-${o.id}`,
            type: 'arrived',
            orderId: o.id,
            stationId: o.station_id,
            title: `Xe ${formatPlate(o.license_plate)} đã tới quầy`,
            detail: [`Đơn #${o.id}`, STATUS_LABEL[o.status], nameOf(o.station_id)].filter(Boolean).join(' · '),
            at: o.arrived_at ? new Date(o.arrived_at) : now,
            read: false,
          })
        })

      if (fresh.length) setEvents((list) => [...fresh.reverse(), ...list].slice(0, 30))
      setOrders(queue)
      setRecent(done)
      setError('')
      setUpdatedAt(new Date())
    } catch (err) {
      setError(errorMessage(err))
    }
  }, [stationId, nameOf])

  useEffect(() => {
    seen.current = null
    announced.current = new Set()
    setEvents([])
    setOrders(null)
    load()
    const timer = setInterval(() => {
      if (document.visibilityState === 'visible') load()
    }, POLL_MS)
    return () => clearInterval(timer)
  }, [load])

  async function runAction(order, action) {
    setBusyId(order.id)
    setNotice('')
    try {
      await action.run()
      if (action.cash) {
        setDone(`Đã thu ${formatPrice(order.total_amount)} của xe ${formatPlate(order.license_plate)} (đơn #${order.id}) và giao món.`)
      }
      setCashFor(null)
      await load()
    } catch (err) {
      setNotice(`Đơn #${order.id}: ${errorMessage(err)}`)
      setCashFor(null)
    } finally {
      setBusyId(null)
    }
  }

  function handleAction(order, action) {
    setDone('')
    // Thu tiền mặt: mở hộp xác nhận riêng thay vì bấm là xong
    if (action.cash) setCashFor({ order, action })
    else runAction(order, action)
  }

  // Bấm một thông báo: đánh dấu đã đọc, bỏ lọc nếu đơn bị ẩn, cuộn tới thẻ đơn và nháy sáng
  function pickEvent(ev) {
    setEvents((list) => list.map((e) => (e.key === ev.key ? { ...e, read: true } : e)))
    if (filter && filter !== ev.stationId) setFilter('')
    setTimeout(() => {
      const el = document.getElementById(`ticket-${ev.orderId}`)
      if (!el) {
        setNotice(`Đơn #${ev.orderId} không còn trong hàng đợi (đã giao hoặc đã hủy).`)
        return
      }
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      setFlashId(ev.orderId)
      setTimeout(() => setFlashId(null), 1600)
    }, 50)
  }

  if (!orders) {
    return error ? (
      <div className="state">
        <p className="error-text">{error}</p>
        <button type="button" className="btn" onClick={load}>Thử lại</button>
      </div>
    ) : (
      <div className="state">Đang tải đơn hàng...</div>
    )
  }

  // Admin xem mọi cửa hàng: có bộ lọc + nhãn màu cửa hàng trên từng thẻ
  const multiStation = !stationId && !!stationNames
  const stationIds = multiStation ? Object.keys(stationNames).map(Number) : []
  const shown = filter ? orders.filter((o) => o.station_id === filter) : orders
  const shownRecent = (filter ? recent.filter((o) => o.station_id === filter) : recent).slice(0, 10)
  const arrivedWaiting = shown.filter(hasArrived).length

  return (
    <div className="board-wrap">
      <div className="board-bar">
        <span>
          {shown.length} đơn đang xử lý
          {arrivedWaiting > 0 && (
            <strong className="bar-arrived"> · {arrivedWaiting} xe đang chờ ở quầy</strong>
          )}
          {updatedAt && ` · cập nhật lúc ${updatedAt.toLocaleTimeString('vi-VN')}`}
        </span>
        <NotificationBell
          items={events}
          onPick={pickEvent}
          onReadAll={() => setEvents((list) => list.map((e) => ({ ...e, read: true })))}
          onClear={() => setEvents([])}
        />
      </div>

      {multiStation && (
        <div className="station-filter" role="tablist" aria-label="Lọc theo cửa hàng">
          <button
            type="button"
            role="tab"
            aria-selected={!filter}
            className={`station-chip${!filter ? ' on' : ''}`}
            onClick={() => setFilter('')}
          >
            Tất cả <span className="badge">{orders.length}</span>
          </button>
          {stationIds.map((id) => {
            const count = orders.filter((o) => o.station_id === id).length
            const waiting = orders.filter((o) => o.station_id === id && hasArrived(o)).length
            return (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={filter === id}
                className={`station-chip${filter === id ? ' on' : ''}`}
                onClick={() => setFilter(id)}
              >
                {nameOf(id)} <span className="badge">{count}</span>
                {waiting > 0 && (
                  <span className="chip-car" title={`${waiting} xe đang chờ`}>
                    <Icon name="car" size={14} /> {waiting}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      )}

      {error && <div className="form-error" role="alert">Mất kết nối: {error}</div>}
      {notice && <div className="form-error" role="alert">{notice}</div>}
      {done && (
        <div className="form-success" role="status">
          <Icon name="check" size={18} strokeWidth={2.4} /> {done}
        </div>
      )}

      {cashFor && (
        <CashDialog
          order={cashFor.order}
          busy={busyId === cashFor.order.id}
          onConfirm={() => runAction(cashFor.order, cashFor.action)}
          onCancel={() => setCashFor(null)}
        />
      )}

      <div className="board">
        {COLUMNS.map((col) => {
          const list = shown.filter((o) => col.statuses.includes(o.status)).sort(byPriority)
          return (
            <section key={col.key} className="board-col">
              <h2>
                {col.title} <span className="badge">{list.length}</span>
              </h2>
              {list.length === 0 ? (
                <p className="board-empty">Không có đơn</p>
              ) : (
                <ul className="ticket-list">
                  {list.map((o) => (
                    <Ticket
                      key={o.id}
                      order={o}
                      stationName={multiStation ? nameOf(o.station_id) : ''}
                      flash={flashId === o.id}
                      busy={busyId === o.id}
                      onAction={handleAction}
                    />
                  ))}
                </ul>
              )}
            </section>
          )
        })}
      </div>

      {shownRecent.length > 0 && (
        <details className="recent">
          <summary>Đơn đã xong gần đây ({shownRecent.length})</summary>
          <table className="table">
            <thead>
              <tr>
                <th>Đơn</th>
                <th>Biển số</th>
                {multiStation && <th>Cửa hàng</th>}
                <th>Trạng thái</th>
                <th>Tổng</th>
                <th>Đặt lúc</th>
              </tr>
            </thead>
            <tbody>
              {shownRecent.map((o) => (
                <tr key={o.id}>
                  <td>#{o.id}</td>
                  <td><LicensePlate value={o.license_plate} size="sm" /></td>
                  {multiStation && (
                    <td>
                      {nameOf(o.station_id)}
                    </td>
                  )}
                  <td>
                    <span className={`status-pill status-${o.status.toLowerCase()}`}>
                      {STATUS_LABEL[o.status]}
                    </span>
                  </td>
                  <td>{formatPrice(o.total_amount)}</td>
                  <td>{formatDateTime(o.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </div>
  )
}
