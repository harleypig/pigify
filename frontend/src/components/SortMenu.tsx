import { useEffect, useRef, useState } from 'react'
import {
  SortDirection,
  SortField,
  SortKeySpec,
  SortPreset,
} from '../services/api'
import { presetToKeys } from '../services/sortEngine'
import './SortMenu.css'

export interface SortSpec {
  keys: SortKeySpec[]
}

interface SortMenuProps {
  fields: SortField[]
  presets: SortPreset[]
  current: SortSpec
  onChange: (spec: SortSpec) => void
  onSavePreset: (preset: SortPreset) => void
  onDeletePreset: (name: string) => void
  onApplyView: () => void
  onApplyToPlaylist: () => void
  onUndo: () => void
  applying: boolean
  undoAvailable: boolean
  warnings?: string[]
}

const MAX_KEYS = 8

function fieldLabel(fields: SortField[], key: string): string {
  return fields.find((f) => f.key === key)?.label ?? key
}

function KeyRow({
  fields,
  value,
  index,
  total,
  onChange,
  onMove,
  onRemove,
}: {
  fields: SortField[]
  value: SortKeySpec
  index: number
  total: number
  onChange: (v: SortKeySpec) => void
  onMove: (from: number, to: number) => void
  onRemove: () => void
}) {
  const groups: Record<string, SortField[]> = {}
  for (const f of fields) {
    ;(groups[f.group] ||= []).push(f)
  }

  const handleField = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onChange({ field: e.target.value, direction: value.direction })
  }
  const handleDir = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onChange({ field: value.field, direction: e.target.value as SortDirection })
  }
  const isDate = fields.find((f) => f.key === value.field)?.type === 'date'
  const label =
    index === 0 ? 'Sort by' : index === 1 ? 'Then by' : `Then by (${index + 1})`

  return (
    <div className="sort-row sort-row-multi">
      <label className="sort-row-label">{label}</label>
      <select
        className="sort-field-select"
        value={value.field}
        onChange={handleField}
      >
        {Object.entries(groups).map(([group, list]) => (
          <optgroup label={group} key={group}>
            {list.map((f) => (
              <option key={f.key} value={f.key}>
                {f.label}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
      <select
        className="sort-dir-select"
        value={value.direction}
        onChange={handleDir}
      >
        <option value="asc">{isDate ? 'Oldest first' : 'Asc (A→Z / low→high)'}</option>
        <option value="desc">{isDate ? 'Newest first' : 'Desc (Z→A / high→low)'}</option>
      </select>
      <div className="sort-row-actions">
        <button
          type="button"
          className="sort-row-btn"
          aria-label="Move sort key up"
          title="Move up"
          onClick={() => onMove(index, index - 1)}
          disabled={index === 0}
        >
          ↑
        </button>
        <button
          type="button"
          className="sort-row-btn"
          aria-label="Move sort key down"
          title="Move down"
          onClick={() => onMove(index, index + 1)}
          disabled={index === total - 1}
        >
          ↓
        </button>
        <button
          type="button"
          className="sort-row-btn sort-row-remove"
          aria-label="Remove this sort key"
          title="Remove this sort key"
          onClick={onRemove}
          disabled={total <= 1}
        >
          ×
        </button>
      </div>
    </div>
  )
}

function SortMenu(props: SortMenuProps) {
  const {
    fields, presets, current, onChange,
    onSavePreset, onDeletePreset,
    onApplyView, onApplyToPlaylist, onUndo,
    applying, undoAvailable, warnings,
  } = props

  const [open, setOpen] = useState(false)
  const [presetName, setPresetName] = useState('')
  const wrapperRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (!wrapperRef.current) return
      if (!wrapperRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const keys = current.keys
  const primaryKey = keys[0]
  const summary = primaryKey
    ? `${fieldLabel(fields, primaryKey.field)} ${
        primaryKey.direction === 'desc' ? '↓' : '↑'
      }${keys.length > 1 ? ` +${keys.length - 1}` : ''}`
    : '—'

  const updateKey = (i: number, v: SortKeySpec) => {
    const next = keys.slice()
    next[i] = v
    onChange({ keys: next })
  }

  const removeKey = (i: number) => {
    if (keys.length <= 1) return
    const next = keys.slice()
    next.splice(i, 1)
    onChange({ keys: next })
  }

  const moveKey = (from: number, to: number) => {
    if (to < 0 || to >= keys.length) return
    const next = keys.slice()
    const [item] = next.splice(from, 1)
    next.splice(to, 0, item)
    onChange({ keys: next })
  }

  const addKey = () => {
    if (keys.length >= MAX_KEYS) return
    // Pick the first field not already in use, falling back to the first field.
    const used = new Set(keys.map((k) => k.field))
    const candidate = fields.find((f) => !used.has(f.key)) ?? fields[0]
    if (!candidate) return
    onChange({
      keys: [...keys, { field: candidate.key, direction: 'asc' }],
    })
  }

  const handleQuickPreset = (key: string) => {
    onChange({ keys: [{ field: key, direction: 'asc' }] })
  }

  const defaultFields = fields.filter((f) => f.default)

  return (
    <div className="sort-menu" ref={wrapperRef}>
      <button
        className="sort-trigger"
        onClick={() => setOpen((v) => !v)}
        title="Sort tracks"
      >
        Sort by: <span className="sort-trigger-summary">{summary}</span> ▾
      </button>
      {undoAvailable && (
        <button className="sort-undo" onClick={onUndo} title="Undo last apply">
          Undo
        </button>
      )}

      {open && (
        <div className="sort-popover" role="dialog">
          <div className="sort-popover-section">
            <div className="sort-section-title">Defaults</div>
            <div className="sort-quick-grid">
              {defaultFields.map((f) => (
                <button
                  key={f.key}
                  className={`sort-quick ${
                    primaryKey?.field === f.key ? 'active' : ''
                  }`}
                  onClick={() => handleQuickPreset(f.key)}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          <div className="sort-popover-section">
            <div className="sort-section-title">Custom</div>
            {keys.map((k, i) => (
              <KeyRow
                key={i}
                fields={fields}
                value={k}
                index={i}
                total={keys.length}
                onChange={(v) => updateKey(i, v)}
                onMove={moveKey}
                onRemove={() => removeKey(i)}
              />
            ))}
            <button
              type="button"
              className="sort-add-key"
              onClick={addKey}
              disabled={keys.length >= MAX_KEYS || fields.length === 0}
              title={
                keys.length >= MAX_KEYS
                  ? `Up to ${MAX_KEYS} sort keys`
                  : 'Add another sort key'
              }
            >
              + Add another sort key
            </button>
          </div>

          <div className="sort-popover-section">
            <div className="sort-section-title">Saved sorts</div>
            <div className="sort-presets">
              {presets.length === 0 && (
                <div className="sort-empty">No saved sorts yet.</div>
              )}
              {presets.map((p) => {
                const pk = presetToKeys(p)
                const title = pk
                  .map(
                    (k) =>
                      `${fieldLabel(fields, k.field)} ${k.direction}`
                  )
                  .join(', ')
                return (
                  <div key={p.name} className="sort-preset-row">
                    <button
                      className="sort-preset-load"
                      onClick={() =>
                        pk.length > 0 && onChange({ keys: pk })
                      }
                      title={title}
                    >
                      <span className="sort-preset-name">{p.name}</span>
                      {pk.length > 1 && (
                        <span className="sort-preset-count">
                          {' '}
                          · {pk.length} keys
                        </span>
                      )}
                    </button>
                    <button
                      className="sort-preset-del"
                      onClick={() => onDeletePreset(p.name)}
                      aria-label={`Delete preset ${p.name}`}
                      title="Delete preset"
                    >
                      ×
                    </button>
                  </div>
                )
              })}
            </div>
            <div className="sort-save-row">
              <input
                type="text"
                placeholder="Save current as…"
                value={presetName}
                onChange={(e) => setPresetName(e.target.value)}
                className="sort-preset-name-input"
              />
              <button
                className="sort-preset-save-btn"
                disabled={!presetName.trim() || keys.length === 0}
                onClick={() => {
                  onSavePreset({
                    name: presetName.trim(),
                    keys,
                  })
                  setPresetName('')
                }}
              >
                Save
              </button>
            </div>
          </div>

          <div className="sort-popover-section">
            <div className="sort-actions">
              <button className="sort-apply-view" onClick={onApplyView}>
                Apply to view
              </button>
              <button
                className="sort-apply-playlist"
                onClick={onApplyToPlaylist}
                disabled={applying}
                title="Rewrite the actual Spotify playlist order"
              >
                {applying ? 'Applying…' : 'Apply to playlist'}
              </button>
            </div>
            {warnings && warnings.length > 0 && (
              <div className="sort-warnings">
                {warnings.map((w, i) => (
                  <div key={i} className="sort-warning">⚠ {w}</div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default SortMenu
