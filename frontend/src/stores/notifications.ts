import { defineStore } from 'pinia'
import { ref } from 'vue'

import { describeError } from '@/api/errors'
import { i18n } from '@/i18n'

export type NotificationType = 'error' | 'warning' | 'info' | 'success'

export interface AppNotification {
  id: number
  type: NotificationType
  message: string
  /** Occurrences du même message. */
  count: number
}

/** Durée d'affichage en ms ; `null` = fermeture manuelle. */
const TIMEOUTS: Record<NotificationType, number | null> = {
  error: null,
  warning: 8000,
  info: 5000,
  success: 5000,
}

/** Messages utilisateur, affichés par <AppNotifications />. */
export const useNotificationsStore = defineStore('notifications', () => {
  const items = ref<AppNotification[]>([])

  let nextId = 1
  const timers = new Map<number, ReturnType<typeof setTimeout>>()

  function scheduleDismiss(notification: AppNotification) {
    clearTimeout(timers.get(notification.id))
    const timeout = TIMEOUTS[notification.type]
    if (timeout !== null) {
      timers.set(
        notification.id,
        setTimeout(() => dismiss(notification.id), timeout),
      )
    }
  }

  function notify(type: NotificationType, message: string) {
    const existing = items.value.find((n) => n.type === type && n.message === message)
    if (existing) {
      existing.count++
      scheduleDismiss(existing)
      return existing.id
    }
    const notification: AppNotification = { id: nextId++, type, message, count: 1 }
    items.value.push(notification)
    scheduleDismiss(notification)
    return notification.id
  }

  /** Notifie une erreur en clair et la journalise en console. */
  function notifyError(error: unknown, context?: string) {
    console.error(context ?? 'Error', error)
    const description = describeError(error)
    return notify(
      'error',
      context
        ? i18n.global.t('notifications.withContext', { context, message: description })
        : description,
    )
  }

  function dismiss(id: number) {
    clearTimeout(timers.get(id))
    timers.delete(id)
    items.value = items.value.filter((n) => n.id !== id)
  }

  function clear() {
    for (const timer of timers.values()) clearTimeout(timer)
    timers.clear()
    items.value = []
  }

  return { items, notify, notifyError, dismiss, clear }
})
