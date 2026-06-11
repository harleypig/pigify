import { describe, expect, it } from "vitest";
import { authMessageFromSearch } from "./Login.helpers";

describe("authMessageFromSearch", () => {
  it("returns a message when the access gate rejected the login", () => {
    const msg = authMessageFromSearch("?error=not_authorized");
    expect(msg).toContain("not authorized");
    expect(msg).toContain("Pigify");
  });

  it("returns null with no error param", () => {
    expect(authMessageFromSearch("")).toBeNull();
    expect(authMessageFromSearch("?foo=bar")).toBeNull();
  });

  it("returns null for an unrecognized error", () => {
    expect(authMessageFromSearch("?error=whatever")).toBeNull();
  });

  it("explains a failed demo invite", () => {
    expect(authMessageFromSearch("?error=demo_invalid")).toContain("demo");
    expect(authMessageFromSearch("?error=demo_failed")).toContain("demo");
  });
});
