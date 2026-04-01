import { useState } from 'react'
import { signIn, signUp, type AppSession, type SessionRole } from '../lib/api'
import { saveStoredSession } from '../lib/session'
import { Card } from './Card'
import { PressableButton } from './Pressable'
import { BellSticker, ElderSticker, FamilySticker, SparkleSticker } from './stickers'

type AuthMode = 'login' | 'signup'

async function requestAssistantPermissions() {
  try {
    if (navigator.mediaDevices?.getUserMedia) {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: true })
      stream.getTracks().forEach((track) => track.stop())
    }
  } catch {
    // permission can be retried later from the UI
  }
  try {
    if ('Notification' in window && Notification.permission === 'default') {
      await Notification.requestPermission()
    }
  } catch {
    // ignore notification prompt failures
  }
}

export function AuthPanel({
  preferredRole = 'support',
  onReady,
}: {
  preferredRole?: SessionRole
  onReady?: (session: AppSession) => void
}) {
  const [mode, setMode] = useState<AuthMode>('login')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const [name, setName] = useState('')
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [phone, setPhone] = useState('')
  const [relation, setRelation] = useState('')

  const submit = async () => {
    const trimmedName = name.trim()
    const trimmedIdentifier = identifier.trim()
    const trimmedPhone = phone.trim()
    const trimmedRelation = relation.trim()

    if (!trimmedIdentifier || !password.trim()) {
      setError('Email or parent user ID, plus password, are required')
      return
    }
    if (mode === 'signup') {
      if (!trimmedName) {
        setError('Family manager name is required')
        return
      }
      if (!trimmedIdentifier.includes('@')) {
        setError('Enter a valid email for the family manager login')
        return
      }
    }

    try {
      setBusy(true)
      setError('')
      const result =
        mode === 'login'
          ? await signIn({ identifier: trimmedIdentifier, password })
          : await signUp(
              {
                role: preferredRole,
                name: trimmedName,
                email: trimmedIdentifier,
                password,
                phone: trimmedPhone,
                relation: trimmedRelation,
              },
            )
      await requestAssistantPermissions()
      saveStoredSession(result.session)
      if (
        result.session.role === 'support' &&
        typeof window !== 'undefined' &&
        window.location.pathname.toLowerCase() !== '/support.html'
      ) {
        window.location.href = '/support.html'
        return
      }
      onReady?.(result.session)
    } catch (e: unknown) {
      setError((e as { message?: string } | undefined)?.message || 'Could not continue')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <div className="rounded-3xl bg-[linear-gradient(135deg,rgba(255,255,255,0.92),rgba(232,244,238,0.95))] p-4 shadow-soft ring-1 ring-black/5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.24em] text-ink/45">Bhumi Setup</p>
            <p className="mt-2 text-xl font-extrabold tracking-tight text-ink">Login or create your account</p>
            <p className="mt-2 max-w-xl text-sm text-ink/60">
              Child or family manager signs up first, then creates parent logins inside the Family Hub.
            </p>
          </div>
          <div className="flex items-end gap-2 self-start sm:self-auto">
            <div className="rounded-2xl bg-white/65 p-2 shadow-soft ring-1 ring-black/5">
              <FamilySticker className="h-14 w-14" tone="sky" />
            </div>
            <div className="rounded-2xl bg-white/65 p-2 shadow-soft ring-1 ring-black/5">
              <ElderSticker className="h-14 w-14" tone="mint" />
            </div>
            <div className="flex flex-col gap-2">
              <div className="rounded-2xl bg-white/65 p-2 shadow-soft ring-1 ring-black/5">
                <BellSticker className="h-10 w-10" />
              </div>
              <div className="rounded-2xl bg-white/65 p-2 shadow-soft ring-1 ring-black/5">
                <SparkleSticker className="h-10 w-10" />
              </div>
            </div>
          </div>
        </div>
        <div className="mt-3 grid grid-cols-1 gap-2 text-center sm:grid-cols-3">
          {['Create family login', 'Add parents with user IDs', 'Turn medicines into reminders'].map((step) => (
            <div
              key={step}
              className="rounded-2xl bg-white/75 px-3 py-2 text-xs font-semibold text-ink/65 shadow-soft ring-1 ring-black/5"
            >
              {step}
            </div>
          ))}
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <PressableButton variant={mode === 'login' ? 'primary' : 'soft'} onClick={() => setMode('login')}>
          Login
        </PressableButton>
        <PressableButton variant={mode === 'signup' ? 'primary' : 'soft'} onClick={() => setMode('signup')}>
          Sign up
        </PressableButton>
      </div>

      <div className="mt-3 space-y-2">
        {mode === 'signup' ? (
          <label className="block text-sm font-semibold text-ink/70">
            <span>Family manager name</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full rounded-xl2 border-0 bg-white/75 px-3 py-3 text-base shadow-soft ring-1 ring-black/5"
            />
          </label>
        ) : null}

        <label className="block text-sm font-semibold text-ink/70">
          <span>{mode === 'login' ? 'Email or parent user ID' : 'Email'}</span>
          <input
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            className="mt-1 w-full rounded-xl2 border-0 bg-white/75 px-3 py-3 text-base shadow-soft ring-1 ring-black/5"
          />
        </label>

        <label className="block text-sm font-semibold text-ink/70">
          <span>Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-xl2 border-0 bg-white/75 px-3 py-3 text-base shadow-soft ring-1 ring-black/5"
          />
        </label>

        {mode === 'signup' ? (
          <label className="block text-sm font-semibold text-ink/70">
            <span>Phone</span>
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="mt-1 w-full rounded-xl2 border-0 bg-white/75 px-3 py-3 text-base shadow-soft ring-1 ring-black/5"
            />
          </label>
        ) : null}

        {mode === 'signup' ? (
          <label className="block text-sm font-semibold text-ink/70">
            <span>Relation</span>
            <input
              value={relation}
              onChange={(e) => setRelation(e.target.value)}
              placeholder="Son, Daughter, Relative"
              className="mt-1 w-full rounded-xl2 border-0 bg-white/75 px-3 py-3 text-base shadow-soft ring-1 ring-black/5"
            />
          </label>
        ) : null}
      </div>

      {error ? <p className="mt-3 text-sm font-semibold text-danger">{error}</p> : null}

      <div className="mt-3">
        <PressableButton className="w-full" size="lg" variant="primary" onClick={submit} disabled={busy}>
          {busy ? 'Please wait...' : mode === 'login' ? 'Login' : 'Create family manager account'}
        </PressableButton>
      </div>
    </Card>
  )
}
