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
    event:
      | "initialization_error"
      | "authentication_error"
      | "account_error"
      | "playback_error",
    cb: (e: SpotifyErrorEvent) => void,
  ): void;
  addListener(event: "autoplay_failed", cb: () => void): void;
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
  private onReadyChange: ((deviceId: string | null) => void) | null = null;

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

  /**
   * Register this browser as a Spotify Connect device. `getToken` is invoked
   * by the SDK whenever it needs a (fresh) OAuth access token — so token
   * refresh is handled by re-fetching rather than capturing one statically.
   * `onReadyChange` fires with the device id when the browser device becomes
   * ready, and with null when it goes offline (or never registers, e.g. a
   * non-Premium account). Calling it again after a successful connect just
   * re-reports the current device id.
   */
  async connect(
    getToken: () => Promise<string>,
    onReadyChange: (deviceId: string | null) => void,
  ): Promise<void> {
    await this.initialize();
    if (!window.Spotify) {
      throw new Error("Spotify SDK not loaded");
    }
    console.log(
      "Web Playback: SDK present:",
      !!window.Spotify,
      "| secureContext:",
      window.isSecureContext,
    );
    this.onReadyChange = onReadyChange;

    if (this.player) {
      onReadyChange(this.deviceId);
      return;
    }

    this.player = new window.Spotify.Player({
      name: "Pigify - Web",
      getOAuthToken: (cb: (token: string) => void) => {
        getToken()
          .then((t) => {
            console.log(
              "Web Playback: delivering token to SDK (length",
              t?.length,
              ")",
            );
            cb(t);
          })
          .catch((e) => console.error("Web Playback token fetch failed:", e));
      },
      volume: 0.5,
    });

    this.player.addListener(
      "initialization_error",
      ({ message }: { message: string }) =>
        console.error("Web Playback init error:", message),
    );
    this.player.addListener(
      "authentication_error",
      ({ message }: { message: string }) =>
        console.error("Web Playback auth error:", message),
    );
    this.player.addListener(
      "account_error",
      ({ message }: { message: string }) =>
        console.error(
          "Web Playback account error (Premium required?):",
          message,
        ),
    );
    this.player.addListener(
      "playback_error",
      ({ message }: { message: string }) =>
        console.error("Web Playback playback error:", message),
    );
    this.player.addListener("autoplay_failed", () =>
      console.warn("Web Playback: autoplay failed — a user gesture is needed"),
    );

    this.player.addListener("ready", ({ device_id }: { device_id: string }) => {
      console.log("Web Playback ready — registered device id:", device_id);
      this.deviceId = device_id;
      this.onReadyChange?.(device_id);
    });
    this.player.addListener(
      "not_ready",
      ({ device_id }: { device_id: string }) => {
        console.warn("Web Playback device went offline:", device_id);
        this.deviceId = null;
        this.onReadyChange?.(null);
      },
    );

    const connected = await this.player.connect();
    console.log("Web Playback connect() returned:", connected);
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
