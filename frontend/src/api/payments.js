import client from './client.js'

export const createZaloPayPayment = (orderId) =>
  client.post('/payments/zalopay/create', { order_id: orderId }).then((r) => r.data)

/** Gửi nguyên chuỗi query ZaloPay trả về (vd "?appid=...&apptransid=...&checksum=..."). */
export const getZaloPayResult = (search) =>
  client.get(`/payments/zalopay/return${search}`).then((r) => r.data)

// Chỉ dùng khi PAYMENT_MOCK_MODE=true ở payment-service
export const mockPay = (txnRef, success = true) =>
  client
    .get('/payments/mock/pay', { params: { txn_ref: txnRef, success } })
    .then((r) => r.data)
