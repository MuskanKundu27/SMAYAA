import { NavLink, Outlet } from 'react-router'

import { useAuth } from '../auth/useAuth'
import { menuFor, roleLabel } from '../navigation'
import type { MenuItem } from '../navigation'

const SECTIONS: MenuItem['section'][] = ['Modules', 'Plant', 'Administration']

export function AppLayout() {
  const { me, plant, selectPlant, logout } = useAuth()
  if (!me) return null
  const items = menuFor(me.permissions)

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand__mark">S</span>
          <div className="brand__name">SMAYAA.ai</div>
        </div>
        <nav>
          <NavLink to="/" end className="nav-link">
            Home
          </NavLink>
          {SECTIONS.map((section) => {
            const sectionItems = items.filter((item) => item.section === section)
            if (sectionItems.length === 0) return null
            return (
              <div key={section} className="nav-section">
                <div className="nav-section__title">{section}</div>
                {sectionItems.map((item) => (
                  <NavLink key={item.path} to={item.path} className="nav-link">
                    {item.label}
                  </NavLink>
                ))}
              </div>
            )
          })}
        </nav>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="topbar__context">
            {me.company && <span className="topbar__company">{me.company.name}</span>}
            {me.plants.length > 1 ? (
              <select
                className="plant-select"
                aria-label="Plant"
                value={plant?.id ?? ''}
                onChange={(e) => selectPlant(e.target.value)}
              >
                {me.plants.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            ) : (
              plant && <span className="topbar__plant">{plant.name}</span>
            )}
          </div>
          <div className="topbar__user">
            <span>
              {me.full_name || me.username}
              <span className="role-badge">{me.roles.map(roleLabel).join(', ')}</span>
            </span>
            <button className="button button--ghost" onClick={() => void logout()}>
              Log out
            </button>
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
