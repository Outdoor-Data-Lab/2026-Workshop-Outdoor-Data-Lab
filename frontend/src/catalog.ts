/** Couches proposées, construites depuis les tables de référence de l'API. */
import { getExternalLayers, getFeatures } from '@/api/externalLayers'
import { getCountingObjectTypes, getCountingObjectsForMap } from '@/api/traffic'
import { referenceLabel } from '@/i18n'
import type { LayerDefinition } from '@/stores/layers'
import { mapObjectKey, type LayerId, type MapObject } from '@/types/mapObject'

/** Une couche par type de compteur. */
export async function trafficLayers(): Promise<LayerDefinition[]> {
  const { results } = await getCountingObjectTypes()
  return results.map((type) => {
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
}

/** Une couche par couche externe déclarée dans l'admin, colorée selon un attribut si demandé. */
export async function externalLayers(): Promise<LayerDefinition[]> {
  const { results } = await getExternalLayers()
  return results.map((layer) => {
    const id: LayerId = `external/${layer.id}`
    return {
      id,
      label: layer.label,
      group: 'external',
      description: layer.description,
      load: async () =>
        (await getFeatures(layer.url)).map((feature, i): MapObject => {
          const properties = feature.properties ?? {}
          return {
            key: mapObjectKey(id, i),
            id: feature.id ?? i,
            domain: 'external',
            layer: id,
            label: layer.label,
            geometry: feature.geometry,
            color:
              (layer.color_property && layer.colors[String(properties[layer.color_property])]) ||
              layer.color,
            // Sans attribut choisi : tous.
            attributes: layer.properties.length
              ? Object.fromEntries(layer.properties.map((name) => [name, properties[name]]))
              : properties,
          }
        }),
    }
  })
}
