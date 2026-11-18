/** Couches GeoJSON d'autres sites, déclarées dans l'admin. */
import type { Feature, FeatureCollection } from 'geojson'

import { apiFetch, type Paginated } from './client'
import type { components } from './schema'

export type ExternalLayer = components['schemas']['ExternalLayer']

export function getExternalLayers() {
  return apiFetch<Paginated<ExternalLayer>>('/api/commons/external-layers')
}

/** Toutes les features de `url`, en suivant les liens `next` d'une API paginée (Biodiv'Sports…). */
export async function getFeatures(url: string): Promise<Feature[]> {
  let features: Feature[] = []
  for (let next: string | null | undefined = url; next;) {
    // `application/json` seul : Biodiv'Sports répond 406 à `format=geojson`.
    const page: FeatureCollection & { next?: string | null } = await apiFetch(next, {
      headers: { Accept: 'application/geo+json, application/json' },
    })
    features = features.concat(page.features)
    next = page.next
  }
  return features
}
