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
}

export interface User {
  id: string
  display_name: string
  email?: string
  images: Array<{ url: string; height?: number; width?: number }>
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

  async getTrackDetail(spotifyTrackId: string): Promise<TrackDetail> {
    const response = await apiClient.get(`/api/integrations/track-detail/${spotifyTrackId}`)
    return response.data
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
}

