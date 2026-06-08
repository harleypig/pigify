// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import UserMenu from "./UserMenu";

describe("UserMenu", () => {
  const baseProps = {
    label: "Alan Young",
    onOpenSettings: vi.fn(),
    onLogout: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the label and stays closed initially", () => {
    render(<UserMenu {...baseProps} />);

    expect(screen.getByText("Alan Young")).toBeInTheDocument();
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("shows initials when no image is provided", () => {
    render(<UserMenu {...baseProps} />);

    expect(screen.getByText("AY")).toBeInTheDocument();
  });

  it("opens the dropdown when the trigger is clicked", async () => {
    render(<UserMenu {...baseProps} />);

    await userEvent.click(screen.getByRole("button", { name: /Alan Young/ }));

    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(
      screen.getByRole("menuitem", { name: /Settings/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("menuitem", { name: "Logout" }),
    ).toBeInTheDocument();
  });

  it("invokes onOpenSettings and closes when Settings is clicked", async () => {
    const onOpenSettings = vi.fn();
    render(<UserMenu {...baseProps} onOpenSettings={onOpenSettings} />);

    await userEvent.click(screen.getByRole("button", { name: /Alan Young/ }));
    await userEvent.click(screen.getByRole("menuitem", { name: /Settings/ }));

    expect(onOpenSettings).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("invokes onLogout when Logout is clicked", async () => {
    const onLogout = vi.fn();
    render(<UserMenu {...baseProps} onLogout={onLogout} />);

    await userEvent.click(screen.getByRole("button", { name: /Alan Young/ }));
    await userEvent.click(screen.getByRole("menuitem", { name: "Logout" }));

    expect(onLogout).toHaveBeenCalledTimes(1);
  });

  it("renders a badge when badgeCount is positive", () => {
    render(<UserMenu {...baseProps} badgeCount={5} />);

    expect(screen.getByText("5")).toBeInTheDocument();
  });
});
