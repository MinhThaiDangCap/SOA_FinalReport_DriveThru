import { useCallback, useEffect, useState } from 'react'

import { createCoupon, getCoupons, updateCoupon } from '../../api/admin.js'
import { errorMessage } from '../../api/client.js'
import { formatPrice } from '../../format.js'

const today = () => new Date().toLocaleDateString('en-CA') // YYYY-MM-DD theo giờ máy

const EMPTY = { code: '', discount_type: 'PERCENT', discount_value: '', valid_from: today(), valid_to: today() }

function formatDate(d) {
  const [y, m, day] = d.split('-')
  return `${day}/${m}/${y}`
}

export default function CouponsTab() {
  const [coupons, setCoupons] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    getCoupons()
      .then(setCoupons)
      .catch((err) => setError(errorMessage(err)))
  }, [])

  useEffect(load, [load])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function handleCreate(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await createCoupon({ ...form, discount_value: Number(form.discount_value), is_active: true })
      setForm({ ...EMPTY, valid_from: today(), valid_to: today() })
      setShowForm(false)
      load()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function toggle(c) {
    setError('')
    try {
      await updateCoupon(c.id, { is_active: !c.is_active })
      load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  const now = today()
  const stateOf = (c) => {
    if (!c.is_active) return ['Đã tắt', 'status-cancelled']
    if (c.valid_to < now) return ['Hết hạn', 'status-cancelled']
    if (c.valid_from > now) return ['Chưa tới ngày', '']
    return ['Đang áp dụng', 'status-completed']
  }

  return (
    <div>
      <div className="panel-toolbar">
        <p className="panel-hint">Khách nhập mã ở bước đặt đơn. Mã không đổi được sau khi tạo vì đơn cũ đã lưu mã này.</p>
        {!showForm && (
          <button type="button" className="btn btn-small" onClick={() => setShowForm(true)}>+ Tạo mã</button>
        )}
      </div>
      {error && <div className="form-error" role="alert">{error}</div>}

      {showForm && (
        <form className="form panel-form" onSubmit={handleCreate}>
          <div className="form-row">
            <label className="field">
              Mã (chữ, số, - _)
              <input value={form.code} onChange={set('code')} pattern="[A-Za-z0-9_\-]{3,30}" required placeholder="GIAM20" />
            </label>
            <label className="field">
              Kiểu giảm
              <select value={form.discount_type} onChange={set('discount_type')}>
                <option value="PERCENT">Theo %</option>
                <option value="FIXED">Số tiền cố định</option>
              </select>
            </label>
            <label className="field">
              {form.discount_type === 'PERCENT' ? 'Giảm (%)' : 'Giảm (VND)'}
              <input
                type="number"
                min={1}
                max={form.discount_type === 'PERCENT' ? 100 : undefined}
                value={form.discount_value}
                onChange={set('discount_value')}
                required
              />
            </label>
          </div>
          <div className="form-row">
            <label className="field">
              Từ ngày
              <input type="date" value={form.valid_from} onChange={set('valid_from')} required />
            </label>
            <label className="field">
              Đến ngày
              <input type="date" value={form.valid_to} min={form.valid_from} onChange={set('valid_to')} required />
            </label>
          </div>
          <div className="form-actions">
            <button type="submit" className="btn" disabled={busy}>{busy ? 'Đang tạo...' : 'Tạo mã'}</button>
            <button type="button" className="btn btn-ghost" onClick={() => setShowForm(false)}>Hủy</button>
          </div>
        </form>
      )}

      {!coupons ? (
        <div className="state">Đang tải...</div>
      ) : coupons.length === 0 ? (
        <p className="board-empty">Chưa có mã giảm giá nào.</p>
      ) : (
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>Mã</th>
                <th>Giảm</th>
                <th>Hiệu lực</th>
                <th>Trạng thái</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {coupons.map((c) => {
                const [label, cls] = stateOf(c)
                return (
                  <tr key={c.id}>
                    <td><strong>{c.code}</strong></td>
                    <td>{c.discount_type === 'PERCENT' ? `${c.discount_value}%` : formatPrice(c.discount_value)}</td>
                    <td>{formatDate(c.valid_from)} – {formatDate(c.valid_to)}</td>
                    <td><span className={`status-pill ${cls}`}>{label}</span></td>
                    <td>
                      <button type="button" className="btn btn-ghost btn-small" onClick={() => toggle(c)}>
                        {c.is_active ? 'Tắt' : 'Bật'}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
