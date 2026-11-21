import { Link, NavLink, Route, Routes } from "react-router-dom";

import { useAuth } from "./context/AuthContext.jsx";
import { useCart } from "./context/CartContext.jsx";
import CheckoutPage from "./pages/CheckoutPage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import MenuPage from "./pages/MenuPage.jsx";
import RegisterPage from "./pages/RegisterPage.jsx";
import StationsPage from "./pages/StationsPage.jsx";

import "./board.css";
import Icon from "./components/Icon.jsx";
import ProtectedRoute, {
  GuestOnlyRoute,
  homePath,
} from "./components/ProtectedRoute.jsx";
import "./dashboard.css";
import "./home.css";
import "./icons.css";
import "./modal.css";
import AdminPage from "./pages/AdminPage.jsx";
import OrderPage from "./pages/OrderPage.jsx";
import OrdersPage from "./pages/OrdersPage.jsx";
import PaymentResultPage from "./pages/PaymentResultPage.jsx";
import StaffPage from "./pages/StaffPage.jsx";

const ROLE_BADGE = {
  CUSTOMER: "Khách hàng",
  STAFF: "Nhân viên quầy",
  ADMIN: "Quản trị viên",
};

export default function App() {
  const { cart, totalQuantity } = useCart();
  const { user, logout } = useAuth();

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <Link to={user ? homePath(user.role) : "/login"} className="brand">
            <span className="brand-mark" aria-hidden="true">
              <Icon name="car" size={20} strokeWidth={2.2} />
            </span>
            <span className="brand-text">
              <strong>GoLane</strong>
              <small>Drive-Thru Express</small>
            </span>
          </Link>

          <nav className="topbar-nav">
            {user?.role === "CUSTOMER" && (
              <>
                <NavLink
                  to="/"
                  end
                  className={({ isActive }) =>
                    `topbar-link${isActive ? " active" : ""}`
                  }
                >
                  Trang chủ
                </NavLink>
                <a href="/#stations" className="topbar-link">
                  Cửa hàng
                </a>
                <a href="/#about" className="topbar-link">
                  About
                </a>
                <a href="/#combo-promo" className="topbar-link">
                  Thực đơn nổi bật
                </a>
                <a href="/#faq" className="topbar-link">
                  Hỗ trợ
                </a>
                <NavLink
                  to="/orders"
                  className={({ isActive }) =>
                    `topbar-link${isActive ? " active" : ""}`
                  }
                >
                  Đơn của tôi
                </NavLink>
              </>
            )}
            {user?.role === "CUSTOMER" &&
              cart.stationId &&
              totalQuantity > 0 && (
                <Link
                  to={`/stations/${cart.stationId}`}
                  className="topbar-cart"
                >
                  <Icon name="bag" size={16} />
                  Giỏ hàng <span className="badge">{totalQuantity}</span>
                </Link>
              )}
            {user?.role === "STAFF" && (
              <NavLink
                to="/staff"
                className={({ isActive }) =>
                  `topbar-link${isActive ? " active" : ""}`
                }
              >
                Màn hình quầy
              </NavLink>
            )}
            {user?.role === "ADMIN" && (
              <NavLink
                to="/admin"
                className={({ isActive }) =>
                  `topbar-link${isActive ? " active" : ""}`
                }
              >
                Quản trị hệ thống
              </NavLink>
            )}
            {user ? (
              <div className="user-chip">
                <div className="user-chip-info">
                  <span className="topbar-user">{user.full_name}</span>
                  <span className={`role-tag role-${user.role?.toLowerCase()}`}>
                    {ROLE_BADGE[user.role] || user.role}
                  </span>
                </div>
                <button
                  type="button"
                  className="btn btn-ghost btn-small"
                  onClick={logout}
                >
                  Đăng xuất
                </button>
              </div>
            ) : (
              <div className="auth-actions">
                <Link to="/login" className="btn btn-ghost btn-small">
                  Đăng nhập
                </Link>
                <Link to="/register" className="btn btn-small">
                  Đăng ký
                </Link>
              </div>
            )}
          </nav>
        </div>
      </header>

      <main className="page">
        <Routes>
          <Route
            path="/"
            element={
              <ProtectedRoute roles={["CUSTOMER"]}>
                <StationsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/stations/:stationId"
            element={
              <ProtectedRoute roles={["CUSTOMER"]}>
                <MenuPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/checkout"
            element={
              <ProtectedRoute roles={["CUSTOMER"]}>
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
              <ProtectedRoute roles={["CUSTOMER"]}>
                <OrdersPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/staff"
            element={
              <ProtectedRoute roles={["STAFF"]}>
                <StaffPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedRoute roles={["ADMIN"]}>
                <AdminPage />
              </ProtectedRoute>
            }
          />
          <Route path="/payment/result" element={<PaymentResultPage />} />
          <Route
            path="/login"
            element={
              <GuestOnlyRoute>
                <LoginPage />
              </GuestOnlyRoute>
            }
          />
          <Route
            path="/register"
            element={
              <GuestOnlyRoute>
                <RegisterPage />
              </GuestOnlyRoute>
            }
          />
          <Route
            path="*"
            element={
              <div className="state">
                <p>Không tìm thấy trang.</p>
                <Link
                  to={user ? homePath(user.role) : "/login"}
                  className="btn"
                >
                  Về trang chính
                </Link>
              </div>
            }
          />
        </Routes>
      </main>

      <footer className="site-footer">
        <div className="site-footer-grid">
          <div className="footer-brand-col">
            <div className="brand">
              <span className="brand-mark" aria-hidden="true">
                <Icon name="car" size={18} strokeWidth={2.2} />
              </span>
              <strong>GoLane Drive-Thru</strong>
            </div>
            <p className="footer-desc">
              Chuỗi cửa hàng đồ ăn nhanh mô hình Drive-Thru hiện đại. Đặt món
              trước trên web, thanh toán nhanh gọn và nhận món tận xe chỉ trong
              vài chục giây.
            </p>
          </div>

          <div>
            <h3>Khám phá</h3>
            <ul className="footer-links">
              <li>
                <Link to="/">Danh sách cửa hàng</Link>
              </li>
              <li>
                <Link to="/orders">Theo dõi đơn hàng</Link>
              </li>
              <li>
                <a href="/#why-golane">Về GoLane Express</a>
              </li>
              <li>
                <a href="/#faq">Câu hỏi thường gặp</a>
              </li>
            </ul>
          </div>

          <div>
            <h3>Hệ thống chi nhánh</h3>
            <ul className="footer-links">
              <li>GoLane Quận 7 · Nguyễn Thị Thập</li>
              <li>GoLane Thủ Đức · Võ Văn Ngân</li>
              <li>GoLane Bình Thạnh · Điện Biên Phủ</li>
            </ul>
          </div>

          <div>
            <h3>Chăm sóc khách hàng</h3>
            <ul className="footer-links">
              <li>
                Hotline: <strong>1900 6868</strong>
              </li>
              <li>
                Email: <strong>cskh@golane.vn</strong>
              </li>
              <li>Giờ hoạt động: 06:00 – 23:00 hàng ngày</li>
            </ul>
          </div>
        </div>

        <div className="site-footer-bottom">
          <span>© 2026 GoLane Vietnam. Tất cả các quyền được bảo lưu.</span>
          <div className="footer-badges">
            <span>Thanh toán MoMo</span>
            <span>Tiền mặt tại quầy</span>
            <span>Nhận món tại làn xe</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
