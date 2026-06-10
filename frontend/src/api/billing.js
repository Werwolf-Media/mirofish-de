/**
 * Abrechnungs-API (eingeloggt).
 */
import service from './index'

export const listBilling = () => service.get('/api/billing/list')
export const updateBilling = (projectId, data) => service.post(`/api/billing/${projectId}/update`, data)
