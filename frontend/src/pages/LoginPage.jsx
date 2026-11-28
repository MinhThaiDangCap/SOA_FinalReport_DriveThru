import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useFormik } from 'formik'
import * as Yup from 'yup'

import { errorMessage } from '../api/client.js'
import Icon from '../components/Icon.jsx'
import { homePath } from '../components/ProtectedRoute.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const loginSchema = Yup.object({
  email: Yup.string()
    .trim()
    .email('Email không đúng định dạng (ví dụ: ten@gmail.com).')
    .required('Vui lòng nhập email.'),
  password: Yup.string()
    .min(6, 'Mật khẩu phải có tối thiểu 6 ký tự.')
    .required('Vui lòng nhập mật khẩu.'),
})

const HIGHLIGHTS = [
  {
    icon: 'clock',
    title: 'Tiết kiệm thời gian tối đa',
    text: 'Đặt món trước trên điện thoại, bếp chuẩn bị sẵn trước khi xe bạn tới trạm.',
  },
  {
    icon: 'car',
    title: 'Nhận diện qua biển số xe',
    text: 'Đọc mã nhận món ở trạm 1 và trạm 2, nhân viên đối chiếu biển số để giao đúng xe.',
  },
  {
    icon: 'card',
    title: 'Thanh toán linh hoạt',
    text: 'Đặt trước không cần trả tiền; tới trạm 1 trả bằng ZaloPay hoặc tiền mặt.',
  },
]

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [serverError, setServerError] = useState('')
  const [showPass, setShowPass] = useState(false)

  const formik = useFormik({
    initialValues: {
      email: '',
      password: '',
    },
    validationSchema: loginSchema,
    validateOnChange: true,
    validateOnBlur: true,
    onSubmit: async (values) => {
      setServerError('')
      try {
        const user = await login(values.email.trim(), values.password)
        const from = user?.role === 'CUSTOMER' ? location.state?.from : null
        navigate(from || homePath(user?.role), { replace: true })
      } catch (err) {
        setServerError(errorMessage(err))
      }
    },
  })

  const showError = (field) =>
    (formik.touched[field] || formik.values[field] !== '') && formik.errors[field]

  return (
    <div className="auth-showcase">
      <section className="auth-brand-panel">
        <span className="auth-eyebrow">
          <Icon name="car" size={16} /> Mô hình Drive-Thru thế hệ mới
        </span>
        <h1>Đặt món trước, nhận ngay trên xe không cần chờ đợi</h1>
        <p className="auth-lead">
          Chào mừng bạn đến với <strong>GoLane</strong> — chuỗi đồ ăn nhanh Drive-Thru tiện lợi
          dành cho người bận rộn. Trải nghiệm đặt món nhanh gọn, an toàn và chính xác theo từng
          biển số xe.
        </p>

        <div className="auth-photo-wrap">
          <img
            src="/images/hero-drivethru.jpg"
            alt="Nhân viên GoLane giao món tận xe tại làn Drive-Thru"
            className="auth-photo"
          />
          <span className="auth-photo-badge with-icon"><Icon name="car" size={15} /> Giao món tại làn xe ~60s</span>
        </div>

        <ul className="auth-highlights">
          {HIGHLIGHTS.map((item) => (
            <li key={item.title} className="auth-highlight-card">
              <span className="step-icon">
                <Icon name={item.icon} size={20} />
              </span>
              <div>
                <strong>{item.title}</strong>
                <p>{item.text}</p>
              </div>
            </li>
          ))}
        </ul>

        <div className="auth-metrics">
          <div>
            <strong>3+</strong>
            <span>Chi nhánh TP.HCM</span>
          </div>
          <div>
            <strong>~60 giây</strong>
            <span>Giao món tại làn xe</span>
          </div>
          <div>
            <strong className="with-icon">4.9 <Icon name="star" filled size={18} className="star-fill" /></strong>
            <span>Đánh giá hài lòng</span>
          </div>
        </div>
      </section>

      <section className="auth-card">
        <div className="auth-header-badge">
          <Icon name="car" size={17} /> Tài khoản GoLane
        </div>
        <h2>Đăng nhập</h2>
        <p className="auth-sub">
          Đăng nhập để đặt món nhanh chóng hoặc truy cập hệ thống quản lý cửa hàng.
        </p>

        <form className="form" onSubmit={formik.handleSubmit} noValidate>
          {serverError && <div className="form-error" role="alert">{serverError}</div>}

          <label className="field">
            Email
            <input
              type="email"
              name="email"
              value={formik.values.email}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              className={showError('email') ? 'input-error' : ''}
              placeholder="ten@gmail.com"
              autoComplete="email"
            />
            {showError('email') && (
              <span className="field-error">{formik.errors.email}</span>
            )}
          </label>

          <label className="field">
            Mật khẩu
            <div className="password-wrap">
              <input
                type={showPass ? 'text' : 'password'}
                name="password"
                value={formik.values.password}
                onChange={formik.handleChange}
                onBlur={formik.handleBlur}
                className={showError('password') ? 'input-error' : ''}
                placeholder="Nhập mật khẩu của bạn"
                autoComplete="current-password"
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPass((v) => !v)}
              >
                {showPass ? 'Ẩn' : 'Hiện'}
              </button>
            </div>
            {showError('password') && (
              <span className="field-error">{formik.errors.password}</span>
            )}
          </label>

          <button type="submit" className="btn btn-block" disabled={formik.isSubmitting}>
            {formik.isSubmitting ? 'Đang đăng nhập...' : 'Đăng nhập ngay'}
          </button>
        </form>

        <p className="auth-switch">
          Bạn là khách hàng mới? <Link to="/register">Tạo tài khoản miễn phí</Link>
        </p>
      </section>
    </div>
  )
}
