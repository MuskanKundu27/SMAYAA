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

  async function apply() {
    setBusy(true)
    setError(null)
    try {
      const result = await applyTemplate(companyId)
      const added = Object.entries(result.added).filter(([, n]) => n > 0)
      setMessage(
        added.length === 0
          ? 'Nothing was missing: the company already has everything in the default template.'
          : `Added ${added.map(([kind, n]) => `${n} ${kind}`).join(', ')}.`,
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
        The <strong>default template</strong> holds the standard Water Chemistry, Filter and Thermal setup.
        Applying it adds only what this company is missing (matched by key or code). It never changes
        or removes the company&apos;s own edits.
      </p>
      {message && <Notice>{message}</Notice>}
      <ErrorText message={error} />
      <button className="button button--primary" onClick={() => void apply()} disabled={busy}>
        {busy ? 'Applying…' : 'Apply default template'}
      </button>
    </div>
  )
}
