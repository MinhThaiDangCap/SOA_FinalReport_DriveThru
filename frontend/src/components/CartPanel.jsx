import { useNavigate } from 'react-router-dom'

import { MAX_QUANTITY, useCart } from '../context/CartContext.jsx'
import { formatPrice } from '../format.js'

/**
 * Giỏ hàng bên cạnh menu.
 * soldOutIds: id các món cửa hàng vừa báo hết, để cảnh báo trước khi đặt.
 */
export default function CartPanel({ stationId, soldOutIds }) {
  const { cart, subtotal, totalQuantity, setQuantity, clear } = useCart()
  const navigate = useNavigate()

  const isThisStation = cart.stationId === stationId
  const items = isThisStation ? cart.items : []
  const hasSoldOut = items.some((i) => soldOutIds.has(i.id))

  return (
    <aside className="cart-panel" aria-label="Giỏ hàng">
      <div className="cart-head">
        <h2>Giỏ hàng</h2>
        {items.length > 0 && (
          <button className="link-btn" onClick={clear}>Xóa hết</button>
        )}
      </div>

      {items.length === 0 ? (
        <p className="cart-empty">
          {cart.stationId !== null && !isThisStation
            ? `Bạn đang có giỏ hàng ở "${cart.stationName}". Thêm món ở đây sẽ thay giỏ đó.`
            : 'Chưa có món nào. Bấm "Thêm" để chọn món.'}
        </p>
      ) : (
        <>
          <ul className="cart-list">
            {items.map((item) => {
              const soldOut = soldOutIds.has(item.id)
              return (
                <li key={item.id} className={soldOut ? 'cart-row warn' : 'cart-row'}>
                  <div className="cart-row-info">
                    <span className="cart-row-name">{item.name}</span>
                    {soldOut ? (
                      <span className="cart-row-warn">Vừa hết hàng, hãy bỏ khỏi giỏ</span>
                    ) : (
                      <span className="cart-row-price">
                        {formatPrice(item.price * item.quantity)}
                      </span>
                    )}
                  </div>
                  <div className="stepper">
                    <button
                      aria-label={`Bớt một ${item.name}`}
                      onClick={() => setQuantity(item.id, item.quantity - 1)}
                    >
                      −
                    </button>
                    <span>{item.quantity}</span>
                    <button
                      aria-label={`Thêm một ${item.name}`}
                      onClick={() => setQuantity(item.id, item.quantity + 1)}
                      disabled={soldOut || item.quantity >= MAX_QUANTITY}
                    >
                      +
                    </button>
                  </div>
                </li>
              )
            })}
          </ul>

          <div className="cart-total">
            <span>Tạm tính ({totalQuantity} món)</span>
            <strong>{formatPrice(subtotal)}</strong>
          </div>

          <button
            className="btn btn-block"
            disabled={hasSoldOut}
            onClick={() => navigate('/checkout')}
          >
            Tiếp tục đặt đơn
          </button>
          {hasSoldOut && (
            <p className="cart-note">Bỏ món đã hết khỏi giỏ để tiếp tục.</p>
          )}
        </>
      )}
    </aside>
  )
}
