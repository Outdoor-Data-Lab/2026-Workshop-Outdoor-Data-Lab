import { defineStore } from 'pinia'
import { computed, ref, shallowRef } from 'vue'
import type { FeatureCollection, Geometry } from 'geojson'

import { i18n } from '@/i18n'
import { CONCEPTS, type Concept } from '@/types/concept'
import { SEASON_MONTHS, type Season } from '@/types/season'
import { layerDomain, type LayerId, type MapObject } from '@/types/mapObject'

import { useNotificationsStore } from './notifications'

export interface LayerStatus {
  loading: boolean
  error?: unknown
}

/** Propriétés envoyées à MapLibre (valeurs simples uniquement). */
export interface MapFeatureProperties {
  key: string
  label: string
  color?: string
  value?: number
}

/** Filtres communs à toutes les couches, passés à leur `load`. */
export interface LayerFilters {
  /** Zone `ref_geo` : seuls les objets qui l'intersectent. */
  areaId?: number
  /** Mois de l'année d'une saison, toutes années confondues (mailles de fréquentation). */
  months?: number[]
}

/** Zone choisie pour filtrer les couches. */
export interface SelectedArea {
  id: number
  name: string
  typeCode: string
  geometry: Geometry
}

/** Couche proposée à l'utilisateur. `load` est appelé au premier affichage et à chaque changement de filtre. */
export interface LayerDefinition {
  id: LayerId
  label: string
  /** Clé `layerGroups.<group>` des traductions. */
  group: string
  /** Une seule couche `exclusive` visible à la fois dans son groupe. */
  exclusive?: boolean
  /** Affichée dès son ajout ; sinon l'utilisateur la coche. */
  visibleByDefault?: boolean
  /** Affichée au survol du nom. */
  description?: string
  /** Type d'un objet de la couche, au singulier, en tête de son détail ; sinon `label`. */
  itemLabel?: string
  /** Objets chargés en entier. Sans `load`, la couche est servie en `tiles`. */
  load?: (filters: LayerFilters) => Promise<MapObject[]>
  /** Tuiles vectorielles, dessinées par la carte à partir de `minzoom`. */
  tiles?: { url: (filters: LayerFilters) => string; minzoom: number }
}

