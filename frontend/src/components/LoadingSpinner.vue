<template>
  <span class="spinner" role="status" :aria-label="$t('loading')"></span>
</template>

<style scoped>
.spinner {
  display: inline-block;
  width: 0.9em;
  height: 0.9em;
  vertical-align: -0.1em;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinner {
    animation-duration: 2.5s;
  }
}
</style>
