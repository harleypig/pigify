import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// A single mock axios instance shared by the module under test. api.ts
// calls `axios.create(...)` once at import time; we make that return this
// object so every apiService/recipesApi method exercises these spies.
// vi.hoisted lets the instance be defined before the hoisted vi.mock factory
// references it.
const instance = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}));

vi.mock("axios", () => ({
  default: {
    create: vi.fn(() => instance),
  },
}));

// Imported after the mock is registered so the module picks up the spy.
import { apiService, recipesApi } from "./api";

// Each verb resolves to `{ data }`; tests override per-case as needed.
function resolveAll(data: unknown): void {
  instance.get.mockResolvedValue({ data });
  instance.post.mockResolvedValue({ data });
  instance.put.mockResolvedValue({ data });
  instance.delete.mockResolvedValue({ data });
}

beforeEach(() => {
  resolveAll(undefined);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("apiService — auth", () => {
  it("getCurrentUser returns response.data from /api/auth/me", async () => {
    const user = { id: "u1", display_name: "Pig", images: [] };
    instance.get.mockResolvedValueOnce({ data: user });

    const out = await apiService.getCurrentUser();

    expect(instance.get).toHaveBeenCalledWith("/api/auth/me");
    expect(out).toBe(user);
  });

  it("getAccessToken unwraps the nested access_token field", async () => {
    instance.get.mockResolvedValueOnce({ data: { access_token: "tok-123" } });

    const token = await apiService.getAccessToken();

    expect(instance.get).toHaveBeenCalledWith("/api/auth/token");
    expect(token).toBe("tok-123");
  });

  it("logout posts to /api/auth/logout and resolves void", async () => {
    await expect(apiService.logout()).resolves.toBeUndefined();
    expect(instance.post).toHaveBeenCalledWith("/api/auth/logout");
  });
});

describe("apiService — profile", () => {
  it("updateProfile sends custom_display_name in the body", async () => {
    const profile = { spotify_id: "s1", display_name: "Name" };
    instance.put.mockResolvedValueOnce({ data: profile });

    const out = await apiService.updateProfile("Custom");

    expect(instance.put).toHaveBeenCalledWith("/api/me/profile", {
      custom_display_name: "Custom",
    });
    expect(out).toBe(profile);
  });

  it("updateProfile passes null through unchanged", async () => {
    await apiService.updateProfile(null);

    expect(instance.put).toHaveBeenCalledWith("/api/me/profile", {
      custom_display_name: null,
    });
  });
});

describe("apiService — playlists", () => {
  it("getPlaylists uses default limit/offset params", async () => {
    await apiService.getPlaylists();

    expect(instance.get).toHaveBeenCalledWith("/api/playlists", {
      params: { limit: 50, offset: 0 },
    });
  });

  it("getPlaylists forwards explicit limit/offset", async () => {
    await apiService.getPlaylists(10, 20);

    expect(instance.get).toHaveBeenCalledWith("/api/playlists", {
      params: { limit: 10, offset: 20 },
    });
  });

  it("getPlaylist interpolates the playlist id into the path", async () => {
    await apiService.getPlaylist("abc");

    expect(instance.get).toHaveBeenCalledWith("/api/playlists/abc");
  });

  it("getPlaylistTracks uses default limit/offset params", async () => {
    await apiService.getPlaylistTracks("pl");

    expect(instance.get).toHaveBeenCalledWith("/api/playlists/pl/tracks", {
      params: { limit: 100, offset: 0 },
    });
  });

  it("getAllPlaylistTracks requests the all=true param", async () => {
    await apiService.getAllPlaylistTracks("pl");

    expect(instance.get).toHaveBeenCalledWith("/api/playlists/pl/tracks", {
      params: { all: true },
    });
  });
});

describe("apiService — sort presets", () => {
  it("saveSortPreset posts the preset to the presets endpoint", async () => {
    const preset = { name: "p", keys: [] };

    await apiService.saveSortPreset(preset);

    expect(instance.post).toHaveBeenCalledWith(
      "/api/playlists/sort/presets",
      preset,
    );
  });

  it("deleteSortPreset URL-encodes the preset name", async () => {
    await apiService.deleteSortPreset("a b/c");

    expect(instance.delete).toHaveBeenCalledWith(
      "/api/playlists/sort/presets/a%20b%2Fc",
    );
  });
});

describe("apiService — hydrate", () => {
  it("posts track_ids, sources and track_meta in the body", async () => {
    const meta = [{ id: "t1", name: "n", artist: "a" }];

    await apiService.hydrateTracks("pl", ["t1"], ["lastfm"], meta);

    expect(instance.post).toHaveBeenCalledWith("/api/playlists/pl/hydrate", {
      track_ids: ["t1"],
      sources: ["lastfm"],
      track_meta: meta,
    });
  });

  it("sends track_meta as undefined when omitted", async () => {
    await apiService.hydrateTracks("pl", ["t1"], ["audio_features"]);

    expect(instance.post).toHaveBeenCalledWith("/api/playlists/pl/hydrate", {
      track_ids: ["t1"],
      sources: ["audio_features"],
      track_meta: undefined,
    });
  });
});

describe("apiService — reorder/undo", () => {
  it("reorderPlaylist posts target_uris", async () => {
    await apiService.reorderPlaylist("pl", ["spotify:track:1"]);

    expect(instance.post).toHaveBeenCalledWith("/api/playlists/pl/reorder", {
      target_uris: ["spotify:track:1"],
    });
  });

  it("undoReorder posts to the undo endpoint", async () => {
    await apiService.undoReorder("pl");

    expect(instance.post).toHaveBeenCalledWith("/api/playlists/pl/undo");
  });

  it("getUndoStatus reads the undo-status endpoint", async () => {
    await apiService.getUndoStatus("pl");

    expect(instance.get).toHaveBeenCalledWith("/api/playlists/pl/undo-status");
  });
});

describe("apiService — player", () => {
  it("playTrack defaults missing args to null", async () => {
    await apiService.playTrack();

    expect(instance.put).toHaveBeenCalledWith("/api/player/play", {
      track_uri: null,
      device_id: null,
    });
  });

  it("playTrack forwards uri and device id", async () => {
    await apiService.playTrack("spotify:track:1", "dev");

    expect(instance.put).toHaveBeenCalledWith("/api/player/play", {
      track_uri: "spotify:track:1",
      device_id: "dev",
    });
  });

  it("seekTo rounds the position into the query string", async () => {
    await apiService.seekTo(1234.7);

    expect(instance.put).toHaveBeenCalledWith(
      "/api/player/seek?position_ms=1235",
    );
  });

  it("getAudioAnalysis defaults bars to 80", async () => {
    await apiService.getAudioAnalysis("t1");

    expect(instance.get).toHaveBeenCalledWith("/api/player/analysis/t1", {
      params: { bars: 80 },
    });
  });
});

describe("apiService — favorites", () => {
  it("checkFavorites short-circuits to [] without any request", async () => {
    const out = await apiService.checkFavorites([]);

    expect(out).toEqual([]);
    expect(instance.get).not.toHaveBeenCalled();
  });

  it("checkFavorites builds repeated query params per item", async () => {
    instance.get.mockResolvedValueOnce({ data: [] });

    await apiService.checkFavorites([
      { track_id: "t1", name: "N1", artist: "A1" },
      { name: "N2", artist: "A2" },
    ]);

    const url = instance.get.mock.calls[0][0] as string;
    expect(url.startsWith("/api/favorites/check?")).toBe(true);

    const query = url.split("?")[1];
    const params = new URLSearchParams(query);
    // Missing track_id is sent as an empty string for that slot.
    expect(params.getAll("track_id")).toEqual(["t1", ""]);
    expect(params.getAll("name")).toEqual(["N1", "N2"]);
    expect(params.getAll("artist")).toEqual(["A1", "A2"]);
  });

  it("syncFavorites defaults max_tracks to 500", async () => {
    await apiService.syncFavorites();

    expect(instance.post).toHaveBeenCalledWith("/api/favorites/sync", {
      max_tracks: 500,
    });
  });

  it("resolveFavoriteConflict posts index and choice", async () => {
    await apiService.resolveFavoriteConflict(2, "keep");

    expect(instance.post).toHaveBeenCalledWith(
      "/api/favorites/resolve-conflict",
      { index: 2, choice: "keep" },
    );
  });

  it("clearLastfmQueue sends the ids in the request body data", async () => {
    await apiService.clearLastfmQueue([1, 2]);

    expect(instance.delete).toHaveBeenCalledWith(
      "/api/integrations/lastfm/queue",
      { data: { ids: [1, 2] } },
    );
  });

  it("clearLastfmQueue sends an empty body when no ids given", async () => {
    await apiService.clearLastfmQueue();

    expect(instance.delete).toHaveBeenCalledWith(
      "/api/integrations/lastfm/queue",
      { data: {} },
    );
  });
});

describe("apiService — track detail", () => {
  it("getTrackDetail omits params when refresh is not requested", async () => {
    await apiService.getTrackDetail("t1");

    expect(instance.get).toHaveBeenCalledWith(
      "/api/integrations/track-detail/t1",
      { params: undefined },
    );
  });

  it("getTrackDetail passes refresh=true when requested", async () => {
    await apiService.getTrackDetail("t1", { refresh: true });

    expect(instance.get).toHaveBeenCalledWith(
      "/api/integrations/track-detail/t1",
      { params: { refresh: true } },
    );
  });
});

describe("apiService — error propagation", () => {
  it("rejects when the underlying request rejects", async () => {
    const err = new Error("network down");
    instance.get.mockRejectedValueOnce(err);

    await expect(apiService.getCurrentUser()).rejects.toBe(err);
  });
});

describe("recipesApi", () => {
  it("list reads /api/recipes", async () => {
    await recipesApi.list();

    expect(instance.get).toHaveBeenCalledWith("/api/recipes");
  });

  it("create posts the recipe body", async () => {
    const recipe = { name: "r", buckets: [], combine: "in_order" as const };

    await recipesApi.create(recipe);

    expect(instance.post).toHaveBeenCalledWith("/api/recipes", recipe);
  });

  it("update interpolates the id and sends the recipe", async () => {
    const recipe = { name: "r", buckets: [], combine: "shuffled" as const };

    await recipesApi.update("rid", recipe);

    expect(instance.put).toHaveBeenCalledWith("/api/recipes/rid", recipe);
  });

  it("remove deletes by id", async () => {
    await recipesApi.remove("rid");

    expect(instance.delete).toHaveBeenCalledWith("/api/recipes/rid");
  });

  it("play defaults uris to null", async () => {
    await recipesApi.play("rid");

    expect(instance.post).toHaveBeenCalledWith("/api/recipes/rid/play", {
      uris: null,
    });
  });

  it("play forwards the provided uris", async () => {
    await recipesApi.play("rid", ["spotify:track:1"]);

    expect(instance.post).toHaveBeenCalledWith("/api/recipes/rid/play", {
      uris: ["spotify:track:1"],
    });
  });

  it("materialize defaults options to an empty object", async () => {
    await recipesApi.materialize("rid");

    expect(instance.post).toHaveBeenCalledWith(
      "/api/recipes/rid/materialize",
      {},
    );
  });
});
