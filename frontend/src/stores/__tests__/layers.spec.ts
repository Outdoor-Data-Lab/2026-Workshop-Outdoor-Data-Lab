import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useLayersStore, type LayerDefinition } from '@/stores/layers'
import type { LayerId, MapObject } from '@/types/mapObject'

const point: MapObject = {
  key: 'traffic/counter:1',
  id: 1,
  domain: 'traffic',
  layer: 'traffic/counter',
  label: 'Counter 1',
  geometry: { type: 'Point', coordinates: [6, 45] },
}

function definition(id: LayerId, load = vi.fn().mockResolvedValue([])): LayerDefinition {
  return { id, label: id, group: 'Group', load }
}

describe('layers store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('loads a layer the first time it is shown, and only then', async () => {
    const layers = useLayersStore()
    const load = vi.fn().mockResolvedValue([point])

    layers.addDefinitions([definition('traffic/counter', load)])
    await vi.waitFor(() => expect(layers.objectsByLayer['traffic/counter']).toEqual([point]))
    layers.setVisible('traffic/counter', false)
    layers.setVisible('traffic/counter', true)

    expect(load).toHaveBeenCalledTimes(1)
  })

  it('sends only visible layers to the map', () => {
    const layers = useLayersStore()
    layers.setLayer('traffic/counter', [point])

    expect(layers.featureCollections['traffic/counter']).toBeUndefined()
    layers.setVisible('traffic/counter', true)
    expect(layers.featureCollections['traffic/counter']?.features).toHaveLength(1)
  })

  it('shows the layers of the selected concept only', () => {
    const layers = useLayersStore()
    layers.addDefinitions([definition('traffic/counter'), definition('biodiversity/taxon')])
    expect(layers.visible).toEqual({ 'traffic/counter': true, 'biodiversity/taxon': true })

    layers.setConcept('traffic')
    expect(layers.visible).toEqual({ 'traffic/counter': true, 'biodiversity/taxon': false })

    layers.setConcept('biodiversity')
    expect(layers.visible).toEqual({ 'traffic/counter': false, 'biodiversity/taxon': true })
  })
})
