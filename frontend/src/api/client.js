 import axios from 'axios'

// Đường dẫn tương đối: chạy được cả với Vite proxy (dev) lẫn Nginx/ngrok (demo).
const client = axios.create({ baseURL: '/api', timeout: 8000 })

// Tên khóa localStorage dùng chung cho cả app.
export const TOKEN_KEY = 'access_token'
export const USER_KEY = 'drive_thru_user'

client.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Token hết hạn hoặc không hợp lệ: xóa phiên đăng nhập và về trang đăng nhập.
// Bỏ qua chính API đăng nhập (sai mật khẩu cũng trả 401).
client.interceptors.response.use(
  (res) => res,
  (error) => {
    const url = error?.config?.url || ''
    const hadToken = !!localStorage.getItem(TOKEN_KEY)
    if (error?.response?.status === 401 && hadToken && !url.includes('/auth/login')) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem('refresh_token')
      localStorage.removeItem(USER_KEY)
      window.location.assign('/login')
    }
    return Promise.reject(error)
  },
)

/** Lấy thông báo lỗi để hiển thị. Mọi service trả lỗi dạng {"detail": "..."}. */
export function errorMessage(error) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    const firstMsg = detail[0]?.msg || ''
    const field = detail[0]?.loc?.[detail[0].loc.length - 1]
    if (firstMsg.startsWith('Value error, ')) return firstMsg.slice('Value error, '.length)
    if (field === 'email') return 'Email không đúng định dạng (ví dụ: ten@gmail.com).'
    if (field === 'phone') return 'Số điện thoại phải gồm 10 chữ số và bắt đầu bằng số 0.'
    if (field === 'password') return 'Mật khẩu phải có từ 6 ký tự trở lên.'
    if (field === 'full_name') return 'Họ và tên phải có từ 2 ký tự trở lên.'
    return firstMsg || 'Thông tin chưa hợp lệ, vui lòng kiểm tra lại.'
  }
  if (error?.response?.status === 422) return 'Thông tin chưa hợp lệ, vui lòng kiểm tra lại.'
  if (error?.code === 'ECONNABORTED') return 'Máy chủ phản hồi quá lâu, vui lòng thử lại.'
  if (!error?.response) return 'Không kết nối được máy chủ.'
  return 'Đã có lỗi xảy ra, vui lòng thử lại.'
}

export default client