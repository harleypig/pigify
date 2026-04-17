import { useEffect, useMemo, useState } from 'react'
import {
  apiService,
  recipesApi,
  Playlist,
  Recipe,
  RecipeBucket,
  RecipeFilter,
  RecipeResolveResponse,
  SortField,
  StoredRecipe,
  Track,
} from '../services/api'
import './RecipeBuilder.css'

interface Props {
  open: boolean
  initial?: StoredRecipe | null
  onClose: () => void
  onSaved: (r: StoredRecipe) => void
}

const COMBINE_LABELS: Record<string, string> = {
  in_order: 'In order (concatenate buckets)',
  interleave: 'Interleave (round-robin)',
  shuffled: 'Shuffled',
}

const NUMERIC_OPS: Array<[string, string]> = [
  ['gte', '≥'], ['lte', '≤'], ['gt', '>'], ['lt', '<'],
  ['eq', '='], ['ne', '≠'], ['between', 'between'],
]
const STRING_OPS: Array<[string, string]> = [
  ['contains', 'contains'], ['eq', '='], ['ne', '≠'],
]
const ENUM_OPS: Array<[string, string]> = [['eq', 'is'], ['ne', 'is not']]
const DATE_OPS: Array<[string, string]> = [
  ['gte', 'on/after'], ['lte', 'on/before'], ['between', 'between'],
]

function opsForField(f?: SortField): Array<[string, string]> {
  if (!f) return STRING_OPS
  if (f.type === 'number') return NUMERIC_OPS
  if (f.type === 'date') return DATE_OPS
  if (f.type === 'enum') return ENUM_OPS
  return STRING_OPS
}

function blankBucket(): RecipeBucket {
  return {
    name: '',
    source: 'liked',
    filters: [],
    sort: { field: 'added_at', direction: 'desc' },
    count: 10,
  }
}

function blankRecipe(): Recipe {
  return { name: 'New filter', buckets: [blankBucket()], combine: 'in_order' }
}

