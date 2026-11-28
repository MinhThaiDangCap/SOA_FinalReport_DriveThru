import { useCallback, useEffect, useState } from 'react'

import { errorMessage } from '../api/client.js'
import { updatePlate } from '../api/orders.js'
import { cancelOrderByStaff, checkIn, confirmCash, getHolds, lookupOrders } from '../api/staff.js'
import { formatPrice, formatTime, METHOD_LABEL, PAYMENT_METHODS, STATUS_LABEL } from '../format.js'
import ConfirmDialog from './ConfirmDialog.jsx'
import Icon from './Icon.jsx'
import LicensePlate from './LicensePlate.jsx'
import { CashDialog } from './OrderBoard.jsx'

const POLL_MS = 5000

/** Thẻ đơn ở trạm 1: mã, biển số (đối chiếu với camera), SĐT, món, nút xử lý. */
function HoldCard({ order, busy, onCheckIn, onCash, onCancel, onEditPlate }) {
  const awaiting = order.status === 'AWAITING_PAYMENT'
  return (
    <li className={`ticket${order.is_overdue ? ' ticket-overdue' : ''}${awaiting ? ' ticket-arrived' : ''}`}>
      <div className="ticket-head">
        <span className="pickup-chip">Mã {order.pickup_code}</span>
        <LicensePlate value={order.license_plate} size="md" />
      </div>
      {order.is_overdue && (
        <div className="ticket-flag">
          <Icon name="clock" size={18} /> Quá hạn giữ ({formatTime(order.hold_expires_at)}) · gọi {order.contact_phone}
        </div>
      )}
      <ul className="ticket-items">
        {order.items.map((i) => (
          <li key={i.menu_item_id}>
            <strong>{i.quantity}×</strong> {i.item_name}
          </li>
        ))}
      </ul>
      <div className="ticket-meta">
        {formatPrice(order.total_amount)} · SĐT {order.contact_phone || '—'}
        {order.status === 'HOLD' && order.expected_arrival_at && ` · hẹn ${formatTime(order.expected_arrival_at)}`}
        {awaiting && ` · ${STATUS_LABEL.AWAITING_PAYMENT} (${METHOD_LABEL[order.payment_method]})`}
      </div>

      {order.status === 'HOLD' && (
        <div className="ticket-actions">
          {PAYMENT_METHODS.map((m) => (
            <button
              key={m.value}
              type="button"
              className="btn btn-small"
              disabled={busy}
              onClick={() => onCheckIn(order, m.value)}
            >
              <Icon name={m.icon} size={16} /> Nhận đơn · {m.title}
            </button>
          ))}
        </div>
      )}
      {awaiting && order.payment_method === 'CASH' && (
        <div className="ticket-actions">
          <button type="button" className="btn btn-small" disabled={busy} onClick={() => onCash(order)}>
            Thu {formatPrice(order.total_amount)} · đưa vào bếp
          </button>
          <button type="button" className="btn btn-ghost btn-small" disabled={busy} onClick={() => onCheckIn(order, 'ZALOPAY')}>
            Đổi sang ZaloPay
          </button>
        </div>
      )}
      {awaiting && order.payment_method === 'ZALOPAY' && (
        <div className="ticket-actions">
          <span className="muted">Khách đang trả trên điện thoại. Trả xong đơn tự vào bếp.</span>
          <button type="button" className="btn btn-ghost btn-small" disabled={busy} onClick={() => onCheckIn(order, 'CASH')}>
            Đổi sang tiền mặt
          </button>
        </div>
      )}
      <div className="ticket-actions ticket-actions-minor">
        <button type="button" className="btn btn-ghost btn-small" disabled={busy} onClick={() => onEditPlate(order)}>
          Sửa biển số
        </button>
        <button type="button" className="btn btn-ghost btn-small" disabled={busy} onClick={() => onCancel(order)}>
          Hủy đơn
        </button>
      </div>
    </li>
  )
}

/**
 * Trạm 1: khách đọc mã, nhân viên tìm đơn, nhìn camera đối chiếu biển số,
 * khách trả tiền mặt (thu tại trạm) hoặc ZaloPay (trên điện thoại khách) -> đơn vào bếp.
 */
