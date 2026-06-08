// @vitest-environment jsdom
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

// SettingsPanel and its sub-tabs talk to the backend through apiService.
// Each tab fires its own load on mount, so the mock has to provide every
// method the panel touches with a realistic resolved shape; individual
// tests override the relevant ones.
const getFavoritesStatus = vi.fn();
const syncFavorites = vi.fn();
const updateFavoritesSettings = vi.fn();
const resolveFavoriteConflict = vi.fn();
const getConnections = vi.fn();
const getProfile = vi.fn();
const updateProfile = vi.fn();
const getLastfmStatus = vi.fn();
const disconnectLastfm = vi.fn();
const getLastfmQueue = vi.fn();
const flushLastfmQueue = vi.fn();
const deleteLastfmQueueEntry = vi.fn();
const clearLastfmQueue = vi.fn();
const clearEnrichmentCache = vi.fn();
const getVersionInfo = vi.fn();

vi.mock("../services/api", () => ({
  apiService: {
    getFavoritesStatus: (...a: unknown[]) => getFavoritesStatus(...a),
    syncFavorites: (...a: unknown[]) => syncFavorites(...a),
    updateFavoritesSettings: (...a: unknown[]) => updateFavoritesSettings(...a),
    resolveFavoriteConflict: (...a: unknown[]) => resolveFavoriteConflict(...a),
    getConnections: (...a: unknown[]) => getConnections(...a),
    getProfile: (...a: unknown[]) => getProfile(...a),
    updateProfile: (...a: unknown[]) => updateProfile(...a),
    getLastfmStatus: (...a: unknown[]) => getLastfmStatus(...a),
    disconnectLastfm: (...a: unknown[]) => disconnectLastfm(...a),
    getLastfmQueue: (...a: unknown[]) => getLastfmQueue(...a),
    flushLastfmQueue: (...a: unknown[]) => flushLastfmQueue(...a),
    deleteLastfmQueueEntry: (...a: unknown[]) => deleteLastfmQueueEntry(...a),
    clearLastfmQueue: (...a: unknown[]) => clearLastfmQueue(...a),
    clearEnrichmentCache: (...a: unknown[]) => clearEnrichmentCache(...a),
    getVersionInfo: (...a: unknown[]) => getVersionInfo(...a),
  },
}));

// __APP_VERSION__ is a Vite build-time `define`; it is not injected into the
// Vitest config, so the AboutTab read of it would throw a ReferenceError
// without this stub.
(globalThis as { __APP_VERSION__?: string }).__APP_VERSION__ = "9.9.9-test";

import type { Profile } from "../services/api";
import SettingsPanel, { type SettingsTabId } from "./SettingsPanel";

const favoritesStatus = {
  connections: [
    { service: "spotify", connected: true, username: "alan", detail: null },
    { service: "lastfm", connected: false, username: null, detail: null },
  ],
  last_sync: null as null | {
    ran_at: string;
    services_checked: string[];
    spotify_count: number;
    lastfm_count: number;
    matched: number;
    conflicts: unknown[];
    error?: string | null;
  },
  background_interval_minutes: 0,
  pending_conflicts: [] as unknown[],
};

const syncSummary = {
  ran_at: "2026-06-01T12:00:00Z",
  services_checked: ["spotify", "lastfm"],
  spotify_count: 12,
  lastfm_count: 8,
  matched: 6,
  conflicts: [],
  error: null,
};

const profile = {
  spotify_id: "alan123",
  spotify_display_name: "Alan",
  custom_display_name: null,
  display_name: "Alan",
};

// A connections map where Last.fm is authenticated (connect/disconnect path).
const authedConnections = {
  spotify: {
    service: "spotify",
    tier: "authenticated" as const,
    display_name: "Spotify",
    connected_account: "alan",
  },
  lastfm: {
    service: "lastfm",
    tier: "authenticated" as const,
    display_name: "Last.fm",
    connected_account: "alan_lfm",
    needs_reconnect: false,
  },
};

function renderPanel(overrides?: {
  initialTab?: SettingsTabId;
  onClose?: () => void;
  onProfileChange?: (p: Profile) => void;
}) {
  return render(
    <SettingsPanel
      onClose={overrides?.onClose ?? vi.fn()}
      onProfileChange={overrides?.onProfileChange}
      initialTab={overrides?.initialTab}
    />,
  );
}

