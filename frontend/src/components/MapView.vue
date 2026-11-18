<script setup lang="ts">
/** Carte MapLibre pilotée par le store layers. */
import { onMounted, onUnmounted, shallowRef, useTemplateRef, watch } from 'vue'
import {
  Map as MlMap,
  NavigationControl,
  type ExpressionSpecification,
  type GeoJSONSource,
  type LayerSpecification,
  type PointLike,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

import { useLayersStore } from '@/stores/layers'
import { DOMAIN_COLORS, layerDomain, type LayerId } from '@/types/mapObject'

const props = defineProps<{
  center?: [number, number]
  zoom?: number
}>()

const store = useLayersStore()

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
    fill: { 'fill-opacity': whenSelected(0.6, 0.3) },
    outline: { 'line-width': whenSelected(3, 1.5) },
    line: { 'line-width': whenSelected(6, 3) },
    point: {
      'circle-radius': whenSelected(9, 6),
      'circle-stroke-width': whenSelected(3, 1),
    },
  }
}

function layerSpecs(source: LayerId): LayerSpecification[] {
  const color: ExpressionSpecification = [
    'coalesce',
    ['get', 'color'],
    DOMAIN_COLORS[layerDomain(source)],
  ]
  const sel = selectionPaint()
  const isPolygon: ExpressionSpecification = ['==', ['geometry-type'], 'Polygon']
  // Points en dernier, au-dessus du reste.
  return [
    {
      id: `${source}/fill`,
      type: 'fill',
      source,
      filter: isPolygon,
      paint: { 'fill-color': color, ...sel.fill },
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
  }
  for (const source of rendered.keys()) {
    if (!(source in collections)) removeSource(m, source)
  }
}

function featureAt(m: MlMap, point: PointLike) {
  const layers = [...rendered.values()].flat()
  if (layers.length === 0) return undefined
  return m.queryRenderedFeatures(point, { layers })[0]
}

onMounted(() => {
  const m = new MlMap({
    container: container.value!,
    style: 'https://tiles.openfreemap.org/styles/liberty',
    center: props.center ?? [6.08, 45.2],
    zoom: props.zoom ?? 9,
  })
  m.addControl(new NavigationControl(), 'top-right')

  // Clic dans le vide = désélection.
  m.on('click', (e) => {
    const key = featureAt(m, e.point)?.properties?.key
    store.select(typeof key === 'string' ? key : null)
  })
  m.on('mousemove', (e) => {
    m.getCanvas().style.cursor = featureAt(m, e.point) ? 'pointer' : ''
  })

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
