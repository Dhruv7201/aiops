// Mirrors src/aiops/annotate/models.py

export type ShapeType = 'rectangle' | 'polygon' | 'circle' | 'line' | 'point' | 'linestrip'

/** The editor only creates/edits these; other LabelMe types render read-only. */
export const isEditableShape = (t: ShapeType) => t === 'rectangle' || t === 'polygon'

export type ExportFormat = 'labelme' | 'yolo' | 'coco'

export interface Shape {
  label: string
  points: number[][]
  shape_type: ShapeType
  group_id: number | null
  description: string
  flags: Record<string, unknown>
}

export interface LabelMeDoc {
  version: string
  flags: Record<string, unknown>
  shapes: Shape[]
  imagePath: string
  imageData: string | null
  imageHeight: number
  imageWidth: number
}

export interface LabelDef {
  name: string
  color: string
}

export interface ProjectMeta {
  name: string
  images_dir: string
  labels: LabelDef[]
  users: string[]
  assignments: Record<string, string>
}

export interface ProjectSummary {
  name: string
  images_dir: string
  num_images: number
  num_annotated: number
}

export interface ImageInfo {
  filename: string
  width: number
  height: number
  assigned_to: string | null
  annotated: boolean
  num_shapes: number
}

export interface ExportResult {
  output_dir: string
  counts: Record<string, number>
}

export const DEFAULT_LABEL_COLORS = [
  '#e6194b', '#3cb44b', '#4363d8', '#f58231', '#911eb4',
  '#46f0f0', '#f032e6', '#bcf60c', '#fabebe', '#008080',
]

export function newShape(label: string, points: number[][], shapeType: ShapeType): Shape {
  return { label, points, shape_type: shapeType, group_id: null, description: '', flags: {} }
}
