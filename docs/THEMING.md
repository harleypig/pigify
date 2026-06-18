# Theming

pigify's look is driven entirely by a set of CSS custom properties — the
**token contract**. Components never hard-code colours, fonts, or radii; they
reference `--brand-*` tokens, and a *theme* is just a set of values for those
tokens. Switching themes swaps the values; the components don't change.

There are **three levels** of theming, from "pick one" to "write raw CSS".

## The token contract

The canonical list of tokens lives in [`frontend/src/theme.css`](../frontend/src/theme.css)
— surfaces, text, accents, shadow, code-syntax, type, and shape. Every theme
**must** define a value for each token (a test enforces parity between the
built-in themes). `theme.css` also `@import`s the built-in theme files and is
the single stylesheet `main.tsx` loads.

`:root` defaults to the **dark** theme; setting `data-theme="<name>"` on
`<html>` activates another theme's token block.

## Level 1 — pick a built-in theme (Settings › Theme)

Users choose **System / Dark / Light** in Settings › Theme. The choice is
persisted to `localStorage` (`pigify.theme`) and applied by setting
`data-theme` on `<html>`; **System** follows the OS `prefers-color-scheme`
and stays in sync if the OS setting changes. The logic is in
[`frontend/src/lib/theme.ts`](../frontend/src/lib/theme.ts).

To add a built-in theme to the picker, register it in
`THEME_CHOICES` / `themeChoiceLabel` in that file (after creating the theme
at level 2 or 3 below).

## Level 2 — author a theme as YAML

A theme is most easily authored as a flat YAML map of token → value:

```yaml
# frontend/src/themes/<name>.theme.yaml
_label: Sepia        # display name (Settings picker)
_default: false      # true for the :root default (dark is the default)
bg: "#f4ecd8"
surface: "#fffaf0"
ink: "#3a2f1c"
accent: "#a6671f"
# … one line per token in the contract …
```

A build step compiles each `*.theme.yaml` to a CSS file:

```bash
cd frontend
npm run generate:themes      # writes src/themes/<name>.css
```

This runs automatically on `npm run dev` / `npm run build` (the
`predev` / `prebuild` hooks), the same pattern as the generated changelog.
No YAML parser ships to the client — compilation is build-time only. The dark
and light themes are authored this way; their `.theme.yaml` files are the
source of truth and the `.css` files are generated (do not hand-edit the
generated CSS).

## Level 3 — a theme is a CSS file

The compiled artifact is plain CSS that sets the tokens under a selector:

```css
/* frontend/src/themes/<name>.css */
[data-theme="sepia"] {
  --brand-bg: #f4ecd8;
  --brand-surface: #fffaf0;
  /* … every token … */
}
```

For a **white-label deploy** with full control, skip the YAML and hand-write
this CSS file (or override individual tokens), then `@import` it from
`theme.css` and register the name in `theme.ts`. Anything CSS can express is
available at this level.

## Branding the logo (owner-only)

The brand **logo** is a deployer concern, not a user setting — there is no
Settings control for it. Like the colour tokens, the logo is fitted with CSS
custom properties so a white-label deploy can drop in its own artwork and
align it **without code edits**. These `--brand-logo-*` knobs live in
[`frontend/src/theme.css`](../frontend/src/theme.css) (not in the per-theme
files — logo *geometry* is the same whatever the colour theme):

| Knob | Default | What it does |
|------|---------|--------------|
| `--brand-logo-scale` | `1.25` | logo height as a multiple of the wordmark |
| `--brand-logo-shift-y` | `0.1em` | vertical nudge so the artwork's visual anchor (the medallion circle), not its bounding box, centres on the wordmark |
| `--brand-logo-shift-x` | `-0.28em` | horizontal optical-balance nudge for the lockup |
| `--brand-logo-gap` | `0.2em` | space between the logo and the wordmark |
| `--brand-logo-trim` | `0em` | inset that crops a transparent/empty margin around a logo so it sits flush (0 for the edge-to-edge pigify medallion) |
| `--brand-logo-tint` | `opacity(1)` | optional `filter` to recolour the logo toward the active theme; `opacity(1)` is the identity (off) |

The defaults are the hero (login) values. The compact app-header lockup
overrides `--brand-logo-scale` / `--brand-logo-shift-y` in
[`frontend/src/App.css`](../frontend/src/App.css); both lockups consume the
rest. To rebrand: replace `frontend/src/assets/pigify-logo.png`, then tune the
knobs above (override them in a hand-written theme CSS or directly in
`theme.css`) until the new logo sits right against the wordmark.

## The brand mark (owner-only)

*What* the brand mark is — image, text, or both, and how they're arranged —
is owner config in [`frontend/src/lib/brand.ts`](../frontend/src/lib/brand.ts)
(build-time; edit + rebuild). A shared
[`<Brand>`](../frontend/src/components/Brand.tsx) component renders it on
every surface (login hero, app header) from one structure, so there's no
duplicated markup; each surface keeps only its own *size*.

