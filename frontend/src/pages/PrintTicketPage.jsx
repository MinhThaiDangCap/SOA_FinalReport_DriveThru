import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import { errorMessage } from '../api/client.js'
import { getStations } from '../api/menu.js'
import { getOrderDetail } from '../api/staff.js'
import { formatDateTime, formatPrice } from '../format.js'

/**
 * Phiếu bếp khổ 80mm (máy in nhiệt ở quầy). Bếp dán phiếu lên túi để trạm 2 giao đúng xe.
 * Mở trang là tự gọi lệnh in của trình duyệt; không có máy in thì chọn "Lưu dưới dạng PDF".
 */
export default function PrintTicketPage() {
  const { orderId } = useParams()
  const [order, setOrder] = useState(null)
  const [stationName, setStationName] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    getOrderDetail(orderId)
      .then(setOrder)
      .catch((err) => setError(errorMessage(err)))
    getStations()
      .then((list) => setStationName(Object.fromEntries(list.map((s) => [s.id, s.name]))))
      .catch(() => {})
  }, [orderId])

  useEffect(() => {
    if (!order) return undefined
    // Tên file gợi ý khi "Lưu dưới dạng PDF"
    const old = document.title
    document.title = `Phieu_${order.pickup_code}`
    const timer = setTimeout(() => window.print(), 300)
    return () => {
      clearTimeout(timer)
      document.title = old
    }
  }, [order])

  if (error) return <div className="state"><p>{error}</p></div>
  if (!order) return <div className="state">Đang tải phiếu...</div>

  const station = typeof stationName === 'object' ? stationName[order.station_id] : ''
  const qty = order.items.reduce((n, i) => n + i.quantity, 0)

  return (
    <div className="print-ticket">
      <div className="pt-brand">GoLane Drive-Thru</div>
      <div className="pt-station">{station || `Chi nhánh #${order.station_id}`}</div>
      <div className="pt-code-label">MÃ NHẬN MÓN</div>
      <div className="pt-code">{order.pickup_code}</div>
      <div className="pt-plate">{order.license_plate}</div>
      <hr />
      <ul className="pt-items">
        {order.items.map((i) => (
          <li key={i.menu_item_id}>
            <strong>{i.quantity} ×</strong> {i.item_name}
          </li>
        ))}
      </ul>
      <hr />
      <div className="pt-row">
        <span>{qty} phần</span>
        <span>{formatPrice(order.total_amount)}</span>
      </div>
      <div className="pt-row">
        <span>Đơn #{order.id}</span>
        <span>{formatDateTime(order.confirmed_at || order.created_at)}</span>
      </div>
      <p className="pt-foot">Trạm 2: đối chiếu mã + biển số trước khi giao</p>
      <button type="button" className="btn no-print" onClick={() => window.print()}>
        In lại
      </button>
    </div>
  )
}
