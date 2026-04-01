import { useState } from 'react'
import { createSession, type AppSession, type SessionRole } from '../lib/api'
import { saveStoredSession } from '../lib/session'
import { Card } from './Card'
import { PressableButton } from './Pressable'

export function SessionSetupCard({
  initialRole = 'elder',
  onReady,
}: {
  initialRole?: SessionRole
  onReady?: (session: AppSession) => void
}) {
  const [role, setRole] = useState<SessionRole>(initialRole)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [name, setName] = useState(initialRole === 'support' ? 'Aniket' : 'Prajwal')
  const [language, setLanguage] = useState('Hindi')
  const [region, setRegion] = useState('Karnataka')
  const [city, setCity] = useState('Tumkur')
  const [userId, setUserId] = useState('demo')
  const [phone, setPhone] = useState('+91-9888888888')
  const [caretakerName, setCaretakerName] = useState('Kiran')
  const [caretakerPhone, setCaretakerPhone] = useState('+91-9999999999')

  const submit = async () => {
    try {
      setBusy(true)
      setError('')
      const session = await createSession(
        role === 'support'
          ? { role, name, user_id: userId }
          : {
              role,
              user_id: userId,
              name,
              language,
              region,
              city,
              phone,
              caretaker_name: caretakerName,
              caretaker_phone: caretakerPhone,
            },
      )
      saveStoredSession(session)
      onReady?.(session)
    } catch (e: unknown) {
      setError((e as { message?: string } | undefined)?.message || 'Could not start session')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <p className="text-lg font-extrabold tracking-tight text-ink">Start your session</p>
      <p className="mt-1 text-sm text-ink/60">Choose elder or support circle, then continue.</p>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <PressableButton variant={role === 'elder' ? 'primary' : 'soft'} onClick={() => setRole('elder')}>
          Elder
        </PressableButton>
        <PressableButton variant={role === 'support' ? 'primary' : 'soft'} onClick={() => setRole('support')}>
          Support Circle
        </PressableButton>
      </div>

      <div className="mt-3 space-y-2">
        <label className="block text-sm font-semibold text-ink/70">
          <span>Name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 w-full rounded-xl2 border-0 bg-white/75 px-3 py-3 text-base shadow-soft ring-1 ring-black/5"
          />
        </label>

        <label className="block text-sm font-semibold text-ink/70">
          <span>{role === 'support' ? 'Elder User ID' : 'User ID'}</span>
          <input
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            className="mt-1 w-full rounded-xl2 border-0 bg-white/75 px-3 py-3 text-base shadow-soft ring-1 ring-black/5"
          />
        </label>

        {role === 'elder' ? (
          <>
            <label className="block text-sm font-semibold text-ink/70">
              <span>Language</span>
              <input
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="mt-1 w-full rounded-xl2 border-0 bg-white/75 px-3 py-3 text-base shadow-soft ring-1 ring-black/5"
              />
            </label>
            <label className="block text-sm font-semibold text-ink/70">
              <span>Region</span>
              <input
                value={region}
                onChange={(e) => setRegion(e.target.value)}
                className="mt-1 w-full rounded-xl2 border-0 bg-white/75 px-3 py-3 text-base shadow-soft ring-1 ring-black/5"
              />
            </label>
            <label className="block text-sm font-semibold text-ink/70">
              <span>City</span>
              <input
                value={city}
                onChange={(e) => setCity(e.target.value)}
                className="mt-1 w-full rounded-xl2 border-0 bg-white/75 px-3 py-3 text-base shadow-soft ring-1 ring-black/5"
              />
            </label>
            <label className="block text-sm font-semibold text-ink/70">
              <span>Phone</span>
              <input
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="mt-1 w-full rounded-xl2 border-0 bg-white/75 px-3 py-3 text-base shadow-soft ring-1 ring-black/5"
              />
            </label>
            <label className="block text-sm font-semibold text-ink/70">
              <span>Primary Support Name</span>
              <input
                value={caretakerName}
                onChange={(e) => setCaretakerName(e.target.value)}
                className="mt-1 w-full rounded-xl2 border-0 bg-white/75 px-3 py-3 text-base shadow-soft ring-1 ring-black/5"
              />
            </label>
            <label className="block text-sm font-semibold text-ink/70">
              <span>Primary Support Phone</span>
              <input
                value={caretakerPhone}
                onChange={(e) => setCaretakerPhone(e.target.value)}
                className="mt-1 w-full rounded-xl2 border-0 bg-white/75 px-3 py-3 text-base shadow-soft ring-1 ring-black/5"
              />
            </label>
          </>
        ) : null}
      </div>

      {error ? <p className="mt-3 text-sm font-semibold text-danger">{error}</p> : null}

      <div className="mt-3">
        <PressableButton className="w-full" size="lg" variant="primary" onClick={submit} disabled={busy}>
          {busy ? 'Starting...' : 'Continue'}
        </PressableButton>
      </div>
    </Card>
  )
}
