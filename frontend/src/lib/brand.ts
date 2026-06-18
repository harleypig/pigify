/**
 * Brand mark configuration (owner-level, build-time).
 *
 * The brand mark — the logo + wordmark shown in the login hero and the app
 * header — is the deployer's to set, not a user setting. This is the
 * build-time provisioning seam: the owner edits `BRAND` and rebuilds (the same
 * pattern as `OWNER_THEME_DEFAULT` in `lib/ownerTheme`). A runtime-injected
 * value can replace this constant later without touching `<Brand>` — see
 * docs/branding-design.md › Provisioning.
 *
 * ICEBOX: 2026-06-18 — runtime brand injection / no-rebuild white-label.
 * To let the *average owner* re-skin the published image WITHOUT a rebuild
 * (no toolchain, no source edit), have the SPA fetch a mounted brand config +
 * logo at startup (e.g. /brand/config.json, /brand/logo.png served by nginx)
 * and feed it here / into OWNER_THEME_DEFAULT / the theme. The compiled-CSS
 * theme is the biggest blocker (colours/fonts need the YAML→CSS build), so a
 * runtime path would also serve a mounted theme CSS. Deferred (build-time was
 * chosen); revisit on request. Full sketch in branding-design.md › Runtime
 * branding (future).
 *
 * One structure is shared across surfaces (same `mode` and `layout`
 * everywhere); only the overall *size* differs per surface, which stays in
 * each surface's CSS. The `--brand-logo-*` alignment knobs (theme.css) tune
 * the fit.
 */

import logoUrl from "../assets/pigify-logo.png";

/** lockup = image + wordmark; wordmark = text only; image = a logotype. */
export type BrandMode = "lockup" | "wordmark" | "image";

/** Where the image sits relative to the wordmark (the lockup's flex flow). */
export type BrandLayout =
  | "image-left"
  | "image-right"
  | "image-above"
  | "image-below";

export interface BrandConfig {
  mode: BrandMode;
  layout: BrandLayout;
  /** The wordmark text; also the image's accessible name in `image` mode. */
  wordmark: string;
  /** The logo asset (unused in `wordmark` mode). */
  image: string;
}

/** Owner config — edit + rebuild to rebrand. */
export const BRAND: BrandConfig = {
  mode: "lockup",
  layout: "image-left",
  wordmark: "pigify",
  image: logoUrl,
};
