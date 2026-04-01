import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { gsap } from 'gsap'
import { AppShell } from '../ui/AppShell'
import { AuthPanel } from '../ui/AuthPanel'
import { Card } from '../ui/Card'
import { MicButton } from '../ui/MicButton'
import { PressableButton } from '../ui/Pressable'
import { ElderSticker, SparkleSticker } from '../ui/stickers'
import { includesWakeWord, parseAlarmTime, runAssistantPlugin, stripWakeWords } from '../lib/assistantPlugins'
import { addConversationHistory, createAlarm, deleteAlarm, getAlarms, getConversationHistory, getUserProfile, postVoice, postVoiceAudio, sendSos, callContact, updateActivityStatus, type AlarmItem, type AppSession, type ConversationItem, type UserProfile } from '../lib/api'
import { notify, playAlarmTone } from '../lib/notifications'
import { listenOnce, playAudioUrl, speak, stopSpeaking } from '../lib/speech'
import { clearStoredSession, getStoredSession } from '../lib/session'


function browserLang(profile: UserProfile | null) {
  const language = (profile?.language || 'English').toLowerCase()
  if (language.includes('hindi')) return 'hi-IN'
  if (language.includes('kannada')) return 'kn-IN'
  if (language.includes('tamil')) return 'ta-IN'
  if (language.includes('telugu')) return 'te-IN'
  if (language.includes('gujarati')) return 'gu-IN'
  if (language.includes('marathi')) return 'mr-IN'
  return 'en-IN'
}

function responseSpeechLang(
  response: { response_speech_lang?: string; response_language_code?: string },
  profile: UserProfile | null,
) {
  if (response.response_speech_lang) return response.response_speech_lang
  if (response.response_language_code === 'hi') return 'hi-IN'
  if (response.response_language_code === 'kn') return 'kn-IN'
  if (response.response_language_code === 'ta') return 'ta-IN'
  if (response.response_language_code === 'te') return 'te-IN'
  if (response.response_language_code === 'gu') return 'gu-IN'
  if (response.response_language_code === 'mr') return 'mr-IN'
  return browserLang(profile)
}

function isHindiLike(text: string) {
  return /[\u0900-\u097F]/.test(text) || /\b(kya|haan|ji|paani|dard|madad|sunao|baje|acha|thoda)\b/i.test(text)
}

function localActionText(text: string, english: string, hindi: string) {
  return isHindiLike(text) ? hindi : english
}

function normalizeTypedWakeCommand(text: string, wakeWords: string[]) {
  const trimmed = text.trim()
  if (!trimmed) return ''
  if (!includesWakeWord(trimmed, wakeWords)) return trimmed
  return stripWakeWords(trimmed, wakeWords)
}

