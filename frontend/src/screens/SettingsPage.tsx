import { useEffect, useMemo, useState } from 'react'
import { AppShell } from '../ui/AppShell'
import { AuthPanel } from '../ui/AuthPanel'
import { Card } from '../ui/Card'
import { PressableButton } from '../ui/Pressable'
import { clearConversationHistory, clearMemories, createAlarm, deleteAlarm, deleteConversationDay, deleteConversationItem, getAlarms, getConversationHistory, getUserProfile, updateUserProfile, type AlarmItem, type AppSession, type ConversationItem, type UserProfile } from '../lib/api'
import { regionalLanguages } from '../lib/regionalLanguages'
import { clearStoredSession, getStoredSession } from '../lib/session'

function familyContactsText(profile: UserProfile | null) {
  return (profile?.family_contacts || [])
    .map((item) => [item.name || '', item.relation || item.role || '', item.phone || ''].join(' | '))
    .join('\n')
}

function parseFamilyContacts(value: string): NonNullable<UserProfile['family_contacts']> {
  return value
    .split('\n')
    .map((line, index) => {
      const [name, relation, phone] = line.split('|').map((item) => item.trim())
      if (!name && !phone) return null
      return {
        id: `family-${index + 1}`,
        name: name || relation || `Family ${index + 1}`,
        relation: relation || 'family',
        role: relation || 'family',
        phone: phone || '',
      }
    })
    .filter(Boolean) as NonNullable<UserProfile['family_contacts']>
}

type Section = 'profile' | 'assistant' | 'alarms' | 'history' | null