describe("SettingsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getFavoritesStatus.mockResolvedValue(favoritesStatus);
    syncFavorites.mockResolvedValue(syncSummary);
    updateFavoritesSettings.mockResolvedValue({
      ...favoritesStatus,
      background_interval_minutes: 30,
    });
    resolveFavoriteConflict.mockResolvedValue(undefined);
    getConnections.mockResolvedValue(authedConnections);
    getProfile.mockResolvedValue(profile);
    updateProfile.mockResolvedValue(profile);
    getLastfmStatus.mockResolvedValue({
      connection: authedConnections.lastfm,
      status: { queued: 0, last_scrobble_at: null },
    });
    disconnectLastfm.mockResolvedValue(undefined);
    getLastfmQueue.mockResolvedValue({ entries: [], count: 0 });
    flushLastfmQueue.mockResolvedValue({
      attempted: 0,
      succeeded: 0,
      remaining: 0,
    });
    deleteLastfmQueueEntry.mockResolvedValue(undefined);
    clearLastfmQueue.mockResolvedValue({ deleted: 0, remaining: 0 });
    clearEnrichmentCache.mockResolvedValue({ deleted: 0, scope: "user" });
    getVersionInfo.mockResolvedValue({
      backend_version: "1.2.3",
      python_version: "3.12.0",
      fastapi_version: "0.110.0",
      git_commit: "abc1234",
      schema_version: "5",
    });
  });

  describe("shell + tabs", () => {
    it("renders the header and the three tabs without throwing", async () => {
      renderPanel();

      expect(
        screen.getByRole("complementary", { name: "Settings" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("tab", { name: "Favorites" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("tab", { name: "Connections" }),
      ).toBeInTheDocument();
      expect(screen.getByRole("tab", { name: "About" })).toBeInTheDocument();

      // Favorites is the default tab and loads its status on mount.
      await waitFor(() => expect(getFavoritesStatus).toHaveBeenCalled());
    });

    it("defaults to the favorites tab as selected", async () => {
      renderPanel();

      expect(screen.getByRole("tab", { name: "Favorites" })).toHaveAttribute(
        "aria-selected",
        "true",
      );
      await waitFor(() => expect(getFavoritesStatus).toHaveBeenCalled());
    });

    it("honours the initialTab prop", async () => {
      renderPanel({ initialTab: "about" });

      expect(screen.getByRole("tab", { name: "About" })).toHaveAttribute(
        "aria-selected",
        "true",
      );
      await waitFor(() => expect(getVersionInfo).toHaveBeenCalled());
    });

    it("invokes onClose when the close button is clicked", async () => {
      const onClose = vi.fn();
      renderPanel({ onClose });

      await userEvent.click(
        screen.getByRole("button", { name: "Close settings" }),
      );

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it("switches to the Connections tab when its tab is clicked", async () => {
      renderPanel();

      await userEvent.click(screen.getByRole("tab", { name: "Connections" }));

      expect(screen.getByRole("tab", { name: "Connections" })).toHaveAttribute(
        "aria-selected",
        "true",
      );
      // The Connections tab loads connections + profile on mount.
      await waitFor(() => expect(getConnections).toHaveBeenCalled());
      expect(await screen.findByText("Profile")).toBeInTheDocument();
    });

    it("switches to the About tab and shows version info", async () => {
      renderPanel();

      await userEvent.click(screen.getByRole("tab", { name: "About" }));

      expect(await screen.findByText("Pigify")).toBeInTheDocument();
      expect(screen.getByText("9.9.9-test")).toBeInTheDocument();
      await waitFor(() => expect(getVersionInfo).toHaveBeenCalled());
    });
  });

  describe("favorites tab", () => {
    it("renders the loaded sync sources", async () => {
      renderPanel();

      expect(await screen.findByText("Sync sources")).toBeInTheDocument();
      expect(screen.getByText("spotify")).toBeInTheDocument();
      expect(screen.getByText(/Connected as alan/)).toBeInTheDocument();
    });

    it("shows an error message when the status fails to load", async () => {
      getFavoritesStatus.mockRejectedValue(new Error("boom"));
      renderPanel();

      expect(
        await screen.findByText("Failed to load settings"),
      ).toBeInTheDocument();
    });

    it("runs a manual sync and reflects the result", async () => {
      getFavoritesStatus.mockResolvedValue({
        ...favoritesStatus,
        background_interval_minutes: 0,
      });
      renderPanel();

      const syncBtn = await screen.findByRole("button", { name: "Sync now" });
      await userEvent.click(syncBtn);

      await waitFor(() => expect(syncFavorites).toHaveBeenCalledTimes(1));
      // The summary line is rendered from the returned SyncSummary.
      expect(await screen.findByText(/Last sync:/)).toBeInTheDocument();
      expect(screen.getByText(/Spotify 12/)).toBeInTheDocument();
    });

    it("shows a sync error when the sync call rejects", async () => {
      syncFavorites.mockRejectedValue(new Error("nope"));
      renderPanel();

      const syncBtn = await screen.findByRole("button", { name: "Sync now" });
      await userEvent.click(syncBtn);

      expect(await screen.findByText("Sync failed")).toBeInTheDocument();
    });

    it("saves the background sync interval", async () => {
      renderPanel();

      const input = await screen.findByRole("spinbutton");
      await userEvent.clear(input);
      await userEvent.type(input, "30");
      await userEvent.click(screen.getByRole("button", { name: "Save" }));

      await waitFor(() =>
        expect(updateFavoritesSettings).toHaveBeenCalledWith(30),
      );
    });

    it("reports no pending conflicts when the list is empty", async () => {
      renderPanel();

      expect(
        await screen.findByText("No pending conflicts."),
      ).toBeInTheDocument();
      expect(screen.getByText("Conflicts (0)")).toBeInTheDocument();
    });

    it("resolves a pending conflict via the api", async () => {
      getFavoritesStatus.mockResolvedValue({
        ...favoritesStatus,
        pending_conflicts: [
          {
            track: {
              name: "Song A",
              artist: "Artist A",
              spotify_id: "sp1",
            },
            loved_on: ["lastfm"],
            not_loved_on: ["spotify"],
          },
        ],
      });
      renderPanel();

      expect(await screen.findByText("Song A")).toBeInTheDocument();
      await userEvent.click(
        screen.getByRole("button", { name: "Unlove on both" }),
      );

      await waitFor(() =>
        expect(resolveFavoriteConflict).toHaveBeenCalledWith(0, "unlove_both"),
      );
    });
  });

  describe("connections tab — Last.fm authenticated", () => {
    it("shows the connected account and a Disconnect control", async () => {
      renderPanel({ initialTab: "connections" });

      expect(await screen.findByText("Last.fm")).toBeInTheDocument();
      expect(screen.getByText("alan_lfm")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Disconnect" }),
      ).toBeInTheDocument();
    });

    it("calls disconnectLastfm and refreshes when Disconnect is clicked", async () => {
      renderPanel({ initialTab: "connections" });

      const disconnectBtn = await screen.findByRole("button", {
        name: "Disconnect",
      });
      await userEvent.click(disconnectBtn);

      await waitFor(() => expect(disconnectLastfm).toHaveBeenCalledTimes(1));
      // refresh() re-fetches connections (initial load + post-disconnect).
      await waitFor(() =>
        expect(getConnections.mock.calls.length).toBeGreaterThanOrEqual(2),
      );
    });

    it("saves a custom display name through updateProfile", async () => {
      const onProfileChange = vi.fn();
      updateProfile.mockResolvedValue({
        ...profile,
        custom_display_name: "Piggy",
        display_name: "Piggy",
      });
      renderPanel({ initialTab: "connections", onProfileChange });

      const input = await screen.findByLabelText("Display name");
      await userEvent.type(input, "Piggy");
      await userEvent.click(screen.getByRole("button", { name: "Save" }));

      await waitFor(() => expect(updateProfile).toHaveBeenCalledWith("Piggy"));
      expect(await screen.findByText("Saved")).toBeInTheDocument();
      expect(onProfileChange).toHaveBeenCalledTimes(1);
    });

    it("renders the enrichment cache card with a clear control", async () => {
      renderPanel({ initialTab: "connections" });

      expect(
        await screen.findByText("Cached track trivia"),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Clear cached track trivia" }),
      ).toBeInTheDocument();
    });
  });

  describe("connections tab — Last.fm unconfigured", () => {
    beforeEach(() => {
      getConnections.mockResolvedValue({
        spotify: {
          service: "spotify",
          tier: "authenticated",
          display_name: "Spotify",
          connected_account: "alan",
        },
        lastfm: {
          service: "lastfm",
          tier: "none",
          display_name: "Last.fm",
        },
      });
    });

    it("hides the Last.fm card and skips the status fetch", async () => {
      renderPanel({ initialTab: "connections" });

      // Profile card still loads so we can assert the tab settled.
      expect(await screen.findByText("Profile")).toBeInTheDocument();
      // No Last.fm card heading, no connect/disconnect controls.
      expect(
        screen.queryByRole("button", { name: "Disconnect" }),
      ).not.toBeInTheDocument();
      // getLastfmStatus is only called when tier !== "none".
      expect(getLastfmStatus).not.toHaveBeenCalled();
    });
  });

  describe("connections tab — Last.fm public tier (connect path)", () => {
    beforeEach(() => {
      getConnections.mockResolvedValue({
        lastfm: {
          service: "lastfm",
          tier: "public",
          display_name: "Last.fm",
        },
      });
    });

    it("shows a Connect Last.fm link and no Disconnect button", async () => {
      renderPanel({ initialTab: "connections" });

      const connect = await screen.findByRole("link", {
        name: "Connect Last.fm",
      });
      expect(connect).toHaveAttribute("href", "/api/integrations/lastfm/login");
      expect(
        screen.queryByRole("button", { name: "Disconnect" }),
      ).not.toBeInTheDocument();
    });
  });

  describe("Last.fm queue panel", () => {
    it("shows the empty queue state when nothing is pending", async () => {
      renderPanel({ initialTab: "connections" });

      expect(await screen.findByText(/Nothing queued/)).toBeInTheDocument();
    });

    it("retries the queue and reports the flush result", async () => {
      getLastfmQueue.mockResolvedValue({
        entries: [
          {
            id: 1,
            artist: "Artist A",
            track: "Track A",
            timestamp: 1_700_000_000,
            attempts: 2,
            last_error: "rate limited",
            queued_at: "2026-06-01T11:00:00Z",
          },
        ],
        count: 1,
      });
      flushLastfmQueue.mockResolvedValue({
        attempted: 1,
        succeeded: 1,
        remaining: 0,
        error: null,
      });
      renderPanel({ initialTab: "connections" });

      expect(await screen.findByText("Track A")).toBeInTheDocument();
      await userEvent.click(screen.getByRole("button", { name: "Retry now" }));

      await waitFor(() => expect(flushLastfmQueue).toHaveBeenCalledTimes(1));
      expect(await screen.findByText(/Retried 1/)).toBeInTheDocument();
    });

    it("deletes a single queued scrobble", async () => {
      getLastfmQueue.mockResolvedValue({
        entries: [
          {
            id: 7,
            artist: "Artist B",
            track: "Track B",
            timestamp: 1_700_000_000,
            attempts: 1,
            queued_at: "2026-06-01T11:00:00Z",
          },
        ],
        count: 1,
      });
      renderPanel({ initialTab: "connections" });

      const delBtn = await screen.findByRole("button", {
        name: "Delete Track B",
      });
      await userEvent.click(delBtn);

      await waitFor(() =>
        expect(deleteLastfmQueueEntry).toHaveBeenCalledWith(7),
      );
    });
  });

  describe("about tab", () => {
    it("renders version rows and the GitHub source link", async () => {
      renderPanel({ initialTab: "about" });

      expect(await screen.findByText("Versions")).toBeInTheDocument();
      // Backend version comes from getVersionInfo.
      expect(await screen.findByText("1.2.3")).toBeInTheDocument();
      expect(screen.getByText("3.12.0")).toBeInTheDocument();

      const link = screen.getByRole("link", {
        name: "https://github.com/harleypig/pigify",
      });
      expect(link).toHaveAttribute(
        "href",
        "https://github.com/harleypig/pigify",
      );
    });

    it("shows an unavailable message when version info fails", async () => {
      getVersionInfo.mockRejectedValue(new Error("offline"));
      renderPanel({ initialTab: "about" });

      expect(
        await screen.findByText("Backend version info unavailable"),
      ).toBeInTheDocument();
    });

    it("renders the What's new changelog with the latest entry", async () => {
      renderPanel({ initialTab: "about" });

      expect(await screen.findByText("What's new")).toBeInTheDocument();
      // Toggling older releases reveals the rest of the changelog.
      const olderToggle = screen.getByRole("button", {
        name: /Show older releases/,
      });
      await userEvent.click(olderToggle);

      expect(screen.getByText("0.4.0")).toBeInTheDocument();
    });

    it("lists the public providers", async () => {
      renderPanel({ initialTab: "about" });

      const providers = await screen.findByText("Public providers");
      const card = providers.closest("section");
      expect(card).not.toBeNull();
      if (card) {
        expect(
          within(card).getByRole("link", { name: "MusicBrainz" }),
        ).toBeInTheDocument();
        expect(
          within(card).getByRole("link", { name: "Wikipedia" }),
        ).toBeInTheDocument();
      }
    });
  });
});
