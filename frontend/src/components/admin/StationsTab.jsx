import { useState } from 'react'

import { errorMessage } from '../../api/client.js'
import { createStation, updateStation } from '../../api/menu.js'

const EMPTY = { name: '', address: '', opening_hours: '', kitchen_capacity: 2, is_active: true }

function StationForm({ initial, submitLabel, onSubmit, onCancel }) {
  const [form, setForm] = useState(initial)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) =>
    setForm((f) => ({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))

  async function handleSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await onSubmit({
        ...form,
        opening_hours: form.opening_hours || null,
        kitchen_capacity: Number(form.kitchen_capacity) || 2,
      })
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  return (
    <form className="form panel-form" onSubmit={handleSubmit}>
      {error && <div className="form-error" role="alert">{error}</div>}
      <div className="form-row">
        <label className="field">
          Tên cửa hàng
          <input value={form.name} onChange={set('name')} required maxLength={100} />
        </label>
        <label className="field">
          Giờ mở cửa
          <input value={form.opening_hours || ''} onChange={set('opening_hours')} placeholder="06:00 - 22:00" maxLength={50} />
        </label>
        <label className="field">
          Số đơn bếp làm cùng lúc
          <input
            type="number"
            min={1}
            max={20}
            value={form.kitchen_capacity ?? 2}
            onChange={set('kitchen_capacity')}
            required
            title="Dùng để ước lượng thời gian chờ cho khách"
          />
        </label>
      </div>
      <label className="field">
        Địa chỉ
        <input value={form.address} onChange={set('address')} required maxLength={255} />
      </label>
      <label className="check">
        <input type="checkbox" checked={form.is_active} onChange={set('is_active')} /> Đang hoạt động
      </label>
      <div className="form-actions">
        <button type="submit" className="btn" disabled={busy}>{busy ? 'Đang lưu...' : submitLabel}</button>
        {onCancel && <button type="button" className="btn btn-ghost" onClick={onCancel}>Hủy</button>}
      </div>
    </form>
  )
}

export default function StationsTab({ stations, onChanged }) {
  const [editing, setEditing] = useState(null) // id đang sửa, 'new' = thêm mới

  async function save(id, body) {
    if (id === 'new') await createStation(body)
    else await updateStation(id, body)
    setEditing(null)
    onChanged()
  }

  return (
    <div>
      <div className="panel-toolbar">
        <p className="panel-hint">Cửa hàng ngừng hoạt động sẽ không hiện với khách.</p>
        {editing !== 'new' && (
          <button type="button" className="btn btn-small" onClick={() => setEditing('new')}>+ Thêm cửa hàng</button>
        )}
      </div>

      {editing === 'new' && (
        <StationForm initial={EMPTY} submitLabel="Tạo cửa hàng" onSubmit={(b) => save('new', b)} onCancel={() => setEditing(null)} />
      )}

      <ul className="admin-list">
        {stations.map((s) => (
          <li key={s.id}>
            {editing === s.id ? (
              <StationForm initial={s} submitLabel="Lưu" onSubmit={(b) => save(s.id, b)} onCancel={() => setEditing(null)} />
            ) : (
              <div className="admin-row">
                <div>
                  <strong>#{s.id} {s.name}</strong>{' '}
                  <span className={`status-pill ${s.is_active ? 'status-completed' : 'status-cancelled'}`}>
                    {s.is_active ? 'Hoạt động' : 'Ngừng'}
                  </span>
                  <p className="muted">
                    {s.address}{s.opening_hours ? ` · ${s.opening_hours}` : ''} · bếp làm {s.kitchen_capacity ?? 2} đơn cùng lúc
                  </p>
                </div>
                <button type="button" className="btn btn-ghost btn-small" onClick={() => setEditing(s.id)}>Sửa</button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
