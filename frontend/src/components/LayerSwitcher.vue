<script setup lang="ts">
/** Liste des couches, par groupe, à cocher ; repliable. */
import { computed, ref } from 'vue'

import LoadingSpinner from '@/components/LoadingSpinner.vue'
import { useLayersStore, type LayerDefinition } from '@/stores/layers'

const layers = useLayersStore()
const open = ref(true)

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
    <button type="button" class="toggle" :aria-expanded="open" @click="open = !open">
      {{ $t('layers.title') }} <span aria-hidden="true">{{ open ? '▴' : '▾' }}</span>
    </button>
    <fieldset v-for="[group, definitions] in groups" v-show="open" :key="group">
      <legend>{{ $t(`layerGroups.${group}`) }}</legend>
      <label v-for="definition in definitions" :key="definition.id" :title="definition.description">
        <input
          type="checkbox"
          :checked="layers.visible[definition.id] ?? false"
          @change="layers.setVisible(definition.id, ($event.target as HTMLInputElement).checked)"
        />
        {{ definition.label }}
        <LoadingSpinner v-if="layers.status[definition.id]?.loading" />
        <span v-else-if="layers.status[definition.id]?.error" class="error">{{
          $t('layers.failed')
        }}</span>
      </label>
    </fieldset>
  </div>
</template>

<style scoped>
.layer-switcher {
  display: flex;
  flex-direction: column;
  gap: calc(var(--space) / 3);
  background: var(--color-background);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: calc(var(--space) / 1.5);
}

.toggle {
  padding: 0;
  border: 0;
  background: none;
  color: inherit;
  font: inherit;
  font-weight: bold;
  text-align: left;
  cursor: pointer;
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
