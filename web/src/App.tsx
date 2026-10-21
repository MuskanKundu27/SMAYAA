import { BrowserRouter, Route, Routes } from 'react-router'

import { AuthProvider } from './auth/AuthContext'
import { useAuth } from './auth/useAuth'
import { AppLayout } from './layout/AppLayout'
import { ModulePage } from './modules/ModulePage'
import { MENU } from './navigation'
import { HomePage } from './pages/HomePage'
import { LoginPage } from './pages/LoginPage'
import { NoAccessPage, NotFoundPage, PlaceholderPage } from './pages/PlaceholderPage'
import { PlantDataProvider } from './plant/PlantDataProvider'

function AppRoutes() {
  const { status, can } = useAuth()

  if (status === 'loading') return <div className="splash">Loading…</div>
  if (status === 'anonymous') return <LoginPage />

  return (
    <PlantDataProvider>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<HomePage />} />
          <Route
            path="/m/:moduleKey"
            element={can('modules.view') ? <ModulePage /> : <NoAccessPage />}
          />
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
    </PlantDataProvider>
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
