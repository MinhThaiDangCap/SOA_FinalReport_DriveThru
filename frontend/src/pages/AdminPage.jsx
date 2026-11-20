import { useCallback, useEffect, useMemo, useState } from 'react'

import { errorMessage } from '../api/client.js'
import { getAllStations } from '../api/menu.js'
import CouponsTab from '../components/admin/CouponsTab.jsx'
import MenuTab from '../components/admin/MenuTab.jsx'
import OverviewTab from '../components/admin/OverviewTab.jsx'
import StaffTab from '../components/admin/StaffTab.jsx'
import StationsTab from '../components/admin/StationsTab.jsx'
import OrderBoard from '../components/OrderBoard.jsx'
import ReviewsPanel from '../components/ReviewsPanel.jsx'

const TABS = [
  { key: 'overview', label: 'Tổng quan' },
  { key: 'orders', label: 'Đơn hàng' },
  { key: 'stations', label: 'Cửa hàng' },
  { key: 'menu', label: 'Thực đơn' },
  { key: 'staff', label: 'Nhân viên' },
  { key: 'coupons', label: 'Mã giảm giá' },
  { key: 'reviews', label: 'Đánh giá' },
]

/** Chọn cửa hàng cho các tab xem theo từng cửa hàng. allowAll = có lựa chọn "Tất cả". */
function StationPicker({ stations, value, onChange, allowAll }) {
  return (
    <label className="picker">
      Cửa hàng:{' '}
      <select value={value} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : '')}>
        {allowAll && <option value="">Tất cả cửa hàng</option>}
        {stations.map((s) => (
          <option key={s.id} value={s.id}>{s.name}</option>
        ))}
      </select>
    </label>
  )
}

export default function AdminPage() {
  const [tab, setTab] = useState('overview')
  const [stations, setStations] = useState(null)
  const [error, setError] = useState('')
  const [reviewStation, setReviewStation] = useState('')
  // useMemo: giữ nguyên object giữa các lần render, để màn hình đơn không tải lại liên tục
  const names = useMemo(
    () => (stations ? Object.fromEntries(stations.map((s) => [s.id, s.name])) : null),
    [stations],
  )

  const loadStations = useCallback(() => {
    getAllStations()
      .then((list) => {
        setStations(list)
        setReviewStation((v) => v || list[0]?.id || '')
      })
      .catch((err) => setError(errorMessage(err)))
  }, [])

  useEffect(loadStations, [loadStations])

  if (error) {
    return (
      <div className="state">
        <p className="error-text">{error}</p>
        <button type="button" className="btn" onClick={loadStations}>Thử lại</button>
      </div>
    )
  }
  if (!stations) return <div className="state">Đang tải...</div>

  return (
    <div className="dash">
      <header className="dash-head">
        <div>
          <p className="dash-eyebrow">Quản trị hệ thống · Chuỗi GoLane ({stations.length} chi nhánh)</p>
          <h1>{TABS.find((t) => t.key === tab)?.label}</h1>
        </div>
        <div className="dash-head-actions">
          {tab === 'reviews' && (
            <StationPicker stations={stations} value={reviewStation} onChange={setReviewStation} />
          )}
          <a
            href="http://localhost:3000"
            target="_blank"
            rel="noreferrer"
            className="btn btn-ghost btn-small"
          >
            Giám sát Grafana ↗
          </a>
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

      {tab === 'overview' && <OverviewTab stations={stations} />}
      {tab === 'orders' && <OrderBoard stationNames={names} />}
      {tab === 'stations' && <StationsTab stations={stations} onChanged={loadStations} />}
      {tab === 'menu' && <MenuTab />}
      {tab === 'staff' && <StaffTab stations={stations} />}
      {tab === 'coupons' && <CouponsTab />}
      {tab === 'reviews' && reviewStation && <ReviewsPanel stationId={reviewStation} />}
    </div>
  )
}
