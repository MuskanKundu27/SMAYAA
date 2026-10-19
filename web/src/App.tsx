import { BrowserRouter, Route, Routes } from 'react-router'

import { AuthProvider } from './auth/AuthContext'
import { useAuth } from './auth/useAuth'
import { AppLayout } from './layout/AppLayout'
import { MENU } from './navigation'
import { HomePage } from './pages/HomePage'
import { LoginPage } from './pages/LoginPage'
import { NoAccessPage, NotFoundPage, PlaceholderPage } from './pages/PlaceholderPage'

function AppRoutes() {
  const { status, can } = useAuth()

  if (status === 'loading') return <div className="splash">Loading…</div>
  if (status === 'anonymous') return <LoginPage />

  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<HomePage />} />
        {MENU.map((item) => (
          <Route
            key={item.path}
            path={item.path}
            element={can(item.permission) ? <PlaceholderPage item={item} /> : <NoAccessPage />}
          />
        ))}
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  )
}
