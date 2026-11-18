/** API trafic. Types générés par `npm run gen:api`. */
import type { Feature, FeatureCollection, Geometry, MultiPolygon } from 'geojson'

import { i18n } from '@/i18n'
import { mapObjectKey, type LayerId, type MapObject } from '@/types/mapObject'

import {
  apiFetch,
  fetchAllFeatures,
  withQuery,
  type GeoJsonPage,
  type LimitOffset,
  type Paginated,
} from './client'
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

export type CountingObjectPage = GeoJsonPage<Geometry, CountingObjectProperties>
export type CountingObjectFilters = {
  typeCode?: string
  sourceCode?: string
  originCode?: string
  /** minlon, minlat, maxlon, maxlat (WGS84) */
  bbox?: [number, number, number, number]
  /** Zone `ref_geo` : objets qui l'intersectent. */
  areaId?: number
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
    area_id: filters.areaId,
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

// Synthèse de fréquentation par maille de 1 km

export type TrafficAreaScore = 'basic' | 'cazalis'
export type SourceCount = Schemas['SourceCount']
export type TrafficAreaProperties = Required<NonNullable<Schemas['AreaCounts']['properties']>>
export type TrafficAreaFeature = Feature<MultiPolygon, TrafficAreaProperties>
export type TrafficAreaPage = GeoJsonPage<MultiPolygon, TrafficAreaProperties>

export type TrafficAreaFilters = {
  sources?: number[]
  dateFrom?: string
  dateTo?: string
  scores?: TrafficAreaScore[]
  sourceWeights?: Record<number, number>
  bbox?: [number, number, number, number]
  /** Zone `ref_geo` : objets qui l'intersectent. */
  areaId?: number
}

function trafficAreasUrl(
  filters: TrafficAreaFilters,
  { limit = OBJECTS_LIMIT, offset }: LimitOffset,
) {
  return withQuery(`${BASE}/areas`, {
    source: filters.sources,
    date_from: filters.dateFrom,
    date_to: filters.dateTo,
    scores: filters.scores,
    source_weights: filters.sourceWeights
      ? Object.entries(filters.sourceWeights)
          .map(([source, weight]) => `${source}:${weight}`)
          .join(',')
      : undefined,
    bbox: filters.bbox?.join(','),
    area_id: filters.areaId,
    limit,
    offset,
  })
}

/** Mailles ayant des mesures, avec comptages et scores (une page). */
export function getTrafficByArea(filters: TrafficAreaFilters = {}, page: LimitOffset = {}) {
  return apiFetch<TrafficAreaPage>(trafficAreasUrl(filters, page))
}

/** Une maille, avec ses comptages par source et le détail du score cazalis (404 si elle n'a pas de mesure). */
export function getTrafficArea(id: number) {
  return apiFetch<TrafficAreaFeature>(withQuery(`${BASE}/areas/${id}`, { scores: ['cazalis'] }))
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

export const TRAFFIC_AREA_LAYER: LayerId = 'traffic/area'

/** Zoom minimal des tuiles de compteurs (en dessous, le backend ne renvoie rien : les mailles résument). */
export const TILE_MIN_ZOOM = 10

/** Gabarit d'URL des tuiles vectorielles de compteurs, absolu comme MapLibre l'attend. */
export function countingObjectTileUrl(filters: { typeCode?: string; areaId?: number } = {}) {
  const path = withQuery(`${BASE}/tiles/{z}/{x}/{y}.pbf`, {
    type_code: filters.typeCode,
    area_id: filters.areaId,
  })
  return `${window.location.origin}${path}`
}

/** Score utilisé pour colorer les mailles. */
const MAP_AREA_SCORE: TrafficAreaScore = 'cazalis'

/** Valeur d'un score : un nombre, ou `{ score, …détails }` quand l'API joint ses détails (cazalis). */
function scoreValue(score?: TrafficAreaProperties['score'][string]): number | undefined {
  return typeof score === 'object' ? (score.score as number | undefined) : score
}

export function trafficAreaToMapObject(feature: TrafficAreaFeature): MapObject {
  if (feature.id === undefined) throw new Error('Maille sans identifiant dans la réponse API')
  const score = scoreValue(feature.properties.score[MAP_AREA_SCORE])
  return {
    key: mapObjectKey(TRAFFIC_AREA_LAYER, feature.id),
    id: feature.id,
    domain: 'traffic',
    layer: TRAFFIC_AREA_LAYER,
    label: `${i18n.global.t('layers.cellName')} ${feature.id}`,
    geometry: feature.geometry,
    value: score,
  }
}

/** Toutes les mailles, page par page. Les scores portent sur toutes les mailles, pas sur la page ; sans `sourceWeights`, le backend estime les poids de `cazalis`. */
export async function getTrafficAreasForMap(filters: TrafficAreaFilters = {}) {
  const url = trafficAreasUrl({ ...filters, scores: [MAP_AREA_SCORE] }, {})
  return (await fetchAllFeatures<TrafficAreaFeature>(url)).map(trafficAreaToMapObject)
}
