/** API trafic. Types générés par `npm run gen:api`. */
import type { Feature, FeatureCollection, Geometry } from 'geojson'

import { mapObjectKey, type LayerId, type MapObject } from '@/types/mapObject'

import { apiFetch, withQuery, type LimitOffset, type Paginated } from './client'
import type { components } from './schema'

type Schemas = components['schemas']

export type Unit = Schemas['Unit']
export type CountingObjectType = Schemas['CountingObjectType']
export type CountingMeasure = Schemas['CountingMeasure']
export type CountingObject = Schemas['CountingObject']

/** En GeoJSON, l'`id` passe sur la Feature : les autres champs vont dans `properties`. */
export type CountingObjectProperties = Omit<CountingObject, 'id'>
export type CountingObjectFeature = Feature<Geometry, CountingObjectProperties>
export type CountingObjectCollection = FeatureCollection<Geometry, CountingObjectProperties>

export type CountingObjectPage = CountingObjectCollection & {
  count: number
  next: string | null
  previous: string | null
}
export type CountingObjectFilters = {
  typeCode?: string
  sourceCode?: string
  originCode?: string
  /** minlon, minlat, maxlon, maxlat (WGS84) */
  bbox?: [number, number, number, number]
}

export type SpatialPredicate = 'intersects' | 'within' | 'contains'

const BASE = '/api/traffic'

const OBJECTS_LIMIT = 1000

function countingObjectQuery(filters: CountingObjectFilters) {
  return {
    type_code: filters.typeCode,
    source_code: filters.sourceCode,
    origin_code: filters.originCode,
    bbox: filters.bbox?.join(','),
  }
}

/** Compteurs en GeoJSON (une page). */
export function getCountingObjects(
  filters: CountingObjectFilters = {},
  { limit = OBJECTS_LIMIT, offset }: LimitOffset = {},
) {
  const url = withQuery(`${BASE}/counting-objects`, {
    format: 'geojson',
    ...countingObjectQuery(filters),
    limit,
    offset,
  })
  return apiFetch<CountingObjectPage>(url)
}

/** Détail d'un compteur, en JSON (sans géométrie). */
export function getCountingObject(id: number) {
  return apiFetch<CountingObject>(`${BASE}/counting-objects/${id}`)
}

/** Compteurs qui intersectent, sont contenus dans ou contiennent `geometry`. */
export function searchCountingObjects(
  geometry: Geometry,
  predicate: SpatialPredicate = 'intersects',
  filters: CountingObjectFilters = {},
  { limit = OBJECTS_LIMIT, offset }: LimitOffset = {},
) {
  const url = withQuery(`${BASE}/counting-objects`, {
    format: 'geojson',
    ...countingObjectQuery(filters),
    [predicate]: JSON.stringify(geometry),
    limit,
    offset,
  })
  return apiFetch<CountingObjectPage>(url)
}

export function getMeasures(
  countingObjectId: number,
  filters: { unitCode?: string; practiceCode?: string } = {},
  { limit, offset }: LimitOffset = {},
) {
  const url = withQuery(`${BASE}/counting-measures`, {
    counting_object: countingObjectId,
    unit_code: filters.unitCode,
    practice_code: filters.practiceCode,
    limit,
    offset,
  })
  return apiFetch<Paginated<CountingMeasure>>(url)
}

export function getUnits({ limit, offset }: LimitOffset = {}) {
  return apiFetch<Paginated<Unit>>(withQuery(`${BASE}/units`, { limit, offset }))
}

export function getCountingObjectTypes({ limit, offset }: LimitOffset = {}) {
  return apiFetch<Paginated<CountingObjectType>>(
    withQuery(`${BASE}/counting-object-types`, { limit, offset }),
  )
}

// Adaptateur vers MapObject

export const COUNTING_OBJECT_LAYER: LayerId = 'traffic/counting-object'

export function countingObjectToMapObject(feature: CountingObjectFeature): MapObject {
  // GeoFeatureModelSerializer met la clé primaire sur la Feature.
  if (feature.id === undefined) throw new Error('Compteur sans identifiant dans la réponse API')
  return {
    key: mapObjectKey(COUNTING_OBJECT_LAYER, feature.id),
    id: feature.id,
    domain: 'traffic',
    layer: COUNTING_OBJECT_LAYER,
    label: feature.properties.external_id || `Compteur ${feature.id}`,
    geometry: feature.geometry,
  }
}

export async function getCountingObjectsForMap(filters: CountingObjectFilters = {}) {
  const page = await getCountingObjects(filters)
  return page.features.map(countingObjectToMapObject)
}
