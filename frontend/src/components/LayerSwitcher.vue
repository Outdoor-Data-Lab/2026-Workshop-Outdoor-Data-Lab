<script setup lang="ts">
/** Liste des couches, par groupe, à cocher. */
import { computed } from 'vue'

import { useLayersStore, type LayerDefinition } from '@/stores/layers'

const layers = useLayersStore()

const groups = computed(() => {
  const byGroup = new Map<string, LayerDefinition[]>()
  for (const definition of layers.definitions) {
    byGroup.set(definition.group, [...(byGroup.get(definition.group) ?? []), definition])
  }
  return byGroup
})
</script>

<template>
  <div v-if="layers.definitions.length" class="layer-switcher">
    <fieldset v-for="[group, definitions] in groups" :key="group">
      <legend>{{ $t(`layerGroups.${group}`) }}</legend>
      <label v-for="definition in definitions" :key="definition.id" :title="definition.description">
        <input
          type="checkbox"
          :checked="layers.visible[definition.id] ?? false"
          @change="layers.setVisible(definition.id, ($event.target as HTMLInputElement).checked)"
        />
        {{ definition.label }}
        <span v-if="layers.status[definition.id]?.loading">{{ $t('layers.loading') }}</span>
        <span v-else-if="layers.status[definition.id]?.error" class="error">{{
          $t('layers.failed')
        }}</span>
      </label>
    </fieldset>
  </div>
</template>

<style scoped>
.layer-switcher {
  background: var(--color-background);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: calc(var(--space) / 1.5);
}

fieldset {
  border: none;
  margin: 0;
  padding: 0;
}

legend {
  font-weight: bold;
}

label {
  display: block;
}

.error {
  color: #c00;
}
</style>
