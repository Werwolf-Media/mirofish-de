/**
 * Share-Verwaltung (Ersteller, eingeloggt). Nutzt den authentifizierten Client.
 */
import service from './index'

export const createShare = (reportId) => service.post('/api/share/create', { report_id: reportId })
export const getShareByReport = (reportId) => service.get(`/api/share/by-report/${reportId}`)
export const deactivateShare = (token) => service.post(`/api/share/${token}/deactivate`)
export const activateShare = (token) => service.post(`/api/share/${token}/activate`)
export const resetShare = (token) => service.post(`/api/share/${token}/reset`)
