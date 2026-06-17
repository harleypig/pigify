/**
 * Theme selection (level 1): pick a built-in theme, persist it, and apply it
 * by setting `data-theme` on <html>. The themes themselves are CSS token sets
 * (src/themes/*.css, compiled from *.theme.yaml); this module only chooses
 * which one is active.
 *
 * The pure helpers (validation, resolution) are exported for unit tests; the
 * DOM/`matchMedia` glue lives in `applyResolvedTheme` / `initTheme` /
 * `setThemeChoice`.
 */

/** A user choice: a concrete theme, or "system" to follow the OS preference. */
export const THEME_CHOICES = ["system", "dark", "light"] as const;
export type ThemeChoice = (typeof THEME_CHOICES)[number];

/** A concrete, applied theme (what `data-theme` is set to). */
export type ResolvedTheme = "dark" | "light";

export const THEME_STORAGE_KEY = "pigify.theme";

const CHOICE_LABEL: Record<ThemeChoice, string> = {
  system: "System",
  dark: "Dark",
  light: "Light",
};

export function themeChoiceLabel(choice: ThemeChoice): string {
  return CHOICE_LABEL[choice];
}

export function isThemeChoice(value: unknown): value is ThemeChoice {
  return (
    typeof value === "string" &&
    (THEME_CHOICES as readonly string[]).includes(value)
  );
}

/** The stored choice, or "system" when absent/invalid. */
export function readStoredChoice(
  read: (key: string) => string | null,
): ThemeChoice {
  const raw = read(THEME_STORAGE_KEY);
  return isThemeChoice(raw) ? raw : "system";
}

/** Resolve a choice to a concrete theme, given the OS dark-mode preference. */
export function resolveTheme(
  choice: ThemeChoice,
  prefersDark: boolean,
): ResolvedTheme {
  if (choice === "system") return prefersDark ? "dark" : "light";
  return choice;
}

// --- DOM / browser glue (thin; not unit-tested) ---

const DARK_QUERY = "(prefers-color-scheme: dark)";

function prefersDark(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia(DARK_QUERY).matches
  );
}

export function applyResolvedTheme(theme: ResolvedTheme): void {
  document.documentElement.dataset.theme = theme;
}

/** Read + apply the stored choice, and keep "system" in sync with the OS. */
export function initTheme(): void {
  const choice = readStoredChoice((k) => localStorage.getItem(k));
  applyResolvedTheme(resolveTheme(choice, prefersDark()));

  if (typeof window !== "undefined" && window.matchMedia) {
    window.matchMedia(DARK_QUERY).addEventListener("change", (e) => {
      // Only follow the OS while the user's choice is "system".
      if (readStoredChoice((k) => localStorage.getItem(k)) === "system") {
        applyResolvedTheme(e.matches ? "dark" : "light");
      }
    });
  }
}

export function getThemeChoice(): ThemeChoice {
  return readStoredChoice((k) => localStorage.getItem(k));
}

/** Persist a choice and apply it immediately. */
export function setThemeChoice(choice: ThemeChoice): void {
  localStorage.setItem(THEME_STORAGE_KEY, choice);
  applyResolvedTheme(resolveTheme(choice, prefersDark()));
}
