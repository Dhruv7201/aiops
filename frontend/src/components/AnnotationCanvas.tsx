import { useCallback, useEffect, useRef, useState } from 'react'
import type { Dispatch } from 'react'
import type { Shape, ShapeType } from '../types'
import type { EditorAction } from '../state/editorReducer'
import {
  fitViewport,
  hitVertex,
  moveRectCorner,
  pointInShape,
  shapeVertices,
  toImage,
  translateShape,
  zoomAt,
} from '../canvas/geometry'
import type { Viewport } from '../canvas/geometry'

export type Tool = 'select' | 'rectangle' | 'polygon'

interface Props {
  imageUrl: string
  imageWidth: number
  imageHeight: number
  shapes: Shape[]
  selected: number[]
  labelColors: Map<string, string>
  tool: Tool
  onAddShape: (points: number[][], shapeType: ShapeType) => void
  dispatch: Dispatch<EditorAction>
}

type Drag =
  | { kind: 'pan'; startX: number; startY: number; panX: number; panY: number }
  | { kind: 'move'; index: number; lastX: number; lastY: number }
  | { kind: 'vertex'; index: number; vertex: number }

const FALLBACK_COLOR = '#4d9fff'

export function AnnotationCanvas({
  imageUrl,
  imageWidth,
  imageHeight,
  shapes,
  selected,
  labelColors,
  tool,
  onAddShape,
  dispatch,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [vp, setVp] = useState<Viewport>({ zoom: 1, panX: 0, panY: 0 })
  const [draft, setDraft] = useState<number[][]>([]) // in-progress rect/polygon points
  const [cursor, setCursor] = useState<[number, number] | null>(null)
  const [drag, setDrag] = useState<Drag | null>(null)
  const [spaceHeld, setSpaceHeld] = useState(false)

  const color = (label: string) => labelColors.get(label) ?? FALLBACK_COLOR

  // -- viewport --

  const fit = useCallback(() => {
    const el = svgRef.current
    if (!el) return
    const { width, height } = el.getBoundingClientRect()
    setVp(fitViewport(imageWidth, imageHeight, width, height))
  }, [imageWidth, imageHeight])

  useEffect(fit, [fit])

  // Native wheel listener (react's onWheel is passive; we need preventDefault)
  useEffect(() => {
    const el = svgRef.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const rect = el.getBoundingClientRect()
      const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12
      setVp((v) => zoomAt(v, e.clientX - rect.left, e.clientY - rect.top, factor))
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [])

  // Space key = pan mode; Esc/Backspace manage drafts
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.code === 'Space') setSpaceHeld(true)
      if (e.key === 'Escape') setDraft([])
      if (e.key === 'Backspace' && tool === 'polygon' && draft.length) {
        setDraft((d) => d.slice(0, -1))
        e.preventDefault()
      }
    }
    const up = (e: KeyboardEvent) => {
      if (e.code === 'Space') setSpaceHeld(false)
    }
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    return () => {
      window.removeEventListener('keydown', down)
      window.removeEventListener('keyup', up)
    }
  }, [tool, draft.length])

  // Reset draft when tool or image changes
  useEffect(() => setDraft([]), [tool, imageUrl])

  const screenPos = (e: React.PointerEvent): [number, number] => {
    const rect = svgRef.current!.getBoundingClientRect()
    return [e.clientX - rect.left, e.clientY - rect.top]
  }
  const imagePos = (e: React.PointerEvent): [number, number] => {
    const [sx, sy] = screenPos(e)
    const [x, y] = toImage(vp, sx, sy)
    return [Math.min(imageWidth, Math.max(0, x)), Math.min(imageHeight, Math.max(0, y))]
  }

  // -- pointer handlers --

  const onPointerDown = (e: React.PointerEvent) => {
    svgRef.current?.setPointerCapture(e.pointerId)
    const [sx, sy] = screenPos(e)

    if (e.button === 1 || spaceHeld) {
      setDrag({ kind: 'pan', startX: sx, startY: sy, panX: vp.panX, panY: vp.panY })
      return
    }
    if (e.button !== 0) return
    const [x, y] = imagePos(e)

    if (tool === 'rectangle') {
      if (draft.length === 0) {
        setDraft([[x, y]])
      } else {
        const [start] = draft
        if (Math.abs(x - start[0]) > 1 && Math.abs(y - start[1]) > 1) {
          onAddShape([start, [x, y]], 'rectangle')
        }
        setDraft([])
      }
      return
    }

    if (tool === 'polygon') {
      // Close when clicking near the first point
      if (draft.length >= 3) {
        const [fx, fy] = draft[0]
        if (Math.hypot(fx - x, fy - y) <= 8 / vp.zoom) {
          onAddShape(draft, 'polygon')
          setDraft([])
          return
        }
      }
      setDraft((d) => [...d, [x, y]])
      return
    }

    // -- select tool --
    const vertexRadius = 7 / vp.zoom

    // Vertex handles of selected shapes take priority
    for (const i of selected) {
      const v = hitVertex(x, y, shapes[i], vertexRadius)
      if (v >= 0) {
        dispatch({ type: 'DRAG_START' })
        setDrag({ kind: 'vertex', index: i, vertex: v })
        return
      }
    }
    // Topmost shape under cursor
    for (let i = shapes.length - 1; i >= 0; i--) {
      if (pointInShape(x, y, shapes[i])) {
        const indices = e.shiftKey
          ? selected.includes(i)
            ? selected.filter((s) => s !== i)
            : [...selected, i]
          : selected.includes(i)
            ? selected
            : [i]
        dispatch({ type: 'SELECT', indices })
        dispatch({ type: 'DRAG_START' })
        setDrag({ kind: 'move', index: i, lastX: x, lastY: y })
        return
      }
    }
    dispatch({ type: 'SELECT', indices: [] })
  }

  const onPointerMove = (e: React.PointerEvent) => {
    const [x, y] = imagePos(e)
    setCursor([x, y])

    if (!drag) return
    if (drag.kind === 'pan') {
      const [sx, sy] = screenPos(e)
      setVp((v) => ({ ...v, panX: drag.panX + sx - drag.startX, panY: drag.panY + sy - drag.startY }))
      return
    }
    if (drag.kind === 'move') {
      const dx = x - drag.lastX
      const dy = y - drag.lastY
      // Move every selected shape together
      for (const i of selected) {
        dispatch({ type: 'DRAG_PREVIEW', index: i, shape: translateShape(shapes[i], dx, dy) })
      }
      setDrag({ ...drag, lastX: x, lastY: y })
      return
    }
    if (drag.kind === 'vertex') {
      const shape = shapes[drag.index]
      const points =
        shape.shape_type === 'rectangle'
          ? moveRectCorner(shape.points, drag.vertex, x, y)
          : shape.points.map((p, i) => (i === drag.vertex ? [x, y] : p))
      dispatch({ type: 'DRAG_PREVIEW', index: drag.index, shape: { ...shape, points } })
    }
  }

  const onPointerUp = () => {
    if (drag && drag.kind !== 'pan') dispatch({ type: 'DRAG_END' })
    setDrag(null)
  }

  const onDoubleClick = () => {
    if (tool === 'polygon' && draft.length >= 3) {
      onAddShape(draft, 'polygon')
      setDraft([])
    }
  }

  // -- rendering --

  const sw = 2 / vp.zoom // stroke width in image space
  const vr = 5 / vp.zoom // vertex radius

  const renderShape = (shape: Shape, i: number) => {
    const c = color(shape.label)
    const isSel = selected.includes(i)
    const common = {
      stroke: c,
      strokeWidth: isSel ? sw * 1.6 : sw,
      fill: c,
      fillOpacity: isSel ? 0.28 : 0.14,
    }
    if (shape.shape_type === 'rectangle') {
      const [[ax, ay], [bx, by]] = shape.points
      return (
        <rect
          key={i}
          x={Math.min(ax, bx)}
          y={Math.min(ay, by)}
          width={Math.abs(bx - ax)}
          height={Math.abs(by - ay)}
          {...common}
        />
      )
    }
    return <polygon key={i} points={shape.points.map((p) => p.join(',')).join(' ')} {...common} />
  }

  const cursorStyle =
    drag?.kind === 'pan' || spaceHeld ? 'grabbing' : tool === 'select' ? 'default' : 'crosshair'

  return (
    <svg
      ref={svgRef}
      style={{ cursor: cursorStyle, touchAction: 'none' }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onDoubleClick={onDoubleClick}
      onContextMenu={(e) => e.preventDefault()}
    >
      <g transform={`translate(${vp.panX} ${vp.panY}) scale(${vp.zoom})`}>
        <image
          href={imageUrl}
          width={imageWidth}
          height={imageHeight}
          style={{ imageRendering: vp.zoom > 4 ? 'pixelated' : 'auto' }}
        />
        {shapes.map(renderShape)}

        {/* vertex handles on selected shapes */}
        {selected.map((i) =>
          shapes[i] ? (
            <g key={`v${i}`}>
              {shapeVertices(shapes[i]).map(([vx, vy], j) => (
                <circle
                  key={j}
                  cx={vx}
                  cy={vy}
                  r={vr}
                  fill="#fff"
                  stroke={color(shapes[i].label)}
                  strokeWidth={sw}
                />
              ))}
            </g>
          ) : null,
        )}

        {/* draft rectangle */}
        {tool === 'rectangle' && draft.length === 1 && cursor && (
          <rect
            x={Math.min(draft[0][0], cursor[0])}
            y={Math.min(draft[0][1], cursor[1])}
            width={Math.abs(cursor[0] - draft[0][0])}
            height={Math.abs(cursor[1] - draft[0][1])}
            fill="none"
            stroke={FALLBACK_COLOR}
            strokeWidth={sw}
            strokeDasharray={`${sw * 3} ${sw * 3}`}
          />
        )}

        {/* draft polygon */}
        {tool === 'polygon' && draft.length > 0 && (
          <g>
            <polyline
              points={[...draft, ...(cursor ? [cursor] : [])].map((p) => p.join(',')).join(' ')}
              fill="none"
              stroke={FALLBACK_COLOR}
              strokeWidth={sw}
              strokeDasharray={`${sw * 3} ${sw * 3}`}
            />
            {draft.map(([px, py], j) => (
              <circle
                key={j}
                cx={px}
                cy={py}
                r={j === 0 ? vr * 1.4 : vr}
                fill={j === 0 ? FALLBACK_COLOR : '#fff'}
                stroke={FALLBACK_COLOR}
                strokeWidth={sw}
              />
            ))}
          </g>
        )}
      </g>
    </svg>
  )
}
