import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { gsap } from 'gsap'
import { AppShell } from '../ui/AppShell'
import { AuthPanel } from '../ui/AuthPanel'
import { Card } from '../ui/Card'
import { PressableButton } from '../ui/Pressable'
import { SparkleSticker } from '../ui/stickers'
import { getActivity, updateActivityStatus, type ActivitySummary, type AppSession } from '../lib/api'
import { getStoredSession } from '../lib/session'
import { RppgCaptureCard } from '../ui/RppgCaptureCard'

function StatusDot({ status }: { status: string }) {
  const ref = useRef<HTMLSpanElement | null>(null)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const ctx = gsap.context(() => {
      gsap.fromTo(el, { scale: 0.92, opacity: 0.75 }, { scale: 1.08, opacity: 1, duration: 0.9, repeat: -1, yoyo: true, ease: 'sine.inOut' })
    }, el)
    return () => ctx.revert()
  }, [])

  const color = status === 'good' ? 'bg-mint' : status === 'watch' ? 'bg-rose' : 'bg-lemon'
  return (
    <span className="relative inline-flex h-3 w-3 items-center justify-center">
      <span ref={ref} className={['absolute h-3 w-3 rounded-full', color].join(' ')} />
      <span className="absolute h-6 w-6 rounded-full bg-white/30 ring-1 ring-black/5" />
    </span>
  )
}

export function ActivityPage() {
  const [session] = useState<AppSession | null>(() => getStoredSession())
  const [activity, setActivity] = useState<ActivitySummary | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const panelRef = useRef<HTMLDivElement | null>(null)

  const load = async () => {
    if (!session) return
    setActivity(await getActivity(session.user_id))
  }

  useEffect(() => {
    if (!session) return
    void load().catch((e: unknown) => setError((e as { message?: string } | undefined)?.message || 'Could not load activity'))
  }, [session])

  useLayoutEffect(() => {
    const el = panelRef.current
    if (!el || activity?.status !== 'watch') return
    const ctx = gsap.context(() => {
      gsap.fromTo(el, { x: -2 }, { x: 2, duration: 0.08, repeat: 5, yoyo: true })
    }, el)
    return () => ctx.revert()
  }, [activity?.status])

  const setStatus = async (status: string, mood: string, note: string) => {
    if (!session) return
    try {
      setBusy(true)
      setActivity(await updateActivityStatus(session.user_id, { status, mood, note }))
    } catch (e: unknown) {
      setError((e as { message?: string } | undefined)?.message || 'Could not update status')
    } finally {
      setBusy(false)
    }
  }

  if (!session) {
    return (
      <AppShell title="Health" subtitle="Login required." showNav={false}>
        <AuthPanel onReady={() => window.location.reload()} />
      </AppShell>
    )
  }

  return (
    <AppShell title="Activity" subtitle="Live status, hydration, sleep, and notes.">
      <Card>
        <div ref={panelRef} className="flex items-start justify-between gap-4">
          <div>
            <p className="text-lg font-extrabold tracking-tight text-ink">Right now</p>
            <p className="mt-1 text-sm text-ink/60">
              {activity?.status === 'good'
                ? 'You are doing well today.'
                : activity?.status === 'watch'
                  ? 'A gentle watch is active for today.'
                  : 'Everything looks steady and calm.'}
            </p>
            <div className="mt-3 inline-flex items-center gap-2 rounded-2xl bg-white/70 px-3 py-2 shadow-soft ring-1 ring-black/5">
              <StatusDot status={activity?.status || 'okay'} />
              <span className="text-sm font-bold text-ink">
                {activity?.status || 'okay'} - mood {activity?.mood || 'okay'}
              </span>
            </div>
          </div>
          <div className="h-14 w-14 shrink-0">
            <SparkleSticker className="h-14 w-14" />
          </div>
        </div>
      </Card>

      {error ? (
        <Card>
          <p className="text-sm font-semibold text-danger">{error}</p>
        </Card>
      ) : null}

      <Card>
        <p className="text-lg font-extrabold tracking-tight text-ink">Today's snapshot</p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <div className="rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
            <p className="text-xs font-bold tracking-wide text-ink/60">Steps</p>
            <p className="mt-1 text-2xl font-extrabold tracking-tight text-ink">{activity?.steps ?? 0}</p>
          </div>
          <div className="rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
            <p className="text-xs font-bold tracking-wide text-ink/60">Sleep</p>
            <p className="mt-1 text-2xl font-extrabold tracking-tight text-ink">{activity?.sleep_hours ?? 0}h</p>
          </div>
          <div className="rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
            <p className="text-xs font-bold tracking-wide text-ink/60">Water</p>
            <p className="mt-1 text-2xl font-extrabold tracking-tight text-ink">{activity?.water_cups ?? 0} cups</p>
          </div>
          <div className="rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
            <p className="text-xs font-bold tracking-wide text-ink/60">Mood Score</p>
            <p className="mt-1 text-2xl font-extrabold tracking-tight text-ink">{activity?.mood_score ?? 0}</p>
          </div>
        </div>
      </Card>

      <RppgCaptureCard userId={session.user_id} onAnalyzed={() => load()} />

      <Card>
        <p className="text-lg font-extrabold tracking-tight text-ink">Quick actions</p>
        <p className="mt-1 text-sm text-ink/60">These actions now update today's status in the backend.</p>
        <div className="mt-3 grid gap-2">
          <PressableButton size="lg" variant="soft" onClick={() => void setStatus('good', 'good', 'User feels okay today.')} disabled={busy}>
            I feel okay
          </PressableButton>
          <PressableButton size="lg" variant="soft" onClick={() => void setStatus('okay', 'okay', 'User feels a little tired.')} disabled={busy}>
            A little tired
          </PressableButton>
          <PressableButton size="lg" variant="soft" onClick={() => void setStatus('watch', 'low', 'User is not feeling great and needs a closer check.')} disabled={busy}>
            Not feeling great
          </PressableButton>
        </div>
      </Card>

      <Card>
        <p className="text-lg font-extrabold tracking-tight text-ink">Today's notes</p>
        <div className="mt-3 space-y-2">
          {(activity?.notes || []).slice(-5).reverse().map((note, index) => (
            <div key={`${note}-${index}`} className="rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
              <p className="text-sm text-ink/70">{note}</p>
            </div>
          ))}
          {!(activity?.notes || []).length ? <p className="text-sm text-ink/60">No notes saved yet.</p> : null}
        </div>
      </Card>
    </AppShell>
  )
}
