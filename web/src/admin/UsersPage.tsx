import { useState } from 'react'
import type { FormEvent } from 'react'

import { createUser, deactivateUser, listCompanies, listUsers } from '../api/admin'
import type { Company, User } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { manageableRoles, roleLabel, roleNeedsPlant } from '../navigation'
import { ErrorText, Loading, Notice, StatusBadge } from './ui'
import { errorMessage, useLoad } from './useLoad'

const NO_COMPANIES: Company[] = []

export function UsersPage() {
  const { me, can } = useAuth()
  const isPlatform = !me?.company
  const users = useLoad(listUsers, [])
  const companies = useLoad(
    () => (isPlatform ? listCompanies().then((p) => p.items) : Promise.resolve(NO_COMPANIES)),
    [isPlatform],
  )
  const [messages, setMessages] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)

  if (!me) return null
  const roles = manageableRoles(me.permissions)
  const plantName = new Map(me.plants.map((p) => [p.id, p.name]))
  const companyName = new Map((companies.data ?? []).map((c) => [c.id, c.name]))

  async function handleDeactivate(user: User) {
    const ok = window.confirm(
      `Deactivate ${user.username}? They are signed out immediately. Their name stays on past data.`,
    )
    if (!ok) return
    setError(null)
    try {
      const result = await deactivateUser(user.id)
      setMessages([`${user.username} was deactivated.`, ...result.warnings])
      users.reload()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  const canDeactivate = (user: User) =>
    user.is_active && user.id !== me.id && user.roles.every((r) => roles.includes(r))

  return (
    <>
      <h1>Users</h1>
      {messages.map((m) => (
        <Notice key={m} tone={m.includes('no manager') ? 'warn' : 'info'}>
          {m}
        </Notice>
      ))}
      <ErrorText message={error ?? users.error} />

      {roles.length > 0 && can('users.read') && (
        <NewUserForm
          roles={roles}
          isPlatform={isPlatform}
          plants={me.plants}
          companies={companies.data ?? []}
          onCreated={(user) => {
            setMessages([`${user.username} was created.`])
            users.reload()
          }}
        />
      )}

      <h2>All users</h2>
      {!users.data ? (
        <Loading />
      ) : (
        <div className="card table-card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Username</th>
                <th>Name</th>
                <th>Role</th>
                <th>{isPlatform ? 'Company' : 'Plant'}</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {users.data.items.map((u) => (
                <tr key={u.id} className={u.is_active ? undefined : 'row--inactive'}>
                  <td>{u.username}</td>
                  <td>{u.full_name}</td>
                  <td>{u.roles.map(roleLabel).join(', ')}</td>
                  <td>
                    {isPlatform
                      ? (u.company_id && companyName.get(u.company_id)) || '–'
                      : u.plant_ids.map((id) => plantName.get(id) ?? 'Other plant').join(', ') ||
                        'All plants'}
                  </td>
                  <td>
                    <StatusBadge active={u.is_active} />
                  </td>
                  <td className="cell-actions">
                    {canDeactivate(u) && (
                      <button className="button button--ghost button--small" onClick={() => void handleDeactivate(u)}>
                        Deactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

interface NewUserFormProps {
  roles: string[]
  isPlatform: boolean
  plants: { id: string; name: string }[]
  companies: Company[]
  onCreated: (user: User) => void
}

function NewUserForm({ roles, isPlatform, plants, companies, onCreated }: NewUserFormProps) {
  const [role, setRole] = useState(roles[roles.length - 1] ?? '')
  const [username, setUsername] = useState('')
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const [plantId, setPlantId] = useState(plants[0]?.id ?? '')
  const [companyId, setCompanyId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const needsPlant = roleNeedsPlant(role)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const user = await createUser({
        username: username.trim(),
        full_name: fullName.trim(),
        password,
        role,
        plant_id: needsPlant ? plantId || null : null,
        company_id: !needsPlant && isPlatform ? companyId || null : null,
      })
      setUsername('')
      setFullName('')
      setPassword('')
      onCreated(user)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card form-grid" onSubmit={handleSubmit}>
      <h2 className="form-grid__title">Add a user</h2>
      <label className="field">
        <span>Role</span>
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          {roles.map((r) => (
            <option key={r} value={r}>
              {roleLabel(r)}
            </option>
          ))}
        </select>
      </label>
      {needsPlant ? (
        <label className="field">
          <span>Plant</span>
          <select value={plantId} onChange={(e) => setPlantId(e.target.value)} required>
            {plants.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
      ) : (
        isPlatform && (
          <label className="field">
            <span>Company</span>
            <select value={companyId} onChange={(e) => setCompanyId(e.target.value)} required>
              <option value="">Choose…</option>
              {companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
        )
      )}
      <label className="field">
        <span>Username</span>
        <input value={username} onChange={(e) => setUsername(e.target.value)} required minLength={3} />
      </label>
      <label className="field">
        <span>Full name</span>
        <input value={fullName} onChange={(e) => setFullName(e.target.value)} />
      </label>
      <label className="field">
        <span>Password</span>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
          required
        />
        <small className="muted">At least 10 characters, with a letter and a digit.</small>
      </label>
      <div className="form-grid__actions">
        <ErrorText message={error} />
        <button className="button button--primary" type="submit" disabled={busy || (needsPlant && !plantId)}>
          {busy ? 'Creating…' : 'Create user'}
        </button>
      </div>
      {needsPlant && plants.length === 0 && <p className="muted">Create a plant first.</p>}
    </form>
  )
}
