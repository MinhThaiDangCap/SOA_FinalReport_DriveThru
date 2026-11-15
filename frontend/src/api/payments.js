import client from './client.js'

export const createVnpayPayment = (orderId) =>
  client.post('/payments/vnpay/create', { order_id: orderId }).then((r) => r.data)

// Chỉ dùng khi PAYMENT_MOCK_MODE=true ở payment-service
export const mockPay = (txnRef, success = true) =>
  client
    .get('/payments/mock/pay', { params: { txn_ref: txnRef, success } })
    .then((r) => r.data)