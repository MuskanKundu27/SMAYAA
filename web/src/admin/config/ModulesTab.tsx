import { useState } from 'react'
import type { FormEvent } from 'react'

import { createModule, listConfigModules, updateModule } from '../../api/admin'
import type { Module } from '../../api/types'
import { ErrorText, Loading, Notice, StatusBadge } from '../ui'
import { errorMessage, useLoad } from '../useLoad'
import { useScrollToTop } from '../../components/scroll'

const EXAMPLE = `{
  "widgets": [
    { "type": "value_tiles", "title": "KPIs", "params": ["appr", "range"] },
    { "type": "predicted_problems", "title": "Predicted problems", "rules": ["TH-P01"] }
  ]
}`

const WIDGET_HELP: [string, string][] = [
  ['input_group', '"group": "chemistry" or "params": [...] – editable tiles'],
  ['value_tiles', '"params": [...] – read-only KPI cards'],
  ['trend_chart', '"params": [...], "hours": 24, "ranges": [6, 24, 168, 720], "combine": true – history'],
  ['predicted_problems', '"rules": [...], "style": "table" – matching rules (table adds severity and ETA)'],
  ['recommended_actions', '"rules": [...] – action, priority and expected benefit of matching rules'],
  ['kpi_cards', '"items": [{"param", "target", "status_from", "caption", "delta", "delta_good"}], "style": "benefit"'],
  ['system_diagram', '"makeup", "blowdown", "sidestream": keys, "chemistry": [...] – tower picture'],
  ['quick_links', '"items": [{"label", "target": "limits" or "module:<key>"}] – buttons'],
  ['(any widget)', '"width": "full" | "half" | "third" | "quarter"'],
  ['alert_list', '"modules": [...] or "params": [...] (both optional)'],
  ['inputs_summary', '"params": [...] – compact list of inputs'],
  ['text_note', '"text": "..." – static text'],
]

export function ModulesTab({ companyId }: { companyId: string }) {
  const modules = useLoad(() => listConfigModules(companyId), [companyId])
  const [editing, setEditing] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])

  if (!modules.data) return modules.error ? <ErrorText message={modules.error} /> : <Loading />
  const current = modules.data.find((m) => m.key === editing) ?? null

  return (
    <>
      {message && <Notice>{message}</Notice>}
      {warnings.length > 0 && (
        <Notice tone="warn">
          Saved with references that show as “insufficient data”: {warnings.join('; ')}
        </Notice>
      )}
      {editing ? (
        <ModuleEditor
          key={editing}
          companyId={companyId}
          module={editing === 'new' ? null : current}
          onClose={() => setEditing(null)}
          onSaved={(saved) => {
            setMessage(`Module "${saved.title}" was saved.`)
            setWarnings(saved.warnings)
            setEditing(null)
            modules.reload()
          }}
        />
      ) : (
        <button className="button button--primary" onClick={() => setEditing('new')}>
          Add module
        </button>
      )}
      <div className="card table-card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Key</th>
              <th>Title</th>
              <th>Widgets</th>
              <th>Order</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {modules.data.map((m) => (
              <tr key={m.key} className={m.is_active ? undefined : 'row--inactive'}>
                <td>
                  <code>{m.key}</code>
                </td>
                <td>
                  {m.title}
                  {m.warnings.length > 0 && (
                    <span className="pill pill--warn" title={m.warnings.join('\n')}>
                      {' '}
                      {m.warnings.length} missing reference{m.warnings.length === 1 ? '' : 's'}
                    </span>
                  )}
                </td>
                <td>{m.layout.widgets?.length ?? 0}</td>
                <td>{m.sort_order}</td>
                <td>
                  <StatusBadge active={m.is_active} />
                </td>
                <td className="cell-actions">
                  <button className="button button--ghost button--small" onClick={() => setEditing(m.key)}>
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
  module: Module | null
  onClose: () => void
  onSaved: (module: Module) => void
}

function ModuleEditor({ companyId, module, onClose, onSaved }: EditorProps) {
  useScrollToTop()
  const isNew = module === null
  const [key, setKey] = useState(module?.key ?? '')
  const [title, setTitle] = useState(module?.title ?? '')
  const [sortOrder, setSortOrder] = useState(String(module?.sort_order ?? 0))
  const [active, setActive] = useState(module?.is_active ?? true)
  const [layoutText, setLayoutText] = useState(module ? JSON.stringify(module.layout, null, 2) : EXAMPLE)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    let layout: unknown
    try {
      layout = JSON.parse(layoutText)
    } catch (err) {
      setError(`Layout is not valid JSON: ${err instanceof Error ? err.message : ''}`)
      return
    }
    const body = { title: title.trim(), sort_order: Number(sortOrder), layout }
    setBusy(true)
    setError(null)
    try {
      const saved = isNew
        ? await createModule(companyId, { ...body, key: key.trim() })
        : await updateModule(companyId, module.key, { ...body, is_active: active })
      onSaved(saved)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card form-grid editor" onSubmit={handleSubmit}>
      <h2 className="form-grid__title">{isNew ? 'New module' : `Edit ${module.key}`}</h2>
      <label className="field">
        <span>Key</span>
        <input value={key} onChange={(e) => setKey(e.target.value)} disabled={!isNew} required pattern="[a-z][a-z0-9_]*" />
      </label>
      <label className="field">
        <span>Title (menu name)</span>
        <input value={title} onChange={(e) => setTitle(e.target.value)} required />
      </label>
      <label className="field">
        <span>Menu order</span>
        <input type="number" value={sortOrder} onChange={(e) => setSortOrder(e.target.value)} />
      </label>
      {!isNew && (
        <label className="checkbox">
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} /> Active (shown to plants)
        </label>
      )}
      <label className="field form-grid__wide">
        <span>Layout (JSON)</span>
        <textarea className="code-input" rows={16} value={layoutText} onChange={(e) => setLayoutText(e.target.value)} spellCheck={false} />
      </label>
      <details className="form-grid__wide">
        <summary>Widget types</summary>
        <ul className="change-list">
          {WIDGET_HELP.map(([type, help]) => (
            <li key={type}>
              <code>{type}</code>: {help}. Every widget can have a <code>&quot;title&quot;</code>.
            </li>
          ))}
        </ul>
      </details>
      <div className="form-grid__actions">
        <ErrorText message={error} />
        <button type="button" className="button button--ghost" onClick={onClose}>
          Cancel
        </button>
        <button className="button button--primary" type="submit" disabled={busy}>
          {busy ? 'Saving…' : 'Save module'}
        </button>
      </div>
    </form>
  )
}
