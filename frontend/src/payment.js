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

  // Trước khi rời web, đổi địa chỉ của trang hiện tại thành trang đơn hàng.
  // Khách bấm "Quay lại" trên trình duyệt (từ trang MoMo) sẽ về đúng đơn đang thanh toán,
  // thay vì trang /checkout đã hết giỏ hàng. Trang đơn có sẵn nút thanh toán lại / đổi phương thức.
  window.history.replaceState(window.history.state, '', `/orders/${orderId}`)
  window.location.assign(payment.payment_url)
  return null
}
