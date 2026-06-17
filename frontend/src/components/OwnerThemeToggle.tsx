import type { ResolvedTheme } from "../lib/theme";

interface OwnerThemeToggleProps {
  /** The theme currently applied to the owner surface. */
  theme: ResolvedTheme;
  /** Flip to the other theme (ephemeral — never persisted). */
  onToggle: () => void;
}

/**
 * Ephemeral light/dark toggle for the owner surface (login / system pages).
 *
 * It shows the icon for the theme it would switch *to* (a sun while dark, a
 * moon while light) and flips on click. This is a readability convenience,
 * not a preference: it never persists and resets to the owner default on the
 * next view (see lib/ownerTheme).
 */
export function OwnerThemeToggle({ theme, onToggle }: OwnerThemeToggleProps) {
  const next = theme === "dark" ? "light" : "dark";
  return (
    <button
      type="button"
      className="owner-theme-toggle"
      onClick={onToggle}
      aria-label={`Switch to ${next} mode`}
      title={`Switch to ${next} mode`}
    >
      {theme === "dark" ? <SunIcon /> : <MoonIcon />}
    </button>
  );
}

function SunIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
    </svg>
  );
}
