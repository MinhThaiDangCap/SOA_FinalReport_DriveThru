import client from './client.js'

// ----- Khách -----
export const getStations = () => client.get('/menu/stations').then((r) => r.data)

export const getStationMenu = (stationId) =>
  client.get(`/menu/stations/${stationId}/menu`).then((r) => r.data)

// ----- Nhân viên (dashboard sẽ dùng) -----
export const setItemAvailability = (stationId, itemId, available) =>
  client
    .put(`/menu/stations/${stationId}/items/${itemId}/availability`, { available })
    .then((r) => r.data)

// ----- Admin (dashboard sẽ dùng) -----
export const getAllStations = () => client.get('/menu/stations/all').then((r) => r.data)
export const createStation = (body) => client.post('/menu/stations', body).then((r) => r.data)
export const updateStation = (id, body) =>
  client.put(`/menu/stations/${id}`, body).then((r) => r.data)
export const deactivateStation = (id) => client.delete(`/menu/stations/${id}`)

export const getCategories = () => client.get('/menu/categories').then((r) => r.data)
export const createCategory = (body) => client.post('/menu/categories', body).then((r) => r.data)
export const updateCategory = (id, body) =>
  client.put(`/menu/categories/${id}`, body).then((r) => r.data)
export const deleteCategory = (id) => client.delete(`/menu/categories/${id}`)

export const getItems = (params) => client.get('/menu/items', { params }).then((r) => r.data)
export const createItem = (body) => client.post('/menu/items', body).then((r) => r.data)
export const updateItem = (id, body) => client.put(`/menu/items/${id}`, body).then((r) => r.data)
export const deactivateItem = (id) => client.delete(`/menu/items/${id}`)
