import { i18n } from '@/i18n'

import { ApiError, NetworkError } from './client'

const { t } = i18n.global

/** Message lisible par l'utilisateur à partir d'une erreur technique. */
export function describeError(error: unknown): string {
  if (error instanceof NetworkError) {
    return t('errors.network')
  }
  if (error instanceof ApiError) {
    if (error.status >= 500) {
      return t('errors.server')
    }
    if (error.status === 404) return t('errors.notFound')
    if (error.status === 401 || error.status === 403) {
      return t('errors.forbidden')
    }
    if (error.status === 400) return drfMessage(error.body) ?? t('errors.badRequest')
    return t('errors.unexpectedStatus', { status: error.status })
  }
  return t('errors.unexpected')
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
    if (message)
      return field === 'non_field_errors' ? message : t('errors.field', { field, message })
  }
  return undefined
}
