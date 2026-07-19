// Pure geometry helpers for the annotation canvas.

import type { Shape } from '../types'

export interface Viewport {
  zoom: number
  panX: number
  panY: number
}

/** Screen (svg-local) coords → image coords. */
export function toImage(vp: Viewport, sx: number, sy: number): [number, number] {
  return [(sx - vp.panX) / vp.zoom, (sy - vp.panY) / vp.zoom]
}

/** Zoom about a screen point, returning the new viewport. */
export function zoomAt(vp: Viewport, sx: number, sy: number, factor: number): Viewport {
  const zoom = Math.min(50, Math.max(0.05, vp.zoom * factor))
  const scale = zoom / vp.zoom
  return {
    zoom,
    panX: sx - (sx - vp.panX) * scale,
    panY: sy - (sy - vp.panY) * scale,
  }
}

/** Fit an image into a container, centered. */
export function fitViewport(imgW: number, imgH: number, cw: number, ch: number): Viewport {
  if (!imgW || !imgH || !cw || !ch) return { zoom: 1, panX: 0, panY: 0 }
  const zoom = Math.min(cw / imgW, ch / imgH) * 0.95
  return { zoom, panX: (cw - imgW * zoom) / 2, panY: (ch - imgH * zoom) / 2 }
}

/** Normalized [x1,y1,x2,y2] for a 2-point LabelMe rectangle. */
export function rectBounds(points: number[][]): [number, number, number, number] {
  const [[ax, ay], [bx, by]] = points
  return [Math.min(ax, bx), Math.min(ay, by), Math.max(ax, bx), Math.max(ay, by)]
}

export function pointInRect(x: number, y: number, points: number[][]): boolean {
  const [x1, y1, x2, y2] = rectBounds(points)
  return x >= x1 && x <= x2 && y >= y1 && y <= y2
}

export function pointInPolygon(x: number, y: number, points: number[][]): boolean {
  let inside = false
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    const [xi, yi] = points[i]
    const [xj, yj] = points[j]
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) {
      inside = !inside
    }
  }
  return inside
}

export function pointInShape(x: number, y: number, shape: Shape): boolean {
  return shape.shape_type === 'rectangle'
    ? pointInRect(x, y, shape.points)
    : pointInPolygon(x, y, shape.points)
}

/** Rectangle corner handles: 4 corners derived from the 2 stored points. */
export function rectCorners(points: number[][]): number[][] {
  const [x1, y1, x2, y2] = rectBounds(points)
  return [
    [x1, y1],
    [x2, y1],
    [x2, y2],
    [x1, y2],
  ]
}

/** Editable vertices of a shape (corners for rects, points for polygons). */
export function shapeVertices(shape: Shape): number[][] {
  return shape.shape_type === 'rectangle' ? rectCorners(shape.points) : shape.points
}

/** Index of the vertex within `radius` of (x, y), or -1. */
export function hitVertex(x: number, y: number, shape: Shape, radius: number): number {
  const verts = shapeVertices(shape)
  for (let i = 0; i < verts.length; i++) {
    if (Math.hypot(verts[i][0] - x, verts[i][1] - y) <= radius) return i
  }
  return -1
}

/** Move a rect corner: returns new 2-point rect keeping the opposite corner fixed. */
export function moveRectCorner(points: number[][], corner: number, x: number, y: number): number[][] {
  const corners = rectCorners(points)
  const opposite = corners[(corner + 2) % 4]
  return [
    [x, y],
    [opposite[0], opposite[1]],
  ]
}

export function translateShape(shape: Shape, dx: number, dy: number): Shape {
  return { ...shape, points: shape.points.map(([x, y]) => [x + dx, y + dy]) }
}

/** Clamp all points into image bounds. */
export function clampShape(shape: Shape, w: number, h: number): Shape {
  return {
    ...shape,
    points: shape.points.map(([x, y]) => [
      Math.min(w, Math.max(0, x)),
      Math.min(h, Math.max(0, y)),
    ]),
  }
}
