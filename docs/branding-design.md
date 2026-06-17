# Branding & system-page theming — design note

**Status:** partly shipped — *Increment 2* of the branding work.
Increment 1 (the per-logo alignment knobs) shipped; see
[`THEMING.md` › Branding the logo](THEMING.md). **The owner-surface theme
scope + ephemeral toggle (section 1) are now shipped** for the login surface
(the only system surface that exists today): the login renders under an
owner-controlled theme via `data-theme` scoped to the `.login` subtree,
independent of `pigify.theme`, with a top-right light/dark toggle. The owner
default is the build-time constant `OWNER_THEME_DEFAULT` in
`frontend/src/lib/ownerTheme.ts` (provisioning resolved to **build-time now**;
see below). **Still open:** the brand-mark mode/layout config (section 3) and
its provisioning — to be decided when built. This note keeps the decisions so
they aren't re-litigated.

## Why this exists

A user-selectable theme (Settings › dark / light / system) should **not**
bleed onto the login or error screens. Those are seen before there's a user
whose preference could count (login), or while the app can't function
(connection error) — they're the **owner's** storefront, not a user surface.
Branding (the logo + the system-page look) is therefore the **deployer's** to
set, never a per-user runtime setting.

## Two theme surfaces

The boundary is the **working area** — *authenticated **and** on a
music/audio task page*.

| Surface | Who's there | Theme source | Brand mark |
|---------|-------------|--------------|------------|
| **Working area** — logged in, doing a music/audio task | a real user | the **user's** pick (`pigify.theme`) | header mark |
| **Owner surface** — anything an unauthorized user can see, or any non-task page (login, connection-error, not-authorized, 404, splash, maintenance) | maybe nobody yet | the **owner's** scheme, independent of the user's pick | front-door mark |

**Classification rule:** anything an unauthorized user can see, or any page
not about the music/audio task, is the owner surface. **Exception:** a
logged-in user who hits an error (e.g. a Spotify/data failure) *while in the
working area* keeps their own theme — the error doesn't kick them to the owner
surface.

## (1) Owner-surface theming

- The owner surface renders under an **owner-controlled** theme, never
  inheriting the working-area `pigify.theme`.
- Each system page carries a **small light/dark toggle in the top-right of the
  dialog card** (not the mostly-empty full page).
- It **defaults to `system`** (OS `prefers-color-scheme`); the **owner can set
  a different default**.
- The toggle is **ephemeral** — never remembered. Each time the page is seen
  it shows the owner default again; the toggle only exists so a visitor can
  flip light/dark to read the text better *right now*. It is not a preference
  and never touches the working-area theme.
- Implies a **separate, non-persistent theme state**, distinct from
  `pigify.theme`.

## (3) Brand mark

- **One structure**, shared across surfaces: the **same mode and the same
  order/arrangement** everywhere.
- Per surface, only the **overall size of the lockup** differs (the "size of
  the whole" — e.g. the header's `font-size` vs the login hero's). This is
  already the Increment-1 pattern (the header overrides `--brand-logo-scale`
  and its `font-size`).
- **Mode:** `lockup` (image + wordmark) · `wordmark` (text only) · `image`
  (a logotype whose artwork includes the name → its `alt`/`aria-label`).
- **Layout / arrangement** (a single shared choice): `image-left` ·
  `image-right` · `image-above` · `image-below`, mapping to the lockup's
  `flex-direction`. Caveat: the header bar is height-constrained, so a stacked
  (`above`/`below`) arrangement is impractical there — the arrangement choice
  must respect each surface's constraints.
- **Alignment knobs** (Increment 1, already built): `--brand-logo-scale`,
  `-shift-x`, `-shift-y`, `-gap`, `-trim`, `-tint` (see `THEMING.md`).

## What the owner configures

- **Brand mark:** mode, layout, wordmark text, image asset.
- **Per-surface size** (login hero vs header).
- **System-theme default:** `system | dark | light` (default `system`).
- The **logo alignment knobs** (already CSS custom properties).

## Provisioning model

**Resolved for the system-theme default (shipped):** build-time —
`OWNER_THEME_DEFAULT` is a typed constant in `lib/ownerTheme.ts` the deployer
edits + rebuilds. This is the "build-time now, runtime later" option below; a
runtime-injected value can replace the constant later without touching
callers. **Still open for the brand mark** (mode/layout/wordmark/image) —
decide when section 3 is built. The options below stand for that decision:

- **Build-time config module** — a typed `brand.ts` (mode/layout/wordmark +
  image `import`) the owner edits, then rebuilds the image. Simplest,
  type-safe, matches the build-time theme system (YAML→CSS). Cost: a
  white-label deployer must rebuild the frontend image, not just run the
  published one.
- **Runtime-mounted** — a `BRAND_*` env set + a logo file mounted into the
  published image; the SPA reads injected runtime config at startup. True
  white-label (no rebuild). Cost: runtime config injection into the static SPA
  + nginx serving the mounted asset.
- **Build-time now, runtime later** *(recommended)* — ship the build-time
  module + `<Brand>` component now (unblocks mode/layout/size immediately),
  with a clean seam to switch to runtime when the white-label TODO is actually
  built. The owner currently builds anyway, so build-time costs nothing today.

## Implementation seams (for when it's built)

- **Theme state (shipped):** working area uses `pigify.theme` on `<html>`; the
  owner surface uses a separate **ephemeral** React state seeded from the
  owner default and applied by scoping `data-theme` to the **`.login`
  subtree** (not `<html>`), so the two never interact and there's no flash.
  Future system pages reuse `lib/ownerTheme` + `OwnerThemeToggle` likewise.
- **`<Brand>` component:** replaces the duplicated lockup in `Login.tsx` /
  `App.tsx` (already copy #2 of the same markup), driven by the brand config;
  renders the chosen mode/layout and consumes the alignment knobs.
- **Page classification:** a single predicate for "working area"
  (authenticated **and** on a music/audio task route) decides theme source and
  which brand mark + size apply.
