/**
 * Öffentliche Share-API (Empfänger). Eigene axios-Instanz OHNE App-Token,
 * damit anonyme Link-Nutzer ohne Login zugreifen können.
 */
import axios from 'axios'
import i18n from '../i18n'

const shared = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 300000,
  headers: { 'Content-Type': 'application/json' }
})

shared.interceptors.request.use(config => {
  config.headers['Accept-Language'] = i18n.global.locale.value
  return config
})

shared.interceptors.response.use(
  response => response.data,
  error => {
    // Backend-Fehlercode (share_invalid / share_revoked / share_limit ...) durchreichen
    const code = error.response?.data?.error
    if (code && typeof code === 'string') error.message = code
    return Promise.reject(error)
  }
)

export const getSharedReport = (token) => shared.get(`/api/shared/${token}/report`)
export const getSharedProfiles = (token) => shared.get(`/api/shared/${token}/profiles`)
export const sharedChat = (token, message, history = []) =>
  shared.post(`/api/shared/${token}/chat`, { message, chat_history: history })
export const sharedInterview = (token, agentId, prompt) =>
  shared.post(`/api/shared/${token}/interview`, { agent_id: agentId, prompt })
