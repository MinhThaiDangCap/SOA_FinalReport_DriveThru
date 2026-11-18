import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { errorMessage } from '../api/client.js'
import { getStations } from '../api/menu.js'
import { getMyOrders, getWaitTimes } from '../api/orders.js'
import { getStationStats } from '../api/reviews.js'
import { useAuth } from '../context/AuthContext.jsx'
import { formatPrice, STATUS_LABEL } from '../format.js'

const STEPS = [
  { icon: '📍', title: 'Chọn cửa hàng', text: 'Chọn quán gần bạn, xem menu và thời gian chờ.' },
  { icon: '📱', title: 'Đặt & trả trước', text: 'Thanh toán MoMo hoặc trả tại quầy khi nhận món.' },
  { icon: '🚗', title: 'Lái xe tới nhận', text: 'Bấm "Tôi đã đến", nhân viên nhận diện biển số và giao món.' },
]

const ACTIVE = ['PENDING_PAYMENT', 'CONFIRMED', 'PREPARING', 'READY', 'ARRIVED']

/** "06:00 - 23:00" | "24/7" -> đang mở cửa không (theo giờ máy người dùng). null = không rõ. */
export function isOpenNow(hours, now = new Date()) {
  if (!hours) return null
  if (/24\s*\/\s*7/.test(hours)) return true
  const m = hours.match(/(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})/)
  if (!m) return null
  const open = Number(m[1]) * 60 + Number(m[2])
  const close = Number(m[3]) * 60 + Number(m[4])
  const cur = now.getHours() * 60 + now.getMinutes()
  // Mở qua đêm, ví dụ 18:00 - 02:00
  return open <= close ? cur >= open && cur < close : cur >= open || cur < close
}

