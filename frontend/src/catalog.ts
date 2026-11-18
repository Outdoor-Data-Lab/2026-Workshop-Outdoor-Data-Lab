/** Couches proposées, construites depuis les tables de référence de l'API. */
import { getCountingObjectTypes, getCountingObjectsForMap } from '@/api/traffic'
import type { LayerDefinition } from '@/stores/layers'
import { mapObjectKey, type LayerId } from '@/types/mapObject'

/** Une couche par type de compteur. */
export async function trafficLayers(): Promise<LayerDefinition[]> {
  const { results } = await getCountingObjectTypes()
  return results.map((type) => {
    const id: LayerId = `traffic/${type.code}`
    return {
      id,
      label: type.label,
      group: 'Traffic',
      // L'adaptateur range tous les compteurs dans une même couche : on les rattache à celle du type.
      load: async () =>
        (await getCountingObjectsForMap({ typeCode: type.code })).map((o) => ({
          ...o,
          layer: id,
          key: mapObjectKey(id, o.id),
        })),
    }
  })
}
