<script setup lang="ts">
/** Bouton « i » qui ouvre la fenêtre « À propos ». Textes : clés `about.*` des traductions. */
import { useTemplateRef } from 'vue'

import schemaUrl from '@/assets/schema-odl.webp'

const REPOSITORY_URL = 'https://github.com/Outdoor-Data-Lab/2026-Workshop-Outdoor-Data-Lab'

/** Noms propres : pas traduits. */
const PARTNERS = [
  'LPO France et AuRA',
  'Natural Solutions',
  'PatriNat (MNHN-OFB-CNRS-IRD)',
  'Parc national des Cévennes',
  'Parc national des Écrins',
  'PRNTESN - CREPS AuRA Vallon Pont d’Arc · Voiron · Lyon',
  'Réserves naturelles de France',
]

const dialog = useTemplateRef<HTMLDialogElement>('dialog')

/** Clic sur le fond assombri (hors du contenu) : ferme la fenêtre. */
function closeOnBackdrop(event: MouseEvent) {
  if (event.target === dialog.value) dialog.value?.close()
}
</script>

<template>
  <button
    type="button"
    class="open"
    :aria-label="$t('about.open')"
    :title="$t('about.open')"
    @click="dialog?.showModal()"
  >
    i
  </button>
  <dialog ref="dialog" aria-labelledby="about-title" @click="closeOnBackdrop">
    <div class="content">
      <!-- Focus à l'ouverture sur le titre : sinon sur le lien, et la fenêtre s'ouvre défilée. -->
      <h2 id="about-title" tabindex="-1" autofocus>{{ $t('about.title') }}</h2>
      <p v-for="(paragraph, i) in $tm('about.intro')" :key="i">{{ $rt(paragraph) }}</p>
      <img :src="schemaUrl" :alt="$t('about.schemaAlt')" width="1400" height="1125" />
      <p>{{ $t('about.outlook') }}</p>
      <p>
        {{ $t('about.repository') }}
        <a :href="REPOSITORY_URL" target="_blank" rel="noopener noreferrer">{{ REPOSITORY_URL }}</a>
      </p>
      <p>{{ $t('about.credits') }}</p>
      <ul>
        <li v-for="partner in PARTNERS" :key="partner">{{ partner }}</li>
      </ul>
      <form method="dialog">
        <button>{{ $t('about.close') }}</button>
      </form>
    </div>
  </dialog>
</template>

<style scoped>
.open {
  width: 1.75rem;
  height: 1.75rem;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  background: var(--color-background);
  color: var(--color-text);
  font: italic bold 1rem serif;
  cursor: pointer;
}

dialog {
  width: min(44rem, calc(100vw - 2 * var(--space)));
  max-height: calc(100vh - 4 * var(--space));
  padding: 0;
  border: none;
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}

dialog::backdrop {
  background: rgb(0 0 0 / 40%);
}

.content {
  display: flex;
  flex-direction: column;
  gap: var(--space);
  padding: calc(var(--space) * 1.5);
  line-height: 1.5;
}

h2 {
  margin: 0;
  font-size: 1.25rem;
  outline: none;
}

p,
ul {
  margin: 0;
}

img {
  width: 100%;
  height: auto;
}

/* Le lien long passe à la ligne au lieu de déborder. */
a {
  overflow-wrap: anywhere;
}

form {
  display: flex;
  justify-content: flex-end;
}
</style>