/** Couches de la carte : définitions, visibilité et objets chargés. */
export const useLayersStore = defineStore('layers', () => {
  const notifications = useNotificationsStore()

  const concept = ref<Concept>('global')
  const definitions = shallowRef<LayerDefinition[]>([])
  const visible = ref<Partial<Record<LayerId, boolean>>>({})
  // shallowRef + remplacement : pas de réactivité profonde sur les géométries.
  const objectsByLayer = shallowRef<Partial<Record<LayerId, MapObject[]>>>({})
  const status = ref<Partial<Record<LayerId, LayerStatus>>>({})
  const selectedKey = ref<string | null>(null)
  const area = shallowRef<SelectedArea | null>(null)
  const season = ref<Season | null>(null)
  const filters = computed<LayerFilters>(() => ({
    areaId: area.value?.id,
    months: season.value ? SEASON_MONTHS[season.value] : undefined,
  }))

  const byKey = computed(() => {
    const index = new Map<string, MapObject>()
    for (const objects of Object.values(objectsByLayer.value)) {
      for (const object of objects ?? []) index.set(object.key, object)
    }
    return index
  })

  const selected = computed(() =>
    selectedKey.value ? (byKey.value.get(selectedKey.value) ?? null) : null,
  )

  // Une collection par tableau d'objets : une couche inchangée garde la sienne, et la carte ne la renvoie pas.
  const collectionOf = new WeakMap<MapObject[], FeatureCollection<Geometry, MapFeatureProperties>>()

  function toCollection(objects: MapObject[]) {
    let collection = collectionOf.get(objects)
    if (!collection) {
      collection = {
        type: 'FeatureCollection',
        features: objects.map((o) => ({
          type: 'Feature',
          geometry: o.geometry,
          properties: {
            key: o.key,
            label: o.label,
            color: o.color,
            ...(o.value !== undefined && { value: o.value }),
          },
        })),
      }
      collectionOf.set(objects, collection)
    }
    return collection
  }

  const featureCollections = computed(() => {
    const collections: Partial<Record<LayerId, FeatureCollection<Geometry, MapFeatureProperties>>> =
      {}
    for (const [layer, objects] of Object.entries(objectsByLayer.value) as [
      LayerId,
      MapObject[],
    ][]) {
      if (visible.value[layer]) collections[layer] = toCollection(objects)
    }
    return collections
  })

  function setLayer(layer: LayerId, objects: MapObject[]) {
    objectsByLayer.value = { ...objectsByLayer.value, [layer]: objects }
    if (selectedKey.value && !byKey.value.has(selectedKey.value)) selectedKey.value = null
  }

  function removeLayer(layer: LayerId) {
    const { [layer]: _removed, ...rest } = objectsByLayer.value
    objectsByLayer.value = rest
    delete status.value[layer]
    if (selectedKey.value && !byKey.value.has(selectedKey.value)) selectedKey.value = null
  }

  // Par couche, seul le dernier appel est pris en compte.
  const lastCall: Partial<Record<LayerId, number>> = {}

  /** En cas d'échec : erreur dans `status` et notification. `label` nomme la couche dans le message. */
  async function loadLayer(
    layer: LayerId,
    loader: (filters: LayerFilters) => Promise<MapObject[]>,
    { label = layer }: { label?: string } = {},
  ) {
    const call = (lastCall[layer] = (lastCall[layer] ?? 0) + 1)
    status.value[layer] = { loading: true }
    try {
      const objects = await loader(filters.value)
      if (call !== lastCall[layer]) return
      setLayer(layer, objects)
      status.value[layer] = { loading: false }
    } catch (error) {
      if (call !== lastCall[layer]) return
      status.value[layer] = { loading: false, error }
      notifications.notifyError(error, i18n.global.t('layers.loadError', { label }))
    }
  }

  function inConcept(layer: LayerId) {
    return CONCEPTS.find((c) => c.id === concept.value)!.domains.includes(layerDomain(layer))
  }

  /** Les couches ajoutées sont décochées, sauf `visibleByDefault` : l'utilisateur choisit celles à afficher. */
  function addDefinitions(added: LayerDefinition[]) {
    definitions.value = [...definitions.value, ...added]
    for (const definition of added) setVisible(definition.id, definition.visibleByDefault ?? false)
  }

  /** Change de concept et réinitialise la visibilité des couches, sauf des externes. */
  function setConcept(value: Concept) {
    concept.value = value
    for (const definition of definitions.value) {
      if (layerDomain(definition.id) !== 'external') {
        setVisible(definition.id, inConcept(definition.id))
      }
    }
  }

  /** Affiche ou masque une couche ; la charge au premier affichage, ou après un échec. */
  function setVisible(layer: LayerId, on: boolean) {
    visible.value[layer] = on
    const definition = definitions.value.find((d) => d.id === layer)
    if (on && definition?.exclusive) {
      for (const other of definitions.value) {
        if (other.exclusive && other.group === definition.group && other.id !== layer) {
          visible.value[other.id] = false
        }
      }
    }
    if (
      on &&
      definition?.load &&
      !(layer in objectsByLayer.value) &&
      !status.value[layer]?.loading
    ) {
      loadLayer(layer, definition.load, { label: definition.label })
    }
  }

  /** Change de zone : les objets chargés sont oubliés, les couches visibles rechargées, les autres le seront à leur affichage. */
  function setArea(value: SelectedArea | null) {
    area.value = value
    reloadLayers()
  }

  /** Change de saison : rechargement comme pour la zone. */
  function setSeason(value: Season | null) {
    season.value = value
    reloadLayers()
  }

  /** Après un changement de filtre : les objets chargés sont oubliés, les couches visibles rechargées, les autres le seront à leur affichage. */
  function reloadLayers() {
    objectsByLayer.value = {}
    status.value = {}
    selectedKey.value = null
    for (const definition of definitions.value) {
      if (!definition.load) continue // tuiles : la carte suit les filtres
      if (visible.value[definition.id]) {
        loadLayer(definition.id, definition.load, { label: definition.label })
      } else {
        // Un chargement en cours avec les anciens filtres sera ignoré.
        lastCall[definition.id] = (lastCall[definition.id] ?? 0) + 1
      }
    }
  }

  function select(key: string | null) {
    selectedKey.value = key && byKey.value.has(key) ? key : null
  }

  return {
    concept,
    definitions,
    visible,
    objectsByLayer,
    status,
    selectedKey,
    selected,
    area,
    season,
    filters,
    featureCollections,
    setLayer,
    removeLayer,
    loadLayer,
    addDefinitions,
    setConcept,
    setVisible,
    setArea,
    setSeason,
    select,
  }
})
