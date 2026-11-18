import client from './client.js'

export const createOrder = (body) => client.post('/orders', body).then((r) => r.data)

export const getOrder = (orderId) => client.get(`/orders/${orderId}`).then((r) => r.data)

export const getMyOrders = () => client.get('/orders/me').then((r) => r.data)

/** Công khai: số đơn đang chờ và thời gian chờ ước tính của từng cửa hàng. */
export const getWaitTimes = () => client.get('/orders/wait-times').then((r) => r.data)

export const cancelOrder = (orderId) =>
  client.post(`/orders/${orderId}/cancel`).then((r) => r.data)

export const markArrived = (orderId) =>
  client.post(`/orders/${orderId}/arrived`).then((r) => r.data)