import { useCallback, useEffect, useState } from 'react'
import { api, getCurrentUser } from '../api'
import type { ImageInfo, ProjectMeta } from '../types'
import { navigate } from '../App'
import { AssignDialog } from './AssignDialog'
import { LabelsDialog } from './LabelsDialog'
import { ExportDialog } from './ExportDialog'

type Tab = 'mine' | 'all'

export function ProjectView({ project }: { project: string }) {
  const [meta, setMeta] = useState<ProjectMeta | null>(null)
  const [images, setImages] = useState<ImageInfo[]>([])
  const [allUsers, setAllUsers] = useState<string[]>([])
  const [tab, setTab] = useState<Tab>('mine')
  const [dialog, setDialog] = useState<'assign' | 'labels' | 'export' | null>(null)
  const [error, setError] = useState('')
  const currentUser = getCurrentUser()

  const refresh = useCallback(() => {
    api.getProject(project).then(setMeta).catch((e) => setError(e.message))
    api.listImages(project).then(setImages).catch((e) => setError(e.message))
    api.listUsers().then(setAllUsers).catch(() => {})
  }, [project])
  useEffect(refresh, [refresh])

  const visible = tab === 'mine' ? images.filter((i) => i.assigned_to === currentUser) : images
  const annotatedCount = images.filter((i) => i.annotated).length

  const reassign = async (filename: string, user: string) => {
    try {
      const updated = await api.reassign(project, filename, user)
      setMeta(updated)
      setImages((imgs) =>
        imgs.map((i) => (i.filename === filename ? { ...i, assigned_to: user || null } : i)),
      )
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const open = (filename: string) =>
    navigate(`/p/${encodeURIComponent(project)}/edit/${encodeURIComponent(filename)}`)

  return (
    <div className="page">
      <div className="row spread wrap">
        <div className="row">
          <button onClick={() => navigate('/')}>← Home</button>
          <h1 style={{ margin: 0 }}>{project}</h1>
        </div>
        <div className="row">
          <button onClick={() => setDialog('labels')}>Labels…</button>
          <button onClick={() => setDialog('assign')}>Assign images…</button>
          <button className="primary" onClick={() => setDialog('export')} disabled={!annotatedCount}>
            Export…
          </button>
        </div>
      </div>
      <p className="dim">
        {meta?.images_dir} — {annotatedCount} / {images.length} annotated
      </p>
      {error && <p className="error">{error}</p>}

      <div className="row mt">
        <button className={`chip ${tab === 'mine' ? 'active' : ''}`} onClick={() => setTab('mine')}>
          My queue ({images.filter((i) => i.assigned_to === currentUser).length})
        </button>
        <button className={`chip ${tab === 'all' ? 'active' : ''}`} onClick={() => setTab('all')}>
          All images ({images.length})
        </button>
      </div>

      <div className="card mt" style={{ padding: 0, overflow: 'hidden' }}>
        <table>
          <thead>
            <tr>
              <th style={{ width: 20 }}></th>
              <th>Image</th>
              <th>Size</th>
              <th>Shapes</th>
              <th>Assigned to</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {visible.map((img) => (
              <tr key={img.filename} className="clickable" onDoubleClick={() => open(img.filename)}>
                <td>
                  <span className={`dot ${img.annotated ? 'done' : ''}`} />
                </td>
                <td>{img.filename}</td>
                <td className="dim">
                  {img.width}×{img.height}
                </td>
                <td className="dim">{img.num_shapes || '—'}</td>
                <td onClick={(e) => e.stopPropagation()}>
                  <select
                    value={img.assigned_to ?? ''}
                    onChange={(e) => reassign(img.filename, e.target.value)}
                  >
                    <option value="">— unassigned —</option>
                    {allUsers.map((u) => (
                      <option key={u} value={u}>
                        {u}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <button onClick={() => open(img.filename)}>Annotate</button>
                </td>
              </tr>
            ))}
            {visible.length === 0 && (
              <tr>
                <td colSpan={6} className="dim" style={{ textAlign: 'center', padding: 24 }}>
                  {tab === 'mine'
                    ? 'No images assigned to you yet — use "Assign images…"'
                    : 'No images found in this directory'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {dialog === 'assign' && meta && (
        <AssignDialog
          project={project}
          allUsers={allUsers}
          onClose={() => setDialog(null)}
          onDone={() => {
            setDialog(null)
            refresh()
          }}
        />
      )}
      {dialog === 'labels' && meta && (
        <LabelsDialog
          project={project}
          labels={meta.labels}
          onClose={() => setDialog(null)}
          onSaved={(updated) => {
            setMeta(updated)
            setDialog(null)
          }}
        />
      )}
      {dialog === 'export' && (
        <ExportDialog project={project} onClose={() => setDialog(null)} />
      )}
    </div>
  )
}
