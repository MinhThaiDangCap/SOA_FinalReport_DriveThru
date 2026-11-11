const vnd = new Intl.NumberFormat('vi-VN')

/** 45000 -> "45.000 ₫" */
export const formatPrice = (amount) => `${vnd.format(amount)} ₫`
