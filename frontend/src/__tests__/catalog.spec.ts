import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ExternalLayer } from '@/api/externalLayers'
import { externalLayers } from '@/catalog'

const layer: ExternalLayer = {
  id: 1,
  label: 'Habitats',
  url: 'https://example.org/habitats?page=1',
  description: 'Données : Parc national des Écrins',
  properties: ['LIB_CB'],
  color: '#3388ff',
  color_property: 'STATUT',
  colors: { PR: '#c0392b' },
}

function habitat(statut: string) {
  return {
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [6, 45] },
    properties: { STATUT: statut, LIB_CB: 'Eboulis' },
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
  afterEach(() => vi.unstubAllGlobals())

  it('loads every page, colors by value and keeps the chosen attributes', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => new Response(JSON.stringify(responses[url]))),
    )
    const [definition] = await externalLayers()
    const objects = await definition!.load!({})

    expect(definition!.description).toBe('Données : Parc national des Écrins')
    expect(objects.map((o) => o.color)).toEqual(['#c0392b', '#3388ff'])
    expect(objects[0]!.attributes).toEqual({ LIB_CB: 'Eboulis' })
  })
})
