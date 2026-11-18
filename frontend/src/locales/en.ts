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
    fromZoom: 'Visible from zoom {zoom}: zoom in on the map.',
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
    tracks: 'Outings (tracks)',
    trafficAreas: 'Traffic per grid cell (score)',
  },
  offer: {
    practice: 'Practice',
  },
  detail: {
    title: 'Detail',
    empty: 'Select an object on the map.',
  },
  cell: {
    loading: 'Loading…',
    traffic: 'Traffic',
    biodiversity: 'Biodiversity',
    outdoor: 'Outdoor',
    zonings: 'Regulatory zoning',
    soon: 'coming soon',
    taxa: 'no protected or threatened taxon | {n} protected or threatened taxon | {n} protected or threatened taxa',
    taxaList: 'List of taxa',
    protected: 'protected',
    threatened: 'threatened ({code})',
    observations: '{n} observation | {n} observations',
    taxaNote:
      'Protected: national protection. Threatened: national red list (RE, CR, EN, VU, EX). GBIF and SINP observations.',
    offers: 'no offer | {n} offer | {n} offers',
    absolute: 'absolute',
    relative: 'relative',
    /** What each source counts, by code. */
    units: {
      ecocompteur: '{n} passage counted | {n} passages counted',
      strava:
        '{n} trip on the segments of the cell | {n} trips summed over the segments of the cell',
      outdoorvision: '{n} GPS outing crossing the cell | {n} GPS outings crossing the cell',
      inaturalist: '{n} observer-day | {n} observer-days',
      other: '{n} measure | {n} measures',
    },
    countsNote:
      'Absolute: the counter counts every passage. Relative: only the users of an app are counted; these figures compare cells with each other. The score combines the sources, weighted by how well they match the eco-counters.',
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
