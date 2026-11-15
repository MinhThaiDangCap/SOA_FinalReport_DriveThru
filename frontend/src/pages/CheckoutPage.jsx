import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { errorMessage } from '../api/client.js'
import { createOrder } from '../api/orders.js'
import { useCart } from '../context/CartContext.jsx'
import { formatPrice } from '../format.js'
import { payForOrder } from '../payment.js'

export default function CheckoutPage() {
  const { cart, subtotal, clear } = useCart()
  const navigate = useNavigate()
  const [plate, setPlate] = useState('')
  const [coupon, setCoupon] = useState('')
  const [method, setMethod] = useState('MOMO')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [placed, setPlaced] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)

    let order
    try {
      order = await createOrder({
        station_id: cart.stationId,
        license_plate: plate.trim(),
        payment_method: method,
        coupon_code: coupon.trim() || null,
        items: cart.items.map((i) => ({ menu_item_id: i.id, quantity: i.quantity })),
      })
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
      return
    }

    // Đơn đã tạo xong, giỏ hết nhiệm vụ
    setPlaced(true)
    clear()

    if (method === 'CASH') {
      navigate(`/orders/${order.id}`, { replace: true })
      return
    }

    try {
      const next = await payForOrder(order.id)
      if (next) navigate(next, { replace: true })
    } catch (err) {
      // Đơn đã có nhưng chưa tạo được link thanh toán: khách thanh toán lại ở trang đơn
      navigate(`/orders/${order.id}`, {
        replace: true,
        state: { notice: errorMessage(err) },
      })
    }
  }

  if (placed) {
    return (
      <div className="state">
        <p>Đang xử lý đơn hàng của bạn...</p>
      </div>
    )
  }

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
      <p className="checkout-hint">
        Mã giảm giá (nếu có) sẽ được áp dụng khi đặt đơn. Giá cuối cùng do hệ thống tính.
      </p>

      <form className="form checkout-form" onSubmit={handleSubmit}>
        {error && <div className="form-error" role="alert">{error}</div>}

        <label className="field">
          Biển số xe
          <input
            value={plate}
            onChange={(e) => setPlate(e.target.value)}
            placeholder="Ví dụ: 51A-12345"
            minLength={4}
            maxLength={15}
            required
          />
        </label>

        <label className="field">
          Mã giảm giá (không bắt buộc)
          <input
            value={coupon}
            onChange={(e) => setCoupon(e.target.value)}
            maxLength={30}
          />
        </label>

        <fieldset className="option-group">
          <legend>Hình thức thanh toán</legend>
          <label className={`option ${method === 'MOMO' ? 'option-on' : ''}`}>
            <input
              type="radio"
              name="method"
              value="MOMO"
              checked={method === 'MOMO'}
              onChange={() => setMethod('MOMO')}
            />
            <span>
              <strong>Thanh toán online (MoMo)</strong>
              <small>Thanh toán ngay để đơn được xác nhận</small>
            </span>
          </label>
          <label className={`option ${method === 'CASH' ? 'option-on' : ''}`}>
            <input
              type="radio"
              name="method"
              value="CASH"
              checked={method === 'CASH'}
              onChange={() => setMethod('CASH')}
            />
            <span>
              <strong>Trả tại quầy</strong>
              <small>Thanh toán khi nhận món, nhân viên sẽ thu tiền</small>
            </span>
          </label>
        </fieldset>

        <button type="submit" className="btn btn-block" disabled={busy}>
          {busy ? 'Đang xử lý...' : method === 'MOMO' ? 'Đặt đơn và thanh toán' : 'Đặt đơn'}
        </button>
      </form>
    </div>
  )
}