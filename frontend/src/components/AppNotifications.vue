<script setup lang="ts">
import { useNotificationsStore } from '@/stores/notifications'

const notifications = useNotificationsStore()
</script>

<template>
  <div class="notifications">
    <TransitionGroup name="toast">
      <div
        v-for="n in notifications.items"
        :key="n.id"
        class="toast"
        :class="n.type"
        :role="n.type === 'error' ? 'alert' : 'status'"
      >
        <p>
          {{ n.message }}
          <span v-if="n.count > 1" class="count">×{{ n.count }}</span>
        </p>
        <button type="button" aria-label="Close" @click="notifications.dismiss(n.id)">×</button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.notifications {
  position: fixed;
  z-index: 1000; /* au-dessus de la carte */
  /* En haut à gauche de la carte, sous la barre de navigation et à droite du panneau gauche. */
  top: 4rem;
  left: calc(var(--panel-width) + var(--space));
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  width: min(26rem, calc(100vw - 1.5rem));
  pointer-events: none; /* la carte reste cliquable */
}

.toast {
  --accent: #2b6cb0;
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.6rem 0.5rem 0.6rem 0.85rem;
  background: #fff;
  color: #1f2933;
  border-left: 4px solid var(--accent);
  border-radius: 4px;
  box-shadow: 0 2px 8px rgb(0 0 0 / 18%);
  pointer-events: auto;
}

.toast.error {
  --accent: #c0392b;
}
.toast.warning {
  --accent: #d68910;
}
.toast.success {
  --accent: #2e9e5b;
}

.toast p {
  flex: 1;
  margin: 0;
  line-height: 1.4;
}

.count {
  margin-left: 0.25rem;
  padding: 0 0.35rem;
  border-radius: 999px;
  background: var(--accent);
  color: #fff;
  font-size: 0.75rem;
}

.toast button {
  flex-shrink: 0;
  width: 1.75rem;
  height: 1.75rem;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: inherit;
  font-size: 1.25rem;
  line-height: 1;
  cursor: pointer;
}

.toast button:hover,
.toast button:focus-visible {
  background: rgb(0 0 0 / 8%);
}

.toast-enter-active,
.toast-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-0.5rem);
}

@media (prefers-reduced-motion: reduce) {
  .toast-enter-active,
  .toast-leave-active {
    transition: none;
  }
}
</style>
