import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { gsap } from 'gsap'
import { AppShell } from '../ui/AppShell'
import { AuthPanel } from '../ui/AuthPanel'
import { Card } from '../ui/Card'
import { PressableButton } from '../ui/Pressable'
import { SparkleSticker } from '../ui/stickers'
import { getWeeklyReport, generatePdfReport, type AppSession, type WeeklyReport } from '../lib/api'
import { getStoredSession } from '../lib/session'


export function SummaryPage() {
  const [session] = useState<AppSession | null>(() => getStoredSession())
  const [loading, setLoading] = useState(true)
  const [report, setReport] = useState<WeeklyReport | null>(null)
  const [error, setError] = useState('')
  const [pdfBusy, setPdfBusy] = useState(false)
  const [pdfUrl, setPdfUrl] = useState('')
  const barsRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!session) return
    ;(async () => {
      try {
        setLoading(true)
        setError('')
        setReport(await getWeeklyReport(session.user_id))
      } catch (e: unknown) {
        setError((e as { message?: string } | undefined)?.message || 'Failed to load report')
      } finally {
        setLoading(false)
      }
    })()
  }, [session])

  useLayoutEffect(() => {
    const el = barsRef.current
    if (!el || loading) return
    const ctx = gsap.context(() => {
      gsap.fromTo(el.querySelectorAll('[data-bar]'), { scaleY: 0.3, opacity: 0.2 }, { scaleY: 1, opacity: 1, duration: 0.7, stagger: 0.05, ease: 'elastic.out(1,0.6)' })
    }, el)
    return () => ctx.revert()
  }, [loading, report?.mood_trend])

  if (!session) {
    return (
      <AppShell title="Weekly" subtitle="Login required." showNav={false}>
        <AuthPanel onReady={() => window.location.reload()} />
      </AppShell>
    )
  }

  return (
    <AppShell title="Weekly" subtitle="A live summary based on history, mood, medicine, and alerts.">
      <Card>
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-lg font-extrabold tracking-tight text-ink">
              Week of {report?.week_start || '--'} to {report?.week_end || '--'}
            </p>
            <p className="mt-1 text-sm text-ink/60">This view is now driven by stored conversations and medicine logs.</p>
          </div>
          <div className="h-14 w-14 shrink-0">
            <SparkleSticker className="h-14 w-14" />
          </div>
        </div>

        <div className="mt-4 rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
          <p className="text-sm font-bold text-ink/70">Mood trend</p>
          {loading ? (
            <div className="mt-3 grid grid-cols-7 gap-2">
              {Array.from({ length: 7 }).map((_, i) => (
                <div key={i} className="h-16 rounded-xl2 bg-ink/5 animate-pulse" />
              ))}
            </div>
          ) : error ? (
            <p className="mt-3 text-sm font-semibold text-danger">{error}</p>
          ) : (
            <div ref={barsRef} className="mt-3 grid grid-cols-7 items-end gap-2">
              {(report?.mood_trend || []).map((value, i) => (
                <div
                  key={i}
                  data-bar
                  style={{ height: `${Math.max(26, value)}px` }}
                  className={['origin-bottom rounded-xl2 shadow-soft ring-1 ring-black/5', i === 6 ? 'bg-mint/35' : 'bg-sky/28'].join(' ')}
                  aria-hidden="true"
                />
              ))}
            </div>
          )}
        </div>
      </Card>

      <Card>
        <p className="text-lg font-extrabold tracking-tight text-ink">Highlights</p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <div className="rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
            <p className="text-xs font-bold tracking-wide text-ink/60">Medicines</p>
            <p className="mt-1 text-2xl font-extrabold tracking-tight text-ink">{report?.medicine_adherence ?? 0}%</p>
          </div>
          <div className="rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
            <p className="text-xs font-bold tracking-wide text-ink/60">Activity</p>
            <p className="mt-1 text-2xl font-extrabold tracking-tight text-ink">
              {report?.activity_steps_per_day ? `${Math.round(report.activity_steps_per_day / 100) / 10}k` : '0k'}
            </p>
          </div>
          <div className="rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
            <p className="text-xs font-bold tracking-wide text-ink/60">Sleep</p>
            <p className="mt-1 text-2xl font-extrabold tracking-tight text-ink">{report?.sleep_hours ?? 0}h</p>
          </div>
          <div className="rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
            <p className="text-xs font-bold tracking-wide text-ink/60">Alerts</p>
            <p className="mt-1 text-2xl font-extrabold tracking-tight text-ink">{report?.alert_count ?? 0}</p>
          </div>
        </div>
      </Card>

      <Card>
        <p className="text-lg font-extrabold tracking-tight text-ink">Health issues noticed</p>
        <div className="mt-3 grid gap-2">
          {(report?.health_issues || []).length ? (
            (report?.health_issues || []).map((issue) => (
              <PressableButton key={issue} size="lg" variant="soft">
                {issue}
              </PressableButton>
            ))
          ) : (
            <p className="text-sm text-ink/60">No major issues were captured this week.</p>
          )}
        </div>
      </Card>

      <Card>
        <p className="text-lg font-extrabold tracking-tight text-ink">Gentle suggestions</p>
        <div className="mt-3 grid gap-2">
          {(report?.recommendations || []).map((item) => (
            <PressableButton key={item} size="lg" variant="soft">
              {item}
            </PressableButton>
          ))}
        </div>
      </Card>

      <Card>
        <p className="text-lg font-extrabold tracking-tight text-ink">Wellness report</p>
        <p className="mt-1 text-sm text-ink/60">Generate a PDF wellness report to share with family or doctor.</p>
        <div className="mt-3 grid gap-2">
          <PressableButton
            size="lg"
            variant="primary"
            disabled={pdfBusy}
            onClick={() => {
              if (!session) return
              ;(async () => {
                try {
                  setPdfBusy(true)
                  setPdfUrl('')
                  const res = await generatePdfReport(session.user_id)
                  setPdfUrl(res.pdf_url)
                } catch (e: unknown) {
                  setError((e as { message?: string } | undefined)?.message || 'Could not generate report')
                } finally {
                  setPdfBusy(false)
                }
              })()
            }}
          >
            {pdfBusy ? 'Generating report...' : 'Generate PDF report'}
          </PressableButton>
          {pdfUrl && (
            <a href={pdfUrl} target="_blank" rel="noopener noreferrer">
              <PressableButton size="lg" variant="soft">
                Open PDF report
              </PressableButton>
            </a>
          )}
        </div>
      </Card>
    </AppShell>
  )
}
