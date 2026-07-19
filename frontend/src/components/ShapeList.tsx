import type { Dispatch } from 'react'
import type { LabelDef, Shape } from '../types'
import type { EditorAction } from '../state/editorReducer'
import { LabelPicker } from './LabelPicker'

interface Props {
  shapes: Shape[]
  selected: number[]
  labels: LabelDef[]
  dispatch: Dispatch<EditorAction>
}

function shapeTag(shape: Shape): string {
  switch (shape.shape_type) {
    case 'rectangle':
      return 'rect'
    case 'polygon':
      return `poly·${shape.points.length}`
    case 'linestrip':
      return `strip·${shape.points.length}`
    default:
      return shape.shape_type
  }
}

export function ShapeList({ shapes, selected, labels, dispatch }: Props) {
  const colorOf = (label: string) =>
    labels.find((l) => l.name === label)?.color ?? '#4d9fff'

  return (
    <div>
      <h3>
        Shapes <span className="dim">({shapes.length})</span>
      </h3>
      {shapes.length === 0 && <p className="dim">No shapes yet — press R or P to draw.</p>}
      {shapes.map((shape, i) => (
        <div
          key={i}
          className={`shape-row ${selected.includes(i) ? 'selected' : ''}`}
          onClick={(e) =>
            dispatch({
              type: 'SELECT',
              indices: e.shiftKey
                ? selected.includes(i)
                  ? selected.filter((s) => s !== i)
                  : [...selected, i]
                : [i],
            })
          }
        >
          <span className="swatch" style={{ background: colorOf(shape.label) }} />
          <span className="grow" onClick={(e) => e.stopPropagation()}>
            <LabelPicker
              value={shape.label}
              labels={labels}
              onChange={(label) => dispatch({ type: 'SET_LABEL', indices: [i], label })}
            />
          </span>
          <span className="dim" style={{ fontSize: 11 }}>
            {shapeTag(shape)}
          </span>
          <button
            className="danger icon-btn"
            title="Delete shape"
            onClick={(e) => {
              e.stopPropagation()
              dispatch({ type: 'SELECT', indices: [i] })
              dispatch({ type: 'DELETE_SELECTED' })
            }}
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}
