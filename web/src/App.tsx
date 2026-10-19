import { useEffect, useState } from 'react'

type ApiStatus = 'checking' | 'ok' | 'down'

// Placeholder start page for step 0: proves the web app can reach the API.
// Replaced by the login screen and module renderer in later steps.
export default function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>('checking')

  useEffect(() => {
    fetch('/api/v1/health')
      .then((response) => setApiStatus(response.ok ? 'ok' : 'down'))
      .catch(() => setApiStatus('down'))
  }, [])

  return (
    <main style={{ padding: '3rem 1.5rem', maxWidth: 640, margin: '0 auto' }}>
      <h1 style={{ color: 'var(--navy)', marginBottom: '0.25rem' }}>SMAYAA.ai</h1>
      <p style={{ color: 'var(--muted)', marginTop: 0 }}>Cooling-tower water intelligence</p>
      <p>
        API status:{' '}
        <strong style={{ color: apiStatus === 'down' ? 'var(--bad)' : 'var(--good)' }}>
          {apiStatus}
        </strong>
      </p>
    </main>
  )
}
