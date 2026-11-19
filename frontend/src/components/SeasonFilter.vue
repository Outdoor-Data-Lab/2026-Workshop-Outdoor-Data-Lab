<script setup lang="ts">
/** Choix d'une saison météorologique, toutes années confondues ; filtre les mailles de fréquentation. */
import { useLayersStore } from '@/stores/layers'
import { SEASON_MONTHS, type Season } from '@/types/season'

const layers = useLayersStore()
const seasons = Object.keys(SEASON_MONTHS) as Season[]

function choose(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  layers.setSeason(value ? (value as Season) : null)
}
</script>

<template>
  <section class="season-filter">
    <label for="season">{{ $t('season.label') }}</label>
    <select id="season" :value="layers.season ?? ''" @change="choose">
      <option value="">{{ $t('season.all') }}</option>
      <option v-for="season in seasons" :key="season" :value="season">
        {{ $t(`season.${season}`) }}
      </option>
    </select>
  </section>
</template>

<style scoped>
.season-filter {
  display: flex;
  align-items: center;
  gap: calc(var(--space) / 1.5);
  background: var(--color-background);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: calc(var(--space) / 1.5);
}

label {
  font-weight: bold;
}

select {
  flex: 1;
  padding: calc(var(--space) / 3);
  font: inherit;
}
</style>
