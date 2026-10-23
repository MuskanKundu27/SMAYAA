import { useState } from 'react'
import { useSearchParams } from 'react-router'

import { applyTemplate, listCompanies } from '../../api/admin'
import { ErrorText, Loading, Notice } from '../ui'
import { errorMessage, useLoad } from '../useLoad'
import { ModulesTab } from './ModulesTab'
import { ParametersTab } from './ParametersTab'
import { RulesTab } from './RulesTab'
import { TreatmentsTab } from './TreatmentsTab'

const TABS = [
  { key: 'parameters', label: 'Parameters & formulas' },
  { key: 'treatments', label: 'Treatments' },
  { key: 'rules', label: 'Rules' },
  { key: 'modules', label: 'Modules' },
  { key: 'template', label: 'Template' },
] as const
type TabKey = (typeof TABS)[number]['key']

/** Platform admin: everything a company can customise, stored as data (no code changes). */
export function ConfigurationPage() {
  const [params, setParams] = useSearchParams()
  const companies = useLoad(() => listCompanies().then((p) => p.items), [])
  const companyId = params.get('company') ?? ''
  const tab = (params.get('tab') as TabKey | null) ?? 'parameters'

  const choose = (next: { company?: string; tab?: string }) =>
    setParams({ company: next.company ?? companyId, tab: next.tab ?? tab })

  return (
    <>
      <h1>Configuration</h1>
      <ErrorText message={companies.error} />
      <label className="field field--inline">
        <span>Company</span>
        <select value={companyId} onChange={(e) => choose({ company: e.target.value })}>
          <option value="">Choose a company…</option>
          {(companies.data ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
              {c.is_active ? '' : ' (inactive)'}
            </option>
          ))}
        </select>
      </label>

      {!companyId ? (
        <p className="muted">Each company has its own parameters, formulas, limits, treatments, rules and screens.</p>
      ) : (
        <>
          <div className="tabs" role="tablist">
            {TABS.map((t) => (
              <button
                key={t.key}
                role="tab"
                aria-selected={tab === t.key}
                className={`tab ${tab === t.key ? 'tab--active' : ''}`}
                onClick={() => choose({ tab: t.key })}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div key={`${companyId}:${tab}`}>
            {tab === 'parameters' && <ParametersTab companyId={companyId} />}
            {tab === 'treatments' && <TreatmentsTab companyId={companyId} />}
            {tab === 'rules' && <RulesTab companyId={companyId} />}
            {tab === 'modules' && <ModulesTab companyId={companyId} />}
            {tab === 'template' && <TemplateTab companyId={companyId} />}
          </div>
        </>
      )}
      {companies.data === null && !companies.error && <Loading />}
    </>
  )
}

function TemplateTab({ companyId }: { companyId: string }) {
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function apply(updateExisting: boolean) {
    if (
      updateExisting &&
      !window.confirm(
        'Update this company to the latest template? The template’s own parameters, formulas, ' +
          'rules and module screens are replaced by the latest version, including any edits made ' +
          'to them here. Items this company added itself and treatment texts are kept.',
      )
    ) {
      return
    }
    setBusy(true)
    setError(null)
    try {
      const result = await applyTemplate(companyId, updateExisting)
      const describe = (counts: Record<string, number>) =>
        Object.entries(counts)
          .filter(([, n]) => n > 0)
          .map(([kind, n]) => `${n} ${kind}`)
          .join(', ')
      const added = describe(result.added)
      const updated = describe(result.updated ?? {})
      setMessage(
        [added && `Added ${added}.`, updated && `Updated ${updated}.`].filter(Boolean).join(' ') ||
          'Nothing to do: the company already matches the default template.',
      )
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card">
      <p>
        The <strong>default template</strong> holds the standard Input Parameters, Side-Stream Filtration
        and Thermal Efficiency setup: inputs, KPIs, rules and screens.
      </p>
      <ul className="change-list">
        <li>
          <strong>Add missing items</strong> adds only what this company doesn&apos;t have yet. It never
          changes the company&apos;s own edits.
        </li>
        <li>
          <strong>Update to latest template</strong> also brings the template&apos;s existing formulas,
          rules and screens up to date (for companies created before a template improvement). Formula and
          rule versions go up, so saved history is unchanged. The change is recorded in the audit log.
        </li>
      </ul>
      {message && <Notice>{message}</Notice>}
      <ErrorText message={error} />
      <div className="form-grid__actions">
        <button className="button button--ghost" onClick={() => void apply(true)} disabled={busy}>
          Update to latest template
        </button>
        <button className="button button--primary" onClick={() => void apply(false)} disabled={busy}>
          {busy ? 'Working…' : 'Add missing items'}
        </button>
      </div>
    </div>
  )
}
