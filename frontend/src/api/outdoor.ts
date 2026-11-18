/** API outdoor (offres d'activités). Types générés par `npm run gen:api`. */
import type { Feature, Geometry, MultiPolygon } from 'geojson'

import { mapObjectKey, type LayerId, type MapObject } from '@/types/mapObject'

import { apiFetch, withQuery, type GeoJsonPage, type LimitOffset, type Paginated } from './client'
import type { components } from './schema'

type Schemas = components['schemas']

export type Offer = Schemas['Offer']

/** En GeoJSON, l'`id` passe sur la Feature et `geom` devient la géométrie. */
export type OfferProperties = Omit<Offer, 'id' | 'geom'>
export type OfferFeature = Feature<Geometry, OfferProperties>
export type OfferPage = GeoJsonPage<Geometry, OfferProperties>

export type OfferFilters = {
  practice?: number
  source?: number
  uuid?: string
  externalId?: string
  /** Date de création, ISO 8601 */
  dateFrom?: string
  dateTo?: string
  /** Code d'une zone `ref_geo` (ex. `26` pour la Drôme) */
  areaCode?: string
  /** Zone `ref_geo` : objets qui l'intersectent. */
  areaId?: number
}

// Les routes outdoor gardent le `/` final (pas encore alignées sur la convention de l'API).
const BASE = '/api/outdoor'

const OFFERS_LIMIT = 1000

function offerQuery(filters: OfferFilters) {
  return {
    practice: filters.practice,
    source: filters.source,
    uuid: filters.uuid,
    external_id: filters.externalId,
    date_from: filters.dateFrom,
    date_to: filters.dateTo,
    area: filters.areaCode,
    area_id: filters.areaId,
  }
}

/** Offres en GeoJSON (une page). */
export function getOffers(
  filters: OfferFilters = {},
  { limit = OFFERS_LIMIT, offset }: LimitOffset = {},
) {
  const url = withQuery(`${BASE}/offers/`, {
    format: 'geojson',
    ...offerQuery(filters),
    limit,
    offset,
  })
  return apiFetch<OfferPage>(url)
}

export type AreaOffer = Pick<Offer, 'id' | 'name' | 'practice_label' | 'source_label'>

/** Offres qui intersectent la zone `ref_geo` `areaId`, sans géométrie. */
export function getAreaOffers(areaId: number) {
  const url = withQuery(`${BASE}/offers/`, {
    area_id: areaId,
    fields: 'id,name,practice_label,source_label',
    limit: OFFERS_LIMIT,
  })
  return apiFetch<Paginated<AreaOffer>>(url)
}

/** Détail d'une offre, en JSON. */
export function getOffer(id: number) {
  return apiFetch<Offer>(`${BASE}/offers/${id}/`)
}

// Nombre d'offres par zone. Ces champs ne figurent pas dans le schéma OpenAPI
// (serializer choisi selon les paramètres) : ils sont typés ici.

export type PracticeCount = {
  practice_code: string
  practice_label: string
  count: number
}

export type OfferAreaProperties = Omit<Schemas['LArea'], 'id_area'> & {
  offers_count: number
  /** Présent seulement avec `byPractice` */
  offers_count_by_practice?: PracticeCount[]
}
export type OfferAreaFeature = Feature<MultiPolygon, OfferAreaProperties>
export type OfferAreaPage = GeoJsonPage<MultiPolygon, OfferAreaProperties>

export type OfferAreaFilters = {
  /** Type de zone (`M1` pour la maille de 1 km, `COM` pour les communes…) */
  typeCode: string
  byPractice?: boolean
  /** minlon, minlat, maxlon, maxlat (WGS84) */
  bbox?: [number, number, number, number]
}

function offerAreasQuery(filters: OfferAreaFilters) {
  return {
    type_code: filters.typeCode,
    practice_count: filters.byPractice || undefined,
    bbox: filters.bbox?.join(','),
  }
}

/** Zones d'un type avec leur nombre d'offres, en GeoJSON (une page). */
export function getOffersByArea(
  filters: OfferAreaFilters,
  { limit = OFFERS_LIMIT, offset }: LimitOffset = {},
) {
  const url = withQuery(`${BASE}/offers/area/`, {
    format: 'geojson',
    ...offerAreasQuery(filters),
    limit,
    offset,
  })
  return apiFetch<OfferAreaPage>(url)
}

/** Même chose sans géométrie, en JSON. */
export function getOfferCountsByArea(
  filters: OfferAreaFilters,
  { limit = OFFERS_LIMIT, offset }: LimitOffset = {},
) {
  const url = withQuery(`${BASE}/offers/area/`, { ...offerAreasQuery(filters), limit, offset })
  return apiFetch<Paginated<OfferAreaProperties & { id_area: number }>>(url)
}

// Adaptateur vers MapObject

export const OFFER_LAYER: LayerId = 'outdoor/offer'

export function offerToMapObject(feature: OfferFeature): MapObject {
  if (feature.id === undefined) throw new Error('Offre sans identifiant dans la réponse API')
  return {
    key: mapObjectKey(OFFER_LAYER, feature.id),
    id: feature.id,
    domain: 'outdoor',
    layer: OFFER_LAYER,
    label: `${feature.properties.practice_label} ${feature.properties.external_id}`.trim(),
    geometry: feature.geometry,
  }
}

export async function getOffersForMap(filters: OfferFilters = {}) {
  const page = await getOffers(filters)
  return page.features.map(offerToMapObject)
}
