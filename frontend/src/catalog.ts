/** Couches proposées, construites depuis les tables de référence de l'API. */
import { BIODIV_AREA_LAYER, getBiodivAreasForMap } from '@/api/biodiv'
import { getExternalLayers, getFeatures } from '@/api/externalLayers'
import { OFFER_LAYER, getOffersForMap } from '@/api/outdoor'
import {
  TILE_MIN_ZOOM,
  SYNTHESIS_AREA_LAYER,
  SYNTHESIS_COLOR,
  TRAFFIC_AREA_LAYER,
  countingObjectTileUrl,
  getCountingObjectTypes,
  getCountingObjectsForMap,
  getSynthesisAreasForMap,
  getTrafficAreasForMap,
} from '@/api/traffic'
import { gridSize, getInstanceSettings } from '@/api/settings'
import { i18n, referenceLabel } from '@/i18n'
import type { LayerDefinition } from '@/stores/layers'
import { shapeOf, type LegendItem } from '@/types/legend'
import {
  DOMAIN_COLORS,
  VALUE_COLORS,
  mapObjectKey,
  valueMax,
  type LayerId,
  type MapObject,
} from '@/types/mapObject'

/** Types trop nombreux pour être chargés en entier (traces Outdoorvision) : servis en tuiles. */
const TILED_TYPES = ['segment']

/** Légende d'une couche d'une seule couleur, dans la forme de ses géométries. */
function swatch(label: string, color: string) {
  return (objects: MapObject[]): LegendItem[] => {
    const shape = shapeOf(objects)
    return shape ? [{ label, color, shape }] : []
  }
}

/** Type d'objet des mailles, avec leur taille : « Maille de 500 m ». */
async function cellItemLabel() {
  const size = gridSize((await getInstanceSettings()).grid_area_type)
  return size ? i18n.global.t('items.cellOfSize', { size }) : i18n.global.t('items.cell')
}

/** Une couche par type de compteur, puis la fréquentation par maille. */
export async function trafficLayers(): Promise<LayerDefinition[]> {
  const [{ results }, cell] = await Promise.all([getCountingObjectTypes(), cellItemLabel()])
  const byType = results.map((type): LayerDefinition => {
    const id: LayerId = `traffic/${type.code}`
    const label = referenceLabel('countingObjectTypes', type.code, type.label)
    if (TILED_TYPES.includes(type.code)) {
      return {
        id,
        label,
        group: 'traffic',
        description: i18n.global.t('layers.fromZoom', { zoom: TILE_MIN_ZOOM }),
        tiles: {
          url: ({ areaId }) => countingObjectTileUrl({ typeCode: type.code, areaId }),
          minzoom: TILE_MIN_ZOOM,
        },
        legend: () => [{ label, color: DOMAIN_COLORS.traffic, shape: 'line' }],
      }
    }
    return {
      id,
      label,
      group: 'traffic',
      itemLabel: i18n.global.t('items.counter'),
      legend: () => [{ label, color: DOMAIN_COLORS.traffic, shape: 'point' }],
      // L'adaptateur range tous les compteurs dans une même couche : on les rattache à celle du type.
      load: async ({ areaId }) =>
        (await getCountingObjectsForMap({ typeCode: type.code, areaId })).map((o) => ({
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
      group: 'grid',
      exclusive: true,
      visibleByDefault: true,
      itemLabel: cell,
      load: ({ areaId, months }) => getTrafficAreasForMap({ areaId, months }),
      legend: (objects) => [
        {
          label: i18n.global.t('legend.trafficAreas'),
          colors: VALUE_COLORS,
          min: 0,
          max: valueMax(objects.map((o) => o.value)),
        },
      ],
    },
  ]
}

/** Croisement fréquentation × biodiversité : les zones à enjeu. */
export async function synthesisLayers(): Promise<LayerDefinition[]> {
  return [
    {
      id: SYNTHESIS_AREA_LAYER,
      label: i18n.global.t('layers.synthesisAreas'),
      group: 'grid',
      exclusive: true,
      description: i18n.global.t('layers.synthesisDescription'),
      itemLabel: await cellItemLabel(),
      load: ({ areaId, months }) => getSynthesisAreasForMap({ areaId, months }),
      legend: swatch(i18n.global.t('legend.synthesisAreas'), SYNTHESIS_COLOR),
    },
  ]
}

/** Mailles ayant des taxons protégés ou menacés. */
export async function biodiversityLayers(): Promise<LayerDefinition[]> {
  const label = i18n.global.t('layers.biodivAreas')
  return [
    {
      id: BIODIV_AREA_LAYER,
      label,
      group: 'grid',
      exclusive: true,
      itemLabel: await cellItemLabel(),
      load: () => getBiodivAreasForMap(),
      legend: swatch(label, DOMAIN_COLORS.biodiversity),
    },
  ]
}

/** Offres d'activités outdoor. */
export async function outdoorLayers(): Promise<LayerDefinition[]> {
  const label = i18n.global.t('layers.outdoorOffers')
  return [
    {
      id: OFFER_LAYER,
      label,
      group: 'outdoor',
      itemLabel: i18n.global.t('items.offer'),
      load: ({ areaId }) => getOffersForMap({ areaId }),
      legend: swatch(label, DOMAIN_COLORS.outdoor),
    },
  ]
}

/**
 * Une couche par couche externe déclarée dans l'admin, colorée selon un attribut si demandé.
 * Servies par d'autres sites : pas filtrées par zone.
 */
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
            // Le nom de l'objet si l'admin a choisi l'attribut qui le porte, sinon celui de la couche.
            label:
              (layer.label_property && String(properties[layer.label_property] ?? '')) ||
              layer.label,
            geometry: feature.geometry,
            color:
              (layer.color_property && layer.colors[String(properties[layer.color_property])]) ||
              layer.color,
            // Sans attribut choisi : tous ; sauf celui du nom, déjà en titre.
            attributes: Object.fromEntries(
              (layer.properties.length ? layer.properties : Object.keys(properties))
                .filter((name) => name !== layer.label_property)
                .map((name) => [name, properties[name]]),
            ),
          }
        }),
      // Colorée par attribut : une entrée par valeur, puis la couleur de la couche si des objets la gardent.
      legend: (objects): LegendItem[] => {
        const shape = shapeOf(objects)
        if (!shape) return []
        if (!layer.color_property) return [{ label: layer.label, color: layer.color, shape }]
        const categories = Object.entries(layer.colors).map(([label, color]) => ({ label, color }))
        if (objects.some((o) => o.color === layer.color)) {
          categories.push({ label: i18n.global.t('legend.otherValues'), color: layer.color })
        }
        return [{ label: layer.label, shape, categories }]
      },
    }
  })
}
