import axios from 'axios'

const apiClient = axios.create({
  baseURL: '',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

export interface Playlist {
  id: string
  name: string
  description: string
  images: Array<{ url: string; height?: number; width?: number }>
  owner: string
  track_count: number
  public: boolean
}

export interface Track {
  id: string
  name: string
  artists: string[]
  album: string
  duration_ms: number
  uri: string
  image_url: string
  explicit: boolean
  added_at?: string | null
  popularity?: number | null
  release_date?: string | null
  disc_number?: number | null
  track_number?: number | null
}

export type SortType = 'string' | 'number' | 'date' | 'enum'
export type SortSource = 'spotify_track' | 'audio_features' | 'lastfm'
export type SortDirection = 'asc' | 'desc'

export interface SortField {
  key: string
  label: string
  type: SortType
  source: SortSource
  requires_hydration: boolean
  group: string
  default: boolean
}

export interface SortKeySpec {
  field: string
  direction: SortDirection
}

export interface SortPreset {
  name: string
  keys: SortKeySpec[]
  // Legacy fields kept only so the type accepts old payloads while we
  // normalize them on read. New code should always read/write `keys`.
  primary?: SortKeySpec
  secondary?: SortKeySpec | null
}

export interface AudioFeatures {
  tempo?: number | null
  energy?: number | null
  danceability?: number | null
  valence?: number | null
  acousticness?: number | null
  instrumentalness?: number | null
  loudness?: number | null
  speechiness?: number | null
}

export interface LastfmTrackHydration {
  playcount?: number | null
  listeners?: number | null
  user_playcount?: number | null
  tags?: string[]
}

export interface HydrationResult {
  audio_features: Record<string, AudioFeatures | null>
  lastfm: Record<string, LastfmTrackHydration | null>
  warnings: string[]
}

export interface User {
  id: string
  display_name: string
  email?: string
  images: Array<{ url: string; height?: number; width?: number }>
}

export interface Profile {
  spotify_id: string
  spotify_display_name?: string | null
  custom_display_name?: string | null
  display_name: string
}

export const apiService = {
  async getCurrentUser(): Promise<User> {
    const response = await apiClient.get('/api/auth/me')
    return response.data
  },

  async getAccessToken(): Promise<string> {
    const response = await apiClient.get('/api/auth/token')
    return response.data.access_token
  },

  async logout(): Promise<void> {
    await apiClient.post('/api/auth/logout')
  },

  async getProfile(): Promise<Profile> {
    const r = await apiClient.get('/api/me/profile')
    return r.data
  },

  async updateProfile(customDisplayName: string | null): Promise<Profile> {
    const r = await apiClient.put('/api/me/profile', {
      custom_display_name: customDisplayName,
    })
    return r.data
  },

  async getPlaylists(limit = 50, offset = 0): Promise<Playlist[]> {
    const response = await apiClient.get('/api/playlists', {
      params: { limit, offset },
    })
    return response.data
  },

  async getPlaylist(playlistId: string): Promise<Playlist> {
    const response = await apiClient.get(`/api/playlists/${playlistId}`)
    return response.data
  },

  async getPlaylistTracks(
    playlistId: string,
    limit = 100,
    offset = 0
  ): Promise<Track[]> {
    const response = await apiClient.get(`/api/playlists/${playlistId}/tracks`, {
      params: { limit, offset },
    })
    return response.data
  },

  async getAllPlaylistTracks(playlistId: string): Promise<Track[]> {
    const response = await apiClient.get(`/api/playlists/${playlistId}/tracks`, {
      params: { all: true },
    })
    return response.data
  },

  async getSortFields(): Promise<{ fields: SortField[] }> {
    const response = await apiClient.get('/api/playlists/sort/fields')
    return response.data
  },

  async listSortPresets(): Promise<SortPreset[]> {
    const response = await apiClient.get('/api/playlists/sort/presets')
    return response.data
  },

  async saveSortPreset(preset: SortPreset): Promise<SortPreset[]> {
    const response = await apiClient.post('/api/playlists/sort/presets', preset)
    return response.data
  },

  async deleteSortPreset(name: string): Promise<SortPreset[]> {
    const response = await apiClient.delete(
      `/api/playlists/sort/presets/${encodeURIComponent(name)}`
    )
    return response.data
  },

  async hydrateTracks(
    playlistId: string,
    trackIds: string[],
    sources: Array<'audio_features' | 'lastfm'>,
    trackMeta?: Array<{ id: string; name: string; artist: string }>
  ): Promise<HydrationResult> {
    const response = await apiClient.post(
      `/api/playlists/${playlistId}/hydrate`,
      { track_ids: trackIds, sources, track_meta: trackMeta }
    )
    return response.data
  },

  async reorderPlaylist(
    playlistId: string,
    targetUris: string[]
  ): Promise<{ applied: boolean; ops: number; snapshot_id: string | null; undo_available: boolean }> {
    const response = await apiClient.post(
      `/api/playlists/${playlistId}/reorder`,
      { target_uris: targetUris }
    )
    return response.data
  },

  async undoReorder(playlistId: string): Promise<{ restored: boolean; tracks: number }> {
    const response = await apiClient.post(`/api/playlists/${playlistId}/undo`)
    return response.data
  },

  async getUndoStatus(
    playlistId: string
  ): Promise<{ available: boolean; applied_at: number | null }> {
    const response = await apiClient.get(`/api/playlists/${playlistId}/undo-status`)
    return response.data
  },

  async getPlaybackState(): Promise<any> {
    const response = await apiClient.get('/api/player/state')
    return response.data
  },

  async playTrack(trackUri?: string, deviceId?: string): Promise<void> {
    await apiClient.put('/api/player/play', { track_uri: trackUri ?? null, device_id: deviceId ?? null })
  },

  async pausePlayback(): Promise<void> {
    await apiClient.put('/api/player/pause')
  },

  async nextTrack(): Promise<void> {
    await apiClient.post('/api/player/next')
  },

  async previousTrack(): Promise<void> {
    await apiClient.post('/api/player/previous')
  },

  async seekTo(positionMs: number): Promise<void> {
    await apiClient.put(`/api/player/seek?position_ms=${Math.round(positionMs)}`)
  },

  async getAudioAnalysis(trackId: string, bars = 80): Promise<{ bars: number[]; duration: number }> {
    const response = await apiClient.get(`/api/player/analysis/${trackId}`, { params: { bars } })
    return response.data
  },

  async getConnections(): Promise<Record<string, ConnectionStatus>> {
    const response = await apiClient.get('/api/integrations/connections')
    return response.data
  },

  async getLastfmStatus(): Promise<{ connection: ConnectionStatus; status: LastfmStatus }> {
    const response = await apiClient.get('/api/integrations/lastfm/status')
    return response.data
  },

  async disconnectLastfm(): Promise<void> {
    await apiClient.post('/api/integrations/lastfm/disconnect')
  },

  async getLastfmQueue(): Promise<LastfmQueueResponse> {
    const r = await apiClient.get('/api/integrations/lastfm/queue')
    return r.data
  },

  async flushLastfmQueue(): Promise<LastfmQueueFlushResult> {
    const r = await apiClient.post('/api/integrations/lastfm/queue/flush')
    return r.data
  },

  async deleteLastfmQueueEntry(id: number): Promise<void> {
    await apiClient.delete(`/api/integrations/lastfm/queue/${id}`)
  },

  async clearLastfmQueue(
    ids?: number[]
  ): Promise<LastfmQueueClearResult> {
    const r = await apiClient.delete('/api/integrations/lastfm/queue', {
      data: ids ? { ids } : {},
    })
    return r.data
  },

  async getTrackDetail(spotifyTrackId: string): Promise<TrackDetail> {
    const response = await apiClient.get(`/api/integrations/track-detail/${spotifyTrackId}`)
    return response.data
  },

  // -------- Favorites / likes sync --------
  async getFavoritesStatus(): Promise<FavoritesStatus> {
    const r = await apiClient.get('/api/favorites/status')
    return r.data
  },

  async checkFavorites(
    items: Array<{ track_id?: string; name: string; artist: string }>
  ): Promise<Favorite[]> {
    if (items.length === 0) return []
    const params = new URLSearchParams()
    for (const it of items) {
      params.append('track_id', it.track_id ?? '')
      params.append('name', it.name)
      params.append('artist', it.artist)
    }
    const r = await apiClient.get(`/api/favorites/check?${params.toString()}`)
    return r.data
  },

  async loveTrack(track: FavoriteWriteBody): Promise<WriteThroughResult> {
    const r = await apiClient.post('/api/favorites/love', track)
    return r.data
  },

  async unloveTrack(track: FavoriteWriteBody): Promise<WriteThroughResult> {
    const r = await apiClient.post('/api/favorites/unlove', track)
    return r.data
  },

  async syncFavorites(maxTracks = 500): Promise<SyncSummary> {
    const r = await apiClient.post('/api/favorites/sync', { max_tracks: maxTracks })
    return r.data
  },

  async resolveFavoriteConflict(
    index: number,
    choice: 'love_both' | 'unlove_both' | 'keep'
  ): Promise<WriteThroughResult> {
    const r = await apiClient.post('/api/favorites/resolve-conflict', { index, choice })
    return r.data
  },

  async updateFavoritesSettings(intervalMinutes: number): Promise<FavoritesStatus> {
    const r = await apiClient.put('/api/favorites/settings', {
      background_interval_minutes: intervalMinutes,
    })
    return r.data
  },
}

// ============================ Recipes (filtered playlists) ================

export type FilterOp =
  | 'lt' | 'lte' | 'gt' | 'gte' | 'eq' | 'ne'
  | 'between' | 'contains' | 'in' | 'not_in'

export interface RecipeFilter {
  field: string
  op: FilterOp
  value?: any
  value2?: any
}

export interface RecipeSort {
  field: string
  direction: SortDirection
}

export type CombineStrategy = 'in_order' | 'interleave' | 'shuffled'

export interface RecipeBucket {
  name?: string | null
  source: string
  filters: RecipeFilter[]
  sort?: RecipeSort | null
  count: number
}

export interface Recipe {
  name: string
  buckets: RecipeBucket[]
  combine: CombineStrategy
}

export interface StoredRecipe extends Recipe {
  id: string
  created_at: string
  updated_at: string
}

export interface RecipeTrackSource {
  id: string
  name: string
}

export interface RecipeResolveResponse {
  tracks: Track[]
  warnings: string[]
  bucket_counts: number[]
  track_sources: Record<string, RecipeTrackSource[]>
  resolved_at: string
}

export interface RecipePlayResponse {
  started: boolean
  track_count: number
  queued: number
  warnings: string[]
}

export interface RecipeMaterializeResponse {
  playlist_id: string
  playlist_url: string | null
  track_count: number
}

export const recipesApi = {
  async list(): Promise<StoredRecipe[]> {
    const r = await apiClient.get('/api/recipes')
    return r.data
  },
  async create(recipe: Recipe): Promise<StoredRecipe> {
    const r = await apiClient.post('/api/recipes', recipe)
    return r.data
  },
  async update(id: string, recipe: Recipe): Promise<StoredRecipe> {
    const r = await apiClient.put(`/api/recipes/${id}`, recipe)
    return r.data
  },
  async remove(id: string): Promise<StoredRecipe[]> {
    const r = await apiClient.delete(`/api/recipes/${id}`)
    return r.data
  },
  async resolve(recipe: Recipe): Promise<RecipeResolveResponse> {
    const r = await apiClient.post('/api/recipes/resolve', recipe)
    return r.data
  },
  async resolveSaved(id: string): Promise<RecipeResolveResponse> {
    const r = await apiClient.post(`/api/recipes/${id}/resolve`)
    return r.data
  },
  async play(id: string, uris?: string[]): Promise<RecipePlayResponse> {
    const r = await apiClient.post(`/api/recipes/${id}/play`, { uris: uris ?? null })
    return r.data
  },
  async playAdhoc(recipe: Recipe): Promise<RecipePlayResponse> {
    const r = await apiClient.post('/api/recipes/play-adhoc', recipe)
    return r.data
  },
  async materialize(
    id: string,
    opts: { name?: string; description?: string; public?: boolean; uris?: string[] } = {}
  ): Promise<RecipeMaterializeResponse> {
    const r = await apiClient.post(`/api/recipes/${id}/materialize`, opts)
    return r.data
  },
}

export type Tier = 'none' | 'public' | 'authenticated'

export interface ConnectionStatus {
  service: string
  tier: Tier
  display_name: string
  connected_account?: string | null
  last_error?: string | null
}

export interface LastfmQueueEntry {
  id: number
  artist: string
  track: string
  album?: string | null
  duration_sec?: number | null
  timestamp: number
  attempts: number
  last_error?: string | null
  next_attempt_at?: string | null
  queued_at?: string | null
}

export interface LastfmQueueResponse {
  entries: LastfmQueueEntry[]
  count: number
}

export interface LastfmQueueFlushResult {
  attempted: number
  succeeded: number
  remaining: number
  error?: string | null
}

export interface LastfmQueueClearResult {
  deleted: number
  remaining: number
}

export interface LastfmStatus {
  now_playing?: { artist: string; track: string; album?: string; duration_sec?: number } | null
  queued?: number
  last_scrobble_at?: number | null
}

export interface TrackDetail {
  spotify: {
    id: string
    name: string
    artists: string[]
    album?: string
    release_date?: string
    duration_ms?: number
    explicit?: boolean
    isrc?: string
    external_url?: string
  }
  connections: Record<string, ConnectionStatus>
  lastfm?: {
    tier: Tier
    url?: string
    playcount?: number | null
    listeners?: number | null
    user_playcount?: number | null
    user_loved?: boolean | null
    tags?: string[]
    summary?: string | null
    similar?: Array<{ name: string; artist: string; url?: string; match: number }>
    error?: string
  }
  musicbrainz?: {
    mbid: string
    title: string
    length_ms?: number
    artists: Array<{ name: string; mbid: string }>
    releases: Array<{
      title: string
      mbid: string
      date?: string
      country?: string
      release_group_mbid?: string
      release_group_type?: string
    }>
    isrcs: string[]
    tags: string[]
  }
  wikipedia?: {
    tier: Tier
    title: string
    description?: string | null
    extract: string
    url: string
    thumbnail?: string | null
  }
}

export interface TrackIdentity {
  spotify_id?: string | null
  spotify_uri?: string | null
  name: string
  artist: string
  album?: string | null
  image_url?: string | null
}

export interface FavoriteWriteBody extends TrackIdentity {}

export interface Favorite {
  track: TrackIdentity
  sources: Record<string, boolean | null>
  loved_at: Record<string, string | null>
}

export interface ServiceResult {
  service: string
  ok: boolean
  skipped: boolean
  error?: string | null
}

export interface WriteThroughResult {
  track_id?: string | null
  action: 'love' | 'unlove'
  results: ServiceResult[]
}

export interface Conflict {
  track: TrackIdentity
  loved_on: string[]
  not_loved_on: string[]
}

export interface SyncSummary {
  ran_at: string
  services_checked: string[]
  spotify_count: number
  lastfm_count: number
  matched: number
  conflicts: Conflict[]
  error?: string | null
}

export interface FavoritesConnectionStatus {
  service: string
  connected: boolean
  username?: string | null
  detail?: string | null
}

export interface FavoritesStatus {
  connections: FavoritesConnectionStatus[]
  last_sync: SyncSummary | null
  background_interval_minutes: number
  pending_conflicts: Conflict[]
}

