import client from './client.js'

// ----- Đơn hàng (nhân viên + admin) -----
// Nhân viên: backend tự lọc theo cửa hàng của mình. Admin: truyền stationId hoặc bỏ trống = mọi cửa hàng.
export const getQueue = (stationId) =>
  client
    .get('/orders/queue', { params: stationId ? { station_id: stationId } : {} })
    .then((r) => r.data)

export const getRecentOrders = (stationId, limit = 20) =>
  client
    .get('/orders/recent', { params: { limit, ...(stationId ? { station_id: stationId } : {}) } })
    .then((r) => r.data)

export const updateOrderStatus = (orderId, status, note) =>
  client.patch(`/orders/${orderId}/status`, { status, note: note || null }).then((r) => r.data)

/** Ghi nhận đã thu tiền mặt tại quầy (gọi lại nhiều lần vẫn an toàn). */
export const confirmCash = (orderId) =>
  client.post('/payments/cash/confirm', { order_id: orderId }).then((r) => r.data)

// ----- Đánh giá của cửa hàng -----
export const getStationReviews = (stationId, rating) =>
  client
    .get(`/reviews/stations/${stationId}`, { params: rating ? { rating } : {} })
    .then((r) => r.data)
