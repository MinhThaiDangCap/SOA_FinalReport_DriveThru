import { createVnpayPayment, mockPay } from './api/payments.js'

/**
 * Tạo giao dịch VNPay cho đơn rồi đưa khách đi thanh toán.
 * - Chế độ giả lập: gọi API giả, trả về đường dẫn nội bộ để web chuyển tới.
 * - VNPay thật: chuyển trình duyệt sang cổng VNPay, trả về null.
 */
export async function payForOrder(orderId) {
  const payment = await createVnpayPayment(orderId)

  if (payment.payment_url.includes('/api/payments/mock/pay')) {
    await mockPay(payment.txn_ref, true)
    return `/orders/${orderId}`
  }

  window.location.assign(payment.payment_url)
  return null
}