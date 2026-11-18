/** Couches proposées, construites depuis les tables de référence de l'API. */
import {
  TRAFFIC_AREA_LAYER,
  getCountingObjectTypes,
  getCountingObjectsForMap,
  getTrafficAreasForMap,
} from '@/api/traffic'
import { i18n, referenceLabel } from '@/i18n'
import type { LayerDefinition } from '@/stores/layers'
import { mapObjectKey, type LayerId } from '@/types/mapObject'

/** Une couche par type de compteur, puis la fréquentation par maille. */
export async function trafficLayers(): Promise<LayerDefinition[]> {
  const { results } = await getCountingObjectTypes()
  const byType = results.map((type): LayerDefinition => {
    const id: LayerId = `traffic/${type.code}`
    return {
      id,
      label: referenceLabel('countingObjectTypes', type.code, type.label),
      group: 'traffic',
      // L'adaptateur range tous les compteurs dans une même couche : on les rattache à celle du type.
      load: async () =>
        (await getCountingObjectsForMap({ typeCode: type.code })).map((o) => ({
          ...o,
          layer: id,
          key: mapObjectKey(id, o.id),
        })),
    }
  })
  return [
    ...byType,
    {
      id: TRAFFIC_AREA_LAYER,
      label: i18n.global.t('layers.trafficAreas'),
      group: 'traffic',
      load: () => getTrafficAreasForMap(),
    },
  ]
}
