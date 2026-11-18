/** API trafic. Types générés par `npm run gen:api`. */
import type { Feature, FeatureCollection, Geometry } from 'geojson'

import { mapObjectKey, type LayerId, type MapObject } from '@/types/mapObject'

import { apiFetch, withQuery } from './client'
import type { components } from './schema'

type Schemas = components['schemas']

export type Unit = Schemas['Unit']
export type CountingObjectType = Schemas['CountingObjectType']
export type CountingMeasure = Schemas['CountingMeasure']
export type SearchPredicate = Schemas['PredicateEnum']

/** Le schéma OpenAPI rend tout optionnel : on garde ses `properties`, avec une géométrie GeoJSON standard. */
export type CountingObjectProperties = NonNullable<Schemas['CountingObject']['properties']>
export type CountingObjectFeature = Feature<Geometry, CountingObjectProperties>
export type CountingObjectCollection = FeatureCollection<Geometry, CountingObjectProperties>

export type CountingObjectPage = CountingObjectCollection & {
  count: number
  next: string | null
  previous: string | null
}
export type Paginated<T> = {
  count: number
  next?: string | null
  previous?: string | null
  results: T[]
}

const BASE = '/api/traffic'

const OBJECTS_PAGE_SIZE = 1000

type PageOptions = { page?: number; pageSize?: number }

export function getCountingObjects(
  filters: { type?: number } = {},
  { page, pageSize = OBJECTS_PAGE_SIZE }: PageOptions = {},
) {
  const url = withQuery(`${BASE}/counting-object`, {
    type: filters.type,
    page,
    page_size: pageSize,
  })
  return apiFetch<CountingObjectPage>(url)
}

export function getCountingObject(id: number) {
  return apiFetch<CountingObjectFeature>(`${BASE}/counting-object/${id}`)
}

/** Compteurs qui intersectent ou sont contenus dans `geometry`. */
export function searchCountingObjects(
  geometry: Geometry,
  predicate: SearchPredicate = 'intersects',
  filters: { type?: number } = {},
  { page, pageSize = OBJECTS_PAGE_SIZE }: PageOptions = {},
) {
  const url = withQuery(`${BASE}/counting-object/search`, {
    type: filters.type,
    page,
    page_size: pageSize,
  })
  return apiFetch<CountingObjectPage>(url, {
    method: 'POST',
    body: JSON.stringify({ geometry, predicate }),
  })
}

/** Pages de 50, taille fixée par le backend. */
export function getMeasures(countingObjectId: number, { page }: { page?: number } = {}) {
  const url = withQuery(`${BASE}/counting-measure`, { counting_object: countingObjectId, page })
  return apiFetch<Paginated<CountingMeasure>>(url)
}

type LimitOffset = { limit?: number; offset?: number }

export function getUnits({ limit, offset }: LimitOffset = {}) {
  return apiFetch<Paginated<Unit>>(withQuery(`${BASE}/unit`, { limit, offset }))
}

export function getCountingObjectTypes({ limit, offset }: LimitOffset = {}) {
  return apiFetch<Paginated<CountingObjectType>>(
    withQuery(`${BASE}/counting-object-type`, { limit, offset }),
  )
}

// Adaptateur vers MapObject

export const COUNTING_OBJECT_LAYER: LayerId = 'traffic/counting-object'

export type CountingObjectMapObject = MapObject<CountingObjectProperties>

export function countingObjectToMapObject(feature: CountingObjectFeature): CountingObjectMapObject {
  // GeoFeatureModelSerializer met la clé primaire sur la Feature.
  if (feature.id === undefined) throw new Error('Compteur sans identifiant dans la réponse API')
  return {
    key: mapObjectKey(COUNTING_OBJECT_LAYER, feature.id),
    id: feature.id,
    domain: 'traffic',
    layer: COUNTING_OBJECT_LAYER,
    label: feature.properties.external_id || `Compteur ${feature.id}`,
    geometry: feature.geometry,
    properties: feature.properties,
  }
}

export async function getCountingObjectsForMap(filters: { type?: number } = {}) {
  const page = await getCountingObjects(filters)
  return page.features.map(countingObjectToMapObject)
}
