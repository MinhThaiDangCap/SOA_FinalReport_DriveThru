import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { errorMessage } from '../api/client.js'
import { getStationMenu } from '../api/menu.js'
import CartPanel from '../components/CartPanel.jsx'
import MenuItemCard from '../components/MenuItemCard.jsx'
import { useCart } from '../context/CartContext.jsx'

// Tải lại menu định kỳ để thấy món nhân viên vừa báo hết
const REFRESH_MS = 30_000

export default function MenuPage() {
  const stationId = Number(useParams().stationId)
  const { cart, addItem, setQuantity } = useCart()

  const [menu, setMenu] = useState(null)
  const [error, setError] = useState('')
  const [activeCategory, setActiveCategory] = useState('all')

  const load = useCallback(
    (silent = false) => {
      if (!Number.isInteger(stationId) || stationId <= 0) {
        setError('Cửa hàng không hợp lệ')
        return Promise.resolve()
      }
      if (!silent) {
        setError('')
        setMenu(null)
      }
      return getStationMenu(stationId)
        .then((data) => {
          setMenu(data)
          setError('')
        })
        .catch((err) => {
          // Tải ngầm thất bại thì giữ menu đang hiển thị
          if (!silent) setError(errorMessage(err))
        })
    },
    [stationId],
  )

  useEffect(() => {
    load()
    const timer = setInterval(() => load(true), REFRESH_MS)
    return () => clearInterval(timer)
  }, [load])

  const quantityById = useMemo(() => {
    if (cart.stationId !== stationId) return {}
    return Object.fromEntries(cart.items.map((i) => [i.id, i.quantity]))
  }, [cart, stationId])

  // Món đang trong giỏ nhưng cửa hàng vừa báo hết
  const soldOutIds = useMemo(() => {
    if (!menu) return new Set()
    const ids = menu.categories.flatMap((c) => c.items.filter((i) => !i.available).map((i) => i.id))
    return new Set(ids)
  }, [menu])

  const handleAdd = (item) => {
    const otherStation = cart.stationId !== null && cart.stationId !== stationId
    if (otherStation && cart.items.length > 0) {
      const ok = window.confirm(
        `Giỏ hàng đang có món của "${cart.stationName}". Mỗi đơn chỉ đặt ở một cửa hàng.\n` +
          `Xóa giỏ cũ và bắt đầu đặt tại "${menu.station.name}"?`,
      )
      if (!ok) return
    }
    addItem(menu.station, item)
  }

  if (error) {
    return (
      <div className="state">
        <p className="error-text">{error}</p>
        <div className="state-actions">
          <button className="btn" onClick={() => load()}>Thử lại</button>
          <Link to="/" className="btn btn-ghost">Chọn cửa hàng khác</Link>
        </div>
      </div>
    )
  }

  if (!menu) return <div className="state">Đang tải menu…</div>

  const visibleCategories =
    activeCategory === 'all'
      ? menu.categories
      : menu.categories.filter((c) => c.id === activeCategory)

  return (
    <div className="menu-layout">
      <div className="menu-main">
        <Link to="/" className="back-link">← Đổi cửa hàng</Link>
        <div className="station-header">
          <h1>{menu.station.name}</h1>
          <p>{menu.station.address}</p>
          {menu.station.opening_hours && <p>Giờ mở cửa: {menu.station.opening_hours}</p>}
        </div>

        {menu.categories.length === 0 ? (
          <div className="state">Cửa hàng này chưa có món nào.</div>
        ) : (
          <>
            <nav className="category-tabs" aria-label="Danh mục">
              <button
                className={activeCategory === 'all' ? 'tab active' : 'tab'}
                onClick={() => setActiveCategory('all')}
              >
                Tất cả
              </button>
              {menu.categories.map((c) => (
                <button
                  key={c.id}
                  className={activeCategory === c.id ? 'tab active' : 'tab'}
                  onClick={() => setActiveCategory(c.id)}
                >
                  {c.name}
                </button>
              ))}
            </nav>

            {visibleCategories.map((category) => (
              <section key={category.id} className="category-section">
                <h2>{category.name}</h2>
                <div className="item-grid">
                  {category.items.map((item) => (
                    <MenuItemCard
                      key={item.id}
                      item={item}
                      quantity={quantityById[item.id] || 0}
                      onAdd={() => handleAdd(item)}
                      onSetQuantity={(q) => setQuantity(item.id, q)}
                    />
                  ))}
                </div>
              </section>
            ))}
          </>
        )}
      </div>

      <CartPanel stationId={stationId} soldOutIds={soldOutIds} />
    </div>
  )
}
