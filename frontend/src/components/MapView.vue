<script setup lang="ts">
/** Carte MapLibre pilotée par le store layers. */
import { computed, onMounted, onUnmounted, shallowRef, useTemplateRef, watch } from 'vue'
import {
  LngLatBounds,
  Map as MlMap,
  NavigationControl,
  ScaleControl,
  type ExpressionSpecification,
  type GeoJSONSource,
  type LayerSpecification,
  type PointLike,
  setWorkerUrl,
  type StyleSpecification,
  type VectorTileSource,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'

import { useLayersStore, type MapFeatureProperties, type SelectedArea } from '@/stores/layers'
import { DOMAIN_COLORS, VALUE_COLORS, layerDomain, valueMax, type LayerId } from '@/types/mapObject'
import type { FeatureCollection, Geometry } from 'geojson'

const props = defineProps<{
  center?: [number, number]
  zoom?: number
}>()

setWorkerUrl(workerUrl)

const store = useLayersStore()

/** Fond de carte : Plan IGN v2 (Géoplateforme, WMTS). */
const BASEMAP: StyleSpecification = {
  version: 8,
  sources: {
    'plan-ign': {
      type: 'raster',
      tiles: [
        'https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2&STYLE=normal&FORMAT=image/png&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}',
      ],
      tileSize: 256,
      maxzoom: 19,
      attribution: '© <a href="https://www.ign.fr/">IGN</a>',
    },
  },
  layers: [{ id: 'plan-ign', type: 'raster', source: 'plan-ign' }],
}

const container = useTemplateRef<HTMLDivElement>('container')
const map = shallowRef<MlMap | null>(null)

/** Couches MapLibre créées, et dernière collection envoyée, par couche du store. */
const rendered = new Map<LayerId, string[]>()
const sent = new Map<LayerId, object>()

/** `on` si l'objet est sélectionné, sinon `off`. */
function whenSelected<T>(on: T, off: T): ExpressionSpecification {
  return [
    'case',
    ['==', ['get', 'key'], store.selectedKey ?? ''],
    on,
    off,
  ] as ExpressionSpecification
}

/** Styles dépendant de la sélection, par suffixe de couche. */
function selectionPaint(): Record<string, Record<string, ExpressionSpecification>> {
  return {
    fill: {
      'fill-opacity': whenSelected<number | ExpressionSpecification>(0.85, [
        'case',
        ['has', 'value'],
        0.7,
        0.3,
      ]),
    },
    // Pas de contour sur les mailles colorées, sauf sélectionnées.
    outline: {
      'line-width': whenSelected<number | ExpressionSpecification>(3, [
        'case',
        ['has', 'value'],
        0,
        1.5,
      ]),
    },
    line: { 'line-width': whenSelected(6, 3) },
    point: {
      'circle-radius': whenSelected(9, 6),
      'circle-stroke-width': whenSelected(3, 1),
    },
  }
}

/** Couleur de l'objet, sinon celle du domaine. */
function baseColor(source: LayerId): ExpressionSpecification {
  return ['coalesce', ['get', 'color'], DOMAIN_COLORS[layerDomain(source)]]
}

/** Remplissage : dégradé de 0 au maximum de la couche si l'objet a une `value`, sinon `baseColor`. */
function fillColor(
  source: LayerId,
  collection?: FeatureCollection<Geometry, MapFeatureProperties>,
): ExpressionSpecification {
  const max = valueMax((collection?.features ?? []).map((f) => f.properties.value))
  // Couleurs réparties à intervalles réguliers entre 0 et max.
  const stops = VALUE_COLORS.flatMap((color, i) => [(i / (VALUE_COLORS.length - 1)) * max, color])
  return [
    'case',
    ['has', 'value'],
    ['interpolate', ['linear'], ['get', 'value'], ...stops],
    baseColor(source),
  ] as ExpressionSpecification
}

function layerSpecs(source: LayerId): LayerSpecification[] {
  const color = baseColor(source)
  const sel = selectionPaint()
  const isPolygon: ExpressionSpecification = ['==', ['geometry-type'], 'Polygon']
  // Points en dernier, au-dessus du reste.
  return [
    {
      id: `${source}/fill`,
      type: 'fill',
      source,
      filter: isPolygon,
      // Sans antialiasing : les bords lissés des mailles voisines se superposaient en traits sombres.
      paint: { 'fill-color': fillColor(source), 'fill-antialias': false, ...sel.fill },
    },
    {
      id: `${source}/outline`,
      type: 'line',
      source,
      filter: isPolygon,
      paint: { 'line-color': color, ...sel.outline },
    },
    {
      id: `${source}/line`,
      type: 'line',
      source,
      filter: ['==', ['geometry-type'], 'LineString'],
      paint: { 'line-color': color, ...sel.line },
    },
    {
      id: `${source}/point`,
      type: 'circle',
      source,
      filter: ['==', ['geometry-type'], 'Point'],
      paint: { 'circle-color': color, 'circle-stroke-color': '#fff', ...sel.point },
    },
  ]
}

function addSource(m: MlMap, source: LayerId) {
  m.addSource(source, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
  const specs = layerSpecs(source)
  for (const spec of specs) m.addLayer(spec)
  // Le contour de la zone reste au-dessus des couches.
  if (m.getLayer(AREA_SOURCE)) m.moveLayer(AREA_SOURCE)
  rendered.set(
    source,
    specs.map((s) => s.id),
  )
}

function removeSource(m: MlMap, source: LayerId) {
  for (const id of rendered.get(source) ?? []) m.removeLayer(id)
  m.removeSource(source)
  rendered.delete(source)
  sent.delete(source)
}

/** Aligne les sources de la carte sur le store. */
function sync(m: MlMap, collections: typeof store.featureCollections) {
  for (const [source, collection] of Object.entries(collections) as [
    LayerId,
    NonNullable<(typeof collections)[LayerId]>,
  ][]) {
    if (!rendered.has(source)) addSource(m, source)
    if (sent.get(source) === collection) continue
    ;(m.getSource(source) as GeoJSONSource).setData(collection)
    sent.set(source, collection)
    // Le maximum dépend des données : on recale le dégradé à chaque mise à jour.
    m.setPaintProperty(`${source}/fill`, 'fill-color', fillColor(source, collection))
  }
  for (const source of rendered.keys()) {
    if (!(source in collections)) removeSource(m, source)
  }
}

const AREA_SOURCE = 'selected-area'

function bounds(geometry: Geometry): LngLatBounds {
  const box = new LngLatBounds()
  const visit = (coordinates: unknown): void => {
    if (typeof (coordinates as unknown[])[0] === 'number')
      box.extend(coordinates as [number, number])
    else for (const c of coordinates as unknown[]) visit(c)
  }
  if (geometry.type === 'GeometryCollection')
    geometry.geometries.forEach((g) => box.extend(bounds(g)))
  else visit(geometry.coordinates)
  return box
}

/** Contour de la zone qui filtre les couches, et recadrage sur elle. */
function showArea(m: MlMap, area: SelectedArea | null) {
  const data: FeatureCollection = {
    type: 'FeatureCollection',
    features: area ? [{ type: 'Feature', geometry: area.geometry, properties: {} }] : [],
  }
  const source = m.getSource(AREA_SOURCE) as GeoJSONSource | undefined
  if (source) {
    source.setData(data)
  } else {
    m.addSource(AREA_SOURCE, { type: 'geojson', data })
    m.addLayer({
      id: AREA_SOURCE,
      type: 'line',
      source: AREA_SOURCE,
      paint: { 'line-color': '#1f2933', 'line-width': 2.5, 'line-dasharray': [3, 2] },
    })
  }
  if (area) m.fitBounds(bounds(area.geometry), { padding: 40 })
}

function featureAt(m: MlMap, point: PointLike) {
  const layers = [...rendered.values()].flat()
  if (layers.length === 0) return undefined
  return m.queryRenderedFeatures(point, { layers })[0]
}

onMounted(() => {
  const m = new MlMap({
    container: container.value!,
    style: BASEMAP,
    center: props.center ?? [6.08, 45.2],
    zoom: props.zoom ?? 9,
  })
  m.addControl(new NavigationControl(), 'bottom-right')
  // Sous la légende (MapLegend), en bas à gauche.
  m.addControl(new ScaleControl({ unit: 'metric' }), 'bottom-left')

  // Clic dans le vide = désélection.
  m.on('click', (e) => {
    const key = featureAt(m, e.point)?.properties?.key
    store.select(typeof key === 'string' ? key : null)
  })
  m.on('mousemove', (e) => {
    m.getCanvas().style.cursor = featureAt(m, e.point) ? 'pointer' : ''
  })

  // Couches en tuiles : roue tant que des tuiles demandées ne sont pas arrivées.
  const tilesStatus = () => {
    for (const source of tiled.keys()) {
      const loading = !m.isSourceLoaded(source)
      if (store.status[source]?.loading !== loading) store.status[source] = { loading }
    }
  }
  m.on('render', tilesStatus)
  m.on('idle', tilesStatus)

  m.on('load', () => {
    map.value = m
  })
})

watch(
  [map, () => store.featureCollections],
  ([m, collections]) => {
    if (m) sync(m, collections)
  },
  { immediate: true },
)

/** Couche des tuiles vectorielles de compteurs (backend : traffic/api/tiles.py). */
const TILE_SOURCE_LAYER = 'counting_objects'

/** URL des couches en tuiles visibles, d'après les filtres. */
const tileUrls = computed(() => {
  const urls = new Map<LayerId, { url: string; minzoom: number }>()
  for (const d of store.definitions) {
    if (d.tiles && store.visible[d.id]) {
      urls.set(d.id, { url: d.tiles.url(store.filters), minzoom: d.tiles.minzoom })
    }
  }
  return urls
})

/** URL envoyée, par couche en tuiles affichée. */
const tiled = new Map<LayerId, string>()

/** Aligne les sources de tuiles sur les couches visibles ; un filtre changé change l'URL. */
function syncTiles(m: MlMap, urls: typeof tileUrls.value) {
  for (const [source, { url, minzoom }] of urls) {
    if (!tiled.has(source)) {
      // maxzoom 14 : au-delà, la carte agrandit les tuiles du zoom 14.
      m.addSource(source, { type: 'vector', tiles: [url], minzoom, maxzoom: 14 })
      m.addLayer({
        id: `${source}/tiles`,
        type: 'line',
        source,
        'source-layer': TILE_SOURCE_LAYER,
        minzoom,
        paint: {
          'line-color': DOMAIN_COLORS[layerDomain(source)],
          'line-width': 1.5,
          'line-opacity': 0.5,
        },
      })
      if (m.getLayer(AREA_SOURCE)) m.moveLayer(AREA_SOURCE)
    } else if (tiled.get(source) !== url) {
      ;(m.getSource(source) as VectorTileSource).setTiles([url])
    }
    tiled.set(source, url)
  }
  for (const source of [...tiled.keys()]) {
    if (urls.has(source)) continue
    m.removeLayer(`${source}/tiles`)
    m.removeSource(source)
    tiled.delete(source)
    delete store.status[source]
  }
}

watch([map, tileUrls], ([m, urls]) => {
  if (m) syncTiles(m, urls)
})

watch([map, () => store.area], ([m, area]) => {
  if (m) showArea(m, area)
})

watch(
  () => store.selectedKey,
  () => {
    const m = map.value
    if (!m) return
    const sel = selectionPaint()
    for (const ids of rendered.values()) {
      for (const id of ids) {
        const suffix = id.slice(id.lastIndexOf('/') + 1)
        for (const [prop, value] of Object.entries(sel[suffix] ?? {})) {
          m.setPaintProperty(id, prop as Parameters<MlMap['setPaintProperty']>[1], value)
        }
      }
    }
  },
)

onUnmounted(() => {
  map.value?.remove()
  rendered.clear()
  sent.clear()
  tiled.clear()
})
</script>

<template>
  <div ref="container" class="map"></div>
</template>

<style scoped>
.map {
  width: 100%;
  height: 100%;
}
</style>
