/** Référentiel géographique : zones (communes, départements, parcs…) pour filtrer les couches. */
import type { Feature, Geometry } from 'geojson'

import { apiFetch, withQuery, type Paginated } from './client'

const BASE = '/api/ref-geo'

/** Zone trouvée par son nom, sans géométrie. */
export type AreaMatch = {
  id_area: number
  area_name: string
  area_code: string
  type_code: string
}

/** Grilles (M0.5, M1, M5, M10…) exclues : leurs mailles ne se cherchent pas par nom. Les massifs (MAS) restent. */
const GRID_TYPE = /^M\d/

/** Nom exact d'abord, puis ceux qui commencent par `name`, puis les autres, chacun par ordre alphabétique. */
export async function searchAreas(name: string, limit = 10): Promise<AreaMatch[]> {
  const url = withQuery(`${BASE}/areas`, { name, ordering: 'area_name', limit: limit * 3 })
  const { results } = await apiFetch<Paginated<AreaMatch>>(url)
  const query = name.toLocaleLowerCase()
  const rank = (area: AreaMatch) => {
    const areaName = area.area_name.toLocaleLowerCase()
    return areaName === query ? 0 : areaName.startsWith(query) ? 1 : 2
  }
  return results
    .filter((area) => !GRID_TYPE.test(area.type_code))
    .sort((a, b) => rank(a) - rank(b))
    .slice(0, limit)
}

/** Contour d'une zone, en WGS84. */
export async function getAreaGeometry(id: number): Promise<Geometry> {
  const url = withQuery(`${BASE}/areas/${id}`, { format: 'geojson' })
  return (await apiFetch<Feature>(url)).geometry
}
