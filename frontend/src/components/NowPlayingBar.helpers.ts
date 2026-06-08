// Framework-free pure helper lifted out of NowPlayingBar.tsx for direct unit
// testing (see NowPlayingBar.helpers.test.ts). Note: this clamps negatives to
// 0:00 and floors — distinct from TrackInfoPanel's formatDuration, which maps
// 0/undefined to "" and rounds. The two intentionally differ.

/** Format a millisecond playback position as `m:ss` (negatives clamp to 0). */
export function formatMs(ms: number): string {
  const totalSec = Math.floor(Math.max(0, ms) / 1000);
  const mins = Math.floor(totalSec / 60);
  const secs = totalSec % 60;
  return `${mins}:${String(secs).padStart(2, "0")}`;
}
