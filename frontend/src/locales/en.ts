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
    segment: 'Segments and tracks',
  },
  layers: {
    loading: '(loading)',
    failed: '(failed)',
    trafficAreas: 'Traffic per grid cell',
    fromZoom: 'Visible from zoom {zoom}: zoom in on the map.',
    cellName: 'Cell',
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
    scoreRange: '(between 0 and 100)',
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
    score: {
      title: 'How the score is computed',
      reference: 'Reference source: it is used to weight the others and is not part of the score.',
      weight: 'Weight in the score: {weight}%',
      intro:
        'The score (0 to 100) combines the frequentation sources, each counting more the better it matches the eco-counters (BiodivTourAlps method, V. Cazalis).',
      step1:
        "Weights: for each source, its counts around the eco-counters are correlated (Pearson) with the eco-counters' mean daily count in summer (June to September, since 2021, half-months with more than 10 days of data).",
      step2:
        'A source whose correlation r does not exceed 0.25 gets a zero weight; otherwise its raw weight is 1 / (1 − r). Raw weights are scaled to a total of 100.',
      step3:
        'Each source is standardised: for each cell, the mean over all cells is subtracted and the result divided by the standard deviation (z-score; a cell with no data from the source counts as 0).',
      step4:
        'The z-scores are summed with their weights, values above the 98th percentile are capped, and the result is rescaled to 0–100.',
      equation: 'score = normalise 0-100( Σ weight(source) × z-score(source, cell) )',
      counters: 'Weights estimated on {n} eco-counters.',
    },
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
