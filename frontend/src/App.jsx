import { Link, Route, Routes } from 'react-router-dom'

import { useAuth } from './context/AuthContext.jsx'
import { useCart } from './context/CartContext.jsx'
import CheckoutPage from './pages/CheckoutPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import MenuPage from './pages/MenuPage.jsx'
import RegisterPage from './pages/RegisterPage.jsx'
import StationsPage from './pages/StationsPage.jsx'

import ProtectedRoute from './components/ProtectedRoute.jsx'
import OrderPage from './pages/OrderPage.jsx'
import './dashboard.css'
import AdminPage from './pages/AdminPage.jsx'
import OrdersPage from './pages/OrdersPage.jsx'
import PaymentResultPage from './pages/PaymentResultPage.jsx'
import StaffPage from './pages/StaffPage.jsx'

export default function App() {
  const { cart, totalQuantity } = useCart()
  const { user, logout } = useAuth()

  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-mark" aria-hidden="true">DT</span>
          Drive-Thru
        </Link>

        <nav className="topbar-nav">
          {(!user || user.role === 'CUSTOMER') && cart.stationId && totalQuantity > 0 && (
            <Link to={`/stations/${cart.stationId}`} className="topbar-cart">
              Giỏ hàng <span className="badge">{totalQuantity}</span>
            </Link>
          )}
          {user?.role === 'CUSTOMER' && (
            <Link to="/orders" className="topbar-link">Đơn của tôi</Link>
          )}
          {user?.role === 'STAFF' && (
            <Link to="/staff" className="topbar-link">Màn hình quầy</Link>
          )}
          {user?.role === 'ADMIN' && (
            <Link to="/admin" className="topbar-link">Quản trị</Link>
          )}
          {user ? (
            <>
              <span className="topbar-user">{user.full_name}</span>
              <button type="button" className="btn btn-ghost btn-small" onClick={logout}>
                Đăng xuất
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="btn btn-ghost btn-small">Đăng nhập</Link>
              <Link to="/register" className="btn btn-small">Đăng ký</Link>
            </>
          )}
        </nav>
      </header>

      <main className="page">
        <Routes>
          <Route path="/" element={<StationsPage />} />
          <Route path="/stations/:stationId" element={<MenuPage />} />
          <Route
            path="/checkout"
            element={
              <ProtectedRoute roles={['CUSTOMER']}>
                <CheckoutPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/orders/:orderId"
            element={
              <ProtectedRoute>
                <OrderPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/orders"
            element={
              <ProtectedRoute roles={['CUSTOMER']}>
                <OrdersPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/staff"
            element={
              <ProtectedRoute roles={['STAFF']}>
                <StaffPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedRoute roles={['ADMIN']}>
                <AdminPage />
              </ProtectedRoute>
            }
          />
          <Route path="/payment/result" element={<PaymentResultPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route
            path="*"
            element={
              <div className="state">
                <p>Không tìm thấy trang.</p>
                <Link to="/" className="btn">Về trang chọn cửa hàng</Link>
              </div>
            }
          />
        </Routes>
      </main>
    </>
  )
}