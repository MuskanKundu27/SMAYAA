import type { ReactNode } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router'

import { AuditLogPage } from './admin/AuditLogPage'
import { CompaniesPage } from './admin/CompaniesPage'
import { ConfigurationPage } from './admin/config/ConfigurationPage'
import { LimitsPage } from './admin/LimitsPage'
import { OperatorProfilesPage } from './admin/OperatorProfilesPage'
import { PlantsPage } from './admin/PlantsPage'
import { UsersPage } from './admin/UsersPage'
import { AuthProvider } from './auth/AuthContext'
import { useAuth } from './auth/useAuth'
import { AppLayout } from './layout/AppLayout'
import { ModulePage } from './modules/ModulePage'
import { MENU } from './navigation'
import { HomePage } from './pages/HomePage'
import { LoginPage } from './pages/LoginPage'
import { NoAccessPage, NotFoundPage } from './pages/StatusPages'
import { PlantDataProvider } from './plant/PlantDataProvider'

// The screen for each fixed menu entry (navigation.ts). The API checks permissions again.
const PAGES: Record<string, ReactNode> = {
  '/limits': <LimitsPage />,
  '/operator-profiles': <OperatorProfilesPage />,
  '/users': <UsersPage />,
  '/plants': <PlantsPage />,
  '/companies': <CompaniesPage />,
  '/configuration': <ConfigurationPage />,
  '/audit-log': <AuditLogPage />,
}

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
              element={can(item.permission) ? (PAGES[item.path] ?? <NotFoundPage />) : <NoAccessPage />}
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
