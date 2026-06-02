import service from './index'

/**
 * KI-Onboarding-Assistent.
 * @param {Array<{role:string, content:string}>} messages - ganze Konversation
 * @param {string} documentText - optionaler extrahierter Dokumenttext als Kontext
 * Liefert (via Interceptor) { success, data: { status, reply, simulationRequirement, seedText, title } }
 */
export const chatWizard = (messages, documentText = '') =>
  service.post('/api/wizard/chat', { messages, documentText })

/**
 * Text aus einem hochgeladenen Dokument extrahieren (für den Gesprächskontext).
 * @param {FormData} formData - mit Feld "file"
 * Liefert { success, data: { text, filename } }
 */
export const extractWizardDoc = (formData) =>
  service.post('/api/wizard/extract', formData)
