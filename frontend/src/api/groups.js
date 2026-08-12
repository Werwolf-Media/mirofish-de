/**
 * Projektmappen-API ("Projekte"): fester Realitäts-Seed + mehrere Runs
 * mit unterschiedlichen Prompts.
 */
import service from './index'

// formData: name, seed_text?, files[]
export const createGroup = (formData) => {
  return service({
    url: '/api/groups/create',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000
  })
}

export const listGroups = () => service.get('/api/groups/list')

export const getGroup = (groupId) => service.get(`/api/groups/${groupId}`)

export const deleteGroup = (groupId) => service.delete(`/api/groups/${groupId}`)

// data: { simulation_requirement, additional_context?, include_german_sources? }
// Startet die Ontologie serverseitig aus dem Projekt-Seed (kann 1-2 Min. dauern)
export const runInGroup = (groupId, data) => {
  return service({
    url: `/api/groups/${groupId}/run`,
    method: 'post',
    data,
    timeout: 600000
  })
}
