<script setup lang="ts">
import MapView from '@/components/MapView.vue'
import { COUNTING_OBJECT_LAYER, getCountingObjectsForMap } from '@/api/traffic'
import { useLayersStore } from '@/stores/layers'

const layers = useLayersStore()

// Les erreurs sont notifiées par le store.
layers.loadLayer(COUNTING_OBJECT_LAYER, () => getCountingObjectsForMap(), {
  label: 'les compteurs',
})
</script>

<template>
  <main>
    <MapView />
  </main>
</template>

<style scoped>
main {
  flex: 1; /* hauteur restante sous le header */
  min-height: 0;
  position: relative;
}
</style>