export function SettingsPage() {
  const [session] = useState<AppSession | null>(() => getStoredSession())
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [history, setHistory] = useState<ConversationItem[]>([])
  const [saving, setSaving] = useState(false)
  const [historyBusy, setHistoryBusy] = useState('')
  const [locationBusy, setLocationBusy] = useState(false)
  const [alarms, setAlarms] = useState<AlarmItem[]>([])
  const [alarmTitle, setAlarmTitle] = useState('Alarm')
  const [alarmTime, setAlarmTime] = useState('')
  const [openSection, setOpenSection] = useState<Section>(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const toggle = (s: Section) => setOpenSection((prev) => (prev === s ? null : s))

  const load = async () => {
    if (!session) return
    const [user, items, alarmItems] = await Promise.all([getUserProfile(session.user_id), getConversationHistory(session.user_id, 20), getAlarms(session.user_id)])
    setProfile(user)
    setHistory(items)
    setAlarms(alarmItems)
  }

  useEffect(() => {
    if (!session) return
    void load().catch((e: unknown) => setError((e as { message?: string } | undefined)?.message || 'Could not load settings'))
  }, [session])

  const historyGroups = useMemo(() => {
    const groups = new Map<string, ConversationItem[]>()
    for (const item of history) {
      const key = String(item.ts || '').slice(0, 10) || 'Unknown day'
      const bucket = groups.get(key) || []
      bucket.push(item)
      groups.set(key, bucket)
    }
    return Array.from(groups.entries())
      .sort((a, b) => b[0].localeCompare(a[0]))
      .map(([day, items]) => ({ day, items: items.slice().sort((a, b) => String(b.ts).localeCompare(String(a.ts))) }))
  }, [history])

  const removeItem = async (itemId: string) => {
    if (!session) return
    try {
      setHistoryBusy(itemId)
      await deleteConversationItem(session.user_id, itemId)
      await load()
    } finally {
      setHistoryBusy('')
    }
  }

  const removeDay = async (dayKey: string) => {
    if (!session) return
    try {
      setHistoryBusy(dayKey)
      await deleteConversationDay(session.user_id, dayKey)
      await load()
    } finally {
      setHistoryBusy('')
    }
  }

  const fetchCurrentLocation = async () => {
    if (!navigator.geolocation) { setError('Geolocation not available'); return }
    try {
      setLocationBusy(true); setError('')
      const coords = await new Promise<{ lat: number; lon: number }>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(
          (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }), reject, { enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 })
      })
      setProfile((c) => (c ? { ...c, lat: coords.lat, lon: coords.lon } : c))
      setMessage('Location fetched. Save to keep it.')
    } catch { setError('Could not fetch location') }
    finally { setLocationBusy(false) }
  }

  const save = async () => {
    if (!session || !profile) return
    try {
      setSaving(true); setError(''); setMessage('')
      const user = await updateUserProfile(session.user_id, profile)
      setProfile(user)
      setMessage('Saved.')
    } catch (e: unknown) {
      setError((e as { message?: string } | undefined)?.message || 'Could not save')
    } finally { setSaving(false) }
  }

  const addManualAlarm = async () => {
    if (!session || !alarmTime) return
    try {
      const now = new Date()
      const [h, m] = alarmTime.split(':').map(Number)
      if (Number.isNaN(h) || Number.isNaN(m)) { setError('Invalid time'); return }
      const when = new Date(now); when.setSeconds(0, 0); when.setHours(h, m, 0, 0)
      if (when.getTime() <= now.getTime()) when.setDate(when.getDate() + 1)
      await createAlarm(session.user_id, { title: alarmTitle || 'Alarm', time_iso: when.toISOString(), label: alarmTitle || 'Alarm', source: 'manual' })
      setAlarmTime(''); setAlarmTitle('Alarm'); setMessage('Alarm added.')
      await load()
    } catch (e: unknown) { setError((e as { message?: string } | undefined)?.message || 'Could not add alarm') }
  }

  if (!session) {
    return (
      <AppShell title="Settings" subtitle="Login required." showNav={false}>
        <AuthPanel onReady={() => window.location.reload()} />
      </AppShell>
    )
  }

  return (
    <AppShell title="Settings" subtitle="Account and preferences.">
      {/* Account card — always visible, compact */}
      <Card>
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-lg font-extrabold tracking-tight text-ink">{profile?.name || session.display_name || 'Account'}</p>
            <p className="text-sm text-ink/60">{session.email || 'Signed in'} · {session.role === 'support' ? 'Family manager' : 'Elder'}</p>
          </div>
          <PressableButton variant="soft" size="md" onClick={() => { clearStoredSession(); window.location.reload() }}>
            Sign out
          </PressableButton>
        </div>
      </Card>

      {error ? <Card><p className="text-sm font-semibold text-danger">{error}</p></Card> : null}
      {message ? <Card><p className="text-sm font-semibold text-ink/70">{message}</p></Card> : null}

      {/* Collapsible: Profile & Support Circle */}
      <Card>
        <button onClick={() => toggle('profile')} className="flex w-full items-center justify-between text-left">
          <p className="text-lg font-extrabold tracking-tight text-ink">Profile &amp; support circle</p>
          <span className="text-xl text-ink/40">{openSection === 'profile' ? '−' : '+'}</span>
        </button>
        {openSection === 'profile' && (
          <div className="mt-3 space-y-2">
            {[
              ['Name', 'name'], ['Region', 'region'], ['City', 'city'],
              ['Phone', 'phone'], ['Wake time', 'wake_time'], ['Sleep time', 'sleep_time'],
              ['Support name', 'caretaker_name'], ['Support phone', 'caretaker_phone'],
            ].map(([label, key]) => (
              <label key={key} className="block text-sm font-semibold text-ink/70">
                <span>{label}</span>
                <input
                  value={String((profile as Record<string, unknown> | null)?.[key] || '')}
                  onChange={(e) => setProfile((c) => (c ? { ...c, [key]: e.target.value } : c))}
                  className="mt-1 w-full rounded-xl2 border-0 bg-white/75 px-3 py-2.5 text-base shadow-soft ring-1 ring-black/5"
                />
              </label>
            ))}
            <label className="block text-sm font-semibold text-ink/70">
              <span>Language</span>
              <select
                value={profile?.language || 'English'}
                onChange={(e) => setProfile((c) => (c ? { ...c, language: e.target.value } : c))}
                className="mt-1 w-full rounded-xl2 border-0 bg-white/75 px-3 py-2.5 text-base shadow-soft ring-1 ring-black/5"
              >
                {regionalLanguages.map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            </label>
            <div className="rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm text-ink/60">
                  {profile?.lat != null && profile?.lon != null ? `Location: ${profile.lat.toFixed(4)}, ${profile.lon.toFixed(4)}` : 'No location saved'}
                </p>
                <PressableButton variant="soft" size="md" onClick={() => void fetchCurrentLocation()} disabled={locationBusy}>
                  {locationBusy ? '...' : 'Update'}
                </PressableButton>
              </div>
            </div>
            <p className="text-sm font-semibold text-ink/70 mt-2">Support circle (name | relation | phone per line)</p>
            <textarea
              rows={3}
              value={familyContactsText(profile)}
              onChange={(e) => setProfile((c) => c ? { ...c, family_contacts: parseFamilyContacts(e.target.value) } : c)}
              placeholder={'Kiran | son | +91-9999999999'}
              className="w-full rounded-xl2 border-0 bg-white/75 px-3 py-2.5 text-base shadow-soft ring-1 ring-black/5"
            />
            <PressableButton variant="primary" size="lg" onClick={() => void save()} disabled={saving}>
              {saving ? 'Saving...' : 'Save'}
            </PressableButton>
          </div>
        )}
      </Card>

      {/* Collapsible: Assistant settings */}
      <Card>
        <button onClick={() => toggle('assistant')} className="flex w-full items-center justify-between text-left">
          <p className="text-lg font-extrabold tracking-tight text-ink">Assistant &amp; permissions</p>
          <span className="text-xl text-ink/40">{openSection === 'assistant' ? '−' : '+'}</span>
        </button>
        {openSection === 'assistant' && (
          <div className="mt-3 space-y-2">
            {[
              ['History enabled', 'history_enabled'],
              ['Location enabled', 'location_enabled'],
              ['Wake word enabled', 'wake_word_enabled'],
              ['Auto send on pause', 'auto_send_on_pause'],
            ].map(([label, key]) => (
              <label key={key} className="flex items-center justify-between rounded-2xl bg-white/70 px-3 py-2.5 shadow-soft ring-1 ring-black/5">
                <span className="text-sm font-semibold text-ink/70">{label}</span>
                <input
                  type="checkbox"
                  checked={Boolean(profile?.settings?.[key as keyof NonNullable<UserProfile['settings']>])}
                  onChange={(e) =>
                    setProfile((c) => c ? { ...c, settings: { ...c.settings, [key]: e.target.checked } } : c)
                  }
                />
              </label>
            ))}
            <label className="block text-sm font-semibold text-ink/70">
              <span>Wake words</span>
              <input
                value={(profile?.settings?.wake_words || []).join(', ')}
                onChange={(e) => setProfile((c) => c ? { ...c, settings: { ...c.settings, wake_words: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) } } : c)}
                className="mt-1 w-full rounded-xl2 border-0 bg-white/75 px-3 py-2.5 text-base shadow-soft ring-1 ring-black/5"
              />
            </label>
            <PressableButton variant="primary" size="lg" onClick={() => void save()} disabled={saving}>
              {saving ? 'Saving...' : 'Save'}
            </PressableButton>
          </div>
        )}
      </Card>

      {/* Collapsible: Alarms */}
      <Card>
        <button onClick={() => toggle('alarms')} className="flex w-full items-center justify-between text-left">
          <p className="text-lg font-extrabold tracking-tight text-ink">Alarms ({alarms.length})</p>
          <span className="text-xl text-ink/40">{openSection === 'alarms' ? '−' : '+'}</span>
        </button>
        {openSection === 'alarms' && (
          <div className="mt-3 space-y-2">
            <div className="grid gap-2 sm:grid-cols-[1fr,120px,auto]">
              <input value={alarmTitle} onChange={(e) => setAlarmTitle(e.target.value)} placeholder="Label" className="rounded-xl2 border-0 bg-white/75 px-3 py-2.5 text-base shadow-soft ring-1 ring-black/5" />
              <input type="time" value={alarmTime} onChange={(e) => setAlarmTime(e.target.value)} className="rounded-xl2 border-0 bg-white/75 px-3 py-2.5 text-base shadow-soft ring-1 ring-black/5" />
              <PressableButton variant="primary" size="lg" onClick={() => void addManualAlarm()}>Add</PressableButton>
            </div>
            {alarms.map((a) => (
              <div key={a.id} className="flex items-center justify-between gap-3 rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
                <div>
                  <p className="text-sm font-extrabold text-ink">{a.title}</p>
                  <p className="text-xs text-ink/60">{new Date(a.time_iso).toLocaleString()}</p>
                </div>
                <PressableButton variant="soft" size="md" onClick={() => session && void deleteAlarm(session.user_id, a.id).then(() => load())}>Del</PressableButton>
              </div>
            ))}
            {!alarms.length ? <p className="text-sm text-ink/60">No alarms yet.</p> : null}
          </div>
        )}
      </Card>

      {/* Collapsible: Chat history */}
      <Card>
        <button onClick={() => toggle('history')} className="flex w-full items-center justify-between text-left">
          <p className="text-lg font-extrabold tracking-tight text-ink">Chat history ({history.length})</p>
          <span className="text-xl text-ink/40">{openSection === 'history' ? '−' : '+'}</span>
        </button>
        {openSection === 'history' && (
          <div className="mt-3 space-y-2">
            <div className="grid gap-2 grid-cols-2">
              <PressableButton variant="soft" onClick={() => { if (session) void clearConversationHistory(session.user_id).then(() => load()) }}>
                Clear chats
              </PressableButton>
              <PressableButton variant="soft" onClick={() => { if (session) void clearMemories(session.user_id).then(() => load()) }}>
                Clear memories
              </PressableButton>
            </div>
            {historyGroups.map((g) => (
              <div key={g.day} className="rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-extrabold text-ink">{g.day} <span className="font-normal text-ink/55">({g.items.length})</span></p>
                  <PressableButton variant="soft" size="md" onClick={() => void removeDay(g.day)} disabled={historyBusy === g.day}>
                    {historyBusy === g.day ? '...' : 'Delete'}
                  </PressableButton>
                </div>
                <div className="mt-2 space-y-1">
                  {g.items.slice(0, 5).map((item) => (
                    <div key={item.id} className="flex items-start justify-between gap-2 rounded-xl bg-white/80 p-2 ring-1 ring-black/5">
                      <div className="min-w-0 text-xs">
                        <p className="text-ink/70"><span className="font-bold">You:</span> {item.text_input}</p>
                        <p className="mt-0.5 font-semibold text-ink">{item.ai_response}</p>
                      </div>
                      <button onClick={() => void removeItem(item.id)} disabled={historyBusy === item.id} className="shrink-0 text-xs text-ink/40 hover:text-danger">
                        {historyBusy === item.id ? '...' : 'x'}
                      </button>
                    </div>
                  ))}
                  {g.items.length > 5 ? <p className="text-xs text-ink/50">+{g.items.length - 5} more</p> : null}
                </div>
              </div>
            ))}
            {!historyGroups.length ? <p className="text-sm text-ink/60">No history yet.</p> : null}
          </div>
        )}
      </Card>
    </AppShell>
  )
}