export default function StationOne() {
  const [holds, setHolds] = useState(null)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [notice, setNotice] = useState('')
  const [done, setDone] = useState('')
  const [cashFor, setCashFor] = useState(null)
  const [cancelFor, setCancelFor] = useState(null)
  const [plateFor, setPlateFor] = useState(null)
  const [newPlate, setNewPlate] = useState('')

  const load = useCallback(async () => {
    try {
      setHolds(await getHolds())
      setNotice('')
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

  async function search(e) {
    e.preventDefault()
    const q = query.trim()
    if (q.length < 2) return
    try {
      setResults(await lookupOrders(q))
    } catch (err) {
      setNotice(errorMessage(err))
    }
  }

  async function run(order, action, message) {
    setBusyId(order.id)
    setNotice('')
    setDone('')
    try {
      await action()
      if (message) setDone(message)
      setResults(null)
      setQuery('')
      await load()
    } catch (err) {
      setNotice(`Mã ${order.pickup_code}: ${errorMessage(err)}`)
      await load()
    } finally {
      setBusyId(null)
      setCashFor(null)
      setCancelFor(null)
      setPlateFor(null)
    }
  }

  const handlers = {
    onCheckIn: (o, method) =>
      run(o, () => checkIn(o.id, method),
        method === 'CASH' ? `Mã ${o.pickup_code}: thu tiền mặt rồi bấm "Thu".` : `Mã ${o.pickup_code}: khách trả ZaloPay trên điện thoại.`),
    onCash: (o) => setCashFor(o),
    onCancel: (o) => setCancelFor(o),
    onEditPlate: (o) => {
      setNewPlate(o.license_plate)
      setPlateFor(o)
    },
  }

  const list = results ?? holds ?? []
  const atStation = list.filter((o) => ['HOLD', 'AWAITING_PAYMENT'].includes(o.status))
  const others = results ? results.filter((o) => !['HOLD', 'AWAITING_PAYMENT'].includes(o.status)) : []

  return (
    <div className="board-wrap">
      <form className="station-search" onSubmit={search}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Khách đọc mã 4 số (hoặc nhập biển số)"
          inputMode="search"
          autoFocus
        />
        <button type="submit" className="btn">
          <Icon name="search" size={18} /> Tìm
        </button>
        {results && (
          <button type="button" className="btn btn-ghost" onClick={() => { setResults(null); setQuery('') }}>
            Xem tất cả
          </button>
        )}
      </form>
      <p className="muted station-tip">
        Luôn nhìn camera đối chiếu biển số với thẻ đơn. Không khớp: hỏi tên hoặc 3 số cuối điện
        thoại rồi bấm "Sửa biển số".
      </p>

      {notice && <div className="form-error" role="alert">{notice}</div>}
      {done && (
        <div className="form-success" role="status">
          <Icon name="check" size={18} strokeWidth={2.4} /> {done}
        </div>
      )}

      {holds === null ? (
        <div className="state">Đang tải đơn...</div>
      ) : atStation.length === 0 ? (
        <p className="board-empty">
          {results ? 'Không có đơn đang chờ khớp với mã / biển số này.' : 'Chưa có đơn nào đang giữ chỗ.'}
        </p>
      ) : (
        <ul className="ticket-list ticket-grid">
          {atStation.map((o) => (
            <HoldCard key={o.id} order={o} busy={busyId === o.id} {...handlers} />
          ))}
        </ul>
      )}
      {others.length > 0 && (
        <p className="muted">
          {others.map((o) => `Mã ${o.pickup_code}: ${STATUS_LABEL[o.status]}`).join(' · ')}
        </p>
      )}

      {cashFor && (
        <CashDialog
          order={cashFor}
          busy={busyId === cashFor.id}
          confirmLabel={`Đã thu ${formatPrice(cashFor.total_amount)} · đưa vào bếp`}
          onConfirm={() =>
            run(cashFor, () => confirmCash(cashFor.id),
              `Mã ${cashFor.pickup_code}: đã thu tiền, đơn đã vào bếp. Mời xe vào bãi chờ.`)}
          onCancel={() => setCashFor(null)}
        />
      )}
      {cancelFor && (
        <ConfirmDialog
          title={`Hủy đơn mã ${cancelFor.pickup_code}?`}
          confirmLabel="Hủy đơn"
          cancelLabel="Giữ đơn"
          busy={busyId === cancelFor.id}
          onConfirm={() => run(cancelFor, () => cancelOrderByStaff(cancelFor.id), `Đã hủy đơn mã ${cancelFor.pickup_code}.`)}
          onCancel={() => setCancelFor(null)}
        >
          <p>
            Xe <strong>{cancelFor.license_plate}</strong> · SĐT <strong>{cancelFor.contact_phone}</strong>.
            {cancelFor.is_overdue ? ' Đơn đã quá hạn giữ.' : ' Đơn chưa quá hạn giữ.'} Đơn chưa thanh
            toán nên không phải hoàn tiền.
          </p>
        </ConfirmDialog>
      )}
      {plateFor && (
        <ConfirmDialog
          title={`Sửa biển số đơn mã ${plateFor.pickup_code}`}
          confirmLabel="Lưu biển số"
          cancelLabel="Thôi"
          confirmDisabled={newPlate.trim().length < 4}
          busy={busyId === plateFor.id}
          onConfirm={() => run(plateFor, () => updatePlate(plateFor.id, newPlate.trim()), 'Đã sửa biển số.')}
          onCancel={() => setPlateFor(null)}
        >
          <p>Chỉ sửa sau khi đã xác minh khách bằng tên hoặc số điện thoại. Hệ thống ghi lại người sửa.</p>
          <label className="field">
            Biển số mới
            <input value={newPlate} onChange={(e) => setNewPlate(e.target.value)} maxLength={15} />
          </label>
        </ConfirmDialog>
      )}
    </div>
  )
}
