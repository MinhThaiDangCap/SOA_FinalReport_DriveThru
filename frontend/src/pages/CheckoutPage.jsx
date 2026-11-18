import { useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { errorMessage } from '../api/client.js'
import { createOrder } from '../api/orders.js'
import Icon from '../components/Icon.jsx'
import { useCart } from '../context/CartContext.jsx'
import { formatPrice } from '../format.js'
import { payForOrder } from '../payment.js'

// Biển số VN: 2 số tỉnh + 1-2 chữ cái (+ 1 số với xe máy) + 4-5 số. Bỏ qua dấu cách, "-" và ".".
// Ví dụ hợp lệ: 51A-12345, 51A 123.45, 30LD-1234, 59X1-123.45
const PLATE_RE = /^\d{2}[A-Z]{1,2}\d?\d{4,5}$/

export function validatePlate(value) {
  const v = value.trim()
  if (!v) return 'Vui lòng nhập biển số xe để nhân viên nhận ra xe của bạn khi tới quầy.'
  if (!PLATE_RE.test(v.toUpperCase().replace(/[\s.-]/g, ''))) {
    return 'Biển số xe chưa đúng định dạng. Ví dụ: 51A-12345 hoặc 59X1-123.45.'
  }
  return ''
}

export default function CheckoutPage() {
  const { cart, subtotal, clear } = useCart()
  const navigate = useNavigate()
  const plateRef = useRef(null)
  const [plate, setPlate] = useState('')
  const [plateTouched, setPlateTouched] = useState(false)
  const [coupon, setCoupon] = useState('')
  const [method, setMethod] = useState('MOMO')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [placed, setPlaced] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    const plateError = validatePlate(plate)
    setPlateTouched(true)
    if (plateError) {
      plateRef.current?.focus()
      return
    }
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

  const plateMessage = plateTouched ? validatePlate(plate) : ''

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
      <Link to={`/stations/${cart.stationId}`} className="back-link"><Icon name="arrowLeft" size={16} /> Quay lại menu</Link>
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

      <form className="form checkout-form" onSubmit={handleSubmit} noValidate>
        {error && <div className="form-error" role="alert">{error}</div>}

        <label className={`field${plateMessage ? ' field-invalid' : ''}`}>
          Biển số xe <span className="field-required">*</span>
          <input
            ref={plateRef}
            value={plate}
            onChange={(e) => setPlate(e.target.value)}
            onBlur={() => plate.trim() && setPlateTouched(true)}
            placeholder="Ví dụ: 51A-12345"
            maxLength={15}
            autoComplete="off"
            aria-invalid={!!plateMessage}
            aria-describedby="plate-msg"
          />
          {plateMessage ? (
            <span id="plate-msg" className="field-error" role="alert">
              {plateMessage}
            </span>
          ) : (
            <span id="plate-msg" className="field-help">
              Nhân viên dùng biển số để nhận ra xe của bạn khi tới quầy.
            </span>
          )}
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