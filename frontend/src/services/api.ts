import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
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
}

