import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { gsap } from 'gsap'
import { AppShell } from '../ui/AppShell'
import { AuthPanel } from '../ui/AuthPanel'
import { Card } from '../ui/Card'
import { PressableButton } from '../ui/Pressable'
import { PillSticker } from '../ui/stickers'
import { confirmMedicine, getMedicines, type AppSession, type MedicineItem, type MedicineLog } from '../lib/api'
import { getStoredSession } from '../lib/session'


export function MedicationPage() {
  const [session] = useState<AppSession | null>(() => getStoredSession())
  const [meds, setMeds] = useState<MedicineItem[]>([])
  const [logs, setLogs] = useState<MedicineLog[]>([])
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)
  const listRef = useRef<HTMLDivElement | null>(null)

  const load = async () => {
    if (!session) return
    const data = await getMedicines(session.user_id)
    setMeds(data.medicines)
    setLogs(data.logs)
  }

  useEffect(() => {
    if (!session) return
    void load().catch((e: unknown) => setError((e as { message?: string } | undefined)?.message || 'Could not load medicines'))
  }, [session])

  useLayoutEffect(() => {
    const el = listRef.current
    if (!el) return
    const ctx = gsap.context(() => {
      gsap.fromTo(el.querySelectorAll('[data-med-row]'), { y: 12, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5, stagger: 0.06 })
    }, el)
    return () => ctx.revert()
  }, [meds.length])

  const takenToday = useMemo(() => {
    const today = new Date().toISOString().slice(0, 10)
    const map: Record<string, boolean> = {}
    for (const log of logs) {
      const stamp = log.created_at || log.confirmed_time || ''
      if (!stamp.startsWith(today)) continue
      map[log.med_id] = log.status === 'taken'
    }
    return map
  }, [logs])

  const nextUp = useMemo(() => meds.find((med) => !takenToday[med.id]) ?? meds[0], [meds, takenToday])

  const mark = async (med: MedicineItem, status: 'taken' | 'missed') => {
    if (!session) return
    try {
      setBusyId(med.id)
      await confirmMedicine({
        med_id: med.id,
        user_id: session.user_id,
        status,
        scheduled_time: med.times?.[0],
      })
      await load()
    } catch (e: unknown) {
      setError((e as { message?: string } | undefined)?.message || 'Could not update medicine')
    } finally {
      setBusyId(null)
    }
  }

  if (!session) {
    return (
      <AppShell title="Medicines" subtitle="Login required." showNav={false}>
        <AuthPanel onReady={() => window.location.reload()} />
      </AppShell>
    )
  }

  return (
    <AppShell title="Medicines" subtitle="Live reminders, logs, and manual updates.">
      <Card className="overflow-hidden">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-lg font-extrabold tracking-tight text-ink">Next up</p>
            <p className="mt-1 text-sm text-ink/60">These medicines are now loaded from your profile.</p>
            {nextUp ? (
              <div className="mt-3 rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
                <p className="text-base font-bold text-ink">
                  {nextUp.name} <span className="font-semibold text-ink/60">- {nextUp.dose}</span>
                </p>
                <p className="mt-1 text-sm text-ink/60">
                  {(nextUp.times || []).join(', ')} - {nextUp.instructions || 'Take as directed'}
                </p>
              </div>
            ) : (
              <p className="mt-3 text-sm text-ink/60">No medicines added yet. You can add them from your data profile next.</p>
            )}
          </div>
          <div className="h-14 w-14 shrink-0">
            <PillSticker className="h-14 w-14" />
          </div>
        </div>
      </Card>

      {error ? (
        <Card>
          <p className="text-sm font-semibold text-danger">{error}</p>
        </Card>
      ) : null}

      <Card>
        <p className="text-lg font-extrabold tracking-tight text-ink">Today</p>
        <p className="mt-1 text-sm text-ink/60">Mark medicines as taken or missed manually.</p>

        <div ref={listRef} className="mt-3 space-y-2">
          {meds.map((med) => {
            const isTaken = Boolean(takenToday[med.id])
            return (
              <div key={med.id} data-med-row className={['rounded-2xl p-3 ring-1 ring-black/5 shadow-soft', isTaken ? 'bg-mint/15' : 'bg-white/65'].join(' ')}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-base font-extrabold tracking-tight text-ink">
                      {med.name} <span className="font-semibold text-ink/55">- {med.dose}</span>
                    </p>
                    <p className="mt-1 text-sm text-ink/60">
                      {(med.times || []).join(', ')} - {med.instructions || 'Take as directed'}
                    </p>
                    {med.condition ? <p className="mt-1 text-xs font-semibold tracking-wide text-ink/55">{med.condition}</p> : null}
                  </div>
                  <div className="grid gap-2">
                    <PressableButton variant="primary" size="md" onClick={() => void mark(med, 'taken')} disabled={busyId === med.id}>
                      {busyId === med.id ? 'Saving...' : isTaken ? 'Taken' : 'Mark Taken'}
                    </PressableButton>
                    <PressableButton variant="soft" size="md" onClick={() => void mark(med, 'missed')} disabled={busyId === med.id}>
                      Missed
                    </PressableButton>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </Card>

      <Card>
        <p className="text-lg font-extrabold tracking-tight text-ink">Recent medicine history</p>
        <div className="mt-3 space-y-2">
          {logs.slice(-8).reverse().map((log) => (
            <div key={log.id} className="rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
              <p className="text-sm font-extrabold text-ink">
                {log.medicine_name || log.med_id} - {log.status}
              </p>
              <p className="mt-1 text-sm text-ink/60">
                {(log.confirmed_time || log.created_at || '').replace('T', ' ').slice(0, 16)}
              </p>
            </div>
          ))}
          {!logs.length ? <p className="text-sm text-ink/60">No medicine history yet.</p> : null}
        </div>
      </Card>
    </AppShell>
  )
}
