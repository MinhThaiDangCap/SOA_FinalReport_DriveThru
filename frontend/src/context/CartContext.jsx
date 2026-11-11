import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

// order-service giới hạn mỗi món tối đa 20 phần trong một đơn
export const MAX_QUANTITY = 20

const STORAGE_KEY = 'drive_thru_cart'
const EMPTY = { stationId: null, stationName: '', items: [] }

const CartContext = createContext(null)

function loadCart() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY))
    if (saved && Array.isArray(saved.items)) return saved
  } catch {
    // localStorage bị chặn hoặc dữ liệu hỏng: dùng giỏ trống
  }
  return EMPTY
}

/**
 * Giỏ hàng chỉ thuộc về MỘT cửa hàng, vì một đơn chỉ đặt ở một station.
 * Dạng: { stationId, stationName, items: [{ id, name, price, quantity }] }
 */
export function CartProvider({ children }) {
  const [cart, setCart] = useState(loadCart)

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(cart))
    } catch {
      // bỏ qua: giỏ vẫn hoạt động trong phiên này
    }
  }, [cart])

  /** Thêm 1 phần. Nếu giỏ đang của cửa hàng khác thì thay bằng giỏ mới. */
  const addItem = useCallback((station, item) => {
    setCart((prev) => {
      const sameStation = prev.stationId === station.id
      const items = sameStation ? prev.items : []
      const existing = items.find((i) => i.id === item.id)
      const nextItems = existing
        ? items.map((i) =>
            i.id === item.id ? { ...i, quantity: Math.min(i.quantity + 1, MAX_QUANTITY) } : i,
          )
        : [...items, { id: item.id, name: item.name, price: item.price, quantity: 1 }]
      return { stationId: station.id, stationName: station.name, items: nextItems }
    })
  }, [])

  /** Đặt số lượng; <= 0 thì bỏ món khỏi giỏ. */
  const setQuantity = useCallback((itemId, quantity) => {
    setCart((prev) => {
      const items =
        quantity <= 0
          ? prev.items.filter((i) => i.id !== itemId)
          : prev.items.map((i) =>
              i.id === itemId ? { ...i, quantity: Math.min(quantity, MAX_QUANTITY) } : i,
            )
      return items.length ? { ...prev, items } : EMPTY
    })
  }, [])

  const clear = useCallback(() => setCart(EMPTY), [])

  const value = useMemo(() => {
    const totalQuantity = cart.items.reduce((sum, i) => sum + i.quantity, 0)
    const subtotal = cart.items.reduce((sum, i) => sum + i.price * i.quantity, 0)
    return { cart, totalQuantity, subtotal, addItem, setQuantity, clear }
  }, [cart, addItem, setQuantity, clear])

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>
}

export function useCart() {
  const ctx = useContext(CartContext)
  if (!ctx) throw new Error('useCart phải dùng bên trong <CartProvider>')
  return ctx
}
