/** A labelled 0-100 bar. `value === null` renders "unknown", never an empty or zero bar. */
export function Meter({
  label,
  value,
  tone = "olive",
  testId,
  nullText = "—",
}: {
  label: string;
  value: number | null;
  tone?: "olive" | "terracotta" | "ochre";
  testId?: string;
  nullText?: string;
}) {
  const fill = { olive: "bg-olive", terracotta: "bg-terracotta", ochre: "bg-ochre" }[tone];
  return (
    <div className="space-y-1.5" data-testid={testId}>
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="font-medium text-fg-2">{label}</span>
        <span className="font-semibold tabular-nums text-fg" data-testid={testId ? `${testId}-value` : undefined}>
          {value === null ? nullText : `${value.toFixed(1)}`}
          {value !== null && <span className="font-normal text-muted"> / 100</span>}
        </span>
      </div>
      <div
        className="relative h-2 w-full overflow-hidden rounded-full bg-bg"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value ?? undefined}
        aria-valuetext={value === null ? "unknown" : `${value.toFixed(1)} of 100`}
      >
        {[25, 50, 75].map((v) => <span key={v} aria-hidden="true" className="absolute inset-y-0 w-px bg-line" style={{ left: `${v}%` }} />)}
        {value !== null && <div className={`h-full rounded-full ${fill} transition-[width] duration-300`} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />}
      </div>
    </div>
  );
}
