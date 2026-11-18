import { useCallback, useEffect, useRef, useState } from 'react'

import { errorMessage } from '../api/client.js'
import { confirmCash, getQueue, getRecentOrders, updateOrderStatus } from '../api/staff.js'
import { formatDateTime, formatPrice, METHOD_LABEL, STATUS_LABEL } from '../format.js'
import ConfirmDialog from './ConfirmDialog.jsx'
import Icon from './Icon.jsx'

const POLL_MS = 5000

const COLUMNS = [
  { key: 'new', title: 'Đơn mới', statuses: ['CONFIRMED'] },
  { key: 'cooking', title: 'Đang làm', statuses: ['PREPARING'] },
  { key: 'pickup', title: 'Chờ giao', statuses: ['ARRIVED', 'READY'] },
]

function minutesSince(iso) {
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return 0
  return Math.max(0, Math.floor((Date.now() - t) / 60000))
}

/** Hành động kế tiếp của một đơn: mỗi thẻ chỉ có đúng một nút chính. */
function nextAction(order) {
  switch (order.status) {
    case 'CONFIRMED':
      return { label: 'Bắt đầu làm', run: () => updateOrderStatus(order.id, 'PREPARING') }
    case 'PREPARING':
      return { label: 'Món đã xong', run: () => updateOrderStatus(order.id, 'READY') }
    case 'READY':
    case 'ARRIVED':
      if (order.payment_method === 'CASH') {
        return {
          label: `Thu ${formatPrice(order.total_amount)} & giao món`,
          cash: true,
          run: async () => {
            await confirmCash(order.id)
            return updateOrderStatus(order.id, 'COMPLETED', 'Đã thu tiền mặt và giao món')
          },
        }
      }
      return { label: 'Đã giao món', run: () => updateOrderStatus(order.id, 'COMPLETED') }
    default:
      return null
  }
}

// Mệnh giá hay gặp để bấm nhanh số tiền khách đưa
const NOTES = [50000, 100000, 200000, 500000]

/** Hộp xác nhận thu tiền mặt: xem lại đơn, nhập tiền khách đưa để tính tiền thối. */
function CashDialog({ order, busy, onConfirm, onCancel }) {
  const total = order.total_amount
  const [given, setGiven] = useState('')
  const givenNum = Number(given.replace(/\D/g, '')) || 0
  const short = givenNum > 0 && givenNum < total
  const quick = [total, ...NOTES.filter((n) => n > total)].slice(0, 4)

  return (
    <ConfirmDialog
      title="Xác nhận thu tiền mặt"
      confirmLabel={`Đã thu ${formatPrice(total)} · giao món`}
      confirmDisabled={short}
      tone="success"
      busy={busy}
      onConfirm={onConfirm}
      onCancel={onCancel}
    >
      <div className="cash-summary">
        <div>
          <span className="muted">Xe</span>
          <strong className="cash-plate">{order.license_plate}</strong>
        </div>
        <div>
          <span className="muted">Đơn</span>
          <strong>#{order.id}</strong>
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

function Ticket({ order, stationName, busy, onAction }) {
  const action = nextAction(order)
  const waited = minutesSince(order.created_at)
  const arrived = order.status === 'ARRIVED'

  return (
    <li className={`ticket${arrived ? ' ticket-arrived' : ''}`}>
      <div className="ticket-head">
        <span className="ticket-plate">{order.license_plate}</span>
        <span className="ticket-id">#{order.id}</span>
      </div>
      {arrived && (
        <div className="ticket-flag">
          <Icon name="car" size={18} /> Xe đã tới quầy
        </div>
      )}
      {stationName && <div className="ticket-meta">{stationName}</div>}
      <ul className="ticket-items">
        {order.items.map((i) => (
          <li key={i.menu_item_id}>
            <strong>{i.quantity}×</strong> {i.item_name}
          </li>
        ))}
      </ul>
      <div className="ticket-meta">
        {METHOD_LABEL[order.payment_method] || order.payment_method} · {formatPrice(order.total_amount)}
        {' · '}
        <span className={`with-icon${waited >= 15 ? ' ticket-late' : ''}`}>
          <Icon name="clock" size={14} /> chờ {waited} phút
        </span>
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
  const [newCount, setNewCount] = useState(0)
  const [cashFor, setCashFor] = useState(null) // { order, action } khi đang mở hộp thu tiền
  const [done, setDone] = useState('')

  const load = useCallback(async () => {
    try {
      const [queue, done] = await Promise.all([getQueue(stationId), getRecentOrders(stationId, 10)])
      // Đếm đơn mới xuất hiện kể từ lần tải trước để báo cho quầy
      const ids = new Set(queue.map((o) => o.id))
      if (seen.current) {
        const fresh = queue.filter((o) => !seen.current.has(o.id)).length
        if (fresh > 0) setNewCount((n) => n + fresh)
      }
      seen.current = ids
      setOrders(queue)
      setRecent(done)
      setError('')
      setUpdatedAt(new Date())
    } catch (err) {
      setError(errorMessage(err))
    }
  }, [stationId])

  useEffect(() => {
    seen.current = null
    setOrders(null)
    setNewCount(0)
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
        setDone(`Đã thu ${formatPrice(order.total_amount)} của xe ${order.license_plate} (đơn #${order.id}) và giao món.`)
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

  const showStation = !stationId && stationNames

  return (
    <div className="board-wrap">
      <div className="board-bar">
        <span>
          {orders.length} đơn đang xử lý
          {updatedAt && ` · cập nhật lúc ${updatedAt.toLocaleTimeString('vi-VN')}`}
        </span>
        {newCount > 0 && (
          <button type="button" className="new-badge" onClick={() => setNewCount(0)}>
            <Icon name="bell" size={16} /> +{newCount} đơn mới <Icon name="x" size={14} label="Ẩn thông báo" />
          </button>
        )}
      </div>
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
          const list = col.statuses.flatMap((s) => orders.filter((o) => o.status === s))
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
                      stationName={showStation ? stationNames[o.station_id] || `Cửa hàng #${o.station_id}` : ''}
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

      {recent.length > 0 && (
        <details className="recent">
          <summary>Đơn đã xong gần đây ({recent.length})</summary>
          <table className="table">
            <thead>
              <tr>
                <th>Đơn</th>
                <th>Biển số</th>
                {showStation && <th>Cửa hàng</th>}
                <th>Trạng thái</th>
                <th>Tổng</th>
                <th>Đặt lúc</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((o) => (
                <tr key={o.id}>
                  <td>#{o.id}</td>
                  <td>{o.license_plate}</td>
                  {showStation && <td>{stationNames[o.station_id] || `#${o.station_id}`}</td>}
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
