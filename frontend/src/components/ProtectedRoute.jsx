import { Navigate, useLocation } from 'react-router-dom'

import { useAuth } from '../context/AuthContext.jsx'

/** Trang chính của từng vai trò: nhân viên ở màn hình quầy, admin ở trang quản trị. */
export function homePath(role) {
  return { STAFF: '/staff', ADMIN: '/admin' }[role] || '/'
}

/**
 * Bắt buộc đăng nhập. Chưa đăng nhập -> trang đăng nhập (nhớ trang đang mở).
 * Sai vai trò -> đưa về trang chính của vai trò đó (vd. staff mở "/" thì về /staff).
 */
export default function ProtectedRoute({ roles, children }) {
  const { user } = useAuth()
  const location = useLocation()

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }
  if (roles && !roles.includes(user.role)) {
    return <Navigate to={homePath(user.role)} replace />
  }
  return children
}

/** Trang đăng nhập / đăng ký: đã đăng nhập rồi thì vào thẳng trang chính. */
export function GuestOnlyRoute({ children }) {
  const { user } = useAuth()
  const location = useLocation()
  if (user) {
    // Khách quay lại trang đang xem dở trước khi bị bắt đăng nhập
    const from = user.role === 'CUSTOMER' ? location.state?.from : null
    return <Navigate to={from || homePath(user.role)} replace />
  }
  return children
}
