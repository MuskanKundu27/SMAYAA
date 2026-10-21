import { useState } from 'react'
import type { FormEvent } from 'react'

import { createPlant, listPlants, updatePlant } from '../api/admin'
import type { Plant } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { ErrorText, Loading, Notice, StatusBadge } from './ui'
import { errorMessage, useLoad } from './useLoad'

export function PlantsPage() {
  const { reloadMe } = useAuth()
  const plants = useLoad(listPlants, [])
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<string | null>(null)

  // Plants also appear in the plant switcher and user forms, which read GET /me.
  async function changed(text: string) {
    setMessage(text)
    setEditing(null)
    plants.reload()
    await reloadMe()
  }

  async function run(action: () => Promise<unknown>, text: string) {
    setError(null)
    try {
      await action()
      await changed(text)
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <>
      <h1>Plants</h1>
      {message && <Notice>{message}</Notice>}
      <ErrorText message={error ?? plants.error} />
      <NewPlantForm onCreated={(p) => void changed(`Plant "${p.name}" was created.`)} />

      <h2>Your plants</h2>
      {!plants.data ? (
        <Loading />
      ) : plants.data.items.length === 0 ? (
        <p className="muted">No plants yet.</p>
      ) : (
        <div className="card table-card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Location</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {plants.data.items.map((p) =>
                editing === p.id ? (
                  <EditPlantRow
                    key={p.id}
                    plant={p}
                    onCancel={() => setEditing(null)}
                    onSave={(body) => run(() => updatePlant(p.id, body), `Plant "${p.name}" was updated.`)}
                  />
                ) : (
                  <tr key={p.id} className={p.is_active ? undefined : 'row--inactive'}>
                    <td>{p.name}</td>
                    <td>{p.location || '–'}</td>
                    <td>
                      <StatusBadge active={p.is_active} />
                    </td>
                    <td className="cell-actions">
                      <button className="button button--ghost button--small" onClick={() => setEditing(p.id)}>
                        Edit
                      </button>
                      <button
                        className="button button--ghost button--small"
                        onClick={() => {
                          const verb = p.is_active ? 'Deactivate' : 'Reactivate'
                          if (window.confirm(`${verb} plant "${p.name}"?`)) {
                            void run(
                              () => updatePlant(p.id, { is_active: !p.is_active }),
                              `Plant "${p.name}" was ${p.is_active ? 'deactivated' : 'reactivated'}.`,
                            )
                          }
                        }}
                      >
                        {p.is_active ? 'Deactivate' : 'Reactivate'}
                      </button>
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

function NewPlantForm({ onCreated }: { onCreated: (plant: Plant) => void }) {
  const [name, setName] = useState('')
  const [location, setLocation] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const plant = await createPlant({ name: name.trim(), location: location.trim() })
      setName('')
      setLocation('')
      onCreated(plant)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card form-grid" onSubmit={handleSubmit}>
      <h2 className="form-grid__title">Add a plant</h2>
      <label className="field">
        <span>Name</span>
        <input value={name} onChange={(e) => setName(e.target.value)} required minLength={2} />
      </label>
      <label className="field">
        <span>Location</span>
        <input value={location} onChange={(e) => setLocation(e.target.value)} />
      </label>
      <div className="form-grid__actions">
        <ErrorText message={error} />
        <button className="button button--primary" type="submit" disabled={busy}>
          {busy ? 'Creating…' : 'Create plant'}
        </button>
      </div>
    </form>
  )
}

interface EditPlantRowProps {
  plant: Plant
  onCancel: () => void
  onSave: (body: { name: string; location: string }) => Promise<void>
}

function EditPlantRow({ plant, onCancel, onSave }: EditPlantRowProps) {
  const [name, setName] = useState(plant.name)
  const [location, setLocation] = useState(plant.location)
  return (
    <tr>
      <td>
        <input className="cell-input" value={name} onChange={(e) => setName(e.target.value)} aria-label="Name" />
      </td>
      <td>
        <input
          className="cell-input"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          aria-label="Location"
        />
      </td>
      <td>
        <StatusBadge active={plant.is_active} />
      </td>
      <td className="cell-actions">
        <button
          className="button button--primary button--small"
          onClick={() => void onSave({ name: name.trim(), location: location.trim() })}
        >
          Save
        </button>
        <button className="button button--ghost button--small" onClick={onCancel}>
          Cancel
        </button>
      </td>
    </tr>
  )
}
