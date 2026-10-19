import type { MenuItem } from '../navigation'

export function PlaceholderPage({ item }: { item: MenuItem }) {
  return (
    <>
      <h1>{item.label}</h1>
      <div className="card placeholder">
        <p>
          This page is coming in <strong>{item.comingIn}</strong>.
        </p>
        <p className="muted">You can see it because your role includes access to {item.label}.</p>
      </div>
    </>
  )
}

export function NoAccessPage() {
  return (
    <>
      <h1>No access</h1>
      <div className="card placeholder">
        <p>Your role does not include this page.</p>
      </div>
    </>
  )
}

export function NotFoundPage() {
  return (
    <>
      <h1>Page not found</h1>
      <div className="card placeholder">
        <p>This address does not exist.</p>
      </div>
    </>
  )
}
