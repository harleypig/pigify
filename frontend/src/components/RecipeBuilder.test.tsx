// @vitest-environment jsdom
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  Playlist,
  RecipeResolveResponse,
  SortField,
  StoredRecipe,
  Track,
} from "../services/api";

// RecipeBuilder talks to the backend exclusively through `apiService`
// (sort-fields / current-user / playlists, loaded on open) and `recipesApi`
// (resolve / create / update / playAdhoc, driven by the action buttons). The
// mock exposes exactly those, plus the real `apiErrorMessage` helper so the
// error paths produce sensible text.
const getSortFields = vi.fn();
const getCurrentUser = vi.fn();
const getPlaylists = vi.fn();
const resolve = vi.fn();
const create = vi.fn();
const update = vi.fn();
const playAdhoc = vi.fn();

vi.mock("../services/api", () => ({
  apiErrorMessage: (_error: unknown, fallback: string) => fallback,
  apiService: {
    getSortFields: (...a: unknown[]) => getSortFields(...a),
    getCurrentUser: (...a: unknown[]) => getCurrentUser(...a),
    getPlaylists: (...a: unknown[]) => getPlaylists(...a),
  },
  recipesApi: {
    resolve: (...a: unknown[]) => resolve(...a),
    create: (...a: unknown[]) => create(...a),
    update: (...a: unknown[]) => update(...a),
    playAdhoc: (...a: unknown[]) => playAdhoc(...a),
  },
}));

import RecipeBuilder from "./RecipeBuilder";

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
  {
    key: "popularity",
    label: "Popularity",
    type: "number",
    source: "spotify_track",
    requires_hydration: false,
    group: "Track",
    default: false,
  },
];

const playlists: Playlist[] = [
  {
    id: "p1",
    name: "Morning Coffee",
    description: "",
    images: [],
    owner: "me",
    track_count: 12,
    public: false,
  },
  {
    id: "p2",
    name: "Workout",
    description: "",
    images: [],
    owner: "friend",
    track_count: 30,
    public: true,
  },
];

function track(id: string, name: string): Track {
  return {
    id,
    name,
    artists: ["Some Artist"],
    album: "Some Album",
    duration_ms: 180000,
    uri: `spotify:track:${id}`,
    image_url: "",
    explicit: false,
  };
}

const resolveResponse: RecipeResolveResponse = {
  tracks: [track("t1", "First Song"), track("t2", "Second Song")],
  warnings: [],
  bucket_counts: [2],
  track_sources: {},
  resolved_at: "2024-01-01T00:00:00Z",
};

const storedRecipe: StoredRecipe = {
  id: "rec-1",
  name: "Saved Recipe",
  combine: "interleave",
  buckets: [
    {
      name: "Bucket one",
      source: "liked",
      filters: [],
      sort: { field: "added_at", direction: "desc" },
      count: 5,
    },
  ],
  created_at: "2024-01-01",
  updated_at: "2024-01-01",
};

function renderBuilder(
  overrides: Partial<React.ComponentProps<typeof RecipeBuilder>> = {},
) {
  const props = {
    open: true,
    initial: null,
    onClose: vi.fn(),
    onSaved: vi.fn(),
    ...overrides,
  };
  render(<RecipeBuilder {...props} />);
  return props;
}

