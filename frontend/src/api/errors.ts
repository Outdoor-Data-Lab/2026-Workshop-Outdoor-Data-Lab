import { ApiError, NetworkError } from './client'

/** Message lisible par l'utilisateur à partir d'une erreur technique. */
export function describeError(error: unknown): string {
  if (error instanceof NetworkError) {
    return 'Connexion au serveur impossible. Vérifiez votre réseau.'
  }
  if (error instanceof ApiError) {
    if (error.status >= 500) {
      return 'Le serveur est indisponible pour le moment. Réessayez plus tard.'
    }
    if (error.status === 404) return 'Élément introuvable.'
    if (error.status === 401 || error.status === 403) {
      return "Vous n'avez pas accès à cette ressource."
    }
    if (error.status === 400) return drfMessage(error.body) ?? 'Requête invalide.'
    return `Réponse inattendue du serveur (${error.status}).`
  }
  return 'Une erreur inattendue est survenue.'
}

/** Premier message d'une erreur DRF : `{ detail }`, `{ champ: [...] }` ou `[...]`. */
function drfMessage(body: unknown): string | undefined {
  if (typeof body === 'string') return body
  if (Array.isArray(body)) return drfMessage(body[0])
  if (body && typeof body === 'object') {
    const record = body as Record<string, unknown>
    if ('detail' in record) return drfMessage(record.detail)
    const [field, value] = Object.entries(record)[0] ?? []
    const message = drfMessage(value)
    if (message) return field === 'non_field_errors' ? message : `${field} : ${message}`
  }
  return undefined
}
