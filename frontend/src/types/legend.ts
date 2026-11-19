import type { MapObject } from './mapObject'

export type LegendShape = 'point' | 'line' | 'polygon'

export interface LegendSwatch {
  label: string
  color: string
  shape: LegendShape
}

/** Dégradé de valeurs, de `min` (première couleur) à `max` (dernière). */
export interface LegendGradient {
  label: string
  colors: readonly string[]
  min: number
  max: number
}

/** Couleurs selon la valeur d'un attribut, sous le nom de la couche. */
export interface LegendCategories {
  label: string
  shape: LegendShape
  categories: { label: string; color: string }[]
}

export type LegendItem = LegendSwatch | LegendGradient | LegendCategories

const SHAPES: Record<string, LegendShape> = {
  Point: 'point',
  MultiPoint: 'point',
  LineString: 'line',
  MultiLineString: 'line',
  Polygon: 'polygon',
  MultiPolygon: 'polygon',
}

/** Forme du symbole d'une couche, d'après sa première géométrie ; aucune si elle est vide. */
export function shapeOf(objects: MapObject[]): LegendShape | undefined {
  const type = objects[0]?.geometry.type
  return type ? (SHAPES[type] ?? 'point') : undefined
}
