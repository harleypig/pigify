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

type SourceKind = 'liked' | 'playlist' | 'playlists' | 'all_playlists'

function parseSource(source: string): { kind: SourceKind; ids: string[] } {
  if (source === 'liked') return { kind: 'liked', ids: [] }
  if (source === 'all_playlists') return { kind: 'all_playlists', ids: [] }
  if (source.startsWith('playlists:')) {
    const ids = source
      .slice('playlists:'.length)
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    return { kind: 'playlists', ids }
  }
  if (source.startsWith('playlist:')) {
    const id = source.slice('playlist:'.length).trim()
    return { kind: 'playlist', ids: id ? [id] : [] }
  }
  return { kind: 'liked', ids: [] }
}

function buildSource(kind: SourceKind, ids: string[]): string {
  if (kind === 'liked') return 'liked'
  if (kind === 'all_playlists') return 'all_playlists'
  const clean = ids.filter(Boolean)
  if (clean.length === 0) return 'playlists:'
  if (clean.length === 1) return `playlist:${clean[0]}`
  return `playlists:${clean.join(',')}`
}

function blankRecipe(): Recipe {
  return { name: 'New filter', buckets: [blankBucket()], combine: 'in_order' }
}

export default function RecipeBuilder({ open, initial, onClose, onSaved }: Props) {
  const [fields, setFields] = useState<SortField[]>([])
  const [playlists, setPlaylists] = useState<Playlist[]>([])
  const [meDisplayName, setMeDisplayName] = useState<string>('')
  const [recipe, setRecipe] = useState<Recipe>(blankRecipe())
  const [preview, setPreview] = useState<RecipeResolveResponse | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    apiService.getSortFields().then((r) => setFields(r.fields)).catch(() => {})
    apiService.getCurrentUser().then((u) => setMeDisplayName(u.display_name || '')).catch(() => {})
    // Load all the user's playlists so the multi-select picker covers their
    // full library, not just the first page.
    ;(async () => {
      const all: Playlist[] = []
      const pageSize = 50
      let offset = 0
      while (offset < 1000) {
        try {
          const page = await apiService.getPlaylists(pageSize, offset)
          if (!page || page.length === 0) break
          all.push(...page)
          if (page.length < pageSize) break
          offset += pageSize
        } catch {
          break
        }
      }
      setPlaylists(all)
    })()
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
              meDisplayName={meDisplayName}
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
              {preview.tracks.slice(0, 100).map((t: Track, i: number) => {
                const sources = preview.track_sources?.[t.id] ?? []
                const sourceLabel = sources.map((s) => s.name).join(', ')
                return (
                  <div key={`${t.id}-${i}`} className="preview-row">
                    <span className="preview-num">{i + 1}</span>
                    <span className="preview-name">{t.name}</span>
                    <span className="preview-artist">{t.artists.join(', ')}</span>
                    {sourceLabel && (
                      <span className="preview-source" title={sourceLabel}>
                        from {sourceLabel}
                      </span>
                    )}
                  </div>
                )
              })}
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
  meDisplayName: string
  onChange: (patch: Partial<RecipeBucket>) => void
  onRemove: () => void
  onUpdateFilter: (fIdx: number, patch: Partial<RecipeFilter>) => void
  onAddFilter: () => void
  onRemoveFilter: (fIdx: number) => void
  canRemove: boolean
}) {
  const {
    bucket, index, fields, fieldByKey, playlists, meDisplayName,
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

      <BucketSourcePicker
        source={bucket.source}
        playlists={playlists}
        meDisplayName={meDisplayName}
        onChange={(s) => onChange({ source: s })}
      />


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

type GroupBy = 'none' | 'owner' | 'alpha'

function BucketSourcePicker(props: {
  source: string
  playlists: Playlist[]
  meDisplayName: string
  onChange: (source: string) => void
}) {
  const { source, playlists, meDisplayName, onChange } = props
  const parsed = parseSource(source)
  const selected = new Set(parsed.ids)
  const [query, setQuery] = useState('')
  const [groupBy, setGroupBy] = useState<GroupBy>('none')

  const setSelected = (next: Set<string>) => {
    onChange(buildSource('playlists', Array.from(next)))
  }

  const togglePlaylist = (id: string) => {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelected(next)
  }

  const onKindChange = (kind: SourceKind) => {
    if (kind === 'liked' || kind === 'all_playlists') {
      onChange(buildSource(kind, []))
    } else {
      onChange(buildSource('playlists', parsed.ids))
    }
  }

  const showList = parsed.kind === 'playlist' || parsed.kind === 'playlists'
  const uiKind: SourceKind = parsed.kind === 'playlist' ? 'playlists' : parsed.kind

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return playlists
    return playlists.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        (p.owner || '').toLowerCase().includes(q)
    )
  }, [playlists, query])

  const groups = useMemo(() => {
    if (groupBy === 'none') {
      return [{ label: '', items: filtered }]
    }
    if (groupBy === 'owner') {
      const mine: Playlist[] = []
      const byOwner = new Map<string, Playlist[]>()
      const me = (meDisplayName || '').toLowerCase()
      for (const p of filtered) {
        if (me && (p.owner || '').toLowerCase() === me) {
          mine.push(p)
        } else {
          const key = p.owner || 'Unknown'
          if (!byOwner.has(key)) byOwner.set(key, [])
          byOwner.get(key)!.push(p)
        }
      }
      const result: Array<{ label: string; items: Playlist[] }> = []
      if (mine.length) result.push({ label: 'Yours', items: mine })
      const others = Array.from(byOwner.entries()).sort((a, b) =>
        a[0].localeCompare(b[0])
      )
      for (const [owner, items] of others) {
        result.push({ label: owner, items })
      }
      return result
    }
    // alphabetical: bucket by first character of name
    const buckets = new Map<string, Playlist[]>()
    for (const p of filtered) {
      const first = (p.name || '').trim().charAt(0).toUpperCase()
      const key = first && /[A-Z]/.test(first) ? first : '#'
      if (!buckets.has(key)) buckets.set(key, [])
      buckets.get(key)!.push(p)
    }
    return Array.from(buckets.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([label, items]) => ({
        label,
        items: items.slice().sort((a, b) => a.name.localeCompare(b.name)),
      }))
  }, [filtered, groupBy, meDisplayName])

  const visibleIds = useMemo(() => filtered.map((p) => p.id), [filtered])
  const allVisibleSelected =
    visibleIds.length > 0 && visibleIds.every((id) => selected.has(id))

  const selectAllVisible = () => {
    const next = new Set(selected)
    for (const id of visibleIds) next.add(id)
    setSelected(next)
  }
  const clearVisible = () => {
    const next = new Set(selected)
    for (const id of visibleIds) next.delete(id)
    setSelected(next)
  }

  return (
    <div className="bucket-source">
      <div className="bucket-row">
        <label>Source</label>
        <select value={uiKind} onChange={(e) => onKindChange(e.target.value as SourceKind)}>
          <option value="liked">Liked Songs</option>
          <option value="playlists">Specific playlists…</option>
          <option value="all_playlists">All my playlists</option>
        </select>
      </div>
      {showList && (
        <>
          <div className="source-controls">
            <input
              className="source-search"
              type="search"
              placeholder="Search playlists…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <select
              className="source-group"
              value={groupBy}
              onChange={(e) => setGroupBy(e.target.value as GroupBy)}
              title="Group playlists"
            >
              <option value="none">No grouping</option>
              <option value="owner">By owner</option>
              <option value="alpha">Alphabetical</option>
            </select>
            <button
              type="button"
              className="source-bulk"
              onClick={allVisibleSelected ? clearVisible : selectAllVisible}
              disabled={visibleIds.length === 0}
              title={
                allVisibleSelected
                  ? 'Clear all currently visible playlists'
                  : 'Select all currently visible playlists'
              }
            >
              {allVisibleSelected ? 'Clear visible' : 'Select visible'}
            </button>
          </div>
          <div className="bucket-source-list">
            {playlists.length === 0 && (
              <div className="hint">No playlists loaded yet.</div>
            )}
            {playlists.length > 0 && filtered.length === 0 && (
              <div className="hint">No playlists match “{query}”.</div>
            )}
            {groups.map((g, gi) => (
              <div key={gi} className="source-group-block">
                {g.label && groupBy !== 'none' && (
                  <div className="source-group-label">{g.label}</div>
                )}
                {g.items.map((p) => (
                  <label key={p.id} className="source-check">
                    <input
                      type="checkbox"
                      checked={selected.has(p.id)}
                      onChange={() => togglePlaylist(p.id)}
                    />
                    <span className="source-name">{p.name}</span>
                    {groupBy !== 'owner' && p.owner && (
                      <span className="source-owner">{p.owner}</span>
                    )}
                  </label>
                ))}
              </div>
            ))}
          </div>
          {selected.size === 0 && playlists.length > 0 && (
            <div className="hint">Pick at least one playlist.</div>
          )}
          {selected.size > 1 && (
            <div className="hint">
              {selected.size} playlists selected — duplicate tracks are merged.
            </div>
          )}
        </>
      )}
      {parsed.kind === 'all_playlists' && (
        <div className="hint">
          Pulls every playlist you own or follow; tracks appearing in multiple
          playlists are counted once.
        </div>
      )}
    </div>
  )
}
