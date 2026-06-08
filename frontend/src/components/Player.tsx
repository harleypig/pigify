import { useCallback, useEffect, useState } from "react";
import { spotifyService, type WebPlaybackState } from "../services/spotify";
import "./Player.css";

interface PlayerProps {
  trackUri: string;
}

function Player({ trackUri }: PlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentState, setCurrentState] = useState<WebPlaybackState | null>(
    null,
  );

  const playTrack = useCallback(async () => {
    try {
      await spotifyService.play(trackUri);
      setIsPlaying(true);
    } catch (error) {
      console.error("Error playing track:", error);
    }
  }, [trackUri]);

  const updateState = useCallback(async () => {
    try {
      const state = await spotifyService.getCurrentState();
      setCurrentState(state);
      if (state) {
        setIsPlaying(!state.paused);
      }
    } catch (_error) {
      // Silently handle errors
    }
  }, []);

  useEffect(() => {
    playTrack();
    const interval = setInterval(updateState, 1000);
    return () => clearInterval(interval);
  }, [updateState, playTrack]);

  const handlePlayPause = async () => {
    try {
      if (isPlaying) {
        await spotifyService.pause();
        setIsPlaying(false);
      } else {
        await spotifyService.resume();
        setIsPlaying(true);
      }
    } catch (error) {
      console.error("Error toggling play/pause:", error);
    }
  };

  const track = currentState?.track_window?.current_track;

  return (
    <div className="player">
      <div className="player-content">
        {track && (
          <>
            <div className="player-track-info">
              {track.album?.images?.[0]?.url && (
                <img
                  src={track.album.images[0].url}
                  alt={track.name}
                  className="player-track-image"
                />
              )}
              <div className="player-track-details">
                <div className="player-track-name">{track.name}</div>
                <div className="player-track-artist">
                  {track.artists.map((a) => a.name).join(", ")}
                </div>
              </div>
            </div>
            <div className="player-controls">
              <button
                type="button"
                className="player-play-pause"
                onClick={handlePlayPause}
                aria-label={isPlaying ? "Pause" : "Play"}
              >
                {isPlaying ? "⏸" : "▶"}
              </button>
            </div>
          </>
        )}
        {!track && <div className="player-status">Initializing player…</div>}
      </div>
    </div>
  );
}

export default Player;