describe("RecipeBuilder", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    getSortFields.mockResolvedValue({ fields });
    getCurrentUser.mockResolvedValue({
      id: "me",
      display_name: "Me",
      images: [],
    });
    // getPlaylists is paged: return the playlists once, then an empty page so
    // the loader's while-loop terminates.
    getPlaylists.mockImplementation((_limit: number, offset: number) =>
      Promise.resolve(offset === 0 ? playlists : []),
    );
    resolve.mockResolvedValue(resolveResponse);
    create.mockResolvedValue(storedRecipe);
    update.mockResolvedValue(storedRecipe);
    playAdhoc.mockResolvedValue({
      started: true,
      track_count: 2,
      queued: 0,
      warnings: [],
    });
  });

  it("renders nothing when closed", () => {
    renderBuilder({ open: false });

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders the dialog and primary controls when open", async () => {
    renderBuilder();

    const dialog = await screen.findByRole("dialog", { name: "Edit recipe" });
    expect(dialog).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Preview" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Play now" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Save recipe" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "+ Add bucket" }),
    ).toBeInTheDocument();
  });

  it("loads sort fields, current user, and playlists on open", async () => {
    renderBuilder();

    await waitFor(() => expect(getSortFields).toHaveBeenCalled());
    expect(getCurrentUser).toHaveBeenCalled();
    await waitFor(() => expect(getPlaylists).toHaveBeenCalled());
  });

  it("seeds the name field from an initial recipe", async () => {
    renderBuilder({ initial: storedRecipe });

    await screen.findByRole("dialog");
    expect(screen.getByDisplayValue("Saved Recipe")).toBeInTheDocument();
    // An existing recipe gets a "Save changes" button rather than "Save recipe".
    expect(
      screen.getByRole("button", { name: "Save changes" }),
    ).toBeInTheDocument();
  });

  it("closes via the × button", async () => {
    const props = renderBuilder();

    await screen.findByRole("dialog");
    await userEvent.click(
      screen.getByRole("button", { name: "Close recipe editor" }),
    );

    expect(props.onClose).toHaveBeenCalledTimes(1);
  });

  it("adds and removes a bucket", async () => {
    renderBuilder();

    await screen.findByRole("dialog");
    // A fresh recipe starts with a single bucket; its remove button is hidden
    // until a second bucket exists.
    expect(
      screen.queryByRole("button", { name: "Remove bucket" }),
    ).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "+ Add bucket" }));

    const removeButtons = screen.getAllByRole("button", {
      name: "Remove bucket",
    });
    expect(removeButtons).toHaveLength(2);

    await userEvent.click(removeButtons[0]);

    expect(
      screen.queryByRole("button", { name: "Remove bucket" }),
    ).not.toBeInTheDocument();
  });

  it("adds a filter clause, then changes its field and operator", async () => {
    renderBuilder();

    await screen.findByRole("dialog");
    // Wait for the sort fields to load — addFilter is a no-op until they do.
    await waitFor(() => expect(getSortFields).toHaveBeenCalled());

    await userEvent.click(screen.getByRole("button", { name: "+ Add filter" }));

    const removeFilter = await screen.findByRole("button", {
      name: "Remove filter",
    });
    const filterRow = removeFilter.closest(".filter-row") as HTMLElement;
    expect(filterRow).toBeTruthy();

    const selects = within(filterRow).getAllByRole("combobox");
    const fieldSelect = selects[0];
    const opSelect = selects[1];

    // The first field is a date, so the op list is the date operators.
    expect(
      within(opSelect).getByRole("option", { name: "on/after" }),
    ).toBeTruthy();

    // Switch the field to a numeric one; the operator list should swap to the
    // numeric operators.
    await userEvent.selectOptions(fieldSelect, "popularity");
    expect(within(opSelect).getByRole("option", { name: "≥" })).toBeTruthy();

    await userEvent.selectOptions(opSelect, "between");
    expect((opSelect as HTMLSelectElement).value).toBe("between");

    // Removing the clause drops the row.
    await userEvent.click(
      screen.getByRole("button", { name: "Remove filter" }),
    );
    expect(
      screen.queryByRole("button", { name: "Remove filter" }),
    ).not.toBeInTheDocument();
  });

  it("previews the recipe and shows the resolved tracks", async () => {
    renderBuilder();

    await screen.findByRole("dialog");
    await userEvent.click(screen.getByRole("button", { name: "Preview" }));

    expect(resolve).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("2 tracks")).toBeInTheDocument();
    expect(screen.getByText("First Song")).toBeInTheDocument();
    expect(screen.getByText("Second Song")).toBeInTheDocument();
  });

  it("surfaces an error when preview fails", async () => {
    resolve.mockRejectedValue(new Error("boom"));

    renderBuilder();

    await screen.findByRole("dialog");
    await userEvent.click(screen.getByRole("button", { name: "Preview" }));

    expect(await screen.findByText("Preview failed")).toBeInTheDocument();
  });

  it("renders resolver warnings in the preview", async () => {
    resolve.mockResolvedValue({
      ...resolveResponse,
      warnings: ["A heads-up warning"],
    });

    renderBuilder();

    await screen.findByRole("dialog");
    await userEvent.click(screen.getByRole("button", { name: "Preview" }));

    expect(await screen.findByText("A heads-up warning")).toBeInTheDocument();
  });

  it("creates a new recipe on save and reports back", async () => {
    const props = renderBuilder();

    await screen.findByRole("dialog");
    await userEvent.click(screen.getByRole("button", { name: "Save recipe" }));

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
    expect(update).not.toHaveBeenCalled();
    expect(props.onSaved).toHaveBeenCalledWith(storedRecipe);
    expect(props.onClose).toHaveBeenCalledTimes(1);
  });

  it("updates an existing recipe on save", async () => {
    const props = renderBuilder({ initial: storedRecipe });

    await screen.findByRole("dialog");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(update).toHaveBeenCalledTimes(1));
    expect(update).toHaveBeenCalledWith("rec-1", expect.any(Object));
    expect(create).not.toHaveBeenCalled();
    expect(props.onSaved).toHaveBeenCalledWith(storedRecipe);
  });

  it("surfaces an error when save fails and keeps the dialog open", async () => {
    create.mockRejectedValue(new Error("nope"));

    const props = renderBuilder();

    await screen.findByRole("dialog");
    await userEvent.click(screen.getByRole("button", { name: "Save recipe" }));

    expect(await screen.findByText("Save failed")).toBeInTheDocument();
    expect(props.onClose).not.toHaveBeenCalled();
  });

  it("plays the recipe ad-hoc via the Play now button", async () => {
    renderBuilder();

    await screen.findByRole("dialog");
    await userEvent.click(screen.getByRole("button", { name: "Play now" }));

    await waitFor(() => expect(playAdhoc).toHaveBeenCalledTimes(1));
  });

  it("switches the source to specific playlists and lists them", async () => {
    renderBuilder();

    await screen.findByRole("dialog");
    await waitFor(() => expect(getPlaylists).toHaveBeenCalled());

    // The bucket's Source select is the first labelled "Source" combobox.
    const sourceSelect = screen.getByRole("combobox", { name: "Source" });
    await userEvent.selectOptions(sourceSelect, "playlists");

    expect(await screen.findByText("Morning Coffee")).toBeInTheDocument();
    expect(screen.getByText("Workout")).toBeInTheDocument();
    // With nothing picked yet, the prompt hint is shown.
    expect(screen.getByText(/Pick at least one playlist/)).toBeInTheDocument();
  });
});
