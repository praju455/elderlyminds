export function nowMs(): number {
  return Date.now()
}

export function uid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `${nowMs()}-${Math.random().toString(16).slice(2)}`
}

