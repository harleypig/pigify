import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // globals: true so React Testing Library's automatic per-test cleanup
    // registers via the global afterEach (otherwise rendered trees leak
    // across tests). Test files still import { describe, it, expect } etc.
    globals: true,
    // Default environment is node (fast) for pure-logic `*.test.ts`.
    // Component tests are `*.test.tsx` and opt into jsdom with a
    // `// @vitest-environment jsdom` docblock at the top of the file.
    environment: "node",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["./src/test-setup.ts"],
  },
});