export default function RecipeBuilder({ open, initial, onClose, onSaved }: Props) {
  const [fields, setFields] = useState<SortField[]>([])
  const [playlists, setPlaylists] = useState<Playlist[]>([])
  const [recipe, setRecipe] = useState<Recipe>(blankRecipe())
  const [preview, setPreview] = useState<RecipeResolveResponse | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    apiService.getSortFields().then((r) => setFields(r.fields)).catch(() => {})
    apiService.getPlaylists(50, 0).then(setPlaylists).catch(() => {})
    if (initial) {
      setRecipe({
        name: initial.name,
        combine: initial.combine,
        buckets: initial.buckets,
      })
    } else {
      setRecipe(blankRecipe())
    }
    setPreview(null)
    setError(null)
  }, [open, initial])

  const fieldByKey = useMemo(
    () => new Map(fields.map((f) => [f.key, f])),
    [fields]
  )

  if (!open) return null

  const updateBucket = (idx: number, patch: Partial<RecipeBucket>) => {
    setRecipe((r) => ({
      ...r,
      buckets: r.buckets.map((b, i) => (i === idx ? { ...b, ...patch } : b)),
    }))
  }

  const addBucket = () =>
    setRecipe((r) => ({ ...r, buckets: [...r.buckets, blankBucket()] }))

  const removeBucket = (idx: number) =>
    setRecipe((r) => ({
      ...r,
      buckets: r.buckets.length === 1 ? r.buckets : r.buckets.filter((_, i) => i !== idx),
    }))

  const updateFilter = (bIdx: number, fIdx: number, patch: Partial<RecipeFilter>) => {
    setRecipe((r) => ({
      ...r,
      buckets: r.buckets.map((b, i) =>
        i !== bIdx
          ? b
          : {
              ...b,
              filters: b.filters.map((f, j) => (j === fIdx ? { ...f, ...patch } : f)),
            }
      ),
    }))
  }
  const addFilter = (bIdx: number) => {
    const f = fields[0]
    if (!f) return
    updateBucket(bIdx, {
      filters: [
        ...recipe.buckets[bIdx].filters,
        { field: f.key, op: opsForField(f)[0][0] as any, value: '' },
      ],
    })
  }
  const removeFilter = (bIdx: number, fIdx: number) =>
    updateBucket(bIdx, {
      filters: recipe.buckets[bIdx].filters.filter((_, j) => j !== fIdx),
    })

  const handlePreview = async () => {
    setError(null)
    setPreviewing(true)
    try {
      const r = await recipesApi.resolve(recipe)
      setPreview(r)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Preview failed')
    } finally {
      setPreviewing(false)
    }
  }

  const handleSave = async () => {
    setError(null)
    setSaving(true)
    try {
      let saved: StoredRecipe
      if (initial?.id) {
        saved = await recipesApi.update(initial.id, recipe)
      } else {
        saved = await recipesApi.create(recipe)
      }
      onSaved(saved)
      onClose()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const handlePlay = async () => {
    setError(null)
    setPlaying(true)
    try {
      const uris = preview?.tracks.map((t) => t.uri).filter(Boolean) ?? []
      if (uris.length > 0) {
        await recipesApi.playAdhoc(recipe)
      } else {
        await recipesApi.playAdhoc(recipe)
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Playback failed')
    } finally {
      setPlaying(false)
    }
  }

  return (
    <div className="recipe-modal-backdrop" onClick={onClose}>
      <div className="recipe-modal" onClick={(e) => e.stopPropagation()}>
        <div className="recipe-modal-head">
          <input
            className="recipe-name"
            value={recipe.name}
            onChange={(e) => setRecipe((r) => ({ ...r, name: e.target.value }))}
            placeholder="Recipe name"
          />
          <button className="ghost" onClick={onClose}>×</button>
        </div>

        <div className="recipe-buckets">
          {recipe.buckets.map((bucket, bIdx) => (
            <BucketEditor
              key={bIdx}
              bucket={bucket}
              index={bIdx}
              fields={fields}
              fieldByKey={fieldByKey}
              playlists={playlists}
              onChange={(patch) => updateBucket(bIdx, patch)}
              onRemove={() => removeBucket(bIdx)}
              onUpdateFilter={(fIdx, patch) => updateFilter(bIdx, fIdx, patch)}
              onAddFilter={() => addFilter(bIdx)}
              onRemoveFilter={(fIdx) => removeFilter(bIdx, fIdx)}
              canRemove={recipe.buckets.length > 1}
            />
          ))}
          <button className="add-bucket" onClick={addBucket}>+ Add bucket</button>
        </div>

        <div className="recipe-combine">
          <label>Combine strategy</label>
          <select
            value={recipe.combine}
            onChange={(e) =>
              setRecipe((r) => ({ ...r, combine: e.target.value as any }))
            }
          >
            {Object.entries(COMBINE_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </div>

        <div className="recipe-actions">
          <button onClick={handlePreview} disabled={previewing}>
            {previewing ? 'Resolving…' : 'Preview'}
          </button>
          <button onClick={handlePlay} disabled={playing}>
            {playing ? 'Starting…' : 'Play now'}
          </button>
          <button className="primary" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving…' : initial ? 'Save changes' : 'Save recipe'}
          </button>
        </div>

        {error && <div className="recipe-error">{error}</div>}

        {preview && (
          <div className="recipe-preview">
            <div className="preview-header">
              <strong>{preview.tracks.length} tracks</strong>
              {preview.bucket_counts.length > 1 && (
                <span className="preview-counts">
                  ({preview.bucket_counts.join(' + ')} from buckets)
                </span>
              )}
            </div>
            {preview.warnings.length > 0 && (
              <ul className="preview-warnings">
                {preview.warnings.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            )}
            <div className="preview-list">
              {preview.tracks.slice(0, 100).map((t: Track, i: number) => (
                <div key={`${t.id}-${i}`} className="preview-row">
                  <span className="preview-num">{i + 1}</span>
                  <span className="preview-name">{t.name}</span>
                  <span className="preview-artist">{t.artists.join(', ')}</span>
                </div>
              ))}
              {preview.tracks.length > 100 && (
                <div className="preview-more">… and {preview.tracks.length - 100} more</div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function BucketEditor(props: {
  bucket: RecipeBucket
  index: number
  fields: SortField[]
  fieldByKey: Map<string, SortField>
  playlists: Playlist[]
  onChange: (patch: Partial<RecipeBucket>) => void
  onRemove: () => void
  onUpdateFilter: (fIdx: number, patch: Partial<RecipeFilter>) => void
  onAddFilter: () => void
  onRemoveFilter: (fIdx: number) => void
  canRemove: boolean
}) {
  const {
    bucket, index, fields, fieldByKey, playlists,
    onChange, onRemove, onUpdateFilter, onAddFilter, onRemoveFilter, canRemove,
  } = props

  return (
    <div className="bucket">
      <div className="bucket-head">
        <input
          className="bucket-name"
          value={bucket.name ?? ''}
          onChange={(e) => onChange({ name: e.target.value })}
          placeholder={`Bucket ${index + 1}`}
        />
        {canRemove && (
          <button className="ghost" onClick={onRemove} title="Remove bucket">×</button>
        )}
      </div>

      <div className="bucket-row">
        <label>Source</label>
        <select
          value={bucket.source}
          onChange={(e) => onChange({ source: e.target.value })}
        >
          <option value="liked">Liked Songs</option>
          {playlists.map((p) => (
            <option key={p.id} value={`playlist:${p.id}`}>{p.name}</option>
          ))}
        </select>
      </div>

      <div className="bucket-filters">
        <label>Filters</label>
        {bucket.filters.map((f, fIdx) => {
          const fld = fieldByKey.get(f.field)
          const ops = opsForField(fld)
          const isNumber = fld?.type === 'number'
          const isDate = fld?.type === 'date'
          const inputType = isNumber ? 'number' : isDate ? 'date' : 'text'
          return (
            <div className="filter-row" key={fIdx}>
              <select
                value={f.field}
                onChange={(e) => {
                  const newField = fields.find((x) => x.key === e.target.value)
                  const newOps = opsForField(newField)
                  onUpdateFilter(fIdx, {
                    field: e.target.value,
                    op: newOps[0][0] as any,
                    value: '',
                    value2: undefined,
                  })
                }}
              >
                {fields.map((x) => (
                  <option key={x.key} value={x.key}>{x.label}</option>
                ))}
              </select>
              <select
                value={f.op}
                onChange={(e) => onUpdateFilter(fIdx, { op: e.target.value as any })}
              >
                {ops.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              {fld?.type === 'enum' ? (
                <select
                  value={String(f.value ?? 'false')}
                  onChange={(e) =>
                    onUpdateFilter(fIdx, { value: e.target.value === 'true' })
                  }
                >
                  <option value="true">Yes</option>
                  <option value="false">No</option>
                </select>
              ) : (
                <input
                  type={inputType}
                  value={f.value ?? ''}
                  onChange={(e) => onUpdateFilter(fIdx, { value: e.target.value })}
                />
              )}
              {f.op === 'between' && (
                <input
                  type={inputType}
                  value={f.value2 ?? ''}
                  onChange={(e) => onUpdateFilter(fIdx, { value2: e.target.value })}
                />
              )}
              <button className="ghost" onClick={() => onRemoveFilter(fIdx)}>×</button>
            </div>
          )
        })}
        <button className="add-filter" onClick={onAddFilter}>+ Add filter</button>
      </div>

      <div className="bucket-row">
        <label>Sort by</label>
        <select
          value={bucket.sort?.field ?? ''}
          onChange={(e) =>
            onChange({
              sort: e.target.value
                ? { field: e.target.value, direction: bucket.sort?.direction ?? 'desc' }
                : null,
            })
          }
        >
          <option value="">— none —</option>
          {fields.map((x) => <option key={x.key} value={x.key}>{x.label}</option>)}
        </select>
        <select
          value={bucket.sort?.direction ?? 'desc'}
          onChange={(e) =>
            onChange({
              sort: bucket.sort
                ? { ...bucket.sort, direction: e.target.value as any }
                : { field: 'added_at', direction: e.target.value as any },
            })
          }
          disabled={!bucket.sort}
        >
          <option value="desc">descending</option>
          <option value="asc">ascending</option>
        </select>
      </div>

      <div className="bucket-row">
        <label>Take</label>
        <input
          type="number"
          min={1}
          max={500}
          value={bucket.count}
          onChange={(e) =>
            onChange({ count: Math.max(1, Math.min(500, Number(e.target.value) || 1)) })
          }
        />
        <span className="hint">tracks</span>
      </div>
    </div>
  )
}
