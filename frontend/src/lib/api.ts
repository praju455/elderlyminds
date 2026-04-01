export const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8010'

export type SessionRole = 'elder' | 'support'

export type AppSession = {
  session_id: string
  role: SessionRole
  user_id: string
  caregiver_id?: string
  display_name: string
  email?: string
  created_at: string
}

export type UserProfile = {
  user_id: string
  name: string
  age: number
  language: string
  region: string
  city: string
  origin?: string
  lat?: number
  lon?: number
  wake_time: string
  sleep_time: string
  caretaker_name?: string
  caretaker_phone?: string
  caregiver_name?: string
  caregiver_phone?: string
  phone?: string
  healthcare_phone?: string
  conditions?: string[]
  allergies?: string[]
  preferences?: string[]
  family_contacts?: Array<{ id?: string; name: string; relation?: string; phone?: string; role?: string }>
  settings?: {
    history_enabled?: boolean
    location_enabled?: boolean
    wake_word_enabled?: boolean
    wake_words?: string[]
    auto_send_on_pause?: boolean
  }
}

export type VoiceResponse = {
  status: 'success'
  text: string
  mood: 'good' | 'okay' | 'low' | 'anxious'
  emotion: string
  timestamp: string
  response_language?: string
  response_language_code?: string
  response_speech_lang?: string
  alert_sent: boolean
  alert_severity: number
  audio_url?: string
  logs?: {
    health?: string[]
    mood?: string[]
    alerts?: string[]
  }
}

export type MedicineLog = {
  id: string
  med_id: string
  medicine_name?: string
  status: 'taken' | 'missed'
  scheduled_time?: string
  confirmed_time?: string
  created_at: string
}

export type MedicineItem = {
  id: string
  name: string
  dose: string
  times: string[]
  instructions?: string
  condition?: string
}

export type WeeklyReport = {
  week_start: string
  week_end: string
  mood_score: number
  mood_trend: number[]
  activity_steps_per_day: number
  medicine_adherence: number
  sleep_hours: number
  health_issues: string[]
  recommendations: string[]
  alert_count: number
}

export type CulturalItem = {
  id: string
  category: string
  title: string
  tradition: string
  summary: string
  moral: string
  quote?: string
}

export type DailyCulture = {
  date: string
  day_name: string
  deity: string
  language: string
  region: string
  tithi: string
  festival: string
  recommended: CulturalItem
}

export type ActivitySummary = {
  user_id: string
  name: string
  day: string
  status: string
  mood: string
  steps: number
  sleep_hours: number
  water_cups: number
  notes: string[]
  mood_score: number
  recent_alerts: Array<{ time_created: string; type: string; severity: number; message: string }>
}

export type RppgAnalysis = {
  status: 'success'
  bpm: number
  sqi: number
  hrv?: Record<string, unknown>
  raw_bvp: number[]
  timestamps: number[]
  plot_url: string
  note: string
  quality_label: string
  match_pct: number
  quality_issues: string[]
  medical_notice: string
}

export type ConversationItem = {
  id: string
  ts: string
  text_input: string
  ai_response: string
  mood: string
  emotion: string
  health_logs?: string[]
  alerts?: string[]
}

export type MemoryItem = {
  id: string
  fact: string
  category: string
  date: string
  source: string
}

export type AlarmItem = {
  id: string
  user_id: string
  title: string
  time_iso: string
  label?: string
  created_at: string
  source?: string
}

export type ReportItem = {
  id: string
  user_id: string
  file_name: string
  mime_type: string
  image_data_url: string
  ocr_text: string
  summary: string
  advice: string
  created_at: string
}

export type AuditItem = {
  id: string
  user_id: string
  action: string
  actor_name?: string
  actor_role?: string
  summary: string
  meta?: Record<string, unknown>
  created_at: string
}

export type SupportAccount = {
  account_id: string
  email: string
  name: string
  phone?: string
  relation?: string
  managed_user_ids?: string[]
}

export type SupportWorkspace = {
  account: SupportAccount
  managed_users: UserProfile[]
  active: {
    user: UserProfile
    support_contacts: Array<{ id?: string; name: string; phone: string; role: string; relation?: string; email?: string }>
    recent_conversations: ConversationItem[]
    medicine_logs: MedicineLog[]
    alerts: Array<{ time_created: string; type: string; severity: number; message: string }>
    memories: MemoryItem[]
    medicines: MedicineItem[]
    alarms: AlarmItem[]
    reports: ReportItem[]
    audit: AuditItem[]
  } | null
}

