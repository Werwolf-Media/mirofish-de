/**
 * Zugriffsschutz (Login)
 * Hält das Zugriffstoken reaktiv und im localStorage.
 */
import { reactive } from 'vue'
import service from '../api'

const TOKEN_KEY = 'appToken'

const state = reactive({
  token: localStorage.getItem(TOKEN_KEY) || ''
})

export const auth = state

export function isAuthenticated() {
  return !!state.token
}

export function getToken() {
  return state.token
}

export async function login(password) {
  try {
    const res = await service.post('/api/auth/login', { password })
    if (res && res.success && res.token) {
      state.token = res.token
      localStorage.setItem(TOKEN_KEY, res.token)
      return true
    }
    return false
  } catch (e) {
    return false
  }
}

export function logout() {
  state.token = ''
  localStorage.removeItem(TOKEN_KEY)
}

export default state