function ActiveOrders() {
  const [orders, setOrders] = useState([])

  useEffect(() => {
    let cancelled = false
    getMyOrders()
      .then((list) => !cancelled && setOrders(list.filter((o) => ACTIVE.includes(o.status))))
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  if (orders.length === 0) return null

  return (
    <section className="active-orders">
      <h2>Đơn đang xử lý</h2>
      <ul>
        {orders.slice(0, 3).map((o) => (
          <li key={o.id}>
            <Link to={`/orders/${o.id}`} className="active-order">
              <span>
                <strong>Đơn #{o.id}</strong> · {o.license_plate} · {formatPrice(o.total_amount)}
              </span>
              <span className={`status-pill status-${o.status.toLowerCase()}`}>
                {STATUS_LABEL[o.status]}
              </span>
            </Link>
          </li>
        ))}
      </ul>
      {orders.length > 3 && (
        <Link to="/orders" className="active-more">Xem tất cả {orders.length} đơn →</Link>
      )}
    </section>
  )
}

function StationCard({ station, wait, rating }) {
  const open = isOpenNow(station.opening_hours)

  return (
    <Link to={`/stations/${station.id}`} className={`station-card${open === false ? ' station-closed' : ''}`}>
      <div className="station-top">
        <h2>{station.name}</h2>
        {open !== null && (
          <span className={`open-tag ${open ? 'open-yes' : 'open-no'}`}>
            {open ? 'Đang mở cửa' : 'Đã đóng cửa'}
          </span>
        )}
      </div>
      <p className="station-address">{station.address}</p>
      {station.opening_hours && <p className="station-hours">🕒 {station.opening_hours}</p>}

      <div className="station-facts">
        <span title="Ước tính cho đơn đặt bây giờ">
          ⏱ ~{wait?.estimated_minutes ?? 5} phút
          <small> · {wait?.queue_count ?? 0} đơn đang chờ</small>
        </span>
        <span className="station-rating">
          {rating && rating.total_reviews > 0
            ? `★ ${rating.average_rating.toFixed(1)} (${rating.total_reviews})`
            : '☆ Chưa có đánh giá'}
        </span>
      </div>
      <span className="station-cta">{open === false ? 'Xem menu (đặt trước) →' : 'Xem menu & đặt món →'}</span>
    </Link>
  )
}

export default function StationsPage() {
  const { user } = useAuth()
  const [stations, setStations] = useState(null)
  const [waits, setWaits] = useState({})
  const [ratings, setRatings] = useState({})
  const [query, setQuery] = useState('')
  const [onlyOpen, setOnlyOpen] = useState(false)
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    setError('')
    setStations(null)
    getStations()
      .then((data) => {
        if (cancelled) return
        setStations(data)
        // Điểm đánh giá: mỗi quán một request, lỗi thì bỏ qua (không chặn trang)
        Promise.all(
          data.map((s) =>
            getStationStats(s.id)
              .then((r) => [s.id, r])
              .catch(() => [s.id, null]),
          ),
        ).then((pairs) => !cancelled && setRatings(Object.fromEntries(pairs)))
      })
      .catch((err) => !cancelled && setError(errorMessage(err)))
    getWaitTimes()
      .then((list) => !cancelled && setWaits(Object.fromEntries(list.map((w) => [w.station_id, w]))))
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [reloadKey])

  const shown = useMemo(() => {
    if (!stations) return []
    const q = query.trim().toLowerCase()
    return stations
      .filter((s) => !q || `${s.name} ${s.address}`.toLowerCase().includes(q))
      .filter((s) => !onlyOpen || isOpenNow(s.opening_hours) !== false)
      // Quán đang mở lên trước, rồi quán ít đơn chờ hơn
      .sort((a, b) => {
        const oa = isOpenNow(a.opening_hours) === false ? 1 : 0
        const ob = isOpenNow(b.opening_hours) === false ? 1 : 0
        if (oa !== ob) return oa - ob
        return (waits[a.id]?.queue_count ?? 0) - (waits[b.id]?.queue_count ?? 0)
      })
  }, [stations, query, onlyOpen, waits])

  return (
    <>
      {user?.role === 'CUSTOMER' && <ActiveOrders />}

      <section className="hero hero-home">
        <div>
          <p className="dash-eyebrow">Drive-Thru · Đặt trước, không cần xuống xe</p>
          <h1>Đặt trước, lái xe qua, nhận món</h1>
          <p>
            Chọn cửa hàng bạn sẽ ghé, đặt món và thanh toán ngay trên web. Tới nơi chỉ cần bấm
            "Tôi đã đến", món được mang ra tận xe.
          </p>
          {!user && (
            <div className="hero-actions">
              <a href="#stations" className="btn">Chọn cửa hàng</a>
              <Link to="/register" className="btn btn-ghost">Tạo tài khoản</Link>
            </div>
          )}
        </div>
        <ol className="steps">
          {STEPS.map((s, i) => (
            <li key={s.title}>
              <span className="step-icon" aria-hidden="true">{s.icon}</span>
              <div>
                <strong>{i + 1}. {s.title}</strong>
                <p>{s.text}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section id="stations">
        <div className="stations-head">
          <h2>Cửa hàng {stations && <span className="muted">({shown.length})</span>}</h2>
          <div className="stations-filter">
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Tìm theo tên hoặc địa chỉ..."
              aria-label="Tìm cửa hàng"
            />
            <label className="check">
              <input type="checkbox" checked={onlyOpen} onChange={(e) => setOnlyOpen(e.target.checked)} />
              Chỉ quán đang mở
            </label>
          </div>
        </div>

        {error && (
          <div className="state">
            <p className="error-text">{error}</p>
            <button className="btn" onClick={() => setReloadKey((k) => k + 1)}>
              Thử lại
            </button>
          </div>
        )}

        {!error && stations === null && <div className="state">Đang tải danh sách cửa hàng…</div>}

        {stations?.length === 0 && (
          <div className="state">Hiện chưa có cửa hàng nào đang hoạt động.</div>
        )}

        {stations?.length > 0 && shown.length === 0 && (
          <div className="state">Không tìm thấy cửa hàng phù hợp.</div>
        )}

        {shown.length > 0 && (
          <ul className="station-grid">
            {shown.map((station) => (
              <li key={station.id}>
                <StationCard station={station} wait={waits[station.id]} rating={ratings[station.id]} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  )
}
