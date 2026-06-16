// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const getTrackDetail = vi.fn();
vi.mock("../services/api", () => ({
  apiService: {
    getTrackDetail: (...a: unknown[]) => getTrackDetail(...a),
  },
}));

import TrackInfoPanel from "./TrackInfoPanel";

const detail = {
  spotify: {
    id: "t1",
    name: "Detail Track",
    artists: ["The Artist"],
    album: "The Album",
  },
  connections: {},
};

describe("TrackInfoPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    getTrackDetail.mockResolvedValue(detail);
  });

  it("fetches each section independently and shows the base header", async () => {
    render(<TrackInfoPanel trackId="t1" onClose={vi.fn()} />);

    expect(await screen.findByText("Detail Track")).toBeInTheDocument();
    expect(screen.getByText(/The Artist/)).toBeInTheDocument();
    // Base + the always-public providers each load as their own request, so a
    // slow one never blocks the rest.
    expect(getTrackDetail).toHaveBeenCalledWith("t1", {
      sections: "base",
      refresh: false,
    });
    expect(getTrackDetail).toHaveBeenCalledWith("t1", {
      sections: "musicbrainz",
      refresh: false,
    });
    expect(getTrackDetail).toHaveBeenCalledWith("t1", {
      sections: "wikipedia",
      refresh: false,
    });
  });

  it("shows the empty state when no track is selected", () => {
    render(<TrackInfoPanel trackId={null} onClose={vi.fn()} />);

    expect(screen.getByText("No track selected.")).toBeInTheDocument();
    expect(getTrackDetail).not.toHaveBeenCalled();
  });

  it("calls onClose when the close button is clicked", async () => {
    const onClose = vi.fn();
    render(<TrackInfoPanel trackId="t1" onClose={onClose} />);

    await userEvent.click(
      screen.getByRole("button", { name: "Close track info panel" }),
    );

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
