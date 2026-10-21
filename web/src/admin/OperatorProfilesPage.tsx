import { useState } from 'react'

import { listOperatorProfiles, resetOperatorProfile, saveOperatorProfile } from '../api/admin'
import { listModules } from '../api/plant'
import type { ModuleSummary, OperatorProfile } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { roleLabel } from '../navigation'
import { ErrorText, Loading, Notice } from './ui'
import { errorMessage, useLoad } from './useLoad'

export function OperatorProfilesPage() {
  const { plant } = useAuth()
  if (!plant) return <p className="muted">Select a plant first.</p>
  return <ProfilesScreen key={plant.id} plantId={plant.id} plantName={plant.name} />
}

function ProfilesScreen({ plantId, plantName }: { plantId: string; plantName: string }) {
  const profiles = useLoad(() => listOperatorProfiles(plantId), [plantId])
  const modules = useLoad(() => listModules(plantId), [plantId])

  return (
    <>
      <h1>Operator profiles · {plantName}</h1>
      <p className="muted">
        New operators can see every module, see alerts and enter readings. Restrict them here. The
        server enforces these settings, not just the menu.
      </p>
      <ErrorText message={profiles.error ?? modules.error} />
      {!profiles.data || !modules.data ? (
        <Loading />
      ) : profiles.data.length === 0 ? (
        <p className="muted">No operators at this plant yet. Add them on the Users page.</p>
      ) : (
        <div className="profile-list">
          {profiles.data.map((p) => (
            <ProfileCard key={p.user_id} plantId={plantId} profile={p} modules={modules.data ?? []} onSaved={profiles.reload} />
          ))}
        </div>
      )}
    </>
  )
}

interface ProfileCardProps {
  plantId: string
  profile: OperatorProfile
  modules: ModuleSummary[]
  onSaved: () => void
}

function ProfileCard({ plantId, profile, modules, onSaved }: ProfileCardProps) {
  const [allModules, setAllModules] = useState(profile.visible_modules === null)
  const [selected, setSelected] = useState<Set<string>>(new Set(profile.visible_modules ?? modules.map((m) => m.key)))
  const [canEdit, setCanEdit] = useState(profile.can_edit_readings)
  const [showAlerts, setShowAlerts] = useState(profile.show_alerts)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function toggle(key: string) {
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  async function run(action: () => Promise<unknown>, text: string) {
    setBusy(true)
    setError(null)
    try {
      await action()
      setMessage(text)
      onSaved()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const save = () =>
    run(
      () =>
        saveOperatorProfile(plantId, profile.user_id, {
          visible_modules: allModules ? null : [...selected],
          can_edit_readings: canEdit,
          show_alerts: showAlerts,
        }),
      'Saved. It applies on the operator’s next screen refresh.',
    )

  const reset = () => {
    setAllModules(true)
    setCanEdit(true)
    setShowAlerts(true)
    return run(() => resetOperatorProfile(plantId, profile.user_id), 'Back to defaults: everything allowed.')
  }

  return (
    <div className="card profile-card">
      <div className="profile-card__head">
        <div>
          <strong>{profile.full_name || profile.username}</strong>{' '}
          <span className="muted">
            {profile.username} · {profile.roles.map(roleLabel).join(', ')}
          </span>
        </div>
        <span className={`pill ${profile.is_default ? 'pill--good' : 'pill--warn'}`}>
          {profile.is_default ? 'Defaults' : 'Restricted'}
        </span>
      </div>

      <fieldset className="checks">
        <legend>Modules</legend>
        <label>
          <input type="checkbox" checked={allModules} onChange={(e) => setAllModules(e.target.checked)} /> All modules
          (including ones added later)
        </label>
        {!allModules &&
          modules.map((m) => (
            <label key={m.key} className="checks__indent">
              <input type="checkbox" checked={selected.has(m.key)} onChange={() => toggle(m.key)} /> {m.title}
            </label>
          ))}
      </fieldset>

      <fieldset className="checks">
        <legend>Permissions</legend>
        <label>
          <input type="checkbox" checked={canEdit} onChange={(e) => setCanEdit(e.target.checked)} /> May enter and edit
          readings
        </label>
        <label>
          <input type="checkbox" checked={showAlerts} onChange={(e) => setShowAlerts(e.target.checked)} /> Sees alerts
        </label>
      </fieldset>

      {message && <Notice>{message}</Notice>}
      <ErrorText message={error} />
      <div className="profile-card__actions">
        {!profile.is_default && (
          <button className="button button--ghost" onClick={() => void reset()} disabled={busy}>
            Reset to defaults
          </button>
        )}
        <button className="button button--primary" onClick={() => void save()} disabled={busy || (!allModules && selected.size === 0)}>
          Save
        </button>
      </div>
    </div>
  )
}
