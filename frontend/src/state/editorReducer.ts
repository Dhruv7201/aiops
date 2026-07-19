// Shape editing state with undo/redo history.
//
// Drags dispatch DRAG_START (snapshot) → DRAG_PREVIEW (no history) →
// DRAG_END (one history entry), so a whole drag undoes in one step.

import type { Shape } from '../types'

const HISTORY_LIMIT = 100

export interface EditorState {
  shapes: Shape[]
  selected: number[]
  past: Shape[][]
  future: Shape[][]
  preDrag: Shape[] | null
  dirty: boolean
}

export const initialEditorState: EditorState = {
  shapes: [],
  selected: [],
  past: [],
  future: [],
  preDrag: null,
  dirty: false,
}

export type EditorAction =
  | { type: 'LOAD'; shapes: Shape[] }
  | { type: 'ADD_SHAPE'; shape: Shape }
  | { type: 'UPDATE_SHAPE'; index: number; shape: Shape }
  | { type: 'DELETE_SELECTED' }
  | { type: 'SET_LABEL'; indices: number[]; label: string }
  | { type: 'PASTE'; shapes: Shape[] }
  | { type: 'SELECT'; indices: number[] }
  | { type: 'DRAG_START' }
  | { type: 'DRAG_PREVIEW'; index: number; shape: Shape }
  | { type: 'DRAG_END' }
  | { type: 'UNDO' }
  | { type: 'REDO' }
  | { type: 'MARK_SAVED' }

function pushHistory(state: EditorState, snapshot: Shape[]): Pick<EditorState, 'past' | 'future'> {
  return { past: [...state.past.slice(-HISTORY_LIMIT + 1), snapshot], future: [] }
}

export function editorReducer(state: EditorState, action: EditorAction): EditorState {
  switch (action.type) {
    case 'LOAD':
      return { ...initialEditorState, shapes: action.shapes }

    case 'ADD_SHAPE':
      return {
        ...state,
        ...pushHistory(state, state.shapes),
        shapes: [...state.shapes, action.shape],
        selected: [state.shapes.length],
        dirty: true,
      }

    case 'UPDATE_SHAPE': {
      const shapes = state.shapes.map((s, i) => (i === action.index ? action.shape : s))
      return { ...state, ...pushHistory(state, state.shapes), shapes, dirty: true }
    }

    case 'DELETE_SELECTED': {
      if (!state.selected.length) return state
      const keep = state.shapes.filter((_, i) => !state.selected.includes(i))
      return {
        ...state,
        ...pushHistory(state, state.shapes),
        shapes: keep,
        selected: [],
        dirty: true,
      }
    }

    case 'SET_LABEL': {
      const shapes = state.shapes.map((s, i) =>
        action.indices.includes(i) ? { ...s, label: action.label } : s,
      )
      return { ...state, ...pushHistory(state, state.shapes), shapes, dirty: true }
    }

    case 'PASTE': {
      if (!action.shapes.length) return state
      const shapes = [...state.shapes, ...action.shapes]
      const selected = action.shapes.map((_, i) => state.shapes.length + i)
      return { ...state, ...pushHistory(state, state.shapes), shapes, selected, dirty: true }
    }

    case 'SELECT':
      return { ...state, selected: action.indices }

    case 'DRAG_START':
      return { ...state, preDrag: state.shapes }

    case 'DRAG_PREVIEW': {
      const shapes = state.shapes.map((s, i) => (i === action.index ? action.shape : s))
      return { ...state, shapes }
    }

    case 'DRAG_END': {
      if (!state.preDrag) return state
      if (state.preDrag === state.shapes) return { ...state, preDrag: null }
      return {
        ...state,
        ...pushHistory(state, state.preDrag),
        preDrag: null,
        dirty: true,
      }
    }

    case 'UNDO': {
      if (!state.past.length) return state
      const previous = state.past[state.past.length - 1]
      return {
        ...state,
        shapes: previous,
        selected: [],
        past: state.past.slice(0, -1),
        future: [state.shapes, ...state.future],
        dirty: true,
      }
    }

    case 'REDO': {
      if (!state.future.length) return state
      const [next, ...future] = state.future
      return {
        ...state,
        shapes: next,
        selected: [],
        past: [...state.past, state.shapes],
        future,
        dirty: true,
      }
    }

    case 'MARK_SAVED':
      return { ...state, dirty: false }

    default:
      return state
  }
}
