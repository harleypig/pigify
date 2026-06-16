import { execFileSync } from "node:child_process";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import pkg from "./package.json";

// Short commit hash for the build. CI injects GIT_HASH (the Docker build
// context has no .git); otherwise fall back to the last commit that touched
// the frontend tree — the component hash, so a backend-only commit does not
// advance it. Wrapped in try/catch so a non-git build (e.g. a tarball) works.
let gitHash = process.env.GIT_HASH?.trim() ?? "";
if (!gitHash) {
  try {
    gitHash = execFileSync("git", ["log", "-1", "--format=%h", "--", "."])
      .toString()
      .trim();
  } catch {
    gitHash = "";
  }
}
// Match the conventional --short width whatever the source.
gitHash = gitHash.slice(0, 7);

// The frontend version comes from the latest `frontend/v*` git tag, so the
// tag is the single source of truth (no version-file edits per release).
// Prefer the build-time APP_VERSION (injected by CI; the Docker context has
// no .git), then `git describe`, then package.json as a last-ditch fallback.
let appVersion = process.env.APP_VERSION?.trim() ?? "";
if (!appVersion) {
  try {
    appVersion = execFileSync("git", [
      "describe",
      "--tags",
      "--match",
      "frontend/v*",
      "--abbrev=0",
    ])
      .toString()
      .trim()
      .replace(/^frontend\/v?/, "");
  } catch {
    // No matching tag (or git unavailable) — fall back to package.json.
  }
}
if (!appVersion) appVersion = pkg.version;

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
    __GIT_HASH__: JSON.stringify(gitHash),
  },
  server: {
    host: "0.0.0.0",
    port: 5000,
    allowedHosts: true,
    proxy: {
      // Backend routes live under /api/*, so no path rewrite. Target is
      // overridable for non-default local backends.
      "/api": {
        target: process.env.VITE_API_PROXY ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
