/** Client HTTP de l'API Django, via le proxy Vite `/api`. */
import type { Feature, FeatureCollection, GeoJsonProperties, Geometry } from 'geojson'

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
    url: string,
  ) {
    super(`API ${status} sur ${url}`)
    this.name = 'ApiError'
  }
}

/** Aucune réponse HTTP (réseau coupé, DNS…). */
export class NetworkError extends Error {
  constructor(url: string, options?: ErrorOptions) {
    super(`Réseau indisponible pour ${url}`, options)
    this.name = 'NetworkError'
  }
}

export type Paginated<T> = {
  count: number
  next?: string | null
  previous?: string | null
  results: T[]
}

/** Page d'une liste demandée avec `?format=geojson` (`GeoJsonLimitOffsetPagination`). */
export type GeoJsonPage<
  G extends Geometry | null = Geometry,
  P = GeoJsonProperties,
> = FeatureCollection<G, P> & {
  count: number
  next: string | null
  previous: string | null
}

/** Pagination limit/offset ; le backend renvoie 50 éléments si `limit` est absent. */
export type LimitOffset = { limit?: number; offset?: number }

type QueryScalar = string | number | boolean
type QueryValue = QueryScalar | QueryScalar[] | null | undefined

/** Ajoute une query string, sans les valeurs null/undefined. Un tableau répète la clé. */
export function withQuery(path: string, params: Record<string, QueryValue> = {}): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined) continue
    for (const item of Array.isArray(value) ? value : [value]) query.append(key, String(item))
  }
  const qs = query.toString()
  return qs ? `${path}?${qs}` : path
}

export async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(url, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
        ...init?.headers,
      },
    })
  } catch (cause) {
    // fetch ne rejette qu'en l'absence de réponse.
    throw new NetworkError(url, { cause })
  }
  if (!res.ok) {
    throw new ApiError(res.status, await res.json().catch(() => null), url)
  }
  return res.json() as Promise<T>
}

/** Toutes les features de `url`, en suivant les liens `next` d'une FeatureCollection paginée. */
export async function fetchAllFeatures<F extends Feature = Feature>(
  url: string,
  init?: RequestInit,
): Promise<F[]> {
  let features: F[] = []
  for (let next: string | null | undefined = url; next;) {
    const page: { features: F[]; next?: string | null } = await apiFetch(next, init)
    features = features.concat(page.features)
    next = page.next
  }
  return features
}
