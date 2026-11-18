/** Réglages de l'instance, saisis dans l'admin. */
import { apiFetch } from './client'
import type { AreaMatch } from './refGeo'

export type InstanceSettings = {
  /** Zone qui filtre la carte à l'ouverture (ex. le parc national). */
  default_area: AreaMatch | null
}

export function getInstanceSettings() {
  return apiFetch<InstanceSettings>('/api/commons/instance-settings')
}
