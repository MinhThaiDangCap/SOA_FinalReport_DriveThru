import client from './client.js'

export const getOrderReview = (orderId) =>
  client.get(`/reviews/orders/${orderId}`).then((r) => r.data)

export const createReview = (body) => client.post('/reviews', body).then((r) => r.data)

export const getStationStats = (stationId) =>
  client.get(`/reviews/stations/${stationId}/stats`).then((r) => r.data)