import type { Root } from 'react-dom/client'
import { HomePage } from './screens/HomePage'
import { MedicationPage } from './screens/MedicationPage'
import { ActivityPage } from './screens/ActivityPage'
import { AlertPage } from './screens/AlertPage'
import { SummaryPage } from './screens/SummaryPage'
import { CaregiverPage } from './screens/CaregiverPage'
import { SettingsPage } from './screens/SettingsPage'
import { CulturePage } from './screens/CulturePage'

export type ElderMindPage = 'home' | 'medication' | 'activity' | 'alert' | 'summary' | 'caregiver' | 'caretaker' | 'support' | 'settings' | 'culture'

export function renderPage({ root, page }: { root: Root; page: string }) {
  const normalized = page.toLowerCase() as ElderMindPage

  switch (normalized) {
    case 'home':
      root.render(<HomePage />)
      return
    case 'medication':
      root.render(<MedicationPage />)
      return
    case 'activity':
      root.render(<ActivityPage />)
      return
    case 'alert':
      root.render(<AlertPage />)
      return
    case 'summary':
      root.render(<SummaryPage />)
      return
    case 'culture':
      root.render(<CulturePage />)
      return
    case 'caregiver':
    case 'caretaker':
    case 'support':
      root.render(<CaregiverPage />)
      return
    case 'settings':
      root.render(<SettingsPage />)
      return
    default:
      root.render(<HomePage />)
  }
}
