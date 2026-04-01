import { useEffect, useRef, useState } from 'react'
import { analyzeRppgVideo, type RppgAnalysis } from '../lib/api'
import { Card } from './Card'
import { PressableButton } from './Pressable'
import { HeartPulseSticker } from './stickers'

export function RppgCaptureCard({
  userId,
  onAnalyzed,
}: {
  userId: string
  onAnalyzed?: (result: RppgAnalysis) => void | Promise<void>
}) {
  const [busy, setBusy] = useState(false)
  const [recording, setRecording] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<RppgAnalysis | null>(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const inputRef = useRef<HTMLInputElement | null>(null)
  const liveVideoRef = useRef<HTMLVideoElement | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const autoStopTimerRef = useRef<number | null>(null)
  const previewUrlRef = useRef('')

  useEffect(() => {
    return () => {
      if (autoStopTimerRef.current) window.clearTimeout(autoStopTimerRef.current)
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        try {
          mediaRecorderRef.current.stop()
        } catch {
          // ignore shutdown issues
        }
      }
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((track) => track.stop())
      }
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current)
    }
  }, [])

  const setPreview = (url: string) => {
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current)
    previewUrlRef.current = url
    setPreviewUrl(url)
  }

  const stopRecordingResources = () => {
    if (autoStopTimerRef.current) {
      window.clearTimeout(autoStopTimerRef.current)
      autoStopTimerRef.current = null
    }
    const video = liveVideoRef.current as HTMLVideoElement & { srcObject?: MediaStream | null }
    if (video) video.srcObject = null
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop())
      mediaStreamRef.current = null
    }
    mediaRecorderRef.current = null
    setRecording(false)
  }

  const analyzeFile = async (file: Blob, fileName: string) => {
    try {
      setBusy(true)
      setError('')
      const wrapped = file instanceof File ? file : new File([file], fileName, { type: file.type || 'video/webm' })
      const nextPreview = URL.createObjectURL(wrapped)
      setPreview(nextPreview)
      const analysis = await analyzeRppgVideo(userId, wrapped)
      setResult(analysis)
      await onAnalyzed?.(analysis)
    } catch (e: unknown) {
      setError((e as { message?: string } | undefined)?.message || 'Could not run the camera wellness check')
    } finally {
      setBusy(false)
    }
  }

  const startRecording = async () => {
    try {
      setError('')
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 720 }, height: { ideal: 720 } },
        audio: false,
      })
      mediaStreamRef.current = stream
      const video = liveVideoRef.current as HTMLVideoElement & { srcObject?: MediaStream | null }
      if (video) {
        video.srcObject = stream
        await video.play().catch(() => {})
      }

      const recorder = new MediaRecorder(stream, { mimeType: 'video/webm' })
      mediaRecorderRef.current = recorder
      const chunks: BlobPart[] = []
      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) chunks.push(event.data)
      }
      recorder.onerror = () => {
        stopRecordingResources()
        setError('Video recording failed. Please try again.')
      }
      recorder.onstop = () => {
        const blob = new Blob(chunks, { type: 'video/webm' })
        stopRecordingResources()
        if (blob.size > 0) {
          void analyzeFile(blob, `bhumi-rppg-${Date.now()}.webm`)
        } else {
          setError('No video was recorded. Please try again.')
        }
      }
      recorder.start()
      setRecording(true)
      autoStopTimerRef.current = window.setTimeout(() => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
          mediaRecorderRef.current.stop()
        }
      }, 15000)
    } catch (e: unknown) {
      stopRecordingResources()
      setError((e as { message?: string } | undefined)?.message || 'Camera access failed. Please allow camera permission.')
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop()
    } else {
      stopRecordingResources()
    }
  }

  return (
    <Card>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-lg font-extrabold tracking-tight text-ink">Camera wellness check</p>
          <p className="mt-1 text-sm text-ink/60">
            Upload a short face video or record one now and Bhumi will estimate an experimental pulse and show the raw BVP signal.
          </p>
          <p className="mt-1 text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Experimental only · not medical</p>
        </div>
        <div className="rounded-2xl bg-rose/10 p-2 ring-1 ring-black/5">
          <HeartPulseSticker className="h-12 w-12" />
        </div>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="video/*"
        capture="user"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) void analyzeFile(file, file.name)
          e.currentTarget.value = ''
        }}
      />

      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <PressableButton variant="soft" size="lg" onClick={() => inputRef.current?.click()} disabled={busy || recording}>
          {busy ? 'Analyzing face video...' : 'Upload video'}
        </PressableButton>
        <PressableButton variant={recording ? 'danger' : 'primary'} size="lg" onClick={() => (recording ? stopRecording() : void startRecording())} disabled={busy}>
          {recording ? 'Stop recording' : 'Record video now'}
        </PressableButton>
      </div>

      <div className="mt-3 rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
        {recording ? (
          <>
            <p className="text-sm font-semibold text-ink">Recording now. Keep your face steady for up to 15 seconds.</p>
            <video ref={liveVideoRef} className="mt-3 w-full rounded-2xl bg-black object-cover ring-1 ring-black/5" muted playsInline />
          </>
        ) : previewUrl ? (
          <>
            <p className="text-sm font-semibold text-ink">Latest video preview</p>
            <video src={previewUrl} className="mt-3 w-full rounded-2xl bg-black object-cover ring-1 ring-black/5" controls playsInline />
          </>
        ) : (
          <p className="text-sm text-ink/60">Use the front camera or upload a saved face video with good light and a steady face.</p>
        )}
      </div>

      {error ? (
        <div className="mt-3 rounded-2xl bg-rose/10 p-3 shadow-soft ring-1 ring-black/5">
          <p className="text-sm font-semibold text-danger">{error}</p>
        </div>
      ) : null}

      {result ? (
        <div className="mt-3 space-y-3">
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
              <p className="text-xs font-bold tracking-wide text-ink/60">Estimated pulse</p>
              <p className="mt-1 text-2xl font-extrabold tracking-tight text-ink">{Math.round(result.bpm)} BPM</p>
            </div>
            <div className="rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
              <p className="text-xs font-bold tracking-wide text-ink/60">Signal quality</p>
              <p className={`mt-1 text-2xl font-extrabold tracking-tight ${result.match_pct >= 65 ? 'text-emerald-600' : result.match_pct >= 40 ? 'text-amber-600' : 'text-rose-600'}`}>
                {result.quality_label}
              </p>
            </div>
            <div className="rounded-2xl bg-white/70 p-3 shadow-soft ring-1 ring-black/5">
              <p className="text-xs font-bold tracking-wide text-ink/60">Match</p>
              <p className={`mt-1 text-2xl font-extrabold tracking-tight ${result.match_pct >= 65 ? 'text-emerald-600' : result.match_pct >= 40 ? 'text-amber-600' : 'text-rose-600'}`}>
                {result.match_pct}%
              </p>
            </div>
          </div>

          {result.quality_issues.length > 0 && (
            <div className="rounded-2xl bg-amber-50 p-3 shadow-soft ring-1 ring-amber-200/60">
              <p className="text-sm font-bold text-amber-800">Tips to improve</p>
              <ul className="mt-1 list-disc pl-4 text-sm text-amber-700">
                {result.quality_issues.map((issue, i) => <li key={i}>{issue}</li>)}
              </ul>
            </div>
          )}

          <p className="text-sm text-ink/70">{result.note}</p>
          <p className="text-xs text-ink/55">{result.medical_notice}</p>
          <img src={result.plot_url} alt="Raw BVP signal" className="w-full rounded-2xl bg-white object-cover ring-1 ring-black/5" />
        </div>
      ) : null}
    </Card>
  )
}
