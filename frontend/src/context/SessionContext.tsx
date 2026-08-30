// Tracks resumes/jobs created in this browser (localStorage-backed) so
// Dashboard has something to show. The backend has no "list all
// resumes/jobs" endpoint (docs/ARCHITECTURE.md §10 doesn't define one —
// there's no auth/user-scoping yet for it to filter by), so this is a
// deliberate, honestly-scoped frontend-only substitute: what you created
// in this browser, not a persisted account history.
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

const STORAGE_KEY = 'resume-matcher-session-v1'

interface TrackedResume {
  id: string
  name: string | null
  filename: string
}

interface TrackedJob {
  id: string
  title: string | null
}

interface SessionState {
  resumes: TrackedResume[]
  jobs: TrackedJob[]
}

interface SessionContextValue extends SessionState {
  addResume: (resume: TrackedResume) => void
  addJob: (job: TrackedJob) => void
}

const SessionContext = createContext<SessionContextValue | null>(null)

function loadInitialState(): SessionState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw) as SessionState
  } catch {
    // corrupted/inaccessible storage — start fresh rather than crash the app
  }
  return { resumes: [], jobs: [] }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SessionState>(loadInitialState)

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
    } catch {
      // best-effort persistence only
    }
  }, [state])

  const addResume = (resume: TrackedResume) =>
    setState((prev) => ({ ...prev, resumes: [resume, ...prev.resumes.filter((r) => r.id !== resume.id)] }))

  const addJob = (job: TrackedJob) =>
    setState((prev) => ({ ...prev, jobs: [job, ...prev.jobs.filter((j) => j.id !== job.id)] }))

  return <SessionContext.Provider value={{ ...state, addResume, addJob }}>{children}</SessionContext.Provider>
}

export function useSession(): SessionContextValue {
  const context = useContext(SessionContext)
  if (!context) throw new Error('useSession must be used within a SessionProvider')
  return context
}
