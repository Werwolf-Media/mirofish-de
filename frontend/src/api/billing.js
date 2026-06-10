/**
 * Abrechnungs-API (nur Inhaber). Eigener Client mit Admin-Token (X-Admin-Token),
 * unabhängig vom normalen Tool-Login.
 */
import axios from 'axios'
import i18n from '../i18n'

const admin = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' }
})

admin.interceptors.request.use(config => {
  config.headers['Accept-Language'] = i18n.global.locale.value
  const tk = localStorage.getItem('adminToken')
  if (tk) config.headers['X-Admin-Token'] = tk
  return config
})

admin.interceptors.response.use(
  response => response.data,
  error => {
    const code = error.response?.data?.error
    if (code && typeof code === 'string') error.message = code
    return Promise.reject(error)
  }
)

export const adminLogin = (password) => admin.post('/api/auth/admin-login', { password })
export const listBilling = () => admin.get('/api/billing/list')
export const updateBilling = (projectId, data) => admin.post(`/api/billing/${projectId}/update`, data)
export const setDefaultPrice = (price) => admin.post('/api/billing/settings', { default_billing_price_eur: price })
