export type AssistantPluginResult =
  | { type: 'navigate'; href: string; spokenText?: string }
  | { type: 'activity'; payload: { status: string; mood: string; note: string }; spokenText?: string }
  | { type: 'call'; spokenText?: string }
  | { type: 'sos'; spokenText?: string; reason?: string }
  | { type: 'alarm'; payload: { title: string; timeIso: string; label?: string }; spokenText?: string }
  | { type: 'list_alarms'; spokenText?: string }
  | { type: 'assistant_prompt'; prompt: string; spokenText?: string }
  | { type: 'none' }

export type AssistantPlugin = {
  name: string
  match: (text: string) => boolean
  run: (text: string) => AssistantPluginResult
}

export function parseAlarmTime(text: string): { timeIso: string; label?: string } | null {
  const lowered = text.toLowerCase()
  const match = lowered.match(/(?:alarm|remind(?: me)?|wake me|अलार्म|रिमाइंड)(?:.*?)(?:for|at|on)?\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm|baje| बजे)?/)
  if (!match) return null
  const hourRaw = Number(match[1])
  const minute = Number(match[2] || 0)
  const suffix = (match[3] || '').trim()
  if (Number.isNaN(hourRaw) || Number.isNaN(minute)) return null
  let hour = hourRaw
  if (suffix === 'pm' && hour < 12) hour += 12
  if (suffix === 'am' && hour === 12) hour = 0
  if (hour > 23 || minute > 59) return null
  const now = new Date()
  const when = new Date(now)
  when.setSeconds(0, 0)
  when.setHours(hour, minute, 0, 0)
  if (when.getTime() <= now.getTime()) when.setDate(when.getDate() + 1)
  return {
    timeIso: when.toISOString(),
    label: text.trim(),
  }
}

const plugins: AssistantPlugin[] = [
  {
    name: 'alarm',
    match: (text) => /\b(alarm|remind|wake me)\b/i.test(text) || /अलार्म|रिमाइंड|बजे/i.test(text),
    run: (text) => {
      const parsed = parseAlarmTime(text)
      if (!parsed) {
        return {
          type: 'assistant_prompt',
          prompt: 'Ask for a clear alarm time in the same language the user used.',
          spokenText: 'I need a clear alarm time.',
        }
      }
      return {
        type: 'alarm',
        payload: { title: 'Alarm', timeIso: parsed.timeIso, label: parsed.label },
        spokenText: 'Setting your alarm now.',
      }
    },
  },
  {
    name: 'list-alarms',
    match: (text) => /\b(how many alarms|list alarms|what alarms|which alarms)\b/i.test(text) || /कितने अलार्म|कौन सा अलार्म|अलार्म लगे/i.test(text),
    run: () => ({ type: 'list_alarms', spokenText: 'Checking your alarms now.' }),
  },
  {
    name: 'call',
    match: (text) => /\b(call support|call family|phone support|phone family|call my son|call my daughter)\b/i.test(text) || /कॉल|फोन/i.test(text),
    run: () => ({ type: 'call', spokenText: 'Calling your support person now.' }),
  },
  {
    name: 'sos',
    match: (text) => /\b(sos|emergency|help me|urgent help)\b/i.test(text) || /बचाओ|मदद/i.test(text),
    run: (text) => ({ type: 'sos', spokenText: 'Sending an SOS now.', reason: text.trim() || 'Voice SOS' }),
  },
  {
    name: 'medicines',
    match: (text) => /\b(medicine|medicines|tablet|dawa|meds)\b/i.test(text),
    run: () => ({ type: 'navigate', href: '/medication.html', spokenText: 'Opening medicines.' }),
  },
  {
    name: 'summary',
    match: (text) => /\b(summary|weekly|report)\b/i.test(text),
    run: () => ({ type: 'navigate', href: '/summary.html', spokenText: 'Opening the weekly summary.' }),
  },
  {
    name: 'culture',
    match: (text) =>
      /\b(ramayana|gita|doha|story|stories|calendar|chalisa|birbal|tenali|panchatantra|mahabharata)\b/i.test(text) ||
      /रामायण|कहानी|दोहा|चालीसा|महाभारत/i.test(text),
    run: (text) => {
      if (/\b(play|tell|read|sunao|suno|recite)\b/i.test(text) || /सुनाओ|पढ़ो|कहानी/i.test(text)) {
        return {
          type: 'assistant_prompt',
          prompt: text.trim(),
          spokenText: 'Playing that for you now.',
        }
      }
      return { type: 'navigate', href: '/culture.html', spokenText: 'Opening calendar and stories.' }
    },
  },
  {
    name: 'help',
    match: (text) => /\b(help|health page)\b/i.test(text),
    run: () => ({ type: 'navigate', href: '/alert.html', spokenText: 'Opening emergency help.' }),
  },
  {
    name: 'settings',
    match: (text) => /\b(settings|profile|history|location)\b/i.test(text),
    run: () => ({ type: 'navigate', href: '/settings.html', spokenText: 'Opening settings.' }),
  },
  {
    name: 'status-good',
    match: (text) => /\b(i feel okay|feeling okay|i am okay)\b/i.test(text),
    run: () => ({
      type: 'activity',
      payload: { status: 'good', mood: 'good', note: 'User said they feel okay.' },
      spokenText: 'Noted. You are feeling okay today.',
    }),
  },
]

export function stripWakeWords(text: string, wakeWords: string[]): string {
  const normalized = text.trim()
  for (const wakeWord of wakeWords) {
    const pattern = new RegExp(`^${wakeWord.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}[\\s,.:!-]*`, 'i')
    if (pattern.test(normalized)) {
      return normalized.replace(pattern, '').trim()
    }
  }
  return normalized
}

export function includesWakeWord(text: string, wakeWords: string[]): boolean {
  return wakeWords.some((wakeWord) => text.toLowerCase().includes(wakeWord.toLowerCase()))
}

export function runAssistantPlugin(text: string): AssistantPluginResult {
  for (const plugin of plugins) {
    if (plugin.match(text)) return plugin.run(text)
  }
  return { type: 'none' }
}
