import { useCallback, useEffect, useRef, useState } from 'react'

import { errorMessage } from '../api/client.js'
import { getStations } from '../api/menu.js'
import { getKitchenQueue, updateOrderStatus } from '../api/staff.js'
import AvailabilityPanel from '../components/AvailabilityPanel.jsx'
import Icon from '../components/Icon.jsx'
import LicensePlate from '../components/LicensePlate.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { formatDuration, formatTime, minutesUntil } from '../format.js'

const POLL_MS = 5000
const AGING_MINUTES = 10 // khớp order-service: chờ quá 10 phút thì được đẩy lên đầu

function minutesSince(iso) {
  const t = new Date(iso).getTime()
  return Number.isNaN(t) ? 0 : Math.max(0, Math.floor((Date.now() - t) / 60000))
}

/** Lý do đơn đứng ở vị trí này trong hàng bếp. */
function reason(order) {
  if (order.status === 'PREPARING') return 'Đang làm'
  if (minutesSince(order.confirmed_at || order.created_at) >= AGING_MINUTES) return 'Chờ lâu · làm trước'
  return `Làm khoảng ${order.prep_minutes} phút`
}

/** Mở trang phiếu trong tab mới; trang phiếu tự gọi lệnh in (chọn máy in hoặc "Lưu dưới dạng PDF"). */
function printTicket(orderId) {
  window.open(`/kitchen/print/${orderId}`, '_blank', 'noopener')
}

function KitchenTicket({ order, index, busy, onAction }) {
  const preparing = order.status === 'PREPARING'
  const left = order.estimated_ready_at ? minutesUntil(order.estimated_ready_at) : null
  return (
    <li className={`ticket${preparing ? ' ticket-arrived' : ''}`}>
      <div className="ticket-head">
        <span className="pickup-chip">
          {index + 1}. Mã {order.pickup_code}
        </span>
        <LicensePlate value={order.license_plate} size="sm" />
      </div>
      <div className="ticket-flag">
        <Icon name={preparing ? 'flame' : 'timer'} size={16} /> {reason(order)}
      </div>
      <ul className="ticket-items">
        {order.items.map((i) => (
          <li key={i.menu_item_id}>
            <strong>{i.quantity}×</strong> {i.item_name}
          </li>
        ))}
      </ul>
      <div className="ticket-meta">
        Vào bếp {formatDuration(minutesSince(order.confirmed_at || order.created_at))} trước
        {order.estimated_ready_at && (
          <>
            {' · '}
            <span className={left !== null && left <= 0 ? 'ticket-late' : ''}>
              {left !== null && left <= 0 ? 'Trễ hẹn ' : 'Hẹn xong '}
              {formatTime(order.estimated_ready_at)}
            </span>
          </>
        )}
      </div>
      <div className="ticket-actions">
        <button type="button" className="btn btn-ghost btn-small" onClick={() => printTicket(order.id)}>
          <Icon name="printer" size={16} /> In phiếu
        </button>
        {preparing ? (
          <button type="button" className="btn btn-small" disabled={busy} onClick={() => onAction(order, 'READY')}>
            Đã dán phiếu · Món đã xong
          </button>
        ) : (
          <button type="button" className="btn btn-small" disabled={busy} onClick={() => onAction(order, 'PREPARING')}>
            Bắt đầu làm
          </button>
        )}
      </div>
    </li>
  )
}

function KitchenQueue() {
  const [orders, setOrders] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [notice, setNotice] = useState('')
  const [autoPrint, setAutoPrint] = useState(false)
  const printed = useRef(null)

  const load = useCallback(async () => {
    try {
      const list = await getKitchenQueue()
      // Tự in phiếu cho đơn mới vào bếp (bỏ qua các đơn đã có lúc mở màn hình)
      if (printed.current === null) printed.current = new Set(list.map((o) => o.id))
      list.forEach((o) => {
        if (!printed.current.has(o.id)) {
          printed.current.add(o.id)
          if (autoPrint) printTicket(o.id)
        }
      })
      setOrders(list)
      setNotice('')
    } catch (err) {
      setNotice(errorMessage(err))
    }
  }, [autoPrint])

  useEffect(() => {
    load()
    const timer = setInterval(() => {
      if (document.visibilityState === 'visible') load()
    }, POLL_MS)
    return () => clearInterval(timer)
  }, [load])

  async function act(order, status) {
    setBusyId(order.id)
    setNotice('')
    try {
      await updateOrderStatus(order.id, status)
      await load()
    } catch (err) {
      setNotice(`Mã ${order.pickup_code}: ${errorMessage(err)}`)
    } finally {
      setBusyId(null)
    }
  }

  if (orders === null) return <div className="state">Đang tải hàng đợi bếp...</div>

  return (
    <div className="board-wrap">
      <div className="board-bar">
        <span>
          {orders.length} đơn đã thanh toán · thứ tự làm: đơn đang làm, đơn chờ quá {AGING_MINUTES} phút,
          rồi đơn nhanh trước
        </span>
        <label className="auto-print">
          <input type="checkbox" checked={autoPrint} onChange={(e) => setAutoPrint(e.target.checked)} /> Tự in
          phiếu khi có đơn mới
        </label>
      </div>
      {notice && <div className="form-error" role="alert">{notice}</div>}
      {orders.length === 0 ? (
        <p className="board-empty">Chưa có đơn nào cần làm.</p>
      ) : (
        <ul className="ticket-list ticket-grid">
          {orders.map((o, i) => (
            <KitchenTicket key={o.id} order={o} index={i} busy={busyId === o.id} onAction={act} />
          ))}
        </ul>
      )}
      <p className="muted station-tip">
        Làm xong: dán phiếu lên túi, đặt ở cửa sổ trạm 2 rồi bấm "Món đã xong". Khách sẽ được mời
        ra trạm 2.
      </p>
    </div>
  )
}

const TABS = [
  { key: 'queue', label: 'Hàng đợi bếp' },
  { key: 'menu', label: 'Báo hết món' },
]

/** Màn hình bếp: chỉ thấy chi nhánh của tài khoản bếp. */
export default function KitchenPage() {
  const { user } = useAuth()
  const [tab, setTab] = useState('queue')
  const [stationName, setStationName] = useState('')
  const stationId = user?.station_id

  useEffect(() => {
    if (!stationId) return
    getStations()
      .then((list) => setStationName(list.find((s) => s.id === stationId)?.name || ''))
      .catch(() => {})
  }, [stationId])

  if (!stationId) {
    return (
      <div className="state">
        <p>Tài khoản bếp chưa được gán chi nhánh. Hãy liên hệ quản trị viên.</p>
      </div>
    )
  }

  return (
    <div className="dash">
      <header className="dash-head">
        <div>
          <p className="dash-eyebrow">Bếp · {user?.full_name}</p>
          <h1>{stationName || `Chi nhánh #${stationId}`}</h1>
        </div>
        <div className="dash-live-pill">
          <span className="live-dot" /> Tự cập nhật mỗi 5 giây
        </div>
      </header>
      <nav className="category-tabs dash-tabs">
        {TABS.map((t) => (
          <button key={t.key} type="button" className={tab === t.key ? 'tab active' : 'tab'} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </nav>
      {tab === 'queue' && <KitchenQueue />}
      {tab === 'menu' && <AvailabilityPanel stationId={stationId} />}
    </div>
  )
}
