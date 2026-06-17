// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Login from "./Login";

describe("Login", () => {
  it("renders the wordmark and call-to-action", () => {
    render(<Login onLogin={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "pigify" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Connect Spotify" }),
    ).toBeInTheDocument();
  });

  it("calls onLogin when the button is clicked", async () => {
    const onLogin = vi.fn();
    render(<Login onLogin={onLogin} />);

    await userEvent.click(
      screen.getByRole("button", { name: "Connect Spotify" }),
    );
    expect(onLogin).toHaveBeenCalledTimes(1);
  });

  it("stays on the page and shows an error when sign-in fails", async () => {
    const onLogin = vi.fn().mockRejectedValue(new Error("backend down"));
    render(<Login onLogin={onLogin} />);

    await userEvent.click(
      screen.getByRole("button", { name: "Connect Spotify" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("backend down");
    // Still the login screen, ready to retry.
    expect(screen.getByRole("heading", { name: "pigify" })).toBeInTheDocument();
  });

  it("renders the owner-surface theme on the login subtree", () => {
    const { container } = render(<Login onLogin={vi.fn()} />);
    // jsdom has no matchMedia, so the "system" owner default resolves to light.
    expect(container.querySelector(".login")).toHaveAttribute(
      "data-theme",
      "light",
    );
  });

  it("flips the owner-surface theme via the ephemeral toggle", async () => {
    const { container } = render(<Login onLogin={vi.fn()} />);
    const login = container.querySelector(".login");

    // Default light → the toggle offers a switch to dark.
    const toggle = screen.getByRole("button", { name: "Switch to dark mode" });
    expect(login).toHaveAttribute("data-theme", "light");

    await userEvent.click(toggle);
    expect(login).toHaveAttribute("data-theme", "dark");
    expect(
      screen.getByRole("button", { name: "Switch to light mode" }),
    ).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "Switch to light mode" }),
    );
    expect(login).toHaveAttribute("data-theme", "light");
  });
});
