import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { gsap } from 'gsap'
import { AppShell } from '../ui/AppShell'
import { AuthPanel } from '../ui/AuthPanel'
import { Card } from '../ui/Card'
import { PressableButton } from '../ui/Pressable'
import { HeartPulseSticker } from '../ui/stickers'
import { callContact, getActivity, postVoice, sendSos, type ActivitySummary, type AppSession } from '../lib/api'
import { getStoredSession } from '../lib/session'
import { RppgCaptureCard } from '../ui/RppgCaptureCard'


export function AlertPage() {
  const [session] = useState<AppSession | null>(() => getStoredSession())
  const [armed, setArmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState('')
  const [activity, setActivity] = useState<ActivitySummary | null>(null)
  const buttonRef = useRef<HTMLButtonElement | null>(null)

  useEffect(() => {
    if (!session) return
    void getActivity(session.user_id).then(setActivity).catch(() => {})
  }, [session])

  useLayoutEffect(() => {
    const el = buttonRef.current
    if (!el) return
    const ctx = gsap.context(() => {
      if (armed) gsap.fromTo(el, { rotate: -1.2 }, { rotate: 1.2, duration: 0.08, repeat: 8, yoyo: true })
      else gsap.to(el, { rotate: 0, duration: 0.2 })
    }, el)
    return () => ctx.revert()
  }, [armed])

  const sendQuickVoice = async (text: string) => {
    if (!session) return
    try {
      setBusy(true)
      const res = await postVoice({ user_id: session.user_id, text })
      setResult(res.text)
    } catch (e: unknown) {
      setResult((e as { message?: string } | undefined)?.message || 'Could not reach the assistant')
    } finally {
      setBusy(false)
    }
  }

  const doCall = async () => {
    if (!session) return
    try {
      const res = await callContact({ user_id: session.user_id })
      if (res.mode === 'fallback') window.location.href = `tel:${res.target}`
      else setResult(`Calling ${res.label} now.`)
    } catch (e: unknown) {
      setResult((e as { message?: string } | undefined)?.message || 'Could not place a call')
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
    <AppShell title="Health" subtitle="Status, support, and emergency help in one place.">
      <Card>
        <p className="text-lg font-extrabold tracking-tight text-ink">Current status</p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <div className="rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
            <p className="text-xs font-bold tracking-wide text-ink/60">Mood</p>
            <p className="mt-1 text-xl font-extrabold tracking-tight text-ink">{activity?.mood || 'okay'}</p>
          </div>
          <div className="rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
            <p className="text-xs font-bold tracking-wide text-ink/60">Status</p>
            <p className="mt-1 text-xl font-extrabold tracking-tight text-ink">{activity?.status || 'steady'}</p>
          </div>
        </div>
      </Card>

      <RppgCaptureCard userId={session.user_id} onAnalyzed={() => getActivity(session.user_id).then(setActivity)} />

      <Card className="relative">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-lg font-extrabold tracking-tight text-ink">Need help?</p>
            <p className="mt-1 text-sm text-ink/60">This will alert your support circle and share your location if it is allowed in settings.</p>
          </div>
          <div className="h-14 w-14 shrink-0 animate-slowGlow">
            <HeartPulseSticker className="h-14 w-14" />
          </div>
        </div>

        <div className="mt-4 grid gap-2">
          <PressableButton
            ref={buttonRef}
            variant="danger"
            size="lg"
            className="py-5 text-xl"
            onClick={() => {
              setResult('')
              setArmed(true)
            }}
            disabled={busy}
          >
            SOS - Call for help
          </PressableButton>

          {armed ? (
            <div className="rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
              <p className="text-base font-extrabold text-ink">Confirm SOS?</p>
              <p className="mt-1 text-sm text-ink/60">We will do this quickly and gently.</p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <PressableButton
                  variant="primary"
                  size="lg"
                  onClick={() => {
                    ;(async () => {
                      try {
                        setBusy(true)
                        const loc =
                          'geolocation' in navigator
                            ? await new Promise<{ lat: number; lng: number } | undefined>((resolve) => {
                                navigator.geolocation.getCurrentPosition(
                                  (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude }),
                                  () => resolve(undefined),
                                  { enableHighAccuracy: false, timeout: 2000 },
                                )
                              })
                            : undefined
                        const res = await sendSos({ user_id: session.user_id, reason: 'SOS pressed', location: loc, severity: 90 })
                        const callRes = await callContact({ user_id: session.user_id })
                        if (callRes.mode === 'fallback') window.location.href = `tel:${callRes.target}`
                        setResult(`${res.message} (severity ${res.severity}). Calling ${callRes.label} too.`)
                        setArmed(false)
                      } catch (e: unknown) {
                        setResult((e as { message?: string } | undefined)?.message || 'SOS failed')
                      } finally {
                        setBusy(false)
                      }
                    })()
                  }}
                >
                  {busy ? 'Sending...' : 'Yes, send'}
                </PressableButton>
                <PressableButton variant="soft" size="lg" onClick={() => setArmed(false)}>
                  Cancel
                </PressableButton>
              </div>
            </div>
          ) : (
            <p className="text-sm text-ink/60">If it is not urgent, you can also use the calm help buttons below.</p>
          )}

          <div className="grid grid-cols-2 gap-2">
            <PressableButton variant="soft" onClick={() => void doCall()} disabled={busy}>
              Call support
            </PressableButton>
            <PressableButton variant="soft" onClick={() => (window.location.href = '/support.html')}>
              Open support page
            </PressableButton>
          </div>

          {result ? (
            <div className="rounded-2xl bg-mint/15 p-3 shadow-soft ring-1 ring-black/5">
              <p className="text-sm font-semibold text-ink">{result}</p>
            </div>
          ) : null}
        </div>
      </Card>

      <Card>
        <p className="text-lg font-extrabold tracking-tight text-ink">Quick calm steps</p>
        <div className="mt-3 grid gap-2">
          <PressableButton size="lg" variant="soft" onClick={() => void sendQuickVoice('I feel dizzy')}>
            I feel dizzy
          </PressableButton>
          <PressableButton size="lg" variant="soft" onClick={() => void sendQuickVoice('Chest feels uncomfortable')}>
            Chest feels uncomfortable
          </PressableButton>
          <PressableButton size="lg" variant="soft" onClick={() => void sendQuickVoice('I had a fall')}>
            I had a fall
          </PressableButton>
        </div>
      </Card>
    </AppShell>
  )
}
