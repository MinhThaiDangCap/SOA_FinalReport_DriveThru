import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useFormik } from 'formik'
import * as Yup from 'yup'

import { errorMessage } from '../api/client.js'
import { useAuth } from '../context/AuthContext.jsx'

const registerSchema = Yup.object({
  full_name: Yup.string()
    .trim()
    .min(2, 'Họ và tên phải có từ 2 ký tự trở lên.')
    .max(100, 'Họ và tên tối đa 100 ký tự.')
    .required('Vui lòng nhập họ và tên.'),
  email: Yup.string()
    .trim()
    .email('Email không đúng định dạng (ví dụ: ten@gmail.com).')
    .required('Vui lòng nhập email.'),
  phone: Yup.string()
    .trim()
    .matches(/^$|^0\d{9}$/, 'Số điện thoại phải gồm 10 chữ số và bắt đầu bằng số 0.'),
  password: Yup.string()
    .min(6, 'Mật khẩu phải có tối thiểu 6 ký tự.')
    .max(72, 'Mật khẩu tối đa 72 ký tự.')
    .required('Vui lòng nhập mật khẩu.'),
})

export default function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [serverError, setServerError] = useState('')

  const formik = useFormik({
    initialValues: {
      full_name: '',
      email: '',
      phone: '',
      password: '',
    },
    validationSchema: registerSchema,
    validateOnChange: true,
    validateOnBlur: true,
    onSubmit: async (values) => {
      setServerError('')
      try {
        await register({
          full_name: values.full_name.trim(),
          email: values.email.trim(),
          phone: values.phone.trim() || null,
          password: values.password,
        })
        navigate('/', { replace: true })
      } catch (err) {
        setServerError(errorMessage(err))
      }
    },
  })

  // Hiện lỗi ngay khi người dùng vừa gõ sai hoặc vừa rời khỏi ô nhập
  const showError = (field) =>
    (formik.touched[field] || formik.values[field] !== '') && formik.errors[field]

  return (
    <div className="auth-card">
      <h1>Tạo tài khoản</h1>
      <p className="auth-sub">Chỉ mất một phút để bắt đầu đặt món.</p>

      <form className="form" onSubmit={formik.handleSubmit} noValidate>
        {serverError && <div className="form-error" role="alert">{serverError}</div>}

        <label className="field">
          Họ và tên
          <input
            name="full_name"
            value={formik.values.full_name}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            className={showError('full_name') ? 'input-error' : ''}
            placeholder="Nguyễn Văn A"
          />
          {showError('full_name') && (
            <span className="field-error">{formik.errors.full_name}</span>
          )}
        </label>

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
          />
          {showError('email') && (
            <span className="field-error">{formik.errors.email}</span>
          )}
        </label>

        <label className="field">
          Số điện thoại (không bắt buộc)
          <input
            type="tel"
            name="phone"
            value={formik.values.phone}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            className={showError('phone') ? 'input-error' : ''}
            placeholder="0901234567"
          />
          {showError('phone') && (
            <span className="field-error">{formik.errors.phone}</span>
          )}
        </label>

        <label className="field">
          Mật khẩu (tối thiểu 6 ký tự)
          <input
            type="password"
            name="password"
            value={formik.values.password}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            className={showError('password') ? 'input-error' : ''}
            autoComplete="new-password"
          />
          {showError('password') && (
            <span className="field-error">{formik.errors.password}</span>
          )}
        </label>

        <button type="submit" className="btn btn-block" disabled={formik.isSubmitting}>
          {formik.isSubmitting ? 'Đang tạo tài khoản...' : 'Đăng ký'}
        </button>
      </form>

      <p className="auth-switch">
        Đã có tài khoản? <Link to="/login">Đăng nhập</Link>
      </p>
    </div>
  )
}
