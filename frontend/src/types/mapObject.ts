import type { Geometry } from 'geojson'

/** `external` : couches GeoJSON d'autres sites, hors concepts, cochées au choix de l'utilisateur. */
export type Domain = 'traffic' | 'biodiversity' | 'external'

export type LayerId = `${Domain}/${string}`

/** Objet affiché sur la carte : le minimum pour dessiner et identifier. Le détail se charge par `id`. */
export interface MapObject {
  key: string
  id: number | string
  domain: Domain
  layer: LayerId
  label: string
  geometry: Geometry
  /** Sinon, la couleur du domaine. */
  color?: string
  /** Attributs affichés dans le détail, quand il ne se charge pas par `id` (couches externes). */
  attributes?: Record<string, unknown>
}

export function mapObjectKey(layer: LayerId, id: number | string): string {
  return `${layer}:${id}`
}

export function layerDomain(layer: LayerId): Domain {
  return layer.split('/')[0] as Domain
}

export const DOMAIN_COLORS: Record<Domain, string> = {
  traffic: '#e4572e',
  biodiversity: '#2e9e5b',
  external: '#3388ff',
}
