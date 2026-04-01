export async function ensureNotificationPermission(): Promise<NotificationPermission> {
  if (!('Notification' in window)) return 'denied'
  if (Notification.permission === 'granted') return 'granted'
  if (Notification.permission === 'denied') return 'denied'
  return await Notification.requestPermission()
}

export async function notify(title: string, options?: NotificationOptions) {
  const permission = await ensureNotificationPermission()
  if (permission !== 'granted') return

  const reg = await navigator.serviceWorker.getRegistration()
  if (reg && 'showNotification' in reg) {
    await reg.showNotification(title, options)
    return
  }

  // Fallback (when SW isn't ready)
  new Notification(title, options)
}

export async function playAlarmTone(durationMs = 2600) {
  const Ctx = window.AudioContext || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  if (!Ctx) return
  const ctx = new Ctx()
  const endAt = ctx.currentTime + durationMs / 1000
  let start = ctx.currentTime

  while (start < endAt) {
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'sine'
    osc.frequency.setValueAtTime(880, start)
    gain.gain.setValueAtTime(0.0001, start)
    gain.gain.exponentialRampToValueAtTime(0.25, start + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.26)
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.start(start)
    osc.stop(start + 0.28)
    start += 0.32
  }

  window.setTimeout(() => {
    void ctx.close()
  }, durationMs + 200)
}
