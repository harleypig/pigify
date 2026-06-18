// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BRAND } from "../lib/brand";
import { Brand } from "./Brand";

describe("Brand", () => {
  it("renders the wordmark as a heading in the default lockup mode", () => {
    // The shipped config is the lockup; this also documents the default so a
    // future owner change is a deliberate edit.
    expect(BRAND.mode).toBe("lockup");

    const { container } = render(<Brand surface="login" wordmarkId="wm" />);
    const heading = screen.getByRole("heading", { name: BRAND.wordmark });
    expect(heading).toHaveAttribute("id", "wm");
    // The logo is decorative in lockup mode (the wordmark names the lockup).
    expect(container.querySelector("img")).toHaveAttribute("alt", "");
  });

  it("applies the owner layout via data-brand-layout", () => {
    const { container } = render(<Brand surface="header" />);
    expect(container.firstChild).toHaveAttribute(
      "data-brand-layout",
      BRAND.layout,
    );
  });

  it("uses the surface's class set", () => {
    const { container: login } = render(<Brand surface="login" />);
    expect(login.querySelector(".console__lockup")).toBeInTheDocument();

    const { container: header } = render(<Brand surface="header" />);
    expect(header.querySelector(".app-brand")).toBeInTheDocument();
  });

  it("tints the logo on error (login auth failure)", () => {
    const { container } = render(<Brand surface="login" error />);
    expect(container.querySelector("img")).toHaveClass("is-error");
  });
});
