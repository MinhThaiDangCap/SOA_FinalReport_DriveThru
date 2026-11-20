/**
 * Bộ icon SVG nét mảnh dùng chung (24x24, stroke theo currentColor).
 * Dùng: <Icon name="clock" /> hoặc <Icon name="star" filled size={18} />
 * Icon chỉ để trang trí nên mặc định aria-hidden; nếu icon đứng một mình thì truyền label.
 */
const PATHS = {
  mapPin: (
    <>
      <path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21Z" />
      <circle cx="12" cy="9.5" r="2.5" />
    </>
  ),
  phone: (
    <>
      <rect x="6.5" y="2.5" width="11" height="19" rx="2.5" />
      <path d="M10.5 18.5h3" />
    </>
  ),
  card: (
    <>
      <rect x="2.5" y="5" width="19" height="14" rx="2.5" />
      <path d="M2.5 10h19M6.5 15h4" />
    </>
  ),
  car: (
    <>
      <path d="M5 16.5H3.5v-4l2-5.2A2 2 0 0 1 7.4 6h9.2a2 2 0 0 1 1.9 1.3l2 5.2v4H19" />
      <path d="M3.5 12.5h17" />
      <circle cx="7.5" cy="16.5" r="2" />
      <circle cx="16.5" cy="16.5" r="2" />
      <path d="M9.5 16.5h5" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  timer: (
    <>
      <circle cx="12" cy="13.5" r="7.5" />
      <path d="M12 9.5v4l2.5 1.5M9.5 2.5h5M12 2.5v3.5M18.5 6l1.5-1.5" />
    </>
  ),
  star: <path d="m12 3 2.7 5.6 6.1.8-4.5 4.2 1.1 6.1L12 16.8l-5.4 2.9 1.1-6.1-4.5-4.2 6.1-.8L12 3Z" />,
  check: <path d="m5 12.5 4.5 4.5L19 7.5" />,
  x: <path d="M6 6l12 12M18 6 6 18" />,
  arrowLeft: <path d="M19 12H5m6-6-6 6 6 6" />,
  arrowRight: <path d="M5 12h14m-6-6 6 6-6 6" />,
  bell: (
    <>
      <path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 1.5h-15L6 16.5Z" />
      <path d="M10 20.5a2 2 0 0 0 4 0" />
    </>
  ),
  utensils: (
    <>
      <path d="M7 3v7a2 2 0 0 0 2 2v9M11 3v7a2 2 0 0 1-2 2M9 3v6" />
      <path d="M17 21V3c-1.9 1.2-3 3.6-3 6.5V14h3" />
    </>
  ),
  hourglass: (
    <>
      <path d="M6.5 3h11M6.5 21h11" />
      <path d="M7.5 3v3.5L12 12l4.5-5.5V3M7.5 21v-3.5L12 12l4.5 5.5V21" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16 16 4.5 4.5" />
    </>
  ),
  store: (
    <>
      <path d="M3.5 9.5 5 4h14l1.5 5.5" />
      <path d="M3.5 9.5a2.8 2.8 0 0 0 5.7 0 2.8 2.8 0 0 0 5.6 0 2.8 2.8 0 0 0 5.7 0" />
      <path d="M5 12v8.5h14V12M10 20.5v-5h4v5" />
    </>
  ),
  logout: (
    <>
      <path d="M14 4.5h3.5a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H14" />
      <path d="M10 8 6 12l4 4M6 12h10" />
    </>
  ),
  // ----- Món ăn theo danh mục -----
  burger: (
    <>
      <path d="M4 10.5C4 6.6 7.6 4 12 4s8 2.6 8 6.5H4Z" />
      <path d="M9 7.3h.01M12 6.3h.01M15 7.3h.01" />
      <path d="M3.5 13.5c1.4 0 1.4 1 2.8 1s1.4-1 2.9-1 1.4 1 2.8 1 1.4-1 2.8-1 1.4 1 2.9 1 1.4-1 2.8-1" />
      <path d="M4.5 17h15v.5A3 3 0 0 1 16.5 20.5h-9a3 3 0 0 1-3-3V17Z" />
    </>
  ),
  drumstick: (
    <>
      <path d="M10.6 13.4c-2.5-2.6-2.2-6.6.6-8.8 2.8-2.2 7-1.6 8.9 1.4 1.9 3 1 6.9-2.1 8.7-2.3 1.4-5.3 1.1-7.4-1.3Z" />
      <path d="M10.6 13.4 7.4 16.6" />
      <circle cx="5.6" cy="16.4" r="1.6" />
      <circle cx="7.6" cy="18.4" r="1.6" />
    </>
  ),
  fries: (
    <>
      <path d="M8.3 9.5 7.6 4M11 9.5V3M13.7 9.5l.4-5.5M16.3 9.5l.9-4.5" />
      <path d="M5 9.5h14l-1.6 11H6.6L5 9.5Z" />
      <path d="M5.6 13.5c2 1.5 4.2 2 6.4 2s4.4-.5 6.4-2" />
    </>
  ),
  cup: (
    <>
      <path d="M6 8.5h12l-1.3 12H7.3L6 8.5Z" />
      <path d="M5 8.5h14V6.8a1.3 1.3 0 0 0-1.3-1.3H6.3A1.3 1.3 0 0 0 5 6.8v1.7Z" />
      <path d="m12 5.5 1.6-3.5h3" />
      <path d="M6.6 13h10.8" />
    </>
  ),
  iceCream: (
    <>
      <path d="M7 10.5a5 5 0 0 1 10 0" />
      <path d="M6.5 10.5h11a1 1 0 0 1 0 2h-11a1 1 0 0 1 0-2Z" />
      <path d="M7.5 12.5 12 21.5l4.5-9" />
      <path d="m9.6 15.5 3.4-3M10.9 18.3l4-4.3" />
    </>
  ),
  bag: (
    <>
      <path d="M5 8h14l-1.2 12.5H6.2L5 8Z" />
      <path d="M9 10.5V6.5a3 3 0 0 1 6 0v4" />
    </>
  ),
}

export default function Icon({ name, size = 20, filled = false, label, className = '', strokeWidth = 1.8 }) {
  const content = PATHS[name]
  if (!content) return null
  return (
    <svg
      className={`icon ${className}`.trim()}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={filled ? 'currentColor' : 'none'}
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
    >
      {content}
    </svg>
  )
}

/** Hàng 5 ngôi sao chỉ để hiển thị (đánh giá đã có). */
export function StarRow({ value, size = 16 }) {
  return (
    <span className="star-row" role="img" aria-label={`${value} trên 5 sao`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <Icon key={n} name="star" size={size} filled={n <= value} className={n <= value ? 'star-fill' : 'star-empty'} />
      ))}
    </span>
  )
}
