import { useEffect, useState } from 'react'

import { getOrderStats } from '../../api/admin.js'
import { errorMessage } from '../../api/client.js'
import { getStationStats } from '../../api/reviews.js'
import { formatPrice } from '../../format.js'

/** Tổng quan: doanh thu, số đơn và điểm đánh giá theo từng cửa hàng. */
export default function OverviewTab({ stations }) {
  const [stats, setStats] = useState(null)
  const [ratings, setRatings] = useState({})
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    getOrderStats()
      .then((s) => !cancelled && setStats(s))
      .catch((err) => !cancelled && setError(errorMessage(err)))
    Promise.all(
      stations.map((s) =>
        getStationStats(s.id)
          .then((r) => [s.id, r])
          .catch(() => [s.id, null]),
      ),
    ).then((pairs) => !cancelled && setRatings(Object.fromEntries(pairs)))
    return () => {
      cancelled = true
    }
  }, [stations])

  if (error) return <p className="form-error">{error}</p>
  if (!stats) return <div className="state">Đang tải thống kê...</div>

  const byStation = Object.fromEntries(stats.map((s) => [s.station_id, s]))
  const sum = (key) => stats.reduce((t, s) => t + s[key], 0)

  const cards = [
    { label: 'Doanh thu hôm nay', value: formatPrice(sum('today_revenue')) },
    { label: 'Đơn hôm nay', value: sum('today_orders') },
    { label: 'Đơn đang xử lý', value: sum('active_orders') },
    { label: 'Tổng doanh thu', value: formatPrice(sum('revenue')) },
    { label: 'Đơn hoàn thành', value: sum('completed_orders') },
    { label: 'Đơn đã hủy', value: sum('cancelled_orders') },
  ]

  return (
    <div>
      <div className="stat-grid">
        {cards.map((c) => (
          <div key={c.label} className="stat-card">
            <span>{c.label}</span>
            <strong>{c.value}</strong>
          </div>
        ))}
      </div>

      <h2 className="panel-title">Theo cửa hàng</h2>
      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th>Cửa hàng</th>
              <th>Đơn hôm nay</th>
              <th>Doanh thu hôm nay</th>
              <th>Đang xử lý</th>
              <th>Hoàn thành</th>
              <th>Đã hủy</th>
              <th>Tổng doanh thu</th>
              <th>Đánh giá</th>
            </tr>
          </thead>
          <tbody>
            {stations.map((st) => {
              const s = byStation[st.id]
              const r = ratings[st.id]
              return (
                <tr key={st.id} className={st.is_active ? '' : 'row-off'}>
                  <td>
                    <strong>{st.name}</strong>
                    {!st.is_active && <span className="muted"> (ngừng hoạt động)</span>}
                  </td>
                  <td>{s?.today_orders ?? 0}</td>
                  <td>{formatPrice(s?.today_revenue ?? 0)}</td>
                  <td>{s?.active_orders ?? 0}</td>
                  <td>{s?.completed_orders ?? 0}</td>
                  <td>{s?.cancelled_orders ?? 0}</td>
                  <td>{formatPrice(s?.revenue ?? 0)}</td>
                  <td>
                    {r && r.total_reviews > 0
                      ? `${r.average_rating.toFixed(1)}★ (${r.total_reviews})`
                      : '–'}
                    {r?.negative_reviews?.length > 0 && (
                      <span className="tag-bad"> {r.negative_reviews.length} tiêu cực</span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="panel-hint">
        Doanh thu chỉ tính đơn đã hoàn thành. Theo dõi hệ thống chi tiết hơn tại{' '}
        <a href="http://localhost:3000" target="_blank" rel="noreferrer">Grafana</a>.
      </p>
    </div>
  )
}
