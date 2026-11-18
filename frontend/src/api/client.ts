/**
 * Client HTTP minimal pour l'API Django (/api/...).
 *
 * En dev, Vite proxifie /api vers le backend (cf. vite.config.ts) : les URLs
 * restent relatives et il n'y a pas de CORS à gérer.
 */

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

/** Le serveur n'a pas pu être joint (réseau coupé, DNS, CORS…) : aucune réponse HTTP. */
export class NetworkError extends Error {
  constructor(url: string, options?: ErrorOptions) {
    super(`Réseau indisponible pour ${url}`, options)
    this.name = 'NetworkError'
  }
}

type QueryValue = string | number | boolean | null | undefined

/** Ajoute une query string à `path`, en ignorant les valeurs null/undefined. */
export function withQuery(path: string, params: Record<string, QueryValue> = {}): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined) query.set(key, String(value))
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
    // fetch ne rejette que si aucune réponse n'arrive (les 4xx/5xx sont traités plus bas).
    throw new NetworkError(url, { cause })
  }
  if (!res.ok) {
    throw new ApiError(res.status, await res.json().catch(() => null), url)
  }
  return res.json() as Promise<T>
}