```ts
// frontend/src/lib/brand.ts
export const BRAND: BrandConfig = {
  mode: "lockup", // "lockup" (image + text) | "wordmark" (text) | "image" (logotype)
  layout: "image-left", // image-left | image-right | image-above | image-below
  wordmark: "pigify",
  image: logoUrl, // unused in "wordmark" mode
};
```

- **`mode`** picks what shows: both, text only, or the logo alone (in `image`
  mode the image's `alt` carries the name).
- **`layout`** flows the lockup via `data-brand-layout` (`Brand.css` maps it
  to `flex-direction`). The app header is height-constrained, so the stacked
  arrangements (`image-above` / `image-below`) suit the login hero more than
  the bar.
- Fit/alignment is still the `--brand-logo-*` knobs above. Note `-shift-x`
  nudges the side-by-side layouts and `-shift-y` the stacked ones — they
  aren't auto-swapped, so a non-default `layout` may want them re-tuned.

## Adding a theme — checklist

1. Create `frontend/src/themes/<name>.theme.yaml` (copy `dark.theme.yaml`) —
   or hand-write `<name>.css` for level 3.
2. `npm run generate:themes` (skip if hand-writing the CSS).
3. `@import "./themes/<name>.css";` in `frontend/src/theme.css`.
4. Add the name to `THEME_CHOICES` + `themeChoiceLabel` in
   `frontend/src/lib/theme.ts` so it appears in Settings › Theme.
5. Run the tests — the parity test will flag any token the new theme misses.

## Bring your own brand (white-label)

A deployer (the "owner") can re-skin pigify end to end — colours, fonts,
logo, wordmark, and the pre-login look — by changing config and **rebuilding
the frontend image**. Everything below is **build-time**: the brand is
compiled into the bundle, so a rebrand is "edit the source, rebuild", not a
runtime setting. (A no-rebuild *runtime* path is a planned future enhancement
— see *Runtime branding* in [`branding-design.md`](branding-design.md).)

The four levers, each documented in its own section above:

1. **Colours & fonts** → a **custom theme**. Author it as YAML (level 2) or
   hand-write the CSS (level 3), then make it the default. This is the most
   involved step — see *Compiling a theme* below.
2. **Logo & wordmark** → the **`BRAND` config** (`frontend/src/lib/brand.ts`):
   `mode` (lockup / wordmark / image), `layout`, the `wordmark` text, and the
   `image` asset. Replace `frontend/src/assets/pigify-logo.png` (or point
   `image` at your own file). See *The brand mark*.
3. **Logo fit** → the **`--brand-logo-*` knobs** (`theme.css`) — scale, gap,
   nudge, trim, tint — so a new logo sits right against the wordmark. See
   *Branding the logo*.
4. **Pre-login look** → **`OWNER_THEME_DEFAULT`**
   (`frontend/src/lib/ownerTheme.ts`) — the theme the login / system pages
   default to (`system` / `dark` / `light`), independent of any user's pick.

Then rebuild: `docker compose up -d --build frontend` (or your deploy's image
build). No code edits beyond these config files and the asset are needed.

### Compiling a theme

Colours and fonts live in a **compiled CSS** theme, so changing them is the
one step that needs the build toolchain — the biggest hurdle to a
minimal-effort rebrand. The flow (also in *Adding a theme — checklist*):

```bash
cd frontend
# 1. Author the palette as a friendly YAML map (copy an existing one):
cp src/themes/dark.theme.yaml src/themes/mybrand.theme.yaml
#    …edit the token values (bg / surface / ink / accent / fonts / …)…

# 2. Compile YAML → CSS (writes src/themes/mybrand.css):
npm run generate:themes

# 3. Make it the default: set `_default: true` in mybrand.theme.yaml (and
#    false on the old default), recompile, then @import it in src/theme.css
#    and register it in src/lib/theme.ts (see the checklist above).

# 4. npm run build   # or rebuild the image
```

Hand-writing `src/themes/mybrand.css` directly (level 3) skips the YAML +
`generate:themes` step — anything CSS can express is available, at the cost
of writing raw token declarations.

## Files

| Path | Role |
|------|------|
| `frontend/src/theme.css` | token contract + `@import` of the built-ins |
| `frontend/src/themes/*.theme.yaml` | level-2 theme sources |
| `frontend/src/themes/*.css` | level-3 artifacts (generated from YAML) |
| `frontend/scripts/generate-themes.mjs` | YAML → CSS compiler |
| `frontend/src/lib/theme.ts` | level-1 selection + persistence + apply |
| `frontend/src/lib/brand.ts` | the `BRAND` mark config (mode/layout/wordmark/image) |
| `frontend/src/lib/ownerTheme.ts` | `OWNER_THEME_DEFAULT` (pre-login theme) |
| `frontend/src/assets/pigify-logo.png` | the default logo asset |
