import {
  Track,
  SortField,
  SortKeySpec,
  SortType,
  AudioFeatures,
  LastfmTrackHydration,
} from './api'

export interface SortableHydration {
  audio_features: Record<string, AudioFeatures | null>
  lastfm: Record<string, LastfmTrackHydration | null>
}

const collator = new Intl.Collator(undefined, {
  sensitivity: 'base',
  numeric: true,
})

function isMissing(v: unknown): boolean {
  return v === null || v === undefined || v === ''
}

function compareValues(a: unknown, b: unknown, type: SortType, dir: 'asc' | 'desc'): number {
  const aN = isMissing(a)
  const bN = isMissing(b)
  // Missing values always sort last regardless of direction.
  if (aN && bN) return 0
  if (aN) return 1
  if (bN) return -1

  const sign = dir === 'desc' ? -1 : 1
  let cmp = 0
  if (type === 'string') {
    cmp = collator.compare(String(a), String(b))
  } else if (type === 'date') {
    const at = new Date(String(a)).getTime()
    const bt = new Date(String(b)).getTime()
    cmp = (isNaN(at) ? 0 : at) - (isNaN(bt) ? 0 : bt)
  } else if (type === 'enum') {
    // booleans / categorical: false < true alphabetically by string form
    cmp = collator.compare(String(a), String(b))
  } else {
    cmp = Number(a) - Number(b)
  }
  return cmp * sign
}

/**
 * Resolve the value of a sort field for a given track, using hydration
 * data when the field's source is not the Track object itself.
 */
export function getSortValue(
  field: SortField,
  track: Track,
  hydration: SortableHydration
): unknown {
  if (field.source === 'spotify_track') {
    switch (field.key) {
      case 'name':
        return track.name
      case 'artist':
        return track.artists?.[0] ?? ''
      case 'album':
        return track.album
      case 'duration_ms':
        return track.duration_ms
      case 'added_at':
        return track.added_at
      case 'release_date':
        return track.release_date
      case 'popularity':
        return track.popularity
      case 'explicit':
        return track.explicit
      case 'track_number':
        return track.track_number
      default:
        return undefined
    }
  }
  if (field.source === 'audio_features') {
    const f = hydration.audio_features[track.id]
    if (!f) return undefined
    return (f as Record<string, unknown>)[field.key]
  }
  if (field.source === 'lastfm') {
    const l = hydration.lastfm[track.id]
    if (!l) return undefined
    if (field.key === 'lastfm_playcount') return l.playcount
    if (field.key === 'lastfm_listeners') return l.listeners
    if (field.key === 'lastfm_user_playcount') return l.user_playcount
    return undefined
  }
  return undefined
}

/**
 * Sort tracks using an ordered list of keys (each with its own direction).
 * Earlier keys take priority; later keys break ties. The sort is stable
 * (Array.prototype.sort is stable in modern JS engines) and locale-aware
 * for string fields.
 */
export function sortTracks(
  tracks: Track[],
  fields: SortField[],
  keys: SortKeySpec[],
  hydration: SortableHydration
): Track[] {
  const fieldByKey = new Map(fields.map((f) => [f.key, f]))
  const resolved = keys
    .map((k) => ({ spec: k, field: fieldByKey.get(k.field) }))
    .filter((r): r is { spec: SortKeySpec; field: SortField } => !!r.field)
  if (resolved.length === 0) return tracks

  return [...tracks].sort((a, b) => {
    for (const { spec, field } of resolved) {
      const c = compareValues(
        getSortValue(field, a, hydration),
        getSortValue(field, b, hydration),
        field.type,
        spec.direction
      )
      if (c !== 0) return c
    }
    return 0
  })
}

/** Which hydration sources does this sort spec depend on? */
export function requiredSources(
  fields: SortField[],
  keys: SortKeySpec[]
): Array<'audio_features' | 'lastfm'> {
  const out = new Set<'audio_features' | 'lastfm'>()
  const byKey = new Map(fields.map((f) => [f.key, f]))
  for (const k of keys) {
    const f = byKey.get(k.field)
    if (!f || !f.requires_hydration) continue
    if (f.source === 'audio_features') out.add('audio_features')
    if (f.source === 'lastfm') out.add('lastfm')
  }
  return [...out]
}

/** Normalize a saved preset into its `keys` list, accepting legacy shape. */
export function presetToKeys(p: {
  keys?: SortKeySpec[] | null
  primary?: SortKeySpec | null
  secondary?: SortKeySpec | null
}): SortKeySpec[] {
  if (p.keys && p.keys.length > 0) return p.keys
  const out: SortKeySpec[] = []
  if (p.primary) out.push(p.primary)
  if (p.secondary) out.push(p.secondary)
  return out
}
