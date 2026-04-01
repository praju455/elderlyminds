import { useEffect, useState } from 'react'
import { AppShell } from '../ui/AppShell'
import { AuthPanel } from '../ui/AuthPanel'
import { Card } from '../ui/Card'
import { PressableButton } from '../ui/Pressable'
import { getCultureLibrary, getDailyCulture, postVoice, type AppSession, type CulturalItem, type DailyCulture } from '../lib/api'
import { getStoredSession } from '../lib/session'

export function CulturePage() {
  const [session] = useState<AppSession | null>(() => getStoredSession())
  const [calendar, setCalendar] = useState<DailyCulture | null>(null)
  const [stories, setStories] = useState<CulturalItem[]>([])
  const [busyId, setBusyId] = useState('')
  const [error, setError] = useState('')

  const load = async () => {
    if (!session) return
    const [daily, library] = await Promise.all([
      getDailyCulture(session.user_id),
      getCultureLibrary(),
    ])
    setCalendar(daily.calendar)
    setStories(library)
  }

  useEffect(() => {
    if (!session) return
    void load().catch((e: unknown) => setError((e as { message?: string } | undefined)?.message || 'Could not load calendar and stories'))
  }, [session])

  const askForStory = async (item: CulturalItem) => {
    if (!session) return
    try {
      setBusyId(item.id)
      await postVoice({ user_id: session.user_id, text: `Please tell me the ${item.title} story from ${item.tradition}.` })
      window.location.href = '/index.html'
    } finally {
      setBusyId('')
    }
  }

  if (!session) {
    return (
      <AppShell title="Calendar & Stories" subtitle="Login required." showNav={false}>
        <AuthPanel onReady={() => window.location.reload()} />
      </AppShell>
    )
  }

  return (
    <AppShell title="Calendar & Stories" subtitle="Daily cultural context, prayers, and stories.">
      <Card>
        <p className="text-lg font-extrabold tracking-tight text-ink">Today's calendar</p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <div className="rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
            <p className="text-xs font-bold tracking-wide text-ink/60">Day</p>
            <p className="mt-1 text-xl font-extrabold tracking-tight text-ink">{calendar?.day_name || '--'}</p>
          </div>
          <div className="rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
            <p className="text-xs font-bold tracking-wide text-ink/60">Deity</p>
            <p className="mt-1 text-xl font-extrabold tracking-tight text-ink">{calendar?.deity || '--'}</p>
          </div>
          <div className="rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
            <p className="text-xs font-bold tracking-wide text-ink/60">Tithi</p>
            <p className="mt-1 text-sm font-semibold text-ink">{calendar?.tithi || 'Unknown'}</p>
          </div>
          <div className="rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
            <p className="text-xs font-bold tracking-wide text-ink/60">Festival</p>
            <p className="mt-1 text-sm font-semibold text-ink">{calendar?.festival || 'None today'}</p>
          </div>
        </div>
        {calendar?.recommended ? (
          <div className="mt-3 rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
            <p className="text-sm font-extrabold text-ink">Recommended today</p>
            <p className="mt-1 text-base font-semibold text-ink">{calendar.recommended.title}</p>
            <p className="mt-1 text-sm text-ink/65">{calendar.recommended.summary}</p>
          </div>
        ) : null}
      </Card>

      <Card>
        <p className="text-lg font-extrabold tracking-tight text-ink">Stories and prayers</p>
        <div className="mt-3 space-y-2">
          {stories.map((item) => (
            <div key={item.id} className="rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
              <p className="text-sm font-extrabold text-ink">{item.title}</p>
              <p className="mt-1 text-xs font-bold tracking-wide text-ink/55">{item.tradition}</p>
              <p className="mt-2 text-sm text-ink/70">{item.summary}</p>
              <p className="mt-2 text-sm font-semibold text-ink">Moral: {item.moral}</p>
              {item.quote ? <p className="mt-2 text-sm italic text-ink/70">"{item.quote}"</p> : null}
              <div className="mt-3">
                <PressableButton variant="soft" size="lg" onClick={() => void askForStory(item)} disabled={busyId === item.id}>
                  {busyId === item.id ? 'Loading...' : 'Tell me this'}
                </PressableButton>
              </div>
            </div>
          ))}
        </div>
        {error ? <p className="mt-3 text-sm font-semibold text-danger">{error}</p> : null}
      </Card>
    </AppShell>
  )
}
