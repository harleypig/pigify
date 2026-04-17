import { useEffect, useRef, useState } from 'react'
import {
  SortDirection,
  SortField,
  SortKeySpec,
  SortPreset,
} from '../services/api'
import './SortMenu.css'

export interface SortSpec {
  primary: SortKeySpec
  secondary: SortKeySpec | null
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

const DEFAULT_KEYS = new Set([
  'added_at', 'name', 'artist', 'album', 'duration_ms',
  'release_date', 'popularity', 'tempo', 'energy', 'lastfm_playcount',
])

function fieldLabel(fields: SortField[], key: string): string {
  return fields.find((f) => f.key === key)?.label ?? key
}

function FieldPicker({
  fields,
  value,
  onChange,
  label,
  allowNone,
}: {
  fields: SortField[]
  value: SortKeySpec | null
  onChange: (v: SortKeySpec | null) => void
  label: string
  allowNone?: boolean
}) {
  // Group fields by group for an organised dropdown.
  const groups: Record<string, SortField[]> = {}
  for (const f of fields) {
    ;(groups[f.group] ||= []).push(f)
  }

  const handleField = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const v = e.target.value
    if (v === '__none__') {
      onChange(null)
      return
    }
    onChange({ field: v, direction: value?.direction ?? 'asc' })
  }

  const handleDir = (e: React.ChangeEvent<HTMLSelectElement>) => {
    if (!value) return
    onChange({ field: value.field, direction: e.target.value as SortDirection })
  }

  const isDate =
    value && fields.find((f) => f.key === value.field)?.type === 'date'

  return (
    <div className="sort-row">
      <label className="sort-row-label">{label}</label>
      <select
        className="sort-field-select"
        value={value?.field ?? '__none__'}
        onChange={handleField}
      >
        {allowNone && <option value="__none__">— none —</option>}
        {Object.entries(groups).map(([group, list]) => (
          <optgroup label={group} key={group}>
            {list.map((f) => (
              <option key={f.key} value={f.key}>
                {f.label}
                {DEFAULT_KEYS.has(f.key) ? '' : ''}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
      <select
        className="sort-dir-select"
        value={value?.direction ?? 'asc'}
        onChange={handleDir}
        disabled={!value}
      >
        <option value="asc">{isDate ? 'Oldest first' : 'Asc (A→Z / low→high)'}</option>
        <option value="desc">{isDate ? 'Newest first' : 'Desc (Z→A / high→low)'}</option>
      </select>
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

  const summary = `${fieldLabel(fields, current.primary.field)} ${
    current.primary.direction === 'desc' ? '↓' : '↑'
  }`

  const handleQuickPreset = (key: string) => {
    onChange({ primary: { field: key, direction: 'asc' }, secondary: null })
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
                    current.primary.field === f.key ? 'active' : ''
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
            <FieldPicker
              fields={fields}
              value={current.primary}
              onChange={(v) =>
                v && onChange({ primary: v, secondary: current.secondary })
              }
              label="Primary"
            />
            <FieldPicker
              fields={fields}
              value={current.secondary}
              onChange={(v) =>
                onChange({ primary: current.primary, secondary: v })
              }
              label="Then by"
              allowNone
            />
          </div>

          <div className="sort-popover-section">
            <div className="sort-section-title">Saved sorts</div>
            <div className="sort-presets">
              {presets.length === 0 && (
                <div className="sort-empty">No saved sorts yet.</div>
              )}
              {presets.map((p) => (
                <div key={p.name} className="sort-preset-row">
                  <button
                    className="sort-preset-load"
                    onClick={() =>
                      onChange({ primary: p.primary, secondary: p.secondary ?? null })
                    }
                    title={`${fieldLabel(fields, p.primary.field)} ${p.primary.direction}`}
                  >
                    {p.name}
                  </button>
                  <button
                    className="sort-preset-del"
                    onClick={() => onDeletePreset(p.name)}
                    title="Delete preset"
                  >
                    ×
                  </button>
                </div>
              ))}
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
                disabled={!presetName.trim()}
                onClick={() => {
                  onSavePreset({
                    name: presetName.trim(),
                    primary: current.primary,
                    secondary: current.secondary,
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
