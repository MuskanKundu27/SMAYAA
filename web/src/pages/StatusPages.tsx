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
