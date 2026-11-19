import type { LineString } from 'geojson'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ExternalLayer } from '@/api/externalLayers'
import { externalLayers } from '@/catalog'

const layer: ExternalLayer = {
  id: 1,
  label: 'Habitats',
  url: 'https://example.org/habitats?page=1',
  description: 'Données : Parc national des Écrins',
  properties: ['LIB_CB', 'CODE_CB'],
  label_property: 'LIB_CB',
  color: '#3388ff',
  color_property: 'STATUT',
  colors: { PR: '#c0392b' },
}

function habitat(statut: string) {
  return {
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [6, 45] },
    properties: { STATUT: statut, LIB_CB: 'Eboulis', CODE_CB: '61.2' },
  }
}

const responses: Record<string, unknown> = {
  '/api/commons/external-layers': { count: 1, results: [layer] },
  'https://example.org/habitats?page=1': {
    type: 'FeatureCollection',
    features: [habitat('PR')],
    next: 'https://example.org/habitats?page=2',
  },
  'https://example.org/habitats?page=2': { type: 'FeatureCollection', features: [habitat('NC')] },
}

describe('externalLayers', () => {
  beforeEach(() =>
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => new Response(JSON.stringify(responses[url]))),
    ),
  )
  afterEach(() => vi.unstubAllGlobals())

  it('loads every page, colors by value and keeps the chosen attributes', async () => {
    const [definition] = await externalLayers()
    const objects = await definition!.load!({})

    expect(definition!.description).toBe('Données : Parc national des Écrins')
    expect(objects.map((o) => o.color)).toEqual(['#c0392b', '#3388ff'])
    // L'attribut du nom est en titre, pas dans les attributs.
    expect(objects[0]!.attributes).toEqual({ CODE_CB: '61.2' })
    expect(objects[0]!.label).toBe('Eboulis')
  })

  it('lists the attribute values under the layer name, then the layer color if used', async () => {
    const [definition] = await externalLayers()
    const point = { key: 'k', id: 1, domain: 'external', layer: 'external/1', label: 'x' } as const
    const line: LineString = { type: 'LineString', coordinates: [] }

    expect(definition!.legend!([])).toEqual([])
    // Un objet sans couleur de valeur : « Other », à la couleur de la couche.
    expect(definition!.legend!([{ ...point, geometry: line, color: '#3388ff' }])).toEqual([
      {
        label: 'Habitats',
        shape: 'line',
        categories: [
          { label: 'PR', color: '#c0392b' },
          { label: 'Other', color: '#3388ff' },
        ],
      },
    ])
    expect(
      definition!.legend!([{ ...point, geometry: { type: 'MultiLineString', coordinates: [] } }]),
    ).toEqual([
      { label: 'Habitats', shape: 'line', categories: [{ label: 'PR', color: '#c0392b' }] },
    ])
  })
})
