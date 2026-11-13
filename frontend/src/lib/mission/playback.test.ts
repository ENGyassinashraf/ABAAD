import { describe, expect, it } from "vitest";
import { eventsUpTo, formatSimTime, frameIndexAt, fromMapPx, interpolatedPose, phaseStates, sampleElevation, toMapPx } from "./playback";
import type { Frame, MissionEvent, Phase } from "./types";

const f = (t: number, x: number): Frame => ({
  t, x, y: 0, hdg: 90, ex: x + 1, ey: 0, sigma: 1, nav: "NOMINAL", phase: 3, wp: "W1", los: "LINE_OF_SIGHT",
  local: true, earth: true, path: "direct", relay_ok: null, queue: 0, safety: "NOMINAL", dist: x, obs: null, since_contact: 0,
});
const frames = [f(0, 0), f(10, 1), f(20, 2), f(30, 3)];

describe("frame lookup", () => {
  it("finds the last frame at or before t", () => {
    expect(frameIndexAt(frames, -5)).toBe(0);
    expect(frameIndexAt(frames, 0)).toBe(0);
    expect(frameIndexAt(frames, 19.9)).toBe(1);
    expect(frameIndexAt(frames, 20)).toBe(2);
    expect(frameIndexAt(frames, 99)).toBe(3);
    expect(frameIndexAt([], 5)).toBe(-1);
  });
  it("interpolates position between saved frames only", () => {
    expect(interpolatedPose(frames, 15)?.x).toBeCloseTo(1.5);
    expect(interpolatedPose(frames, 15)?.ex).toBeCloseTo(2.5);
    expect(interpolatedPose(frames, 1000)?.x).toBe(3);
  });
});

describe("events and phases", () => {
  const ev = [{ t: 0 }, { t: 50 }, { t: 100 }] as MissionEvent[];
  it("returns events up to the playback time", () => {
    expect(eventsUpTo(ev, 50)).toHaveLength(2);
  });
  it("marks done/current/next phases and unreached phases", () => {
    const phases: Phase[] = [
      { phase: 1, name: "a", start_s: 0, end_s: 100, status: "completed" },
      { phase: 2, name: "b", start_s: 100, end_s: 200, status: "halted" },
      { phase: 3, name: "c", status: "not_reached" },
    ];
    expect(phaseStates(phases, 50)).toEqual(["current", "next", "not_reached"]);
    expect(phaseStates(phases, 150)).toEqual(["done", "current", "not_reached"]);
    expect(phaseStates(phases, 250)).toEqual(["done", "halted", "not_reached"]);
  });
  it("formats simulated time", () => {
    expect(formatSimTime(3725)).toBe("1:02:05");
  });
});

describe("map and elevation helpers", () => {
  it("round-trips metres and map pixels with north up", () => {
    expect(toMapPx([0, 1280], 1280, 640)).toEqual([0, 0]);
    expect(fromMapPx([320, 320], 1280, 640)).toEqual([640, 640]);
    expect(fromMapPx([-10, 700], 1280, 640)).toEqual([0, 0]);
  });
  it("samples the display grid bilinearly", () => {
    const g = [[0, 10], [20, 30]];
    expect(sampleElevation(g, 10, [0, 0], 5, 5)).toBeCloseTo(15);
    expect(sampleElevation(g, 10, [0, 0], 0, 0)).toBe(0);
  });
});
