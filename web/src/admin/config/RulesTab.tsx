import { useState } from 'react'
import type { FormEvent } from 'react'

import { createRule, listConfigModules, listParameters, listRules, testRule, updateRule } from '../../api/admin'
import type { Module, Parameter, Rule, RuleTestResult } from '../../api/types'
import { parseInput } from '../../format'
import { ErrorText, Loading, Notice, StatusBadge } from '../ui'
import { errorMessage, useLoad } from '../useLoad'

export function RulesTab({ companyId }: { companyId: string }) {
  const rules = useLoad(() => listRules(companyId), [companyId])
  const parameters = useLoad(() => listParameters(companyId), [companyId])
  const modules = useLoad(() => listConfigModules(companyId), [companyId])
  const [editing, setEditing] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  if (!rules.data || !parameters.data || !modules.data) {
    const error = rules.error ?? parameters.error ?? modules.error
    return error ? <ErrorText message={error} /> : <Loading />
  }
  const current = rules.data.find((r) => r.code === editing) ?? null

  return (
    <>
      <p className="muted">
        Predicted-problem rules. A rule shows on a module&apos;s predicted-problems widget when its
        condition is true. Helpers: <code>value(&apos;k&apos;)</code>, <code>status(&apos;k&apos;)</code>,{' '}
        <code>off(&apos;k&apos;)</code>, <code>sev(&apos;k&apos;)</code>, <code>count_off([&apos;k1&apos;, &apos;k2&apos;])</code>,
        and the trend functions <code>rate(&apos;k&apos;, 24)</code>, <code>change(&apos;k&apos;, 6)</code>,{' '}
        <code>events(&apos;clean&apos;, 168)</code>, <code>coalesce(x, 0)</code>. A rule shows
        &ldquo;insufficient data&rdquo; until a value it needs exists or its trend has enough
        history. Probabilities are demo heuristics until trained models replace them.
      </p>
      {message && <Notice>{message}</Notice>}
      {editing ? (
        <RuleEditor
          key={editing}
          companyId={companyId}
          rule={editing === 'new' ? null : current}
          parameters={parameters.data}
          modules={modules.data}
          onClose={() => setEditing(null)}
          onSaved={(text) => {
            setMessage(text)
            setEditing(null)
            rules.reload()
          }}
        />
      ) : (
        <button className="button button--primary" onClick={() => setEditing('new')}>
          Add rule
        </button>
      )}
      <div className="card table-card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Title</th>
              <th>Condition</th>
              <th>Modules</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rules.data.map((r) => (
              <tr key={r.code} className={r.is_active ? undefined : 'row--inactive'}>
                <td className="nowrap">
                  <code>{r.code}</code> <span className="muted">v{r.version}</span>
                </td>
                <td>{r.title}</td>
                <td className="cell-text">
                  <code>{r.condition_expr}</code>
                </td>
                <td>{r.affects_modules.join(', ') || '–'}</td>
                <td>
                  <StatusBadge active={r.is_active} />
                </td>
                <td className="cell-actions">
                  <button className="button button--ghost button--small" onClick={() => setEditing(r.code)}>
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
  rule: Rule | null
  parameters: Parameter[]
  modules: Module[]
  onClose: () => void
  onSaved: (message: string) => void
}

function RuleEditor({ companyId, rule, parameters, modules, onClose, onSaved }: EditorProps) {
  const isNew = rule === null
  const inputs = parameters.filter((p) => p.is_active && p.kind === 'input')
  const [code, setCode] = useState(rule?.code ?? '')
  const [title, setTitle] = useState(rule?.title ?? '')
  const [condition, setCondition] = useState(rule?.condition_expr ?? '')
  const [probability, setProbability] = useState(rule?.probability_expr ?? '')
  const [action, setAction] = useState(rule?.action_text ?? '')
  const [affects, setAffects] = useState<Set<string>>(new Set(rule?.affects_modules ?? []))
  const [sortOrder, setSortOrder] = useState(String(rule?.sort_order ?? 0))
  const [active, setActive] = useState(rule?.is_active ?? true)
  const [testValues, setTestValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(inputs.map((p) => [p.key, p.sample_value === null ? '' : String(p.sample_value)])),
  )
  const [test, setTest] = useState<RuleTestResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function toggleModule(key: string) {
    setAffects((current) => {
      const next = new Set(current)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  async function runTest() {
    const values: Record<string, number | null> = {}
    for (const [key, text] of Object.entries(testValues)) {
      const parsed = parseInput(text)
      values[key] = parsed.ok ? parsed.value : null
    }
    setError(null)
    try {
      setTest(await testRule(companyId, { condition_expr: condition, probability_expr: probability || null, values }))
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const body = {
      title: title.trim(),
      condition_expr: condition.trim(),
      probability_expr: probability.trim(),
      action_text: action.trim(),
      affects_modules: [...affects],
      sort_order: Number(sortOrder),
    }
    setBusy(true)
    setError(null)
    try {
      if (isNew) {
        await createRule(companyId, { ...body, code: code.trim() })
        onSaved(`Rule ${code} was added. Add it to a module's predicted-problems widget to show it.`)
      } else {
        await updateRule(companyId, rule.code, { ...body, is_active: active })
        onSaved(`Rule ${rule.code} was saved.`)
      }
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card form-grid editor" onSubmit={handleSubmit}>
      <h2 className="form-grid__title">{isNew ? 'New rule' : `Edit ${rule.code}`}</h2>
      <label className="field">
        <span>Code</span>
        <input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} disabled={!isNew} required placeholder="e.g. TH-P03" />
      </label>
      <label className="field">
        <span>Title</span>
        <input value={title} onChange={(e) => setTitle(e.target.value)} required />
      </label>
      <label className="field form-grid__wide">
        <span>Condition (when is the problem predicted?)</span>
        <input
          className="formula-input"
          value={condition}
          onChange={(e) => {
            setCondition(e.target.value)
            setTest(null)
          }}
          required
          placeholder="e.g. off('dp') and count_off(['tds', 'sio2']) == 0"
        />
      </label>
      <label className="field form-grid__wide">
        <span>Probability % (demo heuristic)</span>
        <input
          className="formula-input"
          value={probability}
          onChange={(e) => {
            setProbability(e.target.value)
            setTest(null)
          }}
          required
          placeholder="e.g. min(95, 15 + sev('dp'))"
        />
      </label>
      <label className="field form-grid__wide">
        <span>Recommended action</span>
        <textarea rows={2} value={action} onChange={(e) => setAction(e.target.value)} />
      </label>
      <fieldset className="checks form-grid__wide">
        <legend>Modules it affects (used for alert “modules affected”)</legend>
        {modules.map((m) => (
          <label key={m.key}>
            <input type="checkbox" checked={affects.has(m.key)} onChange={() => toggleModule(m.key)} /> {m.title}
          </label>
        ))}
      </fieldset>
      <label className="field">
        <span>Display order</span>
        <input type="number" value={sortOrder} onChange={(e) => setSortOrder(e.target.value)} />
      </label>
      {!isNew && (
        <label className="checkbox">
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} /> Active
        </label>
      )}

      <details className="form-grid__wide test-box">
        <summary>Test with values (company default limits)</summary>
        <div className="test-values">
          {inputs.map((p) => (
            <label key={p.key} className="field">
              <small>
                {p.label} <code>{p.key}</code>
              </small>
              <input
                inputMode="decimal"
                value={testValues[p.key] ?? ''}
                onChange={(e) => setTestValues((v) => ({ ...v, [p.key]: e.target.value }))}
              />
            </label>
          ))}
        </div>
        <button type="button" className="button button--ghost" onClick={() => void runTest()} disabled={!condition.trim()}>
          Run test
        </button>
        {test && (
          <p className={test.ok ? 'ok-message' : 'form-error'}>
            {test.ok
              ? `${test.matched ? 'Matches' : 'Does not match'}${test.probability !== null ? ` · probability ${Math.round(test.probability)}%` : ''} (uses ${test.references.join(', ') || 'nothing'})`
              : test.error ?? 'Not enough data to evaluate (a referenced value is missing).'}
          </p>
        )}
      </details>

      <div className="form-grid__actions">
        <ErrorText message={error} />
        <button type="button" className="button button--ghost" onClick={onClose}>
          Cancel
        </button>
        <button className="button button--primary" type="submit" disabled={busy}>
          {busy ? 'Saving…' : 'Save rule'}
        </button>
      </div>
    </form>
  )
}
