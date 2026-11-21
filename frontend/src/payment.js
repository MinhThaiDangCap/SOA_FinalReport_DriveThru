import { createMomoPayment, mockPay } from './api/payments.js'

/**
 * Tạo giao dịch MoMo cho đơn rồi đưa khách đi thanh toán.
 * - Chế độ giả lập: gọi API giả, trả về đường dẫn nội bộ để web chuyển tới.
 * - MoMo thật: chuyển trình duyệt sang trang thanh toán MoMo, trả về null.
 */
export async function payForOrder(orderId) {
  const payment = await createMomoPayment(orderId)

  if (payment.payment_url.includes('/api/payments/mock/pay')) {
    await mockPay(payment.txn_ref, true)
    return `/orders/${orderId}`
  }

  window.location.assign(payment.payment_url)
  return null
}
