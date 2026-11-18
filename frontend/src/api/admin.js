import client from './client.js'

// ----- Thống kê -----
export const getOrderStats = () => client.get('/orders/stats').then((r) => r.data)

// ----- Nhân viên -----
export const getStaff = () => client.get('/auth/staff').then((r) => r.data)
export const createStaff = (body) => client.post('/auth/staff', body).then((r) => r.data)
export const toggleStaff = (id) =>
  client.patch(`/auth/staff/${id}/toggle-active`).then((r) => r.data)

// ----- Mã giảm giá -----
export const getCoupons = () => client.get('/orders/coupons').then((r) => r.data)
export const createCoupon = (body) => client.post('/orders/coupons', body).then((r) => r.data)
export const updateCoupon = (id, body) =>
  client.patch(`/orders/coupons/${id}`, body).then((r) => r.data)
