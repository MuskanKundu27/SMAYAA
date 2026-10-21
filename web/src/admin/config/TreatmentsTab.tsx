import { useState } from 'react'
import type { FormEvent } from 'react'

import { listParameters, listTreatments, saveTreatments } from '../../api/admin'
import type { Direction, Treatment } from '../../api/types'
import { ErrorText, Loading, Notice } from '../ui'
import { errorMessage, useLoad } from '../useLoad'

interface Selection {
  parameterKey: string
  direction: Direction
}

export function TreatmentsTab({ companyId }: { companyId: string }) {
  const treatments = useLoad(() => listTreatments(companyId), [companyId])
  const parameters = useLoad(() => listParameters(companyId), [companyId])
  const [selection, setSelection] = useState<Selection | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  if (!treatments.data || !parameters.data) {
    const error = treatments.error ?? parameters.error
    return error ? <ErrorText message={error} /> : <Loading />
  }
  const labels = new Map(parameters.data.map((p) => [p.key, p.label]))
  const existing = selection
    ? (treatments.data.find(
        (t) => t.parameter_key === selection.parameterKey && t.direction === selection.direction,
      ) ?? null)
    : null

  return (
    <>
      <Notice tone="warn">
        Shipped texts are placeholders. A qualified water-treatment engineer must review them before
        real use; untick “needs review” once that is done.
      </Notice>
      <p className="muted">
        Shown with an alert when a value is too high or too low: likely cause, treatment and
        precautions.
      </p>
      {message && <Notice>{message}</Notice>}

      <PickTreatment
        parameters={parameters.data.filter((p) => p.is_active).map((p) => ({ key: p.key, label: p.label }))}
        onPick={setSelection}
      />
      {selection && (
        <TreatmentEditor
          key={`${selection.parameterKey}:${selection.direction}`}
          companyId={companyId}
          selection={selection}
          label={labels.get(selection.parameterKey) ?? selection.parameterKey}
          existing={existing}
          onClose={() => setSelection(null)}
          onSaved={() => {
            setMessage('Treatment saved.')
            setSelection(null)
            treatments.reload()
          }}
        />
      )}

      {treatments.data.length === 0 ? (
        <p className="muted">No treatments yet. Alerts then show generic advice.</p>
      ) : (
        <div className="card table-card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Parameter</th>
                <th>When</th>
                <th>Likely cause</th>
                <th>Review</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {treatments.data.map((t) => (
                <tr key={t.id}>
                  <td>{labels.get(t.parameter_key) ?? t.parameter_key}</td>
                  <td>{t.direction === 'high' ? 'Too high ↑' : 'Too low ↓'}</td>
                  <td className="cell-text">{t.cause || <span className="muted">–</span>}</td>
                  <td>
                    {t.needs_review ? <span className="pill pill--warn">Needs review</span> : <span className="pill pill--good">Reviewed</span>}
                  </td>
                  <td className="cell-actions">
                    <button
                      className="button button--ghost button--small"
                      onClick={() => setSelection({ parameterKey: t.parameter_key, direction: t.direction })}
                    >
                      Edit
                    </button>
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

function PickTreatment({
  parameters,
  onPick,
}: {
  parameters: { key: string; label: string }[]
  onPick: (s: Selection) => void
}) {
  const [parameterKey, setParameterKey] = useState(parameters[0]?.key ?? '')
  const [direction, setDirection] = useState<Direction>('high')
  return (
    <div className="filters">
      <label className="field">
        <span>Parameter</span>
        <select value={parameterKey} onChange={(e) => setParameterKey(e.target.value)}>
          {parameters.map((p) => (
            <option key={p.key} value={p.key}>
              {p.label}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>When the value is</span>
        <select value={direction} onChange={(e) => setDirection(e.target.value as Direction)}>
          <option value="high">Too high</option>
          <option value="low">Too low</option>
        </select>
      </label>
      <button className="button button--primary" disabled={!parameterKey} onClick={() => onPick({ parameterKey, direction })}>
        Add or edit
      </button>
    </div>
  )
}

interface EditorProps {
  companyId: string
  selection: Selection
  label: string
  existing: Treatment | null
  onClose: () => void
  onSaved: () => void
}

function TreatmentEditor({ companyId, selection, label, existing, onClose, onSaved }: EditorProps) {
  const [cause, setCause] = useState(existing?.cause ?? '')
  const [treatment, setTreatment] = useState(existing?.treatment ?? '')
  const [precautions, setPrecautions] = useState(existing?.precautions ?? '')
  const [needsReview, setNeedsReview] = useState(existing?.needs_review ?? true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await saveTreatments(companyId, [
        {
          parameter_key: selection.parameterKey,
          direction: selection.direction,
          cause,
          treatment,
          precautions,
          needs_review: needsReview,
        },
      ])
      onSaved()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card form-grid editor" onSubmit={handleSubmit}>
      <h2 className="form-grid__title">
        {label} – {selection.direction === 'high' ? 'too high' : 'too low'}
      </h2>
      <label className="field form-grid__wide">
        <span>Likely cause</span>
        <textarea rows={2} value={cause} onChange={(e) => setCause(e.target.value)} />
      </label>
      <label className="field form-grid__wide">
        <span>Treatment</span>
        <textarea rows={3} value={treatment} onChange={(e) => setTreatment(e.target.value)} />
      </label>
      <label className="field form-grid__wide">
        <span>Precautions</span>
        <textarea rows={2} value={precautions} onChange={(e) => setPrecautions(e.target.value)} />
      </label>
      <label className="checkbox form-grid__wide">
        <input type="checkbox" checked={needsReview} onChange={(e) => setNeedsReview(e.target.checked)} /> Needs review
        by a water-treatment engineer
      </label>
      <div className="form-grid__actions">
        <ErrorText message={error} />
        <button type="button" className="button button--ghost" onClick={onClose}>
          Cancel
        </button>
        <button className="button button--primary" type="submit" disabled={busy}>
          {busy ? 'Saving…' : 'Save treatment'}
        </button>
      </div>
    </form>
  )
}
