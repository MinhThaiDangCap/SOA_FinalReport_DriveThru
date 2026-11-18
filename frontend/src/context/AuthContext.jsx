import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import { TOKEN_KEY, USER_KEY } from '../api/client.js'
import { getMe, loginRequest, registerRequest } from '../api/auth.js'

const REFRESH_KEY = 'refresh_token'

const AuthContext = createContext(null)

function readUser() {
  try {
    if (!localStorage.getItem(TOKEN_KEY)) return null
    return JSON.parse(localStorage.getItem(USER_KEY))
  } catch {
    return null
  }
}

/**
 * Lưu phiên đăng nhập. user.role là ADMIN, STAFF hoặc CUSTOMER (chữ hoa).
 * Dạng user: { id, email, full_name, phone, role, station_id, ... }
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(readUser)

  const login = useCallback(async (email, password) => {
    const data = await loginRequest(email, password)
    localStorage.setItem(TOKEN_KEY, data.access_token)
    localStorage.setItem(REFRESH_KEY, data.refresh_token)
    localStorage.setItem(USER_KEY, JSON.stringify(data.user))
    setUser(data.user)
    return data.user
  }, [])

  // Backend đăng ký xong không trả token, nên đăng nhập luôn cho khách.
  const register = useCallback(
    async (body) => {
      await registerRequest(body)
      return login(body.email, body.password)
    },
    [login],
  )

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_KEY)
    localStorage.removeItem(USER_KEY)
    setUser(null)
  }, [])

  // Mỗi lần mở web: lấy lại thông tin mới nhất từ auth-service, vì bản lưu trong
  // trình duyệt có thể đã cũ (admin đổi tên, đổi cửa hàng, khóa tài khoản...).
  useEffect(() => {
    if (!localStorage.getItem(TOKEN_KEY)) return
    let cancelled = false
    getMe()
      .then((fresh) => {
        if (cancelled) return
        const cached = readUser()
        // Vai trò / cửa hàng nằm trong token: đổi thì phải đăng nhập lại để có token mới
        if (!fresh.is_active || (cached && (cached.role !== fresh.role || cached.station_id !== fresh.station_id))) {
          logout()
          return
        }
        localStorage.setItem(USER_KEY, JSON.stringify(fresh))
        setUser(fresh)
      })
      .catch(() => {}) // 401 đã được client.js xử lý (đưa về trang đăng nhập)
    return () => {
      cancelled = true
    }
  }, [logout])

  const value = useMemo(
    () => ({ user, isAuthenticated: !!user, login, register, logout }),
    [user, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth phải dùng bên trong <AuthProvider>')
  return ctx
}