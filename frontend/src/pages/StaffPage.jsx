import { useEffect, useState } from 'react'

import { getStations } from '../api/menu.js'
import AvailabilityPanel from '../components/AvailabilityPanel.jsx'
import OrderBoard from '../components/OrderBoard.jsx'
import ReviewsPanel from '../components/ReviewsPanel.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const TABS = [
  { key: 'orders', label: 'Đơn hàng' },
  { key: 'menu', label: 'Món hôm nay' },
  { key: 'reviews', label: 'Đánh giá' },
]

/** Màn hình quầy của nhân viên: chỉ thấy cửa hàng mình được gán. */
export default function StaffPage() {
  const { user } = useAuth()
  const [tab, setTab] = useState('orders')
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
        <p>Tài khoản của bạn chưa được gán cửa hàng. Hãy liên hệ quản trị viên.</p>
      </div>
    )
  }

  return (
    <div className="dash">
      <header className="dash-head">
        <div>
          <p className="dash-eyebrow">Màn hình quầy</p>
          <h1>{stationName || `Cửa hàng #${stationId}`}</h1>
        </div>
      </header>

      <nav className="category-tabs dash-tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            className={tab === t.key ? 'tab active' : 'tab'}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {tab === 'orders' && <OrderBoard stationId={stationId} />}
      {tab === 'menu' && <AvailabilityPanel stationId={stationId} />}
      {tab === 'reviews' && <ReviewsPanel stationId={stationId} />}
    </div>
  )
}
