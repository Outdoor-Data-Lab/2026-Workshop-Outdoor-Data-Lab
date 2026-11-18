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
  value?: number
}

/** Dégradé viridis, de la valeur la plus faible à la plus forte. */
export const VALUE_COLORS = ['#440154', '#3b528b', '#21918c', '#5ec962', '#fde725']

export function valueMax(values: (number | undefined)[]): number {
  return Math.max(1, ...values.map((v) => v ?? 0))
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
