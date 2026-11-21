/**
 * Biển số xe hiển thị giống biển ô tô Việt Nam: nền trắng, viền đen, chữ đậm,
 * định dạng chuẩn "51A-123.45" (5 số) hoặc "51A-1234" (4 số).
 * Biển số khách nhập lộn xộn (vd "51a 12345", "51A.123-45") vẫn hiện đúng chuẩn.
 */
// Thứ tự thử: biển 5 số trước (phổ biến nhất), rồi tới biển 4 số.
// "41A12384" -> 41A-123.84 (ô tô), "59X112345" -> 59X1-123.45 (xe máy), "30LD1234" -> 30LD-1234
const PLATE_PATTERNS = [
  /^(\d{2}[A-Z]{1,2})(\d{5})$/,
  /^(\d{2}[A-Z]{1,2}\d)(\d{5})$/,
  /^(\d{2}[A-Z]{1,2})(\d{4})$/,
  /^(\d{2}[A-Z]{1,2}\d)(\d{4})$/,
]

export function formatPlate(raw) {
  const compact = String(raw || '').toUpperCase().replace(/[\s.-]/g, '')
  for (const re of PLATE_PATTERNS) {
    const m = compact.match(re)
    if (m) {
      const [, series, digits] = m
      const number = digits.length === 5 ? `${digits.slice(0, 3)}.${digits.slice(3)}` : digits
      return `${series}-${number}`
    }
  }
  return String(raw || '').toUpperCase()
}

export default function LicensePlate({ value, size = 'md', className = '' }) {
  const text = formatPlate(value)
  return (
    <span className={`plate plate-${size} ${className}`.trim()} aria-label={`Biển số ${text}`}>
      {text}
    </span>
  )
}
