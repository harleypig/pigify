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

## Adding a theme — checklist

1. Create `frontend/src/themes/<name>.theme.yaml` (copy `dark.theme.yaml`) —
   or hand-write `<name>.css` for level 3.
2. `npm run generate:themes` (skip if hand-writing the CSS).
3. `@import "./themes/<name>.css";` in `frontend/src/theme.css`.
4. Add the name to `THEME_CHOICES` + `themeChoiceLabel` in
   `frontend/src/lib/theme.ts` so it appears in Settings › Theme.
5. Run the tests — the parity test will flag any token the new theme misses.

## Files

| Path | Role |
|------|------|
| `frontend/src/theme.css` | token contract + `@import` of the built-ins |
| `frontend/src/themes/*.theme.yaml` | level-2 theme sources |
| `frontend/src/themes/*.css` | level-3 artifacts (generated from YAML) |
| `frontend/scripts/generate-themes.mjs` | YAML → CSS compiler |
| `frontend/src/lib/theme.ts` | level-1 selection + persistence + apply |
