<script setup lang="ts">
import AboutDialog from '@/components/AboutDialog.vue'
</script>

<template>
  <header class="navbar">
    <span class="title">Outdoor Data Lab</span>
    <AboutDialog />
  </header>
</template>

<style scoped>
.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space);
  border-bottom: 1px solid var(--color-border);
}

.title {
  font-size: 1.25rem;
  font-weight: bold;
}
</style>
