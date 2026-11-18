import type { Geometry } from 'geojson'

export type Domain = 'traffic' | 'biodiversity'

export type LayerId = `${Domain}/${string}`

/** Objet affiché sur la carte : le minimum pour dessiner et identifier. Le détail se charge par `id`. */
export interface MapObject {
  key: string
  id: number | string
  domain: Domain
  layer: LayerId
  label: string
  geometry: Geometry
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
}
