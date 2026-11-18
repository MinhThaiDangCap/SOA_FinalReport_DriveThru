import { MAX_QUANTITY } from '../context/CartContext.jsx'
import { formatPrice } from '../format.js'
import Icon from './Icon.jsx'

export default function MenuItemCard({ item, quantity, onAdd, onSetQuantity }) {
  const soldOut = !item.available

  return (
    <article className={soldOut ? 'item-card sold-out' : 'item-card'}>
      <div className="item-thumb">
        {item.image_url ? (
          <img src={item.image_url} alt="" loading="lazy" />
        ) : (
          <Icon name="utensils" size={34} strokeWidth={1.5} />
        )}
        {soldOut && <span className="sold-out-tag">Hết hàng</span>}
      </div>

      <div className="item-body">
        <h3>{item.name}</h3>
        {item.description && <p className="item-desc">{item.description}</p>}
        <div className="item-footer">
          <span className="item-price">{formatPrice(item.price)}</span>

          {soldOut ? (
            <button className="btn btn-small" disabled>Tạm hết</button>
          ) : quantity > 0 ? (
            <div className="stepper">
              <button
                aria-label={`Bớt một ${item.name}`}
                onClick={() => onSetQuantity(quantity - 1)}
              >
                −
              </button>
              <span aria-live="polite">{quantity}</span>
              <button
                aria-label={`Thêm một ${item.name}`}
                onClick={() => onSetQuantity(quantity + 1)}
                disabled={quantity >= MAX_QUANTITY}
              >
                +
              </button>
            </div>
          ) : (
            <button className="btn btn-small" onClick={onAdd}>Thêm</button>
          )}
        </div>
      </div>
    </article>
  )
}
