import { Link, Navigate, useLocation } from 'react-router-dom'

import { useAuth } from '../context/AuthContext.jsx'

export default function ProtectedRoute({ roles, children }) {
  const { user } = useAuth()
  const location = useLocation()

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  if (roles && !roles.includes(user.role)) {
    return (
      <div className="state">
        <p>Bạn không có quyền truy cập trang này.</p>
        <Link to="/" className="btn">Về trang chủ</Link>
      </div>
    )
  }
  return children
}