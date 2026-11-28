import { useEffect, useState } from 'react'

import { getStations } from '../api/menu.js'
import ReviewsPanel from '../components/ReviewsPanel.jsx'
import StationOne from '../components/StationOne.jsx'
import StationTwo from '../components/StationTwo.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const TABS = [
  { key: 'station1', label: 'Trạm 1 · Xác nhận & thanh toán' },
  { key: 'station2', label: 'Trạm 2 · Giao món' },
  { key: 'reviews', label: 'Đánh giá' },
]

/** Màn hình nhân viên trạm (cùng vai trò STAFF, chọn trạm đang đứng). Chỉ thấy chi nhánh mình. */
export default function StaffPage() {
  const { user } = useAuth()
  const [tab, setTab] = useState(() => {
    try {
      return localStorage.getItem('golane_staff_tab') || 'station1'
    } catch {
      return 'station1'
    }
  })

  function pick(key) {
    setTab(key)
    try {
      localStorage.setItem('golane_staff_tab', key)
    } catch {
      /* không lưu được thì thôi */
    }
  }
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
          <p className="dash-eyebrow">Nhân viên trạm · Ca trực: {user?.full_name}</p>
          <h1>{stationName || `Cửa hàng #${stationId}`}</h1>
        </div>
        <div className="dash-live-pill">
          <span className="live-dot" /> Tự cập nhật mỗi 5 giây
        </div>
      </header>

      <nav className="category-tabs dash-tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            className={tab === t.key ? 'tab active' : 'tab'}
            onClick={() => pick(t.key)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {tab === 'station1' && <StationOne />}
      {tab === 'station2' && <StationTwo />}
      {tab === 'reviews' && <ReviewsPanel stationId={stationId} />}
    </div>
  )
}
