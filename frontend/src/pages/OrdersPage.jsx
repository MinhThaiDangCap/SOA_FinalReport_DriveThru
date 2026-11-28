import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { errorMessage } from '../api/client.js'
import { getStations } from '../api/menu.js'
import { getMyOrders } from '../api/orders.js'
import { formatDateTime, formatPrice, STATUS_LABEL } from '../format.js'

export default function OrdersPage() {
  const [orders, setOrders] = useState(null)
  const [stations, setStations] = useState({})
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    getMyOrders()
      .then((data) => {
        if (!cancelled) setOrders(data)
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err))
      })
    getStations()
      .then((list) => {
        if (!cancelled) setStations(Object.fromEntries(list.map((s) => [s.id, s.name])))
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  if (error) {
    return (
      <div className="state">
        <p>{error}</p>
        <Link to="/" className="btn">Về trang chủ</Link>
      </div>
    )
  }
  if (!orders) {
    return (
      <div className="state">
        <p>Đang tải danh sách đơn...</p>
      </div>
    )
  }
  if (orders.length === 0) {
    return (
      <div className="state">
        <p>Bạn chưa có đơn hàng nào.</p>
        <Link to="/" className="btn">Đặt món ngay</Link>
      </div>
    )
  }

  return (
    <div className="checkout">
      <h1>Đơn của tôi</h1>
      <ul className="order-list">
        {orders.map((o) => (
          <li key={o.id}>
            <Link to={`/orders/${o.id}`} className="order-card">
              <div className="order-card-head">
                <strong>
                  Đơn #{o.id}
                  {o.pickup_code && !['COMPLETED', 'CANCELLED'].includes(o.status) && (
                    <span className="order-card-code"> · Mã {o.pickup_code}</span>
                  )}
                </strong>
                <span className={`status-pill status-${o.status.toLowerCase()}`}>
                  {STATUS_LABEL[o.status] || o.status}
                </span>
              </div>
              <div className="order-card-meta">
                {stations[o.station_id] || `Cửa hàng #${o.station_id}`} · {formatDateTime(o.created_at)}
              </div>
              <div className="order-card-items">
                {o.items.map((i) => `${i.quantity} × ${i.item_name}`).join(', ')}
              </div>
              <div className="order-card-total">{formatPrice(o.total_amount)}</div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}