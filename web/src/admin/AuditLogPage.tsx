import { useState } from 'react'

import { listAuditLog, listCompanies } from '../api/admin'
import type { AuditEntry, Company } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { formatDateTime } from '../format'
import { ErrorText, Loading } from './ui'
import { useLoad } from './useLoad'

const ENTITIES = [
  'company',
  'plant',
  'user',
  'parameter',
  'treatment',
  'rule',
  'module',
  'operator_profile',
]
const NO_COMPANIES: Company[] = []
const PAGE_SIZE = 50

export function AuditLogPage() {
  const { me } = useAuth()
  const isPlatform = !me?.company
  const [companyId, setCompanyId] = useState('')
  const [entity, setEntity] = useState('')
  const [offset, setOffset] = useState(0)
  const log = useLoad(() => listAuditLog({ companyId, entity, offset }), [companyId, entity, offset])
  const companies = useLoad(
    () => (isPlatform ? listCompanies().then((p) => p.items) : Promise.resolve(NO_COMPANIES)),
    [isPlatform],
  )

  const total = log.data?.total ?? 0

  return (
    <>
      <h1>Audit log</h1>
      <p className="muted">Every change to companies, plants, users, limits and configuration, newest first.</p>
      <div className="filters">
        {isPlatform && (
          <label className="field">
            <span>Company</span>
            <select
              value={companyId}
              onChange={(e) => {
                setCompanyId(e.target.value)
                setOffset(0)
              }}
            >
              <option value="">All companies</option>
              {(companies.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="field">
          <span>What changed</span>
          <select
            value={entity}
            onChange={(e) => {
              setEntity(e.target.value)
              setOffset(0)
            }}
          >
            <option value="">Everything</option>
            {ENTITIES.map((e) => (
              <option key={e} value={e}>
                {e.replace('_', ' ')}
              </option>
            ))}
          </select>
        </label>
      </div>
      <ErrorText message={log.error} />
      {!log.data ? (
        <Loading />
      ) : log.data.items.length === 0 ? (
        <p className="muted">Nothing recorded yet.</p>
      ) : (
        <>
          <div className="card table-card">
            <table className="data-table">
              <thead>
                <tr>
                  <th>When</th>
                  {isPlatform && <th>Company</th>}
                  <th>Who</th>
                  <th>Action</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {log.data.items.map((entry) => (
                  <tr key={entry.id}>
                    <td className="nowrap">{formatDateTime(entry.created_at)}</td>
                    {isPlatform && <td>{entry.company_name ?? 'Platform'}</td>}
                    <td>{entry.actor_name}</td>
                    <td>
                      <code>{entry.action}</code>
                    </td>
                    <td>
                      <ChangeDetails entry={entry} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pager">
            <button className="button button--ghost" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
              Newer
            </button>
            <span className="muted">
              {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
            </span>
            <button
              className="button button--ghost"
              disabled={offset + PAGE_SIZE >= total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              Older
            </button>
          </div>
        </>
      )}
    </>
  )
}

/** Fields that differ between before and after, or the whole "after" for new items. */
function ChangeDetails({ entry }: { entry: AuditEntry }) {
  const before = entry.before ?? {}
  const after = entry.after ?? {}
  const keys = [...new Set([...Object.keys(before), ...Object.keys(after)])].filter(
    (k) => JSON.stringify(before[k]) !== JSON.stringify(after[k]),
  )
  if (keys.length === 0) return <span className="muted">–</span>
  const show = (value: unknown) => (value === undefined ? '–' : JSON.stringify(value))
  return (
    <details>
      <summary>
        {keys.slice(0, 3).join(', ')}
        {keys.length > 3 ? ` +${keys.length - 3}` : ''}
      </summary>
      <ul className="change-list">
        {keys.map((k) => (
          <li key={k}>
            <strong>{k}</strong>: {entry.before ? `${show(before[k])} → ` : ''}
            {show(after[k])}
          </li>
        ))}
      </ul>
    </details>
  )
}
