import { useState } from 'react'
import type { FormEvent } from 'react'

import { createParameter, listParameters, testFormula, updateParameter } from '../../api/admin'
import type { FormulaTestResult, Parameter } from '../../api/types'
import { parseInput } from '../../format'
import { LIMIT_FIELDS, parseDraft, toDraft } from '../limits'
import type { LimitDraft } from '../limits'
import { ErrorText, Loading, Notice, StatusBadge } from '../ui'
import { errorMessage, useLoad } from '../useLoad'
import { useScrollToTop } from '../../components/scroll'

const limitsText = (p: Parameter) =>
  p.default_limits
    ? `${p.default_limits.warn_min} / ${p.default_limits.good_min} – ${p.default_limits.good_max} / ${p.default_limits.warn_max}`
    : '–'

export function ParametersTab({ companyId }: { companyId: string }) {
  const parameters = useLoad(() => listParameters(companyId), [companyId])
  // null = no editor open; 'new' = adding; otherwise the key being edited.
  const [editing, setEditing] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  if (!parameters.data) return parameters.error ? <ErrorText message={parameters.error} /> : <Loading />
  const current = parameters.data.find((p) => p.key === editing) ?? null

  return (
    <>
      {message && <Notice>{message}</Notice>}
      {editing ? (
        <ParameterEditor
          key={editing}
          companyId={companyId}
          parameter={editing === 'new' ? null : current}
          onClose={() => setEditing(null)}
          onSaved={(text) => {
            setMessage(text)
            setEditing(null)
            parameters.reload()
          }}
        />
      ) : (
        <button className="button button--primary" onClick={() => setEditing('new')}>
          Add parameter
        </button>
      )}
      <div className="card table-card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Key</th>
              <th>Label</th>
              <th>Group</th>
              <th>Kind / formula</th>
              <th>Default limits</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {parameters.data.map((p) => (
              <tr key={p.key} className={p.is_active ? undefined : 'row--inactive'}>
                <td>
                  <code>{p.key}</code>
                </td>
                <td>
                  {p.label}
                  {p.unit && <span className="muted"> ({p.unit})</span>}
                </td>
                <td>{p.group_key}</td>
                <td>
                  {p.kind === 'calculated' ? (
                    <>
                      <code>{p.formula}</code> <span className="muted">v{p.formula_version}</span>
                    </>
                  ) : (
                    <span className="muted">{p.formula ? 'measured (can be calculated)' : 'input'}</span>
                  )}
                </td>
                <td className="nowrap">{limitsText(p)}</td>
                <td>
                  <StatusBadge active={p.is_active} />
                </td>
                <td className="cell-actions">
                  <button className="button button--ghost button--small" onClick={() => setEditing(p.key)}>
                    Edit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

interface EditorProps {
  companyId: string
  parameter: Parameter | null
  onClose: () => void
  onSaved: (message: string) => void
}

function ParameterEditor({ companyId, parameter, onClose, onSaved }: EditorProps) {
  useScrollToTop()
  const isNew = parameter === null
  const [key, setKey] = useState(parameter?.key ?? '')
  const [label, setLabel] = useState(parameter?.label ?? '')
  const [unit, setUnit] = useState(parameter?.unit ?? '')
  const [group, setGroup] = useState(parameter?.group_key ?? 'calculated')
  const [kind, setKind] = useState<'input' | 'calculated'>(parameter?.kind ?? 'calculated')
  const [formula, setFormula] = useState(parameter?.formula ?? '')
  const [precision, setPrecision] = useState(String(parameter?.precision ?? 2))
  const [sortOrder, setSortOrder] = useState(String(parameter?.sort_order ?? 0))
  const [sample, setSample] = useState(parameter?.sample_value === null || parameter?.sample_value === undefined ? '' : String(parameter.sample_value))
  const [limits, setLimits] = useState<LimitDraft>(toDraft(parameter?.default_limits ?? null))
  const [active, setActive] = useState(parameter?.is_active ?? true)
  const [test, setTest] = useState<FormulaTestResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function runTest() {
    setError(null)
    try {
      setTest(await testFormula(companyId, formula))
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const parsedLimits = parseDraft(limits)
    if (parsedLimits && 'error' in parsedLimits) {
      setError(`Default limits: ${parsedLimits.error}`)
      return
    }
    const sampleValue = parseInput(sample)
    if (!sampleValue.ok) {
      setError('Sample value must be a number.')
      return
    }
    const body: Record<string, unknown> = {
      label: label.trim(),
      unit: unit.trim(),
      group_key: group.trim(),
      precision: Number(precision),
      sort_order: Number(sortOrder),
      sample_value: sampleValue.value,
      default_limits: parsedLimits ? parsedLimits.limits : null,
    }
    if (kind === 'calculated') body.formula = formula.trim()
    setBusy(true)
    setError(null)
    try {
      if (isNew) {
        await createParameter(companyId, { ...body, key: key.trim(), kind })
        onSaved(`Parameter ${key} was added. Add it to a module so plants can see it.`)
      } else {
        await updateParameter(companyId, parameter.key, { ...body, kind, is_active: active })
        onSaved(`Parameter ${parameter.key} was saved.`)
      }
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card form-grid editor" onSubmit={handleSubmit}>
      <h2 className="form-grid__title">{isNew ? 'New parameter' : `Edit ${parameter.key}`}</h2>
      <label className="field">
        <span>Key</span>
        <input value={key} onChange={(e) => setKey(e.target.value)} disabled={!isNew} required pattern="[a-z][a-z0-9_]*" />
        <small className="muted">Lower-case, used in formulas. Cannot be changed later.</small>
      </label>
      <label className="field">
        <span>Source</span>
        <select
          value={kind}
          onChange={(e) => {
            setKind(e.target.value as 'input' | 'calculated')
            setTest(null)
          }}
        >
          <option value="input">Measured (typed in or from PLC)</option>
          <option value="calculated">Calculated (formula)</option>
        </select>
        {!isNew && kind !== parameter.kind && (
          <small className="muted">
            {kind === 'input'
              ? 'The formula is kept, so you can switch back later.'
              : 'Inputs the formula needs are switched on automatically.'}
          </small>
        )}
      </label>
      <label className="field">
        <span>Label</span>
        <input value={label} onChange={(e) => setLabel(e.target.value)} required />
      </label>
      <label className="field">
        <span>Unit</span>
        <input value={unit} onChange={(e) => setUnit(e.target.value)} />
      </label>
      <label className="field">
        <span>Group</span>
        <input value={group} onChange={(e) => setGroup(e.target.value)} required />
        <small className="muted">e.g. chemistry, thermal, filter, calculated</small>
      </label>
      <label className="field">
        <span>Decimals</span>
        <input type="number" min={0} max={6} value={precision} onChange={(e) => setPrecision(e.target.value)} />
      </label>
      <label className="field">
        <span>Display order</span>
        <input type="number" value={sortOrder} onChange={(e) => setSortOrder(e.target.value)} />
      </label>
      <label className="field">
        <span>Sample value</span>
        <input inputMode="decimal" value={sample} onChange={(e) => setSample(e.target.value)} />
        <small className="muted">Used to test formulas and rules.</small>
      </label>

      {kind === 'calculated' && (
        <div className="field form-grid__wide">
          <span>Formula</span>
          <div className="formula-row">
            <input
              className="formula-input"
              value={formula}
              onChange={(e) => {
                setFormula(e.target.value)
                setTest(null)
              }}
              placeholder="e.g. tr - ts"
              required
            />
            <button type="button" className="button button--ghost" onClick={() => void runTest()} disabled={!formula.trim()}>
              Test
            </button>
          </div>
          <small className="muted">
            Allowed: + − × ÷ ** ( ), comparisons, and/or/not, min max abs round sqrt log log10 exp if_else
            coalesce. Over time: change(&apos;k&apos;, h), rate(&apos;k&apos;, h), avg, total, events(&apos;e&apos;, h),
            hours_since(&apos;e&apos;), event_interval(&apos;e&apos;), before_event(&apos;k&apos;, &apos;e&apos;), after_event(&apos;k&apos;, &apos;e&apos;)
            (h = hours; e = an on/off input such as cleaning). Plant values: setting(&apos;design_flow&apos;);
            known(&apos;k&apos;) is 1 when k has a value.
          </small>
          {test && (
            <p className={test.ok ? 'ok-message' : 'form-error'}>
              {test.ok
                ? `Result with sample values: ${test.result === null ? 'no data' : String(test.result)} (uses ${test.references.join(', ') || 'nothing'})`
                : test.error}
            </p>
          )}
        </div>
      )}

      <div className="field form-grid__wide">
        <span>Default limits (plants start with these; leave empty for none)</span>
        <div className="limit-inputs">
          {LIMIT_FIELDS.map((f) => (
            <label key={f.key} className="field">
              <small>{f.label}</small>
              <input
                inputMode="decimal"
                value={limits[f.key]}
                onChange={(e) => setLimits((l) => ({ ...l, [f.key]: e.target.value }))}
              />
            </label>
          ))}
        </div>
      </div>

      {!isNew && (
        <label className="checkbox form-grid__wide">
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} /> Active
          <small className="muted">
            {' '}
            (deactivating is blocked while a formula or rule uses it; history stays)
          </small>
        </label>
      )}

      <div className="form-grid__actions">
        <ErrorText message={error} />
        <button type="button" className="button button--ghost" onClick={onClose}>
          Cancel
        </button>
        <button className="button button--primary" type="submit" disabled={busy}>
          {busy ? 'Saving…' : 'Save parameter'}
        </button>
      </div>
    </form>
  )
}
