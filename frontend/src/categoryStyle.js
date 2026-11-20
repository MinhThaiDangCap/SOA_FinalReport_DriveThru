/**
 * Icon + tông màu cho từng danh mục món, dùng khi món chưa có ảnh.
 * Nhận theo tên danh mục (cả tiếng Việt lẫn tiếng Anh), danh mục lạ dùng icon dao nĩa mặc định.
 * Màu của từng tông nằm trong styles.css (.tone-burger, .tone-chicken, ...).
 */
const RULES = [
  { match: /burger|hamburger|bánh mì kẹp/, icon: 'burger', tone: 'burger' },
  { match: /gà|chicken|wing|cánh/, icon: 'drumstick', tone: 'chicken' },
  { match: /kèm|side|khoai|fries|snack/, icon: 'fries', tone: 'sides' },
  { match: /uống|drink|nước|trà|cà phê|coffee|tea|beverage/, icon: 'cup', tone: 'drinks' },
  { match: /tráng miệng|dessert|kem|ice cream|bánh ngọt|sweet/, icon: 'iceCream', tone: 'dessert' },
]

const DEFAULT = { icon: 'utensils', tone: 'default' }

export function categoryStyle(categoryName) {
  const name = (categoryName || '').toLowerCase()
  return RULES.find((r) => r.match.test(name)) || DEFAULT
}
