export type SpeechSupport = {
  stt: boolean
  tts: boolean
}

type SpeechRecognitionCtor = new () => SpeechRecognitionLike

type SpeechRecognitionLike = {
  lang: string
  interimResults: boolean
  maxAlternatives: number
  start: () => void
  stop: () => void
  onresult: ((event: unknown) => void) | null
  onerror: ((event: unknown) => void) | null
  onend: (() => void) | null
}

type SpeechRecognitionResultEventLike = {
  results?: ArrayLike<ArrayLike<{ transcript?: string }>>
}

export function getSpeechSupport(): SpeechSupport {
  const w = window as unknown as { SpeechRecognition?: SpeechRecognitionCtor; webkitSpeechRecognition?: SpeechRecognitionCtor }
  const stt = typeof window !== 'undefined' && Boolean(w.SpeechRecognition || w.webkitSpeechRecognition)
  const tts = typeof window !== 'undefined' && 'speechSynthesis' in window
  return { stt, tts }
}

export function speak(text: string, { lang = 'en-IN', rate = 0.92, pitch = 1.02 }: { lang?: string; rate?: number; pitch?: number } = {}) {
  if (!('speechSynthesis' in window)) return
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(text)
  u.lang = lang
  u.rate = rate
  u.pitch = pitch
  window.speechSynthesis.speak(u)
}

export function stopSpeaking() {
  if (!('speechSynthesis' in window)) return
  window.speechSynthesis.cancel()
}

export async function playAudioUrl(url: string): Promise<void> {
  const a = new Audio(url)
  a.preload = 'auto'
  a.crossOrigin = 'anonymous'
  await new Promise<void>((resolve, reject) => {
    const done = () => {
      a.removeEventListener('canplaythrough', onReady)
      a.removeEventListener('error', onError)
      resolve()
    }
    const fail = (message: string) => {
      a.removeEventListener('canplaythrough', onReady)
      a.removeEventListener('error', onError)
      reject(new Error(message))
    }
    const onReady = () => done()
    const onError = () => fail('Audio could not be loaded')
    a.addEventListener('canplaythrough', onReady, { once: true })
    a.addEventListener('error', onError, { once: true })
    a.load()
  })
  await a.play()
}

export function listenOnce({
  lang = 'en-IN',
  timeoutMs = 9000,
  pauseMs = 5000,
}: {
  lang?: string
  timeoutMs?: number
  pauseMs?: number
}): Promise<{ transcript: string }> {
  return new Promise((resolve, reject) => {
    const w = window as unknown as { SpeechRecognition?: SpeechRecognitionCtor; webkitSpeechRecognition?: SpeechRecognitionCtor }
    const SR = w.SpeechRecognition || w.webkitSpeechRecognition
    if (!SR) return reject(new Error('SpeechRecognition not supported in this browser'))

    const rec = new SR()
    rec.lang = lang
    rec.interimResults = true
    rec.maxAlternatives = 1

    let done = false
    let transcript = ''
    const finish = (fn: () => void) => {
      if (done) return
      done = true
      try {
        rec.stop()
      } catch {
        // ignore
      }
      fn()
    }

    const totalTimer = window.setTimeout(() => {
      finish(() => reject(new Error('Listening timed out')))
    }, timeoutMs)

    let pauseTimer = window.setTimeout(() => {
      finish(() =>
        transcript.trim()
          ? resolve({ transcript: transcript.trim() })
          : reject(new Error('Listening timed out')),
      )
    }, pauseMs)

    const resetPauseTimer = () => {
      window.clearTimeout(pauseTimer)
      pauseTimer = window.setTimeout(() => {
        finish(() =>
          transcript.trim()
            ? resolve({ transcript: transcript.trim() })
            : reject(new Error('Listening timed out')),
        )
      }, pauseMs)
    }

    rec.onresult = (event: unknown) => {
      const ev = event as SpeechRecognitionResultEventLike
      const results = ev?.results
      if (!results?.length) return
      const lastResult = results[results.length - 1]
      const nextTranscript = lastResult?.[0]?.transcript?.toString?.() || ''
      if (nextTranscript) transcript = nextTranscript
      resetPauseTimer()
    }
    rec.onerror = (e: unknown) => {
      window.clearTimeout(totalTimer)
      window.clearTimeout(pauseTimer)
      const msg = (e as { error?: string } | undefined)?.error || 'Speech recognition error'
      finish(() => reject(new Error(msg)))
    }
    rec.onend = () => {
      if (done) return
      window.clearTimeout(totalTimer)
      window.clearTimeout(pauseTimer)
      if (transcript.trim()) {
        finish(() => resolve({ transcript: transcript.trim() }))
        return
      }
      finish(() => reject(new Error('No speech detected')))
    }

    try {
      rec.start()
    } catch (e: unknown) {
      window.clearTimeout(totalTimer)
      window.clearTimeout(pauseTimer)
      finish(() => reject(e))
    }
  })
}
