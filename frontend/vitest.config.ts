import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // Pure logic only so far (sortEngine, helpers) — the default node
    // environment is enough. Switch a suite to jsdom only if it touches
    // DOM/browser APIs.
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
