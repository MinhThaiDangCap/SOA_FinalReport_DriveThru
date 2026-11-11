import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { errorMessage } from '../api/client.js'
import { getStations } from '../api/menu.js'

export default function StationsPage() {
  const [stations, setStations] = useState(null)
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    setError('')
    setStations(null)
    getStations()
      .then((data) => !cancelled && setStations(data))
      .catch((err) => !cancelled && setError(errorMessage(err)))
    return () => {
      cancelled = true
    }
  }, [reloadKey])

  return (
    <>
      <section className="hero">
        <h1>Đặt trước, lái xe qua, nhận món</h1>
        <p>Chọn cửa hàng bạn sẽ ghé để xem menu và đặt món.</p>
      </section>

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

      {stations?.length > 0 && (
        <ul className="station-grid">
          {stations.map((station) => (
            <li key={station.id}>
              <Link to={`/stations/${station.id}`} className="station-card">
                <h2>{station.name}</h2>
                <p className="station-address">{station.address}</p>
                {station.opening_hours && (
                  <p className="station-hours">Giờ mở cửa: {station.opening_hours}</p>
                )}
                <span className="station-cta">Xem menu →</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
