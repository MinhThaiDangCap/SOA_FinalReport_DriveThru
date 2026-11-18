import client from './client.js'

export const createMomoPayment = (orderId) =>
  client.post('/payments/momo/create', { order_id: orderId }).then((r) => r.data)

/** Gửi nguyên chuỗi query MoMo trả về (vd "?partnerCode=...&signature=...") để lấy kết quả. */
export const getMomoResult = (search) =>
  client.get(`/payments/momo/return${search}`).then((r) => r.data)

// Chỉ dùng khi PAYMENT_MOCK_MODE=true ở payment-service
export const mockPay = (txnRef, success = true) =>
  client
    .get('/payments/mock/pay', { params: { txn_ref: txnRef, success } })
    .then((r) => r.data)
