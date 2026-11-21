import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import App from './App.jsx'
import { AuthProvider } from './context/AuthContext.jsx'
import { CartProvider } from './context/CartContext.jsx'
import './styles.css'

// Trình duyệt có thể khôi phục nguyên trang cũ từ bộ nhớ đệm khi bấm "Quay lại"
// (vd. từ trang MoMo về), lúc đó giao diện là trạng thái cũ, không khớp địa chỉ hiện tại.
// Tải lại để luôn hiện đúng trang và dữ liệu mới nhất.
window.addEventListener('pageshow', (event) => {
  if (event.persisted) window.location.reload()
})

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <CartProvider>
          <App />
        </CartProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
)