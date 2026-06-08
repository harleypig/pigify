// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

// RecipesSidebar reads/plays/removes recipes via recipesApi. It also renders
// RecipeBuilder, which imports apiService from the same module — so the mock
// must expose apiService too (RecipeBuilder returns null while closed, but its
// module-level import is still resolved).
const list = vi.fn();
const remove = vi.fn();
const play = vi.fn();
const materialize = vi.fn();
vi.mock("../services/api", () => ({
  recipesApi: {
    list: (...a: unknown[]) => list(...a),
    remove: (...a: unknown[]) => remove(...a),
    play: (...a: unknown[]) => play(...a),
    materialize: (...a: unknown[]) => materialize(...a),
  },
  apiService: {
    getPlaylists: vi.fn().mockResolvedValue([]),
  },
}));

import RecipesSidebar from "./RecipesSidebar";

const recipe = {
  id: "r1",
  name: "Chill Mix",
  buckets: [{ name: "b", filters: [], sort: null, limit: null }],
  combine: "in_order" as const,
  created_at: "2024-01-01",
  updated_at: "2024-01-01",
};

describe("RecipesSidebar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    list.mockResolvedValue([recipe]);
    play.mockResolvedValue({ track_count: 10 });
    remove.mockResolvedValue([]);
  });

  it("renders the loaded recipes", async () => {
    render(<RecipesSidebar />);

    expect(await screen.findByText("Chill Mix")).toBeInTheDocument();
    expect(screen.getByText("Smart Filters")).toBeInTheDocument();
  });

  it("shows the empty state when there are no recipes", async () => {
    list.mockResolvedValue([]);

    render(<RecipesSidebar />);

    expect(await screen.findByText(/No saved filters yet/)).toBeInTheDocument();
  });

  it("plays a recipe and shows a status message when play is clicked", async () => {
    render(<RecipesSidebar />);

    await screen.findByText("Chill Mix");
    await userEvent.click(
      screen.getByRole("button", { name: "Play recipe Chill Mix" }),
    );

    expect(play).toHaveBeenCalledWith("r1");
    expect(await screen.findByText(/Playing 10 tracks/)).toBeInTheDocument();
  });

  it("deletes a recipe after the user confirms", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);

    render(<RecipesSidebar />);

    await screen.findByText("Chill Mix");
    await userEvent.click(
      screen.getByRole("button", { name: "Delete recipe Chill Mix" }),
    );

    await waitFor(() => expect(remove).toHaveBeenCalledWith("r1"));
    confirmSpy.mockRestore();
  });
});
