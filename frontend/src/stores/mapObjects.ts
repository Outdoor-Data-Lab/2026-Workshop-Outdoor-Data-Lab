import { defineStore } from 'pinia'
import { computed, ref, shallowRef } from 'vue'
import type { FeatureCollection, Geometry } from 'geojson'

import type { LayerId, MapObject } from '@/types/mapObject'

import { useNotificationsStore } from './notifications'

export interface LayerStatus {
  loading: boolean
  error?: unknown
}

/** Propriétés envoyées à MapLibre (valeurs simples uniquement). */
export interface MapFeatureProperties {
  key: string
  label: string
}

/** Objets de la carte, rangés par couche. */
export const useMapObjectsStore = defineStore('mapObjects', () => {
  const notifications = useNotificationsStore()

  // shallowRef + remplacement : pas de réactivité profonde sur les géométries.
  const layers = shallowRef<Partial<Record<LayerId, MapObject[]>>>({})
  const status = ref<Partial<Record<LayerId, LayerStatus>>>({})
  const selectedKey = ref<string | null>(null)

  const byKey = computed(() => {
    const index = new Map<string, MapObject>()
    for (const objects of Object.values(layers.value)) {
      for (const object of objects ?? []) index.set(object.key, object)
    }
    return index
  })

  const selected = computed(() =>
    selectedKey.value ? (byKey.value.get(selectedKey.value) ?? null) : null,
  )

  const featureCollections = computed(() => {
    const collections: Partial<Record<LayerId, FeatureCollection<Geometry, MapFeatureProperties>>> =
      {}
    for (const [layer, objects] of Object.entries(layers.value) as [LayerId, MapObject[]][]) {
      collections[layer] = {
        type: 'FeatureCollection',
        features: objects.map((o) => ({
          type: 'Feature',
          geometry: o.geometry,
          properties: { key: o.key, label: o.label },
        })),
      }
    }
    return collections
  })

  function setLayer(layer: LayerId, objects: MapObject[]) {
    layers.value = { ...layers.value, [layer]: objects }
    if (selectedKey.value && !byKey.value.has(selectedKey.value)) selectedKey.value = null
  }

  function removeLayer(layer: LayerId) {
    const { [layer]: _removed, ...rest } = layers.value
    layers.value = rest
    delete status.value[layer]
    if (selectedKey.value && !byKey.value.has(selectedKey.value)) selectedKey.value = null
  }

  // Par couche, seul le dernier appel est pris en compte.
  const lastCall: Partial<Record<LayerId, number>> = {}

  /** En cas d'échec : erreur dans `status` et notification. `label` nomme la couche dans le message. */
  async function loadLayer(
    layer: LayerId,
    loader: () => Promise<MapObject[]>,
    { label = layer }: { label?: string } = {},
  ) {
    const call = (lastCall[layer] = (lastCall[layer] ?? 0) + 1)
    status.value[layer] = { loading: true }
    try {
      const objects = await loader()
      if (call !== lastCall[layer]) return
      setLayer(layer, objects)
      status.value[layer] = { loading: false }
    } catch (error) {
      if (call !== lastCall[layer]) return
      status.value[layer] = { loading: false, error }
      notifications.notifyError(error, `Impossible de charger ${label}`)
    }
  }

  function select(key: string | null) {
    selectedKey.value = key && byKey.value.has(key) ? key : null
  }

  return {
    layers,
    status,
    selectedKey,
    selected,
    featureCollections,
    setLayer,
    removeLayer,
    loadLayer,
    select,
  }
})
