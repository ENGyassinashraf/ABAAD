import type { Precision } from "@/lib/mapView";
import { messages as t } from "@/i18n/en";

const STYLE: Record<Precision, string> = {
  source_traced_outline: "border-olive text-olive",
  approximate_outline: "border-dashed border-ochre text-ochre",
  source_traced_point: "border-olive text-olive",
  approximate_point: "border-dashed border-ochre text-ochre",
  none: "border-warn/70 text-warn",
};

/** Spatial precision is always stated in words, never by colour alone (UI spec §7.6, §11). */
export function PrecisionBadge({ precision }: { precision: Precision }) {
  return (
    <span data-testid="precision-badge" data-precision={precision}
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold ${STYLE[precision]}`}>
      {t.precision[precision]}
    </span>
  );
}
