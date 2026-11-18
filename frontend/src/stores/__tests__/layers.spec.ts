import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useLayersStore } from '@/stores/layers'
import type { MapObject } from '@/types/mapObject'

const point: MapObject = {
  key: 'traffic/counter:1',
  id: 1,
  domain: 'traffic',
  layer: 'traffic/counter',
  label: 'Counter 1',
  geometry: { type: 'Point', coordinates: [6, 45] },
}

describe('layers store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('loads a layer the first time it is shown, and only then', async () => {
    const layers = useLayersStore()
    const load = vi.fn().mockResolvedValue([point])
    layers.addDefinitions([{ id: 'traffic/counter', label: 'Counter', group: 'Traffic', load }])

    layers.setVisible('traffic/counter', true)
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
})
