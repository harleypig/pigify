// Compile each theme's YAML (the friendly "level 2" authoring format) into a
// CSS file (the "level 3" artifact). Run on predev / prebuild, like
// generate-changelog. Dependency-free: theme YAML is a flat `key: value` map
// (plus `_`-prefixed meta), so a tiny parser suffices — no js-yaml, nothing
// shipped to the client.
//
// Source:  src/themes/<name>.theme.yaml
// Output:  src/themes/<name>.css   (committed; regenerated here)
//
// Each non-meta `key: value` becomes `--brand-<key>: <value>;`. The default
// theme (`_default: true`) is emitted under `:root, [data-theme="<name>"]`;
// others under `[data-theme="<name>"]`. The token CONTRACT (the canonical
// list every theme must define) lives in src/theme.css.

import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const themesDir = join(
  dirname(fileURLToPath(import.meta.url)),
  "../src/themes",
);

/** Parse a flat `key: value` YAML subset. Returns {meta, tokens}. */
function parseThemeYaml(text) {
  const meta = {};
  const tokens = [];
  for (const raw of text.split("\n")) {
    const line = raw.replace(/\s+#.*$/, "").trimEnd();
    if (!line.trim() || line.trimStart().startsWith("#")) continue;
    const m = line.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
    if (!m) continue;
    const [, key, valueRaw] = m;
    // Strip matching surrounding quotes, if any.
    const value = valueRaw.replace(/^(['"])(.*)\1$/, "$2");
    if (key.startsWith("_")) meta[key.slice(1)] = value;
    else tokens.push([key, value]);
  }
  return { meta, tokens };
}

function toCss(name, { meta, tokens }) {
  const isDefault = String(meta.default).toLowerCase() === "true";
  const selector = isDefault
    ? `:root,\n[data-theme="${name}"]`
    : `[data-theme="${name}"]`;
  const label = meta.label || name;
  const body = tokens.map(([k, v]) => `  --brand-${k}: ${v};`).join("\n");
  return (
    `/* GENERATED from ${name}.theme.yaml by scripts/generate-themes.mjs — do not edit by hand. */\n` +
    `/* Theme: ${label}${isDefault ? " (default)" : ""} */\n` +
    `${selector} {\n${body}\n}\n`
  );
}

let count = 0;
for (const file of readdirSync(themesDir)) {
  if (!file.endsWith(".theme.yaml")) continue;
  const name = file.replace(/\.theme\.yaml$/, "");
  const parsed = parseThemeYaml(readFileSync(join(themesDir, file), "utf-8"));
  writeFileSync(join(themesDir, `${name}.css`), toCss(name, parsed));
  count += 1;
}

console.log(`generate-themes: wrote ${count} theme CSS file(s)`);
