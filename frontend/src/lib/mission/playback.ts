/**
 * Playback helpers. These only LOOK UP and interpolate saved simulation frames
 * for display; every mission calculation happens on the server.
 */
import type { Frame, MissionEvent, Phase, XY } from "./types";

/** Index of the last frame with frame.t <= t (binary search). */
export function frameIndexAt(frames: Frame[], t: number): number {
  if (frames.length === 0) return -1;
  if (t <= frames[0].t) return 0;
  let lo = 0;
  let hi = frames.length - 1;
  if (t >= frames[hi].t) return hi;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (frames[mid].t <= t) lo = mid;
    else hi = mid - 1;
  }
  return lo;
}

/** Display position between two saved frames (linear). Discrete fields come from the earlier frame. */
export function interpolatedPose(frames: Frame[], t: number): { x: number; y: number; ex: number; ey: number; hdg: number } | null {
  const i = frameIndexAt(frames, t);
  if (i < 0) return null;
  const a = frames[i];
  const b = frames[Math.min(i + 1, frames.length - 1)];
  const span = b.t - a.t;
  const f = span > 0 ? Math.min(1, Math.max(0, (t - a.t) / span)) : 0;
  const lerp = (p: number, q: number) => p + (q - p) * f;
  return { x: lerp(a.x, b.x), y: lerp(a.y, b.y), ex: lerp(a.ex, b.ex), ey: lerp(a.ey, b.ey), hdg: a.hdg };
}

export function eventsUpTo(events: MissionEvent[], t: number): MissionEvent[] {
  return events.filter((e) => e.t <= t);
}

export type PhaseState = "done" | "current" | "next" | "pending" | "halted" | "not_reached";

/** Phase states at simulated time t, given the saved phase log. */
export function phaseStates(phases: Phase[], t: number): PhaseState[] {
  let current = -1;
  phases.forEach((p, i) => {
    if (p.start_s !== undefined && p.start_s <= t) current = i;
  });
  return phases.map((p, i) => {
    if (i < current) return "done";
    if (i === current) {
      if (p.end_s !== undefined && t >= p.end_s) return p.status === "halted" ? "halted" : "done";
      return "current";
    }
    if (p.status === "not_reached") return "not_reached";
    return i === current + 1 ? "next" : "pending";
  });
}

export function formatSimTime(s: number): string {
  const v = Math.max(0, Math.round(s));
  const h = Math.floor(v / 3600);
  const m = Math.floor((v % 3600) / 60);
  const sec = v % 60;
  return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

/** Local metres (x east, y north) -> map pixel (north up). */
export function toMapPx(p: XY, extentM: number, sizePx: number): XY {
  return [(p[0] / extentM) * sizePx, ((extentM - p[1]) / extentM) * sizePx];
}

/** Map pixel -> local metres, rounded to 1 m and clamped to the terrain. */
export function fromMapPx(px: XY, extentM: number, sizePx: number): XY {
  const clamp = (v: number) => Math.min(extentM, Math.max(0, v));
  return [Math.round(clamp((px[0] / sizePx) * extentM)), Math.round(clamp(extentM - (px[1] / sizePx) * extentM))];
}

/** Bilinear elevation lookup on the downsampled display grid (for draping graphics only). */
export function sampleElevation(grid: number[][], spacing: number, origin: XY, x: number, y: number): number {
  const rows = grid.length;
  const cols = grid[0]?.length ?? 0;
  if (!rows || !cols) return 0;
  const fx = Math.min(cols - 1.000001, Math.max(0, (x - origin[0]) / spacing));
  const fy = Math.min(rows - 1.000001, Math.max(0, (y - origin[1]) / spacing));
  const c0 = Math.floor(fx);
  const r0 = Math.floor(fy);
  const tx = fx - c0;
  const ty = fy - r0;
  const z = (r: number, c: number) => grid[r][c];
  return (
    z(r0, c0) * (1 - tx) * (1 - ty) + z(r0, c0 + 1) * tx * (1 - ty) + z(r0 + 1, c0) * (1 - tx) * ty + z(r0 + 1, c0 + 1) * tx * ty
  );
}
