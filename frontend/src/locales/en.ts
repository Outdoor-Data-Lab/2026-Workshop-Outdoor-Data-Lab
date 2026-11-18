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
    biodiversity: 'Biodiversity',
    outdoor: 'Outdoor',
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
    trafficArea: 'Cell {id}: score {score}',
    outdoorOffers: 'Outdoor offers',
    biodivAreas: 'Protected or threatened taxa per grid cell',
    biodivArea: 'Cell {name}: {count} protected or threatened taxa',
    loadError: 'Could not load {label}',
  },
  areaFilter: {
    label: 'Area',
    placeholder: 'Search a municipality, a department…',
    noResults: 'No area found.',
    clear: 'Remove the area filter',
  },
  /** Types de zones `ref_geo`, par code (repli : le code). */
  areaTypes: {
    COM: 'Municipality',
    DEP: 'Department',
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
