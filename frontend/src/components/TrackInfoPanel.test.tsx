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
    getTrackDetail.mockResolvedValue(detail);
  });

  it("renders the collapsed view with an expand control", () => {
    render(
      <TrackInfoPanel
        trackId="t1"
        collapsed={true}
        onToggleCollapsed={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("button", { name: "Expand track info panel" }),
    ).toBeInTheDocument();
  });

  it("calls onToggleCollapsed when the expand button is clicked", async () => {
    const onToggle = vi.fn();
    render(
      <TrackInfoPanel
        trackId="t1"
        collapsed={true}
        onToggleCollapsed={onToggle}
      />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Expand track info panel" }),
    );

    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("fetches and shows track detail when expanded", async () => {
    render(
      <TrackInfoPanel
        trackId="t1"
        collapsed={false}
        onToggleCollapsed={vi.fn()}
      />,
    );

    expect(await screen.findByText("Detail Track")).toBeInTheDocument();
    expect(screen.getByText(/The Artist/)).toBeInTheDocument();
    expect(getTrackDetail).toHaveBeenCalledWith("t1", { refresh: false });
  });

  it("shows the empty state when no track is selected", () => {
    render(
      <TrackInfoPanel
        trackId={null}
        collapsed={false}
        onToggleCollapsed={vi.fn()}
      />,
    );

    expect(screen.getByText("No track selected.")).toBeInTheDocument();
    expect(getTrackDetail).not.toHaveBeenCalled();
  });
});
