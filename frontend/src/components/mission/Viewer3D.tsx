"use client";

/**
 * Interactive 3D mission viewer (three.js). It draws the saved terrain, routes
 * and markers and places the rover from the CURRENT SIMULATION FRAME passed in
 * by the playback loop — it never animates on its own.
 */
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { sampleElevation } from "@/lib/mission/playback";
import type { Frame, Run, TerrainData, XY } from "@/lib/mission/types";

export type Layers = { routes: boolean; hazards: boolean; comm: boolean; uncertainty: boolean; markers: boolean };
export type Viewer3DHandle = { snapshot: () => string | null };

type Props = {
  terrain: TerrainData;
  textureUrl: string;
  run: Run;
  pose: { x: number; y: number; ex: number; ey: number; hdg: number } | null;
  frame: Frame | null;
  layers: Layers;
  follow: boolean;
};

const EXAG = 2.0; // vertical exaggeration (display only)

export const Viewer3D = forwardRef<Viewer3DHandle, Props>(function Viewer3D(
  { terrain, textureUrl, run, pose, frame, layers, follow }, ref) {
  const host = useRef<HTMLDivElement>(null);
  const s = useRef<{
    renderer?: THREE.WebGLRenderer; scene?: THREE.Scene; camera?: THREE.PerspectiveCamera; controls?: OrbitControls;
    groups?: Record<string, THREE.Group>; rover?: THREE.Group; estimate?: THREE.Mesh; commLine?: THREE.Line;
    obstruction?: THREE.Mesh; terrainMat?: THREE.MeshLambertMaterial; raf?: number;
  }>({});
  const [state, setState] = useState<"loading" | "ready" | "unavailable">("loading");

  const ext = terrain.extent_m;
  const elev = (x: number, y: number) => sampleElevation(terrain.elevation_m, terrain.spacing_m, terrain.origin_m, x, y);
  const P = (x: number, y: number, lift = 0) => new THREE.Vector3(x - ext / 2, (elev(x, y) + lift) * EXAG, -(y - ext / 2));

  useImperativeHandle(ref, () => ({
    snapshot: () => {
      const r = s.current.renderer;
      if (!r || !s.current.scene || !s.current.camera) return null;
      r.render(s.current.scene, s.current.camera);
      return r.domElement.toDataURL("image/png");
    },
  }));

  // Build scene once per terrain + run
  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    } catch {
      setState("unavailable");
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(el.clientWidth, el.clientHeight);
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#141210");
    const camera = new THREE.PerspectiveCamera(45, el.clientWidth / el.clientHeight, 1, 20000);
    camera.position.set(-ext * 0.45, ext * 0.42, ext * 0.6);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.maxPolarAngle = Math.PI * 0.49;
    scene.add(new THREE.HemisphereLight(0xfff4e0, 0x202020, 0.9));
    const sun = new THREE.DirectionalLight(0xffffff, 1.1);
    sun.position.set(-1, 0.6, 0.4).multiplyScalar(ext);
    scene.add(sun);

    // terrain mesh
    const { rows, cols, spacing_m: sp, origin_m: o, elevation_m: z } = terrain;
    const geo = new THREE.PlaneGeometry((cols - 1) * sp, (rows - 1) * sp, cols - 1, rows - 1);
    geo.rotateX(-Math.PI / 2);
    const pos = geo.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < pos.count; i++) {
      const c = i % cols;
      const r = rows - 1 - Math.floor(i / cols); // plane rows run north->south after rotation
      pos.setY(i, z[r][c] * EXAG);
    }
    geo.translate(o[0] + ((cols - 1) * sp) / 2 - ext / 2, 0, -(o[1] + ((rows - 1) * sp) / 2 - ext / 2));
    geo.computeVertexNormals();
    const mat = new THREE.MeshLambertMaterial({ color: 0xffffff });
    scene.add(new THREE.Mesh(geo, mat));

    const groups: Record<string, THREE.Group> = {};
    for (const k of ["routes", "hazards", "markers", "comm", "uncertainty"]) {
      groups[k] = new THREE.Group();
      scene.add(groups[k]);
    }
    const line = (pts: XY[], color: number, lift: number, dashed = false) => {
      const g = new THREE.BufferGeometry().setFromPoints(pts.map(([x, y]) => P(x, y, lift)));
      const m = dashed ? new THREE.LineDashedMaterial({ color, dashSize: 14, gapSize: 9 }) : new THREE.LineBasicMaterial({ color });
      const l = new THREE.Line(g, m);
      if (dashed) l.computeLineDistances();
      return l;
    };
    const rec = run.routes.recommended;
    const alt = run.routes.alternate;
    if (alt) groups.routes.add(line(alt.path, 0xc9e0a8, 1.2, true));
    if (rec) {
      groups.routes.add(line(rec.path, 0xff7a3d, 1.5));
      for (const w of rec.waypoints) {
        const m = new THREE.Mesh(new THREE.SphereGeometry(5, 12, 8),
          new THREE.MeshBasicMaterial({ color: w.comm_visible ? 0xffffff : 0x777777 }));
        m.position.copy(P(w.x, w.y, 3));
        groups.routes.add(m);
      }
    }
    for (const h of terrain.hazards) {
      const disc = new THREE.Mesh(new THREE.CircleGeometry(h.radius_m, 32),
        new THREE.MeshBasicMaterial({ color: 0xb02a2a, transparent: true, opacity: 0.55, side: THREE.DoubleSide }));
      disc.rotation.x = -Math.PI / 2;
      disc.position.copy(P(h.x, h.y, 1.5));
      groups.hazards.add(disc);
    }
    const mast = (xy: XY, color: number, h: number, shape: "cone" | "cyl") => {
      const g = shape === "cone" ? new THREE.ConeGeometry(9, h * 6, 4) : new THREE.CylinderGeometry(4, 4, h * 6, 10);
      const m = new THREE.Mesh(g, new THREE.MeshLambertMaterial({ color }));
      m.position.copy(P(xy[0], xy[1], h * 3 / EXAG));
      groups.markers.add(m);
    };
    const cfg = run.config;
    mast(terrain.base_xy, 0x5e6c4b, 3, "cone");
    mast(cfg.start_xy, 0xffffff, 1.5, "cyl");
    mast(cfg.target_xy, 0xe0703f, 2, "cyl");
    if (cfg.comm_mode === "relay" && cfg.relay_xy) mast(cfg.relay_xy, 0x3b78b5, 2.5, "cone");
    for (const b of cfg.beacons ?? []) mast(b, 0x8e5ab5, 1.2, "cyl");

    // rover
    const rover = new THREE.Group();
    const body = new THREE.Mesh(new THREE.BoxGeometry(14, 6, 20), new THREE.MeshLambertMaterial({ color: 0xf3ebdd }));
    body.position.y = 5;
    const roverMast = new THREE.Mesh(new THREE.CylinderGeometry(0.8, 0.8, 12, 6), new THREE.MeshLambertMaterial({ color: 0xa95e40 }));
    roverMast.position.set(0, 13, -6);
    // tall locator pole so the rover can be found from far away (display aid, not to scale)
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(1.2, 1.2, 60, 6), new THREE.MeshBasicMaterial({ color: 0xffd34d }));
    pole.position.y = 36;
    const cap = new THREE.Mesh(new THREE.SphereGeometry(5, 12, 8), new THREE.MeshBasicMaterial({ color: 0xffd34d }));
    cap.position.y = 68;
    rover.add(body, roverMast, pole, cap);
    rover.scale.setScalar(1.6);
    scene.add(rover);
    const estimate = new THREE.Mesh(new THREE.RingGeometry(0.92, 1, 48),
      new THREE.MeshBasicMaterial({ color: 0xd6a93c, side: THREE.DoubleSide, transparent: true, opacity: 0.9 }));
    estimate.rotation.x = -Math.PI / 2;
    groups.uncertainty.add(estimate);
    const commLine = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
      new THREE.LineBasicMaterial({ color: 0x5e9a66 }));
    groups.comm.add(commLine);
    const obstruction = new THREE.Mesh(new THREE.SphereGeometry(7, 12, 8), new THREE.MeshBasicMaterial({ color: 0xff3b2f }));
    groups.comm.add(obstruction);

    s.current = { renderer, scene, camera, controls, groups, rover, estimate, commLine, obstruction, terrainMat: mat };
    const loop = () => {
      controls.update();
      renderer.render(scene, camera);
      s.current.raf = requestAnimationFrame(loop);
    };
    loop();
    setState("ready");
    const onResize = () => {
      camera.aspect = el.clientWidth / el.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(el.clientWidth, el.clientHeight);
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      if (s.current.raf) cancelAnimationFrame(s.current.raf);
      controls.dispose();
      renderer.dispose();
      scene.traverse((o) => {
        const m = o as THREE.Mesh;
        m.geometry?.dispose?.();
      });
      el.removeChild(renderer.domElement);
      s.current = {};
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [terrain, run]);

  // texture (map layer)
  useEffect(() => {
    const mat = s.current.terrainMat;
    if (!mat || state !== "ready") return;
    new THREE.TextureLoader().load(textureUrl, (tex) => {
      tex.colorSpace = THREE.SRGBColorSpace;
      mat.map?.dispose();
      mat.map = tex;
      mat.needsUpdate = true;
    });
  }, [textureUrl, state]);

  // layers
  useEffect(() => {
    const g = s.current.groups;
    if (!g) return;
    for (const k of Object.keys(layers) as (keyof Layers)[]) if (g[k]) g[k].visible = layers[k];
  }, [layers, state]);

  // per-frame state from the simulation
  useEffect(() => {
    const { rover, estimate, commLine, obstruction, camera, controls } = s.current;
    if (!rover || !pose || !frame || !estimate || !commLine || !obstruction || !camera || !controls) return;
    rover.position.copy(P(pose.x, pose.y));
    rover.rotation.y = -THREE.MathUtils.degToRad(pose.hdg) + Math.PI;
    const r = Math.max(frame.sigma, 1) ;
    estimate.position.copy(P(pose.ex, pose.ey, 2));
    estimate.scale.set(r, r, r);
    const cfg = run.config;
    const end: XY = frame.path === "relay" && cfg.relay_xy ? cfg.relay_xy : terrain.base_xy;
    const pts = [P(pose.x, pose.y, cfg.advanced.rover_antenna_m), P(end[0], end[1], frame.path === "relay" ? cfg.advanced.relay_antenna_m : cfg.advanced.base_antenna_m)];
    (commLine.geometry as THREE.BufferGeometry).setFromPoints(pts);
    (commLine.material as THREE.LineBasicMaterial).color.set(frame.local ? (frame.earth ? 0x5e9a66 : 0xd6a93c) : 0xd0402f);
    obstruction.visible = !!frame.obs && frame.path !== "relay";
    if (frame.obs) obstruction.position.copy(P(frame.obs[0], frame.obs[1], 2));
    if (follow) {
      const target = P(pose.x, pose.y);
      const delta = target.clone().sub(controls.target);
      controls.target.add(delta);
      camera.position.add(delta);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pose, frame, follow]);

  return (
    <div className="relative h-full w-full">
      <div ref={host} className="h-full w-full" data-testid="viewer3d" data-state={state} />
      {state === "unavailable" && (
        <p className="absolute inset-0 grid place-items-center p-6 text-center text-sm text-ivory">
          WebGL is not available in this browser, so the 3D view cannot be shown. The 2D map, telemetry and timeline still
          show the same simulation.
        </p>
      )}
      <p className="pointer-events-none absolute bottom-2 left-2 rounded bg-black/60 px-2 py-1 text-[11px] text-ivory">
        Synthetic / Demonstration terrain · vertical exaggeration {EXAG}× · rover marked by a yellow pole (not to scale) · drag to orbit, scroll to zoom, right-drag to pan
      </p>
    </div>
  );
});
