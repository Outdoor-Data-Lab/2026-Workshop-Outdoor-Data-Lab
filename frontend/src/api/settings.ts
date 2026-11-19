/** Réglages de l'instance : saisis dans l'admin, ou réglages du serveur (grille). */
import { apiFetch } from './client'
import type { AreaMatch } from './refGeo'

export type InstanceSettings = {
  /** Zone qui filtre la carte à l'ouverture (ex. le parc national). */
  default_area: AreaMatch | null
  /** Grille des mailles (type ref_geo : M0.5, M1…). */
  grid_area_type: string
}

let settings: Promise<InstanceSettings> | undefined

/** Une seule requête pour toute l'appli. */
export function getInstanceSettings() {
  settings ??= apiFetch<InstanceSettings>('/api/commons/instance-settings')
  return settings
}

/** Côté d'une maille de la grille, ex. « 500 m » pour M0.5 ; `undefined` si le code ne le dit pas. */
export function gridSize(areaType: string): string | undefined {
  const km = /^M(\d+(?:\.\d+)?)$/.exec(areaType)?.[1]
  if (km === undefined) return undefined
  return Number(km) < 1 ? `${Number(km) * 1000} m` : `${Number(km)} km`
}
