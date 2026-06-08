// Registers @testing-library/jest-dom matchers (toBeInTheDocument, etc.)
// with Vitest's expect. Safe to load under the node environment too — it
// only extends expect; the matchers are used by the jsdom component tests.
import "@testing-library/jest-dom/vitest";
