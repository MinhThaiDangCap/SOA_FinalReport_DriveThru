import axios from 'axios'

// Đường dẫn tương đối: chạy được cả với Vite proxy (dev) lẫn Nginx/ngrok (demo).
const client = axios.create({ baseURL: '/api', timeout: 8000 })

// Tên khóa localStorage dùng chung cho cả app; trang đăng nhập (auth) sẽ ghi vào đây.
export const TOKEN_KEY = 'access_token'

client.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

/** Lấy thông báo lỗi để hiển thị. Mọi service trả lỗi dạng {"detail": "..."}. */
export function errorMessage(error) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (error?.code === 'ECONNABORTED') return 'Máy chủ phản hồi quá lâu, vui lòng thử lại.'
  if (!error?.response) return 'Không kết nối được máy chủ.'
  return 'Đã có lỗi xảy ra, vui lòng thử lại.'
}

export default client
