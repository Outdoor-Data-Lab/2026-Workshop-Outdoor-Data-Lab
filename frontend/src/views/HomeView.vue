<script setup lang="ts">
import LayerSwitcher from '@/components/LayerSwitcher.vue'
import MapView from '@/components/MapView.vue'
import { trafficLayers } from '@/catalog'
import { useLayersStore } from '@/stores/layers'

const layers = useLayersStore()

// Un échec est notifié par le gestionnaire global des promesses rejetées (main.ts).
trafficLayers().then((definitions) => {
  layers.addDefinitions(definitions)
  for (const definition of definitions) layers.setVisible(definition.id, true)
})
</script>

<template>
  <main>
    <MapView />
    <LayerSwitcher class="layer-switcher" />
  </main>
</template>

<style scoped>
main {
  flex: 1; /* hauteur restante sous le header */
  min-height: 0;
  position: relative;
}

.layer-switcher {
  position: absolute;
  top: 10px;
  left: 10px;
}
</style>
