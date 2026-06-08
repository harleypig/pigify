// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Login from "./Login";

describe("Login", () => {
  it("renders the title and call-to-action", () => {
    render(<Login onLogin={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Pigify" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Login with Spotify" }),
    ).toBeInTheDocument();
  });

  it("calls onLogin when the button is clicked", async () => {
    const onLogin = vi.fn();
    render(<Login onLogin={onLogin} />);

    await userEvent.click(
      screen.getByRole("button", { name: "Login with Spotify" }),
    );
    expect(onLogin).toHaveBeenCalledTimes(1);
  });
});
