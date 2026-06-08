/**
 * Spotify Web Playback SDK wrapper.
 *
 * The interfaces below cover only the slice of the Web Playback SDK this app
 * actually uses; they are not a complete typing of the SDK.
 */

/** A track within the SDK playback state (`track_window.current_track`). */
export interface WebPlaybackTrack {
  name: string;
  uri: string;
  artists: Array<{ name: string; uri?: string }>;
  album: {
    name?: string;
    uri?: string;
    images: Array<{ url: string }>;
  };
}

/** The object returned by `player.getCurrentState()`. */
export interface WebPlaybackState {
  paused: boolean;
  position: number;
  duration: number;
  track_window: {
    current_track: WebPlaybackTrack;
  };
}

interface SpotifyErrorEvent {
  message: string;
}

interface SpotifyReadyEvent {
  device_id: string;
}

/** The minimal `Spotify.Player` surface this app calls. */
interface SpotifyPlayer {
  addListener(
    event: "ready" | "not_ready",
    cb: (e: SpotifyReadyEvent) => void,
  ): void;
  addListener(
    event: "initialization_error" | "authentication_error" | "account_error",
    cb: (e: SpotifyErrorEvent) => void,
  ): void;
  connect(): Promise<boolean>;
  play(options: { uris: string[] }): Promise<void>;
  pause(): Promise<void>;
  resume(): Promise<void>;
  getCurrentState(): Promise<WebPlaybackState | null>;
}

interface SpotifyPlayerConstructor {
  new (options: {
    name: string;
    getOAuthToken: (cb: (token: string) => void) => void;
    volume?: number;
  }): SpotifyPlayer;
}

interface SpotifyNamespace {
  Player: SpotifyPlayerConstructor;
}

declare global {
  interface Window {
    Spotify: SpotifyNamespace;
    onSpotifyWebPlaybackSDKReady: () => void;
  }
}

class SpotifyService {
  private player: SpotifyPlayer | null = null;
  private deviceId: string | null = null;
  private isInitialized = false;

  async initialize(): Promise<void> {
    if (this.isInitialized) {
      return;
    }

    return new Promise((resolve, reject) => {
      // Check if SDK is already loaded
      if (window.Spotify) {
        this.createPlayer();
        resolve();
        return;
      }

      // Load Spotify Web Playback SDK
      const script = document.createElement("script");
      script.src = "https://sdk.scdn.co/spotify-player.js";
      script.async = true;
      document.body.appendChild(script);

      window.onSpotifyWebPlaybackSDKReady = () => {
        this.createPlayer();
        resolve();
      };

      script.onerror = () => {
        reject(new Error("Failed to load Spotify Web Playback SDK"));
      };
    });
  }

  private createPlayer(): void {
    this.isInitialized = true;
  }

  async setAccessToken(token: string): Promise<void> {
    if (!window.Spotify) {
      throw new Error("Spotify SDK not loaded");
    }

    this.player = new window.Spotify.Player({
      name: "Pigify",
      getOAuthToken: (cb: (token: string) => void) => {
        cb(token);
      },
      volume: 0.5,
    });

    // Error handling
    this.player.addListener(
      "initialization_error",
      ({ message }: { message: string }) => {
        console.error("Initialization error:", message);
      },
    );

    this.player.addListener(
      "authentication_error",
      ({ message }: { message: string }) => {
        console.error("Authentication error:", message);
      },
    );

    this.player.addListener(
      "account_error",
      ({ message }: { message: string }) => {
        console.error("Account error:", message);
      },
    );

    // Ready
    this.player.addListener("ready", ({ device_id }: { device_id: string }) => {
      console.log("Ready with Device ID", device_id);
      this.deviceId = device_id;
    });

    // Not Ready
    this.player.addListener(
      "not_ready",
      ({ device_id }: { device_id: string }) => {
        console.log("Device ID has gone offline", device_id);
      },
    );

    // Connect to the player
    await this.player.connect();
  }

  async play(trackUri: string): Promise<void> {
    if (!this.player || !this.deviceId) {
      throw new Error("Player not initialized");
    }

    await this.player.play({
      uris: [trackUri],
    });
  }

  async pause(): Promise<void> {
    if (!this.player) {
      throw new Error("Player not initialized");
    }

    await this.player.pause();
  }

  async resume(): Promise<void> {
    if (!this.player) {
      throw new Error("Player not initialized");
    }

    await this.player.resume();
  }

  async getCurrentState(): Promise<WebPlaybackState | null> {
    if (!this.player) {
      return null;
    }

    return await this.player.getCurrentState();
  }

  getDeviceId(): string | null {
    return this.deviceId;
  }
}

export const spotifyService = new SpotifyService();
