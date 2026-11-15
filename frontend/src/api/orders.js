import client from './client.js'

export const createOrder = (body) => client.post('/orders', body).then((r) => r.data)

export const getOrder = (orderId) => client.get(`/orders/${orderId}`).then((r) => r.data)

// Giai đoạn C sẽ dùng:
export const getMyOrders = () => client.get('/orders/me').then((r) => r.data)