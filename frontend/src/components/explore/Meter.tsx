/** A labelled 0-100 bar. `value === null` renders "unknown", never an empty or zero bar. */
export function Meter({
  label,
  value,
  tone = "olive",
  testId,
}: {
  label: string;
  value: number | null;
  tone?: "olive" | "terracotta" | "ochre";
  testId?: string;
}) {
  const fill = { olive: "bg-olive", terracotta: "bg-terracotta", ochre: "bg-ochre" }[tone];
  return (
    <div className="space-y-1" data-testid={testId}>
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="font-medium">{label}</span>
        <span className="font-semibold tabular-nums" data-testid={testId ? `${testId}-value` : undefined}>
          {value === null ? "—" : `${value.toFixed(1)}`}
          {value !== null && <span className="font-normal"> / 100</span>}
        </span>
      </div>
      <div
        className="h-2 w-full overflow-hidden rounded-full border border-olive/40 bg-sand"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value ?? undefined}
        aria-valuetext={value === null ? "unknown" : `${value.toFixed(1)} of 100`}
      >
        {value !== null && <div className={`h-full ${fill}`} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />}
      </div>
    </div>
  );
}
