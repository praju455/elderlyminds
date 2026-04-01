import { openDB } from 'idb'

type ConversationRow = {
  id: string
  createdAt: number
  userText: string
  botText: string
  mood?: string
}

type MedLogRow = {
  id: string
  createdAt: number
  medId: string
  status: 'taken' | 'missed'
}

const dbPromise = openDB('eldermind', 1, {
  upgrade(db) {
    db.createObjectStore('conversations', { keyPath: 'id' })
    db.createObjectStore('medLogs', { keyPath: 'id' })
  },
})

export async function saveConversation(row: ConversationRow) {
  const db = await dbPromise
  await db.put('conversations', row)
}

export async function getRecentConversations(limit = 10): Promise<ConversationRow[]> {
  const db = await dbPromise
  const all = (await db.getAll('conversations')) as ConversationRow[]
  return all.sort((a, b) => b.createdAt - a.createdAt).slice(0, limit)
}

export async function saveMedLog(row: MedLogRow) {
  const db = await dbPromise
  await db.put('medLogs', row)
}

export async function getRecentMedLogs(limit = 20): Promise<MedLogRow[]> {
  const db = await dbPromise
  const all = (await db.getAll('medLogs')) as MedLogRow[]
  return all.sort((a, b) => b.createdAt - a.createdAt).slice(0, limit)
}

