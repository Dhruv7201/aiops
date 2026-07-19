import { useState } from 'react'
import { api } from '../api'
import type { ExportFormat, ExportResult } from '../types'

interface Props {
  project: string
  onClose: () => void
}

const FORMATS: { value: ExportFormat; label: string; hint: string }[] = [
  {
    value: 'labelme',
    label: 'LabelMe',
    hint: 'Copies images + LabelMe JSONs into <split>/images and <split>/labels.',
  },
  {
    value: 'yolo',
    label: 'YOLO',
    hint: 'Ultralytics txt labels + dataset.yaml; polygons become bounding boxes.',
  },
  {
    value: 'coco',
    label: 'COCO (RF-DETR)',
    hint: 'Roboflow layout: train/valid/test dirs with _annotations.coco.json.',
  },
]

export function ExportDialog({ project, onClose }: Props) {
  const [format, setFormat] = useState<ExportFormat>('labelme')
  const [threeWay, setThreeWay] = useState(true)
  const [train, setTrain] = useState(70)
  const [val, setVal] = useState(20)
  const [test, setTest] = useState(10)
  const [outputDir, setOutputDir] = useState('')
  const [seed, setSeed] = useState('')
  const [result, setResult] = useState<ExportResult | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const effectiveTest = threeWay ? test : 0
  const total = train + val + effectiveTest
  const valid = Math.abs(total - 100) < 0.01 && outputDir.trim() !== ''

  const setMode = (three: boolean) => {
    setThreeWay(three)
    if (three) {
      setTrain(70)
      setVal(20)
      setTest(10)
    } else {
      setTrain(80)
      setVal(20)
    }
  }

  const doExport = async () => {
    setBusy(true)
    setError('')
    try {
      setResult(
        await api.export(
          project,
          outputDir.trim(),
          format,
          { train: train / 100, val: val / 100, test: effectiveTest / 100 },
          seed.trim() === '' ? null : Number(seed),
        ),
      )
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="overlay" onClick={onClose}>
      <div className="dialog" onClick={(e) => e.stopPropagation()}>
        <h2>Export dataset</h2>
        <div className="row">
          {FORMATS.map((f) => (
            <label key={f.value} className="row">
              <input
                type="radio"
                checked={format === f.value}
                onChange={() => setFormat(f.value)}
              />
              {f.label}
            </label>
          ))}
        </div>
        <p className="dim">{FORMATS.find((f) => f.value === format)!.hint}</p>
        <div className="row">
          <label className="row">
            <input type="radio" checked={!threeWay} onChange={() => setMode(false)} />
            train / val
          </label>
          <label className="row">
            <input type="radio" checked={threeWay} onChange={() => setMode(true)} />
            train / val / test
          </label>
        </div>
        <div className="row wrap">
          <label>
            train %{' '}
            <input type="number" min={0} max={100} value={train} onChange={(e) => setTrain(+e.target.value)} />
          </label>
          <label>
            val %{' '}
            <input type="number" min={0} max={100} value={val} onChange={(e) => setVal(+e.target.value)} />
          </label>
          {threeWay && (
            <label>
              test %{' '}
              <input type="number" min={0} max={100} value={test} onChange={(e) => setTest(+e.target.value)} />
            </label>
          )}
          <span className={Math.abs(total - 100) < 0.01 ? 'dim' : 'error'}>Σ {total}%</span>
        </div>
        <label>
          Output directory <span className="dim">(on the server machine)</span>
          <input
            style={{ width: '100%', marginTop: 4 }}
            value={outputDir}
            onChange={(e) => setOutputDir(e.target.value)}
            placeholder="/home/me/datasets/export"
          />
        </label>
        <label>
          Random seed <span className="dim">(optional, for reproducible splits)</span>
          <input
            style={{ width: '100%', marginTop: 4 }}
            value={seed}
            onChange={(e) => setSeed(e.target.value)}
            placeholder="42"
          />
        </label>
        {error && <p className="error">{error}</p>}
        {result && (
          <p>
            ✅ Exported to <code>{result.output_dir}</code>:{' '}
            {Object.entries(result.counts)
              .map(([k, v]) => `${k}=${v}`)
              .join(', ')}
          </p>
        )}
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          <button onClick={onClose}>{result ? 'Close' : 'Cancel'}</button>
          <button className="primary" onClick={doExport} disabled={!valid || busy}>
            {busy ? 'Exporting…' : 'Export'}
          </button>
        </div>
      </div>
    </div>
  )
}
