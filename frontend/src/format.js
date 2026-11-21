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

/**
 * Các phương thức thanh toán khách chọn được. Thêm phương thức mới: thêm 1 dòng ở đây
 * (và cho order-service chấp nhận giá trị đó). online = trả trước qua cổng thanh toán.
 */
export const PAYMENT_METHODS = [
  {
    value: 'ZALOPAY',
    icon: 'wallet',
    title: 'Thanh toán online (ZaloPay)',
    note: 'Quét QR bằng app ZaloPay hoặc trả bằng thẻ ATM / thẻ quốc tế.',
    // Ghi chú thêm ở bước đặt đơn
    checkoutNote: 'Đã thanh toán thì không hủy trên ứng dụng, cần hủy vui lòng gọi hotline 1900 6868.',
    online: true,
  },
  {
    value: 'CASH',
    icon: 'cash',
    title: 'Trả tại quầy',
    note: 'Đơn gửi ngay tới cửa hàng, trả tiền mặt khi nhận món.',
    checkoutNote: 'Sau khi đặt không đổi sang trả online được.',
    online: false,
  },
]

export const METHOD_LABEL = {
  ZALOPAY: 'ZaloPay',
  CASH: 'Trả tại quầy',
}


/** Đọc giờ từ API. Một số service (feedback) trả giờ UTC không kèm múi giờ: coi như UTC. */
function parseTime(iso) {
  const text = typeof iso === 'string' && !/(Z|[+-]\d\d:?\d\d)$/.test(iso) ? `${iso}Z` : iso
  return new Date(text)
}

/** "2026-11-15T14:06:30+00:00" -> "21:06" (giờ máy người dùng) */
export function formatTime(iso) {
  const d = parseTime(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
}

/** Số phút từ bây giờ tới thời điểm iso (âm nếu đã qua), làm tròn lên. */
export function minutesUntil(iso) {
  const t = parseTime(iso).getTime()
  if (Number.isNaN(t)) return null
  return Math.ceil((t - Date.now()) / 60000)
}

/** "2026-11-15T14:06:30+00:00" -> "15/11/2026 21:06" (giờ máy người dùng) */
export function formatDateTime(iso) {
  const d = parseTime(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' })
}

/** 75 -> "1 giờ 15 phút", 4311 -> "2 ngày 23 giờ", 8 -> "8 phút" */
export function formatDuration(minutes) {
  const m = Math.max(0, Math.floor(minutes))
  if (m < 60) return `${m} phút`
  if (m < 1440) {
    const rest = m % 60
    return rest ? `${Math.floor(m / 60)} giờ ${rest} phút` : `${m / 60} giờ`
  }
  const hours = Math.floor((m % 1440) / 60)
  return hours ? `${Math.floor(m / 1440)} ngày ${hours} giờ` : `${Math.floor(m / 1440)} ngày`
}
