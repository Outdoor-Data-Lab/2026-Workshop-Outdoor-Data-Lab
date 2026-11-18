<script setup lang="ts">
import MapView from '@/components/MapView.vue'
</script>

<template>
  <main>
    <MapView @feature-click="(p) => console.log(p)"></MapView>
  </main>
</template>

<style scoped>
main {
  flex: 1; /* prend toute la hauteur restante de #app, sous le header */
  min-height: 0;
}
</style>