export function HomePage() {
  const [session, setSession] = useState<AppSession | null>(() => getStoredSession())
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [history, setHistory] = useState<ConversationItem[]>([])
  const [speaking, setSpeaking] = useState(false)
  const [busy, setBusy] = useState(false)
  const [wakeBusy, setWakeBusy] = useState(false)
  const [lastUser, setLastUser] = useState('')
  const [lastBot, setLastBot] = useState('')
  const [lastEmotion, setLastEmotion] = useState('')
  const [input, setInput] = useState('')
  const [error, setError] = useState('')
  const [alarms, setAlarms] = useState<AlarmItem[]>([])
  const [pendingAlarmPrompt, setPendingAlarmPrompt] = useState<string | null>(null)
  const [handsFree, setHandsFree] = useState(false)
  const stickerRef = useRef<HTMLDivElement | null>(null)
  const firedRef = useRef<Set<string>>(new Set())

  const greeting = useMemo(() => {
    const h = new Date().getHours()
    if (h < 12) return 'Good morning'
    if (h < 18) return 'Good afternoon'
    return 'Good evening'
  }, [])

  const wakeWords = profile?.settings?.wake_words?.length
    ? profile.settings.wake_words
    : ['bhumi', 'hey bhumi', 'hi bhumi', 'hello bhumi']

  const load = async (activeSession: AppSession) => {
    if (!activeSession.user_id) {
      setProfile(null)
      setHistory([])
      setAlarms([])
      return
    }
    const [user, items, alarmItems] = await Promise.all([
      getUserProfile(activeSession.user_id),
      getConversationHistory(activeSession.user_id, 20),
      getAlarms(activeSession.user_id),
    ])
    setProfile(user)
    setHistory(items)
    setAlarms(alarmItems)
  }

  useEffect(() => {
    if (!session) return
    if (session.role !== 'elder') return
    void load(session).catch((e: unknown) => {
      setError((e as { message?: string } | undefined)?.message || 'Could not load your session')
    })
  }, [session])

  useEffect(() => {
    if (session?.role === 'elder' && profile?.settings?.wake_word_enabled !== false) {
      setHandsFree(true)
    }
  }, [profile?.settings?.wake_word_enabled, session?.role])

  useEffect(() => {
    if (session?.role === 'support' && document.body.dataset.page === 'home') {
      window.location.replace('/support.html')
    }
  }, [session])

  useEffect(() => {
    if (!session || session.role !== 'elder') return
    const refreshTimer = window.setInterval(() => {
      void getAlarms(session.user_id)
        .then((items) => setAlarms(items))
        .catch(() => {})
    }, 12000)
    return () => window.clearInterval(refreshTimer)
  }, [session])

  useEffect(() => {
    if (!session || !alarms.length) return
    const timer = window.setInterval(() => {
      const now = Date.now()
      for (const alarm of alarms) {
        const when = new Date(alarm.time_iso).getTime()
        if (Number.isNaN(when)) continue
        if (when <= now && !firedRef.current.has(alarm.id)) {
          firedRef.current.add(alarm.id)
          void notify(alarm.title || 'Alarm', {
            body: alarm.label || 'It is time now.',
          })
          void playAlarmTone()
          speak(alarm.label || alarm.title || 'Alarm', { lang: browserLang(profile) })
          void deleteAlarm(session.user_id, alarm.id)
            .then(() => load(session))
            .catch(() => {})
        }
      }
    }, 15000)
    return () => window.clearInterval(timer)
  }, [alarms, profile, session])

  useEffect(() => {
    if (!session || session.role !== 'elder' || !handsFree || profile?.settings?.wake_word_enabled === false) return
    let cancelled = false
    const loop = async () => {
      while (!cancelled) {
        try {
          const heard = await listenOnce({ lang: browserLang(profile), timeoutMs: 12000 })
          if (cancelled) return
          if (!includesWakeWord(heard.transcript, wakeWords)) continue
          let command = stripWakeWords(heard.transcript, wakeWords)
          if (!command && profile?.settings?.auto_send_on_pause !== false) {
            const followUp = await listenOnce({ lang: browserLang(profile), timeoutMs: 9000 })
            if (cancelled) return
            command = followUp.transcript.trim()
          }
          if (command.trim()) await sendAssistantMessage(command)
        } catch {
          // keep the passive listener alive
        }
      }
    }
    void loop()
    return () => {
      cancelled = true
    }
  }, [handsFree, profile, session, wakeWords.join('|')])

  useLayoutEffect(() => {
    const el = stickerRef.current
    if (!el) return
    const ctx = gsap.context(() => {
      gsap.fromTo(el, { rotate: -2, y: 6, opacity: 0 }, { rotate: 0, y: 0, opacity: 1, duration: 0.6 })
    }, el)
    return () => ctx.revert()
  }, [])

  useLayoutEffect(() => {
    const el = stickerRef.current
    if (!el) return
    const ctx = gsap.context(() => {
      if (speaking || wakeBusy) gsap.to(el, { rotate: 2, duration: 0.4, yoyo: true, repeat: 5, ease: 'sine.inOut' })
      else gsap.to(el, { rotate: 0, duration: 0.2 })
    }, el)
    return () => ctx.revert()
  }, [speaking, wakeBusy])

  const getGeoOnce = async (): Promise<{ lat: number; lon: number } | null> => {
    if (!profile?.settings?.location_enabled) return null
    if (!('geolocation' in navigator)) return null
    return await new Promise((resolve) => {
      navigator.geolocation.getCurrentPosition(
        (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
        () => resolve(null),
        { enableHighAccuracy: false, timeout: 6000, maximumAge: 5 * 60_000 },
      )
    })
  }

  const recordOnce = async (maxMs = 9000): Promise<Blob> => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    return await new Promise((resolve, reject) => {
      const chunks: BlobPart[] = []
      const rec = new MediaRecorder(stream)
      
      const AudioContextCtor = window.AudioContext || (window as any).webkitAudioContext
      let rafId: number
      let audioCtx: AudioContext | null = null
      
      if (AudioContextCtor) {
        audioCtx = new AudioContextCtor()
        const source = audioCtx.createMediaStreamSource(stream)
        const analyser = audioCtx.createAnalyser()
        analyser.minDecibels = -55
        analyser.fftSize = 256
        source.connect(analyser)
        
        const dataArray = new Uint8Array(analyser.frequencyBinCount)
        let silenceStart = Date.now()
        let hasSpoken = false
        
        const checkAudio = () => {
          analyser.getByteFrequencyData(dataArray)
          let sum = 0
          for (let i = 0; i < dataArray.length; i++) sum += dataArray[i]
          const avg = sum / dataArray.length
          
          if (avg > 15) {
            hasSpoken = true
            silenceStart = Date.now()
          } else if (hasSpoken && Date.now() - silenceStart > 1200) {
            try { rec.stop() } catch {}
            return
          }
          rafId = requestAnimationFrame(checkAudio)
        }
        checkAudio()
      }

      rec.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunks.push(e.data)
      }
      rec.onerror = () => {
        if (rafId) cancelAnimationFrame(rafId)
        if (audioCtx) void audioCtx.close()
        reject(new Error('Audio recording failed'))
      }
      rec.onstop = () => {
        if (rafId) cancelAnimationFrame(rafId)
        if (audioCtx) void audioCtx.close()
        for (const track of stream.getTracks()) track.stop()
        resolve(new Blob(chunks, { type: 'audio/webm' }))
      }
      
      rec.start()
      window.setTimeout(() => {
        try { rec.stop() } catch {}
      }, maxMs)
    })
  }

  const afterReply = async (text: string) => {
    if (!session) return
    const items = await getConversationHistory(session.user_id, 20)
    setHistory(items)
    setInput('')
    if (text) setLastBot(text)
  }

  const saveLocalHistory = async (userText: string, botText: string) => {
    if (!session) return
    await addConversationHistory(session.user_id, {
      ts: new Date().toISOString(),
      text_input: userText,
      ai_response: botText,
      mood: 'okay',
      emotion: lastEmotion || 'supportive',
      source: 'local_action',
    })
    await afterReply(botText)
  }

  const sendAssistantMessage = async (message: string, audioBlob?: Blob, options?: { skipPlugin?: boolean }) => {
    if (!session) return
    const rawText = message.trim()
    const commandText = options?.skipPlugin ? rawText : normalizeTypedWakeCommand(rawText, wakeWords)

    if (!options?.skipPlugin && rawText && includesWakeWord(rawText, wakeWords) && !commandText) {
      const wakeReply = localActionText(rawText, 'Yes? Tell me what you need.', 'Haan ji, bataiye kya chahiye?')
      setLastUser(rawText)
      setLastBot(wakeReply)
      speak(wakeReply, { lang: browserLang(profile) })
      await saveLocalHistory(rawText, wakeReply)
      return
    }

    if (!commandText && !audioBlob) return

    if (pendingAlarmPrompt && commandText) {
      const parsedFollowUp = parseAlarmTime(commandText)
      if (parsedFollowUp) {
        speak(localActionText(commandText, 'Setting your alarm now.', 'Abhi aapka alarm set kar raha hoon.'), { lang: browserLang(profile) })
        const alarm = await createAlarm(session.user_id, {
          title: 'Alarm',
          time_iso: parsedFollowUp.timeIso,
          label: pendingAlarmPrompt,
          source: 'voice_follow_up',
        })
        setPendingAlarmPrompt(null)
        setAlarms((current) => [...current, alarm].sort((a, b) => a.time_iso.localeCompare(b.time_iso)))
        setLastUser(commandText)
        setLastBot(localActionText(commandText, `Alarm set for ${new Date(alarm.time_iso).toLocaleString()}.`, `Alarm ${new Date(alarm.time_iso).toLocaleString()} ke liye set ho gaya.`))
        return
      }
    }

    if (!options?.skipPlugin) {
      const plugin = runAssistantPlugin(commandText)
      if (plugin.type === 'navigate') {
        if (plugin.spokenText) speak(plugin.spokenText, { lang: browserLang(profile) })
        window.location.href = plugin.href
        return
      }
      if (plugin.type === 'assistant_prompt') {
        if (/alarm|अलार्म|remind/i.test(commandText)) {
          setPendingAlarmPrompt(commandText)
        const followUpText = localActionText(commandText, 'Sure. What time should I set it for?', 'Theek hai. Kitne baje lagaun?')
        speak(followUpText, { lang: browserLang(profile) })
        setLastUser(commandText)
        setLastBot(followUpText)
        await saveLocalHistory(commandText, followUpText)
        return
      }
        if (plugin.spokenText) speak(localActionText(commandText, plugin.spokenText, 'Abhi sunata hoon.'), { lang: browserLang(profile) })
        await sendAssistantMessage(plugin.prompt, undefined, { skipPlugin: true })
        return
      }
      if (plugin.type === 'list_alarms') {
        const upcoming = alarms.filter((alarm) => new Date(alarm.time_iso).getTime() >= Date.now())
        const messageText =
          upcoming.length === 0
            ? localActionText(commandText, 'You do not have any alarms set right now.', 'Abhi aapka koi alarm set nahi hai.')
            : upcoming.length === 1
              ? localActionText(commandText, `You have 1 alarm set for ${new Date(upcoming[0].time_iso).toLocaleString()}.`, `Aapka 1 alarm ${new Date(upcoming[0].time_iso).toLocaleString()} ke liye set hai.`)
              : localActionText(commandText, `You have ${upcoming.length} alarms set. The next one is at ${new Date(upcoming[0].time_iso).toLocaleString()}.`, `Aapke ${upcoming.length} alarms lage hain. Agla alarm ${new Date(upcoming[0].time_iso).toLocaleString()} par hai.`)
        speak(messageText, { lang: browserLang(profile) })
        setLastUser(commandText)
        setLastBot(messageText)
        await saveLocalHistory(commandText, messageText)
        return
      }
      if (plugin.type === 'activity') {
        await updateActivityStatus(session.user_id, plugin.payload)
        setLastUser(commandText)
        setLastBot(plugin.spokenText || 'Status updated.')
        await saveLocalHistory(commandText, plugin.spokenText || 'Status updated.')
        return
      }
      if (plugin.type === 'call') {
        speak(localActionText(commandText, 'Calling your support person now.', 'Abhi aapke support person ko call kar raha hoon.'), { lang: browserLang(profile) })
        const res = await callContact({ user_id: session.user_id })
        if (res.mode === 'fallback') window.location.href = `tel:${res.target}`
        setLastUser(commandText)
        const replyText = localActionText(commandText, `Calling ${res.label}.`, `${res.label} ko call kar raha hoon.`)
        setLastBot(replyText)
        await saveLocalHistory(commandText, replyText)
        return
      }
      if (plugin.type === 'sos') {
        speak(localActionText(commandText, 'Sending an SOS now.', 'Abhi SOS bhej raha hoon.'), { lang: browserLang(profile) })
        const geoForSos = await getGeoOnce()
        const res = await sendSos({
          user_id: session.user_id,
          reason: plugin.reason || commandText || 'Voice SOS',
          location: geoForSos ? { lat: geoForSos.lat, lng: geoForSos.lon } : undefined,
          severity: 90,
        })
        const callRes = await callContact({ user_id: session.user_id })
        if (callRes.mode === 'fallback') window.location.href = `tel:${callRes.target}`
        setLastUser(commandText)
        const replyText = `${res.message} ${localActionText(commandText, `Calling ${callRes.label} too.`, `${callRes.label} ko call bhi kar raha hoon.`)}`
        setLastBot(replyText)
        await saveLocalHistory(commandText, replyText)
        return
      }
      if (plugin.type === 'alarm') {
        speak(localActionText(commandText, 'Setting your alarm now.', 'Abhi aapka alarm set kar raha hoon.'), { lang: browserLang(profile) })
        const alarm = await createAlarm(session.user_id, {
          title: plugin.payload.title,
          time_iso: plugin.payload.timeIso,
          label: plugin.payload.label,
          source: 'voice_command',
        })
        setAlarms((current) => [...current, alarm].sort((a, b) => a.time_iso.localeCompare(b.time_iso)))
        setLastUser(commandText)
        const replyText = localActionText(commandText, `Alarm set for ${new Date(alarm.time_iso).toLocaleString()}.`, `Alarm ${new Date(alarm.time_iso).toLocaleString()} ke liye set ho gaya.`)
        setLastBot(replyText)
        await saveLocalHistory(commandText, replyText)
        return
      }
    }

    const geo = await getGeoOnce()
    setBusy(true)
    setLastUser(commandText || '(voice)')
    try {
      const res = audioBlob
        ? await postVoiceAudio({ user_id: session.user_id, audio: audioBlob, text: commandText || undefined, lat: geo?.lat, lon: geo?.lon })
        : await postVoice({ user_id: session.user_id, text: commandText, lat: geo?.lat, lon: geo?.lon })
      setLastBot(res.text)
      setLastEmotion(`${res.mood}${res.emotion ? ` | ${res.emotion}` : ''}`)
      if (res.audio_url) {
        try {
          await playAudioUrl(res.audio_url)
        } catch {
          speak(res.text, { lang: responseSpeechLang(res, profile) })
        }
      } else {
        speak(res.text, { lang: responseSpeechLang(res, profile) })
      }
      await afterReply(res.text)
    } catch (e: unknown) {
      setError((e as { message?: string } | undefined)?.message || 'Could not send your message')
    } finally {
      setBusy(false)
    }
  }

  const runVoice = async () => {
    setError('')
    if (!session || busy) return
    if (speaking) {
      setSpeaking(false)
      stopSpeaking()
      return
    }

    try {
      setSpeaking(true)
      let transcript = ''
      let audioBlob: Blob | undefined
      try {
        const heard = await listenOnce({ lang: browserLang(profile), timeoutMs: 9000 })
        transcript = heard.transcript
      } catch (err: any) {
        if (err.message && err.message.includes('not supported')) {
          audioBlob = await recordOnce(9000)
        } else {
          throw err
        }
      }
      setSpeaking(false)
      await sendAssistantMessage(transcript, audioBlob)
    } catch (e: unknown) {
      setSpeaking(false)
      setError((e as { message?: string } | undefined)?.message || 'Listening failed')
    }
  }

  const runWakeMode = async () => {
    if (!session || wakeBusy) return
    setError('')
    try {
      setWakeBusy(true)
      const heard = await listenOnce({ lang: browserLang(profile), timeoutMs: 12000 })
      const transcript = heard.transcript.trim()
      const wakeEnabled = profile?.settings?.wake_word_enabled !== false
      let command = transcript
      if (wakeEnabled) {
        if (!includesWakeWord(transcript, wakeWords)) {
          throw new Error(`Say ${wakeWords[0]} to wake me up`)
        }
        command = stripWakeWords(transcript, wakeWords)
        if (!command && profile?.settings?.auto_send_on_pause !== false) {
          const followUp = await listenOnce({ lang: browserLang(profile), timeoutMs: 9000 })
          command = followUp.transcript.trim()
        }
      }
      await sendAssistantMessage(command)
    } catch (e: unknown) {
      setError((e as { message?: string } | undefined)?.message || 'Wake mode failed')
    } finally {
      setWakeBusy(false)
    }
  }

  if (!session) {
    return (
      <AppShell title="Welcome" subtitle="Create the family manager account first, then add parents inside the app." showNav={false}>
        <AuthPanel
          preferredRole="support"
          onReady={(next) => {
            setSession(next)
            setError('')
          }}
        />
      </AppShell>
    )
  }

  if (session.role === 'support') {
    return (
      <AppShell title="Support Circle" subtitle="Your support session is active. Open the dashboard or settings.">
        <Card>
          <p className="text-lg font-extrabold tracking-tight text-ink">Support tools</p>
          <div className="mt-3 grid gap-2">
            <a href="/support.html" className="block">
              <PressableButton className="w-full" variant="primary" size="lg">
                Open support dashboard
              </PressableButton>
            </a>
          <a href="/settings.html" className="block">
            <PressableButton className="w-full" variant="soft" size="lg">
              Open settings
              </PressableButton>
            </a>
            <PressableButton
              variant="soft"
              size="lg"
              onClick={() => {
                clearStoredSession()
                setSession(null)
                setProfile(null)
                setHistory([])
              }}
            >
              Switch session
            </PressableButton>
          </div>
        </Card>
      </AppShell>
    )
  }

  return (
    <AppShell title="Home" subtitle={`${greeting}. Ready when you are.`}>
      <Card className="pb-2">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-base font-semibold text-ink/75">Hi {profile?.name || session.display_name}</p>
            <p className="mt-1 text-sm text-ink/60">
              Bhumi is ready for voice, text, wake word, and live reminders.
            </p>
          </div>
          <div ref={stickerRef} className="h-14 w-14 shrink-0">
            <ElderSticker className="h-14 w-14" tone="sky" />
          </div>
        </div>

        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <PressableButton variant="primary" onClick={runWakeMode} disabled={wakeBusy || busy}>
            {wakeBusy ? 'Listening...' : 'Say Bhumi once'}
          </PressableButton>
          <PressableButton
            variant="soft"
            onClick={() => {
              clearStoredSession()
              setSession(null)
              setProfile(null)
              setHistory([])
            }}
          >
            Switch Session
          </PressableButton>
        </div>

        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          <PressableButton variant={handsFree ? 'primary' : 'soft'} onClick={() => setHandsFree((current) => !current)}>
            {handsFree ? 'Bhumi hands-free on' : 'Enable Bhumi hands-free'}
          </PressableButton>
          <div className="rounded-2xl bg-white/65 px-3 py-3 text-sm font-semibold text-ink/65 shadow-soft ring-1 ring-black/5">
            Wake words: {wakeWords.join(', ')}
          </div>
        </div>

        <MicButton speaking={speaking || wakeBusy} busy={busy} onToggle={runVoice} />

        <div className="mt-3 rounded-2xl bg-white/75 p-3 shadow-soft ring-1 ring-black/5">
          <label className="text-sm font-semibold text-ink/70">Type to Bhumi</label>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                if (!busy && input.trim()) void sendAssistantMessage(input)
              }
            }}
            rows={3}
            placeholder="Type a question, prayer request, symptom, or family note..."
            className="mt-2 w-full rounded-xl2 border-0 bg-white px-3 py-3 text-base shadow-soft ring-1 ring-black/5"
          />
          <div className="mt-2 flex gap-2">
            <PressableButton variant="primary" onClick={() => void sendAssistantMessage(input)} disabled={busy || !input.trim()}>
              Send Text
            </PressableButton>
            <PressableButton variant="soft" onClick={() => setInput('')}>
              Clear
            </PressableButton>
          </div>
        </div>

        {(lastUser || lastBot || error) && (
          <div className="mt-3 rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
            {error ? (
              <p className="text-sm font-semibold text-danger">{error}</p>
            ) : (
              <>
                {lastUser ? (
                  <p className="text-sm text-ink/70">
                    <span className="font-bold text-ink">You:</span> {lastUser}
                  </p>
                ) : null}
                {lastBot ? (
                  <p className="mt-2 text-base font-semibold text-ink">
                    <span className="font-extrabold">Bhumi:</span> {lastBot}
                  </p>
                ) : null}
                {lastEmotion ? <p className="mt-2 text-sm text-ink/60">Detected mood and emotion: {lastEmotion}</p> : null}
              </>
            )}
          </div>
        )}
      </Card>

      <Card>
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-lg font-extrabold tracking-tight text-ink">Quick prompts</p>
            <p className="mt-1 text-sm text-ink/60">These now send directly to the assistant.</p>
          </div>
          <div className="h-10 w-10">
            <SparkleSticker className="h-10 w-10" />
          </div>
        </div>
        <div className="mt-3 grid gap-2">
          {[
            'How are you feeling right now?',
            'Did you drink some water today?',
            'Please tell me a short doha.',
          ].map((prompt) => (
            <PressableButton key={prompt} variant="soft" size="lg" className="text-left" onClick={() => void sendAssistantMessage(prompt)}>
              {prompt}
            </PressableButton>
          ))}
        </div>
      </Card>

      <Card>
        <p className="text-lg font-extrabold tracking-tight text-ink">Recent text and voice history</p>
        <p className="mt-1 text-sm text-ink/60">Latest conversations are kept here and in settings.</p>
        <div className="mt-3 space-y-2">
          {history.slice(-6).reverse().map((item) => (
            <div key={item.id} className="rounded-2xl bg-white/75 p-3 shadow-soft ring-1 ring-black/5">
              <p className="text-sm text-ink/70">
                <span className="font-bold text-ink">You:</span> {item.text_input}
              </p>
              <p className="mt-2 text-sm font-semibold text-ink">
                <span className="font-extrabold">Bhumi:</span> {item.ai_response}
              </p>
            </div>
          ))}
          {!history.length ? <p className="text-sm text-ink/60">No history yet. Start by speaking or typing above.</p> : null}
        </div>
      </Card>

      <Card>
        <p className="text-lg font-extrabold tracking-tight text-ink">Quick screens</p>
        <p className="mt-1 text-sm text-ink/60">Big buttons. Easy to find.</p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <a href="/medication.html" className="block">
            <PressableButton className="w-full" variant="primary" size="lg">
              Medicines
            </PressableButton>
          </a>
          <a href="/summary.html" className="block">
            <PressableButton className="w-full" variant="soft" size="lg">
              Weekly
            </PressableButton>
          </a>
          <a href="/culture.html" className="block">
            <PressableButton className="w-full" variant="soft" size="lg">
              Stories
            </PressableButton>
          </a>
          <a href="/alert.html" className="block">
            <PressableButton className="w-full" variant="danger" size="lg">
              Health
            </PressableButton>
          </a>
          <a href="/settings.html" className="block">
            <PressableButton className="w-full" variant="soft" size="lg">
              Settings
            </PressableButton>
          </a>
        </div>
      </Card>
    </AppShell>
  )
}
