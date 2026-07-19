import { useState } from 'react'
import { api } from '../api'
import type { LabelDef, ProjectMeta } from '../types'
import { DEFAULT_LABEL_COLORS } from '../types'

interface Props {
  project: string
  labels: LabelDef[]
  onClose: () => void
  onSaved: (meta: ProjectMeta) => void
}

export function LabelsDialog({ project, labels, onClose, onSaved }: Props) {
  const [items, setItems] = useState<LabelDef[]>(labels)
  const [newName, setNewName] = useState('')
  const [error, setError] = useState('')

  const add = () => {
    const name = newName.trim()
    if (!name || items.some((l) => l.name === name)) return
    const color = DEFAULT_LABEL_COLORS[items.length % DEFAULT_LABEL_COLORS.length]
    setItems([...items, { name, color }])
    setNewName('')
  }

  const save = async () => {
    try {
      onSaved(await api.setLabels(project, items))
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <div className="overlay" onClick={onClose}>
      <div className="dialog" onClick={(e) => e.stopPropagation()}>
        <h2>Labels</h2>
        {items.map((label, i) => (
          <div key={i} className="row">
            <input
              type="color"
              value={label.color}
              onChange={(e) =>
                setItems(items.map((l, j) => (j === i ? { ...l, color: e.target.value } : l)))
              }
            />
            <input
              className="grow"
              value={label.name}
              onChange={(e) =>
                setItems(items.map((l, j) => (j === i ? { ...l, name: e.target.value } : l)))
              }
            />
            <button className="danger" onClick={() => setItems(items.filter((_, j) => j !== i))}>
              ✕
            </button>
          </div>
        ))}
        <div className="row">
          <input
            className="grow"
            placeholder="new label name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && add()}
          />
          <button onClick={add} disabled={!newName.trim()}>
            Add
          </button>
        </div>
        {error && <p className="error">{error}</p>}
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          <button onClick={onClose}>Cancel</button>
          <button className="primary" onClick={save}>
            Save labels
          </button>
        </div>
      </div>
    </div>
  )
}
