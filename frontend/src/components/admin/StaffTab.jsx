import { useCallback, useEffect, useState } from 'react'

import { createStaff, getStaff, toggleStaff } from '../../api/admin.js'
import { errorMessage } from '../../api/client.js'

const EMPTY = { full_name: '', email: '', phone: '', password: '', station_id: '' }

export default function StaffTab({ stations }) {
  const [staff, setStaff] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    getStaff()
      .then(setStaff)
      .catch((err) => setError(errorMessage(err)))
  }, [])

  useEffect(load, [load])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const stationName = Object.fromEntries(stations.map((s) => [s.id, s.name]))

  async function handleCreate(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await createStaff({ ...form, phone: form.phone || null, station_id: Number(form.station_id) })
      setForm(EMPTY)
      setShowForm(false)
      load()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleToggle(s) {
    const verb = s.is_active ? 'Khóa' : 'Mở khóa'
    if (!window.confirm(`${verb} tài khoản ${s.full_name}?`)) return
    setError('')
    try {
      await toggleStaff(s.id)
      load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <div>
      <div className="panel-toolbar">
        <p className="panel-hint">Mỗi nhân viên được gán một cửa hàng và chỉ thấy đơn của cửa hàng đó.</p>
        {!showForm && (
          <button type="button" className="btn btn-small" onClick={() => setShowForm(true)}>+ Thêm nhân viên</button>
        )}
      </div>
      {error && <div className="form-error" role="alert">{error}</div>}

      {showForm && (
        <form className="form panel-form" onSubmit={handleCreate}>
          <div className="form-row">
            <label className="field">
              Họ và tên
              <input value={form.full_name} onChange={set('full_name')} minLength={2} required />
            </label>
            <label className="field">
              Email đăng nhập
              <input type="email" value={form.email} onChange={set('email')} required />
            </label>
          </div>
          <div className="form-row">
            <label className="field">
              Số điện thoại
              <input type="tel" value={form.phone} onChange={set('phone')} />
            </label>
            <label className="field">
              Mật khẩu ban đầu (tối thiểu 6 ký tự)
              <input type="password" value={form.password} onChange={set('password')} minLength={6} autoComplete="new-password" required />
            </label>
            <label className="field">
              Cửa hàng
              <select value={form.station_id} onChange={set('station_id')} required>
                <option value="">-- Chọn --</option>
                {stations.filter((s) => s.is_active).map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="form-actions">
            <button type="submit" className="btn" disabled={busy}>{busy ? 'Đang tạo...' : 'Tạo tài khoản'}</button>
            <button type="button" className="btn btn-ghost" onClick={() => setShowForm(false)}>Hủy</button>
          </div>
        </form>
      )}

      {!staff ? (
        <div className="state">Đang tải...</div>
      ) : (
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>Nhân viên</th>
                <th>Email</th>
                <th>Điện thoại</th>
                <th>Cửa hàng</th>
                <th>Trạng thái</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {staff.map((s) => (
                <tr key={s.id} className={s.is_active ? '' : 'row-off'}>
                  <td><strong>{s.full_name}</strong></td>
                  <td>{s.email}</td>
                  <td>{s.phone || '–'}</td>
                  <td>{stationName[s.station_id] || (s.station_id ? `#${s.station_id}` : '–')}</td>
                  <td>
                    <span className={`status-pill ${s.is_active ? 'status-completed' : 'status-cancelled'}`}>
                      {s.is_active ? 'Hoạt động' : 'Đã khóa'}
                    </span>
                  </td>
                  <td>
                    <button type="button" className="btn btn-ghost btn-small" onClick={() => handleToggle(s)}>
                      {s.is_active ? 'Khóa' : 'Mở khóa'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
