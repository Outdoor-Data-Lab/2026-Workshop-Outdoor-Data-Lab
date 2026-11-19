import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, describe, expect, it, vi } from 'vitest'

import LayerSwitcher from '@/components/LayerSwitcher.vue'
import { i18n } from '@/i18n'
import { useLayersStore, type LayerDefinition } from '@/stores/layers'

const layer = (id: string, group: string): LayerDefinition =>
  ({ id, label: id, group, load: async () => [] }) as LayerDefinition

describe('LayerSwitcher', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('sorts the sections, then the layers of each section, the unranked ones last', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              group_order: { outdoor: 1, traffic: 2 },
              layer_order: { 'traffic/area': 1, 'traffic/segment': 2 },
            }),
          ),
      ),
    )
    const pinia = createPinia()
    setActivePinia(pinia)
    useLayersStore().addDefinitions([
      layer('traffic/counter', 'traffic'),
      layer('traffic/segment', 'traffic'),
      layer('traffic/area', 'traffic'),
      layer('outdoor/offer', 'outdoor'),
    ])
    const wrapper = mount(LayerSwitcher, { global: { plugins: [i18n, pinia] } })
    await flushPromises()

    expect(wrapper.findAll('label').map((l) => l.text())).toEqual([
      'outdoor/offer',
      'traffic/area',
      'traffic/segment',
      'traffic/counter',
    ])
  })
})
