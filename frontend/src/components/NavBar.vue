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
  background: #2e6b3f;
  color: #fff;
}

.title {
  font-size: 1.25rem;
  font-weight: bold;
}
</style>
