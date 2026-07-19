import { useEffect, useState } from 'react'
import { api, getCurrentUser, setCurrentUser } from '../api'
import type { ProjectSummary } from '../types'
import { navigate } from '../App'

export function HomeScreen() {
  const [users, setUsers] = useState<string[]>([])
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [currentUser, setUser] = useState(getCurrentUser())
  const [newUser, setNewUser] = useState('')
  const [showNewProject, setShowNewProject] = useState(false)
  const [projName, setProjName] = useState('')
  const [projDir, setProjDir] = useState('')
  const [error, setError] = useState('')

  const refresh = () => {
    api.listUsers().then(setUsers).catch((e) => setError(e.message))
    api.listProjects().then(setProjects).catch((e) => setError(e.message))
  }
  useEffect(refresh, [])

  const pickUser = (name: string) => {
    setCurrentUser(name)
    setUser(name)
  }

  const addUser = async () => {
    const name = newUser.trim()
    if (!name) return
    try {
      setUsers(await api.createUser(name))
      pickUser(name)
      setNewUser('')
      setError('')
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const createProject = async () => {
    try {
      await api.createProject(projName.trim(), projDir.trim())
      setShowNewProject(false)
      setProjName('')
      setProjDir('')
      setError('')
      refresh()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <div className="page">
      <div className="row spread">
        <h1>aiops annotate</h1>
        {currentUser && <span className="dim">signed in as <b>{currentUser}</b></span>}
      </div>
      {error && <p className="error">{error}</p>}

      <div className="card mt">
        <h2>Who's annotating?</h2>
        <div className="row wrap">
          {users.map((u) => (
            <button
              key={u}
              className={`chip ${u === currentUser ? 'active' : ''}`}
              onClick={() => pickUser(u)}
            >
              {u}
            </button>
          ))}
          <input
            placeholder="new user name"
            value={newUser}
            onChange={(e) => setNewUser(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addUser()}
          />
          <button onClick={addUser} disabled={!newUser.trim()}>
            Add user
          </button>
        </div>
      </div>

      <div className="row spread mt">
        <h2 style={{ margin: 0 }}>Projects</h2>
        <button className="primary" onClick={() => setShowNewProject(true)}>
          + New project
        </button>
      </div>

      {projects.length === 0 && (
        <p className="dim mt">No projects yet — create one from a directory of images.</p>
      )}
      <div className="mt" style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}>
        {projects.map((p) => (
          <div
            key={p.name}
            className="card clickable"
            onClick={() => {
              if (!currentUser) {
                setError('Pick or create a user first')
                return
              }
              navigate(`/p/${encodeURIComponent(p.name)}`)
            }}
          >
            <h3>{p.name}</h3>
            <div className="dim" style={{ fontSize: 12, wordBreak: 'break-all' }}>{p.images_dir}</div>
            <div className="row mt">
              <span className="dot done" />
              <span>
                {p.num_annotated} / {p.num_images} annotated
              </span>
            </div>
          </div>
        ))}
      </div>

      {showNewProject && (
        <div className="overlay" onClick={() => setShowNewProject(false)}>
          <div className="dialog" onClick={(e) => e.stopPropagation()}>
            <h2>New project</h2>
            <label>
              Project name
              <input
                style={{ width: '100%', marginTop: 4 }}
                value={projName}
                onChange={(e) => setProjName(e.target.value)}
                placeholder="my-dataset"
              />
            </label>
            <label>
              Images directory <span className="dim">(path on the server machine)</span>
              <input
                style={{ width: '100%', marginTop: 4 }}
                value={projDir}
                onChange={(e) => setProjDir(e.target.value)}
                placeholder="/home/me/datasets/images"
              />
            </label>
            {error && <p className="error">{error}</p>}
            <div className="row" style={{ justifyContent: 'flex-end' }}>
              <button onClick={() => setShowNewProject(false)}>Cancel</button>
              <button
                className="primary"
                onClick={createProject}
                disabled={!projName.trim() || !projDir.trim()}
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
