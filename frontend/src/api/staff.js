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

// ----- Trạm 1: đơn đang giữ chỗ, tìm theo mã / biển số, nhận đơn -----
export const getHolds = () => client.get('/orders/station/holds').then((r) => r.data)

export const lookupOrders = (q) =>
  client.get('/orders/station/lookup', { params: { q } }).then((r) => r.data)

/** Nhận đơn ở trạm 1, khách chọn trả tiền mặt hoặc ZaloPay (gọi lại để đổi cách trả). */
export const checkIn = (orderId, paymentMethod) =>
  client.post(`/orders/${orderId}/check-in`, { payment_method: paymentMethod }).then((r) => r.data)

export const cancelOrderByStaff = (orderId) =>
  client.post(`/orders/${orderId}/cancel`).then((r) => r.data)

export const getOrderDetail = (orderId) => client.get(`/orders/${orderId}`).then((r) => r.data)

// ----- Bếp -----
export const getKitchenQueue = () => client.get('/orders/kitchen').then((r) => r.data)

// ----- Trạm 2 -----
export const getReadyOrders = () => client.get('/orders/station/ready').then((r) => r.data)

/** Trạm 1 ghi nhận đã thu tiền mặt: đơn vào bếp (gọi lại nhiều lần vẫn an toàn). */
export const confirmCash = (orderId) =>
  client.post('/payments/cash/confirm', { order_id: orderId }).then((r) => r.data)

// ----- Đánh giá của cửa hàng -----
export const getStationReviews = (stationId, rating) =>
  client
    .get(`/reviews/stations/${stationId}`, { params: rating ? { rating } : {} })
    .then((r) => r.data)
