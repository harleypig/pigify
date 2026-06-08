// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SortField, SortPreset } from "../services/api";
import SortMenu, { type SortSpec } from "./SortMenu";

const fields: SortField[] = [
  {
    key: "added_at",
    label: "Date added",
    type: "date",
    source: "spotify_track",
    requires_hydration: false,
    group: "Playlist",
    default: true,
  },
  {
    key: "name",
    label: "Title",
    type: "string",
    source: "spotify_track",
    requires_hydration: false,
    group: "Track",
    default: true,
  },
];

const current: SortSpec = {
  keys: [{ field: "added_at", direction: "desc" }],
};

function renderMenu(
  overrides: Partial<React.ComponentProps<typeof SortMenu>> = {},
) {
  const props = {
    fields,
    presets: [] as SortPreset[],
    current,
    onChange: vi.fn(),
    onSavePreset: vi.fn(),
    onDeletePreset: vi.fn(),
    onApplyView: vi.fn(),
    onApplyToPlaylist: vi.fn(),
    onUndo: vi.fn(),
    applying: false,
    undoAvailable: false,
    ...overrides,
  };
  render(<SortMenu {...props} />);
  return props;
}

describe("SortMenu", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the trigger summarizing the current primary key", () => {
    renderMenu();

    expect(
      screen.getByRole("button", { name: /Sort by:/ }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Date added/)).toBeInTheDocument();
  });

  it("opens the popover and lists the default quick fields", async () => {
    renderMenu();

    await userEvent.click(screen.getByRole("button", { name: /Sort by:/ }));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Defaults")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Title" })).toBeInTheDocument();
  });

  it("calls onChange with a single key when a quick default is picked", async () => {
    const props = renderMenu();

    await userEvent.click(screen.getByRole("button", { name: /Sort by:/ }));
    await userEvent.click(screen.getByRole("button", { name: "Title" }));

    expect(props.onChange).toHaveBeenCalledWith({
      keys: [{ field: "name", direction: "asc" }],
    });
  });

  it("calls onApplyToPlaylist when the apply-to-playlist button is clicked", async () => {
    const props = renderMenu();

    await userEvent.click(screen.getByRole("button", { name: /Sort by:/ }));
    await userEvent.click(
      screen.getByRole("button", { name: "Apply to playlist" }),
    );

    expect(props.onApplyToPlaylist).toHaveBeenCalledTimes(1);
  });

  it("shows the undo button and calls onUndo when undo is available", async () => {
    const props = renderMenu({ undoAvailable: true });

    await userEvent.click(screen.getByRole("button", { name: "Undo" }));

    expect(props.onUndo).toHaveBeenCalledTimes(1);
  });

  it("reports an empty saved-sorts state", async () => {
    renderMenu({ presets: [] });

    await userEvent.click(screen.getByRole("button", { name: /Sort by:/ }));

    expect(screen.getByText("No saved sorts yet.")).toBeInTheDocument();
  });
});
