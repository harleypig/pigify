/**
 * Owner-surface theming (level 1, owner side).
 *
 * The login and other system pages (the "owner surface") render under an
 * OWNER-controlled theme, independent of the working-area user pick
 * (`pigify.theme`). The deployer sets the default here; a visitor can flip
 * light/dark with the per-dialog toggle, but that choice is **ephemeral** —
 * it lives only in component state, so every fresh view starts from the owner
 * default again. See docs/branding-design.md.
 *
 * The pure helpers below are exported for unit tests; there is no DOM glue —
 * the resolved theme is applied by scoping `data-theme` to the login subtree
 * (Login.tsx), not by touching `<html>`.
 */

import {
  prefersDark,
  type ResolvedTheme,
  resolveTheme,
  type ThemeChoice,
} from "./theme";

/**
 * The owner default for the system/owner surface. **Owner config:** the
 * deployer edits this constant and rebuilds (`system` follows the OS
 * preference; `dark` / `light` force one). Provisioning is build-time for
 * now; a runtime-injected value can replace this later without touching
 * callers — see docs/branding-design.md › provisioning.
 */
export const OWNER_THEME_DEFAULT: ThemeChoice = "system";

/** The owner default resolved to a concrete theme against the OS preference. */
export function resolveOwnerDefault(): ResolvedTheme {
  return resolveTheme(OWNER_THEME_DEFAULT, prefersDark());
}

/** The opposite theme — what the ephemeral per-dialog toggle flips to. */
export function flipTheme(theme: ResolvedTheme): ResolvedTheme {
  return theme === "dark" ? "light" : "dark";
}
