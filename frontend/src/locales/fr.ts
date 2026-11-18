import type en from './en'

export default {
  concepts: {
    label: 'Concept',
    global: 'Global',
    traffic: 'Fréquentation',
    biodiversity: 'Biodiversité',
  },
  layerGroups: {
    traffic: 'Fréquentation',
    external: 'Couches externes',
  },
  countingObjectTypes: {
    counter: 'Compteur',
    segment: 'Segment',
  },
  layers: {
    loading: '(chargement)',
    failed: '(échec)',
    trafficAreas: 'Fréquentation par maille',
    loadError: 'Impossible de charger {label}',
  },
  legend: {
    title: 'Légende',
    counters: 'Compteurs',
    trafficAreas: 'Fréquentation par maille (score)',
  },
  detail: {
    title: 'Détail',
    empty: 'Sélectionnez un objet sur la carte.',
  },
  notifications: {
    close: 'Fermer',
    withContext: '{context} : {message}',
  },
  errors: {
    network: 'Connexion au serveur impossible. Vérifiez votre réseau.',
    server: 'Le serveur est indisponible pour le moment. Réessayez plus tard.',
    notFound: 'Élément introuvable.',
    forbidden: "Vous n'avez pas accès à cette ressource.",
    badRequest: 'Requête invalide.',
    unexpectedStatus: 'Réponse inattendue du serveur ({status}).',
    unexpected: 'Une erreur inattendue est survenue.',
    field: '{field} : {message}',
  },
} satisfies typeof en
