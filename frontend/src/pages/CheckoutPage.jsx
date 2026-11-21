import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { errorMessage } from '../api/client.js'
import { createOrder, getAvailableCoupons } from '../api/orders.js'
import Icon from '../components/Icon.jsx'
import { useCart } from '../context/CartContext.jsx'
import { formatPrice, PAYMENT_METHODS } from '../format.js'
import { payForOrder } from '../payment.js'

/** "Giảm 10% (-8.700 ₫)" / "Giảm 20.000 ₫" (giỏ nhỏ hơn mức giảm: "Giảm 15.000 ₫") */
function couponLabel(c) {
  return c.discount_type === 'PERCENT'
    ? `Giảm ${c.discount_value}% (-${formatPrice(c.discount_amount)})`
    : `Giảm ${formatPrice(c.discount_amount)}`
}

/** "2027-02-15" -> "15/02/2027" */
function formatDay(iso) {
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y}`
}

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
  const [coupons, setCoupons] = useState([])
  const [couponsState, setCouponsState] = useState('loading') // loading | ready | error
  const [method, setMethod] = useState('ZALOPAY')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [placed, setPlaced] = useState(false)

  // Tải mã giảm giá dùng được cho giỏ hàng hiện tại (số tiền giảm phụ thuộc tạm tính)
  useEffect(() => {
    if (!subtotal) return undefined
    let cancelled = false
    setCouponsState('loading')
    getAvailableCoupons(subtotal)
      .then((list) => {
        if (cancelled) return
        setCoupons(list)
        setCouponsState('ready')
        // Mã đang chọn không còn dùng được (vd. giỏ đổi): bỏ chọn
        setCoupon((cur) => (list.some((c) => c.code === cur) ? cur : ''))
      })
      .catch(() => {
        if (!cancelled) setCouponsState('error')
      })
    return () => {
      cancelled = true
    }
  }, [subtotal])

  const selectedCoupon = coupons.find((c) => c.code === coupon)
  const discount = selectedCoupon ? selectedCoupon.discount_amount : 0

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
        coupon_code: coupon || null,
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
      <div className="cart-row checkout-subtotal">
        <span>Tạm tính</span>
        <span>{formatPrice(subtotal)}</span>
      </div>
      {selectedCoupon && (
        <div className="cart-row checkout-discount">
          <span className="with-icon">
            <Icon name="ticket" size={16} /> Mã {selectedCoupon.code}
          </span>
          <span>-{formatPrice(discount)}</span>
        </div>
      )}
      <div className="cart-total">
        <span>Tổng thanh toán</span>
        <strong>{formatPrice(subtotal - discount)}</strong>
      </div>
      <p className="checkout-hint">Giá cuối cùng do hệ thống tính lại khi đặt đơn.</p>

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
          Mã giảm giá
          <select
            className="coupon-select"
            value={coupon}
            onChange={(e) => setCoupon(e.target.value)}
            disabled={couponsState !== 'ready' || coupons.length === 0}
          >
            <option value="">
              {couponsState === 'loading'
                ? 'Đang tải mã giảm giá...'
                : coupons.length
                  ? 'Không dùng mã giảm giá'
                  : 'Hiện chưa có mã giảm giá'}
            </option>
            {coupons.map((c) => (
              <option key={c.code} value={c.code}>
                {c.code} · {couponLabel(c)} · HSD {formatDay(c.valid_to)}
              </option>
            ))}
          </select>
          {couponsState === 'error' ? (
            <span className="field-error">Không tải được mã giảm giá. Bạn vẫn đặt đơn được.</span>
          ) : (
            couponsState === 'ready' &&
            coupons.length > 0 && (
              <span className="field-help">
                Có {coupons.length} mã dùng được cho đơn này, sắp xếp theo số tiền giảm.
              </span>
            )
          )}
        </label>

        <fieldset className="option-group">
          <legend>Hình thức thanh toán</legend>
          {PAYMENT_METHODS.map((m) => (
            <label key={m.value} className={`option ${method === m.value ? 'option-on' : ''}`}>
              <input
                type="radio"
                name="method"
                value={m.value}
                checked={method === m.value}
                onChange={() => setMethod(m.value)}
              />
              <span className="option-icon">
                <Icon name={m.icon} size={20} />
              </span>
              <span>
                <strong>{m.title}</strong>
                <small>
                  {m.note} {m.checkoutNote}
                </small>
              </span>
            </label>
          ))}
        </fieldset>

        <button type="submit" className="btn btn-block" disabled={busy}>
          {busy ? 'Đang xử lý...' : PAYMENT_METHODS.find((m) => m.value === method)?.online ? 'Đặt đơn và thanh toán' : 'Đặt đơn'}
        </button>
      </form>
    </div>
  )
}