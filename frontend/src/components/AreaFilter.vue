<script setup lang="ts">
/**
 * Choix d'une zone `ref_geo` par son nom ; elle filtre toutes les couches.
 * À l'ouverture : la zone par défaut de l'instance, si l'admin en a choisi une.
 */
import { onMounted, ref, watch } from 'vue'

import { getAreaGeometry, searchAreas, type AreaMatch } from '@/api/refGeo'
import { getInstanceSettings } from '@/api/settings'
import { referenceLabel } from '@/i18n'
import { useLayersStore } from '@/stores/layers'
import { useNotificationsStore } from '@/stores/notifications'

const layers = useLayersStore()
const notifications = useNotificationsStore()

const query = ref('')
const matches = ref<AreaMatch[] | null>(null)

let timer: ReturnType<typeof setTimeout> | undefined
let lastSearch = 0

watch(query, (value) => {
  clearTimeout(timer)
  const name = value.trim()
  if (name.length < 2) {
    matches.value = null
    return
  }
  timer = setTimeout(async () => {
    const search = ++lastSearch
    try {
      const found = await searchAreas(name)
      if (search === lastSearch) matches.value = found
    } catch (error) {
      notifications.notifyError(error)
    }
  }, 300)
})

function typeLabel(typeCode: string) {
  return referenceLabel('areaTypes', typeCode, typeCode)
}

onMounted(async () => {
  try {
    const { default_area } = await getInstanceSettings()
    // L'utilisateur a pu choisir une zone pendant le chargement.
    if (default_area && !layers.area) await choose(default_area)
  } catch (error) {
    notifications.notifyError(error)
  }
})

async function choose(area: AreaMatch) {
  try {
    const geometry = await getAreaGeometry(area.id_area)
    layers.setArea({ id: area.id_area, name: area.area_name, typeCode: area.type_code, geometry })
    query.value = ''
  } catch (error) {
    notifications.notifyError(error)
  }
}
</script>

<template>
  <section class="area-filter">
    <div v-if="layers.area" class="selected">
      <span>{{ layers.area.name }} ({{ typeLabel(layers.area.typeCode) }})</span>
      <button type="button" :aria-label="$t('areaFilter.clear')" @click="layers.setArea(null)">
        ×
      </button>
    </div>
    <template v-else>
      <label for="area-search">{{ $t('areaFilter.label') }}</label>
      <input
        id="area-search"
        v-model="query"
        type="search"
        autocomplete="off"
        :placeholder="$t('areaFilter.placeholder')"
      />
      <ul v-if="matches?.length">
        <li v-for="area in matches" :key="area.id_area">
          <button type="button" @click="choose(area)">
            {{ area.area_name }} ({{ typeLabel(area.type_code) }})
            <span class="type">{{ area.area_code }}</span>
          </button>
        </li>
      </ul>
      <p v-else-if="matches" class="empty">{{ $t('areaFilter.noResults') }}</p>
    </template>
  </section>
</template>

<style scoped>
.area-filter {
  display: flex;
  flex-direction: column;
  gap: calc(var(--space) / 3);
  width: 18rem;
  background: var(--color-background);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: calc(var(--space) / 1.5);
}

label {
  font-weight: bold;
}

input {
  padding: calc(var(--space) / 3);
  font: inherit;
}

ul {
  margin: 0;
  padding: 0;
  list-style: none;
  max-height: 16rem;
  overflow-y: auto;
}

li button {
  width: 100%;
  padding: calc(var(--space) / 3);
  border: 0;
  background: none;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

li button:hover,
li button:focus-visible {
  background: var(--color-panel);
}

.selected {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space);
}

.selected button {
  border: 0;
  background: none;
  color: inherit;
  font-size: 1.25rem;
  line-height: 1;
  cursor: pointer;
}

.type,
.empty {
  color: var(--color-muted);
  font-size: 0.85rem;
}

.empty {
  margin: 0;
}
</style>
