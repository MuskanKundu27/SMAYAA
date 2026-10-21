import type { ReactNode } from 'react'

export function ErrorText({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <p className="form-error" role="alert">
      {message}
    </p>
  )
}

export function Notice({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'warn' }) {
  return <div className={`notice notice--${tone}`}>{children}</div>
}

/** Shown while the first load is running. */
export function Loading() {
  return <p className="muted">Loading…</p>
}

export function StatusBadge({ active }: { active: boolean }) {
  return <span className={`pill ${active ? 'pill--good' : 'pill--na'}`}>{active ? 'Active' : 'Inactive'}</span>
}
