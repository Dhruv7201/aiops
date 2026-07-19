import { useCallback, useEffect, useReducer, useRef, useState } from 'react'
import { api } from '../api'
import type { ImageInfo, LabelMeDoc, ProjectMeta, Shape, ShapeType } from '../types'
import { newShape } from '../types'
import { editorReducer, initialEditorState } from '../state/editorReducer'
import { clampShape, translateShape } from '../canvas/geometry'
import { AnnotationCanvas } from './AnnotationCanvas'
import type { Tool } from './AnnotationCanvas'
import { ShapeList } from './ShapeList'
import { LabelPicker } from './LabelPicker'
import { navigate } from '../App'

const CLIPBOARD_KEY = 'aiops.annotate.clipboard'
const DEFAULT_LABEL = 'object'

interface Props {
  project: string
  filename: string
}

export function AnnotationEditor({ project, filename }: Props) {
  const [meta, setMeta] = useState<ProjectMeta | null>(null)
  const [images, setImages] = useState<ImageInfo[]>([])
  const [doc, setDoc] = useState<LabelMeDoc | null>(null)
  const [tool, setTool] = useState<Tool>('rectangle')
  const [currentLabel, setCurrentLabel] = useState('')
  const [error, setError] = useState('')
  const [state, dispatch] = useReducer(editorReducer, initialEditorState)
  const pasteCount = useRef(0)

  // Refs so async/cleanup callbacks see the latest state without re-subscribing
  const stateRef = useRef(state)
  stateRef.current = state
  const docRef = useRef(doc)
  docRef.current = doc

  const labels = meta?.labels ?? []
  const labelColors = new Map(labels.map((l) => [l.name, l.color]))
  const imageIndex = images.findIndex((i) => i.filename === filename)

  // -- loading --

  useEffect(() => {
    api.getProject(project)
      .then((m) => {
        setMeta(m)
        if (m.labels.length) setCurrentLabel((l) => l || m.labels[0].name)
      })
      .catch((e) => setError(e.message))
    api.listImages(project).then(setImages).catch((e) => setError(e.message))
  }, [project])

  useEffect(() => {
    setDoc(null)
    pasteCount.current = 0
    api.getAnnotation(project, filename)
      .then((d) => {
        setDoc(d)
        dispatch({ type: 'LOAD', shapes: d.shapes })
      })
      .catch((e) => setError(e.message))
  }, [project, filename])

  // -- saving --

  const save = useCallback(async () => {
    const s = stateRef.current
    const d = docRef.current
    if (!d || !s.dirty) return
    try {
      await api.saveAnnotation(project, filename, { ...d, shapes: s.shapes })
      dispatch({ type: 'MARK_SAVED' })
      setImages((imgs) =>
        imgs.map((i) =>
          i.filename === filename
            ? { ...i, annotated: s.shapes.length > 0, num_shapes: s.shapes.length }
            : i,
        ),
      )
    } catch (e) {
      setError((e as Error).message)
      throw e
    }
  }, [project, filename])

  // Warn about unsaved changes when closing the tab
  useEffect(() => {
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (stateRef.current.dirty) e.preventDefault()
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [])

  const goTo = useCallback(
    async (target: string) => {
      try {
        await save() // autosave before navigating
      } catch {
        return // stay here if the save failed
      }
      navigate(target)
    },
    [save],
  )

  const goToImage = useCallback(
    (idx: number) => {
      if (idx < 0 || idx >= images.length) return
      void goTo(`/p/${encodeURIComponent(project)}/edit/${encodeURIComponent(images[idx].filename)}`)
    },
    [images, project, goTo],
  )

  // -- shape creation / clipboard --

  const effectiveLabel = currentLabel || labels[0]?.name || DEFAULT_LABEL

  const addShape = useCallback(
    (points: number[][], shapeType: ShapeType) => {
      dispatch({ type: 'ADD_SHAPE', shape: newShape(effectiveLabel, points, shapeType) })
    },
    [effectiveLabel],
  )

  const copySelected = useCallback(() => {
    const s = stateRef.current
    const shapes = s.selected.map((i) => s.shapes[i]).filter(Boolean)
    if (shapes.length) {
      localStorage.setItem(CLIPBOARD_KEY, JSON.stringify(shapes))
      pasteCount.current = 0
    }
  }, [])

  const paste = useCallback(() => {
    const d = docRef.current
    const raw = localStorage.getItem(CLIPBOARD_KEY)
    if (!raw || !d) return
    try {
      const shapes = JSON.parse(raw) as Shape[]
      pasteCount.current += 1
      const offset = 10 * pasteCount.current
      dispatch({
        type: 'PASTE',
        shapes: shapes.map((s) =>
          clampShape(translateShape(s, offset, offset), d.imageWidth, d.imageHeight),
        ),
      })
    } catch {
      /* bad clipboard content — ignore */
    }
  }, [])

  // -- keyboard shortcuts --

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes(target.tagName)) return

      if (e.ctrlKey || e.metaKey) {
        const k = e.key.toLowerCase()
        if (k === 'z' && e.shiftKey) dispatch({ type: 'REDO' })
        else if (k === 'z') dispatch({ type: 'UNDO' })
        else if (k === 'y') dispatch({ type: 'REDO' })
        else if (k === 'c') copySelected()
        else if (k === 'v') paste()
        else if (k === 's') void save()
        else return
        e.preventDefault()
        return
      }

      switch (e.key) {
        case 'r':
        case 'R':
          setTool('rectangle')
          break
        case 'p':
        case 'P':
          setTool('polygon')
          break
        case 's':
        case 'S':
          setTool('select')
          break
        case 'Escape':
          setTool('select')
          break
        case 'Delete':
          dispatch({ type: 'DELETE_SELECTED' })
          break
        case 'ArrowLeft':
        case 'a':
        case 'A':
          goToImage(imageIndex - 1)
          break
        case 'ArrowRight':
        case 'd':
        case 'D':
          goToImage(imageIndex + 1)
          break
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [copySelected, paste, save, goToImage, imageIndex])

  // -- render --

  return (
    <div className="editor">
      <div className="toolbar">
        <button onClick={() => void goTo(`/p/${encodeURIComponent(project)}`)}>← {project}</button>
        <b>{filename}</b>
        <span className="dim">
          {imageIndex + 1}/{images.length}
        </span>
        <div className="sep" />
        <button
          className={tool === 'select' ? 'active' : ''}
          title="Select / move (S)"
          onClick={() => setTool('select')}
        >
          ☰ Select
        </button>
        <button
          className={tool === 'rectangle' ? 'active' : ''}
          title="Rectangle (R)"
          onClick={() => setTool('rectangle')}
        >
          ▭ Rect
        </button>
        <button
          className={tool === 'polygon' ? 'active' : ''}
          title="Polygon (P)"
          onClick={() => setTool('polygon')}
        >
          ⬠ Polygon
        </button>
        <div className="sep" />
        <button
          className="icon-btn"
          title="Undo (Ctrl+Z)"
          disabled={!state.past.length}
          onClick={() => dispatch({ type: 'UNDO' })}
        >
          ↶
        </button>
        <button
          className="icon-btn"
          title="Redo (Ctrl+Shift+Z)"
          disabled={!state.future.length}
          onClick={() => dispatch({ type: 'REDO' })}
        >
          ↷
        </button>
        <button
          className="icon-btn"
          title="Copy selected (Ctrl+C)"
          disabled={!state.selected.length}
          onClick={copySelected}
        >
          ⧉
        </button>
        <button className="icon-btn" title="Paste (Ctrl+V)" onClick={paste}>
          📋
        </button>
        <div className="sep" />
        <span className="dim">Label:</span>
        <span style={{ width: 140 }}>
          <LabelPicker value={effectiveLabel} labels={labels} onChange={setCurrentLabel} />
        </span>
        <div className="grow" />
        <button onClick={() => goToImage(imageIndex - 1)} disabled={imageIndex <= 0}>
          ← Prev
        </button>
        <button onClick={() => goToImage(imageIndex + 1)} disabled={imageIndex >= images.length - 1}>
          Next →
        </button>
        <button className="primary" onClick={() => void save()} disabled={!state.dirty}>
          {state.dirty ? 'Save' : 'Saved ✓'}
        </button>
      </div>

      <div className="editor-body">
        <div className="canvas-wrap">
          {doc && (
            <AnnotationCanvas
              imageUrl={api.imageUrl(project, filename)}
              imageWidth={doc.imageWidth}
              imageHeight={doc.imageHeight}
              shapes={state.shapes}
              selected={state.selected}
              labelColors={labelColors}
              tool={tool}
              onAddShape={addShape}
              dispatch={dispatch}
            />
          )}
        </div>
        <div className="sidebar">
          {error && <p className="error">{error}</p>}
          <ShapeList
            shapes={state.shapes}
            selected={state.selected}
            labels={labels}
            dispatch={dispatch}
          />
          <div className="dim" style={{ fontSize: 12, marginTop: 'auto' }}>
            <p>
              <span className="kbd">R</span> rect · <span className="kbd">P</span> polygon ·{' '}
              <span className="kbd">S</span> select
            </p>
            <p>
              <span className="kbd">Ctrl+Z</span> undo · <span className="kbd">Ctrl+C/V</span>{' '}
              copy/paste · <span className="kbd">Del</span> delete
            </p>
            <p>
              <span className="kbd">Space</span>+drag pan · wheel zoom ·{' '}
              <span className="kbd">←/→</span> prev/next
            </p>
          </div>
        </div>
      </div>

      <div className="statusbar">
        <span>images:</span>
        {images.map((img, i) => (
          <button
            key={img.filename}
            className={`film-dot ${img.annotated ? 'done' : ''} ${i === imageIndex ? 'current' : ''}`}
            title={img.filename}
            onClick={() => goToImage(i)}
          />
        ))}
      </div>
    </div>
  )
}
