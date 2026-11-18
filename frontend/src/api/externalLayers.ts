/** Couches GeoJSON d'autres sites, déclarées dans l'admin. */
import { apiFetch, fetchAllFeatures, type Paginated } from './client'
import type { components } from './schema'

export type ExternalLayer = components['schemas']['ExternalLayer']

export function getExternalLayers() {
  return apiFetch<Paginated<ExternalLayer>>('/api/commons/external-layers')
}

/** Toutes les features de `url`, en suivant les liens `next` d'une API paginée (Biodiv'Sports…). */
export function getFeatures(url: string) {
  // `application/json` seul : Biodiv'Sports répond 406 à `format=geojson`.
  return fetchAllFeatures(url, { headers: { Accept: 'application/geo+json, application/json' } })
}
