/** Textes de référence : `fr.ts` doit avoir les mêmes clés (vérifié par le typage). */
export default {
  concepts: {
    label: 'Concept',
    global: 'Global',
    traffic: 'Traffic',
    biodiversity: 'Biodiversity',
  },
  layerGroups: {
    traffic: 'Traffic',
    external: 'External layers',
  },
  /** Valeurs de référence de l'API, par code (repli : le libellé de l'API). */
  countingObjectTypes: {
    counter: 'Counter',
    segment: 'Segment',
  },
  layers: {
    loading: '(loading)',
    failed: '(failed)',
    trafficAreas: 'Traffic per grid cell',
    loadError: 'Could not load {label}',
  },
  legend: {
    title: 'Legend',
    counters: 'Counters',
    trafficAreas: 'Traffic per grid cell (score)',
  },
  detail: {
    title: 'Detail',
    empty: 'Select an object on the map.',
  },
  notifications: {
    close: 'Close',
    withContext: '{context}: {message}',
  },
  errors: {
    network: 'Cannot reach the server. Check your connection.',
    server: 'The server is unavailable at the moment. Try again later.',
    notFound: 'Not found.',
    forbidden: 'You do not have access to this resource.',
    badRequest: 'Invalid request.',
    unexpectedStatus: 'Unexpected server response ({status}).',
    unexpected: 'An unexpected error occurred.',
    field: '{field}: {message}',
  },
}
