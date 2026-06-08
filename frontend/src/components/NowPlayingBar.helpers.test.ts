import { describe, expect, it } from "vitest";
import { formatMs } from "./NowPlayingBar.helpers";

describe("formatMs", () => {
  it("formats zero as 0:00", () => {
    expect(formatMs(0)).toBe("0:00");
  });

  it("zero-pads the seconds", () => {
    expect(formatMs(5_000)).toBe("0:05");
    expect(formatMs(65_000)).toBe("1:05");
  });

  it("floors fractional seconds", () => {
    expect(formatMs(1_999)).toBe("0:01");
  });

  it("clamps negatives to 0:00", () => {
    expect(formatMs(-5_000)).toBe("0:00");
  });

  it("formats multi-minute positions", () => {
    expect(formatMs(125_000)).toBe("2:05");
  });
});
