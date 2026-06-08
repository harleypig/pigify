import { execFileSync } from "node:child_process";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import pkg from "./package.json";

// Short commit hash for the build. CI injects GIT_HASH; otherwise read it
// from git. Wrapped in try/catch so a non-git build (e.g. a tarball) still
// works.
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

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
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
        target: process.env.VITE_API_PROXY ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
