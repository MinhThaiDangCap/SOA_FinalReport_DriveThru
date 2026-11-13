import { Link } from 'react-router-dom'

import { useCart } from '../context/CartContext.jsx'
import { formatPrice } from '../format.js'

/**
 * Trang giữ chỗ cho bước đặt đơn (biển số xe, mã giảm giá, chọn thanh toán).
 * Phần này nối với order-service: POST /api/orders với
 *   { station_id, license_plate, payment_method, coupon_code, items: [{ menu_item_id, quantity }] }
 * Dữ liệu giỏ lấy từ useCart().
 */
export default function CheckoutPage() {
  const { cart, subtotal } = useCart()

  if (cart.items.length === 0) {
    return (
      <div className="state">
        <p>Giỏ hàng đang trống.</p>
        <Link to="/" className="btn">Chọn cửa hàng</Link>
      </div>
    )
  }

  return (
    <div className="checkout">
      <Link to={`/stations/${cart.stationId}`} className="back-link">← Quay lại menu</Link>
      <h1>Xác nhận đơn</h1>
      <p className="checkout-station">Nhận món tại: <strong>{cart.stationName}</strong></p>

      <ul className="cart-list">
        {cart.items.map((item) => (
          <li key={item.id} className="cart-row">
            <span>{item.quantity} × {item.name}</span>
            <span>{formatPrice(item.price * item.quantity)}</span>
          </li>
        ))}
      </ul>
      <div className="cart-total">
        <span>Tạm tính</span>
        <strong>{formatPrice(subtotal)}</strong>
      </div>

      <p className="notice">
        Bước nhập biển số xe, mã giảm giá và thanh toán đang được phát triển.
      </p>
    </div>
  )
}
