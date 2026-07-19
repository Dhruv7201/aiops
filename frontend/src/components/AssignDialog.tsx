import { useState } from 'react'
import { api } from '../api'

interface Props {
  project: string
  allUsers: string[]
  onClose: () => void
  onDone: () => void
}

export function AssignDialog({ project, allUsers, onClose, onDone }: Props) {
  const [selected, setSelected] = useState<string[]>([])
  const [keepExisting, setKeepExisting] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const toggle = (user: string) =>
    setSelected((s) => (s.includes(user) ? s.filter((u) => u !== user) : [...s, user]))

  const assign = async () => {
    setBusy(true)
    try {
      await api.assign(project, selected, keepExisting)
      onDone()
    } catch (e) {
      setError((e as Error).message)
      setBusy(false)
    }
  }

  return (
    <div className="overlay" onClick={onClose}>
      <div className="dialog" onClick={(e) => e.stopPropagation()}>
        <h2>Assign images</h2>
        <p className="dim">
          Divide the project's images equally (round-robin) among the selected users.
        </p>
        <div className="row wrap">
          {allUsers.map((u) => (
            <button
              key={u}
              className={`chip ${selected.includes(u) ? 'active' : ''}`}
              onClick={() => toggle(u)}
            >
              {u}
            </button>
          ))}
          {allUsers.length === 0 && <span className="dim">No users — create some on the home screen.</span>}
        </div>
        <label className="row">
          <input
            type="checkbox"
            checked={keepExisting}
            onChange={(e) => setKeepExisting(e.target.checked)}
          />
          Keep existing assignments (only distribute unassigned images)
        </label>
        {error && <p className="error">{error}</p>}
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          <button onClick={onClose}>Cancel</button>
          <button className="primary" onClick={assign} disabled={!selected.length || busy}>
            Assign equally
          </button>
        </div>
      </div>
    </div>
  )
}