function _getSessionId(): string {
  try {
    const raw = window.localStorage.getItem('eldermind-session')
    if (!raw) return ''
    const session = JSON.parse(raw) as { session_id?: string }
    return session.session_id || ''
  } catch {
    return ''
  }
}

function _authHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { ...extra }
  const sid = _getSessionId()
  if (sid) headers['authorization'] = `Bearer ${sid}`
  return headers
}

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `Request failed: ${res.status}`
    try {
      const payload = (await res.json()) as { detail?: unknown; message?: unknown }
      if (typeof payload?.detail === 'string' && payload.detail.trim()) detail = payload.detail
      else if (typeof payload?.message === 'string' && payload.message.trim()) detail = payload.message
    } catch {
      // ignore response parsing errors
    }
    throw new Error(detail)
  }
  return (await res.json()) as T
}

export async function createSession(payload: Record<string, unknown>): Promise<AppSession> {
  const res = await fetch(`${API_BASE}/auth/session`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return ((await asJson<{ session: AppSession }>(res)).session)
}

export async function signUp(payload: Record<string, unknown>): Promise<{ session: AppSession; user: UserProfile }> {
  const res = await fetch(`${API_BASE}/auth/signup`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return asJson<{ session: AppSession; user: UserProfile }>(res)
}

export async function signIn(payload: { identifier: string; password: string }): Promise<{ session: AppSession; user: UserProfile }> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return asJson<{ session: AppSession; user: UserProfile }>(res)
}

export async function getUserProfile(user_id: string): Promise<UserProfile> {
  const res = await fetch(`${API_BASE}/user/${encodeURIComponent(user_id)}`, { headers: _authHeaders() })
  return ((await asJson<{ user: UserProfile }>(res)).user)
}

export async function updateUserProfile(user_id: string, payload: Partial<UserProfile>): Promise<UserProfile> {
  const res = await fetch(`${API_BASE}/user/${encodeURIComponent(user_id)}`, {
    method: 'PUT',
    headers: _authHeaders({ 'content-type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  return ((await asJson<{ user: UserProfile }>(res)).user)
}

export async function postVoice({
  user_id,
  text,
  lat,
  lon,
}: {
  user_id: string
  text: string
  lat?: number
  lon?: number
}): Promise<VoiceResponse> {
  const res = await fetch(`${API_BASE}/voice`, {
    method: 'POST',
    headers: _authHeaders({ 'content-type': 'application/json' }),
    body: JSON.stringify({ user_id, text, lat, lon }),
  })
  return asJson<VoiceResponse>(res)
}

export async function postVoiceAudio({
  user_id,
  audio,
  text,
  lat,
  lon,
}: {
  user_id: string
  audio: Blob
  text?: string
  lat?: number
  lon?: number
}): Promise<VoiceResponse> {
  const fd = new FormData()
  fd.set('user_id', user_id)
  if (text) fd.set('text', text)
  if (lat != null) fd.set('lat', String(lat))
  if (lon != null) fd.set('lon', String(lon))
  fd.set('audio', audio, 'audio.webm')
  const res = await fetch(`${API_BASE}/voice`, { method: 'POST', headers: _authHeaders(), body: fd })
  return asJson<VoiceResponse>(res)
}

export async function getConversationHistory(user_id: string, limit = 30): Promise<ConversationItem[]> {
  const res = await fetch(`${API_BASE}/conversations/${encodeURIComponent(user_id)}?limit=${limit}`, { headers: _authHeaders() })
  return ((await asJson<{ items: ConversationItem[] }>(res)).items)
}

export async function addConversationHistory(
  user_id: string,
  payload: {
    ts?: string
    text_input: string
    ai_response: string
    mood?: string
    emotion?: string
    source?: string
    health_logs?: string[]
    alerts?: string[]
  },
) {
  const res = await fetch(`${API_BASE}/conversations/${encodeURIComponent(user_id)}`, {
    method: 'POST',
    headers: _authHeaders({ 'content-type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  return asJson<{ status: string; item: ConversationItem }>(res)
}

export async function clearConversationHistory(user_id: string) {
  const res = await fetch(`${API_BASE}/conversations/${encodeURIComponent(user_id)}`, { method: 'DELETE', headers: _authHeaders() })
  return asJson<{ status: string }>(res)
}

export async function deleteConversationItem(user_id: string, item_id: string) {
  const res = await fetch(`${API_BASE}/conversations/${encodeURIComponent(user_id)}/item/${encodeURIComponent(item_id)}`, { method: 'DELETE', headers: _authHeaders() })
  return asJson<{ status: string }>(res)
}

export async function deleteConversationDay(user_id: string, day_key: string) {
  const res = await fetch(`${API_BASE}/conversations/${encodeURIComponent(user_id)}/day/${encodeURIComponent(day_key)}`, { method: 'DELETE', headers: _authHeaders() })
  return asJson<{ status: string }>(res)
}

export async function getMemories(user_id: string, limit = 20): Promise<MemoryItem[]> {
  const res = await fetch(`${API_BASE}/memory/${encodeURIComponent(user_id)}?limit=${limit}`, { headers: _authHeaders() })
  return ((await asJson<{ items: MemoryItem[] }>(res)).items)
}

export async function clearMemories(user_id: string) {
  const res = await fetch(`${API_BASE}/memory/${encodeURIComponent(user_id)}`, { method: 'DELETE', headers: _authHeaders() })
  return asJson<{ status: string }>(res)
}

export async function getAlarms(user_id: string): Promise<AlarmItem[]> {
  const res = await fetch(`${API_BASE}/alarms/${encodeURIComponent(user_id)}`, { headers: _authHeaders() })
  return ((await asJson<{ items: AlarmItem[] }>(res)).items)
}

export async function createAlarm(user_id: string, payload: { title: string; time_iso: string; label?: string; source?: string }) {
  const res = await fetch(`${API_BASE}/alarms/${encodeURIComponent(user_id)}`, {
    method: 'POST',
    headers: _authHeaders({ 'content-type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  return ((await asJson<{ status: string; item: AlarmItem }>(res)).item)
}

export async function deleteAlarm(user_id: string, alarm_id: string) {
  const res = await fetch(`${API_BASE}/alarms/${encodeURIComponent(user_id)}/${encodeURIComponent(alarm_id)}`, { method: 'DELETE', headers: _authHeaders() })
  return asJson<{ status: string }>(res)
}

export async function getReports(user_id: string, limit = 20): Promise<ReportItem[]> {
  const res = await fetch(`${API_BASE}/reports/${encodeURIComponent(user_id)}?limit=${limit}`, { headers: _authHeaders() })
  return ((await asJson<{ status: string; items: ReportItem[] }>(res)).items)
}

export async function addReport(
  user_id: string,
  payload: {
    file_name: string
    mime_type: string
    image_data_url: string
    ocr_text: string
    summary: string
    advice: string
  },
): Promise<ReportItem> {
  const res = await fetch(`${API_BASE}/reports/${encodeURIComponent(user_id)}`, {
    method: 'POST',
    headers: _authHeaders({ 'content-type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  return ((await asJson<{ status: string; item: ReportItem }>(res)).item)
}

export async function deleteReport(user_id: string, report_id: string) {
  const res = await fetch(`${API_BASE}/reports/${encodeURIComponent(user_id)}/${encodeURIComponent(report_id)}`, { method: 'DELETE', headers: _authHeaders() })
  return asJson<{ status: string }>(res)
}

export async function reviewReportMedicines(
  user_id: string,
  report_id: string,
  payload: {
    decision: 'approve' | 'reject'
    medicines?: MedicineItem[]
    actor_name?: string
    actor_role?: string
  },
) {
  const res = await fetch(`${API_BASE}/reports/${encodeURIComponent(user_id)}/${encodeURIComponent(report_id)}/review`, {
    method: 'POST',
    headers: _authHeaders({ 'content-type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  return asJson<{ status: string; decision: string; medicines?: MedicineItem[] }>(res)
}

export async function shareReportAnalysis(
  user_id: string,
  report_id: string,
  payload: { actor_name?: string; actor_role?: string; severity?: number } = {},
) {
  const res = await fetch(`${API_BASE}/reports/${encodeURIComponent(user_id)}/${encodeURIComponent(report_id)}/share`, {
    method: 'POST',
    headers: _authHeaders({ 'content-type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  return asJson<{ status: string; delivery: { message: string; alerts_sent_to: string[] } }>(res)
}

export async function getAudit(user_id: string, limit = 40): Promise<AuditItem[]> {
  const res = await fetch(`${API_BASE}/audit/${encodeURIComponent(user_id)}?limit=${limit}`, { headers: _authHeaders() })
  return ((await asJson<{ status: string; items: AuditItem[] }>(res)).items)
}

export async function getMedicines(user_id: string): Promise<{ medicines: MedicineItem[]; logs: MedicineLog[] }> {
  const res = await fetch(`${API_BASE}/medicine/${encodeURIComponent(user_id)}`, { headers: _authHeaders() })
  return asJson<{ medicines: MedicineItem[]; logs: MedicineLog[] }>(res)
}

export async function saveMedicines(user_id: string, medicines: MedicineItem[]) {
  const res = await fetch(`${API_BASE}/medicine/${encodeURIComponent(user_id)}`, {
    method: 'PUT',
    headers: _authHeaders({ 'content-type': 'application/json' }),
    body: JSON.stringify({ medicines, actor_role: 'family_manager' }),
  })
  return ((await asJson<{ status: string; medicines: MedicineItem[] }>(res)).medicines)
}

export async function syncMedicineReminders(user_id: string) {
  const res = await fetch(`${API_BASE}/medicine/${encodeURIComponent(user_id)}/sync-reminders`, {
    method: 'POST',
    headers: _authHeaders(),
  })
  return asJson<{ status: string; items: AlarmItem[] }>(res)
}

export async function confirmMedicine({
  med_id,
  user_id,
  status,
  scheduled_time,
}: {
  med_id: string
  user_id: string
  status: 'taken' | 'missed'
  scheduled_time?: string
}) {
  const res = await fetch(`${API_BASE}/medicine/${encodeURIComponent(med_id)}/confirm`, {
    method: 'POST',
    headers: _authHeaders({ 'content-type': 'application/json' }),
    body: JSON.stringify({ user_id, status, scheduled_time }),
  })
  return asJson<{ status: string; logged: MedicineLog }>(res)
}

export async function getWeeklyReport(user_id: string): Promise<WeeklyReport> {
  const res = await fetch(`${API_BASE}/report/weekly/${encodeURIComponent(user_id)}`, { headers: _authHeaders() })
  return asJson<WeeklyReport>(res)
}

export async function generatePdfReport(user_id: string): Promise<{ pdf_url: string; filename: string; user_name: string }> {
  const res = await fetch(`${API_BASE}/report/pdf/${encodeURIComponent(user_id)}`, { headers: _authHeaders() })
  return asJson<{ status: string; pdf_url: string; filename: string; user_name: string }>(res)
}

export async function getDailyCulture(user_id: string): Promise<{ calendar: DailyCulture; stories: CulturalItem[] }> {
  const res = await fetch(`${API_BASE}/culture/daily/${encodeURIComponent(user_id)}`, { headers: _authHeaders() })
  return asJson<{ status: string; calendar: DailyCulture; stories: CulturalItem[] }>(res)
}

export async function getCultureLibrary(query = '', category = ''): Promise<CulturalItem[]> {
  const url = `${API_BASE}/culture/library?q=${encodeURIComponent(query)}&category=${encodeURIComponent(category)}`
  const res = await fetch(url, { headers: _authHeaders() })
  return ((await asJson<{ status: string; items: CulturalItem[] }>(res)).items)
}

export async function getActivity(user_id: string): Promise<ActivitySummary> {
  const res = await fetch(`${API_BASE}/activity/${encodeURIComponent(user_id)}`, { headers: _authHeaders() })
  return ((await asJson<{ activity: ActivitySummary }>(res)).activity)
}

export async function updateActivityStatus(user_id: string, payload: Record<string, unknown>): Promise<ActivitySummary> {
  const res = await fetch(`${API_BASE}/activity/${encodeURIComponent(user_id)}/status`, {
    method: 'POST',
    headers: _authHeaders({ 'content-type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  return ((await asJson<{ activity: ActivitySummary }>(res)).activity)
}

export async function analyzeRppgVideo(user_id: string, video: File | Blob): Promise<RppgAnalysis> {
  const fd = new FormData()
  fd.set('user_id', user_id)
  fd.set('video', video, video instanceof File ? video.name : 'face-video.webm')
  const res = await fetch(`${API_BASE}/rppg/analyze`, { method: 'POST', headers: _authHeaders(), body: fd })
  return asJson<RppgAnalysis>(res)
}

export async function sendSos({
  user_id,
  reason,
  location,
  severity,
}: {
  user_id: string
  reason?: string
  location?: unknown
  severity?: number
}) {
  const res = await fetch(`${API_BASE}/sos`, {
    method: 'POST',
    headers: _authHeaders({ 'content-type': 'application/json' }),
    body: JSON.stringify({ user_id, reason, location, severity }),
  })
  return asJson<{
    status: 'success'
    alerts_sent_to: string[]
    timestamp: string
    severity: number
    message: string
  }>(res)
}

export async function callContact({
  user_id,
  to,
  label,
}: {
  user_id: string
  to?: string
  label?: string
}) {
  const res = await fetch(`${API_BASE}/call`, {
    method: 'POST',
    headers: _authHeaders({ 'content-type': 'application/json' }),
    body: JSON.stringify({ user_id, to, label }),
  })
  return asJson<{ status: string; mode: string; target: string; label: string }>(res)
}

export async function getDashboard(caretaker_id: string) {
  const res = await fetch(`${API_BASE}/dashboard/${encodeURIComponent(caretaker_id)}`, { headers: _authHeaders() })
  return asJson<{
    caregiver_id: string
    user: UserProfile
    support_contacts: Array<{ name: string; phone: string; role: string }>
    recent_conversations: ConversationItem[]
    medicine_logs: MedicineLog[]
    alerts: Array<{ time_created: string; type: string; severity: number; message: string }>
    memories: MemoryItem[]
  }>(res)
}

export async function getSupportWorkspace(account_id: string, active_user_id = ''): Promise<SupportWorkspace> {
  const suffix = active_user_id ? `?active_user_id=${encodeURIComponent(active_user_id)}` : ''
  const res = await fetch(`${API_BASE}/support/account/${encodeURIComponent(account_id)}${suffix}`, { headers: _authHeaders() })
  const payload = await asJson<{ status: string } & SupportWorkspace>(res)
  return {
    account: payload.account,
    managed_users: payload.managed_users,
    active: payload.active,
  }
}

export async function updateSupportAccount(
  account_id: string,
  payload: { name: string; email: string; phone?: string; relation?: string },
) {
  const res = await fetch(`${API_BASE}/support/account/${encodeURIComponent(account_id)}`, {
    method: 'PUT',
    headers: _authHeaders({ 'content-type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  return asJson<{ status: string; account: SupportAccount }>(res)
}

export async function createManagedElder(
  account_id: string,
  payload: {
    name: string
    user_id: string
    password: string
    age?: number
    language?: string
    region?: string
    city?: string
    origin?: string
    phone?: string
    email?: string
    wake_time?: string
    sleep_time?: string
    preferences?: string[]
  },
): Promise<{ user: UserProfile; login: { user_id: string; account_id?: string } }> {
  const res = await fetch(`${API_BASE}/support/account/${encodeURIComponent(account_id)}/elders`, {
    method: 'POST',
    headers: _authHeaders({ 'content-type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  const data = await asJson<{ status: string; user: UserProfile; login: { user_id: string; account_id?: string } }>(res)
  return { user: data.user, login: data.login }
}

export async function createCaretakerLogin(
  account_id: string,
  payload: {
    user_id: string
    name: string
    email: string
    password: string
    phone?: string
    relation?: string
  },
) {
  const res = await fetch(`${API_BASE}/support/account/${encodeURIComponent(account_id)}/caretakers`, {
    method: 'POST',
    headers: _authHeaders({ 'content-type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  return asJson<{ status: string; account: SupportAccount; user: UserProfile }>(res)
}

export async function resetParentPassword(account_id: string, user_id: string, payload: { password: string }) {
  const res = await fetch(`${API_BASE}/support/account/${encodeURIComponent(account_id)}/elders/${encodeURIComponent(user_id)}/reset-password`, {
    method: 'POST',
    headers: _authHeaders({ 'content-type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  return asJson<{ status: string }>(res)
}

export async function updateCaretakerLogin(
  account_id: string,
  contact_id: string,
  payload: { user_id: string; name?: string; relation?: string; role?: string; phone?: string; email?: string; password?: string },
) {
  const res = await fetch(`${API_BASE}/support/account/${encodeURIComponent(account_id)}/caretakers/${encodeURIComponent(contact_id)}`, {
    method: 'PUT',
    headers: _authHeaders({ 'content-type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  return asJson<{ status: string }>(res)
}

export async function deleteCaretakerLogin(account_id: string, contact_id: string, user_id: string) {
  const res = await fetch(
    `${API_BASE}/support/account/${encodeURIComponent(account_id)}/caretakers/${encodeURIComponent(contact_id)}?user_id=${encodeURIComponent(user_id)}`,
    { method: 'DELETE', headers: _authHeaders() },
  )
  return asJson<{ status: string; deleted_account: boolean }>(res)
}

export async function testWhatsApp(payload: { user_id?: string; phone?: string; message?: string }) {
  const res = await fetch(`${API_BASE}/whatsapp/test`, {
    method: 'POST',
    headers: _authHeaders({ 'content-type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  return asJson<{ status: string; configured: boolean; target: string; result: string; message: string }>(res)
}

export async function analyzeReport(payload: { user_id?: string; file_name?: string; report_text: string }) {
  const res = await fetch(`${API_BASE}/report/analyze`, {
    method: 'POST',
    headers: _authHeaders({ 'content-type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  return asJson<{ status: string; summary: string; advice: string; suggested_medicines: Array<Omit<MedicineItem, 'id'> & { id?: string }> }>(res)
}
