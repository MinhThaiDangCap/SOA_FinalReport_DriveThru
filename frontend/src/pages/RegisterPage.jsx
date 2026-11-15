import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { errorMessage } from '../api/client.js'
import { useAuth } from '../context/AuthContext.jsx'

export default function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ full_name: '', email: '', phone: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const update = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  async function handleSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await register({
        full_name: form.full_name.trim(),
        email: form.email.trim(),
        phone: form.phone.trim() || null,
        password: form.password,
      })
      navigate('/', { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-card">
      <h1>Tạo tài khoản</h1>
      <p className="auth-sub">Chỉ mất một phút để bắt đầu đặt món.</p>

      <form className="form" onSubmit={handleSubmit}>
        {error && <div className="form-error" role="alert">{error}</div>}
        <label className="field">
          Họ và tên
          <input value={form.full_name} onChange={update('full_name')} minLength={2} required />
        </label>
        <label className="field">
          Email
          <input type="email" value={form.email} onChange={update('email')} required />
        </label>
        <label className="field">
          Số điện thoại (không bắt buộc)
          <input type="tel" value={form.phone} onChange={update('phone')} />
        </label>
        <label className="field">
          Mật khẩu (tối thiểu 6 ký tự)
          <input
            type="password"
            value={form.password}
            onChange={update('password')}
            minLength={6}
            autoComplete="new-password"
            required
          />
        </label>
        <button type="submit" className="btn btn-block" disabled={busy}>
          {busy ? 'Đang tạo tài khoản...' : 'Đăng ký'}
        </button>
      </form>

      <p className="auth-switch">
        Đã có tài khoản? <Link to="/login">Đăng nhập</Link>
      </p>
    </div>
  )
}