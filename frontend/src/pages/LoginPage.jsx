import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { errorMessage } from '../api/client.js'
import { homePath } from '../components/ProtectedRoute.jsx'
import { useAuth } from '../context/AuthContext.jsx'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const user = await login(email.trim(), password)
      // Nhân viên về màn hình quầy, admin về trang quản trị, khách về trang đang xem dở
      const from = user?.role === 'CUSTOMER' ? location.state?.from : null
      navigate(from || homePath(user?.role), { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-card">
      <h1>Đăng nhập</h1>
      <p className="auth-sub">
        Khách hàng đăng nhập để chọn cửa hàng và đặt món. Nhân viên và quản trị viên dùng tài
        khoản được cấp.
      </p>

      <form className="form" onSubmit={handleSubmit}>
        {error && <div className="form-error" role="alert">{error}</div>}
        <label className="field">
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
          />
        </label>
        <label className="field">
          Mật khẩu
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        <button type="submit" className="btn btn-block" disabled={busy}>
          {busy ? 'Đang đăng nhập...' : 'Đăng nhập'}
        </button>
      </form>

      <p className="auth-switch">
        Chưa có tài khoản? <Link to="/register">Đăng ký</Link>
      </p>
    </div>
  )
}