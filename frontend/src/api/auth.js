import client from './client.js'

export const loginRequest = (email, password) =>
  client.post('/auth/login', { email, password }).then((r) => r.data)

export const registerRequest = (body) =>
  client.post('/auth/register', body).then((r) => r.data)

export const getMe = () => client.get('/auth/me').then((r) => r.data)