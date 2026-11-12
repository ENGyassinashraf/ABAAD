import type { Region } from "@/lib/api";
import { formatCoord } from "@/lib/api";
import { messages as t } from "@/i18n/en";

/**
 * Schematic locator for a planetary reference region: a simple
 * equirectangular frame (longitude 0-360 E, latitude -90..90) with the
 * gazetteer center point. It is a diagram, not a map projection of real
 * imagery, so it makes no claim beyond "where on the body".
 */
export function ReferenceLocator({ region }: { region: Region }) {
  const g = region.geometry;
  const W = 240;
  const H = 120;
  const lon360 = g ? ((g.lon % 360) + 360) % 360 : 0;
  const x = (lon360 / 360) * W;
  const y = g ? ((90 - g.lat) / 180) * H : 0;
  const isMoon = region.body === "moon";
  const fill = isMoon ? "#d9d4c7" : "#c98b62";

  return (
    <figure className="space-y-2" data-testid="reference-locator">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-xs rounded border border-olive/50" role="img"
        aria-label={g ? `${region.name}: ${formatCoord(g)}` : `${region.name}: ${t.explore.locatorNone}`}>
        <rect width={W} height={H} fill={fill} />
        {[30, 60, 90, 120, 150].map((v) => (
          <line key={`lat${v}`} x1={0} x2={W} y1={(v / 180) * H} y2={(v / 180) * H} stroke="#00000022" strokeWidth={0.5} />
        ))}
        {[60, 120, 180, 240, 300].map((v) => (
          <line key={`lon${v}`} y1={0} y2={H} x1={(v / 360) * W} x2={(v / 360) * W} stroke="#00000022" strokeWidth={0.5} />
        ))}
        {g && (
          <g>
            <circle cx={x} cy={Math.min(H - 2, Math.max(2, y))} r={5} fill="none" stroke="#3d352d" strokeWidth={2} />
            <circle cx={x} cy={Math.min(H - 2, Math.max(2, y))} r={1.8} fill="#3d352d" />
          </g>
        )}
        <text x={4} y={H - 4} fontSize={8} fill="#3d352d">0° E</text>
        <text x={W - 26} y={H - 4} fontSize={8} fill="#3d352d">360° E</text>
      </svg>
      <figcaption className="text-xs">
        {g ? (
          <>
            <span className="font-semibold">{formatCoord(g)}</span> · {g.latitude_type}, {g.crs_code} ·{" "}
            {g.source?.url ? <a className="underline" href={g.source.url} target="_blank" rel="noreferrer">{g.source.title}</a> : g.source?.title}
            {g.uncertainty_note && <span className="block text-earth/80">{g.uncertainty_note}</span>}
          </>
        ) : (
          <>
            <span className="font-semibold">{t.explore.locatorNone}.</span> {region.geometry_gap}
          </>
        )}
      </figcaption>
    </figure>
  );
}
