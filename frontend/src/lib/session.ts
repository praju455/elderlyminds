import type { AppSession } from './api'

const KEY = 'eldermind-session'

export function getStoredSession(): AppSession | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(KEY)
    if (!raw) return null
    const session = JSON.parse(raw) as AppSession & { role?: string }
    if (String(session.role || '') === 'caretaker') session.role = 'support'
    return session as AppSession
  } catch {
    return null
  }
}

export function saveStoredSession(session: AppSession) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(KEY, JSON.stringify(session))
}

export function clearStoredSession() {
  if (typeof window === 'undefined') return
  window.localStorage.removeItem(KEY)
}
