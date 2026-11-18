/** API biodiversité : taxons protégés ou menacés par maille. Types générés par `npm run gen:api`. */
import type { Feature, MultiPolygon } from 'geojson'

import { i18n } from '@/i18n'
import { mapObjectKey, type LayerId, type MapObject } from '@/types/mapObject'

import { apiFetch, fetchAllFeatures, withQuery, type GeoJsonPage, type LimitOffset } from './client'
import type { components } from './schema'

type Schemas = components['schemas']

export type TaxonConservationStatus = Schemas['TaxonConservationStatus']
export type AreaTaxon = Schemas['AreaTaxon']

export type BiodivAreaProperties = Required<NonNullable<Schemas['TaxonStatusArea']['properties']>>
export type BiodivAreaFeature = Feature<MultiPolygon, BiodivAreaProperties>
export type BiodivAreaPage = GeoJsonPage<MultiPolygon, BiodivAreaProperties>

export type AreaTaxaProperties = Required<NonNullable<Schemas['TaxonListArea']['properties']>>
export type AreaTaxaFeature = Feature<MultiPolygon, AreaTaxaProperties>
export type AreaTaxaPage = GeoJsonPage<MultiPolygon, AreaTaxaProperties>

/** Sans filtre, le backend renvoie toutes les mailles de France, même vides. */
export type BiodivAreaFilters = {
  areaCode?: string
  /** Seulement les mailles ayant au moins un taxon protégé ou menacé */
  withTaxa?: boolean
}

const BASE = '/api/biodiversity'

const AREAS_LIMIT = 1000

function areaQuery(filters: BiodivAreaFilters) {
  return {
    area_code: filters.areaCode,
    has_protected_or_threatened_taxa: filters.withTaxa || undefined,
  }
}

/** Mailles avec leur nombre de taxons protégés, menacés, et l'un ou l'autre (une page, GeoJSON). */
export function getBiodivAreas(
  filters: BiodivAreaFilters = {},
  { limit = AREAS_LIMIT, offset }: LimitOffset = {},
) {
  const url = withQuery(`${BASE}/synthetic_data`, { ...areaQuery(filters), limit, offset })
  return apiFetch<BiodivAreaPage>(url)
}

/** Mailles avec la liste de leurs taxons protégés ou menacés (une page, GeoJSON). */
export function getAreasTaxa(
  filters: BiodivAreaFilters = {},
  { limit = AREAS_LIMIT, offset }: LimitOffset = {},
) {
  const url = withQuery(`${BASE}/list_taxa`, { ...areaQuery(filters), limit, offset })
  return apiFetch<AreaTaxaPage>(url)
}

/** Taxons protégés ou menacés d'une maille. */
export function getAreaTaxa(idArea: number) {
  return apiFetch<AreaTaxaFeature>(`${BASE}/list_taxa/${idArea}`)
}

// Adaptateur vers MapObject

export const BIODIV_AREA_LAYER: LayerId = 'biodiversity/area'

export function biodivAreaToMapObject(feature: BiodivAreaFeature): MapObject {
  if (feature.id === undefined) throw new Error('Maille sans identifiant dans la réponse API')
  const count = feature.properties.protected_or_threatened_taxa_count
  return {
    key: mapObjectKey(BIODIV_AREA_LAYER, feature.id),
    id: feature.id,
    domain: 'biodiversity',
    layer: BIODIV_AREA_LAYER,
    label: i18n.global.t('layers.biodivArea', {
      name: feature.properties.area_name ?? feature.id,
      count,
    }),
    geometry: feature.geometry,
  }
}

/** Mailles ayant au moins un taxon protégé ou menacé, page par page. */
export async function getBiodivAreasForMap() {
  const url = withQuery(`${BASE}/synthetic_data`, {
    ...areaQuery({ withTaxa: true }),
    limit: AREAS_LIMIT,
  })
  return (await fetchAllFeatures<BiodivAreaFeature>(url)).map(biodivAreaToMapObject)
}
