import { useCallback, useEffect, useState } from 'react'

import { errorMessage } from '../api/client.js'
import { getStationMenu, setItemAvailability } from '../api/menu.js'
import { formatPrice } from '../format.js'

/** Bật/tắt "hết món" trong ngày cho một cửa hàng. */
export default function AvailabilityPanel({ stationId }) {
  const [menu, setMenu] = useState(null)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)

  const load = useCallback(() => {
    setError('')
    getStationMenu(stationId)
      .then(setMenu)
      .catch((err) => setError(errorMessage(err)))
  }, [stationId])

  useEffect(() => {
    setMenu(null)
    load()
  }, [load])

  async function toggle(item) {
    setBusyId(item.id)
    setError('')
    try {
      await setItemAvailability(stationId, item.id, !item.available)
      setMenu((m) => ({
        ...m,
        categories: m.categories.map((c) => ({
          ...c,
          items: c.items.map((i) => (i.id === item.id ? { ...i, available: !i.available } : i)),
        })),
      }))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  if (!menu) {
    return error ? <p className="form-error">{error}</p> : <div className="state">Đang tải món...</div>
  }

  const soldOut = menu.categories.flatMap((c) => c.items).filter((i) => !i.available).length

  return (
    <div>
      <p className="panel-hint">
        Món tắt sẽ hiện "Hết món" với khách và không đặt được. Hiện có <strong>{soldOut}</strong> món đang hết.
      </p>
      {error && <div className="form-error" role="alert">{error}</div>}
      {menu.categories.map((cat) => (
        <section key={cat.id} className="panel-section">
          <h3>{cat.name}</h3>
          <ul className="avail-list">
            {cat.items.map((item) => (
              <li key={item.id} className={item.available ? '' : 'avail-off'}>
                <div>
                  <strong>{item.name}</strong>
                  <span className="muted"> · {formatPrice(item.price)}</span>
                </div>
                <label className="switch">
                  <input
                    type="checkbox"
                    checked={item.available}
                    disabled={busyId === item.id}
                    onChange={() => toggle(item)}
                  />
                  <span>{item.available ? 'Còn món' : 'Hết món'}</span>
                </label>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}
