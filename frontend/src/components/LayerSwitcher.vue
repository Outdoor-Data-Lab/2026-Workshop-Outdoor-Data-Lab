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
  <div class="layer-switcher">
    <fieldset v-for="[group, definitions] in groups" :key="group">
      <legend>{{ group }}</legend>
      <label v-for="definition in definitions" :key="definition.id">
        <input
          type="checkbox"
          :checked="layers.visible[definition.id] ?? false"
          @change="layers.setVisible(definition.id, ($event.target as HTMLInputElement).checked)"
        />
        {{ definition.label }}
        <span v-if="layers.status[definition.id]?.loading">(loading)</span>
        <span v-else-if="layers.status[definition.id]?.error" class="error">(failed)</span>
      </label>
    </fieldset>
  </div>
</template>

<style scoped>
.layer-switcher {
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 1px 4px rgb(0 0 0 / 0.3);
  padding: 0.5rem;
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
