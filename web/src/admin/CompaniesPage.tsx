import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router'

import { createCompany, listCompanies, updateCompany } from '../api/admin'
import type { CompanyCreated } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { formatDateTime } from '../format'
import { ErrorText, Loading, Notice, StatusBadge } from './ui'
import { errorMessage, useLoad } from './useLoad'

export function CompaniesPage() {
  const { can } = useAuth()
  const companies = useLoad(listCompanies, [])
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function toggleActive(id: string, name: string, active: boolean) {
    const verb = active ? 'Deactivate' : 'Reactivate'
    if (!window.confirm(`${verb} ${name}? ${active ? 'Its users can no longer sign in.' : ''}`)) return
    setError(null)
    try {
      await updateCompany(id, { is_active: !active })
      setMessage(`${name} was ${active ? 'deactivated' : 'reactivated'}.`)
      companies.reload()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <>
      <h1>Companies</h1>
      {message && <Notice>{message}</Notice>}
      <ErrorText message={error ?? companies.error} />
      {can('companies.manage') && (
        <NewCompanyForm
          onCreated={(created) => {
            setMessage(
              `${created.company.name} was created with the default configuration. ` +
                `Company admin: ${created.admin.username}.`,
            )
            companies.reload()
          }}
        />
      )}

      <h2>All companies</h2>
      {!companies.data ? (
        <Loading />
      ) : companies.data.items.length === 0 ? (
        <p className="muted">No companies yet.</p>
      ) : (
        <div className="card table-card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Created</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {companies.data.items.map((c) => (
                <tr key={c.id} className={c.is_active ? undefined : 'row--inactive'}>
                  <td>{c.name}</td>
                  <td>{formatDateTime(c.created_at)}</td>
                  <td>
                    <StatusBadge active={c.is_active} />
                  </td>
                  <td className="cell-actions">
                    {can('config.manage') && (
                      <Link className="button button--ghost button--small" to={`/configuration?company=${c.id}`}>
                        Configure
                      </Link>
                    )}
                    {can('companies.manage') && (
                      <button
                        className="button button--ghost button--small"
                        onClick={() => void toggleActive(c.id, c.name, c.is_active)}
                      >
                        {c.is_active ? 'Deactivate' : 'Reactivate'}
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

function NewCompanyForm({ onCreated }: { onCreated: (created: CompanyCreated) => void }) {
  const [name, setName] = useState('')
  const [username, setUsername] = useState('')
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const created = await createCompany({
        name: name.trim(),
        admin: { username: username.trim(), full_name: fullName.trim(), password },
      })
      setName('')
      setUsername('')
      setFullName('')
      setPassword('')
      onCreated(created)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card form-grid" onSubmit={handleSubmit}>
      <h2 className="form-grid__title">Add a company</h2>
      <label className="field form-grid__wide">
        <span>Company name</span>
        <input value={name} onChange={(e) => setName(e.target.value)} required minLength={2} />
      </label>
      <p className="muted form-grid__wide">
        Its first company admin (they create plants, managers and operators):
      </p>
      <label className="field">
        <span>Admin username</span>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
          pattern="[A-Za-z0-9._\-]{3,50}"
          title="3–50 letters, digits, dots, underscores or hyphens (no spaces or @)"
        />
        <small className="muted">Letters, digits, . _ - only (no spaces or @).</small>
      </label>
      <label className="field">
        <span>Admin full name</span>
        <input value={fullName} onChange={(e) => setFullName(e.target.value)} />
      </label>
      <label className="field">
        <span>Admin password</span>
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
        <button className="button button--primary" type="submit" disabled={busy}>
          {busy ? 'Creating…' : 'Create company'}
        </button>
      </div>
    </form>
  )
}
