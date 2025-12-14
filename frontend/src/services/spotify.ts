/**
 * Spotify Web Playback SDK wrapper.
 */

declare global {
  interface Window {
    Spotify: any
    onSpotifyWebPlaybackSDKReady: () => void
  }
}

class SpotifyService {
  private player: any = null
  private deviceId: string | null = null
  private isInitialized = false

  async initialize(): Promise<void> {
    if (this.isInitialized) {
      return
    }

    return new Promise((resolve, reject) => {
      // Check if SDK is already loaded
      if (window.Spotify) {
        this.createPlayer()
        resolve()
        return
      }

      // Load Spotify Web Playback SDK
      const script = document.createElement('script')
      script.src = 'https://sdk.scdn.co/spotify-player.js'
      script.async = true
      document.body.appendChild(script)

      window.onSpotifyWebPlaybackSDKReady = () => {
        this.createPlayer()
        resolve()
      }

      script.onerror = () => {
        reject(new Error('Failed to load Spotify Web Playback SDK'))
      }
    })
  }

  private createPlayer(): void {
    this.isInitialized = true
  }

  async setAccessToken(token: string): Promise<void> {
    if (!window.Spotify) {
      throw new Error('Spotify SDK not loaded')
    }

    this.player = new window.Spotify.Player({
      name: 'Pigify',
      getOAuthToken: (cb: (token: string) => void) => {
        cb(token)
      },
      volume: 0.5,
    })

    // Error handling
    this.player.addListener('initialization_error', ({ message }: { message: string }) => {
      console.error('Initialization error:', message)
    })

    this.player.addListener('authentication_error', ({ message }: { message: string }) => {
      console.error('Authentication error:', message)
    })

    this.player.addListener('account_error', ({ message }: { message: string }) => {
      console.error('Account error:', message)
    })

    // Ready
    this.player.addListener('ready', ({ device_id }: { device_id: string }) => {
      console.log('Ready with Device ID', device_id)
      this.deviceId = device_id
    })

    // Not Ready
    this.player.addListener('not_ready', ({ device_id }: { device_id: string }) => {
      console.log('Device ID has gone offline', device_id)
    })

    // Connect to the player
    await this.player.connect()
  }

  async play(trackUri: string): Promise<void> {
    if (!this.player || !this.deviceId) {
      throw new Error('Player not initialized')
    }

    await this.player.play({
      uris: [trackUri],
    })
  }

  async pause(): Promise<void> {
    if (!this.player) {
      throw new Error('Player not initialized')
    }

    await this.player.pause()
  }

  async resume(): Promise<void> {
    if (!this.player) {
      throw new Error('Player not initialized')
    }

    await this.player.resume()
  }

  async getCurrentState(): Promise<any> {
    if (!this.player) {
      return null
    }

    return await this.player.getCurrentState()
  }

  getDeviceId(): string | null {
    return this.deviceId
  }
}

export const spotifyService = new SpotifyService()

