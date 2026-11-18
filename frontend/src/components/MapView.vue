<script setup lang="ts">
import { onMounted, onUnmounted, useTemplateRef, shallowRef, watch } from 'vue'
import { Map as MlMap, NavigationControl, type GeoJSONSource } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { FeatureCollection } from 'geojson'

const props = defineProps<{
  data?: FeatureCollection
  center?: [number, number]
  zoom?: number
}>()

const emit = defineEmits<{ featureClick: [props: Record<string, unknown>] }>()

const container = useTemplateRef<HTMLDivElement>('container')
const map = shallowRef<MlMap | null>(null)

onMounted(() => {
  const m = new MlMap({
    container: container.value!,
    style: 'https://tiles.openfreemap.org/styles/liberty',
    center: props.center ?? [6.08, 45.2],
    zoom: props.zoom ?? 9,
  })
  m.addControl(new NavigationControl(), 'top-right')

  m.on('load', () => {
    m.addSource('points', {
      type: 'geojson',
      data: props.data ?? { type: 'FeatureCollection', features: [] },
    })
    m.addLayer({
      id: 'points',
      type: 'circle',
      source: 'points',
      paint: { 'circle-radius': 6, 'circle-color': '#e4572e' },
    })
    m.on('click', 'points', (e) => {
      const feature = e.features?.[0]
      if (feature) emit('featureClick', feature.properties)
    })
    map.value = m
  })
})

watch(
  () => props.data,
  (data) => {
    const src = map.value?.getSource('points') as GeoJSONSource | undefined
    if (data && src) src.setData(data)
  },
)

onUnmounted(() => map.value?.remove())
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
