import type { LabelDef } from '../types'

interface Props {
  value: string
  labels: LabelDef[]
  onChange: (label: string) => void
}

export function LabelPicker({ value, labels, onChange }: Props) {
  const known = labels.some((l) => l.name === value)
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} style={{ width: '100%' }}>
      {!known && <option value={value}>{value}</option>}
      {labels.map((l) => (
        <option key={l.name} value={l.name}>
          {l.name}
        </option>
      ))}
    </select>
  )
}
