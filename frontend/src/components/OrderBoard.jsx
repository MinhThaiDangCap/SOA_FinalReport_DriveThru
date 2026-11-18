import { useCallback, useEffect, useRef, useState } from 'react'

import { errorMessage } from '../api/client.js'
import { confirmCash, getQueue, getRecentOrders, updateOrderStatus } from '../api/staff.js'
import { formatDateTime, formatPrice, METHOD_LABEL, STATUS_LABEL } from '../format.js'

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
          confirm: `Xác nhận đã thu ${formatPrice(order.total_amount)} tiền mặt của xe ${order.license_plate}?`,
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
      {arrived && <div className="ticket-flag">🚗 Xe đã tới quầy</div>}
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
        <span className={waited >= 15 ? 'ticket-late' : ''}>chờ {waited} phút</span>
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

  async function handleAction(order, action) {
    if (action.confirm && !window.confirm(action.confirm)) return
    setBusyId(order.id)
    setNotice('')
    try {
      await action.run()
      await load()
    } catch (err) {
      setNotice(`Đơn #${order.id}: ${errorMessage(err)}`)
    } finally {
      setBusyId(null)
    }
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
            +{newCount} đơn mới ✕
          </button>
        )}
      </div>
      {error && <div className="form-error" role="alert">Mất kết nối: {error}</div>}
      {notice && <div className="form-error" role="alert">{notice}</div>}

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
