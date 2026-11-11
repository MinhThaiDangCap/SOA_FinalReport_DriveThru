import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Khi dev, frontend gọi /api/... (đường dẫn tương đối, giống lúc chạy sau Nginx).
// Vite chuyển tiếp tới từng service đang chạy trên localhost.
// Thêm dòng cho service khác khi cần: '/api/orders': 'http://localhost:8003', ...
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api/menu': 'http://localhost:8002',
    },
  },
})
