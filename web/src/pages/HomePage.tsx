import { Link } from 'react-router'

import { useAuth } from '../auth/useAuth'
import { menuFor, roleLabel } from '../navigation'
import { usePlantData } from '../plant/usePlantData'

export function HomePage() {
  const { me, plant } = useAuth()
  const { modules } = usePlantData()
  if (!me) return null
  const items = menuFor(me.permissions)

  return (
    <>
      <h1>Welcome, {me.full_name || me.username}</h1>
      <div className="card">
        <dl className="facts">
          <dt>Role</dt>
          <dd>{me.roles.map(roleLabel).join(', ')}</dd>
          <dt>Company</dt>
          <dd>{me.company?.name ?? 'Platform (all companies)'}</dd>
          {plant && (
            <>
              <dt>Plant</dt>
              <dd>
                {plant.name}
                {plant.location && ` · ${plant.location}`}
              </dd>
            </>
          )}
        </dl>
      </div>

      <h2>You can open</h2>
      <div className="tile-grid">
        {modules.map((m) => (
          <Link key={m.key} to={`/m/${m.key}`} className="tile">
            <span className="tile__section">Module</span>
            <span className="tile__label">{m.title}</span>
          </Link>
        ))}
        {items.map((item) => (
          <Link key={item.path} to={item.path} className="tile">
            <span className="tile__section">{item.section}</span>
            <span className="tile__label">{item.label}</span>
          </Link>
        ))}
      </div>
    </>
  )
}
