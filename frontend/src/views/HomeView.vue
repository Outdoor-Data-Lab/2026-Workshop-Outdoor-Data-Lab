<script setup lang="ts">
import DetailPanel from '@/components/DetailPanel.vue'
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
  <main class="home">
    <aside class="panel left"></aside>
    <div class="map">
      <MapView />
      <LayerSwitcher class="layer-switcher" />
    </div>
    <aside class="panel right">
      <DetailPanel />
    </aside>
  </main>
</template>

<style scoped>
.home {
  flex: 1; /* hauteur restante sous la barre de navigation */
  min-height: 0;
  display: grid;
  grid-template-columns: var(--panel-width) 1fr var(--panel-width);
}

.panel {
  overflow-y: auto;
  padding: var(--space);
  background: var(--color-panel);
}

.left {
  border-right: 1px solid var(--color-border);
}

.right {
  border-left: 1px solid var(--color-border);
}

.map {
  position: relative;
  min-width: 0;
}

/* Sous les boutons de zoom de MapLibre, en haut à droite. */
.layer-switcher {
  position: absolute;
  top: 100px;
  right: 10px;
}
</style>
