const vnd = new Intl.NumberFormat('vi-VN')

/** 45000 -> "45.000 ₫" */
export const formatPrice = (amount) => `${vnd.format(amount)} ₫`


/** Tên hiển thị của trạng thái đơn */
export const STATUS_LABEL = {
  PENDING_PAYMENT: 'Chờ thanh toán',
  CONFIRMED: 'Đã xác nhận',
  PREPARING: 'Đang chuẩn bị',
  READY: 'Sẵn sàng nhận',
  ARRIVED: 'Khách đã đến',
  COMPLETED: 'Hoàn thành',
  CANCELLED: 'Đã hủy',
}

export const METHOD_LABEL = {
  MOMO: 'MoMo',
  CASH: 'Trả tại quầy',
}


/** "2026-11-15T14:06:30+00:00" -> "15/11/2026 21:06" (giờ máy người dùng) */
export function formatDateTime(iso) {
  // Một số service (feedback) trả giờ UTC không kèm múi giờ: coi như UTC
  const text = typeof iso === 'string' && !/(Z|[+-]\d\d:?\d\d)$/.test(iso) ? `${iso}Z` : iso
  const d = new Date(text)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' })
}