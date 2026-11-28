import { useCallback, useEffect, useState } from 'react'

import { errorMessage } from '../api/client.js'
import { getReadyOrders, updateOrderStatus } from '../api/staff.js'
import { formatTime } from '../format.js'
import ConfirmDialog from './ConfirmDialog.jsx'
import Icon from './Icon.jsx'
import LicensePlate from './LicensePlate.jsx'

const POLL_MS = 5000

/**
 * Trạm 2 (trang tối giản, dùng được trên điện thoại / máy tính bảng):
 * các đơn bếp đã làm xong (túi đã dán phiếu). Khách đọc mã, nhân viên chạm thẻ hoặc gõ mã,
 * nhìn camera đối chiếu biển số rồi bấm "Đã giao".
 */
export default function StationTwo() {
  const [orders, setOrders] = useState(null)
  const [code, setCode] = useState('')
  const [picked, setPicked] = useState(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [done, setDone] = useState('')

  const load = useCallback(async () => {
    try {
      setOrders(await getReadyOrders())
    } catch (err) {
      setNotice(errorMessage(err))
    }
  }, [])

  useEffect(() => {
    load()
    const timer = setInterval(() => {
      if (document.visibilityState === 'visible') load()
    }, POLL_MS)
    return () => clearInterval(timer)
  }, [load])

  function findByCode(e) {
    e.preventDefault()
    setNotice('')
    const found = (orders || []).find((o) => o.pickup_code === code.trim())
    if (found) setPicked(found)
    else setNotice(`Không có đơn đã xong mang mã ${code.trim()}. Món có thể chưa xong hoặc khách đọc nhầm mã.`)
  }

  async function deliver() {
    setBusy(true)
    try {
      await updateOrderStatus(picked.id, 'COMPLETED', 'Trạm 2 đã giao món')
      setDone(`Đã giao mã ${picked.pickup_code} cho xe ${picked.license_plate}.`)
      setCode('')
      setPicked(null)
      await load()
    } catch (err) {
      setNotice(errorMessage(err))
      setPicked(null)
      await load()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="board-wrap station-two">
      <form className="station-search" onSubmit={findByCode}>
        <input
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 4))}
          placeholder="Mã khách đọc"
          inputMode="numeric"
          autoFocus
        />
        <button type="submit" className="btn" disabled={code.length !== 4}>Giao</button>
      </form>

      {notice && <div className="form-error" role="alert">{notice}</div>}
      {done && (
        <div className="form-success" role="status">
          <Icon name="check" size={18} strokeWidth={2.4} /> {done}
        </div>
      )}

      {orders === null ? (
        <div className="state">Đang tải...</div>
      ) : orders.length === 0 ? (
        <p className="board-empty">Chưa có đơn nào làm xong.</p>
      ) : (
        <ul className="ready-list">
          {orders.map((o) => (
            <li key={o.id}>
              <button type="button" className="ready-card" onClick={() => setPicked(o)}>
                <strong className="pickup-code-sm">{o.pickup_code}</strong>
                <LicensePlate value={o.license_plate} size="md" />
                <span className="muted">
                  {o.items.map((i) => `${i.quantity}× ${i.item_name}`).join(', ')}
                  {' · xong lúc '}
                  {formatTime(o.history.at(-1)?.changed_at)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {picked && (
        <ConfirmDialog
          title={`Giao đơn mã ${picked.pickup_code}`}
          confirmLabel="Đã giao"
          cancelLabel="Chưa"
          tone="success"
          busy={busy}
          onConfirm={deliver}
          onCancel={() => setPicked(null)}
        >
          <p>Nhìn camera: biển số xe phải là</p>
          <LicensePlate value={picked.license_plate} size="lg" />
          <p className="muted">
            Túi có phiếu mã {picked.pickup_code} · {picked.items.map((i) => `${i.quantity}× ${i.item_name}`).join(', ')}
          </p>
        </ConfirmDialog>
      )}
    </div>
  )
}
