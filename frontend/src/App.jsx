import { Link, Route, Routes } from 'react-router-dom'

import { useCart } from './context/CartContext.jsx'
import CheckoutPage from './pages/CheckoutPage.jsx'
import MenuPage from './pages/MenuPage.jsx'
import StationsPage from './pages/StationsPage.jsx'

export default function App() {
  const { cart, totalQuantity } = useCart()

  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-mark" aria-hidden="true">DT</span>
          Drive-Thru
        </Link>
        {cart.stationId && totalQuantity > 0 && (
          <Link to={`/stations/${cart.stationId}`} className="topbar-cart">
            Giỏ hàng <span className="badge">{totalQuantity}</span>
          </Link>
        )}
      </header>

      <main className="page">
        <Routes>
          <Route path="/" element={<StationsPage />} />
          <Route path="/stations/:stationId" element={<MenuPage />} />
          <Route path="/checkout" element={<CheckoutPage />} />
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
