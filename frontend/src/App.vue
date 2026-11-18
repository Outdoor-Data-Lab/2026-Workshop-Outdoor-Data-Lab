<script setup lang="ts">
import { RouterView } from 'vue-router'

import AppNotifications from '@/components/AppNotifications.vue'
import NavBar from '@/components/NavBar.vue'
</script>

<template>
  <NavBar />
  <RouterView />
  <AppNotifications />
</template>
